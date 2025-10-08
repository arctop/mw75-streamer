Quick Start Guide
=================

This guide will get you streaming EEG data from your MW75 Neuro headphones in minutes.

Prerequisites
-------------

1. **MW75 Neuro headphones** paired with your Mac
2. **Python 3.9+** installed
3. **uv package manager** installed (see `uv installation guide <https://docs.astral.sh/uv/getting-started/installation/>`_)
4. **Package installed** with dependencies:

.. code-block:: bash

   # Install uv if needed:
   curl -LsSf https://astral.sh/uv/install.sh | sh
   # or: brew install uv

   # Install MW75 streamer:
   uv pip install "mw75-streamer[all]"

Basic Usage
-----------

.. note::
   All commands below use ``uv run`` which automatically manages the virtual environment and dependencies. This ensures you're using the correct Python environment without manually activating it.

Stream to CSV File
~~~~~~~~~~~~~~~~~~

The simplest way to start collecting EEG data:

.. code-block:: bash

   uv run -m mw75_streamer --csv my_eeg_data.csv

This creates two files:
- ``my_eeg_data.csv`` - EEG channel data (expected ~500Hz)
- ``my_eeg_data_events.csv`` - Other device events

Real-time WebSocket Streaming
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For real-time applications:

.. code-block:: bash

   # Start the test server (in one terminal)
   uv run -m mw75_streamer.testing --advanced

   # Start streaming (in another terminal)
   uv run -m mw75_streamer --ws ws://localhost:8080

Press 'b' + Enter in the test server terminal to open a browser visualization.

Lab Streaming Layer (LSL)
~~~~~~~~~~~~~~~~~~~~~~~~~

For integration with LSL applications:

.. code-block:: bash

   uv run -m mw75_streamer --lsl MW75_EEG

This creates an LSL stream named "MW75_EEG" that other applications can consume.

Combined Output
~~~~~~~~~~~~~~~

You can stream to multiple destinations simultaneously:

.. code-block:: bash

   uv run -m mw75_streamer --csv data.csv --ws ws://localhost:8080 --lsl MW75_EEG

WebSocket Server (Remote Control)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

For applications that need to remotely control the device:

.. code-block:: bash

   # Start WebSocket server
   uv run -m mw75_streamer.server --port 8080

   # Client connects and sends commands to control device
   # See :doc:`server` for complete documentation

This mode allows external applications to connect and control when to start/stop device connections.

Command Line Options
--------------------

Core Options
~~~~~~~~~~~~

.. code-block:: bash

   uv run -m mw75_streamer [OPTIONS]

**Output Options:**

- ``--csv PATH`` - Save EEG data to CSV file
- ``--ws URL`` - Stream to WebSocket URL
- ``--lsl NAME`` - Create LSL stream with given name
- Default behavior (no CSV file) prints data to console

**Control Options:**

- ``--verbose`` - Enable detailed logging
- ``--browser`` - Start built-in web server and open browser
- ``--help`` - Show help message

Examples
~~~~~~~~

.. code-block:: bash

   # Verbose logging with CSV output
   uv run -m mw75_streamer --verbose --csv detailed_session.csv

   # Multiple WebSocket destinations
   uv run -m mw75_streamer --ws ws://localhost:8080 --ws ws://remote-server:9090

   # Quick browser visualization
   uv run -m mw75_streamer --browser

Understanding the Data
----------------------

EEG Data Format
~~~~~~~~~~~~~~~

The streamer outputs EEG data at a target rate of ~500Hz with the following channels:

**EEG Channels (12 total):**
- Raw ADC values converted to microvolts (µV)
- Sentinel value ``8388607`` indicates electrode disconnection

**Reference Channels:**
- ``REF`` - Reference electrode (µV)
- ``DRL`` - Driven Right Leg electrode (µV)

**CSV Format:**
Each row contains: ``timestamp,counter,REF,DRL,CH1,CH2,...,CH12,feature_status``

**WebSocket Format:**
JSON messages with ``type``, ``timestamp``, ``counter``, and ``data`` fields.

Connection Process
~~~~~~~~~~~~~~~~~~

The streamer follows this sequence:

1. **BLE Discovery** - Scan for MW75 device
2. **BLE Activation** - Send activation commands with 300ms delays
3. **RFCOMM Connection** - Connect to data streaming channel
4. **Data Processing** - Validate packets and convert to microvolts

Testing Setup
-------------

Browser Visualization
~~~~~~~~~~~~~~~~~~~~~

The easiest way to test your setup:

.. code-block:: bash

   # Start advanced test server
   uv run -m mw75_streamer.testing --advanced

   # In another terminal, start streaming
   uv run -m mw75_streamer --ws ws://localhost:8080

   # In the server terminal, press 'b' + Enter to open browser

This opens a real-time EEG visualization in your web browser.

Validation Checklist
~~~~~~~~~~~~~~~~~~~~~

**Data Rate** - Monitor packet arrival rate (target ~500Hz)
**Sequential Counters** - Counter should increment by 1 each packet
**Realistic Values** - EEG channels should show µV values (not raw ADC)
**Minimal Drops** - Should have very few missing packets

Common Issues
-------------

For detailed troubleshooting information, see the :doc:`troubleshooting` guide.

Device Not Found
~~~~~~~~~~~~~~~~~

If the MW75 device isn't found:

1. Check Bluetooth pairing in System Preferences
2. Ensure headphones are powered on and connected
3. Try re-pairing the device

Connection Failed
~~~~~~~~~~~~~~~~~

If BLE activation fails:

1. Restart the headphones
2. Clear Bluetooth cache (re-pair device)
3. Check for Bluetooth interference

Poor Data Quality
~~~~~~~~~~~~~~~~~

If you see many disconnected electrodes:

1. Clean the electrode contacts
2. Adjust headphone positioning
3. Check for hair or skin contact issues

Next Steps
----------

- Read the :doc:`api` documentation for programmatic usage
- See :doc:`protocol` for technical details
- Check :doc:`troubleshooting` for common issues
