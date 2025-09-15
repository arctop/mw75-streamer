Installation Guide
==================

System Requirements
-------------------

* **Platform**: macOS (required)
* **Python**: 3.9 or newer
* **Hardware**: MW75 Neuro headphones paired in macOS Bluetooth settings

The MW75 EEG Streamer currently supports macOS only, using macOS-specific Bluetooth frameworks through PyObjC.

Basic Installation
------------------

**First, install uv (recommended Python package manager):**

.. code-block:: bash

   # Install uv - see https://docs.astral.sh/uv/getting-started/installation/
   curl -LsSf https://astral.sh/uv/install.sh | sh

   # Or on macOS with Homebrew:
   brew install uv

Option 1: From PyPI (Recommended)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Basic installation
   uv pip install mw75-streamer

   # With all optional dependencies (WebSocket, LSL support)
   uv pip install "mw75-streamer[all]"

Option 2: From Source
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/arctop/mw75-streamer.git
   cd mw75-streamer

   # Using uv (recommended)
   uv venv && uv pip install -e ".[all]"

   # OR alternatively using pip
   python -m venv .venv
   source .venv/bin/activate
   pip install -e ".[all]"

Optional Dependencies
---------------------

The package includes several optional dependency groups:

WebSocket Support
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   uv pip install "mw75-streamer[websocket]"

This adds:
- ``websocket-client>=1.6.0`` for WebSocket streaming

Lab Streaming Layer (LSL) Support
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   uv pip install "mw75-streamer[lsl]"

This adds:
- ``pylsl>=1.16.0`` for LSL streaming

For macOS LSL support, you also need:

.. code-block:: bash

   brew install labstreaminglayer/tap/lsl
   export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"

Testing Utilities
~~~~~~~~~~~~~~~~~

.. code-block:: bash

   uv pip install "mw75-streamer[testing]"

This adds:
- ``websockets>=11.0.0`` for the test WebSocket server

Development Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   uv pip install "mw75-streamer[dev]"

This includes all optional dependencies plus development tools:
- ``pytest>=7.0.0``
- ``black>=23.0.0``
- ``flake8>=6.0.0``
- ``mypy>=1.0.0``

All Dependencies
~~~~~~~~~~~~~~~~

.. code-block:: bash

   uv pip install "mw75-streamer[all]"

This installs WebSocket, LSL, and testing dependencies.

Documentation Dependencies
~~~~~~~~~~~~~~~~~~~~~~~~~~

For building documentation:

.. code-block:: bash

   uv pip install "mw75-streamer[docs]"

This includes:
- ``sphinx>=7.0.0``
- ``sphinx-rtd-theme>=2.0.0``
- ``sphinx-autodoc-typehints>=1.25.0``
- ``myst-parser>=2.0.0``

Hardware Setup
--------------

MW75 Neuro Headphones
~~~~~~~~~~~~~~~~~~~~~~

1. **Pair your MW75 Neuro headphones** with your Mac using the standard macOS Bluetooth settings
2. **Ensure the headphones are connected** before running the streamer
3. **Position the headphones properly** on your head for good electrode contact

The MW75 Neuro headphones must be properly paired and connected via Bluetooth before the streamer can activate EEG mode.

Verification
------------

Test your installation:

.. code-block:: bash

   # Check that the package is installed
   uv run python -c "import mw75_streamer; print('Installation successful!')"

   # Test the CLI
   uv run -m mw75_streamer --help

   # Start a basic test
   uv run -m mw75_streamer.testing

Troubleshooting
---------------

For comprehensive troubleshooting information, see the :doc:`troubleshooting` guide.

Common Installation Issues
~~~~~~~~~~~~~~~~~~~~~~~~~~

**PyObjC Installation Fails**
   On some macOS versions, PyObjC might fail to install. Try:

   .. code-block:: bash

      # Update pip and try again
      pip install --upgrade pip setuptools wheel
      uv pip install "mw75-streamer[all]"

**LSL Library Not Found**
   If you get LSL import errors:

   .. code-block:: bash

      # Make sure LSL is installed
      brew install labstreaminglayer/tap/lsl

      # Set the library path
      export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"

      # Add to your shell profile for persistence
      echo 'export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"' >> ~/.zshrc

**Permission Issues**
   On some systems, Bluetooth access might require additional permissions. Check:

   - System Preferences → Security & Privacy → Privacy → Bluetooth
   - Ensure Terminal/your Python environment has Bluetooth access

Next Steps
----------

After installation, see the :doc:`quickstart` guide for basic usage examples.

If you encounter any issues, check the :doc:`troubleshooting` guide for solutions to common problems.
