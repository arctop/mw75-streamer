#!/usr/bin/env python3
"""
MW75 Streamer - Callback Integration Example

This example demonstrates how to use the enhanced callback interface
to integrate MW75 EEG streaming into your own applications.

The callback interface provides three types of callbacks:
1. eeg_callback - Receives processed EEGPacket objects with µV data
2. raw_data_callback - Receives raw bytes from the device  
3. other_event_callback - Receives non-EEG event packets
"""

import asyncio
import sys
import numpy as np
from typing import List, Optional
from collections import deque
import time
import statistics

# Import MW75 streamer components
from mw75_streamer import MW75Streamer, EEGPacket


class EEGDataProcessor:
    """Example EEG data processor with real-time analysis"""
    
    def __init__(self, buffer_size: int = 2500):  # 5 seconds at 500Hz
        self.buffer_size = buffer_size
        self.eeg_buffer: deque = deque(maxlen=buffer_size)
        self.timestamps: deque = deque(maxlen=buffer_size)
        
        # Statistics tracking
        self.packet_count = 0
        self.start_time = None
        self.last_stats_time = 0
        
        # Channel labels for MW75 (12-channel EEG headset)
        self.channel_names = [f"Ch{i+1}" for i in range(12)]
        
    def process_eeg_packet(self, packet: EEGPacket) -> None:
        """
        Process incoming EEG packet with real-time analysis
        
        Args:
            packet: EEGPacket object containing timestamp, channels, ref/drl data
        """
        if self.start_time is None:
            self.start_time = packet.timestamp
            print(f"EEG streaming started at {time.strftime('%H:%M:%S', time.localtime(packet.timestamp))}")
            print(f"Channels: {len(packet.channels)} EEG + REF + DRL")
            print("-" * 60)
        
        # Store data
        self.eeg_buffer.append(packet.channels)
        self.timestamps.append(packet.timestamp)
        self.packet_count += 1
        
        # Real-time analysis every second
        current_time = packet.timestamp
        if current_time - self.last_stats_time >= 1.0:
            self._print_realtime_stats(packet)
            self.last_stats_time = current_time
        
    def _print_realtime_stats(self, packet: EEGPacket) -> None:
        """Print real-time statistics"""
        if len(self.eeg_buffer) < 10:
            return
            
        # Calculate statistics for last 1000 samples
        recent_samples = list(self.eeg_buffer)[-1000:] if len(self.eeg_buffer) >= 1000 else list(self.eeg_buffer)
        
        if recent_samples:
            # Convert to numpy array for easier analysis
            data_array = np.array(recent_samples)
            
            # Calculate stats per channel
            means = np.mean(data_array, axis=0)
            stds = np.std(data_array, axis=0)
            
            # Calculate data rate
            duration = packet.timestamp - self.start_time
            rate = self.packet_count / duration if duration > 0 else 0
            
            print(f"\n📈 Real-time Stats (Packet #{packet.counter}, Rate: {rate:.1f} Hz)")
            print(f"   REF: {packet.ref:7.1f} µV | DRL: {packet.drl:7.1f} µV")
            
            # Show first 4 channels to keep output manageable
            for i in range(min(4, len(means))):
                print(f"   {self.channel_names[i]:>3}: {packet.channels[i]:7.1f} µV "
                      f"(avg: {means[i]:6.1f} ± {stds[i]:5.1f} µV)")
            
            if len(means) > 4:
                print(f"   ... and {len(means) - 4} more channels")
                
    def get_current_data(self, samples: int = 500) -> Optional[np.ndarray]:
        """
        Get recent EEG data as numpy array
        
        Args:
            samples: Number of recent samples to return
            
        Returns:
            numpy array of shape (samples, channels) or None if insufficient data
        """
        if len(self.eeg_buffer) < samples:
            return None
            
        recent_data = list(self.eeg_buffer)[-samples:]
        return np.array(recent_data)
        
    def print_summary(self) -> None:
        """Print final summary statistics"""
        if self.packet_count == 0:
            return
            
        duration = time.time() - (self.start_time or time.time())
        avg_rate = self.packet_count / duration if duration > 0 else 0
        
        print("\n" + "="*60)
        print("SESSION SUMMARY")
        print("="*60)
        print(f"Duration: {duration:.1f} seconds")
        print(f"Packets received: {self.packet_count}")
        print(f"Average rate: {avg_rate:.1f} Hz")
        print(f"Buffer size: {len(self.eeg_buffer)} samples")
        
        if self.eeg_buffer:
            data_array = np.array(list(self.eeg_buffer))
            print(f"Data shape: {data_array.shape} (samples x channels)")
            print(f"Data range: {np.min(data_array):.1f} to {np.max(data_array):.1f} µV")


