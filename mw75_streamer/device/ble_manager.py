"""
BLE Manager for MW75 EEG Streamer

Handles Bluetooth Low Energy device discovery, connection, and activation sequence
for the MW75 Neuro headphones.
"""

import asyncio
from typing import Optional, Any
from bleak import BleakClient, BleakScanner

from ..config import (
    MW75_COMMAND_CHAR,
    MW75_STATUS_CHAR,
    MW75_CONTROL_CHAR,
    ENABLE_EEG_CMD,
    ENABLE_RAW_MODE_CMD,
    START_SESSION_CMD,
    DISABLE_EEG_CMD,
    DISABLE_RAW_MODE_CMD,
    STOP_SESSION_CMD,
    BATTERY_CMD,
    BLE_ACTIVATION_DELAY,
    BLE_COMMAND_DELAY,
    BLE_SESSION_DELAY,
    BLE_DISCOVERY_TIMEOUT,
    MW75_DEVICE_NAME_PATTERN,
    BLE_SUCCESS_CODE,
    BLE_EEG_COMMAND,
    BLE_RAW_MODE_COMMAND,
    BLE_UNKNOWN_E0_COMMAND,
    BLE_BATTERY_COMMAND,
)
from ..utils.logging import get_logger


class BLEManager:
    """Manages BLE connection and MW75 activation sequence"""

    def __init__(self) -> None:
        self.client: Optional[BleakClient] = None
        self.device_name: Optional[str] = None
        self.logger = get_logger(__name__)

    async def discover_and_activate(self) -> Optional[str]:
        """
        Discover MW75 device and execute activation sequence

        Returns:
            Device name if successful, None if failed
        """
        self.logger.info("Scanning for MW75...")

        # Discover BLE devices
        devices = await BleakScanner.discover(timeout=BLE_DISCOVERY_TIMEOUT)
        mw75_device = None

        for device in devices:
            if device.name and MW75_DEVICE_NAME_PATTERN in device.name.upper():
                self.logger.info(f"Found MW75: {device.name}")
                mw75_device = device
                self.device_name = device.name
                break

        if not mw75_device:
            self.logger.error("MW75 not found")
            return None

        # Execute activation sequence
        if await self._activate_device(mw75_device):
            return self.device_name
        else:
            return None

    async def _activate_device(self, device: Any) -> bool:
        """
        Execute the MW75 activation sequence

        Args:
            device: BLE device to activate

        Returns:
            True if activation successful, False otherwise
        """
        # Activation tracking
        responses = []
        eeg_enabled = False
        raw_mode_enabled = False

        def notification_handler(sender: Any, data: bytearray) -> None:
            """Handle BLE activation responses"""
            responses.append(data)
            hex_data = " ".join(f"{b:02x}" for b in data)
            self.logger.debug(f"BLE Response: {hex_data}")

            nonlocal eeg_enabled, raw_mode_enabled
            if len(data) >= 5:
                cmd_type = data[3]
                status = data[4]
                self.logger.debug(f"BLE Command: 0x{cmd_type:02x}, Status: 0x{status:02x}")

                if cmd_type == BLE_EEG_COMMAND and status == BLE_SUCCESS_CODE:
                    eeg_enabled = True
                    self.logger.info("EEG mode confirmed enabled")
                elif cmd_type == BLE_RAW_MODE_COMMAND and status == BLE_SUCCESS_CODE:
                    raw_mode_enabled = True
                    self.logger.info("Raw mode confirmed enabled")
                elif cmd_type == BLE_UNKNOWN_E0_COMMAND:
                    self.logger.debug(f"Unknown E0 command response: status=0x{status:02x}")
                elif cmd_type == BLE_BATTERY_COMMAND and status == BLE_SUCCESS_CODE:
                    # Battery response format: [0x09, 0x9A, 0x03, 0x14, 0xF1, <battery_level>]
                    if len(data) >= 6:
                        battery_level = data[5]
                        self.logger.info(f"Battery level: {battery_level}%")
                    else:
                        self.logger.debug(f"Battery command response: status=0x{status:02x}")
                elif cmd_type == BLE_SUCCESS_CODE:
                    # Alternative battery response format where success code comes first
                    # Battery response format: [0x09, 0x9A, 0x03, 0xF1, <battery_level>]
                    if data[0] == 0x09 and data[1] == 0x9A and data[2] == 0x03:
                        battery_level = status  # status field contains battery level
                        self.logger.info(f"Battery level: {battery_level}%")
                    else:
                        self.logger.debug(f"Success response: status=0x{status:02x}")
                else:
                    self.logger.warning(
                        f"Unexpected command response: 0x{cmd_type:02x} status=0x{status:02x}"
                    )

        try:
            # Connect to device
            self.client = BleakClient(device)
            await self.client.connect()
            self.logger.info("BLE connected")

            # Setup notifications to receive responses
            await self.client.start_notify(MW75_STATUS_CHAR, notification_handler)
            self.logger.info("BLE notifications enabled")

            # Send activation sequence with proper timing
            await self._send_activation_sequence()

            # Verify activation
            self.logger.info(f"Activation Results: EEG={eeg_enabled}, Raw={raw_mode_enabled}")
            self.logger.debug(f"Total responses: {len(responses)}")

            # Log all responses for debugging
            for i, resp in enumerate(responses):
                hex_data = " ".join(f"{b:02x}" for b in resp)
                self.logger.debug(f"Response {i + 1}: {hex_data}")

            if not (eeg_enabled and raw_mode_enabled):
                self.logger.error("BLE activation failed - EEG streaming not properly enabled")
                await self.client.disconnect()
                self.client = None
                return False

            self.logger.info("BLE activation confirmed successful")
            return True

        except Exception as e:
            self.logger.error(f"BLE activation error: {e}")
            if self.client:
                try:
                    await self.client.disconnect()
                except Exception:
                    pass
                self.client = None
            return False

    async def _send_activation_sequence(self) -> None:
        """Send the MW75 activation command sequence with proper timing"""
        self.logger.info("Sending ENABLE_EEG...")
        if self.client:
            await self.client.write_gatt_char(MW75_COMMAND_CHAR, ENABLE_EEG_CMD)
        await asyncio.sleep(BLE_ACTIVATION_DELAY)

        self.logger.info("Sending ENABLE_RAW_MODE...")
        if self.client:
            await self.client.write_gatt_char(MW75_COMMAND_CHAR, ENABLE_RAW_MODE_CMD)
        await asyncio.sleep(BLE_COMMAND_DELAY)

        self.logger.info("Sending START_SESSION...")
        if self.client:
            await self.client.write_gatt_char(MW75_CONTROL_CHAR, START_SESSION_CMD)
        await asyncio.sleep(BLE_SESSION_DELAY)

        # Battery check
        self.logger.info("Getting battery level...")
        if self.client:
            await self.client.write_gatt_char(MW75_COMMAND_CHAR, BATTERY_CMD)
        await asyncio.sleep(BLE_COMMAND_DELAY)

    async def disconnect_after_activation(self) -> None:
        """
        Disconnect BLE connection after activation is complete.

        This is required on macOS Taho (26+) where keeping the BLE connection open
        blocks RFCOMM delegate callbacks from being delivered.
        """
        if not self.client:
            self.logger.debug("No BLE client to disconnect")
            return

        try:
            if self.client.is_connected:
                await self.client.disconnect()
                self.logger.info("BLE disconnected (activation complete)")
            self.client = None
        except Exception as e:
            self.logger.warning(f"Error disconnecting BLE after activation: {e}")
            self.client = None

    async def cleanup(self) -> None:
        """Send disable commands and disconnect from BLE"""
        # Note: On macOS Taho+, BLE is disconnected after activation, so client may be None
        if not self.client and not self.device_name:
            self.logger.debug("No BLE connection to cleanup")
            return

        # If device_name is set but client is None, we disconnected after activation
        if not self.client and self.device_name:
            self.logger.debug("BLE was already disconnected after activation - no cleanup needed")
            self.device_name = None
            return

        # At this point, self.client must be set (type guard for mypy)
        if not self.client:
            self.logger.debug("No BLE client to cleanup")
            return

        try:
            self.logger.info("Stopping EEG streaming...")

            # Send stop commands in reverse order
            self.logger.info("Sending STOP_SESSION...")
            await self.client.write_gatt_char(MW75_CONTROL_CHAR, STOP_SESSION_CMD)
            await asyncio.sleep(BLE_ACTIVATION_DELAY)

            self.logger.info("Sending DISABLE_RAW_MODE...")
            await self.client.write_gatt_char(MW75_COMMAND_CHAR, DISABLE_RAW_MODE_CMD)
            await asyncio.sleep(BLE_ACTIVATION_DELAY)

            self.logger.info("Sending DISABLE_EEG...")
            await self.client.write_gatt_char(MW75_COMMAND_CHAR, DISABLE_EEG_CMD)
            await asyncio.sleep(BLE_COMMAND_DELAY)

            await self.client.disconnect()
            self.logger.info("EEG streaming disabled and BLE disconnected")

        except Exception as e:
            self.logger.error(f"Error during BLE cleanup: {e}")
        finally:
            self.client = None
            self.device_name = None
