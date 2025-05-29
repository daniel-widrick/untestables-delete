"""
Generic Logging Functionality

This module provides a class for setting up and accessing a configured logger
with consistent formatting and support for both console and file output.
"""

import logging
import sys
from typing import Optional, Union # Union for log_level

class LoggingManager: # Renamed from GenericLogger
    """
    A manager class that can be instantiated to configure and retrieve loggers.
    """

    DEFAULT_LOG_FORMAT = "%(asctime)s | %(name)s | %(levelname)8s | %(message)s"
    DEFAULT_LOG_LEVEL = logging.INFO

    def __init__(self,
                 logger_name: str,
                 log_level: Union[int, str] = DEFAULT_LOG_LEVEL,
                 log_format: str = DEFAULT_LOG_FORMAT,
                 log_file: Optional[str] = None,
                 console_output: bool = True,
                 propagate: bool = False):
        """
        Initializes and configures a specific logger instance.

        Args:
            logger_name (str): The name for the logger to be configured.
            log_level (Union[int, str], optional): The logging level.
            log_format (str, optional): The format string for log messages.
            log_file (Optional[str], optional): Path to a file for log output.
            console_output (bool, optional): Whether to output logs to the console.
            propagate (bool, optional): Whether messages from the configured logger
                                     should be passed to ancestor loggers.
        """
        self.logger_name = logger_name # Name of the logger this instance configures
        self.log_level = log_level
        self.log_format_str = log_format
        self.log_file = log_file
        self.console_output = console_output
        self.propagate = propagate

        self._configured_logger = logging.getLogger(self.logger_name)
        self._configured_logger.setLevel(self.log_level)
        self._configured_logger.propagate = self.propagate

        # Clear existing handlers to prevent duplication if this logger name was used before
        # and is being reconfigured by a new LoggingManager instance.
        if self._configured_logger.hasHandlers():
            self._configured_logger.handlers.clear()

        self._formatter = logging.Formatter(self.log_format_str)
        self._configure_handlers()

    def _configure_handlers(self) -> None:
        """
        Configures and adds console and/or file handlers to the logger
        managed by this LoggingManager instance.
        """
        if self.console_output:
            console_handler = logging.StreamHandler(stream=sys.stdout)
            console_handler.setFormatter(self._formatter)
            self._configured_logger.addHandler(console_handler)

        if self.log_file:
            try:
                file_handler = logging.FileHandler(self.log_file, mode='a')
                file_handler.setFormatter(self._formatter)
                self._configured_logger.addHandler(file_handler)
                # This print remains for now, as it was in previous versions.
                # Consider routing this through the logger itself if appropriate.
                print(f"Logger '{self.logger_name}': Logging to file: {self.log_file}")
            except Exception as e:
                print(f"Warning: Logger '{self.logger_name}': Could not set up logging to file {self.log_file}: {e}", file=sys.stderr)

    def get_configured_logger(self) -> logging.Logger:
        """
        Returns the logger instance that this LoggingManager instance configured.
        """
        return self._configured_logger

    @staticmethod
    def get_logger(name: str) -> logging.Logger:
        """
        Retrieves a logger instance by its name.

        This static method allows other parts of the application to obtain logger
        instances without directly importing or using the standard `logging` module.
        It's expected that a primary logger (e.g., 'app') has been configured
        by an instance of LoggingManager, and child loggers (e.g., 'app.child')
        obtained via this method will propagate their messages to the primary logger's handlers.

        Args:
            name (str): The name of the logger to retrieve (e.g., "app.module").

        Returns:
            logging.Logger: The logger instance.
        """
        return logging.getLogger(name)

    def add_handler(self, handler: logging.Handler) -> None:
        """
        Adds a custom handler to the logger configured by this manager.
        The handler should have its formatter set if required.
        """
        self._configured_logger.addHandler(handler)

    def remove_handler(self, handler: logging.Handler) -> None:
        """
        Removes a specific handler from the logger configured by this manager.
        """
        self._configured_logger.removeHandler(handler)
