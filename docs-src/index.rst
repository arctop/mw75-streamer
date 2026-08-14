MW75 EEG Streamer Documentation
=================================

**MW75 EEG Streamer** is a Python package for streaming real-time EEG data from MW75 Neuro headphones. It provides a clean, modular architecture with support for multiple output formats including WebSocket, CSV, and Lab Streaming Layer (LSL).

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   installation
   quickstart
   server
   api
   protocol
   troubleshooting

Key Features
------------

⚡ **High-Speed Streaming**
   Real-time EEG data streaming at expected ~500Hz with minimal latency

🔄 **Multiple Output Formats**
   Stream to WebSocket, CSV files, Lab Streaming Layer (LSL), or stdout

🧠 **MW75 Neuro Integration**
   Seamless integration with MW75 Neuro headphones using BLE activation

📊 **Data Validation**
   Built-in packet validation, checksum verification, and automatic conversion to microvolts

🔧 **Modular Architecture**
   Clean, modular codebase with type safety and comprehensive logging

🔬 **Research Ready**
   Perfect for neuroscience research, BCI development, and real-time brain signal analysis

Quick Installation
------------------

.. code-block:: bash

   # Install from PyPI (recommended)
   uv pip install "mw75-streamer[all]"

   # For LSL support on macOS
   brew install labstreaminglayer/tap/lsl
   export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"

Quick Usage
-----------

.. code-block:: bash

   # Basic streaming
   python -m mw75_streamer --csv eeg.csv
   python -m mw75_streamer --ws ws://localhost:8080
   python -m mw75_streamer --lsl MW75_EEG

   # Combined outputs
   python -m mw75_streamer --csv eeg.csv --ws ws://localhost:8080

Platform Support
----------------

Supported on **macOS** (IOBluetooth via PyObjC) and **Windows 11** (standard library Bluetooth sockets) for real devices. Linux supports mock mode only; native Linux support is planned for a future release.

Requirements
------------

* macOS or Windows 11
* Python 3.10+
* MW75 Neuro headphones paired in the system Bluetooth settings
* Optional: WebSocket clients, LSL applications for real-time data consumption

Project Links
-------------

* `GitHub Repository <https://github.com/arctop/mw75-streamer>`_
* `Issue Tracker <https://github.com/arctop/mw75-streamer/issues>`_
* `Arctop Website <https://arctop.com>`_

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
