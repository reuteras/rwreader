"""Category list screen for Readwise Reader."""

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, ListItem, ListView, Static

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class CategoryListScreen(Screen):
    """Screen showing all article categories."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_category", "Select"),
        Binding("r", "refresh", "Refresh"),
        Binding("h", "help", "Help"),
        Binding("d", "toggle_dark", "Toggle dark mode"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the category list screen.

        Args:
            **kwargs: Additional keyword arguments
        """
        super().__init__(**kwargs)
        self.categories: dict[str, int] = {}

    def compose(self) -> ComposeResult:
        """Create the category list UI."""
        yield Header(show_clock=True)
        with VerticalScroll():
            yield Static("READWISE READER", id="title")
            yield Static("Select a category to browse articles", id="subtitle")
            yield ListView(id="category_list")
        yield Footer()

    async def on_mount(self) -> None:
        """Load categories when screen mounts."""
        self.load_categories()

    @work(exclusive=True)
    async def load_categories(self) -> None:
        """Load category counts from API."""
        # Get API client from app
        if not hasattr(self.app, "client"):
            logger.error("No client available")
            self.notify("API client not initialized", severity="error")
            return

        try:
            # Show loading message
            self.notify("Loading categories...", title="Loading")

            # Get counts for each category using the client's cache
            client = self.app.client  # type: ignore

            # Get cached data to determine counts
            inbox_data = client._category_cache.get("inbox", {}).get("data", [])
            feed_data = client._category_cache.get("feed", {}).get("data", [])
            later_data = client._category_cache.get("later", {}).get("data", [])

            # Calculate counts
            inbox_count = len(inbox_data) if inbox_data else 0
            # For feed, only count unread articles
            feed_count = (
                len([a for a in feed_data if a.get("first_opened_at") == ""])
                if feed_data
                else 0
            )
            later_count = len(later_data) if later_data else 0

            self.categories = {
                "inbox": inbox_count,
                "feed": feed_count,
                "later": later_count,
                "archive": -1,  # Archive doesn't show count
            }

            # Populate the list
            self.populate_list()

        except Exception as e:
            logger.error(f"Error loading categories: {e}")
            self.notify(f"Error loading categories: {e}", severity="error")

    def populate_list(self) -> None:
        """Populate the ListView with categories."""
        list_view = self.query_one("#category_list", ListView)
        list_view.clear()

        # Category icons and names
        categories = [
            ("inbox", "📥", "Inbox"),
            ("later", "⏰", "Later"),
            ("feed", "📰", "Feed"),
            ("archive", "📦", "Archive"),
        ]

        for category_id, icon, name in categories:
            count = self.categories.get(category_id, 0)
            if count >= 0:
                display_text = f"{icon} {name} ({count})"
            else:
                display_text = f"{icon} {name}"

            item = ListItem(Static(display_text, markup=False), id=f"cat_{category_id}")
            item.data = {"category": category_id}  # type: ignore
            list_view.append(item)

        # Focus the list and select first item
        list_view.focus()
        if len(list_view.children) > 0:
            list_view.index = 0

    def action_cursor_down(self) -> None:
        """Move cursor down."""
        list_view = self.query_one(ListView)
        list_view.action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move cursor up."""
        list_view = self.query_one(ListView)
        list_view.action_cursor_up()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle ListView item selection (Enter key)."""
        # Get the selected item's data
        if event.item and hasattr(event.item, "data") and event.item.data:
            category = event.item.data.get("category")  # type: ignore
            if category:
                # Import and push ArticleListScreen
                from .article_list import ArticleListScreen  # noqa: PLC0415

                self.app.push_screen(ArticleListScreen(category=category))

    async def action_select_category(self) -> None:
        """Select category and push article list screen (fallback)."""
        list_view = self.query_one(ListView)
        if list_view.highlighted_child:
            # Extract category name from ListItem data
            if (
                hasattr(list_view.highlighted_child, "data")
                and list_view.highlighted_child.data
            ):
                category = list_view.highlighted_child.data.get("category")  # type: ignore
                if category:
                    # Import and push ArticleListScreen
                    from .article_list import ArticleListScreen  # noqa: PLC0415

                    self.app.push_screen(ArticleListScreen(category=category))

    def action_refresh(self) -> None:
        """Refresh category counts."""
        # Clear the client cache
        if hasattr(self.app, "client"):
            self.app.client.clear_cache()  # type: ignore
        self.load_categories()
        self.notify("Categories refreshed", title="Refresh")

    def action_help(self) -> None:
        """Show help screen."""
        from .help import HelpScreen  # noqa: PLC0415

        self.app.push_screen(HelpScreen())

    def action_toggle_dark(self) -> None:
        """Toggle dark mode."""
        self.app.theme = (
            "textual-dark" if self.app.theme == "textual-light" else "textual-light"
        )

    def action_quit(self) -> None:
        """Quit the application."""
        self.app.exit()
