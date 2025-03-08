"""Configuration module for rwreader."""

import argparse
import logging
import os
import subprocess
import sys
from importlib import metadata
from pathlib import Path
from typing import Any, Dict, Optional

import toml

logger: logging.Logger = logging.getLogger(name=__name__)

# Default configuration content
DEFAULT_CONFIG = """[general]
# Size of the cache for storing article metadata
cache_size = 10000
# Default theme (dark or light)
default_theme = "dark"
# Whether to automatically mark articles as read when opened
auto_mark_read = true

[readwise]
# Readwise API token - can use op command for 1Password integration
token = "your_readwise_token"  # Or use 1Password CLI integration

[display]
# Display settings
font_size = "medium"  # small, medium, large
reading_width = 80    # characters
"""

def get_conf_value(op_command: str) -> str:
    """Get the configuration value from 1Password if config starts with 'op '.

    Args:
        op_command: Configuration value or 1Password command

    Returns:
        The configuration value or the output of the 1Password command

    Raises:
        SystemExit: If the 1Password command fails
    """
    if op_command.startswith("op "):
        try:
            result: subprocess.CompletedProcess[str] = subprocess.run(
                args=op_command.split(), capture_output=True, text=True, check=True
            )
            return result.stdout.strip()
        except subprocess.CalledProcessError as err:
            logger.error(f"Error executing command '{op_command}': {err}")
            print(f"Error executing command '{op_command}': {err}")
            sys.exit(1)
        except FileNotFoundError:
            logger.error(
                "Error: 'op' command not found. Ensure 1Password CLI is installed and accessible."
            )
            print(
                "Error: 'op' command not found. Ensure 1Password CLI is installed and accessible."
            )
            sys.exit(1)
    else:
        return op_command


class Configuration:
    """A class to handle configuration values."""

    def __init__(self, arguments: Optional[list] = None) -> None:
        """Initialize the configuration.

        Args:
            arguments: Command line arguments
        """
        if arguments is None:
            arguments = sys.argv[1:]
            
        # Use argparse to add arguments
        arg_parser = argparse.ArgumentParser(
            description="A Textual app to read and manage your Readwise Reader library."
        )
        config_file_location: Path = Path.home() / ".rwreader.toml"
        arg_parser.add_argument(
            "--config",
            dest="config",
            help="Path to the config file",
            default=config_file_location,
        )
        arg_parser.add_argument(
            "--create-config",
            dest="create_config",
            help="Create a default configuration file at the specified path",
            metavar="PATH",
        )
        arg_parser.add_argument(
            "--version",
            action="store_true",
            dest="version",
            help="Show version and exit",
            default=False,
        )
        arg_parser.add_argument(
            "--debug",
            action="store_true",
            dest="debug",
            help="Enable debug logging",
            default=False,
        )
        arg_parser.add_argument(
            "--info",
            action="store_true",
            dest="info",
            help="Enable info logging",
            default=False,
        )
        arg_parser.add_argument(
            "--log-file",
            dest="rwreader_log",
            help="Path to the log file",
            default="rwreader.log",
        )
        args: argparse.Namespace = arg_parser.parse_args(args=arguments)

        if not args.debug and not args.info:
            args.rwreader_log = "/dev/null"

        # Set up logging
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[
                logging.FileHandler(filename=args.rwreader_log),
            ],
        )
        logger: logging.Logger = logging.getLogger(name=__name__)

        if args.debug:
            logger.setLevel(level=logging.DEBUG)
            logger.debug("Debug log enabled")

        if args.info:
            logger.setLevel(level=logging.INFO)
            logger.info("Info log enabled")

        # Handle version argument
        if args.version:
            try:
                version: str = metadata.version(distribution_name="rwreader")
                print(f"rwreader version: {version}")
                sys.exit(0)
            except Exception as e:
                print(f"Error getting version: {e}")
                sys.exit(1)

        # Handle create-config argument
        if args.create_config:
            self.create_default_config(config_path=args.create_config)
            print(f"Created default configuration at: {args.create_config}")
            print("Please edit this file with your settings before running rwreader.")
            sys.exit(0)

        # Load the configuration file
        self.config: Dict[str, Any] = self.load_config_file(config_file=args.config)

        try:
            # Get Readwise token
            self.token: str = get_conf_value(
                op_command=self.config["readwise"].get("token", "")
            )

            # Get general settings with defaults
            general_config = self.config.get("general", {})
            self.cache_size: int = general_config.get("cache_size", 10000)
            self.default_theme: str = general_config.get("default_theme", "dark")
            self.auto_mark_read: bool = general_config.get("auto_mark_read", True)

            # Get display settings
            display_config = self.config.get("display", {})
            self.font_size: str = display_config.get("font_size", "medium")
            self.reading_width: int = display_config.get("reading_width", 80)

            # Get version
            try:
                self.version: str = metadata.version(distribution_name="rwreader")
            except Exception:
                self.version = "0.1.0"  # Default version if not installed
                
        except KeyError as err:
            logger.error(f"Error reading configuration: {err}")
            print(f"Error reading configuration: {err}")
            sys.exit(1)

    def load_config_file(self, config_file: str) -> Dict[str, Any]:
        """Load the configuration from the TOML file.

        Args:
            config_file: Path to the config file

        Returns:
            Configuration dictionary
        """
        config_path = Path(config_file)

        try:
            if not config_path.exists():
                # If config file doesn't exist, create it from the default config
                print(f"Config file {config_file} not found. Creating with default settings.")
                config_path.write_text(data=DEFAULT_CONFIG)
                print(f"Created {config_file} with default settings. Please edit it with your settings.")
                sys.exit(1)

            return toml.loads(s=config_path.read_text())
        except (FileNotFoundError, toml.TomlDecodeError) as err:
            logger.error(f"Error reading configuration file: {err}")
            print(f"Error reading configuration file: {err}")
            sys.exit(1)

    def create_default_config(self, config_path: str) -> None:
        """Create a default configuration file at the specified path.

        Args:
            config_path: Path where the configuration file should be created
        """
        path = Path(config_path)

        # Create parent directories if they don't exist
        if not path.parent.exists():
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Error creating directory for config file: {e}")
                print(f"Error creating directory for config file: {e}")
                sys.exit(1)

        # Write the default configuration
        try:
            path.write_text(data=DEFAULT_CONFIG)
        except Exception as e:
            logger.error(f"Error writing configuration file: {e}")
            print(f"Error writing configuration file: {e}")
            sys.exit(1)
