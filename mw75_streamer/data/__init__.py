"""
MW75 Data Processing

Modules for processing MW75 EEG packets and streaming data to various outputs.
"""

from .packet_processor import EEGPacket, PacketProcessor, ChecksumStats
from .streamers import CSVWriter, WebSocketStreamer, StdoutStreamer

# Import LSLStreamer conditionally
try:
    from .streamers import LSLStreamer  # noqa: F401

    _LSL_AVAILABLE = True
except ImportError:
    _LSL_AVAILABLE = False

__all__ = [
    "EEGPacket",
    "PacketProcessor",
    "ChecksumStats",
    "CSVWriter",
    "WebSocketStreamer",
    "StdoutStreamer",
]

# Add LSLStreamer to __all__ only if available
if _LSL_AVAILABLE:
    __all__.append("LSLStreamer")
