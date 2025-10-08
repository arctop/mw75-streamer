# MW75 Neuro Streamer

[![CI](https://github.com/arctop/mw75-streamer/actions/workflows/ci.yml/badge.svg)](https://github.com/arctop/mw75-streamer/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Stream 12-channel EEG data from MW75 Neuro headphones with WebSocket, CSV, and LSL output support.

📖 **[Full Documentation & API Reference](https://arctop.github.io/mw75-streamer/api/)**

**About `uv`:** This project uses [uv](https://docs.astral.sh/uv/) for fast, reliable Python package management. Benefits include faster installs, better dependency resolution, and reproducible environments. All commands can be run with regular Python too (see [Alternative: Using Python Directly](#alternative-using-python-directly)), but we use `uv` throughout this documentation for consistency.

## Features

- **Real-time streaming**: 500Hz, 12-channel EEG with µV precision
- **Multiple outputs**: WebSocket JSON, CSV files, Lab Streaming Layer (LSL)
- **Built-in testing**: WebSocket servers with browser visualization
- **Robust protocol**: Checksum validation and error detection  

## Installation

**Option 1: Install from PyPI (recommended)**

```bash
uv pip install mw75-streamer
```

For additional features (WebSocket, LSL support):
```bash
uv pip install "mw75-streamer[all]"
```

**Option 2: Install from source**

```bash
# Clone this repository
git clone https://github.com/arctop/mw75-streamer.git
cd mw75_streamer
```

![Installation Demo](docs/assets/installation.gif)

```bash
# Install uv if needed (see installation guide: https://docs.astral.sh/uv/getting-started/installation)
brew install uv

# Create environment and install package
uv venv && uv pip install -e ".[all]"
```

## Usage

```bash
# Basic streaming
uv run -m mw75_streamer --browser
uv run -m mw75_streamer --csv eeg.csv
uv run -m mw75_streamer --ws ws://localhost:8080
uv run -m mw75_streamer --lsl MW75_EEG

# Combined outputs
uv run -m mw75_streamer --csv eeg.csv --ws ws://localhost:8080

# WebSocket Server (remote control mode)
uv run -m mw75_streamer.server --port 8080
```
![Browser Visualization](docs/assets/browser.gif)


## Developer Examples

For advanced integration into your own applications, see the [examples/](examples/) folder:

- **[simple_callback.py](examples/simple_callback.py)** - Quick start example for basic callback usage
- **[callback_integration.py](examples/callback_integration.py)** - Comprehensive example showing real-time EEG processing using custom callbacks  
- **[threaded_processing.py](examples/threaded_processing.py)** - Threading patterns for heavy processing (recommended for ML/filtering)
- **Custom Callbacks**: Process EEG packets, raw data, and events directly in your code  
- **Performance Guidance**: Keep callbacks fast (< 1ms) or use threading for heavy work
- **Integration Patterns**: Combine callbacks with existing outputs (CSV, WebSocket, LSL)

```python
# Quick callback example
from mw75_streamer import MW75Streamer, EEGPacket

def process_eeg(packet: EEGPacket):
    # packet.channels = 12 EEG channels in µV
    print(f"Ch1: {packet.channels[0]:.1f} µV")

streamer = MW75Streamer(eeg_callback=process_eeg)
await streamer.start_streaming()
```

See [examples/README.md](examples/README.md) for complete documentation.

## Testing

```bash
# 1. Start test server
uv run -m mw75_streamer.testing --advanced
# Optional: Press 'b' + Enter in server terminal to open browser visualization

# 2. Start EEG streaming
uv run -m mw75_streamer --ws ws://localhost:8080
```

## WebSocket Server (Remote Control Mode)

For applications that need remote control of MW75 device connections, the package includes a WebSocket server mode:

```bash
# Start server
uv run -m mw75_streamer.server --port 8080

# Example client
python examples/websocket_server_client.py
```

**Features:**
- Remote device connection control via JSON commands
- Real-time EEG data streaming  
- Auto-reconnect with exponential backoff
- Configurable log levels (DEBUG, INFO, WARNING, ERROR)
- Single client connection with 30-second keepalive

For complete protocol documentation and examples, see the [WebSocket Server documentation](https://arctop.github.io/mw75-streamer/api/server.html).

## How It Works

1. **BLE Activation**: Discovers MW75 via Bluetooth LE and sends activation commands
2. **RFCOMM Streaming**: Connects to channel 25 and receives 63-byte packets
3. **Data Processing**: Converts raw ADC to µV, validates checksums, outputs to CSV/WebSocket/LSL

## Data Formats

**CSV**: `Timestamp,EventId,Counter,Ref,DRL,Ch1RawEEG,...,Ch12RawEEG,FeatureStatus`

**WebSocket JSON**: Real-time streaming with timestamp, counter, ref/drl, and 12 channel values in µV

## Requirements

- **Hardware**: MW75 Neuro headphones (paired via Bluetooth)
- **OS**: macOS (fully supported), Linux (planned - [contributions welcome](CONTRIBUTING.md))
- **Python**: 3.9+

## macOS Setup for LSL

```bash
# Install LSL library (for LSL support)
brew install labstreaminglayer/tap/lsl
export DYLD_LIBRARY_PATH="/opt/homebrew/lib:$DYLD_LIBRARY_PATH"

# Pair MW75 headphones in System Preferences > Bluetooth
```


## Performance Optimization

For improved real-time performance and reduced packet drops, run with elevated priority:

```bash
# Run with high priority (requires sudo for optimal performance)
sudo uv run -m mw75_streamer --csv eeg.csv

# The streamer automatically sets:
# - Process priority (niceness -10)
# - Thread real-time scheduling policy
# - Optimized RFCOMM event loop timing (1ms intervals)
```

**Note**: Running without `sudo` will still work but may have higher packet drop rates under system load.

## Troubleshooting

- **MW75 not found**: Ensure headphones are powered on and paired
- **Connection failed**: Re-pair device in Bluetooth settings
- **Dropped packets**: Reduce Bluetooth interference, move away from WiFi routers and other 2.4GHz devices

For detailed troubleshooting, see the [Troubleshooting Guide](https://arctop.github.io/mw75-streamer/api/troubleshooting.html)

## Alternative: Using Python Directly

All `uv` commands can be replaced with regular Python. Simply activate your virtual environment first:

```bash
# Example: Replace 'uv run -m mw75_streamer' with 'python -m mw75_streamer'
source .venv/bin/activate
python -m mw75_streamer --csv eeg.csv --ws ws://localhost:8080
python -m mw75_streamer.testing --advanced

# Or replace 'uv pip install' with 'pip install'  
pip install mw75-streamer
```

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup and contribution guidelines.

## License

MIT License - see [LICENSE](LICENSE) for details.

## About

**MW75 EEG Streamer** was developed by [Arctop](https://arctop.com), a neurotechnology company focused on making brain-computer interfaces accessible and practical.

## Acknowledgments

### AI Assistance
- **[Claude Code (by Anthropic)](https://claude.ai/code)** - AI coding assistant used for development support and code optimization.

### Open Source Dependencies
This project builds upon excellent open source libraries:

- **[bleak](https://github.com/hbldh/bleak)** - Cross-platform Bluetooth Low Energy library for Python
- **[PyObjC](https://github.com/ronaldoussoren/pyobjc)** - Python bridge to Objective-C for macOS integration
- **[websocket-client](https://github.com/websocket-client/websocket-client)** - WebSocket client library for real-time streaming
- **[websockets](https://github.com/aaugustin/websockets)** - WebSocket server implementation for testing tools
- **[pylsl](https://github.com/labstreaminglayer/liblsl-Python)** - Python bindings for Lab Streaming Layer
- **[black](https://github.com/psf/black)** - Python code formatter for consistent style
- **[mypy](https://github.com/python/mypy)** - Static type checker for Python
- **[flake8](https://github.com/PyCQA/flake8)** - Python linting tool for code quality

### Hardware & Community
- **Master & Dynamic** for creating the MW75 Neuro headphones and making EEG accessible
- The **Python community** for excellent Bluetooth libraries and frameworks
---

For detailed technical information about the MW75 protocol, see the inline documentation in the source code.
