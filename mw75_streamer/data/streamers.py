"""
Data Streamers for MW75 EEG Data

Handles output of EEG data to various destinations: CSV files, WebSocket, and stdout.
"""

import time
import json
import threading
from pathlib import Path
from typing import Optional, Any

# WebSocket imports with fallback
try:
    import websocket

    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    websocket = None  # type: ignore

# LSL imports with fallback
try:
    import pylsl

    LSL_AVAILABLE = True
except (ImportError, RuntimeError):
    LSL_AVAILABLE = False
    pylsl = None

from .packet_processor import EEGPacket
from ..config import EEG_CSV_HEADER, EXTRA_CSV_HEADER, NUM_EEG_CHANNELS
from ..utils.logging import get_logger


class CSVWriter:
    """Handles CSV file output for EEG data and other events"""

    def __init__(self, eeg_path: Optional[str] = None, extra_path: Optional[str] = None):
        """
        Initialize CSV writer

        Args:
            eeg_path: Path for EEG data CSV file (Event ID 239)
            extra_path: Path for other events CSV file
        """
        self.eeg_file: Optional[Any] = None
        self.extra_file: Optional[Any] = None
        self.eeg_path = eeg_path
        self.extra_path = extra_path
        self.logger = get_logger(__name__)

        if eeg_path or extra_path:
            self._open_files()

    def _open_files(self) -> bool:
        """
        Open CSV files and write headers

        Returns:
            True if files opened successfully, False otherwise
        """
        try:
            if self.eeg_path:
                Path(self.eeg_path).parent.mkdir(parents=True, exist_ok=True)
                self.eeg_file = open(self.eeg_path, "w")
                self.eeg_file.write(EEG_CSV_HEADER + "\n")
                self.eeg_file.flush()

            if self.extra_path:
                Path(self.extra_path).parent.mkdir(parents=True, exist_ok=True)
                self.extra_file = open(self.extra_path, "w")
                self.extra_file.write(EXTRA_CSV_HEADER + "\n")
                self.extra_file.flush()

            self.logger.info(f"CSV files opened - EEG: {self.eeg_path}, Other: {self.extra_path}")
            return True

        except Exception as e:
            self.logger.error(f"Error opening CSV files: {e}")
            return False

    @staticmethod
    def _format_float(value: float) -> str:
        """
        Format float to remove trailing zeros

        Args:
            value: Float value to format

        Returns:
            Formatted string representation
        """
        return f"{value:g}" if value != 0 else "0"

    def write_eeg_packet(self, packet: EEGPacket) -> bool:
        """
        Write EEG packet to CSV file or stdout

        Args:
            packet: EEG packet to write

        Returns:
            True if write successful, False otherwise
        """
        try:
            # Build CSV line
            csv_line = (
                f"{packet.timestamp:.3f},{packet.event_id},{packet.counter},"
                f"{self._format_float(packet.ref)},{self._format_float(packet.drl)}"
            )

            for ch_val in packet.channels:
                csv_line += f",{self._format_float(ch_val)}"
            csv_line += f",{packet.feature_status}"

            if self.eeg_file:
                # Write to CSV file
                self.eeg_file.write(csv_line + "\n")
                self.eeg_file.flush()
            else:
                # Output to stdout if no CSV file specified
                print(csv_line)

            return True

        except Exception as e:
            self.logger.error(f"Error writing EEG packet: {e}")
            return False

    def write_other_event(self, packet: bytes) -> bool:
        """
        Write non-EEG event to extra CSV file

        Args:
            packet: Raw packet bytes

        Returns:
            True if write successful, False otherwise
        """
        if not self.extra_file:
            return True  # Skip if no extra file specified

        try:
            timestamp = time.time()
            event_id = packet[1]
            counter = packet[3]
            data_len = packet[2]
            raw_payload = packet[4:60].hex()
            feature_status = packet[60] if len(packet) > 60 else 0

            csv_line = (
                f"{timestamp:.3f},{event_id},{counter},{data_len},{raw_payload},{feature_status}\n"
            )
            self.extra_file.write(csv_line)
            self.extra_file.flush()
            return True

        except Exception as e:
            self.logger.error(f"Error writing other event: {e}")
            return False

    def close(self) -> None:
        """Close CSV files safely"""
        if self.eeg_file:
            try:
                self.eeg_file.close()
                self.logger.info(f"EEG CSV file closed: {self.eeg_path}")
            except Exception as e:
                self.logger.error(f"Error closing EEG CSV: {e}")
            finally:
                self.eeg_file = None

        if self.extra_file:
            try:
                self.extra_file.close()
                self.logger.info(f"Extra events CSV file closed: {self.extra_path}")
            except Exception as e:
                self.logger.error(f"Error closing extra CSV: {e}")
            finally:
                self.extra_file = None


