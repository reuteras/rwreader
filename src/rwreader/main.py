"""Main entry point for rwreader with sanitized logging."""

import sys
import logging
import os
from pathlib import Path

from .utils.logging import setup_sanitized_logging

def main() -> None:
    """Run the rwreader app with sanitized logging.
    
    Usage:
        rwreader
        rwreader --debug (enables debug logging)
        rwreader --help
    """
    # Check for debug flag
    debug = "--debug" in sys.argv
    
    # Create logs directory if it doesn't exist
    log_dir = Path.home() / ".rwreader" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure the log file path
    log_file = log_dir / "rwreader.log"
    
    # Set up sanitized logging first
    setup_sanitized_logging(debug=debug, log_file=str(log_file))
    
    # Get logger
    logger = logging.getLogger("rwreader.main")
    
    try:
        # Import the app here to ensure logging is configured first
        from .ui.app import RWReader
        
        # Log system info (safely)
        logger.info(f"Starting rwreader")
        logger.info(f"Python version: {sys.version}")
        
        # Create and run application instance
        app = RWReader()
        app.run()
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        logger.info("Application terminated by user (Ctrl+C)")
        print("\nExiting rwreader...")
    except Exception as e:
        logger.exception(f"Error: {e}")
        print(f"Error: {e}")
        print(f"See logs for details (at {log_file})")
        sys.exit(1)

if __name__ == "__main__":
    main()