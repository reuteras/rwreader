"""Improved application class for rwreader with progressive loading."""

import logging
import re
import sys
import webbrowser
from typing import Any, ClassVar

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import (
    Footer,
    Header,
    ListItem,
    ListView,
    LoadingIndicator,
    Static,
    Tree,
)

# Import our improved client
from ..client import ReadwiseClient
from ..config import Configuration
from ..utils.ui_helpers import (
    format_article_content,
    safe_get_article_display_title,
    safe_set_text_style,
)
from .screens.confirm import DeleteArticleScreen
from .screens.help import HelpScreen
from .widgets.api_status import APIStatusWidget
from .widgets.link_selection_screen import LinkSelectionScreen
from .widgets.linkable_markdown_viewer import LinkableMarkdownViewer
from .widgets.load_more import LoadMoreWidget

logger: logging.Logger = logging.getLogger(name=__name__)


class RWReader(App[None]):
    """A Textual app for Readwise Reader with progressive loading."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        # Navigation
        ("j", "next_item", "Next item"),
        ("k", "previous_item", "Previous item"),
        ("tab", "focus_next_pane", "Next pane"),
        ("shift+tab", "focus_previous_pane", "Previous pane"),
        # Direct navigation to categories
        ("I", "goto_inbox", "Go to Inbox"),
        ("L", "goto_later", "Go to Later"),
        ("A", "goto_archive", "Go to Archive"),
        # Article actions
        ("r", "toggle_read", "Toggle read/unread"),
        ("a", "move_to_archive", "Move to Archive"),
        ("l", "move_to_later", "Move to Later"),
        ("i", "move_to_inbox", "Move to Inbox"),
        ("o", "open_in_browser", "Open in browser"),
        ("m", "show_metadata", "Show metadata"),
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
        # Debug - hidden from help
        ("ctrl+d", "debug_dump", ""),  # Dump debug info
        ("ctrl+r", "debug_reset_cache", ""),  # Reset cache
    ]

    CSS_PATH = ["styles.tcss"]  # noqa: RUF012

    def __init__(self) -> None:
        """Initialize the app and connect to Readwise API."""
        super().__init__()  # Initialize first for early access to notify/etc.

        try:
            # Load the configuration
            self.configuration = Configuration(arguments=sys.argv[1:])

            # Set theme based on configuration
            self.theme = (
                "textual-dark"
                if self.configuration.default_theme == "dark"
                else "textual-light"
            )

            # Connect to Readwise API with the improved client
            self.client = ReadwiseClient(
                token=self.configuration.token,
                cache_size=self.configuration.cache_size,
            )

            # State variables
            self.current_article_id: str | None = None
            self.current_article: dict[str, Any] | None = None
            self.current_category: str = "inbox"  # Default category
            self.content_markdown: str = (
                "# Welcome to Readwise Reader TUI\n\nSelect an article to read."
            )

            # Progressive loading state
            self.is_loading: bool = False
            self.initial_page_size: int = 20  # Number of items to load initially
            self.items_loaded: dict[str, int] = {
                "inbox": 0,
                "later": 0,
                "archive": 0,
            }

        except Exception as e:
            logger.error(msg=f"Initialization error: {e}")
            print(f"Error: {e}")
            sys.exit(1)

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

    async def on_mount(self) -> None:
        """Load library data when the app is mounted."""
        # Set up navigation list
        nav_list: ListView = self.query_one("#navigation", expect_type=ListView)

        # Add header - disable markup
        nav_list.append(
            item=ListItem(Static(content="LIBRARY", markup=False), id="nav_header")
        )

        # Add category items with data attributes - disable markup
        inbox_item = ListItem(Static(content="Inbox", markup=False), id="nav_inbox")
        inbox_item.data = {"category": "inbox"}

        later_item = ListItem(Static(content="Later", markup=False), id="nav_later")
        later_item.data = {"category": "later"}

        archive_item = ListItem(
            Static(content="Archive", markup=False), id="nav_archive"
        )
        archive_item.data = {"category": "archive"}

        # Add items to the list
        nav_list.append(item=inbox_item)
        nav_list.append(item=later_item)
        nav_list.append(item=archive_item)

        # Hide loading indicator initially
        loading_indicator = self.query_one(
            "#loading_indicator", expect_type=LoadingIndicator
        )
        loading_indicator.display = False

        # Hide load more button initially
        load_more = self.query_one("#load_more", expect_type=LoadMoreWidget)
        load_more.display = False

        # Focus on the navigation list
        nav_list.focus()

        # Highlight the Inbox item by default
        await self._select_nav_item("nav_inbox")

        # Load initial articles
        await self.load_category(category="inbox", initial_load=True)

    async def _select_nav_item(self, item_id: str) -> None:
        """Select a navigation item by ID.

        Args:
            item_id: ID of the item to select
        """
        nav_list = self.query_one("#navigation", expect_type=ListView)
        for index, item in enumerate(nav_list.children):
            if hasattr(item, "id") and item.id == item_id:
                nav_list.index = index
                break

    async def on_tree_node_selected(self, event: Tree.NodeSelected) -> None:
        """Handle tree node selection."""
        if event.node.data and "category" in event.node.data:
            category = event.node.data["category"]

            # Update current category and load articles
            self.current_category = category
            await self.load_category(category=category, initial_load=True)

    async def add_article_to_list(
        self, article: dict[str, Any], list_view: ListView
    ) -> None:
        """Add an article to the list view with improved error handling."""
        try:
            article_id = article.get("id")
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
            is_read = article.get("read", False) or article.get("state") == "finished"
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
        """Handle list view item highlighting."""
        highlighted_item = message.item
        if not highlighted_item or not hasattr(highlighted_item, "id"):
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
                category = highlighted_item.data["category"]

                # Update current category and load articles
                self.current_category = category
                await self.load_category(category=category, initial_load=True)

        # Check if this is an article
        elif highlighted_item.id.startswith("art_") and highlighted_item.id != "header":
            article_id = highlighted_item.id.replace("art_", "")

            # Load article content
            await self.display_article(article_id=article_id)

        # Check if this is the load more button
        elif highlighted_item.id == "load_more_item":
            await self.action_load_more()

    async def display_article(self, article_id: str) -> None:
        """Fetch and display article content with improved error handling and diagnostics.

        Args:
            article_id: ID of the article to retrieve
        """
        if not article_id:
            logger.warning("Attempted to display article with empty ID")
            self.notify(message="Invalid article ID", title="Error", severity="error")
            return

        # Show loading status
        content_view = self.query_one("#content", expect_type=LinkableMarkdownViewer)
        content_view.update_content(markdown="# Loading article...\n\nPlease wait...")

        try:
            # Fetch the article with debug logging
            logger.debug(f"Beginning article fetch for ID: {article_id}")
            article = self.client.get_article(article_id=article_id)

            if not article:
                logger.error(f"Article not found or returned None: {article_id}")
                self.notify(
                    message=f"Article not found: {article_id}",
                    title="Error",
                    severity="error",
                )
                content_view.update_content(
                    markdown="# Article Not Found\n\nThe requested article could not be loaded."
                )
                return

            # Debug log article
            logger.debug(f"Article successfully fetched with ID: {article_id}")
            logger.debug(f"Article type: {type(article)}")
            logger.debug(f"Article has content: {bool(article.get('content'))}")
            logger.debug(
                f"Article has html_content: {bool(article.get('html_content'))}"
            )

            # Test direct access to content for debugging
            if article.get("content"):
                content_length = len(article["content"])
                logger.debug(f"Direct content length: {content_length}")
                if content_length > 0:
                    preview = article["content"][:100].replace("\n", " ")
                    logger.debug(f"Content preview: {preview}...")
            elif article.get("html_content"):
                content_length = len(article["html_content"])
                logger.debug(f"Direct html_content length: {content_length}")
                if content_length > 0:
                    preview = article["html_content"][:100].replace("\n", " ")
                    logger.debug(f"HTML content preview: {preview}...")
            else:
                logger.warning("Neither content nor html_content is present in article")

                # Check for any large string fields that might contain content
                for key, value in article.items():
                    if isinstance(value, str) and len(value) > 200:
                        logger.debug(
                            f"Found large string in field '{key}': {len(value)} bytes"
                        )

            # Update state
            self.current_article = article
            self.current_article_id = article_id

            # Format content with the new utility function
            logger.debug("Calling format_article_content")
            self.content_markdown = format_article_content(article=article)
            logger.debug(f"Formatted content length: {len(self.content_markdown)}")

            # Display content using LinkableMarkdownViewer
            logger.debug("Creating new markdown viewer")
            content_view = self.query_one("#content")
            await content_view.remove()

            # Then create and mount a new one with link handling
            new_viewer = LinkableMarkdownViewer(
                markdown=self.content_markdown,
                id="content",
                show_table_of_contents=False,
                open_links=False,  # Handle links ourselves
            )
            logger.debug("Mounting new viewer")
            content_container = self.query_one("Vertical")
            await content_container.mount(new_viewer)
            logger.debug("Viewer mounted successfully")

            # Auto-mark as read if enabled
            if (
                self.configuration.auto_mark_read
                and not article.get("read", False)
                and not article.get("state") == "finished"
            ):
                logger.debug(f"Auto-marking article {article_id} as read")
                self.client.toggle_read(article_id=article_id, read=True)

                # Update item style without refreshing everything
                articles_list = self.query_one("#articles", expect_type=ListView)
                for item in articles_list.children:
                    if hasattr(item, "id") and item.id == f"art_{article_id}":
                        safe_set_text_style(item=item, style="none")
                        break

            logger.debug("Article display complete")

        except Exception as e:
            logger.error(f"Error displaying article: {e}", exc_info=True)
            self.notify(
                message=f"Error displaying article: {e}",
                title="Error",
                severity="error",
            )

            # Set a fallback message in the content viewer
            try:
                content_view.update_content(
                    markdown="# Error Loading Article\n\nThere was a problem loading the article content.\n\n"
                    + f"**Error details:** {e!s}"
                )
            except Exception as nested_e:
                logger.error(f"Failed to set error message in content view: {nested_e}")

    # Direct navigation actions
    async def action_goto_inbox(self) -> None:
        """Navigate directly to the Inbox category."""
        await self._select_nav_item("nav_inbox")
        self.current_category = "inbox"
        await self.load_category("inbox", initial_load=True)
        self.notify(message="Navigated to Inbox", title="Navigation")

    async def action_goto_later(self) -> None:
        """Navigate directly to the Later category."""
        await self._select_nav_item("nav_later")
        self.current_category = "later"
        await self.load_category("later", initial_load=True)
        self.notify(message="Navigated to Later", title="Navigation")

    async def action_goto_archive(self) -> None:
        """Navigate directly to the Archive category."""
        await self._select_nav_item("nav_archive")
        self.current_category = "archive"
        await self.load_category("archive", initial_load=True)
        self.notify(message="Navigated to Archive", title="Navigation")

    async def extract_links_from_content(self, content: str) -> list[tuple[str, str]]:
        """Extract links from article content.

        Args:
            content: Article content in markdown or HTML format

        Returns:
            List of tuples with link text and URL
        """
        links = []

        # Extract markdown links [text](url)
        markdown_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        for match in re.finditer(markdown_pattern, content):
            text = match.group(1).strip()
            url = match.group(2).strip()
            links.append((text, url))

        # Extract HTML links <a href="url">text</a>
        html_pattern = r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>'
        for match in re.finditer(html_pattern, content):
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
            webbrowser.open(link)
            self.notify(message=f"Opening link: {link}", title="Browser")
        except Exception as e:
            logger.error(f"Error opening link: {e}")
            self.notify(
                message=f"Error opening link: {e}", title="Error", severity="error"
            )

    @work
    async def action_open_links(self) -> None:
        """Show a list of links in the article and open the selected one in a browser."""
        # Make sure we have an article loaded
        if not self.current_article:
            self.notify(
                message="No article selected", title="Error", severity="warning"
            )
            return

        # Extract links from content
        content = self.content_markdown
        links = await self.extract_links_from_content(content)

        # If no links found
        if not links:
            self.notify(message="No links found in article", title="Info")
            return

        # Show link selection screen
        link_screen = LinkSelectionScreen(
            links=links, configuration=self.configuration, action="browser"
        )
        await self.push_screen(link_screen)

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
        content = self.content_markdown
        links = await self.extract_links_from_content(content)

        # If no links found
        if not links:
            self.notify(message="No links found in article", title="Info")
            return

        # Show link selection screen
        link_screen = LinkSelectionScreen(
            links=links, configuration=self.configuration, action="download"
        )
        await self.push_screen(link_screen)

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
        if (
            not hasattr(self.configuration, "readwise_token")
            or not self.configuration.readwise_token
        ):
            self.notify(
                message="No Readwise token configured", title="Error", severity="error"
            )
            return

        # Extract links from content
        content = self.content_markdown
        links = await self.extract_links_from_content(content)

        # If no links found
        if not links:
            self.notify(message="No links found in article", title="Info")
            return

        # Show link selection screen
        link_screen = LinkSelectionScreen(
            links=links, configuration=self.configuration, action="readwise"
        )
        await self.push_screen(link_screen)

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
        if (
            not hasattr(self.configuration, "readwise_token")
            or not self.configuration.readwise_token
        ):
            self.notify(
                message="No Readwise token configured", title="Error", severity="error"
            )
            return

        # Extract links from content
        content = self.content_markdown
        links = await self.extract_links_from_content(content)

        # If no links found
        if not links:
            self.notify(message="No links found in article", title="Info")
            return

        # Show link selection screen
        link_screen = LinkSelectionScreen(
            links=links,
            configuration=self.configuration,
            action="readwise",
            open_after_save=True,
        )
        await self.push_screen(link_screen)

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
        article_title = self.current_article.get("title", "Unknown article")

        # Show confirmation dialog
        delete_screen = DeleteArticleScreen(
            article_id=self.current_article_id, article_title=article_title
        )
        result = await self.push_screen_wait(delete_screen)

        # Check if confirmed
        if result and result.get("confirmed"):
            article_id = self.current_article_id
            try:
                # Delete the article
                if self.client.delete_article(article_id=article_id):
                    self.notify(message="Article deleted successfully", title="Success")

                    # Refresh the article list
                    await self.load_category(self.current_category, initial_load=True)

                    # Clear the content view
                    await self.action_clear()
                else:
                    self.notify(
                        message="Failed to delete article",
                        title="Error",
                        severity="error",
                    )
            except Exception as e:
                logger.error(f"Error deleting article: {e}")
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

        url = self.current_article.get("url")
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
            metadata = []
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
            category = (
                "Archive"
                if self.current_article.get("archived", True)
                else (
                    "Later"
                    if self.current_article.get("saved_for_later", False)
                    else "Inbox"
                )
            )
            metadata.append(f"Category: {category}")

            # Add summary if available
            if self.current_article.get("summary"):
                metadata.append(f"\nSummary: {self.current_article['summary']}")

            # Show metadata in a notification
            metadata_text = "\n".join(metadata)
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
        content_view = self.query_one("#content", expect_type=LinkableMarkdownViewer)
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

    async def action_load_more(self) -> None:
        """Load more articles for the current category."""
        if self.is_loading:
            return

        try:
            self.is_loading = True

            # Show loading indicator
            loading_indicator = self.query_one(
                "#loading_indicator", expect_type=LoadingIndicator
            )
            loading_indicator.display = True

            # Hide load more button while loading
            load_more = self.query_one("#load_more", expect_type=LoadMoreWidget)
            load_more.display = False

            # Get more articles
            more_articles = self.client.get_more_articles(self.current_category)

            # Get the current list of articles
            articles_list = self.query_one("#articles", expect_type=ListView)

            # Get the current item count
            current_count = len(articles_list.children)
            if current_count > 0:  # Subtract header if present
                current_count -= 1

            # Calculate how many new articles we got
            new_articles = more_articles[current_count:]

            # Add new articles to the list
            for article in new_articles:
                await self.add_article_to_list(article, articles_list)

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
            logger.error(f"Error loading more articles: {e}")
            self.notify(
                message=f"Error loading more articles: {e}",
                title="Error",
                severity="error",
            )
        finally:
            # Hide loading indicator
            loading_indicator = self.query_one(
                "#loading_indicator", expect_type=LoadingIndicator
            )
            loading_indicator.display = False
            self.is_loading = False

    def action_focus_next_pane(self) -> None:
        """Move focus to the next pane."""
        panes: list[str] = ["navigation", "articles", "content"]
        current_focus: Widget | None = self.focused

        if current_focus:
            current_id: str | None = current_focus.id
            if current_id in panes:
                next_index: int = (panes.index(current_id) + 1) % len(panes)
                next_pane: Widget = self.query_one(f"#{panes[next_index]}")
                next_pane.focus()

    def action_focus_previous_pane(self) -> None:
        """Move focus to the previous pane."""
        panes: list[str] = ["navigation", "articles", "content"]
        current_focus: Widget | None = self.focused

        if current_focus:
            current_id: str | None = current_focus.id
            if current_id in panes:
                previous_index: int = (panes.index(current_id) - 1) % len(panes)
                previous_pane: Widget = self.query_one(f"#{panes[previous_index]}")
                previous_pane.focus()

    def action_next_item(self) -> None:
        """Move to the next item in the current list."""
        current_focus: Widget | None = self.focused

        if current_focus and hasattr(current_focus, "action_cursor_down"):
            # For normal listviews and other widgets with cursor_down
            current_focus.action_cursor_down()
        elif current_focus and current_focus.id == "navigation":
            pass

    def action_previous_item(self) -> None:
        """Move to the previous item in the current list."""
        current_focus: Widget | None = self.focused

        if current_focus and hasattr(current_focus, "action_cursor_up"):
            # For normal listviews and other widgets with cursor_up
            current_focus.action_cursor_up()
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

    async def action_debug_reset_cache(self) -> None:
        """Reset cache and reload everything."""
        try:
            self.notify(message="Resetting cache...", title="Debug")

            # Clear the client cache
            self.client.clear_cache()

            # Clear the current selection
            self.current_article = None
            self.current_article_id = None

            # Reload current category
            await self.load_category(self.current_category, initial_load=True)

            self.notify(message="Cache reset complete", title="Debug")
        except Exception as e:
            logger.error(f"Error resetting cache: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    async def load_category(self, category: str, initial_load: bool = False) -> None:  # noqa: PLR0912, PLR0915
        """Load articles for the given category."""
        try:
            # Clear the current article if this is an initial load
            if initial_load:
                self.current_article = None
                self.current_article_id = None

            # Show loading indicator if this is an initial load
            loading_indicator = self.query_one(
                "#loading_indicator", expect_type=LoadingIndicator
            )
            if initial_load:
                loading_indicator.display = True

            # Update the articles list
            articles_list = self.query_one("#articles", expect_type=ListView)

            # Clear the list if this is an initial load
            if initial_load:
                await articles_list.clear()

                # Add category header - IMPORTANT: disable markup
                header_text = category.capitalize()
                articles_list.append(
                    ListItem(
                        Static(f"{header_text.upper()} ARTICLES", markup=False),
                        id="header",
                    )
                )

                # Reset the loaded count for this category
                self.items_loaded[category] = 0

                # Notify user we're loading
                self.notify(
                    message=f"Loading {header_text} articles...", title="Loading"
                )

            # Get articles for the selected category with limit for fast initial loading
            articles = []
            page_size: int = self.initial_page_size if initial_load else 0

            if category == "inbox":
                articles = self.client.get_inbox(refresh=initial_load, limit=page_size)
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
                    await self.add_article_to_list(article, articles_list)
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
                        await self.add_article_to_list(article, articles_list)

            # Show/hide load more button based on if there might be more articles
            load_more = self.query_one("#load_more", expect_type=LoadMoreWidget)
            load_more.display = len(articles) >= self.initial_page_size

            # Show completed notification
            if initial_load:
                self.notify(
                    message=f"Loaded {len(articles)} articles", title=f"{header_text}"
                )

                # Clear the content pane
                content_view = self.query_one(
                    "#content", expect_type=LinkableMarkdownViewer
                )
                content_view.update_content("# Select an article to read")

                # Select the first article if there are any
                if len(articles) > 0:
                    articles_list.focus()
                    # Skip the header by starting at index 1
                    articles_list.index = 1
                    # Trigger display of the first article
                    first_item = (
                        articles_list.children[1]
                        if len(articles_list.children) > 1
                        else None
                    )
                    if (
                        first_item
                        and hasattr(first_item, "id")
                        and first_item.id.startswith("art_")
                    ):
                        article_id = first_item.id.replace("art_", "")
                        await self.display_article(article_id)
        except Exception as e:
            logger.error(f"Error loading category {category}: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

            # Add an error message to the list - disable markup
            try:
                if initial_load:  # Only add error message on initial load
                    articles_list.append(
                        ListItem(
                            Static(f"Error loading {category}: {e}", markup=False),
                            id="error",
                        )
                    )
            except Exception as nested_e:
                logger.error(f"Failed to add error message to list: {nested_e}")
        finally:
            # Hide loading indicator
            loading_indicator = self.query_one(
                "#loading_indicator", expect_type=LoadingIndicator
            )
            loading_indicator.display = False

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
                    await self.load_category(self.current_category, initial_load=True)

                # Update the article display
                if self.current_article_id:
                    await self.display_article(article_id=self.current_article_id)
            else:
                self.notify(
                    message="Failed to move to Inbox", title="Error", severity="error"
                )
        except Exception as e:
            logger.error(f"Error moving to inbox: {e}")
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
                    await self.load_category(self.current_category, initial_load=True)

                # Update the article display
                if self.current_article_id:
                    await self.display_article(article_id=self.current_article_id)
            else:
                self.notify(
                    message="Failed to move to Later", title="Error", severity="error"
                )
        except Exception as e:
            logger.error(f"Error moving to later: {e}")
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
                    await self.load_category(self.current_category, initial_load=True)

                # Update the article display
                if self.current_article_id:
                    await self.display_article(article_id=self.current_article_id)
            else:
                self.notify(
                    message="Failed to move to Archive", title="Error", severity="error"
                )
        except Exception as e:
            logger.error(f"Error moving to archive: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    async def action_toggle_read(self) -> None:
        """Toggle read/unread status of the current article with improved error handling."""
        if not self.current_article_id or not self.current_article:
            self.notify(
                message="No article selected", title="Error", severity="warning"
            )
            return

        try:
            # Determine current read status
            is_read = (
                self.current_article.get("read", False)
                or self.current_article.get("state") == "finished"
            )
            if self.client.toggle_read(
                article_id=self.current_article_id, read=not is_read
            ):
                # Show success message
                status = "read" if not is_read else "unread"
                self.notify(message=f"Marked as {status}", title="Success")

                # Update the article in the list without refreshing everything
                articles_list = self.query_one("#articles", expect_type=ListView)
                for item in articles_list.children:
                    if (
                        hasattr(item, "id")
                        and item.id == f"art_{self.current_article_id}"
                    ):
                        safe_set_text_style(item, "none" if not is_read else "bold")
                        break

                # Update current article's status
                self.current_article["read"] = not is_read
                self.current_article["state"] = "finished" if not is_read else "reading"

                # Refresh the article display
                await self.display_article(article_id=self.current_article_id)
            else:
                self.notify(
                    message="Failed to toggle read status",
                    title="Error",
                    severity="error",
                )
        except Exception as e:
            logger.error(msg=f"Error toggling read status: {e}")
            self.notify(message=f"Error: {e}", title="Error", severity="error")

    def on_unmount(self) -> None:
        """Clean up resources when the app is closed."""
        if hasattr(self, "client"):
            self.client.close()
