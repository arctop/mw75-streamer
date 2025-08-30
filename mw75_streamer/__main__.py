"""
MW75 EEG Streamer - Entry point for python -m mw75_streamer
"""

from .main import main
import asyncio
import sys

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user", file=sys.stderr)
    except Exception as e:
        print(f"\nUnexpected error: {e}", file=sys.stderr)
        sys.exit(1)
