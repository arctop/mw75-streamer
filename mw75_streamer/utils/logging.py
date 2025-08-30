"""
Logging utilities for MW75 EEG Streamer

Provides consistent logging setup and configuration across the application.
"""

import sys
import logging
from typing import Optional


def setup_logging(verbose: bool = False, logger_name: Optional[str] = None) -> logging.Logger:
    """
    Setup logging configuration for the MW75 streamer

    Args:
        verbose: Enable debug level logging if True, otherwise info level
        logger_name: Name for the logger, defaults to the package name

    Returns:
        Configured logger instance
    """
    if logger_name is None:
        logger_name = "mw75_streamer"

    level = logging.DEBUG if verbose else logging.INFO

    # Create formatter for consistent log format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
    )

    # Setup stderr handler
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(formatter)

    # Configure logger
    logger = logging.getLogger(logger_name)
    logger.setLevel(level)

    # Remove any existing handlers to avoid duplicates
    logger.handlers.clear()
    logger.addHandler(handler)

    # Prevent propagation to avoid duplicate messages
    logger.propagate = False

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a specific module

    Args:
        name: Module name (usually __name__)

    Returns:
        Logger instance with consistent configuration
    """
    return logging.getLogger(name)
