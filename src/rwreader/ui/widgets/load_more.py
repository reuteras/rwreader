"""Load more widget for progressive loading."""

from textual.widgets import ListItem, Static


class LoadMoreWidget(Static):
    """Widget that displays a 'Load More' button in list views."""

    DEFAULT_CSS = """
    LoadMoreWidget {
        height: 3;
        width: 100%;
        content-align: center middle;
        background: $boost;
        color: $text;
        border-top: solid $primary;
        display: none;
    }
    
    LoadMoreWidget:focus-within {
        background: $accent;
        color: $text-accent;
    }
    """

    def __init__(self, **kwargs) -> None:
        """Initialize the widget."""
        super().__init__(content="", **kwargs)
        self.update_load_more()

    def update_load_more(self) -> None:
        """Update the load more button content."""
        ListItem(
            Static(content="Load More... (press SPACE)", markup=False),
            id="load_more_item",
        )
        self.update(content="Load More... (press SPACE)")

    def on_click(self) -> None:
        """Handle click events."""
        # Dispatch load_more action to the app
        if self.app:
            self.app.action_load_more()  # type: ignore
