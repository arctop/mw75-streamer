"""
Panel WebSocket relay for MW75 streamer

Broadcasts EEG data, runtime statistics, and log messages to connected
browser clients (e.g., panel.html). Sends data only when clients are
connected and releases resources on disconnect.
"""

import asyncio
import json
import logging
from typing import Set, Optional, Dict, Any
import threading

# WebSocket imports with fallback
try:
    import websockets

    WEBSOCKETS_AVAILABLE = True
except ImportError:  # pragma: no cover - optional dependency
    WEBSOCKETS_AVAILABLE = False
    websockets = None  # type: ignore

from ..utils.logging import get_logger


class PanelServer:
    """Minimal WebSocket relay for browser panel."""

    def __init__(self, host: str = "localhost", port: int = 8090):
        self.host = host
        self.port = port
        self.logger = get_logger(__name__)
        self.server: Optional[Any] = None
        self.clients: Set[Any] = set()
        self._lock = asyncio.Lock()
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._queue: Optional[asyncio.Queue] = None
        self._dispatch_task: Optional[asyncio.Task] = None
        self._thread: Optional[threading.Thread] = None

        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library not found. Install with: pip install websockets")

    async def start(self) -> None:
        """Start the WebSocket server in the current event loop."""

        async def handler(websocket: Any, path: Any = None) -> None:
            await self._on_connect(websocket)
            try:
                # Keep the connection open until closed by client
                await websocket.wait_closed()
            finally:
                await self._on_disconnect(websocket)

        self._loop = asyncio.get_running_loop()
        self.server = await websockets.serve(handler, self.host, self.port)
        # Start dispatcher
        self._queue = asyncio.Queue()
        self._dispatch_task = asyncio.create_task(self._dispatcher())
        self.logger.info(f"Panel server listening on ws://{self.host}:{self.port}/panel")

    async def stop(self) -> None:
        """Stop the WebSocket server and disconnect clients."""
        # Stop dispatcher first
        if self._dispatch_task:
            self._dispatch_task.cancel()
            try:
                await self._dispatch_task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass
            finally:
                self._dispatch_task = None

        if self.server:
            self.logger.info("Stopping panel server...")
            self.server.close()
            await self.server.wait_closed()
            self.server = None

        # Close any remaining client connections
        if self.clients:
            to_close = list(self.clients)
            for ws in to_close:
                try:
                    await ws.close()
                except Exception:
                    pass
            self.clients.clear()
        self.logger.info("Panel server stopped")

    def start_background(self) -> None:
        """Start the server on a dedicated event loop thread."""
        if self._thread and self._thread.is_alive():
            return

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.start())
                loop.run_forever()
            finally:
                try:
                    loop.run_until_complete(self.stop())
                except Exception:
                    pass
                loop.close()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop_background(self) -> None:
        """Stop the background server thread cleanly."""
        if not self._loop:
            return
        try:
            fut = asyncio.run_coroutine_threadsafe(self.stop(), self._loop)
            fut.result(timeout=2.0)
        except Exception:
            pass
        finally:
            try:
                if self._loop and self._loop.is_running():
                    self._loop.call_soon_threadsafe(self._loop.stop)
            except Exception:
                pass
            if self._thread:
                self._thread.join(timeout=2.0)
                self._thread = None

    async def _on_connect(self, websocket: Any) -> None:
        async with self._lock:
            self.clients.add(websocket)
        self.logger.info(f"Panel client connected ({len(self.clients)} active client(s))")

    async def _on_disconnect(self, websocket: Any) -> None:
        async with self._lock:
            if websocket in self.clients:
                self.clients.remove(websocket)
        self.logger.info(f"Panel client disconnected ({len(self.clients)} active client(s))")

    def _has_clients(self) -> bool:
        return len(self.clients) > 0

    async def _broadcast(self, payload: Dict[str, Any]) -> None:
        if not self._has_clients():
            return
        message = json.dumps(payload)
        disconnected = set()
        for client in list(self.clients):
            try:
                await client.send(message)
            except Exception:
                disconnected.add(client)
        if disconnected:
            async with self._lock:
                self.clients -= disconnected

    async def _dispatcher(self) -> None:
        """Background task that drains the queue and broadcasts to clients."""
        assert self._queue is not None
        while True:
            payload = await self._queue.get()
            try:
                await self._broadcast(payload)
            except Exception:
                pass
            finally:
                self._queue.task_done()

    def _enqueue(self, payload: Dict[str, Any]) -> None:
        """Thread-safe enqueue of a payload for broadcast."""
        if not self._queue or not self._loop:
            return
        try:
            if asyncio.get_event_loop() is self._loop and self._loop.is_running():
                # Same loop context
                try:
                    self._queue.put_nowait(payload)
                except asyncio.QueueFull:
                    pass
            else:
                # From another thread
                asyncio.run_coroutine_threadsafe(self._queue.put(payload), self._loop)
        except Exception:
            pass

    def publish_eeg(self, packet: Dict[str, Any]) -> None:
        """Schedule sending EEG packet to clients."""
        if not self._has_clients():
            return
        self._enqueue({"type": "eeg_data", **packet})

    def publish_stats(self, stats: Dict[str, Any]) -> None:
        """Schedule sending aggregated stats to clients."""
        if not self._has_clients():
            return
        self._enqueue({"type": "stats", **stats})

    def publish_log(self, record: Dict[str, Any]) -> None:
        """Schedule sending a log record to clients."""
        if not self._has_clients():
            return
        self._enqueue({"type": "log", **record})


class WebSocketLogHandler(logging.Handler):
    """Logging handler that forwards log records to the PanelServer."""

    def __init__(self, panel: PanelServer):
        super().__init__()
        self.panel = panel

    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover
        try:
            payload = {
                "level": record.levelname,
                "logger": record.name,
                "message": self.format(record),
                "time": getattr(record, "asctime", None),
            }
            self.panel.publish_log(payload)
        except Exception:
            # Never raise from logging handler
            pass
