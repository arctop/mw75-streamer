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
from typing import Optional, Dict, Any, TYPE_CHECKING
from enum import Enum

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

from ..utils.logging import get_logger

# Platform-specific imports
# For type checking, always import the types; at runtime, only on macOS
if TYPE_CHECKING or sys.platform == "darwin":
    from ..device.mw75_device import MW75Device
    from ..device.rfcomm_manager import RFCOMMManager
    from ..data.packet_processor import PacketProcessor, EEGPacket
    from Foundation import NSRunLoop, NSDate

if sys.platform != "darwin":
    # At runtime on non-macOS, these will be None
    MW75Device = None  # type: ignore[assignment, misc]  # noqa: F811
    RFCOMMManager = None  # type: ignore[assignment, misc]  # noqa: F811
    PacketProcessor = None  # type: ignore[assignment, misc]  # noqa: F811
    EEGPacket = None  # type: ignore[assignment, misc]  # noqa: F811
    NSRunLoop = None  # noqa: F811
    NSDate = None  # noqa: F811


class DeviceState(Enum):
    """MW75 device connection states"""

    IDLE = "idle"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    ERROR = "error"


class WebSocketLogHandler(logging.Handler):
    """Custom logging handler that sends logs to WebSocket client"""

    def __init__(self, server: "MW75WebSocketServer"):
        super().__init__()
        self.server = server

    def emit(self, record: logging.LogRecord) -> None:
        """Send log record to WebSocket client"""
        try:
            # Only send if we have a connected client and it's at or above their level
            if self.server.current_client and self.server.client_log_level:
                # Check if this log record meets the client's level threshold
                client_level_value = getattr(logging, self.server.client_log_level)
                if record.levelno >= client_level_value:
                    log_message = self.format(record)
                    # Create async task (we're on main thread with running event loop)
                    asyncio.create_task(
                        self.server._send_log(
                            level=record.levelname, message=log_message, logger_name=record.name
                        )
                    )
        except Exception:
            # Silently ignore errors in log handler to avoid recursion
            pass


