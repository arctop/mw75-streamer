"""
MW75 EEG Streamer Configuration

Contains all constants, UUIDs, and configuration settings for the MW75 EEG streamer.
"""

from typing import Final

# MW75 BLE Service and Characteristic UUIDs
MW75_SERVICE_UUID: Final[str] = "00001100-d102-11e1-9b23-00025b00a5a5"
MW75_COMMAND_CHAR: Final[str] = "00001101-d102-11e1-9b23-00025b00a5a5"
MW75_STATUS_CHAR: Final[str] = "00001102-d102-11e1-9b23-00025b00a5a5"
MW75_CONTROL_CHAR: Final[str] = "00001103-d102-11e1-9b23-00025b00a5a5"

# BLE Command Sequences
ENABLE_EEG_CMD: Final[bytearray] = bytearray([0x09, 0x9A, 0x03, 0x60, 0x01])
ENABLE_RAW_MODE_CMD: Final[bytearray] = bytearray([0x09, 0x9A, 0x03, 0x41, 0x01])
START_SESSION_CMD: Final[bytearray] = bytearray([0x09, 0x9A, 0x03, 0x35, 0xF1, 0x00, 0x00, 0x00])
DISABLE_EEG_CMD: Final[bytearray] = bytearray([0x09, 0x9A, 0x03, 0x60, 0x00])
DISABLE_RAW_MODE_CMD: Final[bytearray] = bytearray([0x09, 0x9A, 0x03, 0x41, 0x00])
STOP_SESSION_CMD: Final[bytearray] = bytearray([0x09, 0x9A, 0x03, 0x35, 0xF0, 0x00, 0x00, 0x00])
BATTERY_CMD: Final[bytearray] = bytearray([0x09, 0x9A, 0x03, 0x14, 0xFF])

# Protocol Constants
EEG_EVENT_ID: Final[int] = 239
PACKET_SIZE: Final[int] = 63
SYNC_BYTE: Final[int] = 0xAA
EEG_SCALING_FACTOR: Final[float] = 0.023842
SENTINEL_VALUE: Final[int] = 8388607
NUM_EEG_CHANNELS: Final[int] = 12

# RFCOMM Configuration
RFCOMM_CHANNEL: Final[int] = 25

# Timing Constants (in seconds)
BLE_ACTIVATION_DELAY: Final[float] = 0.3
BLE_COMMAND_DELAY: Final[float] = 0.5
BLE_SESSION_DELAY: Final[float] = 1.0
BLE_DISCOVERY_TIMEOUT: Final[float] = 4.0
RFCOMM_CONNECTION_TIMEOUT: Final[float] = 10.0

# Device Discovery
MW75_DEVICE_NAME_PATTERN: Final[str] = "MW75"

# CSV Headers
EEG_CSV_HEADER: Final[str] = (
    "Timestamp,EventId,Counter,Ref,DRL,Ch1RawEEG,Ch2RawEEG,Ch3RawEEG,Ch4RawEEG,Ch5RawEEG,Ch6RawEEG,Ch7RawEEG,Ch8RawEEG,Ch9RawEEG,Ch10RawEEG,Ch11RawEEG,Ch12RawEEG,FeatureStatus"
)
EXTRA_CSV_HEADER: Final[str] = "Timestamp,EventId,Counter,DataLength,RawPayloadHex,FeatureStatus"

# Checksum Statistics Reporting
CHECKSUM_ERROR_REPORT_INTERVAL: Final[int] = 100  # Report every N invalid packets

# BLE Response Codes
BLE_SUCCESS_CODE: Final[int] = 0xF1
BLE_EEG_COMMAND: Final[int] = 0x60
BLE_RAW_MODE_COMMAND: Final[int] = 0x41
BLE_BATTERY_COMMAND: Final[int] = 0x14
BLE_UNKNOWN_E0_COMMAND: Final[int] = 0xE0
