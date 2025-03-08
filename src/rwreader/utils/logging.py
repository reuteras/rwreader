"""Custom logging handler that sanitizes log records."""

import logging
import traceback
from typing import List, Dict, Optional

from .sanitize import sanitize_log_message

class SanitizingFormatter(logging.Formatter):
    """A formatter that sanitizes log messages to remove sensitive information."""
    
    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None, style: str = '%') -> None:
        """Initialize the formatter.
        
        Args:
            fmt: Format string
            datefmt: Date format string
            style: Style of format string
        """
        super().__init__(fmt=fmt, datefmt=datefmt, style=style)
    
    def format(self, record: logging.LogRecord) -> str:
        """Format the log record, sanitizing the message.
        
        Args:
            record: The log record to format
            
        Returns:
            Formatted and sanitized log message
        """
        # Make a copy of the record to avoid modifying the original
        sanitized_record = logging.makeLogRecord(record.__dict__)
        
        # Sanitize the message
        if hasattr(record, 'msg') and record.msg:
            sanitized_record.msg = sanitize_log_message(record.msg)
        
        # Sanitize the args if present
        if hasattr(record, 'args') and record.args:
            if isinstance(record.args, (tuple, list)):
                sanitized_args = []
                for arg in record.args:
                    sanitized_args.append(sanitize_log_message(arg))
                sanitized_record.args = tuple(sanitized_args)
            elif isinstance(record.args, dict):
                sanitized_args = {}
                for key, value in record.args.items():
                    sanitized_args[key] = sanitize_log_message(value)
                sanitized_record.args = sanitized_args
        
        # Call the parent format method with the sanitized record
        return super().format(sanitized_record)

class SanitizingFileHandler(logging.FileHandler):
    """A file handler that sanitizes log records."""
    
    def __init__(self, filename: str, mode: str = 'a', encoding: Optional[str] = None, 
                 delay: bool = False, errors: Optional[str] = None) -> None:
        """Initialize the handler with a sanitizing formatter.
        
        Args:
            filename: Path to the log file
            mode: File open mode
            encoding: File encoding
            delay: Whether to delay opening the file
            errors: What to do with encoding errors
        """
        super().__init__(filename, mode=mode, encoding=encoding, delay=delay, errors=errors)
        
        # Set a sanitizing formatter
        formatter = SanitizingFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.setFormatter(formatter)


def setup_sanitized_logging(debug: bool = False, log_file: str = "rwreader.log") -> None:
    """Set up logging with sanitization.
    
    Args:
        debug: Whether to enable debug logging
        log_file: Path to the log file
    """
    # Remove all existing handlers
    root_logger = logging.getLogger()
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Set the level
    log_level = logging.DEBUG if debug else logging.INFO
    root_logger.setLevel(log_level)
    
    # Create and add the sanitizing file handler
    file_handler = SanitizingFileHandler(log_file)
    file_handler.setLevel(log_level)
    root_logger.addHandler(file_handler)
    
    # Create and add a sanitizing stream handler
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(SanitizingFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    ))
    stream_handler.setLevel(log_level)
    root_logger.addHandler(stream_handler)
    
    # Log that logging is set up
    logging.info(f"Sanitized logging initialized at level: {logging.getLevelName(log_level)}")
    logging.info(f"Log file: {log_file}")