class WebSocketStreamer:
    """Handles real-time WebSocket streaming of EEG data"""

    def __init__(self, url: Optional[str] = None):
        """
        Initialize WebSocket streamer

        Args:
            url: WebSocket URL to connect to
        """
        self.url = url
        self.client: Optional[Any] = None
        self.connected = False
        self.logger = get_logger(__name__)

        if url and WEBSOCKET_AVAILABLE:
            self._connect()

    def _connect(self) -> bool:
        """
        Connect to WebSocket server

        Returns:
            True if connection successful, False otherwise
        """
        if not WEBSOCKET_AVAILABLE:
            self.logger.error(
                "WebSocket support not available. Install: pip install websocket-client"
            )
            return False

        if not self.url:
            return True

        def on_open(ws: Any) -> None:
            self.connected = True
            self.logger.info(f"WebSocket connected: {self.url}")

        def on_error(ws: Any, error: Any) -> None:
            self.logger.error(f"WebSocket error: {error}")

        def on_close(ws: Any, close_status_code: Any, close_msg: Any) -> None:
            self.connected = False
            self.logger.info(f"WebSocket closed: {close_status_code} - {close_msg}")

        try:
            self.logger.info(f"Connecting to WebSocket: {self.url}")
            self.client = websocket.WebSocketApp(
                self.url, on_open=on_open, on_error=on_error, on_close=on_close
            )

            # Start WebSocket connection in separate thread
            def run_websocket() -> None:
                if self.client:
                    self.client.run_forever()

            ws_thread = threading.Thread(target=run_websocket, daemon=True)
            ws_thread.start()

            # Wait for connection
            time.sleep(1.0)
            return self.connected

        except Exception as e:
            self.logger.error(f"WebSocket connection failed: {e}")
            return False

    def send_eeg_data(self, packet: EEGPacket) -> bool:
        """
        Send EEG packet as JSON to WebSocket

        Args:
            packet: EEG packet to send

        Returns:
            True if send successful, False otherwise
        """
        if not self.client or not self.connected:
            return False

        try:
            eeg_data = {
                "timestamp": packet.timestamp,
                "event_id": packet.event_id,
                "counter": packet.counter,
                "ref": packet.ref,
                "drl": packet.drl,
                "channels": {f"ch{i + 1}": packet.channels[i] for i in range(len(packet.channels))},
                "feature_status": packet.feature_status,
                "type": "eeg_data",
            }

            self.client.send(json.dumps(eeg_data))
            return True

        except Exception as e:
            self.logger.error(f"WebSocket send error: {e}")
            return False

    def close(self) -> None:
        """Close WebSocket connection"""
        if self.client:
            try:
                self.logger.info("Closing WebSocket connection...")
                self.connected = False
                self.client.close()
                self.logger.info("WebSocket closed")
            except Exception as e:
                self.logger.error(f"Error closing WebSocket: {e}")
            finally:
                self.client = None


class StdoutStreamer:
    """Handles EEG data output to stdout (console)"""

    def __init__(self, print_header: bool = True):
        """
        Initialize stdout streamer

        Args:
            print_header: Whether to print CSV header to stdout
        """
        self.logger = get_logger(__name__)

        if print_header:
            self._print_header()

    def _print_header(self) -> None:
        """Print CSV header to stdout"""
        print(EEG_CSV_HEADER)

    @staticmethod
    def _format_float(value: float) -> str:
        """Format float to remove trailing zeros"""
        return f"{value:g}" if value != 0 else "0"

    def write_eeg_packet(self, packet: EEGPacket) -> bool:
        """
        Write EEG packet to stdout

        Args:
            packet: EEG packet to write

        Returns:
            True if write successful, False otherwise
        """
        try:
            csv_line = (
                f"{packet.timestamp:.3f},{packet.event_id},{packet.counter},"
                f"{self._format_float(packet.ref)},{self._format_float(packet.drl)}"
            )

            for ch_val in packet.channels:
                csv_line += f",{self._format_float(ch_val)}"
            csv_line += f",{packet.feature_status}"

            print(csv_line)
            return True

        except Exception as e:
            self.logger.error(f"Error writing to stdout: {e}")
            return False


