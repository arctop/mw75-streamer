# MW75 Streamer Examples

This folder contains examples demonstrating how to integrate the MW75 streamer into your own applications using the enhanced callback interface.

## Examples

### 1. `simple_callback.py` - Minimal Callback Example

**Quick start example** - Shows the basics of using EEG callbacks:

```python
from mw75_streamer import MW75Streamer, EEGPacket

def process_eeg_data(packet: EEGPacket):
    print(f"Ch1: {packet.channels[0]:.1f} µV")

streamer = MW75Streamer(eeg_callback=process_eeg_data)
await streamer.start_streaming()
```

### 2. `callback_integration.py` - Comprehensive Callback Example

**Recommended starting point** - Shows how to use all three callback types:

- **EEG Callback**: Real-time processing of parsed EEG packets with µV data
- **Raw Data Callback**: Access to raw device bytes for debugging/analysis  
- **Other Event Callback**: Handling of non-EEG events

**Features:**
- Real-time statistics and analysis
- Channel-wise analysis
- Raw data logging for debugging
- Event capture and logging
- Session summary statistics

**Usage:**
```bash
# With uv:
uv run callback_integration.py

# Or directly with python
python callback_integration.py

```

### 3. `threaded_processing.py` - Heavy Processing with Threading

**For computationally intensive processing** - Shows how to handle heavy EEG processing without blocking the streaming thread:

- **Thread-safe queuing**: Lightweight callback queues packets for background processing
- **Separate processing thread**: CPU-intensive work runs in dedicated thread
- **Async processing option**: Alternative pattern for I/O-heavy operations
- **Performance monitoring**: Queue size, latency, and drop rate tracking

**When to use:**
- Callback processing takes > 1-2ms (signal filtering, ML inference, etc.)
- Real-time processing requirements (avoid dropped packets)
- Database writes, API calls, or other I/O operations

**Usage:**
```bash
python threaded_processing.py
# Choose: 1) Threading, 2) Async, or 3) Both
```

### 4. `websocket_server_client.py` - Remote Control via WebSocket Server

**For remote device control** - Demonstrates how to connect to the MW75 WebSocket server and control device connections remotely:

- **Remote device control**: Connect/disconnect to MW75 device via WebSocket
- **Real-time data streaming**: Receive EEG data over WebSocket
- **Status monitoring**: Track connection state and device status
- **Auto-reconnect**: Automatic reconnection with exponential backoff
- **Log filtering**: Configure log levels (DEBUG, INFO, WARNING, ERROR)

**When to use:**
- Building applications that need remote MW75 control
- Web-based or mobile applications connecting to MW75
- Distributed systems requiring EEG data streaming
- Multiple services accessing the same MW75 device (one at a time)

**Usage:**
```bash
# 1. Start the server in one terminal:
uv run -m mw75_streamer.server --port 8080

# 2. Run the client in another terminal:
python examples/websocket_server_client.py
```

## Performance Guidelines

### When to Use Threading

The MW75 streams at **500 Hz** (every 2ms). Your callback runs in the main RFCOMM thread, so timing is critical:

**✅ Direct callbacks OK for:**
- Simple logging, printing
- Basic math operations  
- Lightweight data forwarding
- Processing time < 1ms

**⚠️ Use threading for:**
- Signal filtering (scipy.signal)
- Machine learning inference
- Database writes or API calls
- File I/O operations
- Processing time > 1-2ms

**Example - When threading is needed:**
```python
# ❌ This will block RFCOMM and drop packets:
def slow_callback(packet: EEGPacket):
    filtered = scipy.signal.butter_filter(packet.channels)  # ~5ms
    prediction = ml_model.predict(filtered)  # ~10ms
    database.save(packet, prediction)  # ~20ms
    
# ✅ This keeps RFCOMM responsive:
def fast_callback(packet: EEGPacket):
    processing_queue.put(packet)  # ~0.1ms
```

### Threading Patterns

**1. Thread-safe Queue (recommended):**
```python
import queue, threading

packet_queue = queue.Queue(maxsize=1000)

def fast_callback(packet):
    try:
        packet_queue.put_nowait(packet)  # Fast, non-blocking
    except queue.Full:
        print("Dropped packet - queue full")

def worker_thread():
    while True:
        packet = packet_queue.get()
        # Heavy processing here
        heavy_processing(packet)
```

**2. Async Processing:**
```python
import asyncio

async def async_callback(packet):
    await database.store_eeg(packet)  # I/O doesn't block

# Use call_soon_threadsafe to bridge sync callback to async
```

## Integration Patterns

### Basic EEG Processing
```python
from mw75_streamer import MW75Streamer, EEGPacket

def my_eeg_handler(packet: EEGPacket):
    # packet.channels = list of 12 EEG channels in µV
    # packet.ref, packet.drl = reference electrodes  
    # packet.timestamp = precise timestamp
    print(f"EEG: {packet.channels[0]:.1f} µV at {packet.timestamp}")

streamer = MW75Streamer(eeg_callback=my_eeg_handler)
await streamer.start_streaming()
```

### Raw Data Access
```python
def raw_data_handler(data: bytes):
    # Direct access to RFCOMM data chunks
    print(f"Raw chunk: {len(data)} bytes")

streamer = MW75Streamer(raw_data_callback=raw_data_handler)
```

### Combined Usage
```python
# Use callbacks alongside traditional outputs
streamer = MW75Streamer(
    csv_file="backup.csv",           # Still save to CSV
    eeg_callback=process_realtime,   # Plus real-time processing  
    websocket_url="ws://localhost:8080"  # And WebSocket streaming
)
```

## Data Format Details

### EEGPacket Object
```python
@dataclass
class EEGPacket:
    timestamp: float       # Unix timestamp with high precision
    event_id: int          # Always 239 for EEG packets  
    counter: int           # Sequence counter (0-255, wraps around)
    ref: float             # Reference electrode (µV)
    drl: float             # Driven Right Leg electrode (µV) 
    channels: List[float]  # 12 EEG channels (µV) - Ch1 through Ch12
    feature_status: int    # Device feature status flags
    checksum_valid: bool   # Always True (invalid packets filtered out)
```

### Channel Layout
MW75 uses a 12-channel EEG layout:
- `channels[0]` = Ch1 through `channels[11]` = Ch12
- All values in microvolts (µV)  
- 500 Hz sampling rate (packets arrive every ~2ms)
- Pre-filtered and scaled from raw ADC values

## Requirements

All examples require:
- **Hardware**: MW75 Neuro headphones (paired via Bluetooth)
- **OS**: macOS (Linux support planned)  
- **Python**: 3.9+
- **Installation**: `pip install "mw75-streamer[all]"`

## Performance Notes

- Callbacks are called from the main streaming thread
- Keep callback processing fast to avoid dropped packets
- For heavy processing, consider using queues to offload work
- Running with `sudo` provides better real-time performance

## Contributing Examples

Have a useful integration pattern? We welcome contributions!

1. Create your example file in this folder
2. Follow the naming pattern: `<use_case>_example.py`
3. Include comprehensive docstrings and error handling
4. Add an entry to this README
5. Submit a pull request

See [CONTRIBUTING.md](../CONTRIBUTING.md) for details.

---

For questions or issues with examples, please open an issue at:
https://github.com/arctop/mw75-streamer/issues
