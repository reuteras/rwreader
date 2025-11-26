"""Integration tests for rwreader TUI application."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from rwreader.ui.app import RWReader


@pytest.fixture
def app_with_mock_client(monkeypatch):
    """Create an app instance with mocked API client."""
    # Mock sys.argv to prevent argparse errors
    monkeypatch.setattr("sys.argv", ["rwreader"])
    app = RWReader()

    # Create mock client with test data
    mock_client = Mock()
    inbox_data = [
        {
            "id": "1",
            "title": "Test Article 1",
            "content": "Test content 1",
            "url": "https://example.com/1",
            "author": "Author 1",
            "site_name": "Example",
            "word_count": 500,
            "reading_progress": 0,
            "location": "inbox",
        },
        {
            "id": "2",
            "title": "Test Article 2",
            "content": "Test content 2",
            "url": "https://example.com/2",
            "author": "Author 2",
            "site_name": "Example",
            "word_count": 1000,
            "reading_progress": 50,
            "location": "inbox",
        },
    ]
    feed_data = [
        {
            "id": "3",
            "title": "Feed Article",
            "content": "Feed content",
            "url": "https://example.com/3",
            "author": "Feed Author",
            "site_name": "Feed Site",
            "word_count": 750,
            "reading_progress": 0,
            "location": "feed",
            "first_opened_at": "",
        },
    ]
    later_data = [
        {
            "id": "4",
            "title": "Later Article",
            "content": "Later content",
            "url": "https://example.com/4",
            "author": "Later Author",
            "word_count": 1200,
            "reading_progress": 25,
            "location": "later",
        },
    ]
    archive_data = [
        {
            "id": "5",
            "title": "Archived Article",
            "content": "Archived content",
            "url": "https://example.com/5",
            "word_count": 600,
            "reading_progress": 100,
            "location": "archive",
        },
    ]

    mock_client.get_inbox = Mock(return_value=inbox_data)
    mock_client.get_feed = Mock(return_value=feed_data)
    mock_client.get_later = Mock(return_value=later_data)
    mock_client.get_archive = Mock(return_value=archive_data)
    mock_client.get_article = AsyncMock(return_value=inbox_data[0])
    mock_client.move_to_archive = Mock(return_value=True)
    mock_client.move_to_later = Mock(return_value=True)
    mock_client.move_to_inbox = Mock(return_value=True)
    mock_client.delete_article = Mock(return_value=True)
    mock_client._category_cache = {
        "inbox": {"data": inbox_data, "last_updated": 0},
        "feed": {"data": feed_data, "last_updated": 0},
        "later": {"data": later_data, "last_updated": 0},
        "archive": {"data": archive_data, "last_updated": 0},
    }
    mock_client.clear_cache = Mock()
    mock_client.close = Mock()

    app.client = mock_client
    return app


@pytest.mark.asyncio
@pytest.mark.integration
async def test_app_startup(app_with_mock_client):
    """Test that app starts successfully."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        assert app.is_running
        await pilot.pause()


@pytest.mark.asyncio
@pytest.mark.skip(reason="Needs refactoring - app doesn't have current_category attribute")
async def test_navigate_between_categories(app_with_mock_client):
    """Test navigating between article categories."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        # TODO: Fix this test - should check screen state instead of app.current_category
        # Should start in Inbox
        assert app.current_category == "inbox"

        # Navigate to Later with L
        await pilot.press("L")
        await pilot.pause()
        assert app.current_category == "later"

        # Navigate to Archive with A
        await pilot.press("A")
        await pilot.pause()
        assert app.current_category == "archive"

        # Navigate to Feed with F
        await pilot.press("F")
        await pilot.pause()
        assert app.current_category == "feed"

        # Navigate back to Inbox with I
        await pilot.press("I")
        await pilot.pause()
        assert app.current_category == "inbox"


@pytest.mark.asyncio
async def test_article_selection_and_viewing(app_with_mock_client):
    """Test selecting and viewing an article."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        # Get articles list
        articles_list = app.query_one("#articles")

        # Should have articles loaded
        assert len(articles_list.children) > 0

        # Select first article (skip header at index 0)
        articles_list.index = 1
        await pilot.pause()

        # Verify article was selected and displayed
        assert app.current_article_id is not None
        assert "Test Article" in app.content_markdown


@pytest.mark.asyncio
async def test_keyboard_navigation_j_k(app_with_mock_client):
    """Test j/k vim-style navigation in article list."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        articles_list = app.query_one("#articles")
        initial_index = articles_list.index

        # Press j to move down
        await pilot.press("j")
        await pilot.pause()

        # Verify moved down
        assert articles_list.index > initial_index

        # Press k to move up
        await pilot.press("k")
        await pilot.pause()

        # Should be back at or near initial position
        assert articles_list.index <= initial_index + 1


@pytest.mark.asyncio
async def test_move_article_to_archive(app_with_mock_client):
    """Test moving an article to archive."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        # Select first article
        articles_list = app.query_one("#articles")
        articles_list.index = 1
        await pilot.pause()

        article_id = app.current_article_id
        assert article_id is not None

        # Press 'a' to move to archive
        await pilot.press("a")
        await pilot.pause()

        # Verify API was called
        app.client.move_to_archive.assert_called()


