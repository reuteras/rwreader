"""Integration tests for rwreader TUI application."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from rwreader.ui.app import RWReader


@pytest.fixture
def mock_client():
    """Create a mock Readwise client with test data."""
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
            "first_opened_at": "",
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
            "first_opened_at": "",
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
            "first_opened_at": "",
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
            "first_opened_at": "2024-01-01",
        },
    ]

    mock_client.get_inbox = Mock(return_value=inbox_data)
    mock_client.get_feed = Mock(return_value=feed_data)
    mock_client.get_later = Mock(return_value=later_data)
    mock_client.get_archive = Mock(return_value=archive_data)
    mock_client.get_article = Mock(return_value=inbox_data[0])
    mock_client.move_to_archive = Mock(return_value=True)
    mock_client.move_to_later = Mock(return_value=True)
    mock_client.move_to_inbox = Mock(return_value=True)
    mock_client.delete_article = Mock(return_value=True)
    mock_client.clear_cache = Mock()
    mock_client.close = Mock()
    return mock_client


@pytest.fixture
def app_with_mock_client(monkeypatch, mock_client):
    """Create an app instance with mocked API client."""
    # Mock sys.argv to prevent argparse errors
    monkeypatch.setattr("sys.argv", ["rwreader"])

    # Patch create_readwise_client to return our mock
    async def mock_create_client(token):
        return mock_client

    with patch(
        "rwreader.ui.app.create_readwise_client", side_effect=mock_create_client
    ):
        app = RWReader()
        return app


@pytest.mark.asyncio
async def test_app_initialization(app_with_mock_client):
    """Test that app initializes with correct settings."""
    app = app_with_mock_client
    assert app is not None
    assert hasattr(app, "configuration")
    assert app.configuration.default_theme in ["dark", "light"]


@pytest.mark.asyncio
async def test_dark_mode_toggle(app_with_mock_client, mock_client):
    """Test toggling dark/light mode."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        # Set the client explicitly since on_ready hasn't run yet
        app.client = mock_client
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
async def test_show_help(app_with_mock_client, mock_client):
    """Test showing/hiding help screen."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        app.client = mock_client
        await pilot.pause()

        # Get the current screen type
        from rwreader.ui.screens.help import HelpScreen

        initial_screen_type = type(app.screen)

        # Press 'h' to show help
        await pilot.press("h")
        await pilot.pause()

        # Help screen should be shown
        assert isinstance(app.screen, HelpScreen)

        # Press escape to hide help (help screen's on_key handler pops on non-nav keys)
        await pilot.press("escape")
        await pilot.pause()

        # Should be back to the initial screen type
        assert type(app.screen) == initial_screen_type


@pytest.mark.asyncio
async def test_quit_action(app_with_mock_client, mock_client):
    """Test that quit action works."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        app.client = mock_client
        await pilot.pause()

        # Press 'q' to quit
        await pilot.press("q")
        await pilot.pause()

        # App should have stopped
        assert not app.is_running
