"""
Setup configuration for MW75 EEG Streamer package
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="mw75-streamer",
    version="1.0.0",
    author="Eitan Kay",
    author_email="opensource@arctop.com",
    maintainer="Arctop",
    description="Stream EEG data from MW75 Neuro headphones using BLE and RFCOMM",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: MIT License",
        "Operating System :: MacOS :: MacOS X",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Topic :: Scientific/Engineering :: Medical Science Apps.",
        "Topic :: System :: Hardware :: Hardware Drivers",
        "Topic :: Scientific/Engineering :: Science Apps.",
    ],
    python_requires=">=3.7",
    install_requires=[
        "bleak>=0.20.0",
        "pyobjc>=9.0; sys_platform=='darwin'",
        "pyobjc-framework-IOBluetooth>=9.0; sys_platform=='darwin'",
    ],
    extras_require={
        "websocket": ["websocket-client>=1.6.0"],
        "dev": ["pytest", "black", "flake8", "mypy"],
    },
    entry_points={
        "console_scripts": [
            "mw75-streamer=mw75_streamer.main:cli_main",
            "mw75-test-server=mw75_streamer.testing.__main__:main",
        ],
    },
)