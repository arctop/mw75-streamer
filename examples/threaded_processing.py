#!/usr/bin/env python3
"""
MW75 Streamer - Threaded Processing Example

This example demonstrates how to use separate threads for heavy EEG processing
to avoid blocking the main RFCOMM streaming thread. 

This pattern is recommended when your callback processing takes more than ~1-2ms,
which could otherwise cause dropped packets at the 500Hz data rate.
"""

import asyncio
import threading
import queue
import time
import numpy as np
from typing import List, Optional
from dataclasses import dataclass

from mw75_streamer.main import MW75Streamer
from mw75_streamer import EEGPacket

@dataclass
class ProcessingTask:
    """Task for the processing thread"""
    packet: EEGPacket
    timestamp: float


class ThreadedEEGProcessor:
    """
    EEG processor that uses a separate thread for heavy computation
    while keeping the main RFCOMM thread responsive.
    """
    
    def __init__(self, max_queue_size: int = 1000):
        """
        Initialize threaded processor
        
        Args:
            max_queue_size: Maximum number of packets to queue (prevents memory buildup)
        """
        # Thread-safe queue for passing data to processing thread
        self.task_queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self.stop_event = threading.Event()
        self.processing_thread: Optional[threading.Thread] = None
        
        # Statistics
        self.packets_received = 0
        self.packets_processed = 0
        self.packets_dropped = 0
        self.start_time = time.time()
        
        # Start processing thread
        self._start_processing_thread()
        
    def _start_processing_thread(self):
        """Start the background processing thread"""
        self.processing_thread = threading.Thread(
            target=self._processing_worker, 
            name="EEG-Processor",
            daemon=True
        )
        self.processing_thread.start()
        print("Started background processing thread")
        
    def eeg_callback(self, packet: EEGPacket) -> None:
        """
        Fast callback for EEG packets - just queues for processing
        This runs in the RFCOMM thread and must be very fast!
        """
        self.packets_received += 1
        
        try:
            # Try to queue the packet (non-blocking)
            task = ProcessingTask(packet=packet, timestamp=time.time())
            self.task_queue.put_nowait(task)
        except queue.Full:
            # Queue is full - drop packet and track it
            self.packets_dropped += 1
            if self.packets_dropped % 100 == 1:  # Log every 100 drops
                print(f"Queue full - dropped {self.packets_dropped} packets so far")
    
    def _processing_worker(self):
        """
        Background worker thread for heavy EEG processing
        This runs in a separate thread and can take longer
        """
        print("Background EEG processing thread started")
        
        while not self.stop_event.is_set():
            try:
                # Get next task with timeout
                task = self.task_queue.get(timeout=1.0)
                
                # Do the heavy processing here
                self._process_eeg_packet(task.packet, task.timestamp)
                
                self.packets_processed += 1
                self.task_queue.task_done()
                
            except queue.Empty:
                # No task available - check if we should stop
                continue
            except Exception as e:
                print(f"Error in processing thread: {e}")
                
        print("Background processing thread stopped")
    
    def _process_eeg_packet(self, packet: EEGPacket, received_time: float):
        """
        Heavy EEG processing that happens in background thread
        Add your computationally intensive operations here
        """
        # Example: Simulate heavy processing
        processing_start = time.time()
        
        # 1. Convert to numpy for efficient processing
        eeg_data = np.array(packet.channels)
        
        # 2. Example: Apply some filtering (computationally intensive)
        # This is just a demo - you'd use scipy.signal for real filtering
        filtered_data = self._simple_filter(eeg_data)
        
        # 3. Example: Calculate frequency domain features
        power_spectrum = np.abs(np.fft.fft(filtered_data))
        alpha_power = np.mean(power_spectrum[8:13])  # 8-13 Hz alpha band (simplified)
        
        # 4. Example: Machine learning inference (would be expensive)
        # prediction = self.ml_model.predict(features)
        
        processing_time = time.time() - processing_start
        
        # Log results periodically
        if self.packets_processed % 500 == 0:  # Every second at 500Hz
            latency = processing_start - packet.timestamp
            queue_size = self.task_queue.qsize()
            
            print(f"Processed packet #{packet.counter}")
            print(f"  Processing time: {processing_time*1000:.1f}ms")
            print(f"  Latency: {latency*1000:.1f}ms")
            print(f"  Queue size: {queue_size}")
            print(f"  Alpha power: {alpha_power:.1f}")
            print(f"  Ch1: {packet.channels[0]:.1f} µV")
    
    def _simple_filter(self, data: np.ndarray) -> np.ndarray:
        """
        Simple filtering example (not a real filter!)
        In practice, you'd use scipy.signal.butter, etc.
        """
        # Simulate some computation time
        time.sleep(0.001)  # 1ms of processing
        
        # Just return original data for demo
        return data
    
    def get_stats(self) -> dict:
        """Get processing statistics"""
        duration = time.time() - self.start_time
        return {
            'packets_received': self.packets_received,
            'packets_processed': self.packets_processed,
            'packets_dropped': self.packets_dropped,
            'queue_size': self.task_queue.qsize(),
            'processing_rate': self.packets_processed / max(duration, 0.001),
            'drop_rate': self.packets_dropped / max(self.packets_received, 1) * 100
        }
    
    def stop(self):
        """Stop the processing thread"""
        print("Stopping processing thread...")
        self.stop_event.set()
        
        if self.processing_thread:
            self.processing_thread.join(timeout=2.0)
            
        # Print final stats
        stats = self.get_stats()
        print(f"\nFinal Processing Stats:")
        print(f"  Received: {stats['packets_received']}")
        print(f"  Processed: {stats['packets_processed']}")
        print(f"  Dropped: {stats['packets_dropped']} ({stats['drop_rate']:.1f}%)")
        print(f"  Processing rate: {stats['processing_rate']:.1f} Hz")


