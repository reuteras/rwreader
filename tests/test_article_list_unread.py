"""Tests for ArticleListScreen's unread-only view backed by the local index."""

from typing import Any
from unittest.mock import Mock

import pytest
from textual.app import App
from textual.widgets import ListView, Static

from rwreader.index import DocumentIndex
from rwreader.ui.screens import article_list
from rwreader.ui.screens.article_list import ArticleListScreen

# Unread archive documents in the fixture index
_UNREAD_ARCHIVE = 2


def _doc(doc_id: str, location: str, opened: str = "") -> dict[str, Any]:
    """Build an index-ready article dict."""
    return {
        "id": doc_id,
        "title": f"Doc {doc_id}",
        "location": location,
        "saved_at": f"2026-01-{int(doc_id):02d}",
        "first_opened_at": opened,
    }


class _HostApp(App[None]):
    """Minimal app used to host ArticleListScreen under test."""

    def __init__(self, client: Mock) -> None:
        super().__init__()
        self.client = client


def _client(index: DocumentIndex | None) -> Mock:
    """Return a mock client whose API calls return empty lists."""
    client = Mock()
    client.index = index
    for name in ("get_inbox", "get_later", "get_shortlist", "get_archive", "get_feed"):
        getattr(client, name).return_value = []
    return client


@pytest.fixture
def index() -> DocumentIndex:
    """An in-memory index with read and unread documents in two locations."""
    idx = DocumentIndex(":memory:")
    idx.upsert_many(
        [
            _doc("1", "archive"),
            _doc("2", "archive", opened="2026-02-01"),
            _doc("3", "archive"),
            _doc("4", "new"),
        ]
    )
    return idx


async def _open(app: _HostApp, pilot: Any, category: str) -> ArticleListScreen:
    """Push the list screen for ``category`` and wait for the initial load."""
    screen = ArticleListScreen(category=category)
    app.push_screen(screen)
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()
    return screen


async def _press(app: _HostApp, pilot: Any, key: str) -> None:
    """Press a key and wait for any load it triggers."""
    await pilot.press(key)
    await pilot.pause()
    await app.workers.wait_for_complete()
    await pilot.pause()


class TestUnreadOnly:
    """Tests for the ``u`` unread-only toggle."""

    @pytest.mark.asyncio
    async def test_toggle_shows_only_unopened_from_index(
        self, index: DocumentIndex
    ) -> None:
        """Only never-opened documents in the category's location are listed."""
        app = _HostApp(_client(index))
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "archive")
            await _press(app, pilot, "u")
            assert screen.unread_only
            assert [a["id"] for a in screen.articles] == ["3", "1"]
            assert (
                len(screen.query_one("#article_list", ListView).children)
                == _UNREAD_ARCHIVE
            )
            title = str(screen.query_one("#category_title", Static).render())
            assert "UNREAD (2 of 2)" in title

    @pytest.mark.asyncio
    async def test_toggle_back_uses_api(self, index: DocumentIndex) -> None:
        """Toggling off returns to the normal API-backed list."""
        client = _client(index)
        app = _HostApp(client)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "archive")
            await _press(app, pilot, "u")
            client.get_archive.reset_mock()
            await _press(app, pilot, "u")
            assert not screen.unread_only
            assert screen.articles == []
            client.get_archive.assert_called_once()

    @pytest.mark.asyncio
    async def test_inbox_maps_to_new_location(self, index: DocumentIndex) -> None:
        """The inbox category reads the index's ``new`` location."""
        app = _HostApp(_client(index))
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "inbox")
            await _press(app, pilot, "u")
            assert [a["id"] for a in screen.articles] == ["4"]

    @pytest.mark.asyncio
    async def test_refresh_fetches_category_before_querying(
        self, index: DocumentIndex
    ) -> None:
        """Refresh pulls the category from the API so the index is current."""
        client = _client(index)
        app = _HostApp(client)
        async with app.run_test() as pilot:
            await _open(app, pilot, "archive")
            await _press(app, pilot, "u")
            client.get_archive.reset_mock()
            await _press(app, pilot, "comma")
            client.get_archive.assert_called_once_with(refresh=True)

    @pytest.mark.asyncio
    async def test_load_more_grows_page_and_keeps_cursor(
        self, index: DocumentIndex, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Space reads the next page and keeps the highlighted position."""
        monkeypatch.setattr(article_list, "UNREAD_PAGE_SIZE", 1)
        app = _HostApp(_client(index))
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "archive")
            await _press(app, pilot, "u")
            assert [a["id"] for a in screen.articles] == ["3"]
            await _press(app, pilot, "space")
            assert [a["id"] for a in screen.articles] == ["3", "1"]
            list_view = screen.query_one("#article_list", ListView)
            list_view.index = 1
            await _press(app, pilot, "space")
            assert len(screen.articles) == _UNREAD_ARCHIVE
            assert list_view.index == 1

    @pytest.mark.asyncio
    async def test_back_does_not_report_unread_count(
        self, index: DocumentIndex
    ) -> None:
        """Leaving the unread view must not overwrite the category total."""
        app = _HostApp(_client(index))
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "archive")
            await _press(app, pilot, "u")
            results: list[Any] = []
            screen.dismiss = results.append  # type: ignore[method-assign,assignment]
            screen.action_back()
            assert results == [{"category": "archive"}]

    @pytest.mark.asyncio
    async def test_requires_index(self) -> None:
        """Without the local index the toggle stays off."""
        app = _HostApp(_client(None))
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "archive")
            await _press(app, pilot, "u")
            assert not screen.unread_only

    @pytest.mark.asyncio
    async def test_not_available_for_feed(self, index: DocumentIndex) -> None:
        """Feed is already unread-only, so the toggle does nothing there."""
        app = _HostApp(_client(index))
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "feed")
            await _press(app, pilot, "u")
            assert not screen.unread_only


class TestToggleSeen:
    """Tests for the ``U`` read/unread toggle in the list."""

    @pytest.mark.asyncio
    async def test_marking_read_drops_from_unread_view(
        self, index: DocumentIndex
    ) -> None:
        """In the unread view a newly read article leaves the list."""
        client = _client(index)
        client.mark_seen.return_value = True
        app = _HostApp(client)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "archive")
            await _press(app, pilot, "u")
            await _press(app, pilot, "U")
            client.mark_seen.assert_called_once_with(article_id="3", seen=True)
            assert [a["id"] for a in screen.articles] == ["1"]
            title = str(screen.query_one("#category_title", Static).render())
            assert "UNREAD (1 of 1)" in title

    @pytest.mark.asyncio
    async def test_marking_unread_keeps_article_in_normal_view(self) -> None:
        """Outside the unread view an opened article is marked unread in place."""
        client = _client(None)
        client.get_archive.return_value = [_doc("2", "archive", opened="2026-02-01")]
        client.mark_seen.return_value = True
        app = _HostApp(client)
        async with app.run_test() as pilot:
            screen = await _open(app, pilot, "archive")
            await _press(app, pilot, "U")
            client.mark_seen.assert_called_once_with(article_id="2", seen=False)
            assert screen.articles[0]["first_opened_at"] == ""
