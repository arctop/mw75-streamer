Troubleshooting Guide
=====================

This guide helps resolve common issues when using the MW75 EEG Streamer.

For basic setup information, see the :doc:`installation` and :doc:`quickstart` guides. For technical details, refer to the :doc:`protocol` documentation.

Installation Issues
-------------------

PyObjC Installation Fails
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**
- Error during ``pip install`` or ``uv pip install``
- "Failed building wheel for pyobjc-\\*" messages

**Solutions:**

1. **Update build tools:**

   .. code-block:: bash

      pip install --upgrade pip setuptools wheel
      uv pip install "mw75-streamer[all]"

2. **Use uv instead of pip:**

   .. code-block:: bash

      brew install uv
      uv pip install "mw75-streamer[all]"

3. **Install Xcode command line tools:**

   .. code-block:: bash

      xcode-select --install

LSL Library Not Found
~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**
- ``ImportError: No module named 'pylsl'``
- ``OSError: Could not find liblsl``

**Solutions:**

1. **Install LSL system library:**

   .. code-block:: bash

      brew install labstreaminglayer/tap/lsl
      export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"

2. **Add to shell profile permanently:**

   .. code-block:: bash

      echo 'export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"' >> ~/.zshrc
      source ~/.zshrc

Connection Issues
-----------------

MW75 Device Not Found
~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**
- "No MW75 device found"
- BLE scan timeout

**Diagnostic Steps:**

1. **Check Bluetooth pairing:**

   - Open System Preferences → Bluetooth
   - Verify MW75 Neuro appears in device list
   - Status should show "Connected"

2. **Verify headphone power:**

   - Ensure headphones are powered on
   - Check battery level is sufficient (>20%)
   - Try power cycling the headphones

3. **Test Bluetooth connectivity:**

   .. code-block:: bash

      # Check if device is visible to system
      system_profiler SPBluetoothDataType | grep -i "mw75\|neuro"

**Solutions:**

1. **Re-pair the device:**

   - Remove MW75 from Bluetooth devices
   - Power cycle headphones
   - Re-pair using standard macOS Bluetooth settings

2. **Check permissions:**

   - System Preferences → Security & Privacy → Privacy → Bluetooth
   - Ensure Terminal/Python has Bluetooth access

3. **Reset Bluetooth module:**

   .. code-block:: bash

      # Reset Bluetooth (requires restart)
      sudo pkill bluetoothd

BLE Activation Fails
~~~~~~~~~~~~~~~~~~~~

**Symptoms:**
- "BLE activation timeout"
- "Failed to enable EEG mode"

**Solutions:**

1. **Check connection stability:**

   - Ensure headphones are within 1 meter
   - Reduce 2.4GHz interference (WiFi, other Bluetooth devices)

2. **Retry activation:**

   - BLE activation includes automatic retry logic
   - Try running with ``--verbose`` to see detailed timing

3. **Manual device reset:**

   - Power off headphones for 10 seconds
   - Power on and wait 30 seconds before connecting

RFCOMM Connection Lost
~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**
- "RFCOMM connection failed"
- Data stops flowing mid-session

**Solutions:**

1. **Check interference:**

   - Move closer to headphones
   - Disable other Bluetooth devices temporarily
   - Switch to 5GHz WiFi if available

2. **Monitor connection quality:**

   .. code-block:: bash

      # Run with verbose logging
      python -m mw75_streamer --verbose --csv test.csv

3. **Automatic reconnection:**

   - The streamer includes auto-reconnect logic
   - Data gaps will be logged but streaming continues

Data Quality Issues
-------------------

High Packet Loss
~~~~~~~~~~~~~~~~

**Symptoms:**
- Many missing counter values
- "Packet loss detected" warnings
- Irregular packet timing

**Diagnostic:**

.. code-block:: bash

   # Monitor packet loss with verbose logging (prints to console by default)
   uv run -m mw75_streamer --verbose

**Solutions:**

1. **Reduce interference:**

   - Move away from WiFi routers
   - Disable other 2.4GHz devices
   - Use USB-wired peripherals instead of wireless

2. **Optimize system resources:**

   - Close unnecessary applications
   - Ensure adequate CPU/memory available
   - Run with higher process priority if needed (just run with sudo)

