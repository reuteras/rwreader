"""Tests for the dashboard screen and its pure helper functions."""

import datetime
from collections.abc import Generator
from unittest.mock import Mock

import pytest
from textual.app import App
from textual.coordinate import Coordinate
from textual.widgets import DataTable

from rwreader.index import DocumentIndex
from rwreader.ui.screens.article_list import ArticleListScreen
from rwreader.ui.screens.dashboard import (
    DashboardScreen,
    age_bucket_label,
    days_since,
    format_reading_time,
)

# Test constants
TWO = 2
THREE = 3
FIVE = 5
ARCHIVE_ROW = 4
FORTY_MIN = 39
SOURCE_ROW_SITE2 = 1
AGING_ROW_1_3_DAYS = 1


def _article(doc_id: str, **overrides: object) -> dict:
    """Build a minimal article dict for the index."""
    article: dict = {
        "id": doc_id,
        "title": f"Title {doc_id}",
        "url": f"https://example.com/{doc_id}",
        "site_name": "example.com",
        "location": "new",
        "category": "article",
        "tags": [],
        "word_count": 100,
        "saved_at": "2024-01-01T00:00:00Z",
        "first_opened_at": "",
    }
    article.update(overrides)
    return article


class _HostApp(App[None]):
    """Minimal app used to host DashboardScreen under test."""

    def __init__(self, client: Mock | None = None) -> None:
        super().__init__()
        self.client = client


class TestFormatReadingTime:
    """Tests for format_reading_time."""

    def test_zero_words(self) -> None:
        """No words reads as 0m."""
        assert format_reading_time(0) == "0m"

    def test_minutes_only(self) -> None:
        """Small counts round up to at least one minute."""
        assert format_reading_time(1) == "1m"
        assert format_reading_time(150) == "1m"
        assert format_reading_time(400) == "2m"

    def test_hours_and_minutes(self) -> None:
        """Large counts split into hours and minutes; whole hours drop 0m."""
        assert format_reading_time(12000) == "1h"
        assert format_reading_time(13000) == "1h 5m"


class TestDaysSinceAndBuckets:
    """Tests for days_since and age_bucket_label."""

    def test_unparseable_and_empty(self) -> None:
        """Empty and garbage timestamps return None."""
        assert days_since("") is None
        assert days_since("not-a-date") is None

    def test_iso_and_unix_timestamps(self) -> None:
        """Both ISO strings and unix-seconds strings parse."""
        now = datetime.datetime.now(tz=datetime.UTC)
        assert days_since(now.isoformat()) == 0
        five_days_ago = now - datetime.timedelta(days=5)
        assert days_since(five_days_ago.isoformat()) == FIVE
        forty_days_ago = now - datetime.timedelta(days=40)
        parsed = days_since(str(int(forty_days_ago.timestamp())))
        assert parsed is not None
        assert parsed >= FORTY_MIN

    def test_bucket_boundaries(self) -> None:
        """Each documented boundary lands in the expected bucket."""
        assert age_bucket_label(0) == "Today"
        assert age_bucket_label(1) == "1-3 days"
        assert age_bucket_label(3) == "1-3 days"
        assert age_bucket_label(4) == "4-7 days"
        assert age_bucket_label(7) == "4-7 days"
        assert age_bucket_label(8) == "8-30 days"
        assert age_bucket_label(30) == "8-30 days"
        assert age_bucket_label(31) == "30+ days"
        assert age_bucket_label(99999) == "30+ days"


@pytest.fixture
def populated_index() -> Generator[DocumentIndex, None, None]:
    """An in-memory index with a small, varied set of documents."""
    idx = DocumentIndex(":memory:")
    now = datetime.datetime.now(tz=datetime.UTC)
    old = (now - datetime.timedelta(days=100)).isoformat()
    idx.upsert_many(
        [
            _article(
                "1",
                site_name="site1.com",
                location="new",
                tags=["python"],
                word_count=400,
                saved_at=now.isoformat(),
            ),
            _article(
                "2",
                site_name="site1.com",
                location="new",
                tags=["python", "go"],
                word_count=200,
                saved_at=old,
                first_opened_at="2020-01-02T00:00:00Z",
            ),
            _article(
                "3",
                site_name="site2.com",
                location="archive",
                tags=[],
                word_count=1000,
                saved_at=now.isoformat(),
            ),
        ]
    )
    yield idx
    idx.close()


