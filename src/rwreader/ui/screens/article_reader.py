"""Article reader screen with navigation."""

import asyncio
import logging
import re
import webbrowser
from typing import TYPE_CHECKING, Any, ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import Footer, Header, Static

from ...utils.highlight_manager import (
    create_reader_highlight,
    find_html_fragment,
    get_highlights_for_document,
    inject_highlights_into_markdown,
    is_readwise_cli_available,
)
from ...utils.ui_helpers import format_article_content, move_article_to_destination
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
        Binding("h", "toggle_highlight", "Highlight"),
        Binding("ctrl+j", "cursor_next", "Para ▶", show=False),
        Binding("ctrl+k", "cursor_prev", "◀ Para", show=False),
        Binding("g", "scroll_top", "Top", show=False),
        Binding("G", "scroll_bottom", "Bottom", show=False),
        Binding("escape", "back", "Back"),
        Binding("backspace", "back", "Back", show=False),
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
        self.highlights: list[dict[str, Any]] = []
        self._paragraphs: list[str] = []
        self._cursor: int = -1
        self.is_loading = False

    def compose(self) -> ComposeResult:
        """Create the article reader UI."""
        yield Header(show_clock=True)
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
        self.load_article_content()

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

            # Parse paragraphs and initialise cursor at the first one
            self._paragraphs = self._parse_paragraphs(self.content_markdown)
            self._cursor = 0 if self._paragraphs else -1

            # Display content (without highlights initially)
            self.highlights = []
            content_view.update_content(self._get_display_markdown())
            self._update_position_widget()

            # Fetch highlights in background if CLI is available
            cli_available = is_readwise_cli_available()
            logger.debug(f"Highlight CLI available: {cli_available}, article_id={article_id!r}")
            if cli_available:
                self.fetch_highlights(article_id=article_id)

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

    @work(exclusive=True)
    async def fetch_highlights(self, article_id: str) -> None:
        """Fetch highlights for the current article and re-render content.

        Args:
            article_id: ID of the article being displayed; used to guard
                        against stale updates when the user navigates away.
        """
        logger.debug(f"fetch_highlights started for article_id={article_id!r}")
        try:
            loop = asyncio.get_event_loop()
            highlights = await loop.run_in_executor(
                None,
                lambda: get_highlights_for_document(article_id),
            )
            logger.debug(f"fetch_highlights got {len(highlights)} highlights for {article_id!r}")

            # Guard: article may have changed while we were fetching
            current_id = str(self.article.get("id"))
            logger.debug(f"fetch_highlights guard: current_id={current_id!r} article_id={article_id!r}")
            if current_id != article_id:
                logger.debug("fetch_highlights: article changed, discarding results")
                return

            if not highlights:
                logger.debug("fetch_highlights: no highlights found")
                return

            self.highlights = highlights
            logger.debug(f"fetch_highlights: {len(highlights)} highlights loaded")
            self._update_display()
            self.notify(
                f"{len(highlights)} highlight(s) loaded",
                title="Highlights",
            )

        except Exception as e:
            logger.error(f"Error fetching highlights: {e}", exc_info=True)

    # ── Paragraph cursor helpers ──────────────────────────────────────────

    @staticmethod
    def _parse_paragraphs(markdown: str) -> list[str]:
        """Return highlightable paragraph strings from markdown."""
        _MIN_LEN = 30
        blocks = re.split(r"\n\n+", markdown)
        result = []
        for raw_block in blocks:
            stripped = raw_block.strip()
            if not stripped or len(stripped) < _MIN_LEN:
                continue
            first = stripped.split("\n")[0]
            # Skip headings, code fences, rules, blockquotes, already-marked blocks
            if first.startswith(("#", "```", "---", ">", "|", "⟦")):
                continue
            result.append(stripped)
        return result

    def _get_display_markdown(self) -> str:
        """Build display markdown: cursor mark first, then highlight markers."""
        base = self.content_markdown

        # Mark cursor paragraph with a blockquote prefix (visual left-side marker)
        if 0 <= self._cursor < len(self._paragraphs):
            cursor_text = self._paragraphs[self._cursor]
            if cursor_text in base:
                quoted = "\n".join(f"> {line}" for line in cursor_text.split("\n"))
                base = base.replace(cursor_text, quoted, 1)

        if self.highlights:
            base = inject_highlights_into_markdown(base, self.highlights)
        return base

    def _update_display(self) -> None:
        """Refresh the content view and position widget."""
        try:
            content_view = self.query_one("#article_content", LinkableMarkdownViewer)
            content_view.update_content(self._get_display_markdown())
            self._update_position_widget()
        except Exception as e:
            logger.debug(f"Error updating display: {e}")

    def _update_position_widget(self) -> None:
        """Update the position bar with article index and cursor position."""
        article_info = (
            f"Article {self.current_index + 1}/{len(self.article_list)}"
            f" in {self.category.capitalize()}"
        )
        n = len(self._paragraphs)
        if n > 0 and self._cursor >= 0:
            cursor_info = f"Para {self._cursor + 1}/{n}  Ctrl+K/J navigate  h highlight"
            text = f"{article_info}  |  {cursor_info}"
        else:
            text = article_info
        position_widget = self.query_one("#article_position", Static)
        position_widget.update(text)

    def _scroll_to_cursor(self) -> None:
        """Scroll the viewer so the cursor paragraph is at the top of the viewport."""
        if not self._paragraphs or self._cursor < 0:
            return
        try:
            content_view = self.query_one("#article_content", LinkableMarkdownViewer)
            if self._cursor == 0:
                content_view.scroll_home(animate=False)
                return

            cursor_text = self._paragraphs[self._cursor]
            offset = self.content_markdown.find(cursor_text)
            total = len(self.content_markdown)
            if offset < 0 or total == 0:
                return

            pct = offset / total
            target = int(content_view.virtual_size.height * pct)
            content_view.scroll_to(y=target, animate=False)
        except Exception as e:
            logger.debug(f"Error scrolling to cursor: {e}")

    # ── Cursor actions ────────────────────────────────────────────────────

    def action_cursor_prev(self) -> None:
        """Move the highlight cursor to the previous paragraph."""
        if not self._paragraphs:
            return
        self._cursor = max(0, self._cursor - 1)
        self._update_display()
        self._scroll_to_cursor()

    def action_cursor_next(self) -> None:
        """Move the highlight cursor to the next paragraph."""
        if not self._paragraphs:
            return
        self._cursor = min(len(self._paragraphs) - 1, self._cursor + 1)
        self._update_display()
        self._scroll_to_cursor()

    def action_scroll_top(self) -> None:
        """Scroll to the top of the article."""
        self.query_one("#article_content", LinkableMarkdownViewer).scroll_home(
            animate=False
        )

    def action_scroll_bottom(self) -> None:
        """Scroll to the bottom of the article."""
        self.query_one("#article_content", LinkableMarkdownViewer).scroll_end(
            animate=False
        )

    # ── Highlight creation / deletion ─────────────────────────────────────

    @work
    async def action_toggle_highlight(self) -> None:
        """Create or delete a highlight at the cursor paragraph."""
        if not is_readwise_cli_available():
            self.notify(
                "readwise CLI not found in PATH",
                title="Highlights",
                severity="warning",
            )
            return

        if self._cursor < 0 or not self._paragraphs:
            self.notify(
                "No paragraph selected — use [ ] to move cursor",
                title="Highlights",
            )
            return

        para_text = self._paragraphs[self._cursor]

        # Is this paragraph already highlighted?
        existing = next(
            (h for h in self.highlights if para_text in (h.get("content") or "")),
            None,
        )

        article_id = str(self.article.get("id"))
        loop = asyncio.get_event_loop()

        if existing:
            self.notify(
                "Already highlighted — remove via the Readwise web UI",
                title="Highlights",
            )
            return
        html_content = self.article.get("html_content", "")
        html_frag = await loop.run_in_executor(
            None,
            lambda: find_html_fragment(html_content, para_text),
        )
        success, msg = await loop.run_in_executor(
            None,
            lambda: create_reader_highlight(article_id, html_frag),
        )
        if success:
            self.notify("Highlight created", title="Highlights")
            self.fetch_highlights(article_id=article_id)
        else:
            self.notify(f"Create failed: {msg}", title="Highlights", severity="warning")

    def action_next_article(self) -> None:
        """Navigate to next article in list."""
        if self.current_index < len(self.article_list) - 1:
            self.current_index += 1
            self.article = self.article_list[self.current_index]
            self.highlights = []
            self._paragraphs = []
            self._cursor = -1
            self.refresh_article()

    def action_previous_article(self) -> None:
        """Navigate to previous article in list."""
        if self.current_index > 0:
            self.current_index -= 1
            self.article = self.article_list[self.current_index]
            self.highlights = []
            self._paragraphs = []
            self._cursor = -1
            self.refresh_article()

    def refresh_article(self) -> None:
        """Refresh display with new article."""
        # Scroll the markdown viewer to top
        try:
            content_view = self.query_one("#article_content", LinkableMarkdownViewer)
            content_view.scroll_home(animate=False)
        except Exception:
            pass  # Widget may not be mounted yet

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

        client = self.app.client  # type: ignore
        article_id = str(self.article.get("id"))

        success, message = move_article_to_destination(
            client=client, article_id=article_id, destination=destination
        )

        if success:
            self.notify(message, title="Success")
            if self.category != destination:
                logger.debug(
                    f"Removing article at index {self.current_index} from list of {len(self.article_list)} articles"
                )
                removed_article = self.article_list.pop(self.current_index)
                logger.debug(
                    f"After removal: {len(self.article_list)} articles remaining"
                )
                logger.debug(
                    f"Removed '{removed_article.get('title', 'Unknown')[:30]}', {len(self.article_list)} left"
                )
                if self.current_index >= len(self.article_list):
                    self.current_index = len(self.article_list) - 1
                if len(self.article_list) > 0:
                    self.article = self.article_list[self.current_index]
                    self.refresh_article()
                else:
                    self.notify("No more articles", title="Info")
                    self.app.pop_screen()
            else:
                logger.debug(
                    f"Article moved to {destination} which is same as current category {self.category}, not removing from list"
                )
        else:
            self.notify(message, severity="error")

    @work
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
