"""
MW75 EEG Streamer - Main Entry Point

Clean main function and CLI interface for the MW75 EEG streamer.
"""

import sys
import asyncio
import argparse
from typing import Optional, List, Any, TYPE_CHECKING, Callable
import time
import webbrowser
import os
import logging
from logging import Logger

from .utils.logging import setup_logging, get_logger
from .data.packet_processor import PacketProcessor

# Type checking imports
if TYPE_CHECKING:
    # Import the actual type for MyPy, even if it might not work at runtime
    try:
        from .device.mw75_device import MW75Device
    except ImportError:
        # On platforms where PyObjC dependencies aren't available
        MW75Device = Any  # type: ignore

# Runtime platform detection
if sys.platform == "darwin":
    from .device.mw75_device import MW75Device as _MW75Device  # noqa: F401
else:
    _MW75Device = None
from .data.streamers import CSVWriter, WebSocketStreamer, StdoutStreamer, LSLStreamer
from .data.packet_processor import EEGPacket
from .panel.panel_server import PanelServer, WebSocketLogHandler


class MW75Streamer:
    """Main MW75 EEG streamer application"""

    device: "MW75Device"

    def __init__(
        self,
        csv_file: Optional[str] = None,
        extra_file: Optional[str] = None,
        websocket_url: Optional[str] = None,
        lsl_stream_name: Optional[str] = None,
        panel_server: Optional[PanelServer] = None,
        verbose: Optional[bool] = False,
        eeg_callback: Optional[Callable[[EEGPacket], None]] = None,
        raw_data_callback: Optional[Callable[[bytes], None]] = None,
        other_event_callback: Optional[Callable[[bytes], None]] = None,
    ):
        """
        Initialize MW75 streamer

        Args:
            csv_file: Path for EEG CSV output file
            extra_file: Path for other events CSV output file
            websocket_url: WebSocket URL for real-time streaming
            lsl_stream_name: LSL stream name for LSL streaming
            panel_server: Panel server for browser dashboard
            verbose: Enable verbose logging
            eeg_callback: Custom callback function for EEG packets (receives EEGPacket objects)
            raw_data_callback: Custom callback function for raw device data (receives bytes)
            other_event_callback: Custom callback function for non-EEG events (receives bytes)
        """
        # Store custom callbacks
        self.eeg_callback = eeg_callback
        self.raw_data_callback = raw_data_callback
        self.other_event_callback = other_event_callback
        self.csv_writer = CSVWriter(csv_file, extra_file)
        self.websocket_streamer = WebSocketStreamer(websocket_url)
        self.verbose = verbose

        # Initialize LSL streamer with error handling
        self.lsl_streamer = None
        if lsl_stream_name:
            try:
                self.lsl_streamer = LSLStreamer(lsl_stream_name)
            except ImportError as e:
                self.logger = get_logger(__name__)
                self.logger.error(f"Failed to initialize LSL streamer: {e}")
                sys.exit(1)

        # Suppress stdout printing when browser panel is used or custom callback is provided
        if panel_server is not None:
            self.stdout_streamer = None
        else:
            self.stdout_streamer = StdoutStreamer(
                print_header=(
                    not csv_file and not websocket_url and not lsl_stream_name and not eeg_callback
                )
            )
        self.packet_processor = PacketProcessor(self.verbose or False)

        self.logger = get_logger(__name__)

        # Panel server relay and runtime stats
        self.panel_server = panel_server
        self.last_counter: Optional[int] = None
        self.dropped_packets: int = 0
        self._rate_times: List[float] = []
        self._last_stats_emit: float = 0.0

        # Initialize device with data callback
        if _MW75Device is None:
            raise RuntimeError("MW75Device not available on this platform")
        self.device = _MW75Device(self._handle_device_data)

    def set_verbose(self, verbose: bool) -> None:
        """
        Enable or disable verbose logging including checksum error messages

        Args:
            verbose: True to enable verbose logging, False to suppress it
        """
        self.verbose = verbose
        self.packet_processor.verbose = verbose
        self.logger.debug(f"Verbose logging {'enabled' if verbose else 'disabled'}")

    def _handle_device_data(self, data: bytes) -> None:
        """Handle raw data received from MW75 device"""
        # Call raw data callback if provided
        if self.raw_data_callback:
            try:
                self.raw_data_callback(data)
            except Exception as e:
                self.logger.error(f"Error in raw data callback: {e}")

        # Process the data into packets
        self.packet_processor.process_data_buffer(
            data, self._handle_eeg_packet, self._handle_other_event
        )

    def _handle_eeg_packet(self, packet: EEGPacket) -> None:
        """Handle processed EEG packet"""
        # Call user's custom EEG callback if provided
        if self.eeg_callback:
            try:
                self.eeg_callback(packet)
            except Exception as e:
                self.logger.error(f"Error in EEG callback: {e}")

        # Sequence tracking for dropped packets
        try:
            if self.last_counter is not None:
                expected = (self.last_counter + 1) % 256
                if packet.counter != expected:
                    dropped = (packet.counter - expected) % 256
                    self.dropped_packets += dropped
            self.last_counter = packet.counter
        except Exception:
            pass

        # Write to CSV file if specified
        if self.csv_writer.eeg_file:
            self.csv_writer.write_eeg_packet(packet)
        elif (
            self.stdout_streamer
            and not self.websocket_streamer.connected
            and not self.lsl_streamer
            and not self.eeg_callback
        ):
            # Write to stdout if no other outputs
            self.stdout_streamer.write_eeg_packet(packet)

        # Send to WebSocket if connected
        self.websocket_streamer.send_eeg_data(packet)

        # Send to LSL if configured
        if self.lsl_streamer:
            self.lsl_streamer.send_eeg_data(packet)

        # Debug logging
        self.logger.debug(
            f"EEG Packet: counter={packet.counter}, channels={len(packet.channels)}, checksum=OK"
        )

        # Relay to panel if clients are connected
        if self.panel_server:
            # Lightweight rate tracking (packets per 5s window)
            now = time.time()
            self._rate_times.append(now)
            five_sec_ago = now - 5.0
            self._rate_times = [t for t in self._rate_times if t > five_sec_ago]

            # Publish EEG
            self.panel_server.publish_eeg(
                {
                    "timestamp": packet.timestamp,
                    "event_id": packet.event_id,
                    "counter": packet.counter,
                    "ref": packet.ref,
                    "drl": packet.drl,
                    "channels": {
                        f"ch{i + 1}": packet.channels[i] for i in range(len(packet.channels))
                    },
                    "feature_status": packet.feature_status,
                }
            )

            # Throttle stats emission to 5 Hz
            if now - self._last_stats_emit > 0.2:
                stats = self.packet_processor.get_final_stats()
                current_rate = len(self._rate_times) / 5.0
                self.panel_server.publish_stats(
                    {
                        "total_packets": stats.total_packets,
                        "invalid_packets": stats.invalid_packets,
                        "valid_packets": stats.valid_packets,
                        "error_rate": stats.error_rate,
                        "dropped_packets": self.dropped_packets,
                        "rate": current_rate,
                    }
                )
                self._last_stats_emit = now

    def _handle_other_event(self, packet: bytes) -> None:
        """Handle non-EEG events"""
        # Call user's custom other event callback if provided
        if self.other_event_callback:
            try:
                self.other_event_callback(packet)
            except Exception as e:
                self.logger.error(f"Error in other event callback: {e}")

        self.csv_writer.write_other_event(packet)

        event_id = packet[1] if len(packet) > 1 else 0
        counter = packet[3] if len(packet) > 3 else 0
        self.logger.debug(f"Other Event: event_id={event_id}, counter={counter}")

    async def start_streaming(self) -> bool:
        """
        Start the MW75 streaming process

        Returns:
            True if streaming completed successfully, False otherwise
        """
        try:
            self.logger.info("MW75 EEG Streamer - Starting...")

            # Connect and stream data
            success = await self.device.connect_and_stream()

            return bool(success)

        except Exception as e:
            self.logger.error(f"Error during streaming: {e}")
            return False
        finally:
            await self._cleanup()

    async def _cleanup(self) -> None:
        """Clean up all resources"""
        self.logger.info("Cleaning up streamer resources...")

        # Print final statistics
        stats = self.packet_processor.get_final_stats()
        if stats.total_packets > 0:
            self.logger.info(
                f"Final Stats: {stats.total_packets} packets, "
                f"{stats.valid_packets} valid ({100 - stats.error_rate:.1f}%), "
                f"{stats.invalid_packets} invalid ({stats.error_rate:.1f}%)"
            )

        # Close output streams
        self.csv_writer.close()
        self.websocket_streamer.close()
        if self.lsl_streamer:
            self.lsl_streamer.close()

        self.logger.info("Cleanup complete - stream stopped safely")


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="MW75 EEG Streamer - Stream EEG data to CSV files and/or WebSocket",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m mw75_streamer                                   # EEG data to stdout
  python -m mw75_streamer --browser                         # Open dashboard panel
  python -m mw75_streamer > eeg_data.csv                    # Redirect stdout to file
  python -m mw75_streamer --csv eeg_data.csv                # EEG to CSV file
  python -m mw75_streamer --csv eeg.csv --extra events.csv  # Both CSV files
  python -m mw75_streamer --ws ws://localhost:8080          # WebSocket streaming only
  python -m mw75_streamer --lsl MW75_EEG                    # LSL streaming only
