"""
MW75 WebSocket Server Module

Provides a WebSocket server for remote control of MW75 device connections.
Third-party applications can connect to control device streaming and receive
real-time EEG data, status updates, and logs.
"""

from .ws_server import MW75WebSocketServer

__all__ = ["MW75WebSocketServer"]
