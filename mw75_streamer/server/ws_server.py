"""
WebSocket Server for Remote MW75 Control

Provides a WebSocket server that allows third-party applications to:
- Connect/disconnect to MW75 device remotely
- Receive real-time EEG data
- Get status updates and logs
- Configure auto-reconnect behavior
"""

import asyncio
import json
import logging
import sys
import time
import uuid
from enum import Enum
from typing import TYPE_CHECKING, Any, Dict, Optional

# WebSocket imports with fallback
try:
    import websockets
    from websockets.legacy.server import WebSocketServerProtocol

    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    if TYPE_CHECKING:
        from websockets.legacy.server import WebSocketServerProtocol
    else:
        WebSocketServerProtocol = Any  # type: ignore[misc, assignment]

from ..data.packet_processor import EEGPacket, PacketProcessor
from ..utils.logging import get_logger

# Platform-specific imports
# For type checking, always resolve through mw75_device (it picks the platform's
# RFCOMM manager); at runtime, import only on supported platforms
if TYPE_CHECKING or sys.platform == "darwin":
    from Foundation import NSDate, NSRunLoop

    from ..device.mw75_device import MW75Device, RFCOMMManager
elif sys.platform == "win32":
    from ..device.mw75_device import MW75Device, RFCOMMManager

    # NSRunLoop pumping is macOS-only; Windows streams from a worker thread
    NSRunLoop = None
    NSDate = None
else:
    # At runtime on unsupported platforms, these will be None
    MW75Device = None
    RFCOMMManager = None
    NSRunLoop = None
    NSDate = None

# Mock device support (cross-platform)
from ..device.mock_rfcomm_manager import MockRFCOMMManager


class DeviceState(Enum):
    """MW75 device connection states"""

    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class WebSocketLogHandler(logging.Handler):
    """Custom logging handler that sends logs to all WebSocket clients"""

    def __init__(self, server: "MW75WebSocketServer"):
        super().__init__()
        self.server = server

    def emit(self, record: logging.LogRecord) -> None:
        """Send log record to all WebSocket clients"""
        try:
            # Only send if we have connected clients and a log level is set
            if self.server.clients and self.server.client_log_level:
                # Check if this log record meets the client's level threshold
                client_level_value = getattr(logging, self.server.client_log_level)
                if record.levelno >= client_level_value:
                    log_message = self.format(record)
                    # Schedule coroutine to run in the event loop from logging thread
                    if self.server._loop is not None:
                        asyncio.run_coroutine_threadsafe(
                            self.server._send_log(
                                level=record.levelname,
                                message=log_message,
                                logger_name=record.name,
                            ),
                            self.server._loop,
                        )
        except Exception:
            # Silently ignore errors in log handler to avoid recursion
            pass


