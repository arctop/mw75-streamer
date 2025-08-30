"""
MW75 Testing Tools - Main Entry Point

Simple command-line interface for running WebSocket test servers.
"""

import sys
import asyncio
import argparse
from typing import Union

from .websocket_server import SimpleWebSocketServer, WebSocketTestServer
from ..utils.logging import setup_logging, get_logger


def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description="MW75 WebSocket Test Server - Validate EEG streaming functionality",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m mw75_streamer.testing                    # Simple test server
  python -m mw75_streamer.testing --advanced         # Advanced test server with stats
  python -m mw75_streamer.testing --port 9000        # Custom port
  python -m mw75_streamer.testing --host 0.0.0.0     # Listen on all interfaces

Usage:
  1. Start the test server
  2. In another terminal: python -m mw75_streamer -ws ws://localhost:8080
  3. For browser visualization:
     - Advanced server: Press 'b' + Enter to auto-open browser
     - Or manually open eeg_test_client.html in browser
        """,
    )

    parser.add_argument("--host", default="localhost", help="Host to bind to (default: localhost)")

    parser.add_argument("--port", type=int, default=8080, help="Port to listen on (default: 8080)")

    parser.add_argument(
        "--advanced",
        action="store_true",
        help="Use advanced server with detailed statistics and browser support",
    )

    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    return parser.parse_args()


async def run_server(args: argparse.Namespace) -> bool:
    """Run the appropriate WebSocket test server"""
    logger = get_logger(__name__)

    try:
        server: Union[SimpleWebSocketServer, WebSocketTestServer]
        if args.advanced:
            logger.info("Starting advanced WebSocket test server...")
            server = WebSocketTestServer(host=args.host, port=args.port, verbose=args.verbose)
        else:
            logger.info("Starting simple WebSocket test server...")
            server = SimpleWebSocketServer(host=args.host, port=args.port, verbose=args.verbose)

        await server.start()

    except ImportError as e:
        logger.error(f"Missing dependency: {e}")
        logger.info("Install WebSocket support: pip install websockets")
        return False
    except OSError as e:
        if "Address already in use" in str(e):
            logger.error(f"Port {args.port} is already in use. Try a different port with --port")
        else:
            logger.error(f"Network error: {e}")
        return False
    except Exception as e:
        logger.error(f"Server error: {e}")
        return False

    return True


def main() -> None:
    """Main entry point"""
    try:
        args = parse_arguments()
    except SystemExit:
        return

    # Setup logging
    setup_logging(args.verbose, "mw75_streamer.testing")
    logger = get_logger(__name__)

    logger.info("MW75 WebSocket Test Server")
    logger.info(f"Starting on {args.host}:{args.port}")
    if args.advanced:
        logger.info("🔬 Advanced mode: Detailed statistics and browser support enabled")
        logger.info("Browser shortcut: Press 'b' + Enter to open EEG visualization")

    try:
        success = asyncio.run(run_server(args))
        if not success:
            sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
