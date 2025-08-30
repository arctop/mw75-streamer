"""
WebSocket Test Servers for MW75 EEG Streamer

Provides WebSocket test servers for validating EEG streaming functionality.
"""

import asyncio
import json
import time
import sys
import os
import webbrowser
from datetime import datetime
from typing import Set, Optional, Any, List, Dict, Union

# WebSocket imports with fallback
try:
    import websockets

    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

from ..utils.logging import get_logger


class SimpleWebSocketServer:
    """Minimal WebSocket server for quick testing"""

    def __init__(self, host: str = "localhost", port: int = 8080, verbose: bool = False):
        """
        Initialize simple WebSocket server

        Args:
            host: Host to bind to
            port: Port to listen on
            verbose: Enable detailed logging output
        """
        self.host = host
        self.port = port
        self.verbose = verbose
        self.packet_count = 0
        self.logger = get_logger(__name__)

        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library not found. Install with: pip install websockets")

    async def handle_connection(self, websocket: Any) -> None:
        """Handle WebSocket connections"""
        client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.logger.info(f"New connection from {client_address}")

        try:
            async for message in websocket:
                self.packet_count += 1

                try:
                    # Parse the JSON EEG data
                    eeg_data = json.loads(message)

                    # Extract key info
                    timestamp = eeg_data.get("timestamp", 0)
                    counter = eeg_data.get("counter", 0)
                    channels = eeg_data.get("channels", {})

                    # Display every 10th packet to avoid spam (only if verbose)
                    if self.verbose and self.packet_count % 10 == 0:
                        dt = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3]

                        # Get a few channel values
                        ch_values = []
                        for i in range(min(3, len(channels))):
                            ch_name = f"ch{i + 1}"
                            if ch_name in channels:
                                ch_values.append(f"{channels[ch_name]:.1f}")

                        self.logger.info(
                            f"#{self.packet_count:4d} | {dt} | Counter: {counter:3d} | "
                            f"Channels: [{', '.join(ch_values)}...] µV"
                        )

                except json.JSONDecodeError:
                    self.logger.error(f"Invalid JSON in packet #{self.packet_count}")

        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Connection closed. Total packets received: {self.packet_count}")

    async def start(self) -> None:
        """Start the WebSocket server"""
        self.logger.info("Simple MW75 EEG WebSocket Test Server")
        self.logger.info(f"Starting on ws://{self.host}:{self.port}")
        self.logger.info("Connect with:")
        self.logger.info(f"   python -m mw75_streamer -ws ws://{self.host}:{self.port}")
        self.logger.info("\n" + "=" * 70)

        async with websockets.serve(self.handle_connection, self.host, self.port):
            self.logger.info(f"Server ready! Listening on ws://{self.host}:{self.port}")
            self.logger.info("Press Ctrl+C to stop")
            await asyncio.Future()  # Run forever


