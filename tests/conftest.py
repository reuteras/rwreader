"""Shared pytest fixtures for rwreader tests."""

from pathlib import Path
from unittest.mock import Mock

import pytest


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for config files."""
    config_dir = tmp_path / ".rwreader"
    config_dir.mkdir()
    return config_dir


@pytest.fixture
def clean_environment(monkeypatch):
    """Provide a clean environment without Readwise token."""
    # Remove any existing READWISE_TOKEN from environment
    monkeypatch.delenv("READWISE_TOKEN", raising=False)
    yield
    # Cleanup is automatic with monkeypatch


@pytest.fixture
def mock_readwise_document():
    """Create a mock Readwise Document object with all required fields."""
    doc = Mock()
    doc.id = "test_doc_id"
    doc.title = "Test Document"
    doc.url = "https://example.com/test"
    doc.author = "Test Author"
    doc.site_name = "Example Site"
    doc.word_count = 1000
    doc.created_at = "2024-01-01T00:00:00Z"
    doc.updated_at = "2024-01-02T00:00:00Z"
    doc.published_date = "2024-01-01"
    doc.summary = "Test summary"
    doc.content = "Test content"
    doc.source_url = "https://example.com"
    doc.first_opened_at = ""
    doc.last_opened_at = ""
    doc.location = "new"
    doc.reading_progress = 0
    return doc


@pytest.fixture
def sample_article_dict():
    """Create a sample article dictionary."""
    return {
        "id": "article_123",
        "title": "Sample Article",
        "url": "https://example.com/article",
        "author": "Jane Doe",
        "site_name": "Example Blog",
        "word_count": 1500,
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-02T00:00:00Z",
        "published_date": "2024-01-01",
        "summary": "This is a sample article for testing",
        "content": "Full article content here",
        "source_url": "https://example.com",
        "first_opened_at": "",
        "last_opened_at": "",
        "archived": False,
        "saved_for_later": False,
        "read": False,
        "state": "reading",
        "reading_progress": 0,
    }


@pytest.fixture
def sample_config_data():
    """Create sample configuration data."""
    return {
        "general": {"cache_size": 10000, "default_theme": "dark"},
        "readwise": {"token": "test_token_sample"},
        "display": {"font_size": "medium", "reading_width": 80},
    }


@pytest.fixture(autouse=True)
def reset_logging():
    """Reset logging configuration before each test."""
    import logging

    # Get the root logger
    logger = logging.getLogger()

    # Remove all handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Reset to WARNING level
    logger.setLevel(logging.WARNING)

    yield

    # Cleanup after test
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)
