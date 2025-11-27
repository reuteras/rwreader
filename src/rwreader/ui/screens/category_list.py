"""Category list screen for Readwise Reader."""

import logging
from typing import TYPE_CHECKING, Any, ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
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
        yield Static("Select a category to browse articles", id="title")
        yield ListView(id="category_list")
        yield Footer()

    async def on_mount(self) -> None:
        """Load categories when screen mounts."""
        self.load_categories()

    async def on_resume(self) -> None:
        """Refresh category counts when screen resumes."""
        logger.debug("CategoryListScreen resumed, refreshing counts")
        # Reload categories to reflect any changes made in other screens
        self.load_categories(refresh=True)

    @work(exclusive=True)
    async def load_categories(self, refresh: bool = False) -> None:
        """Load category counts from API.

        Args:
            refresh: Whether to force refresh from API (default: False)
        """
        # Get API client from app
        if not hasattr(self.app, "client"):
            logger.error("No client available")
            self.notify("API client not initialized", severity="error")
            return

        try:
            logger.debug(f"load_categories called with refresh={refresh}")

            # Get counts for each category using the client's methods
            client = self.app.client  # type: ignore

            # Fetch data from API (or cache if not refreshing)
            # Use refresh=True to force API call, otherwise use cache if available
            logger.debug("Fetching inbox data...")
            inbox_data = client.get_inbox(refresh=refresh)
            logger.debug(f"Got {len(inbox_data)} inbox items")

            logger.debug("Fetching feed data...")
            feed_data = client.get_feed(refresh=refresh)
            logger.debug(f"Got {len(feed_data)} feed items")

            logger.debug("Fetching later data...")
            later_data = client.get_later(refresh=refresh)
            logger.debug(f"Got {len(later_data)} later items")

            # Calculate counts
            inbox_count = len(inbox_data) if inbox_data else 0
            # For feed, only count unread articles
            feed_count = (
                len([a for a in feed_data if a.get("first_opened_at") == ""])
                if feed_data
                else 0
            )
            later_count = len(later_data) if later_data else 0

            logger.debug(
                f"Calculated counts: inbox={inbox_count}, feed={feed_count}, later={later_count}"
            )

            self.categories = {
                "inbox": inbox_count,
                "feed": feed_count,
                "later": later_count,
                "archive": -1,  # Archive doesn't show count
            }

            # Populate the list
            logger.debug("Populating list...")
            self.populate_list()
            logger.debug("List populated successfully")

            self.notify("Categories loaded", title="Success")

        except Exception as e:
            logger.error(f"Error loading categories: {e}", exc_info=True)
            self.notify(f"Error loading categories: {e}", severity="error")

    def populate_list(self) -> None:
        """Populate the ListView with categories."""
        try:
            logger.debug("populate_list called")
            list_view = self.query_one("#category_list", ListView)

            # Remove all existing items explicitly to avoid duplicate IDs
            existing_count = len(list(list_view.children))
            logger.debug(f"Removing {existing_count} existing items")
            for child in list(list_view.children):
                child.remove()

            list_view.clear()
            logger.debug("ListView cleared")

            # Category icons and names
            categories = [
                ("inbox", "📥", "Inbox"),
                ("later", "⏰", "Later"),
                ("feed", "📰", "Feed"),
                ("archive", "📦", "Archive"),
            ]

            logger.debug(f"Adding categories with counts: {self.categories}")
            for category_id, icon, name in categories:
                count = self.categories.get(category_id, 0)
                if count >= 0:
                    display_text = f"{icon} {name} ({count})"
                else:
                    display_text = f"{icon} {name}"

                logger.debug(f"Creating item for {category_id}: {display_text}")
                # Don't set explicit ID - let Textual auto-generate to avoid duplicate ID issues
                item = ListItem(Static(display_text, markup=False))
                item.data = {"category": category_id}  # type: ignore
                list_view.append(item)
                logger.debug(f"Appended item {category_id}")

            # Focus the list and select first item
            list_view.focus()
            if len(list_view.children) > 0:
                list_view.index = 0
            logger.debug(f"List populated with {len(list_view.children)} items")

        except Exception as e:
            logger.error(f"Error in populate_list: {e}", exc_info=True)
            raise

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
        logger.info("action_refresh called")

        # Clear the list view immediately to show refresh is happening
        list_view = self.query_one("#category_list", ListView)
        logger.debug(f"Clearing {len(list(list_view.children))} items from view")
        for child in list(list_view.children):
            child.remove()
        list_view.clear()
        logger.debug("ListView cleared in action_refresh")

        # Clear the client cache and reload (same pattern as article_list)
        if hasattr(self.app, "client"):
            logger.debug("Clearing client cache")
            self.app.client.clear_cache()  # type: ignore

        # Load fresh data from API
        logger.debug("Calling load_categories with refresh=True")
        self.load_categories(refresh=True)
        self.notify("Refreshing categories...", title="Refresh")
        logger.debug("action_refresh completed")

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