class WebSocketTestServer:
    """Full-featured WebSocket test server with advanced statistics"""

    def __init__(self, host: str = "localhost", port: int = 8080, verbose: bool = False):
        """
        Initialize advanced WebSocket server

        Args:
            host: Host to bind to
            port: Port to listen on
            verbose: Enable detailed logging output
        """
        self.host = host
        self.port = port
        self.verbose = verbose
        self.packet_count = 0
        self.start_time: Optional[float] = None
        self.last_counter = None
        self.dropped_packets = 0
        self.browser_clients: Set = set()
        self.packet_timestamps: List[float] = []  # Track packet arrival times for rate calculation

        # Enhanced statistics tracking
        self.session_start_time: Optional[float] = None
        self.first_packet_time: Optional[float] = None
        self.last_packet_time: Optional[float] = None
        self.total_bytes_received = 0
        self.channel_stats: Dict[str, Dict[str, float]] = {}  # Track min/max/avg for each channel
        self.disconnection_events = 0
        self.json_errors = 0
        self.browser_client_count = 0
        self.peak_rate = 0.0
        self.rate_history: List[float] = []  # Store rate samples for analysis

        self.logger = get_logger(__name__)

        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library not found. Install with: pip install websockets")

    async def handle_client(self, websocket: Any) -> None:
        """Handle incoming WebSocket connections"""
        client_address = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        path = websocket.request.path
        self.logger.info(f"Client connected: {client_address}, Path: {path}")

        # Determine client type based on path
        is_browser_client = path == "/browser" or "browser" in path.lower()
        if is_browser_client:
            self.browser_clients.add(websocket)
            self.browser_client_count += 1
            self.logger.info("Browser client detected")

        try:
            if is_browser_client:
                # Browser client - just keep connection alive and forward data
                await self._handle_browser_client(websocket)
            else:
                # EEG streamer client - process incoming data
                await self._handle_eeg_client(websocket)

        except websockets.exceptions.ConnectionClosed:
            self.logger.info(f"Client disconnected: {client_address}")
        except Exception as e:
            self.logger.error(f"Error handling client {client_address}: {e}")
        finally:
            if websocket in self.browser_clients:
                self.browser_clients.remove(websocket)

    async def _handle_browser_client(self, websocket: Any) -> None:
        """Handle browser client connections"""
        try:
            # Just keep the connection alive for browser clients
            await websocket.wait_closed()
        except websockets.exceptions.ConnectionClosed:
            pass

    async def _handle_eeg_client(self, websocket: Any) -> None:
        """Handle EEG data from streamer"""
        self.start_time = time.time()

        async for message in websocket:
            try:
                eeg_data = json.loads(message)
                await self._process_eeg_packet(eeg_data)

                # Update byte counter
                self.total_bytes_received += len(message.encode("utf-8"))

                # Forward to browser clients
                await self._broadcast_to_browsers(message)

            except json.JSONDecodeError:
                self.json_errors += 1
                self.logger.error("Invalid JSON received")
            except Exception as e:
                self.logger.error(f"Error processing packet: {e}")

    async def _process_eeg_packet(self, eeg_data: dict) -> None:
        """Process and validate EEG packet"""
        self.packet_count += 1

        # Record packet timestamp for rate calculation
        current_time = time.time()
        self.packet_timestamps.append(current_time)

        # Track session timing
        if self.first_packet_time is None:
            self.first_packet_time = current_time
        self.last_packet_time = current_time

        # Extract packet info
        timestamp = eeg_data.get("timestamp", time.time())
        event_id = eeg_data.get("event_id", 0)
        counter = eeg_data.get("counter", 0)
        ref = eeg_data.get("ref", 0)
        drl = eeg_data.get("drl", 0)
        channels = eeg_data.get("channels", {})
        feature_status = eeg_data.get("feature_status", 0)

        # Check for dropped packets
        if self.last_counter is not None:
            expected = (self.last_counter + 1) % 256
            if counter != expected:
                dropped = (counter - expected) % 256
                self.dropped_packets += dropped
                if self.verbose:
                    self.logger.warning(
                        f"Dropped {dropped} packets (expected {expected}, got {counter})"
                    )

        self.last_counter = counter

        # Display detailed packet info every 100 packets (only if verbose)
        if self.verbose and self.packet_count % 100 == 0:
            self._display_detailed_stats(
                timestamp, event_id, counter, ref, drl, channels, feature_status
            )

        # Check for electrode disconnections and update channel statistics
        if channels:
            disconnected_channels = [ch for ch, val in channels.items() if abs(val - 8388607) < 1]
            if disconnected_channels:
                self.disconnection_events += len(disconnected_channels)
                if self.verbose:
                    self.logger.warning(
                        f"Electrode disconnection detected: {', '.join(disconnected_channels)}"
                    )

            # Update channel statistics for connected channels
            for ch, val in channels.items():
                if abs(val - 8388607) >= 1:  # Not disconnected
                    if ch not in self.channel_stats:
                        self.channel_stats[ch] = {"min": val, "max": val, "sum": val, "count": 1}
                    else:
                        stats = self.channel_stats[ch]
                        stats["min"] = min(stats["min"], val)
                        stats["max"] = max(stats["max"], val)
                        stats["sum"] += val
                        stats["count"] += 1

    def _display_detailed_stats(
        self,
        timestamp: float,
        event_id: int,
        counter: int,
        ref: float,
        drl: float,
        channels: Dict[str, float],
        feature_status: int,
    ) -> None:
        """Display detailed packet statistics"""
        dt = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S.%f")[:-3]

        # Calculate data rate over the last 5 seconds
        current_time = time.time()
        five_seconds_ago = current_time - 5.0

        # Remove timestamps older than 5 seconds
        self.packet_timestamps = [ts for ts in self.packet_timestamps if ts > five_seconds_ago]

        # Calculate rate as packets per second over the last 5 seconds
        rate = len(self.packet_timestamps) / 5.0 if self.packet_timestamps else 0.0

        # Track peak rate and rate history
        if rate > self.peak_rate:
            self.peak_rate = rate
        self.rate_history.append(rate)

        self.logger.info(f"\nEEG Packet #{self.packet_count}:")
        self.logger.info(f"   Timestamp: {dt}")
        self.logger.info(f"   Event ID: {event_id}")
        self.logger.info(f"   Counter: {counter}")
        self.logger.info(f"   REF: {ref:.2f} µV")
        self.logger.info(f"   DRL: {drl:.2f} µV")
        self.logger.info(f"   Channels: {len(channels)} channels")

        if channels:
            # Show first 4 channels as sample
            sample_channels = list(channels.items())[:4]
            channel_str = ", ".join([f"{ch}: {val:.2f}" for ch, val in sample_channels])
            self.logger.info(f"   Sample: {channel_str}...")

        self.logger.info(f"   Feature Status: {feature_status}")
        self.logger.info(
            f"Live Stats: {self.packet_count} packets, {rate:.1f}/sec, {self.dropped_packets} dropped"
        )

    async def _broadcast_to_browsers(self, message: str) -> None:
        """Broadcast message to all connected browser clients"""
        if not self.browser_clients:
            return

        # Remove disconnected clients
        disconnected = set()
        for client in self.browser_clients:
            try:
                await client.send(message)
            except websockets.exceptions.ConnectionClosed:
                disconnected.add(client)
            except Exception as e:
                self.logger.error(f"Error broadcasting to browser client: {e}")
                disconnected.add(client)

        # Clean up disconnected clients
        self.browser_clients -= disconnected

    async def _handle_keyboard_input(self) -> None:
        """Handle keyboard input for server commands"""
        try:
            while True:
                # Use asyncio to read from stdin without blocking
                line = await asyncio.to_thread(sys.stdin.readline)
                if not line:  # EOF
                    break

                command = line.strip().lower()

                if command == "b" or command == "browser":
                    self._open_browser()
                elif command == "s" or command == "stats":
                    self._show_stats()
                elif command == "h" or command == "help":
                    self._show_help()
                elif command == "q" or command == "quit":
                    self.logger.info("Shutting down server...")
                    break

        except Exception:
            # Ignore keyboard interrupt and other exceptions
            pass

    def _open_browser(self) -> None:
        """Open the EEG test client in the default browser"""
        # Find the HTML test client file
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_file = os.path.join(current_dir, "eeg_test_client.html")

        if os.path.exists(html_file):
            file_url = f"file://{html_file}"
            self.logger.info(f"Opening browser with EEG test client: {html_file}")
            try:
                webbrowser.open(file_url)
                self.logger.info("Browser opened successfully")
            except Exception as e:
                self.logger.error(f"Failed to open browser: {e}")
                self.logger.info(f"Manually open: {html_file}")
        else:
            self.logger.error(f"HTML test client not found: {html_file}")

    def _show_stats(self) -> None:
        """Display comprehensive session statistics"""
        current_time = time.time()

        self.logger.info("\n" + "=" * 80)
        self.logger.info("SESSION STATISTICS")
        self.logger.info("=" * 80)

        # Session timing
        if self.session_start_time:
            session_duration = current_time - self.session_start_time
            self.logger.info(
                f"Session Duration: {session_duration:.1f} seconds ({session_duration / 60:.1f} minutes)"
            )

        if self.first_packet_time:
            data_duration = (self.last_packet_time or current_time) - self.first_packet_time
            self.logger.info(f"Data Streaming: {data_duration:.1f} seconds")

        # Packet statistics
        self.logger.info("\nPACKET STATISTICS:")
        self.logger.info(f"   Total Packets: {self.packet_count:,}")
        self.logger.info(f"   Dropped Packets: {self.dropped_packets:,}")
        self.logger.info(f"   JSON Errors: {self.json_errors:,}")

        if self.packet_count > 0:
            drop_rate = (self.dropped_packets / (self.packet_count + self.dropped_packets)) * 100
            self.logger.info(f"   Drop Rate: {drop_rate:.2f}%")

        # Data rate statistics
        self.logger.info("\nDATA RATE STATISTICS:")
        current_rate = len([ts for ts in self.packet_timestamps if ts > current_time - 5]) / 5.0
        self.logger.info(f"   Current Rate: {current_rate:.1f} packets/sec")
        self.logger.info(f"   Peak Rate: {self.peak_rate:.1f} packets/sec")

        if self.rate_history:
            avg_rate = sum(self.rate_history) / len(self.rate_history)
            self.logger.info(f"   Average Rate: {avg_rate:.1f} packets/sec")

        # Expected vs actual rate analysis
        expected_rate = 500  # MW75 streams at 500Hz
        if current_rate > 0:
            rate_efficiency = (current_rate / expected_rate) * 100
            self.logger.info(
                f"   Rate Efficiency: {rate_efficiency:.1f}% (expected: {expected_rate}Hz)"
            )

        # Data volume
        self.logger.info("\nDATA VOLUME:")
        self.logger.info(
            f"   Total Bytes: {self.total_bytes_received:,} bytes ({self.total_bytes_received / 1024 / 1024:.2f} MB)"
        )

        if self.session_start_time and session_duration > 0:
            throughput = (self.total_bytes_received / session_duration) / 1024  # KB/s
            self.logger.info(f"   Throughput: {throughput:.1f} KB/s")

        # Channel statistics
        if self.channel_stats:
            self.logger.info("\nCHANNEL STATISTICS:")
            self.logger.info(f"   Active Channels: {len(self.channel_stats)}")

            # Show stats for first 4 channels as sample
            sample_channels = list(self.channel_stats.items())[:4]
            for ch, stats in sample_channels:
                avg_val = stats["sum"] / stats["count"]
                range_val = stats["max"] - stats["min"]
                self.logger.info(
                    f"   {ch}: avg={avg_val:.1f}µV, range={range_val:.1f}µV, samples={stats['count']:,}"
                )

            if len(self.channel_stats) > 4:
                self.logger.info(f"   ... and {len(self.channel_stats) - 4} more channels")

        # Connection statistics
        self.logger.info("\nCONNECTION STATISTICS:")
        self.logger.info(f"   Current Browser Clients: {len(self.browser_clients)}")
        self.logger.info(f"   Total Browser Connections: {self.browser_client_count}")
        self.logger.info(f"   Electrode Disconnections: {self.disconnection_events}")

        # Quality assessment
        self.logger.info("\nQUALITY ASSESSMENT:")
        issues = []

        if self.dropped_packets > 0:
            drop_rate = (self.dropped_packets / (self.packet_count + self.dropped_packets)) * 100
            if drop_rate > 5:
                issues.append(f"High drop rate ({drop_rate:.1f}%)")
            elif drop_rate > 1:
                issues.append(f"Moderate drop rate ({drop_rate:.1f}%)")

        if current_rate < expected_rate * 0.9:  # Less than 90% of expected rate
            issues.append(f"Low data rate ({current_rate:.1f}/{expected_rate}Hz)")

        if self.json_errors > 0:
            issues.append(f"JSON parsing errors ({self.json_errors})")

        if self.disconnection_events > 10:
            issues.append(f"Frequent electrode disconnections ({self.disconnection_events})")

        if issues:
            self.logger.info(f"   Issues: {', '.join(issues)}")
        else:
            self.logger.info("   No issues detected")

        self.logger.info("=" * 80 + "\n")

    def _show_help(self) -> None:
        """Show available keyboard commands"""
        self.logger.info("\nAvailable Commands:")
        self.logger.info("   b, browser  - Open EEG test client in browser")
        self.logger.info("   s, stats    - Display session statistics")
        self.logger.info("   h, help     - Show this help message")
        self.logger.info("   q, quit     - Stop the server")
        self.logger.info("   Ctrl+C      - Stop the server")

    async def start(self) -> None:
        """Start the advanced WebSocket server"""
        self.session_start_time = time.time()

        self.logger.info("Advanced MW75 EEG WebSocket Test Server")
        self.logger.info(f"Starting on ws://{self.host}:{self.port}")
        self.logger.info("Connect EEG streamer with:")
        self.logger.info(f"   python -m mw75_streamer -ws ws://{self.host}:{self.port}")
        self.logger.info("Connect browser client to:")
        self.logger.info(f"   ws://{self.host}:{self.port}/browser")
        self.logger.info("\n" + "=" * 70)

        # Start keyboard input handler
        keyboard_task = None

        async with websockets.serve(self.handle_client, self.host, self.port):
            self.logger.info(f"Server ready! Listening on ws://{self.host}:{self.port}")
            self.logger.info(
                "Commands: Press 'b' for browser, 's' for stats, 'h' for help, Ctrl+C to stop"
            )

            try:
                # Start keyboard input handling
                keyboard_task = asyncio.create_task(self._handle_keyboard_input())

                # Wait for either keyboard interrupt or keyboard task completion
                await keyboard_task

            except asyncio.CancelledError:
                pass
            finally:
                if keyboard_task and not keyboard_task.done():
                    keyboard_task.cancel()


def main() -> None:
    """CLI entry point for WebSocket test servers"""
    import argparse

    parser = argparse.ArgumentParser(
        description="MW75 EEG WebSocket Test Server",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--host", default="localhost", help="Host to bind to (default: localhost)")

    parser.add_argument(
        "--port", "-p", type=int, default=8080, help="Port to listen on (default: 8080)"
    )

    parser.add_argument(
        "--advanced",
        "-a",
        action="store_true",
        help="Use advanced WebSocket server with detailed statistics and browser support",
    )

    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging (packet details, stats, warnings)",
    )

    args = parser.parse_args()

    try:
        server: Union[SimpleWebSocketServer, WebSocketTestServer]
        if args.advanced:
            server = WebSocketTestServer(args.host, args.port, args.verbose)
        else:
            server = SimpleWebSocketServer(args.host, args.port, args.verbose)

        asyncio.run(server.start())

    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except ImportError as e:
        print(f"{e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
