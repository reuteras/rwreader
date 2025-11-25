"""Article reader screen with navigation."""

import asyncio
import logging
import re
import webbrowser
from typing import TYPE_CHECKING, Any, ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import VerticalScroll
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ...utils.ui_helpers import format_article_content
from ..widgets.linkable_markdown_viewer import LinkableMarkdownViewer

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


class ArticleReaderScreen(Screen):
    """Screen for reading a single article."""

    BINDINGS: ClassVar[list[Binding]] = [
        Binding("J", "next_article", "Next Article", show=True),
        Binding("K", "previous_article", "Previous Article", show=True),
        Binding("a", "archive", "Archive"),
        Binding("l", "later", "Later"),
        Binding("i", "inbox", "Inbox"),
        Binding("D", "delete", "Delete"),
        Binding("o", "open_browser", "Open in Browser"),
        Binding("ctrl+l", "show_links", "Links"),
        Binding("escape", "back", "Back"),
        Binding("backspace", "back", "Back", show=False),
        Binding("h", "help", "Help"),
    ]

    def __init__(
        self,
        article: dict[str, Any],
        article_list: list[dict[str, Any]],
        current_index: int,
        category: str,
        **kwargs: Any,
    ) -> None:
        """Initialize reader with article and navigation context.

        Args:
            article: The article to display
            article_list: Full list of articles for navigation
            current_index: Current position in article_list
            category: Category the articles are from
            **kwargs: Additional keyword arguments
        """
        super().__init__(**kwargs)
        self.article = article
        self.article_list = article_list
        self.current_index = current_index
        self.category = category
        self.content_markdown = ""
        self.is_loading = False

    def compose(self) -> ComposeResult:
        """Create the article reader UI."""
        yield Header(show_clock=True)
        with VerticalScroll(id="reader_scroll"):
            yield Static("", id="article_position")
            yield LinkableMarkdownViewer(
                markdown="# Loading...\n\nPlease wait...",
                id="article_content",
                show_table_of_contents=False,
                open_links=False,
            )
        yield Footer()

    async def on_mount(self) -> None:
        """Load article content when screen mounts."""
        await self.load_article_content()

    @work(exclusive=True)
    async def load_article_content(self) -> None:
        """Load full article content from API if not cached."""
        if self.is_loading:
            return

        self.is_loading = True

        try:
            # Update position indicator
            position_text = f"Article {self.current_index + 1} of {len(self.article_list)} in {self.category.capitalize()}"
            position_widget = self.query_one("#article_position", Static)
            position_widget.update(position_text)

            # Get full article from API
            if not hasattr(self.app, "client"):
                self.notify("API client not available", severity="error")
                return

            client = self.app.client  # type: ignore
            article_id = str(self.article.get("id"))

            # Show loading status
            content_view = self.query_one("#article_content", LinkableMarkdownViewer)
            content_view.update_content("# Loading article...\n\nPlease wait...")

            # Fetch article with timeout
            FETCH_TIMEOUT = 10
            loop = asyncio.get_event_loop()
            full_article = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: client.get_article(article_id=article_id),
                ),
                timeout=FETCH_TIMEOUT,
            )

            if not full_article:
                content_view.update_content("# Error\n\nArticle not found.")
                return

            # Update article with full content
            self.article = full_article

            # Format content
            self.content_markdown = await asyncio.wait_for(
                loop.run_in_executor(
                    None,
                    lambda: format_article_content(article=full_article),
                ),
                timeout=FETCH_TIMEOUT,
            )

            # Display content
            content_view.update_content(self.content_markdown)

        except TimeoutError:
            logger.error("Timeout loading article")
            self.notify("Timeout loading article", severity="error")
            content_view = self.query_one("#article_content", LinkableMarkdownViewer)
            content_view.update_content("# Timeout\n\nFailed to load article in time.")
        except Exception as e:
            logger.error(f"Error loading article: {e}")
            self.notify(f"Error: {e}", severity="error")
            content_view = self.query_one("#article_content", LinkableMarkdownViewer)
            content_view.update_content(f"# Error\n\n{e}")
        finally:
            self.is_loading = False

    def action_next_article(self) -> None:
        """Navigate to next article in list."""
        if self.current_index < len(self.article_list) - 1:
            self.current_index += 1
            self.article = self.article_list[self.current_index]
            self.refresh_article()

    def action_previous_article(self) -> None:
        """Navigate to previous article in list."""
        if self.current_index > 0:
            self.current_index -= 1
            self.article = self.article_list[self.current_index]
            self.refresh_article()

    def refresh_article(self) -> None:
        """Refresh display with new article."""
        # Scroll to top
        scroll_view = self.query_one("#reader_scroll", VerticalScroll)
        scroll_view.scroll_home(animate=False)

        # Load new article content
        self.load_article_content()

    async def action_archive(self) -> None:
        """Archive this article."""
        await self._move_article("archive")

    async def action_later(self) -> None:
        """Move this article to Later."""
        await self._move_article("later")

    async def action_inbox(self) -> None:
        """Move this article to Inbox."""
        await self._move_article("inbox")

    async def _move_article(self, destination: str) -> None:
        """Move the current article to a destination.

        Args:
            destination: Target location (inbox, later, archive)
        """
        if not hasattr(self.app, "client"):
            self.notify("API client not available", severity="error")
            return

        try:
            client = self.app.client  # type: ignore
            article_id = str(self.article.get("id"))

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
                # Auto-advance to next article if not in destination category
                if self.category != destination:
                    # Remove from article list
                    self.article_list.pop(self.current_index)
                    # Adjust index if needed
                    if self.current_index >= len(self.article_list):
                        self.current_index = len(self.article_list) - 1
                    # Load next article or go back if list is empty
                    if len(self.article_list) > 0:
                        self.article = self.article_list[self.current_index]
                        self.refresh_article()
                    else:
                        self.notify("No more articles", title="Info")
                        self.app.pop_screen()
            else:
                self.notify(f"Failed to move to {destination}", severity="error")

        except Exception as e:
            logger.error(f"Error moving article: {e}")
            self.notify(f"Error: {e}", severity="error")

    async def action_delete(self) -> None:
        """Delete this article (with confirmation)."""
        article_id = str(self.article.get("id"))
        article_title = self.article.get("title", "Unknown article")

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

                    # Remove from article list
                    self.article_list.pop(self.current_index)
                    # Adjust index if needed
                    if self.current_index >= len(self.article_list):
                        self.current_index = len(self.article_list) - 1
                    # Load next article or go back if list is empty
                    if len(self.article_list) > 0:
                        self.article = self.article_list[self.current_index]
                        self.refresh_article()
                    else:
                        self.notify("No more articles", title="Info")
                        self.app.pop_screen()
            except Exception as e:
                logger.error(f"Error deleting article: {e}")
                self.notify(f"Error: {e}", severity="error")

    def action_open_browser(self) -> None:
        """Open the current article in browser."""
        url = self.article.get("url")
        if url:
            try:
                webbrowser.open(url)
                self.notify("Opening in browser", title="Browser")
            except Exception as e:
                logger.error(f"Error opening browser: {e}")
                self.notify(f"Error: {e}", severity="error")
        else:
            self.notify("No URL available", severity="warning")

    async def action_show_links(self) -> None:
        """Show links in the article."""
        # Extract links from content
        links = []

        # Extract markdown links [text](url)
        markdown_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        for match in re.finditer(markdown_pattern, self.content_markdown):
            text = match.group(1).strip()
            url = match.group(2).strip()
            links.append((text, url))

        if not links:
            self.notify("No links found in article", title="Info")
            return

        # Show link selection screen
        from .link_screens import LinkSelectionScreen  # noqa: PLC0415

        if hasattr(self.app, "configuration"):
            config = self.app.configuration  # type: ignore
            link_screen = LinkSelectionScreen(
                links=links, configuration=config, open_links="browser"
            )
            self.app.push_screen(link_screen)
        else:
            self.notify("Configuration not available", severity="error")

    def action_back(self) -> None:
        """Return to article list."""
        self.app.pop_screen()

    def action_help(self) -> None:
        """Show help screen."""
        from .help import HelpScreen  # noqa: PLC0415

        self.app.push_screen(HelpScreen())
