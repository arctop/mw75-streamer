WebSocket Server (Remote Control)
===================================

The MW75 WebSocket Server provides a remote control interface for third-party applications to manage MW75 device connections and receive real-time EEG data over WebSocket.

Overview
--------

Unlike the WebSocket client mode (``--ws``), which connects *to* an existing WebSocket server, the server mode creates a WebSocket server that external applications can connect *to* for remote control.

**Use Cases:**

- Web applications controlling MW75 devices
- Mobile apps requiring EEG data
- Distributed systems with centralized device management
- Remote monitoring and control scenarios

Starting the Server
-------------------

Basic Usage
~~~~~~~~~~~

.. code-block:: bash

   # Start on default port 8080
   uv run -m mw75_streamer.server

   # Start on custom port
   uv run -m mw75_streamer.server --port 9000

   # Listen on all interfaces (for remote access)
   uv run -m mw75_streamer.server --host 0.0.0.0 --port 8080

   # Enable verbose logging
   uv run -m mw75_streamer.server --port 8080 --verbose

Connection Behavior
~~~~~~~~~~~~~~~~~~~

- Server starts **idle** (no device connection)
- Waits for client to connect and send commands
- Only **one client** allowed at a time
- Client controls when to connect/disconnect from MW75 device
- Device automatically disconnects when client disconnects

Message Protocol
----------------

All messages use JSON format with this structure:

.. code-block:: json

   {
     "id": "unique-message-id",
     "type": "message-type",
     "data": { }
   }

**Message Fields:**

- ``id`` - Unique identifier (UUID) for the message
- ``type`` - Message type (see below)
- ``data`` - Type-specific data payload

Client Commands
---------------

Commands sent from client to server:

Connect Command
~~~~~~~~~~~~~~~

Request connection to MW75 device:

.. code-block:: json

   {
     "id": "msg-1",
     "type": "connect",
     "data": {
       "auto_reconnect": true,
       "log_level": "ERROR"
     }
   }

**Parameters:**

- ``auto_reconnect`` (boolean, default: false) - Enable automatic reconnection on disconnect
- ``log_level`` (string, default: "ERROR") - Log level: "DEBUG", "INFO", "WARNING", or "ERROR"

**Response:** Server sends ``command_ack`` followed by status updates

Disconnect Command
~~~~~~~~~~~~~~~~~~

Request disconnection from MW75 device:

.. code-block:: json

   {
     "id": "msg-2",
     "type": "disconnect",
     "data": {}
   }

**Response:** Server sends ``command_ack`` and disconnects from device

Status Query
~~~~~~~~~~~~

Query current connection status:

.. code-block:: json

   {
     "id": "msg-3",
     "type": "status",
     "data": {}
   }

**Response:** Server sends current status information:

.. code-block:: json

   {
     "id": "msg-3",
     "type": "status",
     "data": {
       "device_state": "connected",
       "auto_reconnect": true,
       "log_level": "ERROR"
     }
   }

Ping/Pong
~~~~~~~~~

Keepalive mechanism (optional, server sends automatic heartbeats):

.. code-block:: json

   {
     "id": "msg-4",
     "type": "ping",
     "data": {}
   }

**Response:** Server sends ``pong`` message

Server Messages
---------------

Messages sent from server to client:

Command Acknowledgement
~~~~~~~~~~~~~~~~~~~~~~~

Confirms command receipt:

.. code-block:: json

   {
     "id": "msg-1",
     "type": "command_ack",
     "data": {
       "command": "connect",
       "message": "Connect command received, initiating device connection",
       "auto_reconnect": true,
       "log_level": "INFO"
     }
   }

Status Updates
~~~~~~~~~~~~~~

Connection state changes:

.. code-block:: json

   {
     "id": "uuid",
     "type": "status",
     "data": {
       "state": "connected",
       "message": "Successfully connected to MW75 device",
       "timestamp": 1234567890.123
     }
   }

**Connection States:**

- ``idle`` - No device connection
- ``connecting`` - Attempting device connection
- ``connected`` - Device connected and streaming
- ``disconnecting`` - Disconnecting from device
- ``disconnected`` - Device disconnected
- ``reconnecting`` - Auto-reconnect in progress
- ``error`` - Error state

EEG Data
~~~~~~~~

Real-time EEG packets (sent at ~500Hz when connected):

.. code-block:: json

   {
     "id": "uuid",
     "type": "eeg_data",
     "data": {
       "timestamp": 1234567890.123,
       "event_id": 239,
       "counter": 42,
       "ref": 123.45,
       "drl": 67.89,
       "channels": {
         "ch1": 10.5,
         "ch2": 12.3,
         "ch3": -5.2,
         "ch4": 8.7,
         "ch5": -2.1,
         "ch6": 15.3,
         "ch7": 4.8,
         "ch8": -7.6,
         "ch9": 11.2,
         "ch10": 3.4,
         "ch11": -9.8,
         "ch12": 6.1
       },
       "feature_status": 0
     }
   }

