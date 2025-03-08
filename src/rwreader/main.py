"""Main entry point for rwreader with sanitized logging."""

import logging
import sys
from pathlib import Path


def main() -> None:
    """Main entry point for rwreader."""
    # Create logs directory if it doesn't exist
    log_dir: Path = Path.home() / ".rwreader" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configure the log file path
    log_file: Path = log_dir / "rwreader.log"

    # Get logger
    logger: logging.Logger = logging.getLogger(name="rwreader.main")

    try:
        # Import the app here to ensure logging is configured first
        from .ui.app import RWReader

        # Log system info (safely)
        logger.info(msg="Starting rwreader")
        logger.info(msg=f"Python version: {sys.version}")

        # Create and run application instance
        app = RWReader()
        app.run()
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        logger.info(msg="Application terminated by user (Ctrl+C)")
        print("\nExiting rwreader...")
    except Exception as e:
        logger.exception(msg=f"Error: {e}")
        print(f"Error: {e}")
        print(f"See logs for details (at {log_file})")
        sys.exit(1)


if __name__ == "__main__":
    main()
