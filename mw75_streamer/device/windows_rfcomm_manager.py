"""Windows RFCOMM manager for the MW75 EEG byte stream."""

import ctypes
import socket
import sys
import threading
import time
from typing import Callable, List, Optional, Tuple

from ..config import DATA_PACKET_TIMEOUT, RFCOMM_CHANNEL, RFCOMM_CONNECTION_TIMEOUT
from ..utils.logging import get_logger

READ_TIMEOUT = 0.25
READ_SIZE = 65536
RECEIVE_BUFFER_SIZE = 1048576


class _BluetoothAddress(ctypes.Union):
    _fields_ = [
        ("ullLong", ctypes.c_uint64),
        ("rgBytes", ctypes.c_ubyte * 6),
    ]


class _SystemTime(ctypes.Structure):
    _fields_ = [
        ("wYear", ctypes.c_uint16),
        ("wMonth", ctypes.c_uint16),
        ("wDayOfWeek", ctypes.c_uint16),
        ("wDay", ctypes.c_uint16),
        ("wHour", ctypes.c_uint16),
        ("wMinute", ctypes.c_uint16),
        ("wSecond", ctypes.c_uint16),
        ("wMilliseconds", ctypes.c_uint16),
    ]


class _BluetoothDeviceInfo(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("Address", _BluetoothAddress),
        ("ulClassofDevice", ctypes.c_uint32),
        ("fConnected", ctypes.c_int32),
        ("fRemembered", ctypes.c_int32),
        ("fAuthenticated", ctypes.c_int32),
        ("stLastSeen", _SystemTime),
        ("stLastUsed", _SystemTime),
        ("szName", ctypes.c_wchar * 248),
    ]


class _BluetoothDeviceSearchParams(ctypes.Structure):
    _fields_ = [
        ("dwSize", ctypes.c_uint32),
        ("fReturnAuthenticated", ctypes.c_int32),
        ("fReturnRemembered", ctypes.c_int32),
        ("fReturnUnknown", ctypes.c_int32),
        ("fReturnConnected", ctypes.c_int32),
        ("fIssueInquiry", ctypes.c_int32),
        ("cTimeoutMultiplier", ctypes.c_ubyte),
        ("hRadio", ctypes.c_void_p),
    ]


def normalize_bluetooth_address(address: str) -> str:
    """Return the bare ``AA:BB:CC:DD:EE:FF`` form required by CPython."""
    normalized = address.strip().strip("()").upper()
    parts = normalized.split(":")
    if len(parts) != 6 or any(len(part) != 2 for part in parts):
        raise ValueError(
            "Invalid Bluetooth address " f"{address!r}; expected bare AA:BB:CC:DD:EE:FF"
        )
    try:
        bytes(int(part, 16) for part in parts)
    except ValueError as error:
        raise ValueError(f"Invalid Bluetooth address {address!r}") from error
    return normalized


def _format_bluetooth_address(address: int) -> str:
    return ":".join(f"{(address >> (8 * index)) & 0xFF:02X}" for index in range(5, -1, -1))


