"""Article list screen for a category."""

import logging
import webbrowser
from typing import TYPE_CHECKING, Any, ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, ListItem, ListView, Static

from ...utils.ui_helpers import safe_get_article_display_title, safe_set_text_style

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ArticleListScreen(Screen):
    """Screen showing articles in a category."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("j", "cursor_down", "Down", show=False),
        Binding("k", "cursor_up", "Up", show=False),
        Binding("enter", "select_article", "Read"),
        Binding("a", "archive_article", "Archive"),
        Binding("l", "later_article", "Later"),
        Binding("i", "inbox_article", "Inbox"),
        Binding("D", "delete_article", "Delete"),
        Binding("o", "open_browser", "Open in browser"),
        Binding("r", "refresh", "Refresh"),
        Binding("escape", "back", "Back"),
        Binding("backspace", "back", "Back", show=False),
        Binding("h", "help", "Help"),
        Binding("space", "load_more", "Load more"),
    ]

    def __init__(self, category: str, **kwargs: Any) -> None:
        """Initialize the article list screen.

        Args:
            category: Category name (inbox, later, feed, archive)
            **kwargs: Additional keyword arguments
        """
        super().__init__(**kwargs)
        self.category = category
        self.articles: list[dict[str, Any]] = []
        self.current_index = 0
        self.initial_page_size = 20

    def compose(self) -> ComposeResult:
        """Create the article list UI."""
        yield Header(show_clock=True)
        yield Static(f"{self.category.upper()}", id="category_title")
        yield ListView(id="article_list")
        yield Footer()

    async def on_mount(self) -> None:
        """Load articles when screen mounts."""
        self.load_articles()

    @work(exclusive=True)
    async def load_articles(self, load_more: bool = False) -> None:
        """Load articles from API.

        Args:
            load_more: If True, load more articles beyond initial page
        """
        if not hasattr(self.app, "client"):
            logger.error("No client available")
            self.notify("API client not initialized", severity="error")
            return

        try:
            # Show loading message
            if not load_more:
                self.notify(f"Loading {self.category} articles...", title="Loading")

            client = self.app.client  # type: ignore

            # Get articles for the selected category
            if self.category == "inbox":
                self.articles = client.get_inbox(
                    refresh=not load_more,
                    limit=self.initial_page_size if not load_more else None,
                )
            elif self.category == "feed":
                # Only show unread articles in feed
                all_feed = client.get_feed(
                    refresh=not load_more,
                    limit=self.initial_page_size if not load_more else None,
                )
                self.articles = [
                    article
                    for article in all_feed
                    if article.get("first_opened_at") == ""
                ]
            elif self.category == "later":
                self.articles = client.get_later(
                    refresh=not load_more,
                    limit=self.initial_page_size if not load_more else None,
                )
            elif self.category == "archive":
                self.articles = client.get_archive(
                    refresh=not load_more,
                    limit=self.initial_page_size if not load_more else None,
                )

            # Populate the list
            self.populate_list()

            if not load_more:
                self.notify(
                    f"Loaded {len(self.articles)} articles",
                    title=self.category.capitalize(),
                )

        except Exception as e:
            logger.error(f"Error loading articles: {e}")
            self.notify(f"Error loading articles: {e}", severity="error")

    def populate_list(self) -> None:
        """Populate ListView with articles."""
        list_view = self.query_one("#article_list", ListView)

        # Remove all existing items explicitly to avoid duplicate IDs
        for child in list(list_view.children):
            child.remove()

        list_view.clear()

        for article in self.articles:
            article_id = str(article.get("id"))
            display_title = safe_get_article_display_title(article=article)

            # Create list item
            list_item = ListItem(
                Static(display_title, markup=False), id=f"art_{article_id}"
            )

            # Style based on read status
            is_read = article.get("read", False) or article.get("state") == "finished"
            safe_set_text_style(item=list_item, style="none" if is_read else "bold")

            list_view.append(list_item)

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
        # Get the index of the selected item
        list_view = self.query_one(ListView)
        if list_view.index is not None:
            self.current_index = list_view.index
            if 0 <= self.current_index < len(self.articles):
                article = self.articles[self.current_index]

                # Import ArticleReaderScreen
                from .article_reader import ArticleReaderScreen  # noqa: PLC0415

                # Pass article, article_list, and current_index
                # This enables J/K navigation in reader
                self.app.push_screen(
                    ArticleReaderScreen(
                        article=article,
                        article_list=self.articles,
                        current_index=self.current_index,
                        category=self.category,
                    )
                )

    async def action_select_article(self) -> None:
        """Select article and push reader screen (fallback)."""
        list_view = self.query_one(ListView)
        if list_view.highlighted_child and list_view.index is not None:
            # Get highlighted index
            self.current_index = list_view.index
            if 0 <= self.current_index < len(self.articles):
                article = self.articles[self.current_index]

                # Import ArticleReaderScreen
                from .article_reader import ArticleReaderScreen  # noqa: PLC0415

                # Pass article, article_list, and current_index
                # This enables J/K navigation in reader
                self.app.push_screen(
                    ArticleReaderScreen(
                        article=article,
                        article_list=self.articles,
                        current_index=self.current_index,
                        category=self.category,
                    )
                )

    async def action_archive_article(self) -> None:
        """Archive the highlighted article."""
        await self._move_article("archive")

    async def action_later_article(self) -> None:
        """Move article to Later."""
        await self._move_article("later")

    async def action_inbox_article(self) -> None:
        """Move article to Inbox."""
        await self._move_article("inbox")

    async def _move_article(self, destination: str) -> None:
        """Move the highlighted article to a destination.

        Args:
            destination: Target location (inbox, later, archive)
        """
        list_view = self.query_one(ListView)
        if not list_view.highlighted_child or list_view.index is None:
            self.notify("No article selected", severity="warning")
            return

        index = list_view.index
        if not (0 <= index < len(self.articles)):
            return

        article = self.articles[index]
        article_id = str(article.get("id"))

        if not hasattr(self.app, "client"):
            self.notify("API client not available", severity="error")
            return

        try:
            client = self.app.client  # type: ignore

            # Move article based on destination
            if destination == "archive":
                success = client.move_to_archive(article_id=article_id)
            elif destination == "later":
                success = client.move_to_later(article_id=article_id)
            elif destination == "inbox":
                success = client.move_to_inbox(article_id=article_id)
            else:
                success = False

            if success:
                self.notify(f"Moved to {destination.capitalize()}", title="Success")
                # Remove from current list if we're not viewing the destination category
                if self.category != destination:
                    self.articles.pop(index)
                    self.populate_list()
            else:
                self.notify(f"Failed to move to {destination}", severity="error")

        except Exception as e:
            logger.error(f"Error moving article: {e}")
            self.notify(f"Error: {e}", severity="error")

    @work
    async def action_delete_article(self) -> None:
        """Delete article (with confirmation)."""
        list_view = self.query_one(ListView)
        if not list_view.highlighted_child or list_view.index is None:
            self.notify("No article selected", severity="warning")
            return

        index = list_view.index
        if not (0 <= index < len(self.articles)):
            return

        article = self.articles[index]
        article_id = str(article.get("id"))
        article_title = article.get("title", "Unknown article")

        # Push confirmation dialog
        from .confirm import DeleteArticleScreen  # noqa: PLC0415

        result = await self.app.push_screen_wait(
            DeleteArticleScreen(article_id=article_id, article_title=article_title)
        )

        # Check if confirmed
        if result and result.get("confirmed"):
            try:
                if hasattr(self.app, "client"):
                    client = self.app.client  # type: ignore
                    client.delete_article(article_id=article_id)
                    self.notify("Article deleted", title="Success")
                    # Remove from list
                    self.articles.pop(index)
                    self.populate_list()
            except Exception as e:
                logger.error(f"Error deleting article: {e}")
                self.notify(f"Error: {e}", severity="error")

    async def action_open_browser(self) -> None:
        """Open the highlighted article in browser."""
        list_view = self.query_one(ListView)
        if not list_view.highlighted_child or list_view.index is None:
            self.notify("No article selected", severity="warning")
            return

        index = list_view.index
        if not (0 <= index < len(self.articles)):
            return

        article = self.articles[index]
        url = article.get("url")

        if url:
            try:
                webbrowser.open(url)
                self.notify("Opening in browser", title="Browser")
            except Exception as e:
                logger.error(f"Error opening browser: {e}")
                self.notify(f"Error: {e}", severity="error")
        else:
            self.notify("No URL available", severity="warning")

    def action_refresh(self) -> None:
        """Refresh articles."""
        if hasattr(self.app, "client"):
            self.app.client.clear_cache()  # type: ignore
        self.load_articles(load_more=False)
        self.notify("Articles refreshed", title="Refresh")

    def action_load_more(self) -> None:
        """Load more articles."""
        self.load_articles(load_more=True)

    def action_back(self) -> None:
        """Go back to category list."""
        self.app.pop_screen()

    def action_help(self) -> None:
        """Show help screen."""
        from .help import HelpScreen  # noqa: PLC0415

        self.app.push_screen(HelpScreen())