class LSLStreamer:
    """Handles real-time LSL (Lab Streaming Layer) streaming of EEG data"""

    def __init__(self, stream_name: str = "MW75_EEG", stream_type: str = "EEG"):
        """
        Initialize LSL streamer

        Args:
            stream_name: Name of the LSL stream (default: "MW75_EEG")
            stream_type: Type of the LSL stream (default: "EEG")
        """
        self.stream_name = stream_name
        self.stream_type = stream_type
        self.outlet: Optional[Any] = None
        self.logger = get_logger(__name__)
        self.available = LSL_AVAILABLE

        if not LSL_AVAILABLE:
            raise ImportError(
                "LSL support not available. Install LSL library:\n"
                'macOS: brew install labstreaminglayer/tap/lsl && export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"\n'
                "Then: pip install pylsl"
            )

        self._create_outlet()

    def _create_outlet(self) -> None:
        """Create LSL stream outlet for EEG data"""
        if not LSL_AVAILABLE:
            return

        try:
            # Create stream info
            # MW75 has 12 EEG channels + REF + DRL = 14 channels total
            n_channels = NUM_EEG_CHANNELS + 2  # 12 EEG + REF + DRL
            sample_rate = 500.0  # MW75 streams at 500 Hz

            info = pylsl.StreamInfo(
                name=self.stream_name,
                type=self.stream_type,
                channel_count=n_channels,
                nominal_srate=sample_rate,
                channel_format=pylsl.cf_float32,
                source_id=f"MW75_{self.stream_name}",
            )

            # Add channel information
            channels = info.desc().append_child("channels")

            # REF channel
            ref_ch = channels.append_child("channel")
            ref_ch.append_child_value("label", "REF")
            ref_ch.append_child_value("unit", "microvolts")
            ref_ch.append_child_value("type", "EEG")

            # DRL channel
            drl_ch = channels.append_child("channel")
            drl_ch.append_child_value("label", "DRL")
            drl_ch.append_child_value("unit", "microvolts")
            drl_ch.append_child_value("type", "EEG")

            # EEG channels (Ch1-Ch12)
            for i in range(NUM_EEG_CHANNELS):
                ch = channels.append_child("channel")
                ch.append_child_value("label", f"Ch{i + 1}")
                ch.append_child_value("unit", "microvolts")
                ch.append_child_value("type", "EEG")

            # Add acquisition information
            acquisition = info.desc().append_child("acquisition")
            acquisition.append_child_value("manufacturer", "Master & Dynamic")
            acquisition.append_child_value("model", "MW75 Neuro")
            acquisition.append_child_value("serial_number", "unknown")

            # Add processing information
            processing = info.desc().append_child("processing")
            processing.append_child_value("software", "MW75 EEG Streamer")
            processing.append_child_value("version", "1.0.2")
            processing.append_child_value("scaling_factor", "0.023842")
            processing.append_child_value("developer", "Arctop")

            # Create outlet
            self.outlet = pylsl.StreamOutlet(info)

            self.logger.info(f"LSL stream created: {self.stream_name}")
            self.logger.info(f"   Type: {self.stream_type}")
            self.logger.info(f"   Channels: {n_channels} (REF, DRL, Ch1-Ch12)")
            self.logger.info(f"   Sample Rate: {sample_rate} Hz")
            self.logger.info("   Format: float32")

        except Exception as e:
            self.logger.error(f"Failed to create LSL stream: {e}")
            self.outlet = None

    def send_eeg_data(self, packet: EEGPacket) -> bool:
        """
        Send EEG packet to LSL stream

        Args:
            packet: EEG packet to send

        Returns:
            True if send successful, False otherwise
        """
        if not self.outlet or not LSL_AVAILABLE:
            return False

        try:
            # Prepare data: [REF, DRL, Ch1, Ch2, ..., Ch12]
            sample = [packet.ref, packet.drl] + packet.channels

            # Send sample with timestamp
            # LSL uses pylsl.local_clock() for high-precision timing
            self.outlet.push_sample(sample, timestamp=packet.timestamp)

            return True

        except Exception as e:
            self.logger.error(f"LSL send error: {e}")
            return False

    def close(self) -> None:
        """Close LSL stream outlet"""
        if self.outlet:
            try:
                self.logger.info("Closing LSL stream outlet...")
                # LSL outlet automatically cleans up when object is destroyed
                self.outlet = None
                self.logger.info("LSL stream closed")
            except Exception as e:
                self.logger.error(f"Error closing LSL stream: {e}")

    def get_stream_info(self) -> dict:
        """
        Get information about the current LSL stream

        Returns:
            Dictionary with stream information
        """
        if not self.outlet or not LSL_AVAILABLE:
            return {"available": False, "error": "LSL not available or outlet not created"}

        try:
            info = self.outlet.info()
            return {
                "available": True,
                "name": info.name(),
                "type": info.type(),
                "channel_count": info.channel_count(),
                "sample_rate": info.nominal_srate(),
                "source_id": info.source_id(),
                "format": info.channel_format(),
            }
        except Exception as e:
            return {"available": False, "error": str(e)}