class MW75WebSocketServer:
    """WebSocket server for remote MW75 device control"""

    def __init__(self, host: str = "localhost", port: int = 8080, use_mock: bool = False):
        """
        Initialize MW75 WebSocket server

        Args:
            host: Host to bind to
            port: Port to listen on
            use_mock: Use mock device for development (cross-platform)
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library not found. Install with: pip install websockets")

        if not use_mock and MW75Device is None:
            raise RuntimeError(
                "MW75Device not available on this platform (requires macOS or Windows)"
            )

        self.use_mock = use_mock
        self.host = host
        self.port = port
        self.logger = get_logger(__name__)

        # Client management - support multiple clients
        self.clients: set[WebSocketServerProtocol] = set()
        self.controlling_client: Optional[WebSocketServerProtocol] = None
        self.client_lock = asyncio.Lock()
        self.client_log_level: Optional[str] = None
        self.client_heartbeats: dict[WebSocketServerProtocol, asyncio.Task] = {}

        # Device management
        self.device: Optional[MW75Device] = None
        self.device_state = DeviceState.IDLE
        self.device_address: Optional[str] = None
        self.packet_processor: Optional[PacketProcessor] = None

        # Auto-reconnect
        self.auto_reconnect_enabled = False
        self.reconnect_task: Optional[asyncio.Task] = None

        # Heartbeat
        self.heartbeat_interval = 30.0  # seconds

        # Data streaming health monitoring
        self.last_packet_time: Optional[float] = None
        self.data_timeout_task: Optional[asyncio.Task] = None

        # Device connection task
        self.device_connection_task: Optional[asyncio.Task] = None

        # Logging handler
        self.log_handler: Optional[WebSocketLogHandler] = None

        # Server state
        self._server: Optional[Any] = None

        # Event loop reference for thread-safe task scheduling
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    async def start(self) -> None:
        """Start the WebSocket server"""
        print("=" * 80)
        print("MW75 WebSocket Server - Remote Control Mode")
        print("=" * 80)
        print(f"Starting server on ws://{self.host}:{self.port}")
        print("Waiting for client connection...")
        print("Commands: connect, disconnect, status")
        print("Press Ctrl+C to stop server")
        print("=" * 80)

        # Store event loop reference for thread-safe task scheduling
        self._loop = asyncio.get_running_loop()

        try:
            # fmt: off
            async with websockets.serve(self._handle_client, self.host, self.port) as server:  # type: ignore[arg-type]
                # fmt: on
                self._server = server
                print(f"Server ready! Listening on ws://{self.host}:{self.port}")
                print()
                # Wait forever - Ctrl+C will raise KeyboardInterrupt naturally
                await asyncio.Future()
        finally:
            await self._shutdown()

    async def _shutdown(self) -> None:
        """Clean shutdown of server and all connections"""
        print("Shutting down server...")

        # Disconnect all connected clients
        clients_to_cleanup = list(self.clients)
        for client in clients_to_cleanup:
            try:
                await self._cleanup_client(client)
            except Exception as e:
                print(f"Error during client cleanup: {e}")

        print("Server shutdown complete")

    async def _handle_client(self, websocket: WebSocketServerProtocol) -> None:
        """Handle incoming WebSocket client connection"""
        client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"

        # Accept all clients - no rejection for multiple connections
        async with self.client_lock:
            self.clients.add(websocket)
            print(f"Client connected from {client_address} (Total clients: {len(self.clients)})")
            self.logger.info(f"Client connected: {client_address}")

        try:
            # Send welcome status to this specific client
            await self._send_to_client(
                websocket,
                msg_type="status",
                data={
                    "state": self.device_state.value,
                    "message": "Client connected to MW75 server",
                    "timestamp": time.time(),
                    "battery_level": self._get_battery_level(),
                    "device_address": self.device_address,
                },
            )

            # Start per-client heartbeat
            heartbeat_task = asyncio.create_task(self._heartbeat_loop(websocket))
            self.client_heartbeats[websocket] = heartbeat_task

            # Handle messages from client
            async for message in websocket:
                try:
                    # Handle both str and bytes messages
                    if isinstance(message, bytes):
                        message_str = message.decode("utf-8")
                    else:
                        message_str = message
                    await self._process_client_message(message_str, websocket)
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    await self._send_to_client(
                        websocket,
                        msg_type="error",
                        data={
                            "message": str(e),
                            "code": "MESSAGE_PROCESSING_ERROR",
                            "timestamp": time.time(),
                        },
                    )

        except websockets.exceptions.ConnectionClosed:
            print(f"Client disconnected: {client_address}")
            self.logger.info(f"Client disconnected: {client_address}")
        except Exception as e:
            print(f"Error handling client {client_address}: {e}")
            self.logger.error(f"Error handling client {client_address}: {e}")
        finally:
            # Clean up client connection
            await self._cleanup_client(websocket)

    @staticmethod
    async def _cancel_task(task: Optional[asyncio.Task]) -> None:
        """Cancel an asyncio task gracefully"""
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _cleanup_client(self, websocket: WebSocketServerProtocol) -> None:
        """Clean up individual client connection and associated resources"""
        async with self.client_lock:
            # Remove client from set
            if websocket in self.clients:
                self.clients.discard(websocket)
                self.logger.info(f"Client removed. Remaining clients: {len(self.clients)}")

            # Cancel this client's heartbeat
            if websocket in self.client_heartbeats:
                await self._cancel_task(self.client_heartbeats[websocket])
                del self.client_heartbeats[websocket]

            # Check if this client was controlling the device
            was_controlling = websocket == self.controlling_client
            if was_controlling:
                self.controlling_client = None
                self.logger.info("Controlling client disconnected - control released")

                # Notify remaining clients that control is available
                if self.clients:
                    await self._broadcast_message(
                        msg_type="status",
                        data={
                            "state": self.device_state.value,
                            "message": "Device control released - available for new controller",
                            "timestamp": time.time(),
                            "battery_level": self._get_battery_level(),
                            "device_address": self.device_address,
                        },
                    )

            # Only disconnect device if no clients remain
            if not self.clients:
                self.logger.info("No clients remaining - cleaning up device resources")

                # Stop auto-reconnect
                self.auto_reconnect_enabled = False
                await self._cancel_task(self.reconnect_task)
                self.reconnect_task = None

                # Stop data timeout monitoring
                await self._cancel_task(self.data_timeout_task)
                self.data_timeout_task = None
                self.last_packet_time = None

                # Stop RFCOMM streaming if active (before cancelling task)
                if self.device and self.device.rfcomm_manager:
                    self.device.rfcomm_manager.stop()
                    await asyncio.sleep(0.1)  # Let the streaming loop exit gracefully

                # Cancel device connection task (its finally block will handle cleanup)
                await self._cancel_task(self.device_connection_task)
                self.device_connection_task = None

                # If device wasn't cleaned up by the task (shouldn't happen), clean up now
                if self.device:
                    self.logger.warning("Device not cleaned up by connection task, cleaning up now")
                    try:
                        await self.device.cleanup()
                    except Exception as e:
                        self.logger.error(f"Error during fallback device cleanup: {e}")
                    self.device = None
                    self.packet_processor = None
                    self.device_address = None
                    self.device_state = DeviceState.IDLE

                # Remove logging handler
                if self.log_handler:
                    top_logger = logging.getLogger("mw75_streamer")
                    top_logger.removeHandler(self.log_handler)
                    self.log_handler = None

                self.client_log_level = None
                self.logger.info("All clients disconnected - cleanup complete")

    async def _process_client_message(
        self, message: str, websocket: WebSocketServerProtocol
    ) -> None:
        """Process incoming message from client"""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            await self._send_to_client(
                websocket,
                msg_type="error",
                data={
                    "message": "Invalid JSON",
                    "code": "INVALID_JSON",
                    "timestamp": time.time(),
                },
            )
            return

        # Validate message structure
        if not isinstance(data, dict):
            await self._send_to_client(
                websocket,
                msg_type="error",
                data={
                    "message": "Message must be a JSON object",
                    "code": "INVALID_MESSAGE",
                    "timestamp": time.time(),
                },
            )
            return

        msg_id = data.get("id")
        msg_type = data.get("type")
        msg_data = data.get("data", {})

        if not msg_type:
            await self._send_to_client(
                websocket,
                msg_type="error",
                data={
                    "message": "Missing 'type' field in message",
                    "code": "MISSING_TYPE",
                    "timestamp": time.time(),
                },
                request_id=msg_id,
            )
            return

        # Route command
        if msg_type == "connect":
            await self._handle_connect_command(msg_data, msg_id, websocket)
        elif msg_type == "disconnect":
            await self._handle_disconnect_command(msg_data, msg_id, websocket)
        elif msg_type == "status":
            await self._handle_status_command(msg_data, msg_id, websocket)
        elif msg_type == "ping":
            await self._handle_ping_command(msg_id, websocket)
        elif msg_type == "broadcast":
            await self._handle_broadcast_command(msg_data, msg_id, websocket)
        else:
            await self._send_to_client(
                websocket,
                msg_type="error",
                data={
                    "message": f"Unknown command type: {msg_type}",
                    "code": "UNKNOWN_COMMAND",
                    "timestamp": time.time(),
                },
                request_id=msg_id,
            )

    async def _handle_connect_command(
        self,
        data: Dict[str, Any],
        request_id: Optional[str],
        websocket: WebSocketServerProtocol,
    ) -> None:
        """Handle connect command from client"""
        # Check if another client has control
        if self.controlling_client is not None and self.controlling_client != websocket:
            await self._send_to_client(
                websocket,
                msg_type="error",
                data={
                    "message": "Another client currently has device control",
                    "code": "DEVICE_CONTROL_TAKEN",
                    "timestamp": time.time(),
                },
                request_id=request_id,
            )
            return

        # Check current state
        if self.device_state in [DeviceState.CONNECTED, DeviceState.CONNECTING]:
            await self._send_to_client(
                websocket,
                msg_type="error",
                data={
                    "message": f"Already {self.device_state.value}",
                    "code": "ALREADY_CONNECTED",
                    "timestamp": time.time(),
                },
                request_id=request_id,
            )
            return

        # Extract parameters
        self.auto_reconnect_enabled = data.get("auto_reconnect", False)
        log_level = data.get("log_level", "ERROR").upper()

        # Validate log level
        if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            await self._send_to_client(
                websocket,
                msg_type="error",
                data={
                    "message": f"Invalid log_level: {log_level}. Must be DEBUG, INFO, WARNING, or ERROR",
                    "code": "INVALID_LOG_LEVEL",
                    "timestamp": time.time(),
                },
                request_id=request_id,
            )
            return

        # Grant control to this client
        self.controlling_client = websocket
        self.client_log_level = log_level

        # Set up logging handler (remove old one if exists, to support log level changes)
        if self.log_handler:
            top_logger = logging.getLogger("mw75_streamer")
            top_logger.removeHandler(self.log_handler)

        self.log_handler = WebSocketLogHandler(self)
        self.log_handler.setLevel(getattr(logging, log_level))
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )
        self.log_handler.setFormatter(formatter)
        top_logger = logging.getLogger("mw75_streamer")
        top_logger.addHandler(self.log_handler)

        # Send confirmation to requesting client
        await self._send_to_client(
            websocket,
            msg_type="command_ack",
            data={
                "command": "connect",
                "auto_reconnect": self.auto_reconnect_enabled,
                "log_level": log_level,
                "message": "Connect command received, initiating device connection",
            },
            request_id=request_id,
        )

        # Start device connection
        await self._connect_device()

    async def _handle_disconnect_command(
        self,
        _data: Dict[str, Any],
        request_id: Optional[str],
        websocket: WebSocketServerProtocol,
    ) -> None:
        """Handle disconnect command from client"""
        # Check if this client has control
        if self.controlling_client is not None and self.controlling_client != websocket:
            await self._send_to_client(
                websocket,
                msg_type="error",
                data={
                    "message": "Another client currently has device control",
                    "code": "DEVICE_CONTROL_TAKEN",
                    "timestamp": time.time(),
                },
                request_id=request_id,
            )
            return

        # Disable auto-reconnect
        self.auto_reconnect_enabled = False
        await self._cancel_task(self.reconnect_task)
        self.reconnect_task = None

        # Send confirmation to requesting client
        await self._send_to_client(
            websocket,
            msg_type="command_ack",
            data={"command": "disconnect", "message": "Disconnect command received"},
            request_id=request_id,
        )

        # Disconnect device
        if self.device and self.device_state in [
            DeviceState.CONNECTED,
            DeviceState.CONNECTING,
        ]:
            await self._disconnect_device()
        else:
            await self._broadcast_message(
                msg_type="status",
                data={
                    "state": DeviceState.IDLE.value,
                    "message": "No active device connection",
                    "timestamp": time.time(),
                    "battery_level": self._get_battery_level(),
                    "device_address": self.device_address,
                },
            )

    async def _handle_status_command(
        self,
        _data: Dict[str, Any],
        request_id: Optional[str],
        websocket: WebSocketServerProtocol,
    ) -> None:
        """Handle status command from client"""
        status_info = {
            "device_state": self.device_state.value,
            "auto_reconnect": self.auto_reconnect_enabled,
            "log_level": self.client_log_level or "ERROR",
            "battery_level": self._get_battery_level(),
            "device_address": self.device_address,
            "has_control": (websocket == self.controlling_client),
            "total_clients": len(self.clients),
        }

        await self._send_to_client(
            websocket,
            msg_type="status",
            data=status_info,
            request_id=request_id,
        )

    async def _handle_ping_command(
        self, request_id: Optional[str], websocket: WebSocketServerProtocol
    ) -> None:
        """Handle ping command from client"""
        await self._send_to_client(
            websocket,
            msg_type="pong",
            data={"timestamp": time.time()},
            request_id=request_id,
        )

    async def _handle_broadcast_command(
        self,
        data: Dict[str, Any],
        request_id: Optional[str],
        websocket: WebSocketServerProtocol,
    ) -> None:
        """Handle broadcast message from client - forward to all other clients"""
        # Get client address for identification
        client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"

        # Add sender information to the broadcast data
        broadcast_data = {
            "from": client_address,
            "data": data,
            "timestamp": time.time(),
        }

        # Broadcast to all clients except the sender
        await self._broadcast_message(
            msg_type="broadcast",
            data=broadcast_data,
            request_id=request_id,
            exclude=websocket,
        )

        # Send acknowledgement to sender
        await self._send_to_client(
            websocket,
            msg_type="command_ack",
            data={
                "command": "broadcast",
                "message": f"Message broadcast to {len(self.clients) - 1} other client(s)",
                "recipients": len(self.clients) - 1,
            },
            request_id=request_id,
        )

    async def _connect_device(self) -> None:
        """Connect to MW75 device"""
        if self.device_state in [DeviceState.CONNECTED, DeviceState.CONNECTING]:
            return

        try:
            self.device_state = DeviceState.CONNECTING
            await self._send_status(
                state=DeviceState.CONNECTING.value,
                message="Connecting to MW75 device...",
            )

            # Initialize packet processor
            self.packet_processor = PacketProcessor(verbose=False)

            if self.use_mock:
                # Use mock device - skip BLE, create device with mock RFCOMM manager
                # We still need PacketProcessor for data parsing
                self.logger.info("Using mock MW75 device (no hardware required)")
                # Start mock device connection in background
                self.device_connection_task = asyncio.create_task(
                    self._mock_device_connection_task()
                )
            else:
                # Use real device - Disable signal handler in device - we handle Ctrl+C at server level
                self.device = MW75Device(self._handle_device_data, setup_signal_handler=False)
                # Start device connection in background
                self.device_connection_task = asyncio.create_task(self._device_connection_task())

        except Exception as e:
            self.logger.error(f"Error initiating device connection: {e}")
            self.device_state = DeviceState.ERROR
            await self._broadcast_message(
                msg_type="error",
                data={
                    "message": f"Failed to connect to device: {e}",
                    "code": "CONNECTION_FAILED",
                    "timestamp": time.time(),
                },
            )

    async def _device_connection_task(self) -> None:
        """Background task for device connection"""
        connection_successful = False
        try:
            # Ensure device is initialized
            assert self.device is not None, "Device must be initialized before connection task"

            # Start BLE activation
            print("Discovering MW75 device via BLE...")
            self.logger.info("Starting BLE discovery and activation...")
            device_name = await self.device.ble_manager.discover_and_activate()
            if not device_name:
                print("MW75 device not found")
                self.logger.error("BLE activation failed")
                self.device_state = DeviceState.ERROR
                await self._broadcast_message(
                    msg_type="error",
                    data={
                        "message": "MW75 device not found or BLE activation failed",
                        "code": "BLE_ACTIVATION_FAILED",
                        "timestamp": time.time(),
                    },
                )
                if self.auto_reconnect_enabled:
                    await self._start_reconnect_loop()
                return

            print(f"MW75 device found: {device_name}")

            # Disconnect BLE before RFCOMM (macOS Taho compatibility)
            print("Activating EEG mode...")
            self.logger.info("Disconnecting BLE (required for RFCOMM on macOS Taho)...")
            await self.device.ble_manager.disconnect_after_activation()
            await asyncio.sleep(0.5)

            # Establish RFCOMM connection
            print("Establishing data connection (RFCOMM)...")
            self.logger.info("Establishing RFCOMM connection...")
            self.device.rfcomm_manager = RFCOMMManager(device_name, self.device.data_callback)
            if not self.device.rfcomm_manager.connect():
                print("RFCOMM connection failed")
                self.logger.error("RFCOMM connection failed")
                self.device_state = DeviceState.ERROR
                await self._broadcast_message(
                    msg_type="error",
                    data={
                        "message": "RFCOMM connection failed",
                        "code": "RFCOMM_CONNECTION_FAILED",
                        "timestamp": time.time(),
                    },
                )
                if self.auto_reconnect_enabled:
                    await self._start_reconnect_loop()
                return

            # Connection successful - update state and notify
            connection_successful = True
            self.device_state = DeviceState.CONNECTED
            # Get device address from RFCOMM manager
            self.device_address = self.device.rfcomm_manager.device_address
            await self._send_status(
                state=DeviceState.CONNECTED.value,
                message="Successfully connected to MW75 device, streaming EEG data",
            )
            print(f"Successfully connected to MW75 device! (MAC: {self.device_address})")
            print("Streaming..")

            # Start data timeout monitoring
            self.last_packet_time = None
            self.data_timeout_task = asyncio.create_task(self._data_timeout_monitor())
            self.logger.debug("Data timeout monitoring task started")

            # Run RFCOMM event loop interleaved with asyncio
            # NSRunLoop MUST be on main thread for delegates to work
            self.logger.info("Starting data streaming loop (interleaved with asyncio)...")
            await self._run_rfcomm_streaming()

        except Exception as e:
            self.logger.error(f"Device connection error: {e}")
            self.device_state = DeviceState.ERROR
            await self._broadcast_message(
                msg_type="error",
                data={
                    "message": f"Device error: {e}",
                    "code": "DEVICE_ERROR",
                    "timestamp": time.time(),
                },
            )

            # Clean up device on error
            if self.device:
                try:
                    await self.device.cleanup()
                    self.device = None
                    self.packet_processor = None
                    self.device_address = None
                except Exception as cleanup_error:
                    self.logger.error(f"Error during cleanup after device error: {cleanup_error}")
                    # Still clear references even on error
                    self.device = None
                    self.packet_processor = None
                    self.device_address = None

            # Start auto-reconnect if enabled
            if self.auto_reconnect_enabled:
                await self._start_reconnect_loop()
        finally:
            # Stop data timeout monitoring
            if self.data_timeout_task and not self.data_timeout_task.done():
                await self._cancel_task(self.data_timeout_task)
                self.data_timeout_task = None
                self.last_packet_time = None
                self.logger.debug("Data timeout monitoring task stopped")

            # Connection ended - clean up device resources
            if connection_successful:
                print("Device streaming ended")
                self.device_state = DeviceState.DISCONNECTED
                await self._send_status(
                    state=DeviceState.DISCONNECTED.value,
                    message="Device connection closed",
                )

                # Clean up device to properly reset state for next connection
                if self.device:
                    try:
                        await self.device.cleanup()
                        self.device = None
                        self.packet_processor = None
                        self.device_address = None
                    except Exception as cleanup_error:
                        self.logger.error(f"Error during device cleanup: {cleanup_error}")
                        # Still clear references even on error
                        self.device = None
                        self.packet_processor = None
                        self.device_address = None

                # Start auto-reconnect if enabled
                if self.auto_reconnect_enabled:
                    await self._start_reconnect_loop()

    async def _mock_device_connection_task(self) -> None:
        """Background task for mock device connection (simplified flow)"""
        connection_successful = False
        mock_rfcomm_manager: Optional[MockRFCOMMManager] = None

        try:
            # Skip BLE entirely for mock device
            print("Connecting to mock MW75 device...")
            self.logger.info("Using mock RFCOMM manager (no BLE required)")

            # Create mock RFCOMM manager
            mock_rfcomm_manager = MockRFCOMMManager("MW75-MOCK", self._handle_device_data)

            if not mock_rfcomm_manager.connect():
                print("Mock RFCOMM connection failed")
                self.logger.error("Mock RFCOMM connection failed")
                self.device_state = DeviceState.ERROR
                await self._broadcast_message(
                    msg_type="error",
                    data={
                        "message": "Mock RFCOMM connection failed",
                        "code": "MOCK_CONNECTION_FAILED",
                        "timestamp": time.time(),
                    },
                )
                return

            # Connection successful
            connection_successful = True
            self.device_state = DeviceState.CONNECTED
            self.device_address = mock_rfcomm_manager.device_address
            await self._send_status(
                state=DeviceState.CONNECTED.value,
                message="Successfully connected to mock MW75 device, streaming synthetic EEG data",
            )
            print("Successfully connected to mock MW75 device!")
            print("Streaming synthetic data at ~500Hz...")

            # Start data timeout monitoring
            self.last_packet_time = None
            self.data_timeout_task = asyncio.create_task(self._data_timeout_monitor())
            self.logger.debug("Data timeout monitoring task started")

            # Run mock streaming loop (blocking call runs in thread)
            self.logger.info("Starting mock data streaming loop...")
            await asyncio.get_event_loop().run_in_executor(
                None, mock_rfcomm_manager.run_until_stopped
            )

        except Exception as e:
            self.logger.error(f"Mock device connection error: {e}")
            self.device_state = DeviceState.ERROR
            await self._broadcast_message(
                msg_type="error",
                data={
                    "message": f"Mock device error: {e}",
                    "code": "MOCK_DEVICE_ERROR",
                    "timestamp": time.time(),
                },
            )

        finally:
            # Stop data timeout monitoring
            if self.data_timeout_task and not self.data_timeout_task.done():
                await self._cancel_task(self.data_timeout_task)
                self.data_timeout_task = None
                self.last_packet_time = None
                self.logger.debug("Data timeout monitoring task stopped")

            # Clean up mock manager
            if mock_rfcomm_manager:
                try:
                    mock_rfcomm_manager.close()
                except Exception as cleanup_error:
                    self.logger.error(f"Error closing mock RFCOMM: {cleanup_error}")

            # Connection ended
            if connection_successful:
                print("Mock device streaming ended")
                self.device_state = DeviceState.DISCONNECTED
                await self._send_status(
                    state=DeviceState.DISCONNECTED.value,
                    message="Mock device connection closed",
                )

                # Clear packet processor and device address
                self.packet_processor = None
                self.device_address = None

    async def _run_rfcomm_streaming(self) -> None:
        """
        Run RFCOMM streaming loop interleaved with asyncio

        On macOS, NSRunLoop must run on the main thread for delegates to fire,
        so we run it in small chunks and yield to asyncio between each chunk.
        On Windows, the manager's blocking socket receive loop runs in a worker
        thread instead; data callbacks are already thread-safe.
        """
        if not self.device or not self.device.rfcomm_manager:
            return

        if NSRunLoop is None:
            rfcomm_manager = self.device.rfcomm_manager
            await asyncio.get_running_loop().run_in_executor(None, rfcomm_manager.run_until_stopped)
            stream_error = getattr(rfcomm_manager, "stream_error", None)
            if stream_error:
                self.logger.error(f"Data streaming ended unexpectedly: {stream_error}")
            return

        runloop = NSRunLoop.currentRunLoop()

        while not self.device.rfcomm_manager.should_stop:
            # Run NSRunLoop for 1ms to process RFCOMM events
            runloop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.001))

            # Yield to asyncio event loop
            await asyncio.sleep(0)

    async def _disconnect_device(self) -> None:
        """Disconnect from MW75 device"""
        if not self.device:
            self.device_state = DeviceState.IDLE
            return

        try:
            self.device_state = DeviceState.DISCONNECTING
            await self._send_status(
                state=DeviceState.DISCONNECTING.value,
                message="Disconnecting from MW75 device...",
            )
            print("Disconnecting from MW75 device...")

            # Stop RFCOMM streaming loop
            if self.device.rfcomm_manager:
                self.device.rfcomm_manager.stop()

            # Give it a moment to process the stop
            await asyncio.sleep(0.1)

            await self.device.cleanup()
            self.device = None
            self.packet_processor = None
            self.device_address = None

            self.device_state = DeviceState.IDLE
            await self._send_status(
                state=DeviceState.IDLE.value, message="Disconnected from MW75 device"
            )
            print("Disconnected from MW75 device")

        except Exception as e:
            self.logger.error(f"Error disconnecting device: {e}")
            self.device_state = DeviceState.ERROR
            await self._broadcast_message(
                msg_type="error",
                data={
                    "message": f"Disconnect error: {e}",
                    "code": "DISCONNECT_ERROR",
                    "timestamp": time.time(),
                },
            )

    async def _start_reconnect_loop(self) -> None:
        """Start auto-reconnect loop"""
        if not self.auto_reconnect_enabled:
            return

        if self.reconnect_task and not self.reconnect_task.done():
            return  # Already reconnecting

        self.reconnect_task = asyncio.create_task(self._auto_reconnect_loop())

    async def _auto_reconnect_loop(self) -> None:
        """Auto-reconnect loop with exponential backoff"""
        attempt = 0
        max_attempts = 10

        while self.auto_reconnect_enabled and attempt < max_attempts:
            # Calculate backoff delay (exponential with max 30s)
            delay = min(2**attempt, 30)
            attempt += 1

            await self._send_status(
                state="reconnecting",
                message=f"Auto-reconnect attempt {attempt}/{max_attempts} in {delay}s...",
            )

            await asyncio.sleep(delay)

            if not self.auto_reconnect_enabled:
                break

            # Attempt reconnection
            try:
                await self._connect_device()
                # Wait for connection to establish
                await asyncio.sleep(2)

                if self.device_state == DeviceState.CONNECTED:
                    await self._send_status(
                        state=DeviceState.CONNECTED.value,
                        message=f"Auto-reconnect successful after {attempt} attempts",
                    )
                    return  # Success!

            except Exception as e:
                self.logger.error(f"Auto-reconnect attempt {attempt} failed: {e}")
                await self._broadcast_message(
                    msg_type="error",
                    data={
                        "message": f"Reconnect attempt {attempt} failed: {e}",
                        "code": "RECONNECT_FAILED",
                        "timestamp": time.time(),
                    },
                )

        # Max attempts reached
        if self.auto_reconnect_enabled and attempt >= max_attempts:
            await self._broadcast_message(
                msg_type="error",
                data={
                    "message": f"Auto-reconnect failed after {max_attempts} attempts",
                    "code": "RECONNECT_EXHAUSTED",
                    "timestamp": time.time(),
                },
            )
            self.auto_reconnect_enabled = False

    def _handle_device_data(self, data: bytes) -> None:
        """Handle raw data received from MW75 device"""
        if not self.packet_processor:
            return

        try:
            # Process data into packets
            self.packet_processor.process_data_buffer(
                data, self._handle_eeg_packet, self._handle_other_event
            )
        except Exception as e:
            self.logger.error(f"Error processing device data: {e}")

    def _handle_eeg_packet(self, packet: EEGPacket) -> None:
        """Handle processed EEG packet (called from worker thread)"""
        if not self.clients:
            return

        try:
            # Update last packet timestamp for health monitoring
            self.last_packet_time = time.time()

            # Schedule coroutine to run in the event loop from worker thread
            if self._loop is not None:
                asyncio.run_coroutine_threadsafe(self._send_eeg_data(packet), self._loop)
        except Exception as e:
            self.logger.error(f"Error handling EEG packet: {e}")

    def _handle_other_event(self, packet: bytes) -> None:
        """
        Handle non-EEG events

        Currently not forwarding other events to client.
        TODO: Consider forwarding device status events if needed in the future.
        """
        pass

    async def _heartbeat_loop(self, websocket: WebSocketServerProtocol) -> None:
        """Heartbeat loop to keep connection alive for a specific client"""
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)

                # Send heartbeat ping to this specific client
                # Include battery level and device address for periodic updates
                await self._send_to_client(
                    websocket,
                    msg_type="heartbeat",
                    data={
                        "timestamp": time.time(),
                        "battery_level": self._get_battery_level(),
                        "device_address": self.device_address,
                    },
                )

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Heartbeat error: {e}")

    async def _data_timeout_monitor(self) -> None:
        """
        Monitor data stream health and detect device disconnection

        Checks periodically if data packets are still arriving from the device.
        If no packets received within DATA_PACKET_TIMEOUT, assumes device is
        disconnected (e.g., powered off) and triggers cleanup/reconnect.
        """
        from ..config import DATA_PACKET_TIMEOUT, DATA_TIMEOUT_CHECK_INTERVAL

        try:
            # Wait for first packet to arrive before starting monitoring
            while self.last_packet_time is None:
                await asyncio.sleep(DATA_TIMEOUT_CHECK_INTERVAL)

                # Exit if device state changed
                if self.device_state != DeviceState.CONNECTED:
                    self.logger.debug("Data timeout monitor exiting - device not connected")
                    return

            self.logger.debug(f"Data timeout monitoring started (timeout={DATA_PACKET_TIMEOUT}s)")

            # Monitor loop
            while self.device_state == DeviceState.CONNECTED:
                await asyncio.sleep(DATA_TIMEOUT_CHECK_INTERVAL)

                # Calculate time since last packet
                if self.last_packet_time is not None:
                    time_since_last_packet = time.time() - self.last_packet_time

                    # Check for timeout
                    if time_since_last_packet > DATA_PACKET_TIMEOUT:
                        self.logger.warning(
                            f"Data timeout detected: {time_since_last_packet:.1f}s since last packet "
                            f"(threshold: {DATA_PACKET_TIMEOUT}s)"
                        )

                        # Also check RFCOMM state as secondary signal
                        rfcomm_still_connected = (
                            self.device
                            and self.device.rfcomm_manager
                            and self.device.rfcomm_manager.connected
                        )

                        self.logger.info(
                            f"Device appears disconnected (RFCOMM state: {rfcomm_still_connected})"
                        )

                        # Notify clients of timeout
                        await self._broadcast_message(
                            msg_type="error",
                            data={
                                "message": f"Device data stream timeout ({time_since_last_packet:.1f}s without data)",
                                "code": "DATA_STREAM_TIMEOUT",
                                "timestamp": time.time(),
                            },
                        )

                        # Trigger disconnect and cleanup
                        await self._handle_data_timeout()
                        return

        except asyncio.CancelledError:
            self.logger.debug("Data timeout monitor cancelled")
        except Exception as e:
            self.logger.error(f"Error in data timeout monitor: {e}")

    async def _handle_data_timeout(self) -> None:
        """
        Handle data stream timeout (device likely powered off)

        Performs cleanup and triggers auto-reconnect if enabled.
        """
        if self.device_state not in [DeviceState.CONNECTED, DeviceState.CONNECTING]:
            return

        try:
            self.logger.info("Handling data timeout - initiating cleanup")
            self.device_state = DeviceState.DISCONNECTING

            await self._send_status(
                state=DeviceState.DISCONNECTING.value,
                message="Device connection lost (data timeout detected)",
            )

            # Stop RFCOMM streaming loop
            if self.device and self.device.rfcomm_manager:
                self.device.rfcomm_manager.stop()
                await asyncio.sleep(0.1)

            # Clean up device resources
            if self.device:
                try:
                    await self.device.cleanup()
                except Exception as cleanup_error:
                    self.logger.error(f"Error during timeout cleanup: {cleanup_error}")
                finally:
                    self.device = None
                    self.packet_processor = None
                    self.device_address = None
                    self.last_packet_time = None

            self.device_state = DeviceState.DISCONNECTED
            await self._send_status(
                state=DeviceState.DISCONNECTED.value,
                message="Device disconnected due to data timeout",
            )

            # Trigger auto-reconnect if enabled
            if self.auto_reconnect_enabled:
                self.logger.info("Auto-reconnect enabled - starting reconnect loop")
                await self._start_reconnect_loop()

        except Exception as e:
            self.logger.error(f"Error handling data timeout: {e}")
            self.device_state = DeviceState.ERROR
            await self._broadcast_message(
                msg_type="error",
                data={
                    "message": f"Error during timeout handling: {e}",
                    "code": "TIMEOUT_HANDLER_ERROR",
                    "timestamp": time.time(),
                },
            )

    async def _send_to_client(
        self,
        websocket: WebSocketServerProtocol,
        msg_type: str,
        data: Dict[str, Any],
        request_id: Optional[str] = None,
    ) -> None:
        """Send message to a specific client"""
        try:
            message = {
                "id": request_id if request_id else str(uuid.uuid4()),
                "type": msg_type,
                "data": data,
            }

            await websocket.send(json.dumps(message))
        except websockets.exceptions.ConnectionClosed as e:
            self.logger.warning(f"Client connection closed during send: {e}")
            # Clean up the dead client
            try:
                await self._cleanup_client(websocket)
            except Exception as cleanup_error:
                self.logger.error(f"Error cleaning up dead client: {cleanup_error}")
        except Exception as e:
            self.logger.error(f"Error sending message to client: {e}")

    async def _broadcast_message(
        self,
        msg_type: str,
        data: Dict[str, Any],
        request_id: Optional[str] = None,
        exclude: Optional[WebSocketServerProtocol] = None,
    ) -> None:
        """Broadcast message to all connected clients, optionally excluding one"""
        message = {
            "id": request_id if request_id else str(uuid.uuid4()),
            "type": msg_type,
            "data": data,
        }
        message_json = json.dumps(message)

        # Collect dead clients for cleanup
        dead_clients = []

        # Send to all clients except the excluded one
        for client in list(self.clients):
            if exclude and client == exclude:
                continue
            try:
                await client.send(message_json)
            except websockets.exceptions.ConnectionClosed as e:
                self.logger.warning(f"Client connection closed during broadcast: {e}")
                dead_clients.append(client)
            except Exception as e:
                self.logger.error(f"Error broadcasting to client: {e}")
                dead_clients.append(client)

        # Clean up dead clients after broadcast loop
        for dead_client in dead_clients:
            try:
                await self._cleanup_client(dead_client)
            except Exception as e:
                self.logger.error(f"Error cleaning up dead client: {e}")

    def _get_battery_level(self) -> Optional[int]:
        """Get current battery level from device"""
        if self.use_mock:
            return 84
        if self.device and self.device.ble_manager:
            return self.device.ble_manager.battery_level
        return None

    async def _send_status(self, state: str, message: str) -> None:
        """Send status update to all clients"""
        await self._broadcast_message(
            msg_type="status",
            data={
                "state": state,
                "message": message,
                "timestamp": time.time(),
                "battery_level": self._get_battery_level(),
                "device_address": self.device_address,
            },
        )

    async def _send_log(self, level: str, message: str, logger_name: str) -> None:
        """Send log message to all clients"""
        await self._broadcast_message(
            msg_type="log",
            data={
                "level": level,
                "message": message,
                "logger": logger_name,
                "timestamp": time.time(),
            },
        )

    async def _send_eeg_data(self, packet: EEGPacket) -> None:
        """Send EEG data packet to all clients"""
        eeg_data = {
            "timestamp": packet.timestamp,
            "event_id": packet.event_id,
            "counter": packet.counter,
            "ref": packet.ref,
            "drl": packet.drl,
            "channels": {f"ch{i + 1}": packet.channels[i] for i in range(len(packet.channels))},
            "feature_status": packet.feature_status,
        }

        await self._broadcast_message(msg_type="eeg_data", data=eeg_data)