""",
    )

    parser.add_argument(
        "-csv",
        "--csv-file",
        help="Output file for EEG data (Event ID 239). If not specified, EEG data prints to stdout",
    )

    parser.add_argument(
        "-extra",
        "--extra-file",
        help="Output file for other events (non-EEG). Default: other_events.csv if CSV mode is used",
    )

    parser.add_argument(
        "-ws",
        "--websocket",
        help="WebSocket URL for real-time EEG streaming (ws://host:port/path or wss://host:port/path)",
    )

    parser.add_argument(
        "-lsl",
        "--lsl-stream",
        help='LSL stream name for Lab Streaming Layer output (e.g., "MW75_EEG")',
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    # Browser dashboard panel
    parser.add_argument(
        "-b",
        "--browser",
        action="store_true",
        help="Open browser dashboard (panel) and start internal WebSocket relay",
    )
    parser.add_argument(
        "--panel-host",
        default="localhost",
        help="Host for internal panel WebSocket relay (default: localhost)",
    )
    parser.add_argument(
        "--panel-port",
        type=int,
        default=8090,
        help="Port for internal panel WebSocket relay (default: 8090)",
    )

    args = parser.parse_args()

    # Handle default values and validation
    if not args.csv_file and not args.websocket and not args.lsl_stream and not args.browser:
        print(
            "No output specified - streaming EEG data to stdout",
            file=sys.stderr,
        )
    # Don't default extra_file anymore - let it be None to skip extra events

    return args


def show_output_configuration(args: argparse.Namespace, logger: Logger) -> None:
    """Display output configuration to user"""
    logger.info("Streaming data to:")

    if args.csv_file:
        logger.info(f"EEG CSV (Event ID 239): {args.csv_file}")
        if args.extra_file:
            logger.info(f"Other Events CSV: {args.extra_file}")
        else:
            logger.info("Other Events: discarded (use --extra to save)")
    elif args.websocket:
        logger.info(f"WebSocket EEG Stream: {args.websocket}")
    elif args.lsl_stream:
        logger.info(f"LSL Stream: {args.lsl_stream} (Lab Streaming Layer)")
    elif args.browser:
        logger.info("Browser Dashboard Panel")
    else:
        logger.info("EEG Data: stdout (console)")

    logger.info("Press Ctrl+C to stop streaming")


async def main() -> None:
    """Main entry point for the MW75 EEG streamer"""
    try:
        args = parse_arguments()
    except SystemExit:
        return

    # Setup logging
    setup_logging(args.verbose, "mw75_streamer")
    logger = get_logger(__name__)

    # Check if running on supported platform
    if _MW75Device is None:
        logger.error("MW75 device support is only available on macOS")
        logger.error("Current platform: %s", sys.platform)
        logger.info(
            "For cross-platform support contributions, see: https://github.com/arctop/mw75-streamer/blob/main/CONTRIBUTING.md"
        )
        return

    # Optional panel server for browser dashboard
    panel_server: Optional[PanelServer] = None
    ws_log_handler: Optional[WebSocketLogHandler] = None

    if getattr(args, "browser", False):
        try:
            panel_server = PanelServer(
                host=getattr(args, "panel_host", "localhost"),
                port=getattr(args, "panel_port", 8090),
            )
        except ImportError as e:
            logger.error(str(e))
            panel_server = None

    # Show configuration
    show_output_configuration(args, logger)

    # Create and start streamer
    streamer = MW75Streamer(
        csv_file=args.csv_file,
        extra_file=args.extra_file,
        websocket_url=args.websocket,
        lsl_stream_name=args.lsl_stream,
        panel_server=panel_server,
        verbose=args.verbose,
    )

    # Start panel server and open browser if requested
    if panel_server:
        # Run the panel server in background to avoid blocking
        panel_server.start_background()
        # Attach WebSocket logging handler to top-level package logger
        top_logger = logging.getLogger("mw75_streamer")
        ws_log_handler = WebSocketLogHandler(panel_server)
        ws_log_handler.setLevel(logging.DEBUG if args.verbose else logging.INFO)
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )
        ws_log_handler.setFormatter(formatter)
        top_logger.addHandler(ws_log_handler)

        # Auto-open panel HTML in browser
        try:
            panel_html = os.path.join(os.path.dirname(__file__), "panel", "panel.html")
            webbrowser.open(f"file://{panel_html}")
        except Exception:
            logger.warning("Failed to open browser automatically. Open panel/panel.html manually.")

    success = await streamer.start_streaming()

    if not success:
        logger.error("Streaming failed")
        sys.exit(1)

    # Cleanup panel server
    if panel_server:
        try:
            top_logger = logging.getLogger("mw75_streamer")
            if ws_log_handler:
                top_logger.removeHandler(ws_log_handler)
            panel_server.stop_background()
        except Exception:
            pass


def cli_main() -> None:
    """Synchronous entry point for CLI console scripts"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        sys.exit(1)