class RawDataLogger:
    """Example raw data logger for debugging and analysis"""
    
    def __init__(self):
        self.raw_packet_count = 0
        self.total_bytes = 0
        
    def process_raw_data(self, data: bytes) -> None:
        """
        Process raw data from MW75 device
        
        Args:
            data: Raw bytes from RFCOMM connection
        """
        self.raw_packet_count += 1
        self.total_bytes += len(data)
        
        # Log raw data info (useful for debugging)
        if self.raw_packet_count <= 5 or self.raw_packet_count % 100 == 0:
            print(f"Raw data chunk #{self.raw_packet_count}: {len(data)} bytes")
            # Show first few bytes in hex
            hex_preview = ' '.join(f'{b:02x}' for b in data[:8])
            print(f"   Data preview: {hex_preview}...")
            
    def get_stats(self) -> dict:
        """Get raw data statistics"""
        return {
            'raw_packets': self.raw_packet_count,
            'total_bytes': self.total_bytes,
            'avg_bytes_per_packet': self.total_bytes / max(1, self.raw_packet_count)
        }


class EventLogger:
    """Example logger for non-EEG events"""
    
    def __init__(self):
        self.events = []
        
    def process_other_event(self, packet: bytes) -> None:
        """
        Process non-EEG events
        
        Args:
            packet: Raw event packet bytes
        """
        if len(packet) >= 4:
            event_id = packet[1]
            counter = packet[3]
            timestamp = time.time()
            
            self.events.append({
                'timestamp': timestamp,
                'event_id': event_id, 
                'counter': counter,
                'data_length': len(packet)
            })
            
            print(f"Event #{len(self.events)}: ID={event_id}, Counter={counter}, Size={len(packet)}B")


async def main():
    """Main example function demonstrating callback integration"""
    
    print("MW75 Streamer - Callback Integration Example")
    print("=" * 50)
    print("This example shows how to use custom callbacks for real-time EEG processing.")
    print("Press Ctrl+C to stop streaming.\n")
    
    # Create our custom processors
    eeg_processor = EEGDataProcessor()
    raw_logger = RawDataLogger()
    event_logger = EventLogger()
    
    # Create MW75 streamer with callbacks
    streamer = MW75Streamer(
        # Traditional outputs (optional)
        csv_file=None,  # Set to "eeg_data.csv" if you want CSV output too
        
        # Custom callbacks for real-time processing
        eeg_callback=eeg_processor.process_eeg_packet,
        raw_data_callback=raw_logger.process_raw_data,
        other_event_callback=event_logger.process_other_event,
        
        # Enable verbose logging
        verbose=True
    )
    
    try:
        # Start streaming (this will run until Ctrl+C)
        print("Starting MW75 EEG streaming...")
        print("   Make sure MW75 headphones are paired and powered on.")
        print("   Streaming will begin automatically once connected.\n")
        
        success = await streamer.start_streaming()
        
        if not success:
            print("Streaming failed. Check device connection.")
            return
            
    except KeyboardInterrupt:
        print("\nStreaming interrupted by user")
        
    except Exception as e:
        print(f"\nError during streaming: {e}")
        
    finally:
        # Print final statistics
        eeg_processor.print_summary()
        
        raw_stats = raw_logger.get_stats()
        print(f"\nRaw Data Stats:")
        print(f"   Packets: {raw_stats['raw_packets']}")
        print(f"   Total bytes: {raw_stats['total_bytes']:,}")
        print(f"   Avg per packet: {raw_stats['avg_bytes_per_packet']:.1f} bytes")
        
        print(f"\nEvents captured: {len(event_logger.events)}")
        
        # Example: Save data for further analysis
        current_data = eeg_processor.get_current_data(1000)
        if current_data is not None:
            print(f"\nLatest 1000 samples available for analysis:")
            print(f"   Shape: {current_data.shape}")
            print(f"   You could save this with: np.save('eeg_data.npy', current_data)")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nGoodbye!")
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)