Many Disconnected Electrodes
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**
- EEG channels showing value ``8388607``
- Poor signal quality in visualization

**Solutions:**

1. **Improve electrode contact:**

   - Adjust headphone positioning
   - Ensure good skin contact (move hair if needed)

2. **Check headphone condition:**

   - Inspect electrodes for damage or corrosion
   - Ensure electrodes are not loose

3. **Environmental factors:**

   - Avoid excessive movement during recording

Output Issues
-------------

CSV Files Not Created
~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**
- No CSV files appear
- Permission errors during file creation

**Solutions:**

1. **Check file permissions:**

   .. code-block:: bash

      # Test write access in current directory
      touch test_file.csv && rm test_file.csv

2. **Use absolute paths:**

   .. code-block:: bash

      python -m mw75_streamer --csv /full/path/to/output.csv

3. **Check disk space:**

   .. code-block:: bash

      df -h .

WebSocket Connection Failed
~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**
- "WebSocket connection failed"
- Cannot connect to specified URL

**Solutions:**

1. **Test WebSocket server:**

   .. code-block:: bash

      # Start test server first
      python -m mw75_streamer.testing --advanced

2. **Check firewall settings:**

   - Ensure port is not blocked
   - Try localhost connection first: ``ws://localhost:8080``

3. **Verify WebSocket URL format:**

   - Use ``ws://`` for unencrypted connections
   - Use ``wss://`` for encrypted connections

LSL Stream Not Visible
~~~~~~~~~~~~~~~~~~~~~~

**Symptoms:**
- LSL applications don't see the MW75 stream
- "No LSL streams found"

**Solutions:**

1. **Check LSL installation:**

   .. code-block:: bash

      python -c "import pylsl; print(pylsl.version_info())"

2. **Test with LSL tools:**

   .. code-block:: bash

      # Install LSL apps for testing
      brew install labstreaminglayer/tap/lsl-apps

      # View available streams
      lsl_resolve_byprop type EEG

3. **Verify stream name:**

   - Use exact stream name specified with ``--lsl``
   - Stream names are case-sensitive

Performance Issues
------------------

High CPU Usage
~~~~~~~~~~~~~~

**Symptoms:**
- CPU usage >50% for streaming
- System becomes unresponsive

**Solutions:**

1. **Reduce output formats:**

   - Use single output instead of multiple
   - CSV is most efficient, WebSocket least efficient

2. **Optimize Python environment:**

   .. code-block:: bash

      # Use optimized Python build
      brew install python@3.11

3. **Check for memory leaks:**

   .. code-block:: bash

      # Monitor memory usage
      python -m mw75_streamer --verbose --csv test.csv &
      top -pid $!

High Memory Usage
~~~~~~~~~~~~~~~~~

**Symptoms:**
- Memory usage grows over time
- System runs out of memory during long sessions

**Solutions:**

1. **Restart for long sessions:**

   - Stop and restart streamer every few hours
   - Monitor memory usage with Activity Monitor

2. **Use appropriate buffer sizes:**

   - Default settings should work for most cases
   - Avoid unnecessary data retention

Getting Help
------------

Enable Verbose Logging
~~~~~~~~~~~~~~~~~~~~~~

For any issue, start with verbose logging:

.. code-block:: bash

   python -m mw75_streamer --verbose [your normal options]

This provides detailed information about:
- BLE activation steps
- RFCOMM connection status
- Packet validation results
- Timing information

Collect System Information
~~~~~~~~~~~~~~~~~~~~~~~~~~

When reporting issues, include:

.. code-block:: bash

   # Python and package versions
   python --version
   pip show mw75-streamer

   # System information
   sw_vers
   system_profiler SPBluetoothDataType

   # Bluetooth device status
   system_profiler SPBluetoothDataType | grep -A 10 -i "mw75\|neuro"

Report Issues
~~~~~~~~~~~~~

If problems persist:

1. **Check existing issues:** https://github.com/arctop/mw75-streamer/issues
2. **Create new issue:** Include verbose logs and system information
3. **Community support:** Discuss on project GitHub page

The development team actively monitors issues and provides support for users.