@pytest.mark.asyncio
async def test_move_article_to_later(app_with_mock_client):
    """Test moving an article to later."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        # Select first article
        articles_list = app.query_one("#articles")
        articles_list.index = 1
        await pilot.pause()

        # Press 'l' to move to later
        await pilot.press("l")
        await pilot.pause()

        # Verify API was called
        app.client.move_to_later.assert_called()


@pytest.mark.asyncio
async def test_move_article_to_inbox(app_with_mock_client):
    """Test moving an article to inbox."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        # Navigate to Later first
        await pilot.press("L")
        await pilot.pause()

        articles_list = app.query_one("#articles")
        if len(articles_list.children) > 1:
            articles_list.index = 1
            await pilot.pause()

            # Press 'i' to move to inbox
            await pilot.press("i")
            await pilot.pause()

            # Verify API was called
            app.client.move_to_inbox.assert_called()


@pytest.mark.asyncio
async def test_pane_navigation_with_tab(app_with_mock_client):
    """Test navigating between panes with Tab."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        # Get initial pane
        nav_list = app.query_one("#navigation")
        nav_list.focus()
        await pilot.pause()
        initial_pane = app.focused

        # Press Tab to move to next pane
        await pilot.press("tab")
        await pilot.pause()

        # Should have moved to different pane
        assert app.focused != initial_pane

        # Press Tab again
        await pilot.press("tab")
        await pilot.pause()

        # Should move again
        next_pane = app.focused
        assert next_pane != initial_pane


@pytest.mark.asyncio
async def test_dark_mode_toggle(app_with_mock_client):
    """Test toggling dark/light mode."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        initial_theme = app.theme

        # Press 'd' to toggle dark mode
        await pilot.press("d")
        await pilot.pause()

        # Theme should have changed
        assert app.theme != initial_theme

        # Toggle back
        await pilot.press("d")
        await pilot.pause()

        # Should be back to original
        assert app.theme == initial_theme


@pytest.mark.asyncio
async def test_show_help(app_with_mock_client):
    """Test showing/hiding help screen."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        # Initial screen should not be help
        assert not (hasattr(app.screen, "id") and app.screen.id == "help")

        # Press 'h' to show help
        await pilot.press("h")
        await pilot.pause()

        # Help screen should be shown
        assert hasattr(app.screen, "id") and app.screen.id == "help"

        # Press 'h' again to hide help
        await pilot.press("h")
        await pilot.pause()

        # Help screen should be gone
        assert not (hasattr(app.screen, "id") and app.screen.id == "help")


@pytest.mark.asyncio
async def test_refresh_data(app_with_mock_client):
    """Test refreshing data with G shortcut."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        # Press 'G' to refresh
        await pilot.press("G")
        await pilot.pause(0.5)

        # Should complete without error
        assert app.is_running


@pytest.mark.asyncio
async def test_show_metadata(app_with_mock_client):
    """Test showing article metadata."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        # Select first article
        articles_list = app.query_one("#articles")
        articles_list.index = 1
        await pilot.pause()

        # Press 'm' to show metadata
        await pilot.press("m")
        await pilot.pause()

        # Just verify it doesn't error (metadata is shown as notification)
        assert app.is_running


@pytest.mark.asyncio
async def test_open_in_browser(app_with_mock_client):
    """Test opening article in browser."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        # Select first article
        articles_list = app.query_one("#articles")
        articles_list.index = 1
        await pilot.pause()

        with patch("webbrowser.open") as mock_open:
            # Press 'o' to open in browser
            await pilot.press("o")
            await pilot.pause()

            # Verify browser open was called
            mock_open.assert_called()


@pytest.mark.asyncio
async def test_clear_content(app_with_mock_client):
    """Test clearing content pane."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        # Select article to populate content
        articles_list = app.query_one("#articles")
        articles_list.index = 1
        await pilot.pause()

        # Verify content is populated
        assert "Test Article" in app.content_markdown

        # Press 'c' to clear
        await pilot.press("c")
        await pilot.pause()

        # Content should be cleared
        assert "Welcome to Readwise Reader TUI" in app.content_markdown


@pytest.mark.asyncio
async def test_next_previous_category(app_with_mock_client):
    """Test J/K for category navigation."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        initial_category = app.current_category

        # Press 'J' to go to next category
        await pilot.press("J")
        await pilot.pause()

        # Category should have changed
        assert app.current_category != initial_category

        # Press 'K' to go to previous category
        await pilot.press("K")
        await pilot.pause()

        # Should be back at initial category
        assert app.current_category == initial_category


@pytest.mark.asyncio
async def test_multiple_article_interactions(app_with_mock_client):
    """Test a sequence of typical user interactions."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        await pilot.pause()

        # 1. Start in Inbox
        assert app.current_category == "inbox"

        # 2. Select first article
        articles_list = app.query_one("#articles")
        articles_list.index = 1
        await pilot.pause()
        article_id_1 = app.current_article_id
        assert article_id_1 is not None

        # 3. Navigate down to next article
        await pilot.press("j")
        await pilot.pause()
        article_id_2 = app.current_article_id
        assert article_id_2 != article_id_1

        # 4. Go to Later category
        await pilot.press("L")
        await pilot.pause()
        assert app.current_category == "later"

        # 5. Go to Archive category
        await pilot.press("A")
        await pilot.pause()
        assert app.current_category == "archive"

        # 6. Go to Feed category
        await pilot.press("F")
        await pilot.pause()
        assert app.current_category == "feed"

        # 7. Back to Inbox
        await pilot.press("I")
        await pilot.pause()
        assert app.current_category == "inbox"
