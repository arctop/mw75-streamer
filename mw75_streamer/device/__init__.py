"""
MW75 Device Management

Modules for handling MW75 device connections, BLE activation, and RFCOMM streaming.
"""

import sys
from typing import List

if sys.platform == "darwin":
    from .ble_manager import BLEManager  # noqa: F401
    from .rfcomm_manager import RFCOMMManager, RFCOMMDelegate  # noqa: F401
    from .mw75_device import MW75Device  # noqa: F401

    __all__: List[str] = [
        "BLEManager",
        "RFCOMMManager",
        "RFCOMMDelegate",
        "MW75Device",
    ]
else:
    # On non-macOS platforms, these will be None
    BLEManager = None
    RFCOMMManager = None
    RFCOMMDelegate = None
    MW75Device = None

    __all__: List[str] = []
