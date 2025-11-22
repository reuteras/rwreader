"""Application class for rwreader with progressive loading."""

import asyncio
import logging
import re
import sys
import webbrowser
from pathlib import PurePath
from typing import Any, ClassVar, Final, Literal

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widget import Widget
from textual.widgets import (
    Footer,
    Header,
    ListItem,
    ListView,
    LoadingIndicator,
    Static,
)

# Import our improved client
from ..client import ReadwiseClient, create_readwise_client
from ..config import Configuration
from ..utils.ui_helpers import (
    format_article_content,
    safe_get_article_display_title,
    safe_set_text_style,
)
from .screens.confirm import DeleteArticleScreen
from .screens.fullscreen import FullScreenMarkdown
from .screens.help import HelpScreen
from .screens.link_screens import LinkSelectionScreen
from .widgets.api_status import APIStatusWidget
from .widgets.linkable_markdown_viewer import LinkableMarkdownViewer
from .widgets.load_more import LoadMoreWidget

logger: logging.Logger = logging.getLogger(name=__name__)


class RWReader(App[None]):
    """A Textual app for Readwise Reader with progressive loading."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        # Navigation
        ("j", "next_item", "Next item"),
        ("k", "previous_item", "Previous item"),
        ("J", "next_category", "Next category"),
        ("K", "previous_category", "Previous category"),
        ("tab", "focus_next_pane", "Next pane"),
        ("shift+tab", "focus_previous_pane", "Previous pane"),
        # Direct navigation to categories
        ("F", "goto_feed", "Go to Feed"),
        ("I", "goto_inbox", "Go to Inbox"),
        ("L", "goto_later", "Go to Later"),
        ("A", "goto_archive", "Go to Archive"),
        # Article actions
        ("a", "move_to_archive", "Move to Archive"),
        ("l", "move_to_later", "Move to Later"),
        ("i", "move_to_inbox", "Move to Inbox"),
        ("o", "open_in_browser", "Open in browser"),
        ("m", "show_metadata", "Show metadata"),
        ("M", "maximize_content", "Maximize content"),
        ("D", "delete_article", "Delete article"),
        # Link actions
        ("ctrl+o", "open_links", "Open article links"),
        ("ctrl+s", "save_link", "Save article link"),
        ("ctrl+l", "readwise_link", "Add link to Readwise"),
        ("ctrl+shift+l", "readwise_link_and_open", "Add link to Readwise and open"),
        # App controls
        ("?", "toggle_help", "Help"),
        ("h", "toggle_help", "Help"),
        ("d", "toggle_dark", "Toggle dark mode"),
        ("c", "clear", "Clear"),
        ("G", "refresh", "Refresh"),
        ("comma", "refresh", "Refresh"),
        ("q", "quit", "Quit"),
        # Loading more items
        ("space", "load_more", "Load more items"),
        # Testing background updates
        ("ctrl+u", "test_background_update", "Test background update"),
        ("ctrl+r", "refresh_counts", "Refresh all counts"),
    ]

    SCREENS: ClassVar[dict[str, type[Screen]]] = {
        "delete_article": DeleteArticleScreen,
        "maximize_content": FullScreenMarkdown,
        "help": HelpScreen,
        "open_links": LinkSelectionScreen,
    }

    CSS_PATH: Final[list[str | PurePath]] = ["styles.tcss"]

    # Reactive state attributes - automatically trigger UI updates when changed
    current_article_id: reactive[str | None] = reactive(None)
    current_category: reactive[str] = reactive("inbox")
    is_loading: reactive[bool] = reactive(False)

    def __init__(self) -> None:
        """Initialize the app and connect to Readwise API."""
        super().__init__()  # Initialize first for early access to notify/etc.

        # Load the configuration
        self.configuration = Configuration(exec_args=sys.argv[1:])

        # Set theme based on configuration
        self.theme = (
            "textual-dark"
            if self.configuration.default_theme == "dark"
            else "textual-light"
        )

        # Non-reactive state variables
        self.current_article: dict[str, Any] | None = None
        self.content_markdown: str = (
            "# Welcome to Readwise Reader TUI\n\nSelect an article to read."
        )

        # Progressive loading state
        self.initial_page_size: int = 20  # Number of items to load initially
        self.items_loaded: dict[str, int] = {
            "feed": 0,
            "inbox": 0,
            "later": 0,
            "archive": 0,
        }

        # Background count tracking
        self.background_counts: dict[str, int] = {
            "feed": 0,
            "later": 0,
        }
        self.background_update_interval: int = 300  # 5 minutes in seconds

    def watch_current_category(self, new_category: str) -> None:
        """Called automatically when current_category changes.

        Args:
            new_category: The new category value
        """
        logger.debug(f"Category changed to: {new_category}")
        # UI updates can happen here automatically when category changes

    def watch_current_article_id(self, new_article_id: str | None) -> None:
        """Called automatically when current_article_id changes.

        Args:
            new_article_id: The new article ID value
        """
        logger.debug(f"Article ID changed to: {new_article_id}")
        # Article display logic can be triggered here automatically

    def watch_is_loading(self, is_loading: bool) -> None:
        """Called automatically when is_loading changes.

        Args:
            is_loading: The new loading state
        """
        logger.debug(f"Loading state changed to: {is_loading}")
        # Update loading indicators automatically
        try:
            loading_indicator: LoadingIndicator = self.query_one(
                selector="#loading_indicator", expect_type=LoadingIndicator
            )
            loading_indicator.display = is_loading
        except Exception:
            # Widget may not be mounted yet
            pass

    async def on_ready(self) -> None:
        """Connect to the Readwise API and load initial data."""
        """Load library data when the app is mounted."""
        # Set up navigation list
        nav_list: ListView = self.query_one(
            selector="#navigation", expect_type=ListView
        )

        # Add header - disable markup
        nav_list.append(
            item=ListItem(Static(content="LIBRARY", markup=False), id="nav_header")
        )

        # Add category items with data attributes - disable markup
        inbox_item = ListItem(
            Static(content="→ Inbox (...)", markup=False), id="nav_inbox"
        )
        inbox_item.data = {"category": "inbox"}  # type: ignore

        later_item = ListItem(
            Static(content="→ Later (...)", markup=False), id="nav_later"
        )
        later_item.data = {"category": "later"}  # type: ignore

        archive_item = ListItem(
            Static(content="→ Archive", markup=False), id="nav_archive"
        )
        archive_item.data = {"category": "archive"}  # type: ignore

        feed_item = ListItem(Static(content="Feed (...)", markup=False), id="nav_feed")
        feed_item.data = {"category": "feed"}  # type: ignore

        # Add items to the list
        nav_list.append(item=inbox_item)
        nav_list.append(item=later_item)
        nav_list.append(item=archive_item)
        nav_list.append(item=feed_item)

        # Hide loading indicator initially
        loading_indicator: LoadingIndicator = self.query_one(
            selector="#loading_indicator", expect_type=LoadingIndicator
        )
        loading_indicator.display = False

        # Hide load more button initially
        load_more: LoadMoreWidget = self.query_one(
            selector="#load_more", expect_type=LoadMoreWidget
        )
        load_more.display = False

        # Focus on the navigation list
        nav_list.focus()

        self.client: ReadwiseClient = await create_readwise_client(
            token=self.configuration.token
        )

        # Highlight the Inbox item by default
        await self._select_nav_item(item_id="nav_inbox")

        # Load initial articles
        await self.load_category(category="inbox", initial_load=True)

        # Update navigation counts after initial load
        logger.debug(
            f"Before navigation count update - items_loaded: {self.items_loaded}"
        )

        # Debug cache state
        if hasattr(self, "client") and self.client:
            for cat in ["inbox", "feed", "later", "archive"]:
                cache_info = self.client._category_cache.get(cat, {})
                logger.debug(
                    f"Cache for {cat}: last_updated={cache_info.get('last_updated', 0)}, data_len={len(cache_info.get('data', []))}"
                )

        await self.update_navigation_counts()

        # Start background count updates and do an immediate update
        self.start_background_count_updates()

        # Trigger an immediate background count update for feed and later
        logger.debug("Triggering immediate background count update on startup")
        self.update_background_counts()

    def compose(self) -> ComposeResult:
        """Compose the three-pane layout with progressive loading support."""
        yield Header(show_clock=True)
        with Horizontal():
            yield ListView(id="navigation")
            with Vertical():
                with Vertical(id="articles_container"):
                    yield ListView(id="articles")
                    yield LoadMoreWidget(id="load_more")
                    yield LoadingIndicator(id="loading_indicator")
                yield LinkableMarkdownViewer(
                    markdown=self.content_markdown,
                    id="content",
                    show_table_of_contents=False,
                    open_links=False,
                )
        yield APIStatusWidget(name="api_status")
        yield Footer()

    async def _select_nav_item(self, item_id: str) -> None:
        """Select a navigation item by ID.

        Args:
            item_id: ID of the item to select
        """
        nav_list: ListView = self.query_one(
            selector="#navigation", expect_type=ListView
        )
        for index, item in enumerate(iterable=nav_list.children):
            if hasattr(item, "id") and item.id == item_id:
                nav_list.index = index
                break

    async def add_article_to_list(
        self, article: dict[str, Any], list_view: ListView
    ) -> None:
        """Add an article to the list view with improved error handling."""
        try:
            article_id: str = str(object=article.get("id"))
            if not article_id:
                logger.warning(msg="Attempted to add article without ID to list")
                return

            # Get display title safely
            display_title: str = safe_get_article_display_title(article=article)

            # Create the list item - IMPORTANT: disable markup to prevent MarkupError
            list_item = ListItem(
                Static(content=display_title, markup=False), id=f"art_{article_id}"
            )

            # Safely style based on read status
            is_read: bool = (
                article.get("read", False) or article.get("state") == "finished"
            )
            safe_set_text_style(item=list_item, style="none" if is_read else "bold")

            # Add to the list
            list_view.append(item=list_item)
        except Exception as e:
            logger.error(msg=f"Error adding article to list: {e}")
            # Try to add a placeholder item as fallback
            try:
                list_view.append(
                    item=ListItem(Static(content="Error loading article", markup=False))
                )
            except Exception as nested_e:
                logger.error(msg=f"Failed to add fallback item: {nested_e}")

    async def on_list_view_highlighted(self, message: Any) -> None:
        """Handle list view item highlighting with improved performance."""
        highlighted_item: Any = message.item
        if not highlighted_item or not (
            hasattr(highlighted_item, "id") and highlighted_item.id is not None
        ):
            return

        # Check if this is a navigation item
        if (
            highlighted_item.id.startswith("nav_")
            and highlighted_item.id != "nav_header"
        ):
            if (
                hasattr(highlighted_item, "data")
                and isinstance(highlighted_item.data, dict)
                and "category" in highlighted_item.data
            ):
                category: Any = highlighted_item.data["category"]

                # Only switch category if it's different from the current one
                if category != self.current_category:
                    self.current_category = category
                    await self.load_category(category=category, initial_load=True)

        # Check if this is an article
        elif highlighted_item.id.startswith("art_") and highlighted_item.id != "header":
            article_id: str = highlighted_item.id.replace("art_", "")

            # Only load the article if it's different from the current one
            if article_id != self.current_article_id:
                # Load article content
                await self.display_article(article_id=article_id)

        # Check if this is the load more button
        elif highlighted_item.id == "load_more_item":
            await self.action_load_more()

    async def display_article(self, article_id: str) -> None:  # noqa: PLR0912, PLR0915
        """Fetch and display article content with improved error handling and timeouts.

        Args:
            article_id: ID of the article to retrieve
        """
        if not article_id:
            logger.warning(msg="Attempted to display article with empty ID")
            self.notify(message="Invalid article ID", title="Error", severity="error")
            return

        # Show loading status
        content_view: LinkableMarkdownViewer = self.query_one(
            selector="#content", expect_type=LinkableMarkdownViewer
        )
        content_view.update_content(markdown="# Loading article...\n\nPlease wait...")

        try:
            # Set up a timeout to prevent hanging
            FETCH_TIMEOUT = 10  # seconds

            # Create a safer version of the article fetching
            article = None
            try:
                # Run the synchronous get_article in a thread using run_in_executor
                loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()
                article: dict[str, Any] | None = await asyncio.wait_for(
                    fut=loop.run_in_executor(
                        executor=None,  # Use default executor
                        func=lambda: self.client.get_article(article_id=article_id),
                    ),
                    timeout=FETCH_TIMEOUT,
                )
            except TimeoutError:
                logger.error(
                    msg=f"Timeout fetching article {article_id} after {FETCH_TIMEOUT} seconds"
                )
                self.notify(
                    message="Timeout fetching article. Try again or check your connection.",
                    title="Timeout Error",
                    severity="error",
                )
                content_view.update_content(
                    markdown="# Timeout Error\n\nFailed to load the article in a reasonable time. Please try again."
                )
                return
            except Exception as fetch_error:
                logger.error(
                    msg=f"Error fetching article: {fetch_error}", exc_info=True
                )
                self.notify(
                    message=f"Error fetching article: {fetch_error}",
                    title="Error",
                    severity="error",
                )
                content_view.update_content(
                    markdown=f"# Error Loading Article\n\nThere was a problem loading this article.\n\n**Error details:** {fetch_error}"
                )
                return

            if not article:
                logger.error(msg=f"Article not found or returned None: {article_id}")
                self.notify(
                    message=f"Article not found: {article_id}",
                    title="Error",
                    severity="error",
                )
                content_view.update_content(
                    markdown="# Article Not Found\n\nThe requested article could not be loaded."
                )
                return

            # Update state
            self.current_article = article
            self.current_article_id = article_id

            # Format content safely with timeout protection
            try:
                logger.debug(msg="Calling format_article_content")

                # Run the synchronous format_article_content in a thread
                loop = asyncio.get_event_loop()
                self.content_markdown = await asyncio.wait_for(
                    fut=loop.run_in_executor(
                        executor=None,  # Use default executor
                        func=lambda: format_article_content(article=article),
                    ),
                    timeout=FETCH_TIMEOUT,
                )

                logger.debug(
                    msg=f"Formatted content length: {len(self.content_markdown)}"
                )
            except TimeoutError:
                logger.error(
                    msg=f"Timeout formatting article content after {FETCH_TIMEOUT} seconds"
                )
                self.notify(
                    message="Timeout formatting article content. Content may be too large.",
                    title="Timeout Error",
                    severity="error",
                )
                self.content_markdown = "# Timeout Error\n\nThe article content is taking too long to format. It might be too large or complex."
            except Exception as format_error:
                logger.error(
                    msg=f"Error formatting article content: {format_error}",
                    exc_info=True,
                )
                self.content_markdown = f"# Error Formatting Content\n\nThere was an error preparing the article content.\n\n**Error details:** {format_error}"

            # Display content using LinkableMarkdownViewer - with safety
            try:
                content_view = self.query_one(
                    selector="#content", expect_type=LinkableMarkdownViewer
                )

                # Update content instead of removing and creating new viewer
                # This is safer than the mount/unmount approach
                content_view.update_content(markdown=self.content_markdown)

                # Update item style without refreshing everything - only update the current item
                articles_list: ListView = self.query_one(
                    selector="#articles", expect_type=ListView
                )

                # Use a more efficient approach to find and update the item
                item_to_update: Widget | None = None
                for item in articles_list.children:
                    if hasattr(item, "id") and item.id == f"art_{article_id}":
                        item_to_update = item
                        break

                if item_to_update:
                    safe_set_text_style(item=item_to_update, style="none")

            except Exception as view_error:
                logger.error(
                    msg=f"Error updating markdown viewer: {view_error}", exc_info=True
                )
                self.notify(
                    message=f"Error displaying article: {view_error}",
                    title="Error",
                    severity="error",
                )
                # Try a simpler update as fallback
                try:
                    content_view.update_content(
                        markdown="# Error Displaying Article\n\nThere was a problem displaying the article content."
                    )
                except Exception as fallback_error:
                    logger.error(
                        msg=f"Failed to set fallback message: {fallback_error}"
                    )

        except Exception as e:
            logger.error(msg=f"Unexpected error in display_article: {e}", exc_info=True)
            self.notify(
                message=f"Unexpected error: {e}",
                title="Error",
                severity="error",
            )
            try:
                content_view.update_content(
                    markdown="# Error\n\nAn unexpected error occurred while trying to display this article."
                )
            except Exception:
                pass  # At this point we can't do much more

    async def action_goto_feed(self) -> None:
        """Navigate directly to the Feed category."""
        await self._select_nav_item(item_id="nav_feed")
        self.current_category = "feed"
        await self.load_category(category="feed", initial_load=True)

    async def action_goto_inbox(self) -> None:
        """Navigate directly to the Inbox category."""
        await self._select_nav_item(item_id="nav_inbox")
        self.current_category = "inbox"
        await self.load_category(category="inbox", initial_load=True)

    async def action_goto_later(self) -> None:
        """Navigate directly to the Later category."""
        await self._select_nav_item(item_id="nav_later")
        self.current_category = "later"
        await self.load_category(category="later", initial_load=True)

    async def action_goto_archive(self) -> None:
        """Navigate directly to the Archive category."""
        await self._select_nav_item(item_id="nav_archive")
        self.current_category = "archive"
        await self.load_category(category="archive", initial_load=True)

    async def extract_links_from_content(self, content: str) -> list[tuple[str, str]]:
        """Extract links from article content.

        Args:
            content: Article content in markdown or HTML format

        Returns:
            List of tuples with link text and URL
        """
        links: list[tuple[str, str]] = []

        # Extract markdown links [text](url)
        markdown_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        for match in re.finditer(pattern=markdown_pattern, string=content):
            text: str = match.group(1).strip()
            url: str = match.group(2).strip()
            links.append((text, url))

        # Extract HTML links <a href="url">text</a>
        html_pattern = r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>'
        for match in re.finditer(pattern=html_pattern, string=content):
            url = match.group(1).strip()
            text = match.group(2).strip()
            links.append((text, url))

        return links

    async def handle_link_click(self, link: str) -> None:
        """Handle link click in the markdown viewer.

        Args:
            link: URL that was clicked
        """
        # Simply open the link in a browser
        try:
            webbrowser.open(url=link)
            self.notify(message=f"Opening link: {link}", title="Browser")
        except Exception as e:
            logger.error(msg=f"Error opening link: {e}")
            self.notify(
                message=f"Error opening link: {e}", title="Error", severity="error"
            )

    def action_maximize_content(self) -> None:
        """Maximize the content pane."""
        self.push_screen(
            screen=FullScreenMarkdown(markdown_content=self.content_markdown)
        )

    async def action_open_links(self) -> None:
        """Show a list of links in the article and open the selected one in a browser."""
        # Make sure we have an article loaded
        if not self.current_article:
            self.notify(
                message="No article selected", title="Error", severity="warning"
            )
            return

        # Extract links from content
        content: str = self.content_markdown
        links: list[tuple[str, str]] = await self.extract_links_from_content(
            content=content
        )

        # If no links found
        if not links:
            self.notify(message="No links found in article", title="Info")
            return

        # Show link selection screen
        link_screen = LinkSelectionScreen(
            links=links, configuration=self.configuration, open_links="browser"
        )
        self.push_screen(screen=link_screen)

    @work
    async def action_save_link(self) -> None:
        """Show a list of links in the article and save the selected one."""
        # Make sure we have an article loaded
        if not self.current_article:
            self.notify(
                message="No article selected", title="Error", severity="warning"
            )
            return

        # Extract links from content
        content: str = self.content_markdown
        links: list[tuple[str, str]] = await self.extract_links_from_content(
            content=content
        )

        # If no links found
        if not links:
            self.notify(message="No links found in article", title="Info")
            return

        # Show link selection screen
        link_screen = LinkSelectionScreen(
            links=links, configuration=self.configuration, open_links="download"
        )
        await self.push_screen(screen=link_screen)

    @work
    async def action_readwise_link(self) -> None:
        """Show a list of links in the article and save the selected one to Readwise."""
        # Make sure we have an article loaded
        if not self.current_article:
            self.notify(
                message="No article selected", title="Error", severity="warning"
            )
            return

        # Make sure Readwise token is configured
        if not hasattr(self.configuration, "token") or not self.configuration.token:
            self.notify(
                message="No Readwise token configured", title="Error", severity="error"
            )
            return

        # Extract links from content
        content: str = self.content_markdown
        links: list[tuple[str, str]] = await self.extract_links_from_content(
            content=content
        )

        # If no links found
        if not links:
            self.notify(message="No links found in article", title="Info")
            return

        # Show link selection screen
        link_screen = LinkSelectionScreen(
            links=links, configuration=self.configuration, open_links="readwise"
        )
        await self.push_screen(screen=link_screen)

    @work
    async def action_readwise_link_and_open(self) -> None:
        """Show a list of links in the article, save to Readwise and open."""
        # Make sure we have an article loaded
        if not self.current_article:
            self.notify(
                message="No article selected", title="Error", severity="warning"
            )
            return

        # Make sure Readwise token is configured
        if not hasattr(self.configuration, "token") or not self.configuration.token:
            self.notify(
                message="No Readwise token configured", title="Error", severity="error"
            )
            return

        # Extract links from content
        content: str = self.content_markdown
        links: list[tuple[str, str]] = await self.extract_links_from_content(
            content=content
        )

        # If no links found
        if not links:
            self.notify(message="No links found in article", title="Info")
            return

        # Show link selection screen
        link_screen = LinkSelectionScreen(
            links=links,
            configuration=self.configuration,
            open_links="readwise",
            open=True,
        )
        await self.push_screen(screen=link_screen)

    @work
    async def action_delete_article(self) -> None:
        """Delete the current article after confirmation."""
        # Make sure we have an article loaded
        if not self.current_article_id or not self.current_article:
            self.notify(
                message="No article selected", title="Error", severity="warning"
            )
            return

        # Get article title for confirmation
        article_title: str = self.current_article.get("title", "Unknown article")

        # Show confirmation dialog
        delete_screen = DeleteArticleScreen(
            article_id=self.current_article_id, article_title=article_title
        )
        result = await self.push_screen_wait(screen=delete_screen)

        # Check if confirmed
        if result and result.get("confirmed"):
            article_id: str = self.current_article_id
            try:
                # Delete the article
                self.client.delete_article(article_id=article_id)
                self.notify(message="Article deleted successfully", title="Success")

                list_view: ListView = self.query_one(
                    selector="#articles", expect_type=ListView
                )

                # Remove the article from the list
                for _, item in enumerate(iterable=list_view.children):
                    if hasattr(item, "id") and item.id == f"art_{article_id}":
                        await item.remove()
                        break

                await self.update_navigation_counts()

                # Clear the content view
                self.action_clear()
            except Exception as e:
                logger.error(msg=f"Error deleting article: {e}")
                self.notify(
                    message=f"Error deleting article: {e}",
                    title="Error",
                    severity="error",
                )

    def action_open_in_browser(self) -> None:
        """Open the current article in a web browser."""
        if not self.current_article:
            self.notify(
                message="No article selected", title="Error", severity="warning"
            )
            return

        url: str | None = self.current_article.get("url")
        if not url:
            self.notify(
                message="No URL available for this article",
                title="Error",
                severity="warning",
            )
            return

        try:
            webbrowser.open(url=url)
            self.notify(message="Opening in browser", title="Browser")
        except Exception as e:
            logger.error(msg=f"Error opening browser: {e}")
            self.notify(
                message=f"Error opening browser: {e}", title="Error", severity="error"
            )

    def action_show_metadata(self) -> None:
        """Show detailed metadata for the current article."""
        if not self.current_article:
            self.notify(
                message="No article selected", title="Error", severity="warning"
            )
            return

        try:
            # Extract all relevant metadata
            metadata: list[str] = []
            metadata.append(f"Title: {self.current_article.get('title', 'Untitled')}")

            if "author" in self.current_article:
                metadata.append(f"Author: {self.current_article['author']}")

            if "site_name" in self.current_article:
                metadata.append(f"Source: {self.current_article['site_name']}")

            if "url" in self.current_article:
                metadata.append(f"URL: {self.current_article['url']}")

            if "published_date" in self.current_article:
                metadata.append(f"Published: {self.current_article['published_date']}")

            if "word_count" in self.current_article:
                metadata.append(f"Word Count: {self.current_article['word_count']}")

            if "reading_progress" in self.current_article:
                metadata.append(
                    f"Reading Progress: {self.current_article['reading_progress']}%"
                )

            # Determine category
            category: (
                Literal["Archive"]
                | Literal["Feed"]
                | Literal["Later"]
                | Literal["Inbox"]
            ) = (
                "Archive"
                if self.current_article.get("location", "") == "archive"
                else (
                    "Later"
                    if self.current_article.get("location", "") == "later"
                    else (
                        "Feed"
                        if self.current_article.get("location", "") == "feed"
                        else ("Inbox")
                    )
                )
            )
            metadata.append(f"Category: {category}")

            # Add summary if available
            if self.current_article.get("summary"):
                metadata.append(f"\nSummary: {self.current_article['summary']}")

            # Show metadata in a notification
            metadata_text: str = "\n".join(metadata)

            self.notify(
                title="Article Metadata",
                message=metadata_text,
                timeout=10,  # Longer timeout for more time to read
            )
        except Exception as e:
            logger.error(msg=f"Error showing metadata: {e}")
            self.notify(
                message=f"Error showing metadata: {e}", title="Error", severity="error"
            )

    def action_clear(self) -> None:
        """Clear the content view."""
        self.content_markdown = (
            "# Welcome to Readwise Reader TUI\n\nSelect an article to read."
        )
        content_view: LinkableMarkdownViewer = self.query_one(
            selector="#content", expect_type=LinkableMarkdownViewer
        )
        content_view.update_content(markdown=self.content_markdown)
        self.current_article = None
        self.current_article_id = None

    async def action_refresh(self) -> None:
        """Refresh all data from the API."""
        try:
            # Clear the cache
            self.client.clear_cache()
            self.notify(message="Refreshing data...", title="Refresh")

            # Reset loaded item counts
            for category in self.items_loaded:
                self.items_loaded[category] = 0

            # Reload the current category
            await self.load_category(category=self.current_category, initial_load=True)

            # Reload the article if one was selected
            if self.current_article_id:
                await self.display_article(article_id=self.current_article_id)

            self.notify(message="Refresh complete", title="Refresh")
        except Exception as e:
            logger.error(msg=f"Error refreshing data: {e}")
            self.notify(
                message=f"Error refreshing data: {e}", title="Error", severity="error"
            )

    async def update_navigation_counts(self) -> None:
        """Update navigation items with current item counts."""
        try:
            nav_list: ListView = self.query_one(
                selector="#navigation", expect_type=ListView
            )

            # Get counts - use simple approach first
            counts = {}
            try:
                # Get cached data lengths to avoid API calls when possible
                inbox_data = self.client._category_cache.get("inbox", {}).get(
                    "data", []
                )
                feed_data = self.client._category_cache.get("feed", {}).get("data", [])
                later_data = self.client._category_cache.get("later", {}).get(
                    "data", []
                )

                # Get counts for each category
                counts["inbox"] = self._get_category_count("inbox", inbox_data)
                counts["feed"] = self._get_category_count(
                    "feed", feed_data, count_unread=True
                )
                counts["later"] = self._get_category_count("later", later_data)

            except Exception as e:
                logger.error(f"Error getting counts: {e}")
                # Fallback to loaded counts
                counts = {
                    "inbox": self.items_loaded.get("inbox", 0),
                    "feed": self.items_loaded.get("feed", 0),
                    "later": self.items_loaded.get("later", 0),
                }

            # Update navigation items
            for item in nav_list.children:
                if hasattr(item, "id") and hasattr(item, "data") and item.data:  # type: ignore
                    category = item.data["category"]  # type: ignore
                    if category:
                        # Skip archive as it has no counter
                        if category == "archive":
                            continue
                        # Update other categories with counts
                        if category in counts:
                            count = counts[category]
                            category_name = category.capitalize()
                            # Add arrow prefix for library items (inbox, later)
                            prefix = (
                                "→ " if category in ("inbox", "later") else ""
                            )
                            if count >= 0:
                                new_content = f"{prefix}{category_name} ({count})"
                            else:
                                new_content = f"{prefix}{category_name} (...)"

                            # Update the text
                            static_widget = item.children[0] if item.children else None
                            if static_widget and hasattr(static_widget, "update"):
                                static_widget.update(new_content)  # type: ignore

        except Exception as e:
            logger.error(f"Error updating navigation counts: {e}")

    def _get_category_count(
        self, category: str, cache_data: list, count_unread: bool = False
    ) -> int:
        """Get count for a category, handling cache vs loaded items logic."""
        # For feed and later, check background counts first (but only if > 0)
        if category in self.background_counts and self.background_counts[category] > 0:
            logger.debug(
                f"Using background count for {category}: {self.background_counts[category]}"
            )
            return self.background_counts[category]

        # Check if cache has been populated or if we have loaded items
        cache_info = self.client._category_cache.get(category, {})
        last_updated = cache_info.get("last_updated", 0)
        loaded_count = self.items_loaded.get(category, 0)

        # For debugging
        logger.debug(
            f"Count logic for {category}: last_updated={last_updated}, cache_len={len(cache_data)}, loaded={loaded_count}"
        )

        # If we've attempted to load this category OR cache is populated, show actual count
        # We check if the category exists in items_loaded (meaning we tried to load it)
        if category in self.items_loaded or last_updated > 0:
            if count_unread and cache_data:
                count = len([a for a in cache_data if a.get("first_opened_at") == ""])
                logger.debug(f"Using cache unread count for {category}: {count}")
                return count
            elif cache_data is not None:
                logger.debug(f"Using cache count for {category}: {len(cache_data)}")
                return len(cache_data)
            else:
                logger.debug(f"Using loaded count for {category}: {loaded_count}")
                return loaded_count

        # No data available yet - this should show as "(...)"
        logger.debug(f"No data available for {category}, showing as (...)")
        return -1  # Special value to indicate "no data yet"

    def start_background_count_updates(self) -> None:
        """Start the background worker for count updates."""
        # Schedule the first update after initial load
        self.set_timer(self.background_update_interval, self._trigger_background_update)

    def _trigger_background_update(self) -> None:
        """Trigger a background update and schedule the next one."""
        try:
            logger.debug("Triggering background count update")
            # Check if app is still running
            if self.is_running:
                self.update_background_counts()
                # Schedule the next update
                self.set_timer(
                    self.background_update_interval, self._trigger_background_update
                )
            else:
                logger.debug("App not running, stopping background updates")
        except Exception as e:
            logger.error(f"Error in trigger background update: {e}")
            # Try to reschedule anyway
            self.set_timer(
                self.background_update_interval, self._trigger_background_update
            )

    @work(exclusive=False, thread=True)
    def update_background_counts(self) -> None:
        """Background worker to update feed and later counts periodically."""
        try:
            logger.debug("Starting background count update")
            # Check if app is still running
            if not self.is_running:
                logger.debug("App not running, skipping background count update")
                return

            # Get fresh counts from the client
            if hasattr(self, "client") and self.client:
                logger.debug("Client found, getting counts")
                # Get feed count (unread articles only)
                new_feed_count = self.client.get_feed_count()
                logger.debug(f"Feed count: {new_feed_count}")

                # Get later count
                new_later_count = self.client.get_later_count()
                logger.debug(f"Later count: {new_later_count}")

                # Check if counts have changed
                feed_changed = new_feed_count != self.background_counts["feed"]
                later_changed = new_later_count != self.background_counts["later"]

                logger.debug(
                    f"Counts changed - Feed: {feed_changed} ({self.background_counts['feed']} -> {new_feed_count}), Later: {later_changed} ({self.background_counts['later']} -> {new_later_count})"
                )

                if feed_changed or later_changed:
                    # Update background counts
                    self.background_counts["feed"] = new_feed_count
                    self.background_counts["later"] = new_later_count

                    # Schedule UI update on the main thread
                    self.call_from_thread(self.update_background_navigation_counts)

                    logger.info(
                        f"Background counts updated - Feed: {new_feed_count}, Later: {new_later_count}"
                    )
                else:
                    logger.debug("No count changes detected")
            else:
                logger.warning("No client available for background count update")

        except Exception as e:
            logger.error(f"Error in background count update: {e}")

    async def action_test_background_update(self) -> None:
        """Manually test background count update."""
        logger.info("Manual background count update triggered")
        self.update_background_counts()

    async def action_refresh_counts(self) -> None:
        """Manually refresh all navigation counts."""
        logger.info("Manual count refresh triggered")
        logger.debug(f"Current items_loaded: {self.items_loaded}")
        logger.debug(f"Current background_counts: {self.background_counts}")
        await self.update_navigation_counts()

    async def action_next_category(self) -> None:
        """Move to the next category in the navigation."""
        await self._move_category(direction=1)

    async def action_previous_category(self) -> None:
        """Move to the previous category in the navigation."""
        await self._move_category(direction=-1)

    async def _move_category(self, direction: int) -> None:
        """Move to next/previous category in navigation list."""
        try:
            nav_list: ListView = self.query_one(
                selector="#navigation", expect_type=ListView
            )

            # Focus the navigation list first
            nav_list.focus()

            current_index = nav_list.index
            if current_index is None:
                current_index = 0

            # Calculate new index with wrapping
            new_index = (current_index + direction) % len(nav_list.children)
            nav_list.index = new_index

            # Get the selected item and load its category
            selected_item = nav_list.children[new_index]
            if hasattr(selected_item, "data") and selected_item.data:
                category = selected_item.data["category"]  # type: ignore
                logger.debug(f"Moving to category: {category}")
                if category != self.current_category:
                    self.current_category = category
                    await self.load_category(category=category, initial_load=True)

        except Exception as e:
            logger.error(f"Error moving between categories: {e}")

    def update_background_navigation_counts(self) -> None:
        """Update navigation counts using background data."""
        try:
            nav_list: ListView = self.query_one(
                selector="#navigation", expect_type=ListView
            )

            # Update only feed and later navigation items
            for item in nav_list.children:
                if hasattr(item, "id") and hasattr(item, "data") and item.data:  # type: ignore
                    category = item.data["category"]  # type: ignore
                    if category in self.background_counts:
                        count = self.background_counts[category]
                        category_name = category.capitalize()
                        new_content = f"{category_name} ({count})"

                        # Update the text
                        static_widget = item.children[0] if item.children else None
                        if static_widget and hasattr(static_widget, "update"):
                            static_widget.update(new_content)  # type: ignore

        except Exception as e:
            logger.error(f"Error updating background navigation counts: {e}")

    async def action_load_more(self) -> None:
        """Load more articles for the current category."""
        if self.is_loading:
            return

        try:
            self.is_loading = (
                True  # Automatically shows loading indicator via watch_is_loading
            )

            # Hide load more button while loading
            load_more: LoadMoreWidget = self.query_one(
                selector="#load_more", expect_type=LoadMoreWidget
            )
            load_more.display = False

            # Get more articles
            more_articles: list[dict[str, Any]] = self.client.get_more_articles(
                category=self.current_category
            )

            # Get the current list of articles
            articles_list: ListView = self.query_one(
                selector="#articles", expect_type=ListView
            )

            # Get the current item count
            current_count: int = len(articles_list.children)
            if current_count > 0:  # Subtract header if present
                current_count -= 1

            # Calculate how many new articles we got
            new_articles: list[dict[str, Any]] = more_articles[current_count:]

            # Add new articles to the list
            for article in new_articles:
                await self.add_article_to_list(article=article, list_view=articles_list)

            # Update loaded count
            self.items_loaded[self.current_category] = len(more_articles)

            # Show load more button if there are more articles
            load_more.display = len(new_articles) > 0

            # Update notification
            self.notify(
                message=f"Loaded {len(new_articles)} more articles",
                title=f"{self.current_category.capitalize()}",
            )

        except Exception as e:
            logger.error(msg=f"Error loading more articles: {e}")
            self.notify(
                message=f"Error loading more articles: {e}",
                title="Error",
                severity="error",
            )
        finally:
            # Hide loading indicator automatically via watch_is_loading
            self.is_loading = False

    def action_focus_next_pane(self) -> None:
        """Move focus to the next pane."""
        panes: list[str] = ["navigation", "articles", "content"]
        current_focus: Widget | None = self.focused

        if current_focus:
            current_id: str | None = current_focus.id
            if current_id in panes:
                next_index: int = (panes.index(current_id) + 1) % len(panes)
                next_pane: Widget = self.query_one(selector=f"#{panes[next_index]}")
                next_pane.focus()

    def action_focus_previous_pane(self) -> None:
        """Move focus to the previous pane."""
        panes: list[str] = ["navigation", "articles", "content"]
        current_focus: Widget | None = self.focused

        if current_focus:
            current_id: str | None = current_focus.id
            if current_id in panes:
                previous_index: int = (panes.index(current_id) - 1) % len(panes)
                previous_pane: Widget = self.query_one(
                    selector=f"#{panes[previous_index]}"
                )
                previous_pane.focus()

    def action_next_item(self) -> None:
        """Move to the next item in the current list."""
        current_focus: Widget | None = self.focused

        if current_focus and hasattr(current_focus, "action_cursor_down"):
            # For normal listviews and other widgets with cursor_down
            current_focus.action_cursor_down()  # type: ignore
        elif current_focus and hasattr(current_focus, "action_scroll_down"):
            # For scroll-based widgets like MarkdownViewer
            current_focus.action_scroll_down()  # type: ignore
        elif current_focus and current_focus.id == "navigation":
            pass

    def action_previous_item(self) -> None:
        """Move to the previous item in the current list."""
        current_focus: Widget | None = self.focused

        if current_focus and hasattr(current_focus, "action_cursor_up"):
            # For normal listviews and other widgets with cursor_up
            current_focus.action_cursor_up()  # type: ignore
        elif current_focus and hasattr(current_focus, "action_scroll_up"):
            # For scroll-based widgets like MarkdownViewer
            current_focus.action_scroll_up()  # type: ignore
        elif current_focus and current_focus.id == "navigation":
            pass

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

    async def load_category(self, category: str, initial_load: bool = False) -> None:  # noqa: PLR0912, PLR0915
        """Load articles for the given category."""
        try:
            # Clear the current article if this is an initial load
            if initial_load:
                self.current_article = None
                self.current_article_id = None

            # Show loading indicator if this is an initial load (via reactive attribute)
            if initial_load:
                self.is_loading = True
                # Create a header text for notifications
                header_text: str = category.capitalize()

                # Create a status widget for persistent status display
                api_status: APIStatusWidget = self.query_one(
                    selector="APIStatusWidget", expect_type=APIStatusWidget
                )
                api_status.show_info(message=f"Loading {header_text} articles...")

            # Update the articles list
            articles_list: ListView = self.query_one(
                selector="#articles", expect_type=ListView
            )

            # Clear the list if this is an initial load
            if initial_load:
                await articles_list.clear()

                # Add category header - IMPORTANT: disable markup
                header_text: str = category.capitalize()
                articles_list.append(
                    item=ListItem(
                        Static(content=f"{header_text.upper()} ARTICLES", markup=False),
                        id="header",
                    )
                )

                # Reset the loaded count for this category
                self.items_loaded[category] = 0

            # Get articles for the selected category with limit for fast initial loading
            articles: list[dict[str, Any]] = []
            page_size: int = self.initial_page_size if initial_load else 0

            if category == "inbox":
                articles = self.client.get_inbox(refresh=initial_load, limit=page_size)
            elif category == "feed":
                articles = [
                    article
                    for article in self.client.get_feed(
                        refresh=initial_load, limit=page_size
                    )
                    if article.get("first_opened_at") == ""
                ]
            elif category == "later":
                articles = self.client.get_later(refresh=initial_load, limit=page_size)
            elif category == "archive":
                articles = self.client.get_archive(
                    refresh=initial_load, limit=page_size
                )

            # Update loaded count
            self.items_loaded[category] = len(articles)

            # Add each article to the list
            if initial_load:
                for article in articles:
                    await self.add_article_to_list(
                        article=article, list_view=articles_list
                    )
            else:
                # For load_more, we only add articles that aren't already in the list
                current_ids = set()
                for item in articles_list.children:
                    if (
                        hasattr(item, "id")
                        and item.id is not None
                        and item.id.startswith("art_")
                    ):
                        current_ids.add(item.id.replace("art_", ""))

                for article in articles:
                    if article["id"] not in current_ids:
                        await self.add_article_to_list(
                            article=article, list_view=articles_list
                        )

            # Show/hide load more button based on if there might be more articles
            load_more: LoadMoreWidget = self.query_one(
                selector="#load_more", expect_type=LoadMoreWidget
            )
            load_more.display = len(articles) >= self.initial_page_size

            # Show completed notification (only once at the end)
            if initial_load:
                # Update the status widget instead of creating a new notification
                api_status = self.query_one(
                    selector="APIStatusWidget", expect_type=APIStatusWidget
                )
                api_status.show_info(
                    message=f"Loaded {len(articles)} {header_text} articles"
                )

                # Auto-hide the status after 3 seconds
                self.set_timer(delay=3, callback=lambda: api_status.hide())

                # Clear the content pane
                content_view: LinkableMarkdownViewer = self.query_one(
                    selector="#content", expect_type=LinkableMarkdownViewer
                )
                content_view.update_content(markdown="# Select an article to read")

                # Select the first article if there are any
                if len(articles) > 0:
                    articles_list.focus()
                    # Skip the header by starting at index 1
                    articles_list.index = 1
                    # Trigger display of the first article
                    first_item: Widget | None = (
                        articles_list.children[1]
                        if len(articles_list.children) > 1
                        else None
                    )
                    if (
                        first_item
                        and hasattr(first_item, "id")
                        and first_item.id is not None
                        and first_item.id.startswith("art_")
                    ):
                        article_id: str = first_item.id.replace("art_", "")
                        await self.display_article(article_id=article_id)
            if initial_load:
                # Update navigation counts after loading
                await self.update_navigation_counts()

                # For feed and later, immediately update background counts with fresh data
                # to ensure the count is current and not stale from background timer
                if category in ("feed", "later"):
                    try:
                        if category == "feed":
                            new_count = self.client.get_feed_count()
                        else:  # later
                            new_count = self.client.get_later_count()

                        # Update background counts immediately
                        self.background_counts[category] = new_count
                        logger.debug(
                            f"Updated background count for {category} to {new_count}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Error updating background count for {category}: {e}"
                        )
        except Exception as e:
            logger.error(msg=f"Error loading category {category}: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

            # Add an error message to the list - disable markup
            try:
                if initial_load:  # Only add error message on initial load
                    articles_list.append(
                        item=ListItem(
                            Static(
                                content=f"Error loading {category}: {e}", markup=False
                            ),
                            id="error",
                        )
                    )
            except Exception as nested_e:
                logger.error(msg=f"Failed to add error message to list: {nested_e}")
        finally:
            # Hide loading indicator automatically via watch_is_loading
            self.is_loading = False

    async def action_move_to_inbox(self) -> None:
        """Move the current article to Inbox."""
        if not self.current_article_id:
            self.notify(
                message="No article selected", title="Error", severity="warning"
            )
            return

        try:
            if self.client.move_to_inbox(article_id=self.current_article_id):
                # Show success message
                self.notify(message="Moved to Inbox", title="Success")

                # Refresh if we're not already in the inbox
                if self.current_category != "inbox":
                    await self.load_category(
                        category=self.current_category, initial_load=True
                    )

                await self.update_navigation_counts()

                # Update the article display
                if self.current_article_id:
                    await self.display_article(article_id=self.current_article_id)
            else:
                self.notify(
                    message="Failed to move to Inbox", title="Error", severity="error"
                )
        except Exception as e:
            logger.error(msg=f"Error moving to inbox: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    async def action_move_to_later(self) -> None:
        """Move the current article to Later."""
        if not self.current_article_id:
            self.notify(
                message="No article selected", title="Error", severity="warning"
            )
            return

        try:
            if self.client.move_to_later(article_id=self.current_article_id):
                # Show success message
                self.notify(message="Moved to Later", title="Success")

                # Refresh if we're not already in Later
                if self.current_category != "later":
                    await self.load_category(
                        category=self.current_category, initial_load=True
                    )

                await self.update_navigation_counts()

                # Update the article display
                if self.current_article_id:
                    await self.display_article(article_id=self.current_article_id)
            else:
                self.notify(
                    message="Failed to move to Later", title="Error", severity="error"
                )
        except Exception as e:
            logger.error(msg=f"Error moving to later: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    async def action_move_to_archive(self) -> None:
        """Move the current article to Archive."""
        if not self.current_article_id:
            self.notify(
                message="No article selected", title="Error", severity="warning"
            )
            return

        try:
            if self.client.move_to_archive(article_id=self.current_article_id):
                # Show success message
                self.notify(message="Moved to Archive", title="Success")

                # Refresh if we're not already in the Archive
                if self.current_category != "archive":
                    await self.load_category(
                        category=self.current_category, initial_load=True
                    )

                await self.update_navigation_counts()

                # Update the article display
                if self.current_article_id:
                    await self.display_article(article_id=self.current_article_id)
            else:
                self.notify(
                    message="Failed to move to Archive", title="Error", severity="error"
                )
        except Exception as e:
            logger.error(msg=f"Error moving to archive: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    def on_unmount(self) -> None:
        """Clean up resources when the app is closed."""
        if hasattr(self, "client"):
            self.client.close()
