"""
MW75 WebSocket Server CLI Entry Point

Command-line interface for starting the MW75 WebSocket server.
"""

import asyncio
import argparse
import sys
from typing import TYPE_CHECKING

from ..utils.logging import setup_logging, get_logger

# Platform check
if TYPE_CHECKING or sys.platform == "darwin":
    from .ws_server import MW75WebSocketServer

if sys.platform != "darwin":
    MW75WebSocketServer = None  # type: ignore[assignment, misc]  # noqa: F811


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
  Client connects and sends JSON commands:
    {"id": "uuid", "type": "connect", "data": {"auto_reconnect": true, "log_level": "ERROR"}}
    {"id": "uuid", "type": "disconnect", "data": {}}
    {"id": "uuid", "type": "status", "data": {}}

  Server responds with status, eeg_data, log, and error messages.
""",
    )

    parser.add_argument(
        "--port", "-p", type=int, default=8080, help="Port to listen on (default: 8080)"
    )

    parser.add_argument("--host", default="localhost", help="Host to bind to (default: localhost)")

    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose, "mw75_server")
    logger = get_logger(__name__)

    # Check platform support
    if MW75WebSocketServer is None:
        logger.error("MW75 WebSocket server is only available on macOS")
        logger.error("Current platform: %s", sys.platform)
        sys.exit(1)

    try:
        # Create and start server
        server = MW75WebSocketServer(host=args.host, port=args.port)
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