**Fields:**

- ``timestamp`` - Unix timestamp (seconds with microsecond precision)
- ``event_id`` - Always 239 for EEG data
- ``counter`` - Sequence counter (0-255, wraps around)
- ``ref`` - Reference electrode value (µV)
- ``drl`` - Driven Right Leg electrode value (µV)
- ``channels`` - 12 EEG channels (µV), named ch1 through ch12
- ``feature_status`` - Device feature status flags

Log Messages
~~~~~~~~~~~~

Filtered log messages (based on client-requested log level):

.. code-block:: json

   {
     "id": "uuid",
     "type": "log",
     "data": {
       "level": "ERROR",
       "message": "Connection error: timeout",
       "logger": "mw75_streamer.device",
       "timestamp": 1234567890.123
     }
   }

**Log Levels:**

- ``DEBUG`` - Detailed diagnostic information
- ``INFO`` - General informational messages
- ``WARNING`` - Warning messages (potential issues)
- ``ERROR`` - Error messages (failures)

Error Messages
~~~~~~~~~~~~~~

Error notifications:

.. code-block:: json

   {
     "id": "uuid",
     "type": "error",
     "data": {
       "code": "CONNECTION_FAILED",
       "message": "Failed to connect to device",
       "timestamp": 1234567890.123
     }
   }

**Common Error Codes:**

- ``CLIENT_ALREADY_CONNECTED`` - Another client is already connected
- ``INVALID_JSON`` - Malformed JSON received
- ``INVALID_MESSAGE`` - Message structure invalid
- ``MISSING_TYPE`` - Message missing 'type' field
- ``UNKNOWN_COMMAND`` - Unknown command type
- ``INVALID_LOG_LEVEL`` - Invalid log level specified
- ``ALREADY_CONNECTED`` - Device already connected
- ``BLE_ACTIVATION_FAILED`` - MW75 device not found or BLE activation failed
- ``RFCOMM_CONNECTION_FAILED`` - RFCOMM data connection failed
- ``CONNECTION_FAILED`` - Device connection failed
- ``DISCONNECT_ERROR`` - Error during disconnection
- ``RECONNECT_FAILED`` - Auto-reconnect attempt failed
- ``RECONNECT_EXHAUSTED`` - Max reconnection attempts reached
- ``DEVICE_ERROR`` - Device-level error
- ``MESSAGE_PROCESSING_ERROR`` - Error processing message

Heartbeat Messages
~~~~~~~~~~~~~~~~~~

Automatic keepalive (sent every 30 seconds):

.. code-block:: json

   {
     "id": "uuid",
     "type": "heartbeat",
     "data": {
       "timestamp": 1234567890.123
     }
   }

These heartbeats help monitor connection health. The WebSocket library automatically handles connection liveness and will close the connection if it becomes unresponsive.

Features
--------

Auto-Reconnect
~~~~~~~~~~~~~~

When enabled via the connect command:

- Monitors device connection health
- Automatically attempts reconnection on disconnect
- Uses exponential backoff (1, 2, 4, 8, 16, 30 seconds max)
- Maximum 10 reconnection attempts
- Sends status updates during reconnection
- Stops on client disconnect command

Log Level Filtering
~~~~~~~~~~~~~~~~~~~

Client can request specific log levels in the connect command:

- ``DEBUG`` - All logs (very verbose)
- ``INFO`` - Informational and above
- ``WARNING`` - Warnings and errors only
- ``ERROR`` - Errors only (default)

Logs are captured from the entire ``mw75_streamer`` package and filtered before sending to client.

Single Client Policy
~~~~~~~~~~~~~~~~~~~~~

Only one client can connect at a time:

- Subsequent connection attempts are rejected
- Rejection includes ``CLIENT_ALREADY_CONNECTED`` error
- Client must disconnect before another can connect
- Server does not queue or manage multiple clients

Connection Lifecycle
~~~~~~~~~~~~~~~~~~~~

1. Client connects to WebSocket server
2. Server sends welcome status message
3. Client sends ``connect`` command
4. Server acknowledges and begins device connection
5. Device connects, EEG data flows
6. Client sends ``disconnect`` or closes WebSocket
7. Server disconnects device and cleans up

Python Client Example
---------------------

Complete Example
~~~~~~~~~~~~~~~~

