# MW75 Neuro Streamer

[![CI](https://github.com/arctop/mw75-streamer/actions/workflows/ci.yml/badge.svg)](https://github.com/arctop/mw75-streamer/actions/workflows/ci.yml)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

Stream 12-channel EEG data from MW75 Neuro headphones with WebSocket, CSV, and LSL output support.

## Features

- **Real-time streaming**: 500Hz, 12-channel EEG with µV precision
- **Multiple outputs**: WebSocket JSON, CSV files, Lab Streaming Layer (LSL)
- **Built-in testing**: WebSocket servers with browser visualization
- **Robust protocol**: Checksum validation and error detection  

## Installation

```bash
# Clone this repository
git clone https://github.com/arctop/mw75-streamer.git
cd mw75_streamer
```

![Installation Demo](docs/assets/installation.gif)

**Option 1: Using uv (recommended)**

1. Install uv if you need (see [installtion guide](https://docs.astral.sh/uv/getting-started/installation))
```bash
brew install uv
```


2. install python, the dependencies and this package
```bash
uv venv && uv pip install -e ".[all]"
```

**Option 2: Using pip**
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[all]"
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
```
![Browser Visualization](docs/assets/browser.gif)


## Testing

```bash
# 1. Start test server
uv run -m mw75_streamer.testing --advanced
# Optional: Press 'b' + Enter in server terminal to open browser visualization

# 2. Start EEG streaming
uv run -m mw75_streamer --ws ws://localhost:8080
```

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

## Alternative: Using Python Directly

If you prefer to use regular Python instead of `uv`, activate your virtual environment first:

```bash
# After installation with pip
source .venv/bin/activate
python -m mw75_streamer --csv eeg.csv --ws ws://localhost:8080
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