class AsyncEEGProcessor:
    """
    Alternative async-based processor using asyncio queues
    Good for I/O-bound processing (database writes, network requests)
    """
    
    def __init__(self, max_queue_size: int = 1000):
        self.packet_queue: asyncio.Queue = asyncio.Queue(maxsize=max_queue_size)
        self.processing_task: Optional[asyncio.Task] = None
        self.packets_processed = 0
        
    async def start(self):
        """Start the async processing task"""
        self.processing_task = asyncio.create_task(self._async_processor())
        print("Started async EEG processor")
    
    def eeg_callback(self, packet: EEGPacket) -> None:
        """
        Callback that queues packets for async processing
        Note: This still runs in the RFCOMM thread, so keep it fast!
        """
        try:
            # Schedule the packet for async processing
            loop = asyncio.get_event_loop()
            loop.call_soon_threadsafe(self._queue_packet, packet)
        except Exception as e:
            print(f"Error queuing packet for async processing: {e}")
    
    def _queue_packet(self, packet: EEGPacket):
        """Queue packet in async context"""
        try:
            self.packet_queue.put_nowait(packet)
        except asyncio.QueueFull:
            print("Async queue full - dropping packet")
    
    async def _async_processor(self):
        """Async processing loop"""
        while True:
            try:
                # Wait for next packet
                packet = await self.packet_queue.get()
                
                # Do async processing (e.g., database writes, API calls)
                await self._process_packet_async(packet)
                
                self.packets_processed += 1
                self.packet_queue.task_done()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Error in async processor: {e}")
    
    async def _process_packet_async(self, packet: EEGPacket):
        """
        Async processing function - good for I/O operations
        """
        # Example: Simulate async I/O (database write, API call)
        await asyncio.sleep(0.001)  # 1ms async operation
        
        # Example: Send to database, API, etc.
        # await database.store_eeg_data(packet)
        # await api_client.send_realtime_data(packet)
        
        if self.packets_processed % 500 == 0:
            print(f"Async processed packet #{packet.counter}, Ch1: {packet.channels[0]:.1f} µV")
    
    async def stop(self):
        """Stop the async processor"""
        if self.processing_task:
            self.processing_task.cancel()
            try:
                await self.processing_task
            except asyncio.CancelledError:
                pass
        print(f"Async processor stopped. Processed {self.packets_processed} packets.")


async def main():
    """Example showing both threading approaches"""
    print("MW75 Streamer - Threaded Processing Example")
    print("=" * 50)
    print("This example shows how to handle heavy EEG processing")
    print("without blocking the main RFCOMM streaming thread.")
    print("Press Ctrl+C to stop.\n")
    
    # Choose processing approach
    print("Available processing approaches:")
    print("1. Threaded processor (recommended for CPU-heavy tasks)")
    print("2. Async processor (good for I/O-heavy tasks)")
    print("3. Both (for demonstration)")
    
    choice = input("Enter choice (1-3): ").strip()
    
    threaded_processor = None
    async_processor = None
    
    if choice in ["1", "3"]:
        threaded_processor = ThreadedEEGProcessor(max_queue_size=1000)
    
    if choice in ["2", "3"]:
        async_processor = AsyncEEGProcessor(max_queue_size=1000)
        await async_processor.start()
    
    # Create callback function
    def combined_callback(packet: EEGPacket):
        """Fast callback that delegates to processors"""
        if threaded_processor:
            threaded_processor.eeg_callback(packet)
        if async_processor:
            async_processor.eeg_callback(packet)
    
    # Create MW75 streamer
    streamer = MW75Streamer(
        eeg_callback=combined_callback,
        verbose=True
    )
    
    try:
        print(f"\nStarting MW75 streaming with {'threaded' if choice=='1' else 'async' if choice=='2' else 'combined'} processing...")
        await streamer.start_streaming()
        
    except KeyboardInterrupt:
        print("\nStopping streaming...")
        
    finally:
        # Cleanup processors
        if threaded_processor:
            threaded_processor.stop()
        if async_processor:
            await async_processor.stop()
        
        print("\nCleanup complete.")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Goodbye!")
    except Exception as e:
        print(f"Error: {e}")