.. code-block:: python

   import asyncio
   import json
   import uuid
   import websockets

   async def mw75_client():
       uri = "ws://localhost:8080"
       
       async with websockets.connect(uri) as ws:
           # Send connect command
           await ws.send(json.dumps({
               "id": str(uuid.uuid4()),
               "type": "connect",
               "data": {
                   "auto_reconnect": True,
                   "log_level": "INFO"
               }
           }))
           
           # Receive and process messages
           async for message in ws:
               data = json.loads(message)
               msg_type = data.get("type")
               
               if msg_type == "eeg_data":
                   channels = data["data"]["channels"]
                   print(f"Ch1: {channels['ch1']:.1f} µV")
                   
               elif msg_type == "status":
                   state = data["data"]["state"]
                   print(f"Status: {state}")
                   
               elif msg_type == "error":
                   code = data["data"]["code"]
                   msg = data["data"]["message"]
                   print(f"Error [{code}]: {msg}")
                   
               elif msg_type == "log":
                   level = data["data"]["level"]
                   msg = data["data"]["message"]
                   print(f"[{level}] {msg}")

   asyncio.run(mw75_client())

See ``examples/websocket_server_client.py`` for a complete working example.

JavaScript Client Example
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: javascript

   const ws = new WebSocket('ws://localhost:8080');

   ws.onopen = () => {
     // Connect to device
     ws.send(JSON.stringify({
       id: crypto.randomUUID(),
       type: 'connect',
       data: {
         auto_reconnect: true,
         log_level: 'ERROR'
       }
     }));
   };

   ws.onmessage = (event) => {
     const data = JSON.parse(event.data);
     
     switch (data.type) {
       case 'eeg_data':
         const ch1 = data.data.channels.ch1;
         console.log(`Ch1: ${ch1.toFixed(1)} µV`);
         break;
         
       case 'status':
         console.log(`Status: ${data.data.state}`);
         break;
         
       case 'error':
         console.error(`Error: ${data.data.message}`);
         break;
     }
   };

   ws.onerror = (error) => {
     console.error('WebSocket error:', error);
   };

Testing
-------

Integration Test
~~~~~~~~~~~~~~~~

Test with actual MW75 device:

.. code-block:: bash

   # Terminal 1: Start server
   uv run -m mw75_streamer.server --port 8080 --verbose

   # Terminal 2: Run example client
   python examples/websocket_server_client.py

The example client will connect, start device streaming, receive EEG packets, and disconnect.

API Reference
-------------

Server Class
~~~~~~~~~~~~

.. automodule:: mw75_streamer.server.ws_server
   :members:
   :undoc-members:
   :show-inheritance:

Comparison: Client vs Server Mode
----------------------------------

The package offers two WebSocket modes:

**Client Mode** (``--ws``)
  - Streamer connects *to* existing WebSocket server
  - Sends EEG data to server
  - Simple one-way data streaming
  - Use for: sending data to existing infrastructure

**Server Mode** (``-m mw75_streamer.server``)
  - Streamer *is* the WebSocket server
  - Clients connect to control device and receive data
  - Two-way command/response protocol
  - Use for: remote control applications

Both modes can coexist - you can run the server mode and also use ``--ws`` to forward data elsewhere simultaneously.

Troubleshooting
---------------

Connection Refused
~~~~~~~~~~~~~~~~~~

**Problem:** Client cannot connect to server

**Solutions:**

1. Ensure server is running:

   .. code-block:: bash

      uv run -m mw75_streamer.server --port 8080

2. Check port availability:

   .. code-block:: bash

      lsof -i :8080

3. Verify firewall settings allow connections

4. Try localhost first: ``ws://localhost:8080``

Client Rejected
~~~~~~~~~~~~~~~

**Problem:** "CLIENT_ALREADY_CONNECTED" error

**Solutions:**

1. Only one client can connect at a time
2. Disconnect existing client first
3. Wait a few seconds after client disconnect
4. Restart server if needed

Device Won't Connect
~~~~~~~~~~~~~~~~~~~~

**Problem:** Status stays in "connecting" state

**Solutions:**

1. Ensure MW75 headphones are paired and powered on
2. Check Bluetooth connection in System Preferences
3. Run server with ``--verbose`` to see detailed logs
4. See :doc:`troubleshooting` for device-specific issues

No EEG Data
~~~~~~~~~~~

**Problem:** Connected but no ``eeg_data`` messages

**Solutions:**

1. Check device state with status command
2. Ensure device successfully connected (status = "connected")
3. Monitor for error messages
4. Check log messages for connection issues

Security Considerations
-----------------------

The WebSocket server provides no built-in authentication or encryption:

**Recommendations:**

- Bind to ``localhost`` only for local applications
- Use a reverse proxy (nginx, Apache) for remote access
- Implement TLS/SSL at proxy level for encryption
- Add authentication at application level if needed
- Run on isolated network for sensitive applications
- Never expose directly to public internet

For production deployments, consider wrapping the server with proper security infrastructure.

Next Steps
----------

- See :doc:`quickstart` for basic MW75 usage
- Read :doc:`protocol` for technical details
- Check :doc:`troubleshooting` for common issues
- Review ``examples/websocket_server_client.py`` for complete client implementation

