"""
MW75 WebSocket Server CLI Entry Point

Command-line interface for starting the MW75 WebSocket server.
"""

import argparse
import asyncio
import sys

from ..utils.logging import get_logger, setup_logging
from .ws_server import MW75Device, MW75WebSocketServer


async def main() -> None:
    """Main entry point for MW75 WebSocket server"""
    parser = argparse.ArgumentParser(
        description="MW75 WebSocket Server - Remote Control Mode",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m mw75_streamer.server                    # Start on default port 8080
  python -m mw75_streamer.server --port 9000        # Start on custom port
  python -m mw75_streamer.server --host 0.0.0.0     # Listen on all interfaces

WebSocket Protocol:
  Multiple clients can connect simultaneously. One client controls device connection.
  Client commands:
    {"id": "uuid", "type": "connect", "data": {"auto_reconnect": true, "log_level": "ERROR"}}
    {"id": "uuid", "type": "disconnect", "data": {}}
    {"id": "uuid", "type": "status", "data": {}}
    {"id": "uuid", "type": "broadcast", "data": {"custom": "message"}}

  Server responds with status, eeg_data, log, error, and broadcast messages.
  All clients receive EEG data and status updates. Broadcasts forwarded to all clients.
""",
    )

    parser.add_argument(
        "--port", "-p", type=int, default=8080, help="Port to listen on (default: 8080)"
    )

    parser.add_argument("--host", default="localhost", help="Host to bind to (default: localhost)")

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use mock MW75 device for development (no hardware required, cross-platform)",
    )

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose, "mw75_server")
    logger = get_logger(__name__)

    # Check platform support (skip check if using mock)
    if not args.mock and MW75Device is None:
        logger.error("MW75 real-device mode is only available on macOS and Windows")
        logger.error("Current platform: %s", sys.platform)
        logger.info("Tip: Use --mock flag for development with synthetic data")
        sys.exit(1)

    try:
        # Create and start server
        server = MW75WebSocketServer(host=args.host, port=args.port, use_mock=args.mock)
        await server.start()

    except KeyboardInterrupt:
        logger.info("\nServer stopped by user (Ctrl+C)")
    except asyncio.CancelledError:
        logger.info("\nServer cancelled")
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)


def run() -> None:
    """Entry point that handles keyboard interrupt properly"""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # asyncio.run() handles cleanup, just exit cleanly
        print("\nServer stopped", file=sys.stderr)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    run()
