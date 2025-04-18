"""Search screen for rwreader."""

import logging
from collections.abc import Callable

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label

logger: logging.Logger = logging.getLogger(name=__name__)


class SearchScreen(ModalScreen[str]):
    """A modal screen for searching text within articles."""

    DEFAULT_CSS = """
    SearchScreen {
        align: center middle;
    }

    #search-container {
        width: 60%;
        height: auto;
        background: $surface;
        border: solid $primary;
        padding: 1 2;
    }

    #search-title {
        content-align: center middle;
        width: 100%;
        text-style: bold;
        padding-bottom: 1;
    }

    #search-input {
        width: 100%;
        margin-bottom: 1;
    }

    #button-container {
        width: 100%;
        height: 3;
        align: center middle;
    }

    Button {
        margin: 0 1;
    }
    """

    def __init__(
        self,
        search_callback: Callable[[str], None] | None = None,
        initial_query: str = "",
        name: str | None = None,
    ) -> None:
        """Initialize the search screen.

        Args:
            search_callback: Function to call with search query (optional)
            initial_query: Initial text to populate the search field with
            name: Optional name for the screen
        """
        super().__init__(name=name)
        self.search_callback = search_callback
        self.initial_query = initial_query

    def compose(self) -> ComposeResult:
        """Compose the search screen content."""
        with Horizontal(id="search-container"):
            yield Label("Search in Article", id="search-title")
            yield Input(placeholder="Enter search text...", id="search-input")
            with Horizontal(id="button-container"):
                yield Button("Search", variant="primary", id="search-button")
                yield Button("Cancel", variant="error", id="cancel-button")

    def on_mount(self) -> None:
        """Set initial query and focus the search input when the screen is mounted."""
        search_input = self.query_one("#search-input", Input)

        # Set the initial value if provided
        if hasattr(self, "initial_query") and self.initial_query:
            search_input.value = self.initial_query
            # Position cursor at the end of the text
            search_input.cursor_position = len(self.initial_query)

        # Focus the input field
        search_input.focus()

    def on_input_submitted(self, event) -> None:
        """Handle the input submission event."""
        # Explicitly use the value from the event
        search_input = self.query_one("#search-input", Input)
        query = search_input.value.strip()

        # Force dismiss the screen with the query
        if query:
            self.dismiss(query)
        else:
            self.dismiss(None)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button press events.

        Args:
            event: The button pressed event
        """
        if event.button.id == "search-button":
            self.submit_search()
        elif event.button.id == "cancel-button":
            self.dismiss(None)

    def submit_search(self) -> None:
        """Submit the search query."""
        search_input = self.query_one("#search-input", Input)
        query = search_input.value.strip()
        if query:
            # Return the query to the caller
            self.dismiss(query)
        else:
            # If empty, just close without searching
            self.dismiss(None)