class RFCOMMManager:
    """Manage the MW75 RFCOMM connection through Windows Bluetooth sockets."""

    def __init__(self, device_name: str, data_callback: Callable[[bytes], None]):
        """Initialize the manager for a paired Windows Bluetooth device."""
        self.device_name = device_name
        self.data_callback = data_callback
        self.connected = False
        self.device_address: Optional[str] = None
        self.stream_error: Optional[str] = None
        self.logger = get_logger(__name__)
        self._socket: Optional[socket.socket] = None
        self._stop_event = threading.Event()
        self._state_lock = threading.Lock()

    @property
    def should_stop(self) -> bool:
        """Mirror the macOS manager's public stop flag."""
        return self._stop_event.is_set()

    @should_stop.setter
    def should_stop(self, value: bool) -> None:
        if value:
            self._stop_event.set()
        else:
            self._stop_event.clear()

    def connect(self) -> bool:
        """Find the paired device and connect to its EEG RFCOMM channel."""
        self.close()
        self._stop_event.clear()
        self.stream_error = None
        self.logger.info(f"Looking for paired Bluetooth device: {self.device_name}")

        for address in self._find_paired_device_addresses():
            if self._connect_to_address(address):
                return True
        return False

    def _connect_to_address(self, address: str) -> bool:
        """Open the EEG RFCOMM channel to one candidate address."""
        rfcomm: Optional[socket.socket] = None
        try:
            family = getattr(socket, "AF_BLUETOOTH", None)
            protocol = getattr(socket, "BTPROTO_RFCOMM", None)
            if family is None or protocol is None:
                raise RuntimeError("This Python build does not expose AF_BLUETOOTH/BTPROTO_RFCOMM")

            rfcomm = socket.socket(family, socket.SOCK_STREAM, protocol)
            try:
                rfcomm.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECEIVE_BUFFER_SIZE)
            except OSError as error:
                self.logger.warning(f"Could not set RFCOMM receive buffer size: {error}")
            rfcomm.settimeout(RFCOMM_CONNECTION_TIMEOUT)
            rfcomm.connect((address, RFCOMM_CHANNEL))
            rfcomm.settimeout(READ_TIMEOUT)
        except (OSError, RuntimeError) as error:
            self.logger.error(
                f"RFCOMM connection failed for {address} channel {RFCOMM_CHANNEL}: {error}"
            )
            if rfcomm is not None:
                try:
                    rfcomm.close()
                except OSError:
                    pass
            return False

        with self._state_lock:
            self._socket = rfcomm
            self.connected = True
            self.device_address = address
        self.logger.info(
            f"RFCOMM connected to {self.device_name} ({address}) on channel {RFCOMM_CHANNEL}"
        )
        return True

    def _find_paired_device_addresses(self) -> List[str]:
        """Return candidate Classic Bluetooth addresses for matching paired devices.

        Candidates are ordered connected first, then authenticated, so a stale
        remembered pairing record cannot shadow the live headset.
        """
        if sys.platform != "win32":
            self.logger.error("Windows RFCOMM device discovery requires Windows")
            return []

        try:
            bthprops = ctypes.WinDLL("bthprops.cpl", use_last_error=True)
        except (AttributeError, OSError) as error:
            self.logger.error(f"Windows Bluetooth device discovery is unavailable: {error}")
            return []

        find_first = bthprops.BluetoothFindFirstDevice
        find_next = bthprops.BluetoothFindNextDevice
        find_close = bthprops.BluetoothFindDeviceClose
        find_first.argtypes = (
            ctypes.POINTER(_BluetoothDeviceSearchParams),
            ctypes.POINTER(_BluetoothDeviceInfo),
        )
        find_first.restype = ctypes.c_void_p
        find_next.argtypes = (ctypes.c_void_p, ctypes.POINTER(_BluetoothDeviceInfo))
        find_next.restype = ctypes.c_int32
        find_close.argtypes = (ctypes.c_void_p,)
        find_close.restype = ctypes.c_int32

        search = _BluetoothDeviceSearchParams()
        search.dwSize = ctypes.sizeof(search)
        search.fReturnAuthenticated = True
        search.fReturnRemembered = True
        search.fReturnConnected = True
        search.fReturnUnknown = False
        search.fIssueInquiry = False
        search.cTimeoutMultiplier = 0
        search.hRadio = None

        info = _BluetoothDeviceInfo()
        info.dwSize = ctypes.sizeof(info)
        handle = find_first(ctypes.byref(search), ctypes.byref(info))
        if not handle:
            error_code = getattr(ctypes, "get_last_error", lambda: 0)()
            self.logger.error(
                "No paired Classic Bluetooth devices were available "
                f"(Windows error {error_code})"
            )
            return []

        candidates: List[Tuple[bool, bool, str, str]] = []
        try:
            while True:
                name = info.szName
                if name and self.device_name.upper() in name.upper():
                    address = _format_bluetooth_address(info.Address.ullLong)
                    candidates.append(
                        (bool(info.fConnected), bool(info.fAuthenticated), name, address)
                    )

                info = _BluetoothDeviceInfo()
                info.dwSize = ctypes.sizeof(info)
                if not find_next(handle, ctypes.byref(info)):
                    break
        finally:
            find_close(handle)

        if not candidates:
            self.logger.error(f"No paired device found matching '{self.device_name}'")
            self.logger.info("Pair the MW75 in Windows Settings > Bluetooth & devices")
            return []

        candidates.sort(key=lambda candidate: (candidate[0], candidate[1]), reverse=True)
        for is_connected, is_authenticated, name, address in candidates:
            self.logger.info(
                f"Found matching paired device: {name} ({address}) "
                f"connected={is_connected} authenticated={is_authenticated}"
            )
        return [address for _, _, _, address in candidates]

    def _set_high_priority(self) -> None:
        """Raise scheduling priority for the ~500 Hz receive loop, best effort."""
        if sys.platform != "win32":
            return

        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.GetCurrentProcess.restype = ctypes.c_void_p
            kernel32.GetCurrentThread.restype = ctypes.c_void_p
            kernel32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
            kernel32.SetPriorityClass.restype = ctypes.c_int32
            kernel32.SetThreadPriority.argtypes = (ctypes.c_void_p, ctypes.c_int32)
            kernel32.SetThreadPriority.restype = ctypes.c_int32

            high_priority_class = 0x00000080
            thread_priority_highest = 2
            last_error = getattr(ctypes, "get_last_error", lambda: 0)
            if kernel32.SetPriorityClass(kernel32.GetCurrentProcess(), high_priority_class):
                self.logger.info("Process priority raised to high")
            else:
                self.logger.warning(
                    f"Could not raise process priority (Windows error {last_error()})"
                )
            if kernel32.SetThreadPriority(kernel32.GetCurrentThread(), thread_priority_highest):
                self.logger.info("Receive thread priority raised to highest")
            else:
                self.logger.warning(
                    f"Could not raise receive thread priority (Windows error {last_error()})"
                )
        except (AttributeError, OSError) as error:
            self.logger.warning(f"Priority adjustment failed: {error}")

    def _record_stream_failure(self, message: str) -> None:
        """Record an abnormal stream end unless a stop was requested."""
        if self._stop_event.is_set():
            return
        self.stream_error = message
        self.logger.error(message)

    def run_until_stopped(self) -> None:
        """Receive raw RFCOMM chunks until stopped or the stream fails.

        An abnormal end (peer disconnect, read failure, data stall) is recorded
        in ``stream_error`` so callers can report the session as failed.
        """
        with self._state_lock:
            rfcomm = self._socket
            connected = self.connected
        if not connected or rfcomm is None:
            self.logger.error("Cannot run - RFCOMM not connected")
            return

        self.logger.info("Data streaming... Press Ctrl+C to stop")
        self._set_high_priority()

        last_data_time = time.monotonic()
        while not self._stop_event.is_set():
            try:
                chunk = rfcomm.recv(READ_SIZE)
            except TimeoutError as error:
                # A benign settimeout expiry carries no errno; a link failure
                # surfacing as WSAETIMEDOUT does.
                if getattr(error, "errno", None) is not None:
                    self._record_stream_failure(f"RFCOMM read failed: {error}")
                    break
                idle_time = time.monotonic() - last_data_time
                if idle_time > DATA_PACKET_TIMEOUT:
                    self._record_stream_failure(
                        f"No data received for {idle_time:.1f}s "
                        f"(threshold {DATA_PACKET_TIMEOUT}s)"
                    )
                    break
                continue
            except OSError as error:
                self._record_stream_failure(f"RFCOMM read failed: {error}")
                break

            if not chunk:
                self._record_stream_failure("RFCOMM channel closed by device")
                break

            last_data_time = time.monotonic()
            try:
                self.data_callback(chunk)
            except Exception as error:
                self.logger.error(f"Error processing RFCOMM data: {error}")

        with self._state_lock:
            self.connected = False

    def stop(self) -> None:
        """Signal the receive loop to stop; safe to call from another thread."""
        self.logger.info("Stop requested for RFCOMM receive loop")
        self._stop_event.set()

    def close(self) -> None:
        """Close the RFCOMM socket; repeated calls are safe."""
        self._stop_event.set()
        with self._state_lock:
            rfcomm, self._socket = self._socket, None
            self.connected = False

        if rfcomm is None:
            return

        try:
            rfcomm.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            rfcomm.close()
        except OSError:
            pass
        self.logger.info("RFCOMM channel closed")
