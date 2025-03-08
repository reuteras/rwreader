"""Main entry point for rwreader."""

import sys

from .ui.app import RWReader

# Create application instance
app = RWReader()

def main() -> None:
    """Run the rwreader app.
    
    Usage:
        rwreader
        rwreader --config path/to/config.toml
        rwreader --create-config path/to/config.toml
        rwreader --version
        rwreader --help
    """
    try:
        app.run()
    except KeyboardInterrupt:
        # Handle Ctrl+C gracefully
        print("\nExiting rwreader...")
    except Exception as e:
        print(f"Error: {e}")
        print("See rwreader.log for details")
        sys.exit(1)

if __name__ == "__main__":
    main()
