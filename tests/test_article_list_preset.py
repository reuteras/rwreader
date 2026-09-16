"""Tests for ArticleListScreen's preset/snapshot mode used by the dashboard."""

from unittest.mock import Mock

import pytest
from textual.app import App
from textual.widgets import ListView, Static

from rwreader.ui.screens.article_list import ArticleListScreen

_PRESET_ARTICLES = [
    {"id": "1", "title": "First", "site_name": "a.com", "read": False},
    {"id": "2", "title": "Second", "site_name": "b.com", "read": True},
]


class _HostApp(App[None]):
    """Minimal app used to host ArticleListScreen under test."""

    def __init__(self, client: Mock | None = None) -> None:
        super().__init__()
        self.client = client


class TestPresetArticleList:
    """Tests for the preset_articles / title constructor options."""

    @pytest.mark.asyncio
    async def test_populates_without_client_and_uses_title_override(self) -> None:
        """A preset list needs no client call and shows the given title."""
        client = Mock()
        app = _HostApp(client=client)
        async with app.run_test() as pilot:
            app.push_screen(
                ArticleListScreen(
                    category="custom",
                    preset_articles=_PRESET_ARTICLES,
                    title="#python",
                )
            )
            await pilot.pause()
            screen = app.screen
            assert isinstance(screen, ArticleListScreen)
            assert screen.articles == _PRESET_ARTICLES
            title = screen.query_one("#category_title", Static)
            assert "#python" in str(title.render())
            list_view = screen.query_one("#article_list", ListView)
            assert len(list_view.children) == len(_PRESET_ARTICLES)
            client.get_inbox.assert_not_called()

    @pytest.mark.asyncio
    async def test_refresh_and_load_more_are_no_ops(self) -> None:
        """Refresh and load-more notify instead of hitting the API."""
        client = Mock()
        app = _HostApp(client=client)
        async with app.run_test() as pilot:
            app.push_screen(
                ArticleListScreen(category="custom", preset_articles=_PRESET_ARTICLES)
            )
            await pilot.pause()
            await pilot.press("comma")
            await pilot.pause()
            await pilot.press("space")
            await pilot.pause()
            client.clear_cache.assert_not_called()
            client.get_inbox.assert_not_called()

    @pytest.mark.asyncio
    async def test_move_removes_item_from_snapshot(self) -> None:
        """A successful move always drops the item from a preset list."""
        client = Mock()
        client.move_to_archive = Mock(return_value=True)
        app = _HostApp(client=client)
        async with app.run_test() as pilot:
            screen = ArticleListScreen(
                category="custom", preset_articles=list(_PRESET_ARTICLES)
            )
            app.push_screen(screen)
            await pilot.pause()
            list_view = screen.query_one("#article_list", ListView)
            list_view.index = 0
            await pilot.pause()
            await pilot.press("a")
            await pilot.pause()
            assert [a["id"] for a in screen.articles] == ["2"]
            client.move_to_archive.assert_called_once_with(article_id="1")

    @pytest.mark.asyncio
    async def test_default_title_falls_back_to_category(self) -> None:
        """Without a title override, the category name is used, upper-cased."""
        app = _HostApp(client=Mock())
        async with app.run_test() as pilot:
            screen = ArticleListScreen(category="inbox", preset_articles=[])
            app.push_screen(screen)
            await pilot.pause()
            title = screen.query_one("#category_title", Static)
            assert "INBOX" in str(title.render())
