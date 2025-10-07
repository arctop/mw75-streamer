Protocol Documentation
======================

This section provides technical details about the MW75 Neuro headphone communication protocol.

Connection Architecture
-----------------------

The MW75 EEG Streamer uses a two-phase connection approach:

1. **BLE Activation Phase** - Bluetooth Low Energy for device activation
2. **RFCOMM Streaming Phase** - Bluetooth Classic for high-speed data streaming

BLE Activation Sequence
-----------------------

The BLE phase activates EEG mode on the MW75 headphones:

.. code-block:: text

   1. Discover MW75 device via BLE scan
   2. Connect to BLE service
   3. Send ENABLE_EEG command
   4. Wait 300ms (critical timing)
   5. Send ENABLE_RAW_MODE command
   6. Wait 300ms (critical timing)
   7. Send START_SESSION command
   8. Wait for all responses
   9. Disconnect BLE (macOS Taho 26+ only)

**Critical Timing Requirements:**
- 300ms delays between activation commands are mandatory
- Commands must be sent in exact sequence
- **macOS Taho (26+)**: BLE must be disconnected before RFCOMM connection due to event loop interference
- **macOS 15 and earlier**: BLE connection can remain active during RFCOMM streaming

BLE Command Details
~~~~~~~~~~~~~~~~~~~

Commands are sent to the MW75's BLE characteristic:

.. code-block:: python

   ENABLE_EEG = bytes([0x02, 0x73, 0x02, 0x01])      # Enable EEG mode
   ENABLE_RAW_MODE = bytes([0x02, 0x73, 0x05, 0x01]) # Enable raw data mode
   START_SESSION = bytes([0x02, 0x73, 0x01, 0x01])   # Start streaming session

RFCOMM Data Streaming
---------------------

After BLE activation, the headphones begin streaming data over RFCOMM channel 25.

Connection Parameters
~~~~~~~~~~~~~~~~~~~~~

- **Protocol**: Bluetooth Classic RFCOMM
- **Channel**: 25
- **Target Data Rate**: ~500Hz (2ms intervals)
- **Packet Structure**: 63 bytes per logical packet
- **Transport Chunks**: multiples of 64 bytes

Packet Structure
----------------

Each logical data packet is exactly 63 bytes with the following structure:

.. code-block:: text

   Byte 0:    Sync Byte (0xAA)
   Byte 1:    Event ID (239 for EEG data)
   Byte 2:    Data Length (0x3C = 60 bytes)
   Byte 3:    Counter (increments each packet)
   Bytes 4-7:  REF channel (float32, microvolts)
   Bytes 8-11: DRL channel (float32, microvolts)
   Bytes 12-59: 12 EEG channels (float32 each, raw ADC values)
   Byte 60:   Feature Status flags
   Bytes 61-62: 16-bit checksum

EEG Channel Layout
~~~~~~~~~~~~~~~~~~

The 12 EEG channels (bytes 12-59) represent different electrode positions:

.. code-block:: text

   CH1-CH12: Raw ADC values from electrode array

   Conversion: raw_adc_value × 0.023842 = microvolts
   Disconnection: value 8388607 indicates electrode not connected

Data Validation
---------------

Packet Validation
~~~~~~~~~~~~~~~~~

Each packet undergoes validation:

1. **Sync Byte Check** - Must be 0xAA
2. **Packet Size Check** - Must be exactly 63 bytes
3. **Checksum Verification** - 16-bit sum of first 61 bytes
4. **Counter Extraction** - Counter value extracted for monitoring (rollover at 255)

Checksum Calculation
~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   def calculate_checksum(data: bytes) -> int:
       """Calculate 16-bit checksum of first 61 bytes."""
       return sum(data[:61]) & 0xFFFF

Data Processing Pipeline
------------------------

Raw Packet → Validation → Conversion → Output

1. **Receive 63-byte packet** from RFCOMM connection
2. **Validate packet structure** (sync, size, checksum)
3. **Parse channels** using struct.unpack for float32 values
4. **Convert EEG channels** from raw ADC to microvolts
5. **Filter by event type** (EEG vs other events)
6. **Route to outputs** (CSV, WebSocket, LSL, etc.)

Event Types
-----------

The MW75 headphones generate different event types:

EEG Data Events
~~~~~~~~~~~~~~~

- **Event ID**: 239
- **Target Frequency**: ~500Hz
- **Content**: 12-channel EEG + REF/DRL + metadata

Other Events
~~~~~~~~~~~~

- **Event IDs**: Various (non-239)
- **Frequency**: Irregular
- **Content**: Device status, battery, configuration changes

Error Conditions
----------------

Common error conditions and their handling (see :doc:`troubleshooting` for detailed solutions):

Packet Validation Failures
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- **Invalid sync byte** - Packet discarded, connection maintained
- **Checksum mismatch** - Packet discarded, logged as warning

Connection Issues
~~~~~~~~~~~~~~~~~

- **BLE activation timeout** - Retry with exponential backoff
- **RFCOMM connection lost** - Attempt reconnection
- **No data received** - Check device power and pairing

Performance Characteristics
---------------------------

Expected Performance
~~~~~~~~~~~~~~~~~~~~

- **Target Data Rate**: 500 packets/second (2ms intervals)
- **Target Packet Loss**: <0.1% under optimal conditions
- **Expected CPU Usage**: ~2-5% on modern macOS systems

.. note::
   Performance characteristics may vary based on environmental conditions and system configuration.

Bandwidth Requirements
~~~~~~~~~~~~~~~~~~~~~~

- **Target Logical Data**: ~31.5 KB/s (500Hz × 63 bytes logical packets)
- **WebSocket JSON**: ~85 KB/s (with JSON overhead)
- **CSV Output**: ~45 KB/s (text format)

Platform-Specific Details
--------------------------

macOS Implementation
~~~~~~~~~~~~~~~~~~~~

Uses PyObjC bindings for macOS Bluetooth frameworks:

- **IOBluetooth** for BLE operations
- **IOBluetoothDevice** for RFCOMM connections
- **Core Bluetooth** integration via PyObjC

Future Platform Support
~~~~~~~~~~~~~~~~~~~~~~~

Planned implementations for Linux and Windows:

- **Linux**: BlueZ via D-Bus or direct socket access
- **Windows**: Windows Bluetooth API via pywin32
