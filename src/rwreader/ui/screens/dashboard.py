"""Library dashboard: overview, inbox aging, sources and tags.

Everything here reads from the local :class:`~rwreader.index.DocumentIndex`
(see ``rwreader.index``) rather than the API, so it stays fast even for large
libraries. If the index is disabled in configuration, the dashboard says so
and shows empty tables. Pressing ``s`` runs a full sync (fetches every
document from the API once, independent of which categories have been
browsed) before refreshing the tables.
"""

import asyncio
import logging
from datetime import UTC, datetime
from typing import Any, ClassVar

from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import Screen
from textual.widgets import DataTable, Footer, Header, Static, TabbedContent, TabPane

from ...index import DocumentIndex
from .article_list import ArticleListScreen

logger = logging.getLogger(__name__)

_WORDS_PER_MINUTE = 200

# API location code -> display label / category name used elsewhere in the app.
_LOCATION_LABELS: dict[str, str] = {
    "new": "Inbox",
    "later": "Later",
    "shortlist": "Shortlist",
    "feed": "Feed",
    "archive": "Archive",
}
_CATEGORY_BY_LOCATION: dict[str, str] = {
    "new": "inbox",
    "later": "later",
    "shortlist": "shortlist",
    "feed": "feed",
    "archive": "archive",
}
_LOCATION_ORDER: tuple[str, ...] = ("new", "later", "shortlist", "feed", "archive")

# (bucket label, min days, max days inclusive)
_AGE_BUCKETS: tuple[tuple[str, int, int], ...] = (
    ("Today", 0, 0),
    ("1-3 days", 1, 3),
    ("4-7 days", 4, 7),
    ("8-30 days", 8, 30),
    ("30+ days", 31, 10**6),
)

_MAX_SOURCES = 30
_MAX_TAGS = 100
_MAX_AGING_DOCS = 5000


def format_reading_time(words: int) -> str:
    """Format a word count as an estimated reading time (e.g. "1h 20m").

    Args:
        words: Word count.

    Returns:
        A short human string, "0m" for no words.
    """
    if not words:
        return "0m"
    minutes = max(1, round(words / _WORDS_PER_MINUTE))
    hours, mins = divmod(minutes, 60)
    if hours:
        return f"{hours}h {mins}m" if mins else f"{hours}h"
    return f"{mins}m"


def _parse_timestamp(value: str) -> datetime | None:
    """Parse an ISO-8601 or unix-seconds timestamp string; None if unusable."""
    if not value:
        return None
    try:
        stripped = value.strip()
        if stripped.replace(".", "", 1).isdigit():
            return datetime.fromtimestamp(float(stripped), tz=UTC)
        return datetime.fromisoformat(stripped.replace("Z", "+00:00"))
    except (ValueError, OverflowError, OSError):
        return None


def days_since(value: str) -> int | None:
    """Whole days between now and a timestamp string, or None if unparseable.

    Args:
        value: ISO-8601 or unix-seconds timestamp.

    Returns:
        Non-negative day count, or None if ``value`` could not be parsed.
    """
    parsed = _parse_timestamp(value)
    if parsed is None:
        return None
    return max(0, (datetime.now(tz=UTC) - parsed).days)


def age_bucket_label(days: int) -> str:
    """Return the age bucket label a day count falls into."""
    for label, lo, hi in _AGE_BUCKETS:
        if lo <= days <= hi:
            return label
    return _AGE_BUCKETS[-1][0]


