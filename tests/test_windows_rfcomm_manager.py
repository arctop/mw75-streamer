"""Tests for the Windows stdlib RFCOMM manager."""

import asyncio
import socket
import sys
import threading
from typing import Callable, List, Optional, Tuple
from unittest.mock import AsyncMock, patch

import pytest

from mw75_streamer.config import DATA_PACKET_TIMEOUT, RFCOMM_CONNECTION_TIMEOUT
from mw75_streamer.device.windows_rfcomm_manager import (
    READ_TIMEOUT,
    RECEIVE_BUFFER_SIZE,
    RFCOMMManager,
    normalize_bluetooth_address,
)


class FakeSocket:
    """Small socket double used without Windows Bluetooth hardware."""

    def __init__(
        self,
        chunks: Optional[List[bytes]] = None,
        connect_error: Optional[OSError] = None,
        recv_error: Optional[OSError] = None,
        sockopt_error: Optional[OSError] = None,
    ) -> None:
        self.chunks = list(chunks or [])
        self.connect_error = connect_error
        self.recv_error = recv_error
        self.sockopt_error = sockopt_error
        self.connected_to: Optional[Tuple[str, int]] = None
        self.closed = False
        self.shutdown_calls = 0
        self.timeouts: List[float] = []
        self.sockopts: List[Tuple[int, int, int]] = []

    def setsockopt(self, level: int, option: int, value: int) -> None:
        if self.sockopt_error:
            raise self.sockopt_error
        self.sockopts.append((level, option, value))

    def settimeout(self, timeout: float) -> None:
        self.timeouts.append(timeout)

    def connect(self, endpoint: Tuple[str, int]) -> None:
        if self.connect_error:
            raise self.connect_error
        self.connected_to = endpoint

    def recv(self, size: int) -> bytes:
        if self.chunks:
            return self.chunks.pop(0)
        if self.recv_error:
            raise self.recv_error
        return b""

    def shutdown(self, how: int) -> None:
        self.shutdown_calls += 1

    def close(self) -> None:
        self.closed = True


class TimeoutSocket(FakeSocket):
    """Socket double that keeps the receive loop waiting for stop()."""

    def __init__(self) -> None:
        super().__init__()
        self.recv_started = threading.Event()

    def recv(self, size: int) -> bytes:
        self.recv_started.set()
        raise socket.timeout()


@pytest.mark.parametrize(
    "source, expected",
    [
        ("50:0b:91:a9:39:07", "50:0B:91:A9:39:07"),
        (" (50:0B:91:A9:39:07) ", "50:0B:91:A9:39:07"),
    ],
)
def test_normalize_bluetooth_address(source: str, expected: str) -> None:
    assert normalize_bluetooth_address(source) == expected


@pytest.mark.parametrize(
    "address",
    ["", "50-0B-91-A9-39-07", "50:0B:91:A9:39", "GG:0B:91:A9:39:07"],
)
def test_rejects_malformed_bluetooth_address(address: str) -> None:
    with pytest.raises(ValueError, match="Invalid Bluetooth address"):
        normalize_bluetooth_address(address)


def _connect_with_fakes(
    manager: RFCOMMManager,
    fakes: List[FakeSocket],
    addresses: Optional[List[str]] = None,
) -> Tuple[bool, List[Tuple[int, int, int]]]:
    """Connect the manager against socket doubles, recording constructor args."""
    remaining = list(fakes)
    constructor_args: List[Tuple[int, int, int]] = []

    def fake_socket_factory(family: int, kind: int, proto: int) -> FakeSocket:
        constructor_args.append((family, kind, proto))
        return remaining.pop(0)

    with (
        patch.object(
            manager,
            "_find_paired_device_addresses",
            return_value=addresses or ["50:0B:91:A9:39:07"],
        ),
        patch(
            "mw75_streamer.device.windows_rfcomm_manager.socket.socket",
            side_effect=fake_socket_factory,
        ),
        patch("mw75_streamer.device.windows_rfcomm_manager.socket.AF_BLUETOOTH", 32, create=True),
        patch("mw75_streamer.device.windows_rfcomm_manager.socket.BTPROTO_RFCOMM", 3, create=True),
    ):
        return manager.connect(), constructor_args


def _connect_with_fake(manager: RFCOMMManager, fake: FakeSocket) -> bool:
    result, _ = _connect_with_fakes(manager, [fake])
    return result


def test_connect_success() -> None:
    fake = FakeSocket()
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)

    result, constructor_args = _connect_with_fakes(manager, [fake])

    assert result
    assert constructor_args == [(32, socket.SOCK_STREAM, 3)]
    assert fake.connected_to == ("50:0B:91:A9:39:07", 25)
    assert manager.device_address == "50:0B:91:A9:39:07"
    assert manager.connected


def test_connect_pins_timeouts_and_receive_buffer() -> None:
    fake = FakeSocket()
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)

    assert _connect_with_fake(manager, fake)
    assert fake.timeouts == [RFCOMM_CONNECTION_TIMEOUT, READ_TIMEOUT]
    assert (socket.SOL_SOCKET, socket.SO_RCVBUF, RECEIVE_BUFFER_SIZE) in fake.sockopts


def test_connect_succeeds_when_receive_buffer_sockopt_fails() -> None:
    fake = FakeSocket(sockopt_error=OSError("protocol option not supported"))
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)

    assert _connect_with_fake(manager, fake)
    assert fake.connected_to == ("50:0B:91:A9:39:07", 25)
    assert manager.connected


def test_connect_failure_closes_socket() -> None:
    fake = FakeSocket(connect_error=OSError("connection refused"))
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)

    assert not _connect_with_fake(manager, fake)
    assert fake.closed
    assert not manager.connected


