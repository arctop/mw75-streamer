"""
MW75 EEG Streamer

A clean, modular package for streaming EEG data from MW75 Neuro headphones
using BLE activation and RFCOMM data streaming.

Developed by Arctop (https://arctop.com)
"""

__version__ = "1.0.8"
__author__ = "Eitan Kay"
__email__ = "opensource@arctop.com"
__maintainer__ = "Arctop"
__company__ = "Arctop"

# Import main classes for easy access
# Import device classes conditionally (macOS only)
import sys

from .data.packet_processor import ChecksumStats, EEGPacket, PacketProcessor
from .data.streamers import CSVWriter, StdoutStreamer, WebSocketStreamer

if sys.platform == "darwin":
    from .device.ble_manager import BLEManager  # noqa: F401
    from .device.mw75_device import MW75Device  # noqa: F401
    from .device.rfcomm_manager import RFCOMMManager  # noqa: F401
elif sys.platform == "win32":
    from .device.ble_manager import BLEManager  # noqa: F401
    from .device.mw75_device import MW75Device  # noqa: F401
    from .device.windows_rfcomm_manager import RFCOMMManager  # noqa: F401
else:
    # On non-macOS platforms, these will be None
    MW75Device = None
    BLEManager = None
    RFCOMMManager = None

# Import LSL conditionally
try:
    from .data.streamers import LSLStreamer  # noqa: F401

    _LSL_AVAILABLE = True
except ImportError:
    _LSL_AVAILABLE = False

# Import testing utilities
from .testing import open_browser_test, show_quick_start, validate_test_setup

__all__ = [
    "EEGPacket",
    "PacketProcessor",
    "ChecksumStats",
    "CSVWriter",
    "WebSocketStreamer",
    "StdoutStreamer",
    "MW75Device",
    "BLEManager",
    "RFCOMMManager",
    # Testing utilities
    "show_quick_start",
    "open_browser_test",
    "validate_test_setup",
]

# Add LSLStreamer to __all__ only if available
if _LSL_AVAILABLE:
    __all__.append("LSLStreamer")