class DashboardScreen(Screen):
    """Tabbed dashboard over the local document index."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        Binding("comma", "refresh", "Refresh"),
        Binding("s", "sync", "Sync now"),
        Binding("escape", "back", "Back"),
        Binding("backspace", "back", "Back", show=False),
        Binding("h", "help", "Help"),
        Binding("d", "toggle_dark", "Toggle dark mode"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the dashboard screen."""
        super().__init__(**kwargs)
        self._index: DocumentIndex | None = None
        self._bucket_articles: dict[str, list[dict[str, Any]]] = {}

    def compose(self) -> ComposeResult:
        """Build the tabbed layout."""
        yield Header(show_clock=True)
        yield Static("", id="dashboard-status")
        with TabbedContent(initial="overview-pane"):
            with TabPane("Overview", id="overview-pane"):
                yield DataTable(id="overview-table", cursor_type="row")
            with TabPane("Inbox aging", id="aging-pane"):
                yield DataTable(id="aging-table", cursor_type="row")
            with TabPane("Sources", id="sources-pane"):
                yield DataTable(id="sources-table", cursor_type="row")
            with TabPane("Tags", id="tags-pane"):
                yield DataTable(id="tags-table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        """Set up table columns and load data."""
        self.query_one("#overview-table", DataTable).add_columns(
            "Location", "Total", "Unread", "Words", "Est. reading"
        )
        self.query_one("#aging-table", DataTable).add_columns("Age", "Count")
        self.query_one("#sources-table", DataTable).add_columns(
            "Site", "Total", "Unread"
        )
        self.query_one("#tags-table", DataTable).add_columns("Tag", "Count")
        self.refresh_dashboard()
        self.query_one("#overview-table", DataTable).focus()

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        """Focus the table in the tab that just became active."""
        try:
            event.pane.query_one(DataTable).focus()
        except Exception as e:
            logger.debug(f"Could not focus table in activated tab: {e}")

    # ── Data loading ─────────────────────────────────────────────────────

    def refresh_dashboard(self) -> None:
        """Recompute every tab from the current state of the local index."""
        client = getattr(self.app, "client", None)
        index = getattr(client, "index", None) if client is not None else None
        status = self.query_one("#dashboard-status", Static)

        if index is None:
            self._index = None
            self._bucket_articles = {}
            status.update(
                "Local index is disabled — enable [general] index_enabled in "
                "your config to use the dashboard."
            )
            for table_id in (
                "overview-table",
                "aging-table",
                "sources-table",
                "tags-table",
            ):
                self.query_one(f"#{table_id}", DataTable).clear()
            return

        self._index = index
        last_sync = index.last_sync
        sync_text = (
            last_sync.astimezone().strftime("%Y-%m-%d %H:%M") if last_sync else "never"
        )
        status.update(
            f"{index.count()} documents indexed  |  last full sync: {sync_text}  |  "
            "press 's' to sync now, ',' to refresh"
        )
        self._populate_overview(index)
        self._bucket_articles = self._populate_aging(index)
        self._populate_sources(index)
        self._populate_tags(index)

    def _populate_overview(self, index: DocumentIndex) -> None:
        """Fill the Overview table with per-location counts and reading time."""
        counts = index.count_by_location()
        unread = index.count_by_location(unread_only=True)
        words = index.words_by_location()
        table = self.query_one("#overview-table", DataTable)
        table.clear()
        for location in _LOCATION_ORDER:
            word_count = words.get(location, 0)
            table.add_row(
                _LOCATION_LABELS[location],
                str(counts.get(location, 0)),
                str(unread.get(location, 0)),
                str(word_count),
                format_reading_time(word_count),
                key=location,
            )

    def _populate_aging(self, index: DocumentIndex) -> dict[str, list[dict[str, Any]]]:
        """Fill the Inbox aging table and return bucket -> articles for drill-down."""
        docs = index.query(
            location="new",
            order_by="saved_at",
            descending=False,
            limit=_MAX_AGING_DOCS,
        )
        buckets: dict[str, list[dict[str, Any]]] = {
            label: [] for label, _, _ in _AGE_BUCKETS
        }
        for doc in docs:
            timestamp = doc.get("saved_at") or doc.get("created_at") or ""
            days = days_since(timestamp)
            label = age_bucket_label(days) if days is not None else _AGE_BUCKETS[-1][0]
            buckets[label].append(doc)

        table = self.query_one("#aging-table", DataTable)
        table.clear()
        for label, _, _ in _AGE_BUCKETS:
            table.add_row(label, str(len(buckets[label])), key=label)
        return buckets

    def _populate_sources(self, index: DocumentIndex) -> None:
        """Fill the Sources table with the most common sites."""
        table = self.query_one("#sources-table", DataTable)
        table.clear()
        for site, total, unread in index.site_counts_with_unread(limit=_MAX_SOURCES):
            table.add_row(site, str(total), str(unread), key=site)

    def _populate_tags(self, index: DocumentIndex) -> None:
        """Fill the Tags table with the most common tags."""
        table = self.query_one("#tags-table", DataTable)
        table.clear()
        for tag, count in index.tag_counts()[:_MAX_TAGS]:
            table.add_row(tag, str(count), key=tag)

    # ── Drill-down ───────────────────────────────────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Open a filtered article list for the selected row."""
        table_id = event.data_table.id
        key = event.row_key.value
        if key is None:
            return

        if table_id == "overview-table":
            category = _CATEGORY_BY_LOCATION.get(str(key))
            if category:
                self.app.push_screen(ArticleListScreen(category=category))
        elif table_id == "aging-table":
            self._open_snapshot(
                self._bucket_articles.get(str(key), []),
                title=f"Inbox — {key}",
                empty_message="No articles in that range",
            )
        elif table_id == "sources-table" and self._index is not None:
            self._open_snapshot(
                self._index.query(site_name=str(key), order_by="saved_at"),
                title=str(key),
                empty_message="No articles for that source",
            )
        elif table_id == "tags-table" and self._index is not None:
            self._open_snapshot(
                self._index.query(tag=str(key), order_by="saved_at"),
                title=f"#{key}",
                empty_message="No articles with that tag",
            )

    def _open_snapshot(
        self, articles: list[dict[str, Any]], title: str, empty_message: str
    ) -> None:
        """Push a read-only article list snapshot, or notify if it is empty."""
        if not articles:
            self.notify(empty_message, title="Dashboard")
            return
        self.app.push_screen(
            ArticleListScreen(category="custom", preset_articles=articles, title=title)
        )

    # ── Actions ──────────────────────────────────────────────────────────

    def action_refresh(self) -> None:
        """Recompute the tables from the index without hitting the API."""
        self.refresh_dashboard()

    @work
    async def action_sync(self) -> None:
        """Fully sync the local index from the API, then refresh the tables."""
        client = getattr(self.app, "client", None)
        index = getattr(client, "index", None) if client is not None else None
        if client is None or index is None:
            self.notify(
                "Local index not available", severity="warning", title="Dashboard"
            )
            return

        self.notify("Syncing full library…", title="Dashboard")
        loop = asyncio.get_event_loop()
        try:
            written = await loop.run_in_executor(None, client.sync_index, True)
        except Exception as e:
            logger.error(f"Dashboard sync failed: {e}")
            self.notify(f"Sync failed: {e}", severity="error", title="Dashboard")
            return
        self.refresh_dashboard()
        self.notify(f"Synced {written} documents", title="Dashboard")

    def action_back(self) -> None:
        """Return to the category list."""
        self.app.pop_screen()

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
