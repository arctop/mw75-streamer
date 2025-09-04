#!/usr/bin/env python3
"""
MW75 Streamer - Simple Callback Example

A minimal example showing how to use the MW75 streamer with custom callbacks
for basic real-time EEG data processing.

This is the simplest way to get started with custom EEG processing.
"""

import asyncio
from mw75_streamer import MW75Streamer, EEGPacket


def process_eeg_data(packet: EEGPacket):
    """
    Simple EEG data processor - called for every EEG packet
    
    Args:
        packet: EEGPacket containing timestamp, 12 channels, ref/drl data
    """
    # Basic info about the packet
    print(f"EEG packet #{packet.counter} at {packet.timestamp:.3f}s")
    
    # Access the 12 EEG channels (in microvolts)
    ch1_value = packet.channels[0]  # First EEG channel
    ch2_value = packet.channels[1]  # Second EEG channel
    
    print(f"Ch1: {ch1_value:7.1f} µV | Ch2: {ch2_value:7.1f} µV")
    
    # You can access all channels like this:
    # for i, value in enumerate(packet.channels):
    #     print(f"   Ch{i+1}: {value:7.1f} µV")
    
    # Reference electrodes
    print(f"REF: {packet.ref:7.1f} µV | DRL: {packet.drl:7.1f} µV")
    print()


async def main():
    """Simple main function"""
    print("MW75 Simple Callback Example")
    print("Make sure MW75 headphones are paired and on.")
    print("Press Ctrl+C to stop.\n")
    
    # Create streamer with callback
    streamer = MW75Streamer(
        eeg_callback=process_eeg_data,  # Our custom function
        verbose=False  # Set to True for more detailed logs
    )
    
    try:
        # Start streaming
        await streamer.start_streaming()
    except KeyboardInterrupt:
        print("\nStopped by user")


if __name__ == "__main__":
    asyncio.run(main())