class TestDashboardScreen:
    """Tests for DashboardScreen driven through Textual's pilot."""

    @pytest.mark.asyncio
    async def test_no_index_shows_message_and_empty_tables(self) -> None:
        """A client without an index shows guidance and no rows."""
        client = Mock()
        client.index = None
        app = _HostApp(client=client)
        async with app.run_test() as pilot:
            app.push_screen(DashboardScreen())
            await pilot.pause()
            status = app.screen.query_one("#dashboard-status")
            assert "disabled" in str(status.render())
            table = app.screen.query_one("#overview-table", DataTable)
            assert table.row_count == 0

    @pytest.mark.asyncio
    async def test_tables_populate_from_index(
        self, populated_index: DocumentIndex
    ) -> None:
        """Overview, aging, sources and tags tables reflect the index."""
        client = Mock()
        client.index = populated_index
        app = _HostApp(client=client)
        async with app.run_test() as pilot:
            app.push_screen(DashboardScreen())
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, DashboardScreen)

            overview = screen.query_one("#overview-table", DataTable)
            rows = {
                str(overview.get_row(key)[0]): overview.get_row(key)
                for key in overview.rows
            }
            assert rows["Inbox"] == ["Inbox", "2", "1", "600", "3m"]
            assert rows["Archive"] == ["Archive", "1", "1", "1000", "5m"]
            assert rows["Later"] == ["Later", "0", "0", "0", "0m"]

            aging = screen.query_one("#aging-table", DataTable)
            aging_rows = {
                str(aging.get_row(key)[0]): aging.get_row(key)[1] for key in aging.rows
            }
            assert aging_rows["Today"] == "1"
            assert aging_rows["30+ days"] == "1"

            sources = screen.query_one("#sources-table", DataTable)
            source_rows = {
                str(sources.get_row(key)[0]): sources.get_row(key)
                for key in sources.rows
            }
            assert source_rows["site1.com"] == ["site1.com", "2", "1"]
            assert source_rows["site2.com"] == ["site2.com", "1", "1"]

            tags = screen.query_one("#tags-table", DataTable)
            tag_rows = {
                str(tags.get_row(key)[0]): tags.get_row(key)[1] for key in tags.rows
            }
            assert tag_rows["python"] == "2"
            assert tag_rows["go"] == "1"

    @pytest.mark.asyncio
    async def test_drill_into_tag_opens_snapshot_list(
        self, populated_index: DocumentIndex
    ) -> None:
        """Selecting a tag row opens a read-only preset article list."""
        client = Mock()
        client.index = populated_index
        app = _HostApp(client=client)
        async with app.run_test() as pilot:
            app.push_screen(DashboardScreen())
            await pilot.pause()
            table = app.screen.query_one("#tags-table", DataTable)
            table.focus()
            table.cursor_coordinate = Coordinate(0, 0)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()

            assert isinstance(app.screen, ArticleListScreen)
            assert app.screen.title_override == "#python"
            assert app.screen.category == "custom"
            ids = {a["id"] for a in app.screen.articles}
            assert ids == {"1", "2"}

    @pytest.mark.asyncio
    async def test_drill_into_source_and_empty_bucket_notifies(
        self, populated_index: DocumentIndex
    ) -> None:
        """Selecting a source opens a snapshot; an empty aging bucket just notifies."""
        client = Mock()
        client.index = populated_index
        app = _HostApp(client=client)
        async with app.run_test() as pilot:
            app.push_screen(DashboardScreen())
            await pilot.pause()

            sources = app.screen.query_one("#sources-table", DataTable)
            sources.focus()
            sources.cursor_coordinate = Coordinate(SOURCE_ROW_SITE2, 0)  # site2.com
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert isinstance(app.screen, ArticleListScreen)
            assert app.screen.title_override == "site2.com"
            assert [a["id"] for a in app.screen.articles] == ["3"]

            await pilot.press("escape")
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)

            aging = app.screen.query_one("#aging-table", DataTable)
            aging.focus()
            aging.cursor_coordinate = Coordinate(
                AGING_ROW_1_3_DAYS, 0
            )  # "1-3 days", empty
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            # No matching articles: stays on the dashboard
            assert isinstance(app.screen, DashboardScreen)

    @pytest.mark.asyncio
    async def test_drill_into_overview_location_opens_live_list(
        self, populated_index: DocumentIndex
    ) -> None:
        """Selecting an Overview row opens the normal (live) article list."""
        client = Mock()
        client.index = populated_index
        client.get_archive = Mock(return_value=[])
        app = _HostApp(client=client)
        async with app.run_test() as pilot:
            app.push_screen(DashboardScreen())
            await pilot.pause()
            table = app.screen.query_one("#overview-table", DataTable)
            table.focus()
            table.cursor_coordinate = Coordinate(ARCHIVE_ROW, 0)
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause(0.3)
            assert isinstance(app.screen, ArticleListScreen)
            assert app.screen.category == "archive"
            assert app.screen.preset_articles is None

    @pytest.mark.asyncio
    async def test_refresh_recomputes_without_sync(
        self, populated_index: DocumentIndex
    ) -> None:
        """Comma refresh re-reads the index without calling sync_index."""
        client = Mock()
        client.index = populated_index
        client.sync_index = Mock(return_value=0)
        app = _HostApp(client=client)
        async with app.run_test() as pilot:
            app.push_screen(DashboardScreen())
            await pilot.pause()
            await pilot.press("comma")
            await pilot.pause()
            client.sync_index.assert_not_called()

    @pytest.mark.asyncio
    async def test_sync_action_calls_client_and_refreshes(
        self, populated_index: DocumentIndex
    ) -> None:
        """Pressing 's' runs a full sync and refreshes the tables."""
        client = Mock()
        client.index = populated_index
        client.sync_index = Mock(return_value=7)
        app = _HostApp(client=client)
        async with app.run_test() as pilot:
            app.push_screen(DashboardScreen())
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause(0.3)
            client.sync_index.assert_called_once_with(True)

    @pytest.mark.asyncio
    async def test_sync_action_without_index_warns(self) -> None:
        """Pressing 's' with no index attached warns instead of crashing."""
        client = Mock()
        client.index = None
        app = _HostApp(client=client)
        async with app.run_test() as pilot:
            app.push_screen(DashboardScreen())
            await pilot.pause()
            await pilot.press("s")
            await pilot.pause()
            # No exception means the guard clause worked

    @pytest.mark.asyncio
    async def test_back_pops_to_category_list(
        self, populated_index: DocumentIndex
    ) -> None:
        """Escape pops the dashboard off the screen stack."""
        client = Mock()
        client.index = populated_index
        app = _HostApp(client=client)
        async with app.run_test() as pilot:
            app.push_screen(DashboardScreen())
            await pilot.pause()
            assert isinstance(app.screen, DashboardScreen)
            await pilot.press("escape")
            await pilot.pause()
            assert not isinstance(app.screen, DashboardScreen)
