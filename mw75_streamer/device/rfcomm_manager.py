"""
RFCOMM Manager for MW75 EEG Streamer

Handles Bluetooth RFCOMM connection and data streaming using macOS IOBluetooth framework.
"""

import objc
import os
from typing import Optional, Callable, Any
from Foundation import NSObject, NSRunLoop, NSDate
from IOBluetooth import IOBluetoothDevice

from ..config import RFCOMM_CHANNEL, RFCOMM_CONNECTION_TIMEOUT
from ..utils.logging import get_logger


class RFCOMMDelegate(NSObject):
    """RFCOMM delegate for handling Bluetooth data reception"""

    def initWithCallback_(self, callback: Callable[[bytes], None]) -> Optional["RFCOMMDelegate"]:
        """Initialize with data callback function"""
        self = objc.super(RFCOMMDelegate, self).init()
        if self is None:
            return None
        self.data_callback = callback
        self.connected = False
        self.channel = None
        self.logger = get_logger(__name__)

        return self

    def rfcommChannelOpenComplete_status_(self, rfcommChannel: Any, status: int) -> None:
        """Handle RFCOMM channel open completion"""
        self.logger.debug(f"RFCOMM delegate callback fired! status=0x{status:08x}")

        if status == 0:
            self.logger.info("RFCOMM connected successfully")
            self.connected = True
            self.channel = rfcommChannel
        else:
            self.logger.error(f"RFCOMM failed: 0x{status:08x}")

    def rfcommChannelData_data_length_(
        self, rfcommChannel: Any, dataPointer: Any, dataLength: int
    ) -> None:
        """Handle incoming RFCOMM data"""
        self.logger.debug(f"RFCOMM data received: {dataLength} bytes")

        try:
            import ctypes

            data = ctypes.string_at(dataPointer, dataLength)

            # Forward data to packet processor for buffering and framing
            if self.data_callback is not None:
                self.data_callback(data)
        except Exception as e:
            self.logger.error(f"Error processing RFCOMM data: {e}")

    def rfcommChannelClosed_(self, rfcommChannel: Any) -> None:
        """Handle RFCOMM channel closed"""
        self.logger.info("RFCOMM channel closed")
        self.connected = False
        self.channel = None