def test_connect_tries_next_candidate_after_failure() -> None:
    stale = FakeSocket(connect_error=OSError("timed out"))
    live = FakeSocket()
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)

    result, _ = _connect_with_fakes(
        manager,
        [stale, live],
        addresses=["50:0B:91:A9:39:07", "50:0B:91:A9:39:08"],
    )

    assert result
    assert stale.closed
    assert live.connected_to == ("50:0B:91:A9:39:08", 25)
    assert manager.device_address == "50:0B:91:A9:39:08"


def test_receive_loop_delivers_raw_chunks_and_stop_terminates() -> None:
    delivered: List[bytes] = []
    fake = FakeSocket([b"first", b"second"])
    manager = RFCOMMManager("MW75 Neuro", delivered.append)
    assert _connect_with_fake(manager, fake)

    def stop_after_first(chunk: bytes) -> None:
        delivered.append(chunk)
        manager.stop()

    manager.data_callback = stop_after_first
    manager.run_until_stopped()

    assert delivered == [b"first"]
    assert not manager.connected
    assert manager.stream_error is None


def test_receive_loop_delivers_each_raw_chunk() -> None:
    delivered: List[bytes] = []
    fake = FakeSocket([b"first", b"second"])
    manager = RFCOMMManager("MW75 Neuro", delivered.append)
    assert _connect_with_fake(manager, fake)

    manager.run_until_stopped()

    assert delivered == [b"first", b"second"]


def test_peer_disconnect_records_stream_error() -> None:
    fake = FakeSocket([b"first"])
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)
    assert _connect_with_fake(manager, fake)

    manager.run_until_stopped()

    assert manager.stream_error is not None
    assert "closed by device" in manager.stream_error
    assert not manager.connected


def test_read_error_records_stream_error() -> None:
    fake = FakeSocket(recv_error=OSError("connection reset"))
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)
    assert _connect_with_fake(manager, fake)

    manager.run_until_stopped()

    assert manager.stream_error is not None
    assert "read failed" in manager.stream_error


def test_timeout_with_errno_records_stream_error() -> None:
    # A real link failure (WSAETIMEDOUT) surfaces as TimeoutError with an
    # errno on Python 3.10+, unlike a benign settimeout expiry
    fake = FakeSocket(recv_error=TimeoutError(10060, "connection timed out"))
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)
    assert _connect_with_fake(manager, fake)

    manager.run_until_stopped()

    assert manager.stream_error is not None
    assert "read failed" in manager.stream_error


def test_data_stall_trips_watchdog() -> None:
    fake = TimeoutSocket()
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)
    assert _connect_with_fake(manager, fake)

    with patch(
        "mw75_streamer.device.windows_rfcomm_manager.time.monotonic",
        side_effect=[0.0, DATA_PACKET_TIMEOUT + 1.0],
    ):
        manager.run_until_stopped()

    assert manager.stream_error is not None
    assert "No data received" in manager.stream_error


def test_stop_terminates_receive_loop_from_another_thread() -> None:
    fake = TimeoutSocket()
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)
    assert _connect_with_fake(manager, fake)
    receive_thread = threading.Thread(target=manager.run_until_stopped)
    receive_thread.start()
    assert fake.recv_started.wait(1.0)

    manager.stop()
    receive_thread.join(1.0)

    assert not receive_thread.is_alive()
    assert not manager.connected
    assert manager.stream_error is None


def test_should_stop_mirrors_stop_state() -> None:
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)

    assert not manager.should_stop
    manager.stop()
    assert manager.should_stop
    manager.should_stop = False
    assert not manager.should_stop


def test_close_is_idempotent() -> None:
    fake = FakeSocket()
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)
    assert _connect_with_fake(manager, fake)

    manager.close()
    manager.close()

    assert fake.shutdown_calls == 1
    assert fake.closed
    assert not manager.connected


def test_connect_returns_false_when_paired_device_is_missing() -> None:
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)
    with patch.object(manager, "_find_paired_device_addresses", return_value=[]):
        assert not manager.connect()


class _ScriptedManager:
    """RFCOMM manager double for exercising MW75Device's failure reporting."""

    stream_error_after_run: Optional[str] = None

    def __init__(self, device_name: str, data_callback: Callable[[bytes], None]) -> None:
        self.device_address = "50:0B:91:A9:39:07"
        self.stream_error: Optional[str] = None

    def connect(self) -> bool:
        return True

    def run_until_stopped(self) -> None:
        self.stream_error = self.stream_error_after_run

    def stop(self) -> None:
        pass

    def close(self) -> None:
        pass


@pytest.mark.skipif(
    sys.platform not in ("darwin", "win32"),
    reason="MW75Device imports a platform RFCOMM manager",
)
@pytest.mark.parametrize(
    "stream_error, expected_result",
    [(None, True), ("RFCOMM channel closed by device", False)],
)
def test_connect_and_stream_reports_stream_failures(
    stream_error: Optional[str], expected_result: bool
) -> None:
    from mw75_streamer.device import mw75_device as mw75_device_module

    device = mw75_device_module.MW75Device(lambda data: None, setup_signal_handler=False)
    device.ble_manager = AsyncMock()
    device.ble_manager.discover_and_activate.return_value = "MW75 Neuro"

    manager_class = type(
        "ScriptedManager", (_ScriptedManager,), {"stream_error_after_run": stream_error}
    )
    with (
        patch.object(mw75_device_module, "RFCOMMManager", manager_class),
        patch.object(mw75_device_module.asyncio, "sleep", new=AsyncMock()),
    ):
        assert asyncio.run(device.connect_and_stream()) is expected_result
