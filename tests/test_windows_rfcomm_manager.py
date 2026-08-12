"""Tests for the Windows stdlib RFCOMM manager."""

import socket
import threading
from typing import List, Optional, Tuple
from unittest.mock import patch

import pytest

from mw75_streamer.device.windows_rfcomm_manager import (
    RFCOMMManager,
    normalize_bluetooth_address,
)


class FakeSocket:
    """Small socket double used without Windows Bluetooth hardware."""

    def __init__(
        self,
        chunks: Optional[List[bytes]] = None,
        connect_error: Optional[OSError] = None,
    ) -> None:
        self.chunks = list(chunks or [])
        self.connect_error = connect_error
        self.connected_to: Optional[Tuple[str, int]] = None
        self.closed = False
        self.shutdown_calls = 0

    def setsockopt(self, level: int, option: int, value: int) -> None:
        pass

    def settimeout(self, timeout: float) -> None:
        pass

    def connect(self, endpoint: Tuple[str, int]) -> None:
        if self.connect_error:
            raise self.connect_error
        self.connected_to = endpoint

    def recv(self, size: int) -> bytes:
        if self.chunks:
            return self.chunks.pop(0)
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


def _connect_with_fake(manager: RFCOMMManager, fake: FakeSocket) -> bool:
    with (
        patch.object(manager, "_find_paired_device_address", return_value="50:0b:91:a9:39:07"),
        patch("mw75_streamer.device.windows_rfcomm_manager.socket.socket", return_value=fake),
        patch("mw75_streamer.device.windows_rfcomm_manager.socket.AF_BLUETOOTH", 32, create=True),
        patch("mw75_streamer.device.windows_rfcomm_manager.socket.BTPROTO_RFCOMM", 3, create=True),
    ):
        return manager.connect()


def test_connect_success() -> None:
    fake = FakeSocket()
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)

    assert _connect_with_fake(manager, fake)
    assert fake.connected_to == ("50:0B:91:A9:39:07", 25)
    assert manager.device_address == "50:0B:91:A9:39:07"
    assert manager.connected


def test_connect_failure_closes_socket() -> None:
    fake = FakeSocket(connect_error=OSError("connection refused"))
    manager = RFCOMMManager("MW75 Neuro", lambda data: None)

    assert not _connect_with_fake(manager, fake)
    assert fake.closed
    assert not manager.connected


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


def test_receive_loop_delivers_each_raw_chunk() -> None:
    delivered: List[bytes] = []
    fake = FakeSocket([b"first", b"second"])
    manager = RFCOMMManager("MW75 Neuro", delivered.append)
    assert _connect_with_fake(manager, fake)

    manager.run_until_stopped()

    assert delivered == [b"first", b"second"]


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
    with patch.object(manager, "_find_paired_device_address", return_value=None):
        assert not manager.connect()
