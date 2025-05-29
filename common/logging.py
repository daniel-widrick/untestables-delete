"""
Logging functionality

This module provides functions for setting up logging with consistent formatting
and support for both console and file output.
"""

import logging
import sys
from typing import Optional

# Global variable to hold the specifically configured application logger instance.
# Using a more descriptive name for the logger itself, e.g., "untestables_app_logger".
_app_logger: Optional[logging.Logger] = None
_APP_LOGGER_NAME = "untestables_app" # Choose a fixed name for your application logger

def setup_logging(log_file: Optional[str] = None) -> None:
    """
    Initialize or reconfigure the shared application logger.
    This function should be called once at the application's start.
    """
    global _app_logger

    if _app_logger is None:
        _app_logger = logging.getLogger(_APP_LOGGER_NAME)
        _app_logger.setLevel(logging.INFO)
    else:
        # If called again, clear existing handlers to avoid duplication
        # This might happen if setup_logging is inadvertently called multiple times,
        # though the goal is to call it once from cli.py at the very start.
        for handler in _app_logger.handlers[:]:
            _app_logger.removeHandler(handler)

    log_format = "%(asctime)s | %(levelname)8s | %(message)s"
    formatter = logging.Formatter(log_format)

    # Create and add console handler
    console_handler = logging.StreamHandler(stream=sys.stdout) # Explicitly stdout
    console_handler.setFormatter(formatter)
    _app_logger.addHandler(console_handler)

    # Create and add file handler if log_file is provided
    if log_file:
        try:
            file_handler = logging.FileHandler(log_file, mode='a')
            file_handler.setFormatter(formatter)
            _app_logger.addHandler(file_handler)
            # This print is outside of the logging system, so it's fine.
            # It gives immediate feedback that file logging is attempted.
            print(f"Logging to file: {log_file}")
        except Exception as e:
            # Also print this to stderr directly, as logger might not be fully up.
            print(f"Warning: Could not set up logging to file {log_file}: {e}", file=sys.stderr)

    # Important: Prevent messages from this logger from propagating to the root logger.
    # The root logger might have default handlers (e.g., from a previous basicConfig call
    # by another library, or Python's default).
    _app_logger.propagate = False

    # DO NOT call logging.basicConfig(). We are manually configuring handlers
    # for our specific application logger (_app_logger).
    # logging.basicConfig() configures the root logger and can add handlers
    # that would lead to duplicate messages if _app_logger also propagates.

def get_logger() -> logging.Logger:
    """
    Get the configured shared application logger instance.

    Returns
    -------
    logging.Logger
        The configured logger instance.

    Raises
    ------
    RuntimeError
        If setup_logging has not been called before this function.
    """
    global _app_logger
    if _app_logger is None:
        # This state indicates an issue in the application's startup sequence.
        # setup_logging() in cli.py should always be called first.
        raise RuntimeError(
            "Logger not initialized. Call setup_logging() from the main application entry point first."
        )
    return _app_logger
