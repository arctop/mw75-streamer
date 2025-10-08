"""
Example WebSocket Client for MW75 Server

Demonstrates how to connect to the MW75 WebSocket server and control
device connections remotely.

Usage:
    # 1. Start the server in one terminal:
    uv run -m mw75_streamer.server --port 8080

    # 2. Run this client in another terminal:
    python examples/websocket_server_client.py
"""

import asyncio
import json
import sys
import uuid

try:
    import websockets
except ImportError:
    print("Error: websockets library not found")
    print("Install with: pip install websockets")
    sys.exit(1)


async def main():
    """Connect to MW75 server and control device"""
    uri = "ws://localhost:8080"
    
    print("=" * 80)
    print("MW75 WebSocket Server Client Example")
    print("=" * 80)
    print(f"Connecting to {uri}...")
    
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected to server")
            print()
            
            # Send connect command
            print("Sending connect command (auto_reconnect=True, log_level=INFO)")
            connect_msg = {
                "id": str(uuid.uuid4()),
                "type": "connect",
                "data": {
                    "auto_reconnect": True,
                    "log_level": "INFO"
                }
            }
            await websocket.send(json.dumps(connect_msg))
            
            # Track EEG packet count
            eeg_count = 0
            max_packets = 50  # Display first 50 EEG packets then disconnect
            
            # Receive and process messages
            print()
            print("Receiving messages from server...")
            print("-" * 80)
            
            async for message in websocket:
                try:
                    data = json.loads(message)
                    msg_type = data.get("type")
                    msg_data = data.get("data", {})
                    
                    if msg_type == "command_ack":
                        command = msg_data.get("command")
                        message_text = msg_data.get("message")
                        print(f"[ACK] Command acknowledged: {command}")
                        print(f"  {message_text}")
                        
                    elif msg_type == "status":
                        state = msg_data.get("state")
                        message_text = msg_data.get("message")
                        print(f"[STATUS] {state}")
                        print(f"  {message_text}")
                        
                    elif msg_type == "log":
                        level = msg_data.get("level")
                        log_msg = msg_data.get("message")
                        logger = msg_data.get("logger")
                        print(f"[LOG {level}] {logger}: {log_msg}")
                        
                    elif msg_type == "error":
                        code = msg_data.get("code")
                        error_msg = msg_data.get("message")
                        print(f"[ERROR {code}] {error_msg}")
                        
                    elif msg_type == "eeg_data":
                        eeg_count += 1
                        
                        # Display first few packets in detail
                        if eeg_count <= 5:
                            counter = msg_data.get("counter")
                            channels = msg_data.get("channels", {})
                            ch1 = channels.get("ch1", 0)
                            ch2 = channels.get("ch2", 0)
                            print(f"[EEG] Packet #{eeg_count}: counter={counter}, ch1={ch1:.1f}uV, ch2={ch2:.1f}uV")
                        
                        # Show progress for remaining packets
                        elif eeg_count % 10 == 0:
                            print(f"[EEG] Received {eeg_count} packets...")
                        
                        # Disconnect after receiving enough packets
                        if eeg_count >= max_packets:
                            print()
                            print(f"Received {eeg_count} EEG packets")
                            print()
                            print("Sending disconnect command")
                            disconnect_msg = {
                                "id": str(uuid.uuid4()),
                                "type": "disconnect",
                                "data": {}
                            }
                            await websocket.send(json.dumps(disconnect_msg))
                            
                            # Wait for disconnect to complete
                            await asyncio.sleep(2)
                            print("Disconnected")
                            break
                    
                    elif msg_type == "heartbeat":
                        # Server heartbeat - respond to keep connection alive
                        # (optional - the websocket library handles this automatically)
                        pass
                    
                    else:
                        print(f"Unknown message type: {msg_type}")
                
                except json.JSONDecodeError:
                    print(f"Invalid JSON received: {message}")
                except Exception as e:
                    print(f"Error processing message: {e}")
            
            print("-" * 80)
            print("Connection closed")
            
    except (ConnectionRefusedError, OSError) as e:
        print(f"Connection refused. Is the server running?")
        print(f"   Start server with: uv run -m mw75_streamer.server --port 8080")
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)

