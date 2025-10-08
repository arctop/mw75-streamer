"""
MW75 Device Coordinator

High-level interface for managing MW75 device connections and data streaming.
Coordinates BLE activation and RFCOMM data streaming.
"""

import asyncio
import signal
from typing import Optional, Callable, Any

from .ble_manager import BLEManager
from .rfcomm_manager import RFCOMMManager
from ..utils.logging import get_logger


class MW75Device:
    """
    High-level MW75 device coordinator

    Manages the complete MW75 connection lifecycle:
    1. BLE discovery and activation
    2. RFCOMM connection and data streaming
    3. Clean shutdown and cleanup
    """

    def __init__(self, data_callback: Callable[[bytes], None], setup_signal_handler: bool = True):
        """
        Initialize MW75 device coordinator

        Args:
            data_callback: Function to call when data is received from the device
            setup_signal_handler: If True, set up SIGINT handler for graceful shutdown
        """
        self.data_callback = data_callback
        self.ble_manager = BLEManager()
        self.rfcomm_manager: Optional[RFCOMMManager] = None
        self.should_stop = False
        self.logger = get_logger(__name__)

        # Set up signal handler for graceful shutdown (optional)
        if setup_signal_handler:
            signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle SIGINT (Ctrl+C) gracefully"""
        self.logger.info("Interrupt signal received - initiating clean shutdown...")
        self.should_stop = True
        if self.rfcomm_manager:
            self.rfcomm_manager.stop()

    async def connect_and_stream(self) -> bool:
        """
        Connect to MW75 device and start data streaming

        Returns:
            True if streaming started successfully, False otherwise
        """
        try:
            # Step 1: BLE discovery and activation
            self.logger.info("Starting MW75 connection process...")
            device_name = await self.ble_manager.discover_and_activate()
            if not device_name:
                self.logger.error("BLE activation failed")
                return False

            # Step 1.5: Disconnect BLE before RFCOMM (macOS Taho compatibility)
            # On macOS 26+ (Taho), keeping BLE connected blocks RFCOMM delegate callbacks
            self.logger.info("Disconnecting BLE (required for RFCOMM on macOS Taho)...")
            await self.ble_manager.disconnect_after_activation()

            # Wait for Bluetooth stack to settle after BLE disconnection
            await asyncio.sleep(0.5)

            # Step 2: RFCOMM connection
            self.logger.info("Establishing RFCOMM connection...")
            self.rfcomm_manager = RFCOMMManager(device_name, self.data_callback)
            if not self.rfcomm_manager.connect():
                self.logger.error("RFCOMM connection failed")
                return False

            # Step 3: Start data streaming loop
            self.logger.info("Starting data streaming loop...")
            self.rfcomm_manager.run_until_stopped()

            return True

        except Exception as e:
            self.logger.error(f"Error during MW75 streaming: {e}")
            return False
        finally:
            await self.cleanup()

    async def cleanup(self) -> None:
        """Clean up all MW75 connections and resources"""
        self.logger.info("Cleaning up MW75 device connections...")

        # Close RFCOMM connection
        if self.rfcomm_manager:
            self.rfcomm_manager.close()
            self.rfcomm_manager = None

        # Clean up BLE connection
        await self.ble_manager.cleanup()

        self.logger.info("MW75 device cleanup complete")
