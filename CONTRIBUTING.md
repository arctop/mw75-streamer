# Contributing to MW75 EEG Streamer

Thank you for your interest in contributing to MW75 EEG Streamer! We welcome contributions that help make EEG data streaming more accessible across platforms.

## Priority Contributions

### Bluetooth Transport Reliability
**Status**: High Priority  
**Difficulty**: High  

We're currently not achieving the full 500Hz streaming rate due to Bluetooth transport limitations. Help optimize the data streaming pipeline to reach true 500Hz performance.

**What's needed**:
- Investigate packet loss and timing issues in RFCOMM streaming
- Optimize buffer management and data processing pipeline
- Research Bluetooth timing constraints and protocol optimizations
- Test different Bluetooth stack configurations
- Profile and optimize the data path from device to application

**Getting started**:
- Review current streaming performance metrics
- Analyze packet timing and loss patterns
- Research Bluetooth Classic optimization techniques

### Linux Support
**Status**: High Priority  
**Difficulty**: Moderate  

Help bring MW75 EEG streaming to Linux by implementing Bluetooth Classic (RFCOMM) support. The current macOS implementation uses IOBluetooth via PyObjC, but Linux needs a different approach.

**What's needed**:
- Replace macOS-specific Bluetooth code in `mw75_streamer/device/rfcomm_manager.py`
- Implement Linux Bluetooth socket connections for RFCOMM channel 25
- Test with various Linux distributions and Bluetooth stacks
- Update documentation and requirements

**Getting started**:
- Review the existing RFCOMM protocol implementation
- Check the [Protocol Documentation](https://arctop.github.io/mw75-streamer/api/protocol.html) for technical details
- Research Linux Bluetooth libraries (PyBluez, socket module)
- Test BLE activation (already cross-platform via bleak)

### Other Contribution Opportunities

- **Windows Support**: Implement Windows Bluetooth APIs for RFCOMM streaming
- **Protocol Analysis**: Support additional MW75 features and commands
- **Testing Framework**: Add unit tests for data processing components
- **Hardware Validation**: Test with different MW75 firmware versions

## Development Setup

```bash
# Clone and setup
git clone https://github.com/arctop/mw75-streamer.git
cd mw75_streamer
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Code quality
black mw75_streamer/
mypy mw75_streamer/ --ignore-missing-imports
flake8 mw75_streamer/
```

## Contribution Process

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/linux-support`)
3. **Test** your changes thoroughly
4. **Run** code quality checks (black, mypy, flake8)
5. **Submit** a pull request with clear description

## Code Standards

- Follow existing code style and patterns
- Add type annotations for all new code
- Include docstrings for public functions
- Maintain compatibility with Python 3.9+

## Hardware Requirements

- **MW75 Neuro headphones** for testing
- **Bluetooth-enabled development machine**
- Multiple OS environments for cross-platform testing (preferred)

## Questions?

Open an issue for questions about:
- MW75 protocol details
- Architecture decisions
- Development environment setup
- Hardware-specific troubleshooting

We're here to help make your contribution successful!