class MW75WebSocketServer:
    """WebSocket server for remote MW75 device control"""

    def __init__(self, host: str = "localhost", port: int = 8080):
        """
        Initialize MW75 WebSocket server

        Args:
            host: Host to bind to
            port: Port to listen on
        """
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library not found. Install with: pip install websockets")

        if MW75Device is None:
            raise RuntimeError("MW75Device not available on this platform (macOS only)")

        self.host = host
        self.port = port
        self.logger = get_logger(__name__)

        # Client management
        self.current_client: Optional[WebSocketServerProtocol] = None
        self.client_lock = asyncio.Lock()
        self.client_log_level: Optional[str] = None

        # Device management
        self.device: Optional[MW75Device] = None
        self.device_state = DeviceState.IDLE
        self.packet_processor: Optional[PacketProcessor] = None

        # Auto-reconnect
        self.auto_reconnect_enabled = False
        self.reconnect_task: Optional[asyncio.Task] = None

        # Heartbeat
        self.heartbeat_interval = 30.0  # seconds
        self.heartbeat_task: Optional[asyncio.Task] = None

        # Device connection task
        self.device_connection_task: Optional[asyncio.Task] = None

        # Logging handler
        self.log_handler: Optional[WebSocketLogHandler] = None

        # Server state
        self._server: Optional[Any] = None

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

        try:
            async with websockets.serve(self._handle_client, self.host, self.port) as server:  # type: ignore[arg-type]
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

        # Disconnect any connected client
        if self.current_client:
            try:
                await self._cleanup_client()
            except Exception as e:
                print(f"Error during client cleanup: {e}")

        print("Server shutdown complete")

    async def _handle_client(self, websocket: WebSocketServerProtocol) -> None:
        """Handle incoming WebSocket client connection"""
        client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"

        # Check if we already have a client
        async with self.client_lock:
            if self.current_client is not None:
                self.logger.warning(
                    f"Rejected connection from {client_address} - client already connected"
                )
                await websocket.send(
                    json.dumps(
                        {
                            "id": str(uuid.uuid4()),
                            "type": "error",
                            "data": {
                                "message": "Server already has a connected client",
                                "code": "CLIENT_ALREADY_CONNECTED",
                            },
                        }
                    )
                )
                await websocket.close()
                return

            # Accept the client
            self.current_client = websocket
            print(f"Client connected from {client_address}")
            self.logger.info(f"Client connected: {client_address}")

        try:
            # Send welcome status
            await self._send_status(
                state=self.device_state.value, message="Client connected to MW75 server"
            )

            # Start heartbeat
            self.heartbeat_task = asyncio.create_task(self._heartbeat_loop())

            # Handle messages from client
            async for message in websocket:
                try:
                    # Handle both str and bytes messages
                    if isinstance(message, bytes):
                        message_str = message.decode("utf-8")
                    else:
                        message_str = message
                    await self._process_client_message(message_str)
                except Exception as e:
                    self.logger.error(f"Error processing message: {e}")
                    await self._send_error(message=str(e), code="MESSAGE_PROCESSING_ERROR")

        except websockets.exceptions.ConnectionClosed:
            print(f"Client disconnected: {client_address}")
            self.logger.info(f"Client disconnected: {client_address}")
        except Exception as e:
            print(f"Error handling client {client_address}: {e}")
            self.logger.error(f"Error handling client {client_address}: {e}")
        finally:
            # Clean up client connection
            await self._cleanup_client()

    @staticmethod
    async def _cancel_task(task: Optional[asyncio.Task]) -> None:
        """Cancel an asyncio task gracefully"""
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    async def _cleanup_client(self) -> None:
        """Clean up client connection and associated resources"""
        async with self.client_lock:
            # Cancel heartbeat
            await self._cancel_task(self.heartbeat_task)
            self.heartbeat_task = None

            # Stop auto-reconnect
            self.auto_reconnect_enabled = False
            await self._cancel_task(self.reconnect_task)
            self.reconnect_task = None

            # Cancel device connection task
            await self._cancel_task(self.device_connection_task)
            self.device_connection_task = None

            # Disconnect from device
            if self.device and self.device_state in [DeviceState.CONNECTED, DeviceState.CONNECTING]:
                self.logger.info("Client disconnected - disconnecting from MW75 device")
                await self._disconnect_device()

            # Remove logging handler
            if self.log_handler:
                top_logger = logging.getLogger("mw75_streamer")
                top_logger.removeHandler(self.log_handler)
                self.log_handler = None

            self.current_client = None
            self.client_log_level = None
            self.logger.info("Client cleanup complete")

    async def _process_client_message(self, message: str) -> None:
        """Process incoming message from client"""
        try:
            data = json.loads(message)
        except json.JSONDecodeError:
            await self._send_error(message="Invalid JSON", code="INVALID_JSON")
            return

        # Validate message structure
        if not isinstance(data, dict):
            await self._send_error(message="Message must be a JSON object", code="INVALID_MESSAGE")
            return

        msg_id = data.get("id")
        msg_type = data.get("type")
        msg_data = data.get("data", {})

        if not msg_type:
            await self._send_error(
                message="Missing 'type' field in message", code="MISSING_TYPE", request_id=msg_id
            )
            return

        # Route command
        if msg_type == "connect":
            await self._handle_connect_command(msg_data, msg_id)
        elif msg_type == "disconnect":
            await self._handle_disconnect_command(msg_data, msg_id)
        elif msg_type == "status":
            await self._handle_status_command(msg_data, msg_id)
        elif msg_type == "ping":
            await self._handle_ping_command(msg_id)
        else:
            await self._send_error(
                message=f"Unknown command type: {msg_type}",
                code="UNKNOWN_COMMAND",
                request_id=msg_id,
            )

    async def _handle_connect_command(
        self, data: Dict[str, Any], request_id: Optional[str]
    ) -> None:
        """Handle connect command from client"""
        # Check current state
        if self.device_state in [DeviceState.CONNECTED, DeviceState.CONNECTING]:
            await self._send_error(
                message=f"Already {self.device_state.value}",
                code="ALREADY_CONNECTED",
                request_id=request_id,
            )
            return

        # Extract parameters
        self.auto_reconnect_enabled = data.get("auto_reconnect", False)
        log_level = data.get("log_level", "ERROR").upper()

        # Validate log level
        if log_level not in ["DEBUG", "INFO", "WARNING", "ERROR"]:
            await self._send_error(
                message=f"Invalid log_level: {log_level}. Must be DEBUG, INFO, WARNING, or ERROR",
                code="INVALID_LOG_LEVEL",
                request_id=request_id,
            )
            return

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

        # Send confirmation
        await self._send_message(
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
        self, _data: Dict[str, Any], request_id: Optional[str]
    ) -> None:
        """Handle disconnect command from client"""
        # Disable auto-reconnect
        self.auto_reconnect_enabled = False
        await self._cancel_task(self.reconnect_task)
        self.reconnect_task = None

        # Send confirmation
        await self._send_message(
            msg_type="command_ack",
            data={"command": "disconnect", "message": "Disconnect command received"},
            request_id=request_id,
        )

        # Disconnect device
        if self.device and self.device_state in [DeviceState.CONNECTED, DeviceState.CONNECTING]:
            await self._disconnect_device()
        else:
            await self._send_status(
                state=DeviceState.IDLE.value, message="No active device connection"
            )

    async def _handle_status_command(
        self, _data: Dict[str, Any], request_id: Optional[str]
    ) -> None:
        """Handle status command from client"""
        status_info = {
            "device_state": self.device_state.value,
            "auto_reconnect": self.auto_reconnect_enabled,
            "log_level": self.client_log_level or "ERROR",
        }

        await self._send_message(msg_type="status", data=status_info, request_id=request_id)

    async def _handle_ping_command(self, request_id: Optional[str]) -> None:
        """Handle ping command from client"""
        await self._send_message(
            msg_type="pong",
            data={"timestamp": time.time()},
            request_id=request_id,
        )

    async def _connect_device(self) -> None:
        """Connect to MW75 device"""
        if self.device_state in [DeviceState.CONNECTED, DeviceState.CONNECTING]:
            return

        try:
            self.device_state = DeviceState.CONNECTING
            await self._send_status(
                state=DeviceState.CONNECTING.value, message="Connecting to MW75 device..."
            )

            # Initialize packet processor and device
            self.packet_processor = PacketProcessor(verbose=False)
            # Disable signal handler in device - we handle Ctrl+C at server level
            self.device = MW75Device(self._handle_device_data, setup_signal_handler=False)

            # Start device connection in background
            self.device_connection_task = asyncio.create_task(self._device_connection_task())

        except Exception as e:
            self.logger.error(f"Error initiating device connection: {e}")
            self.device_state = DeviceState.ERROR
            await self._send_error(
                message=f"Failed to connect to device: {e}", code="CONNECTION_FAILED"
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
                await self._send_error(
                    message="MW75 device not found or BLE activation failed",
                    code="BLE_ACTIVATION_FAILED",
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
                await self._send_error(
                    message="RFCOMM connection failed", code="RFCOMM_CONNECTION_FAILED"
                )
                if self.auto_reconnect_enabled:
                    await self._start_reconnect_loop()
                return

            # Connection successful - update state and notify
            connection_successful = True
            self.device_state = DeviceState.CONNECTED
            await self._send_status(
                state=DeviceState.CONNECTED.value,
                message="Successfully connected to MW75 device, streaming EEG data",
            )
            print("Successfully connected to MW75 device!")
            print("Streaming..")

            # Run RFCOMM event loop interleaved with asyncio
            # NSRunLoop MUST be on main thread for delegates to work
            self.logger.info("Starting data streaming loop (interleaved with asyncio)...")
            await self._run_rfcomm_streaming()

        except Exception as e:
            self.logger.error(f"Device connection error: {e}")
            self.device_state = DeviceState.ERROR
            await self._send_error(message=f"Device error: {e}", code="DEVICE_ERROR")

            # Start auto-reconnect if enabled
            if self.auto_reconnect_enabled:
                await self._start_reconnect_loop()
        finally:
            # Connection ended
            if connection_successful:
                print("Device streaming ended")
                self.device_state = DeviceState.DISCONNECTED
                await self._send_status(
                    state=DeviceState.DISCONNECTED.value,
                    message="Device connection closed",
                )

                # Start auto-reconnect if enabled
                if self.auto_reconnect_enabled:
                    await self._start_reconnect_loop()

    async def _run_rfcomm_streaming(self) -> None:
        """
        Run RFCOMM streaming loop interleaved with asyncio

        NSRunLoop must run on main thread for delegates to fire,
        so we run it in small chunks and yield to asyncio between each chunk.
        """
        if not self.device or not self.device.rfcomm_manager:
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
                state=DeviceState.DISCONNECTING.value, message="Disconnecting from MW75 device..."
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

            self.device_state = DeviceState.IDLE
            await self._send_status(
                state=DeviceState.IDLE.value, message="Disconnected from MW75 device"
            )
            print("Disconnected from MW75 device")

        except Exception as e:
            self.logger.error(f"Error disconnecting device: {e}")
            self.device_state = DeviceState.ERROR
            await self._send_error(message=f"Disconnect error: {e}", code="DISCONNECT_ERROR")

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
                await self._send_error(
                    message=f"Reconnect attempt {attempt} failed: {e}",
                    code="RECONNECT_FAILED",
                )

        # Max attempts reached
        if self.auto_reconnect_enabled and attempt >= max_attempts:
            await self._send_error(
                message=f"Auto-reconnect failed after {max_attempts} attempts",
                code="RECONNECT_EXHAUSTED",
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
        """Handle processed EEG packet (called from main thread)"""
        if not self.current_client:
            return

        try:
            # Create async task to send EEG data
            asyncio.create_task(self._send_eeg_data(packet))
        except Exception as e:
            self.logger.error(f"Error handling EEG packet: {e}")

    def _handle_other_event(self, packet: bytes) -> None:
        """
        Handle non-EEG events

        Currently not forwarding other events to client.
        TODO: Consider forwarding device status events if needed in the future.
        """
        pass

    async def _heartbeat_loop(self) -> None:
        """Heartbeat loop to keep connection alive"""
        try:
            while True:
                await asyncio.sleep(self.heartbeat_interval)

                # Send heartbeat ping (websockets lib handles connection health)
                await self._send_message(msg_type="heartbeat", data={"timestamp": time.time()})

        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.error(f"Heartbeat error: {e}")

    async def _send_message(
        self, msg_type: str, data: Dict[str, Any], request_id: Optional[str] = None
    ) -> None:
        """Send message to client"""
        if not self.current_client:
            return

        try:
            message = {
                "id": request_id if request_id else str(uuid.uuid4()),
                "type": msg_type,
                "data": data,
            }

            await self.current_client.send(json.dumps(message))
        except Exception as e:
            self.logger.error(f"Error sending message: {e}")

    async def _send_status(self, state: str, message: str) -> None:
        """Send status update to client"""
        await self._send_message(
            msg_type="status",
            data={"state": state, "message": message, "timestamp": time.time()},
        )

    async def _send_error(self, message: str, code: str, request_id: Optional[str] = None) -> None:
        """Send error message to client"""
        await self._send_message(
            msg_type="error",
            data={"message": message, "code": code, "timestamp": time.time()},
            request_id=request_id,
        )

    async def _send_log(self, level: str, message: str, logger_name: str) -> None:
        """Send log message to client"""
        await self._send_message(
            msg_type="log",
            data={
                "level": level,
                "message": message,
                "logger": logger_name,
                "timestamp": time.time(),
            },
        )

    async def _send_eeg_data(self, packet: EEGPacket) -> None:
        """Send EEG data packet to client"""
        eeg_data = {
            "timestamp": packet.timestamp,
            "event_id": packet.event_id,
            "counter": packet.counter,
            "ref": packet.ref,
            "drl": packet.drl,
            "channels": {f"ch{i + 1}": packet.channels[i] for i in range(len(packet.channels))},
            "feature_status": packet.feature_status,
        }

        await self._send_message(msg_type="eeg_data", data=eeg_data)
