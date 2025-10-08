API Reference
=============

This section provides detailed documentation for all classes and functions in the MW75 EEG Streamer package.

Main Module
-----------

.. automodule:: mw75_streamer.main
   :members:
   :undoc-members:
   :show-inheritance:

Device Management
-----------------

MW75 Device Controller
~~~~~~~~~~~~~~~~~~~~~~

.. automodule:: mw75_streamer.device.mw75_device
   :members:
   :undoc-members:
   :show-inheritance:

BLE Manager
~~~~~~~~~~~

.. automodule:: mw75_streamer.device.ble_manager
   :members:
   :undoc-members:
   :show-inheritance:

RFCOMM Manager
~~~~~~~~~~~~~~

.. automodule:: mw75_streamer.device.rfcomm_manager
   :members:
   :undoc-members:
   :show-inheritance:

Data Processing
---------------

Packet Processor
~~~~~~~~~~~~~~~~

.. automodule:: mw75_streamer.data.packet_processor
   :members:
   :undoc-members:
   :show-inheritance:

Streamers
~~~~~~~~~

.. automodule:: mw75_streamer.data.streamers
   :members:
   :undoc-members:
   :show-inheritance:

Configuration
-------------

.. automodule:: mw75_streamer.config
   :members:
   :undoc-members:
   :show-inheritance:

WebSocket Server (Remote Control)
----------------------------------

.. automodule:: mw75_streamer.server.ws_server
   :members:
   :undoc-members:
   :show-inheritance:

Testing Utilities
-----------------

WebSocket Test Server
~~~~~~~~~~~~~~~~~~~~~

.. automodule:: mw75_streamer.testing.websocket_server
   :members:
   :undoc-members:
   :show-inheritance:

Test Guide
~~~~~~~~~~

.. automodule:: mw75_streamer.testing.test_guide
   :members:
   :undoc-members:
   :show-inheritance:

Panel Server
~~~~~~~~~~~~

.. automodule:: mw75_streamer.panel.panel_server
   :members:
   :undoc-members:
   :show-inheritance:

Utilities
---------

Logging
~~~~~~~

.. automodule:: mw75_streamer.utils.logging
   :members:
   :undoc-members:
   :show-inheritance:

Data Structures
---------------

The core data structures are documented within their respective modules above. The main data structure is the ``EEGPacket`` class in the packet processor module.