class RFCOMMManager:
    """Manages RFCOMM connection and data streaming"""

    def __init__(self, device_name: str, data_callback: Callable[[bytes], None]):
        """
        Initialize RFCOMM manager

        Args:
            device_name: Name of the MW75 device to connect to
            data_callback: Function to call when data is received
        """
        self.device_name = device_name
        self.data_callback = data_callback
        self.delegate: Optional[RFCOMMDelegate] = None
        self.connected = False
        self.should_stop = False
        self.logger = get_logger(__name__)

    def connect(self) -> bool:
        """
        Connect to RFCOMM channel and start data streaming

        Returns:
            True if connection successful, False otherwise
        """
        self.logger.info(f"Looking for paired Bluetooth device: {self.device_name}")

        # Find paired device
        target_device = self._find_paired_device()
        if not target_device:
            return False

        # Create delegate and connect
        return self._establish_connection(target_device)

    def _find_paired_device(self) -> Optional[IOBluetoothDevice]:
        """
        Find the paired Bluetooth device matching the device name

        Returns:
            IOBluetoothDevice if found, None otherwise
        """
        paired_devices = IOBluetoothDevice.pairedDevices()
        target_device = None

        if paired_devices:
            self.logger.info(f"Found {len(paired_devices)} paired Bluetooth devices")
            for device in paired_devices:
                device_name = device.name()
                if device_name and self.device_name.upper() in device_name.upper():
                    target_device = device
                    device_address = device.addressString()
                    self.logger.info(
                        f"Found matching paired device: {device_name} ({device_address})"
                    )
                    break
                else:
                    self.logger.debug(f"   - {device_name or 'Unknown'} (not a match)")

        if not target_device:
            self.logger.error(f"No paired device found matching '{self.device_name}'")
            self.logger.info("Please ensure MW75 is paired via System Settings > Bluetooth")

        return target_device

    def _establish_connection(self, device: IOBluetoothDevice) -> bool:
        """
        Establish RFCOMM connection to the device

        Args:
            device: IOBluetoothDevice to connect to

        Returns:
            True if connection successful, False otherwise
        """
        self.delegate = RFCOMMDelegate.alloc().initWithCallback_(self.data_callback)
        self.logger.info(f"Connecting RFCOMM to {self.device_name}...")
        self.logger.debug(f"Delegate created: {self.delegate}")

        # Open RFCOMM channel
        result = device.openRFCOMMChannelAsync_withChannelID_delegate_(
            None, RFCOMM_CHANNEL, self.delegate
        )
        self.logger.debug(f"RFCOMM channel {RFCOMM_CHANNEL} result: {result}")

        # Wait for connection with timeout
        return self._wait_for_connection()

    def _wait_for_connection(self) -> bool:
        """
        Wait for RFCOMM connection to establish

        Returns:
            True if connection established within timeout, False otherwise
        """
        self.logger.debug("Waiting for delegate callback...")
        runloop = NSRunLoop.currentRunLoop()
        end_time = NSDate.dateWithTimeIntervalSinceNow_(RFCOMM_CONNECTION_TIMEOUT)

        while NSDate.date().compare_(end_time) == -1:
            runloop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.1))
            if self.delegate and self.delegate.connected:
                self.connected = True
                self.logger.info("RFCOMM connected - data is flowing!")
                return True

        self.logger.error(f"RFCOMM connection timeout after {RFCOMM_CONNECTION_TIMEOUT}s")
        return False

    def _set_high_priority(self) -> None:
        """Set high priority for the streaming process"""
        try:
            # Set high process priority (niceness = -10, requires sudo for < 0)
            current_nice = os.nice(0)  # Get current niceness
            try:
                os.nice(-10)  # Try to set high priority
                self.logger.info(f"Process priority increased from {current_nice} to {os.nice(0)}")
            except PermissionError:
                # Fallback: set to highest priority we can without sudo
                os.nice(-5)
                self.logger.info(
                    f"Process priority increased from {current_nice} to {os.nice(0)} (limited by permissions)"
                )
            except OSError:
                self.logger.warning("Could not adjust process priority")

            # Set high thread priority for current thread
            import ctypes
            from ctypes import c_void_p

            # macOS thread priority constants
            THREAD_TIME_CONSTRAINT_POLICY = 2

            try:
                # Get current thread handle
                libc = ctypes.CDLL("libc.dylib")
                pthread_self = libc.pthread_self
                pthread_self.restype = c_void_p

                current_thread = pthread_self()

                # Set thread to time constraint policy (real-time)
                libc.thread_policy_set(
                    current_thread,
                    THREAD_TIME_CONSTRAINT_POLICY,
                    ctypes.byref(ctypes.c_uint32(1)),  # period
                    ctypes.sizeof(ctypes.c_uint32),
                )
                self.logger.info("Thread set to real-time priority")

            except Exception as e:
                self.logger.debug(f"Could not set thread priority: {e}")

        except Exception:
            self.logger.warning(
                "Priority adjustment failed (you can run with sudo to optimize performance)"
            )

    def run_until_stopped(self) -> None:
        """Run the RFCOMM event loop until stop is requested"""
        if not self.connected:
            self.logger.error("Cannot run - RFCOMM not connected")
            return

        self.logger.info("Data streaming... Press Ctrl+C to stop")

        # Set high priority for better real-time performance
        self._set_high_priority()

        runloop = NSRunLoop.currentRunLoop()
        while not self.should_stop:
            # Use shorter intervals for more responsive event handling
            runloop.runUntilDate_(NSDate.dateWithTimeIntervalSinceNow_(0.001))

    def stop(self) -> None:
        """Signal to stop the RFCOMM event loop"""
        self.logger.info("Stop requested for RFCOMM event loop")
        self.should_stop = True

    def close(self) -> None:
        """Close RFCOMM connection"""
        if self.delegate and self.delegate.channel:
            try:
                self.logger.info("Closing RFCOMM channel...")
                self.delegate.channel.closeChannel()
                self.logger.info("RFCOMM channel closed")
            except Exception as e:
                self.logger.error(f"Error closing RFCOMM: {e}")
            finally:
                self.connected = False
                self.delegate = None
        else:
            self.logger.debug("No RFCOMM channel to close")
