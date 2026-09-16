"""Application class for rwreader with single-window navigation."""

import logging
import sys
from pathlib import Path, PurePath
from typing import ClassVar

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Footer, Header

# Import our improved client
from ..client import ReadwiseClient, create_readwise_client
from ..config import Configuration
from ..index import DocumentIndex
from .screens.help import HelpScreen

logger: logging.Logger = logging.getLogger(name=__name__)


class RWReader(App[None]):
    """A Textual app for Readwise Reader with single-window navigation."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        # App controls (screens have their own specific bindings)
        ("?", "toggle_help", "Help"),
        ("d", "toggle_dark", "Toggle dark mode"),
        ("q", "quit", "Quit"),
    ]

    CSS_PATH: ClassVar[list[str | PurePath]] = ["styles.tcss"]

    def __init__(self) -> None:
        """Initialize the app and connect to Readwise API."""
        super().__init__()

        # Load the configuration
        self.configuration = Configuration(exec_args=sys.argv[1:])

        # Set theme based on configuration
        self.theme = (
            "textual-dark"
            if self.configuration.default_theme == "dark"
            else "textual-light"
        )

    async def on_ready(self) -> None:
        """Initialize the app and push the initial screen."""
        # Create API client
        self.client: ReadwiseClient = await create_readwise_client(
            token=self.configuration.token
        )

        # Attach the local metadata index if enabled and configured
        index_path = getattr(self.configuration, "index_path", None)
        if getattr(self.configuration, "index_enabled", False) is True and isinstance(
            index_path, str | PurePath
        ):
            try:
                self.client.index = DocumentIndex(Path(index_path))
            except Exception as e:
                logger.error(f"Could not open local index at {index_path}: {e}")

        # Load initial data into cache (non-blocking)
        try:
            # Pre-fetch inbox data to populate cache
            self.client.get_inbox(refresh=True, limit=20)
        except Exception as e:
            logger.error(f"Error pre-fetching inbox: {e}")

        # Push the category list screen as the initial screen
        from .screens.category_list import CategoryListScreen  # noqa: PLC0415

        self.push_screen(CategoryListScreen())

    def compose(self) -> ComposeResult:
        """Compose the single-window app (screens manage their own content)."""
        yield Header(show_clock=True)
        # Screens will be pushed onto this base layout
        yield Footer()

    def action_toggle_dark(self) -> None:
        """Toggle between dark and light theme."""
        self.theme = (
            "textual-dark" if self.theme == "textual-light" else "textual-light"
        )

    def action_toggle_help(self) -> None:
        """Show or hide the help screen."""
        if hasattr(self.screen, "id") and self.screen.id == "help":
            self.pop_screen()
        else:
            self.push_screen(screen=HelpScreen())

    def on_unmount(self) -> None:
        """Clean up resources when the app is closed."""
        if hasattr(self, "client"):
            self.client.close()
