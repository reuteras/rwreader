# Implementation Examples: Modernizing rwreader

This file provides practical code examples for implementing the recommendations from TEXTUAL_ANALYSIS.md.

---

## 1. ADD UNIT TESTS

### Test Structure Setup

```bash
# Create tests directory
mkdir -p tests
touch tests/__init__.py
```

### tests/test_client.py

```python
"""Unit tests for rwreader client."""

import unittest
from unittest import mock
from rwreader.client import Client, ReadwiseError, ReadwiseAuthError


class TestReadwiseClient(unittest.TestCase):
    """Test suite for Readwise API client."""

    def setUp(self):
        """Set up test fixtures."""
        self.mock_session = mock.Mock()
        self.client = Client("test_token", session=self.mock_session)

    def test_get_articles_success(self):
        """Test successful article retrieval."""
        expected_articles = [
            {"id": 1, "title": "Article 1"},
            {"id": 2, "title": "Article 2"},
        ]
        
        response = mock.Mock()
        response.status_code = 200
        response.json.return_value = {"results": expected_articles}
        
        self.mock_session.get = mock.Mock(return_value=response)
        
        articles = self.client.get_articles()
        
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]["title"], "Article 1")
        self.mock_session.get.assert_called_once()

    def test_get_articles_unauthorized(self):
        """Test authentication failure."""
        response = mock.Mock()
        response.status_code = 401
        response.json.return_value = {"error": "Unauthorized"}
        
        self.mock_session.get = mock.Mock(return_value=response)
        
        with self.assertRaises(ReadwiseAuthError):
            self.client.get_articles()

    def test_get_articles_timeout(self):
        """Test timeout handling."""
        import requests
        self.mock_session.get = mock.Mock(
            side_effect=requests.Timeout("Connection timeout")
        )
        
        with self.assertRaises(requests.Timeout):
            self.client.get_articles()

    def test_move_article_success(self):
        """Test moving article to different location."""
        response = mock.Mock()
        response.status_code = 204
        
        self.mock_session.patch = mock.Mock(return_value=response)
        
        result = self.client.move_article(1, "archive")
        
        self.assertTrue(result)
        self.mock_session.patch.assert_called_once()

    def test_api_error_with_message(self):
        """Test API error with error message."""
        response = mock.Mock()
        response.status_code = 400
        response.json.return_value = {"error_message": "Bad request"}
        
        self.mock_session.get = mock.Mock(return_value=response)
        
        with self.assertRaises(ReadwiseError) as context:
            self.client.get_articles()
        
        self.assertIn("Bad request", str(context.exception))


class TestReadwiseClientIntegration(unittest.TestCase):
    """Integration tests (use real session if available)."""

    @unittest.skip("Requires real API token")
    def test_real_api_call(self):
        """Test against real Readwise API."""
        client = Client("real_token")
        articles = client.get_articles(limit=1)
        self.assertIsInstance(articles, list)


if __name__ == "__main__":
    unittest.main()
```

### tests/test_cache.py

```python
"""Unit tests for rwreader cache."""

import unittest
import time
from rwreader.cache import Cache


class TestCache(unittest.TestCase):
    """Test suite for caching functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.cache = Cache(ttl=2)  # 2 second TTL

    def test_cache_hit(self):
        """Test cache hit returns cached value."""
        self.cache.set("key1", "value1")
        result = self.cache.get("key1")
        self.assertEqual(result, "value1")

    def test_cache_miss(self):
        """Test cache miss returns None."""
        result = self.cache.get("nonexistent")
        self.assertIsNone(result)

    def test_cache_expiry(self):
        """Test cache entry expires after TTL."""
        self.cache.set("key1", "value1")
        
        # Wait for TTL to expire
        time.sleep(2.1)
        
        result = self.cache.get("key1")
        self.assertIsNone(result)

    def test_cache_clear(self):
        """Test clearing cache."""
        self.cache.set("key1", "value1")
        self.cache.set("key2", "value2")
        
        self.cache.clear()
        
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))

    def test_cache_update(self):
        """Test updating cached value."""
        self.cache.set("key1", "value1")
        self.cache.set("key1", "value2")
        
        result = self.cache.get("key1")
        self.assertEqual(result, "value2")


if __name__ == "__main__":
    unittest.main()
```

### tests/test_config.py

```python
"""Unit tests for rwreader configuration."""

import unittest
import tempfile
import os
from pathlib import Path
from rwreader.config import Config


class TestConfiguration(unittest.TestCase):
    """Test suite for configuration management."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.config_file = Path(self.temp_dir) / "config.toml"

    def tearDown(self):
        """Clean up test fixtures."""
        import shutil
        shutil.rmtree(self.temp_dir)

    def test_load_valid_config(self):
        """Test loading valid TOML config."""
        config_content = """
[general]
log_level = "info"

[readwise]
token = "test_token_123"
"""
        self.config_file.write_text(config_content)
        
        config = Config(str(self.config_file))
        
        self.assertEqual(config.log_level, "info")
        self.assertEqual(config.token, "test_token_123")

    def test_missing_required_fields(self):
        """Test error when required fields missing."""
        config_content = """
[general]
log_level = "info"
"""
        self.config_file.write_text(config_content)
        
        with self.assertRaises(ValueError):
            Config(str(self.config_file))

    def test_env_override(self):
        """Test environment variable override."""
        config_content = """
[general]
log_level = "info"

[readwise]
token = "config_token"
"""
        self.config_file.write_text(config_content)
        
        # Set environment variable
        os.environ["READWISE_TOKEN"] = "env_token"
        
        config = Config(str(self.config_file))
        
        # Environment variable should override config file
        self.assertEqual(config.token, "env_token")
        
        # Cleanup
        del os.environ["READWISE_TOKEN"]

    def test_1password_integration(self):
        """Test 1Password CLI integration."""
        # This would require mocking the subprocess call
        from unittest import mock
        
        config_content = """
[readwise]
token = "op read op://vault/item/token"
"""
        self.config_file.write_text(config_content)
        
        with mock.patch("subprocess.run") as mock_run:
            mock_run.return_value.stdout = b"secret_token_from_1password"
            
            config = Config(str(self.config_file))
            # Assertion depends on implementation
            self.assertIsNotNone(config.token)


if __name__ == "__main__":
    unittest.main()
```

### Add to pyproject.toml

```toml
[dependency-groups]
dev = [
    "ruff>=0.9.10",
    "textual-dev>=1.7.0",
    "pytest>=7.0.0",      # Add this
    "pytest-cov>=4.0.0",  # Add this for coverage
]

[tool.pytest.ini_options]
minversion = "6.0"
testpaths = ["tests"]
python_files = ["test_*.py"]
addopts = "--cov=src/rwreader --cov-report=html --cov-report=term-missing"

[tool.coverage.run]
source = ["src/rwreader"]
omit = ["*/tests/*"]
```

### Run tests

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/rwreader --cov-report=html

# Run specific test file
pytest tests/test_client.py -v

# Run specific test
pytest tests/test_client.py::TestReadwiseClient::test_get_articles_success -v
```

---

## 2. UPDATE TEXTUAL VERSION

### Update pyproject.toml for Textual version

```toml
# Before:
dependencies = [
    "textual>=0.27.0",  # Old version
    ...
]

# After:
dependencies = [
    "textual>=0.85.0",  # New version with modern features
    ...
]
```

### Benefits and Migration Notes

```python
# Textual 0.85.0 brings:
# 1. Better reactive attributes
from textual.reactive import reactive

class ArticleList(Static):
    selected_index = reactive(0)
    
    def watch_selected_index(self, old: int, new: int) -> None:
        """Called automatically when selected_index changes."""
        self.display_article(new)

# 2. Improved CSS support
class MyApp(App):
    CSS = """
    Screen {
        layout: grid;
        grid-size: 3 1;
    }
    
    #navigation {
        width: 20%;
        border: solid blue;
    }
    """

# 3. Better async/await patterns
async def load_articles(self):
    """Load without blocking UI."""
    try:
        articles = await self.client.get_articles_async()
        self.refresh_display()
    except ReadwiseError as e:
        self.notify(f"Error: {e}", severity="error")

# 4. More widgets available
from textual.widgets import DataTable, Tree, TabbedContent
```

---

## 3. ADD EXCEPTION HIERARCHY

### src/rwreader/exceptions.py

```python
"""Custom exceptions for rwreader."""


class ReadwiseError(Exception):
    """Base exception for Readwise API errors."""

    def __init__(self, message: str, status_code: int | None = None):
        """Initialize exception.
        
        Args:
            message: Error message
            status_code: HTTP status code if applicable
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ReadwiseAuthError(ReadwiseError):
    """Raised when authentication fails (401)."""

    pass


class ReadwiseNotFound(ReadwiseError):
    """Raised when resource not found (404)."""

    pass


class ReadwiseForbidden(ReadwiseError):
    """Raised when access is forbidden (403)."""

    pass


class ReadwiseRateLimit(ReadwiseError):
    """Raised when rate limit is exceeded (429)."""

    def __init__(
        self,
        message: str,
        retry_after: int | None = None,
    ):
        """Initialize rate limit exception.
        
        Args:
            message: Error message
            retry_after: Seconds to wait before retry
        """
        super().__init__(message, 429)
        self.retry_after = retry_after


class ReadwiseValidationError(ReadwiseError):
    """Raised when input validation fails (400)."""

    pass


class ReadwiseServerError(ReadwiseError):
    """Raised when server error occurs (5xx)."""

    pass


class CacheError(Exception):
    """Raised when cache operation fails."""

    pass


class ConfigError(Exception):
    """Raised when configuration is invalid."""

    pass
```

### Update src/rwreader/client.py

```python
"""Readwise API client with proper exception handling."""

from rwreader.exceptions import (
    ReadwiseError,
    ReadwiseAuthError,
    ReadwiseNotFound,
    ReadwiseForbidden,
    ReadwiseRateLimit,
    ReadwiseValidationError,
    ReadwiseServerError,
)


class Client:
    """Readwise API client."""

    def __init__(self, token: str):
        """Initialize client.
        
        Args:
            token: Readwise API token
            
        Raises:
            ValueError: If token is empty
        """
        if not token:
            raise ValueError("Token cannot be empty")
        self.token = token

    def _handle_response(self, response) -> dict:
        """Handle API response and raise appropriate exceptions.
        
        Args:
            response: HTTP response object
            
        Returns:
            Response JSON
            
        Raises:
            ReadwiseAuthError: On 401
            ReadwiseNotFound: On 404
            ReadwiseForbidden: On 403
            ReadwiseRateLimit: On 429
            ReadwiseValidationError: On 400
            ReadwiseServerError: On 5xx
            ReadwiseError: On other errors
        """
        if response.status_code == 200 or response.status_code == 201:
            return response.json()
        
        if response.status_code == 204:
            return {}
        
        error_msg = response.json().get("error_message", "Unknown error")
        
        if response.status_code == 401:
            raise ReadwiseAuthError(f"Authentication failed: {error_msg}", 401)
        
        if response.status_code == 403:
            raise ReadwiseForbidden(f"Access forbidden: {error_msg}", 403)
        
        if response.status_code == 404:
            raise ReadwiseNotFound(f"Resource not found: {error_msg}", 404)
        
        if response.status_code == 400:
            raise ReadwiseValidationError(f"Invalid request: {error_msg}", 400)
        
        if response.status_code == 429:
            retry_after = int(response.headers.get("Retry-After", 60))
            raise ReadwiseRateLimit(
                f"Rate limited: {error_msg}",
                retry_after=retry_after,
            )
        
        if response.status_code >= 500:
            raise ReadwiseServerError(f"Server error: {error_msg}", response.status_code)
        
        raise ReadwiseError(f"API error: {error_msg}", response.status_code)

    def get_articles(self, limit: int = 100) -> list:
        """Get articles with error handling.
        
        Args:
            limit: Maximum articles to retrieve
            
        Returns:
            List of articles
            
        Raises:
            ReadwiseAuthError: If not authenticated
            ReadwiseRateLimit: If rate limited
            ReadwiseServerError: If server error
        """
        try:
            # API call implementation
            pass
        except ReadwiseError:
            raise
        except Exception as e:
            raise ReadwiseError(f"Unexpected error: {e}")
```

---

## 4. ADD TYPE CHECKING (mypy)

### Update pyproject.toml for mypy configuration

```toml
[tool.mypy]
python_version = "3.11"
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
check_untyped_defs = true
warn_unused_ignores = true
show_error_codes = true
show_error_context = true
strict_optional = true

[[tool.mypy.overrides]]
module = [
    "readwise_api.*",  # External dependency
    "tests.*",  # Tests can be less strict
]
ignore_errors = true
```

### Add type hints to client.py

```python
"""Readwise API client with full type hints."""

from typing import Optional, List, Dict, Any
from datetime import datetime
import requests
from rwreader.exceptions import ReadwiseError


class Article:
    """Represents a Readwise article."""

    def __init__(
        self,
        article_id: int,
        title: str,
        url: str,
        author: Optional[str] = None,
        source: Optional[str] = None,
        created_at: Optional[datetime] = None,
    ):
        """Initialize article.
        
        Args:
            article_id: Unique article ID
            title: Article title
            url: Article URL
            author: Article author
            source: Article source/publication
            created_at: When article was created
        """
        self.id: int = article_id
        self.title: str = title
        self.url: str = url
        self.author: Optional[str] = author
        self.source: Optional[str] = source
        self.created_at: Optional[datetime] = created_at

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "id": self.id,
            "title": self.title,
            "url": self.url,
            "author": self.author,
            "source": self.source,
            "created_at": self.created_at,
        }


class Client:
    """Readwise API client with type hints."""

    def __init__(
        self,
        token: str,
        session: Optional[requests.Session] = None,
    ) -> None:
        """Initialize client.
        
        Args:
            token: Readwise API token
            session: Optional requests session
            
        Raises:
            ValueError: If token is empty
        """
        if not token:
            raise ValueError("Token cannot be empty")
        
        self.token: str = token
        self.session: requests.Session = session or requests.Session()
        self.base_url: str = "https://readwise.io/api/v3"

    def get_articles(
        self,
        limit: int = 100,
        offset: int = 0,
        tag: Optional[str] = None,
    ) -> List[Article]:
        """Get articles from Readwise.
        
        Args:
            limit: Maximum articles to return (default: 100)
            offset: Offset for pagination (default: 0)
            tag: Optional tag to filter articles
            
        Returns:
            List of Article objects
            
        Raises:
            ReadwiseError: On API error
        """
        # Implementation with type hints...
        articles: List[Article] = []
        return articles

    def move_article(
        self,
        article_id: int,
        location: str,
    ) -> bool:
        """Move article to different location.
        
        Args:
            article_id: ID of article to move
            location: Target location (inbox, archive, later)
            
        Returns:
            True if successful
            
        Raises:
            ReadwiseError: On API error
            ValueError: If location is invalid
        """
        valid_locations: List[str] = ["inbox", "archive", "later"]
        if location not in valid_locations:
            raise ValueError(f"Invalid location: {location}")
        
        # Implementation...
        return True
```

### Run type checking

```bash
# Check all code
mypy src/rwreader/

# Check specific file
mypy src/rwreader/client.py

# Show detailed errors
mypy src/rwreader/ --show-error-codes --show-error-context
```

---

## 5. IMPLEMENT REACTIVE ATTRIBUTES

### Update src/rwreader/ui/app.py

```python
"""Main TUI application with reactive attributes."""

from textual import on
from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widgets import Header, Footer
from textual.containers import Container


class RwReaderApp(App):
    """Main application with reactive state management."""

    # Reactive attributes
    selected_article_id = reactive(0)
    current_location = reactive("inbox")
    is_loading = reactive(False)

    BINDINGS = [
        ("q", "quit()", "Quit"),
        ("j", "next_article()", "Next"),
        ("k", "prev_article()", "Previous"),
        ("a", "archive_article()", "Archive"),
        ("l", "save_article()", "Later"),
        ("i", "inbox_article()", "Inbox"),
    ]

    def compose(self) -> ComposeResult:
        """Compose UI layout."""
        yield Header()
        with Container(id="main"):
            yield ArticleList(id="article-list")
            yield ArticleViewer(id="article-viewer")
        yield Footer()

    def watch_selected_article_id(
        self,
        old_id: int,
        new_id: int,
    ) -> None:
        """Called when selected article changes.
        
        Args:
            old_id: Previous article ID
            new_id: New article ID
        """
        # Update UI when selection changes
        viewer = self.query_one("#article-viewer", ArticleViewer)
        article = self.get_article(new_id)
        viewer.display_article(article)

    def watch_current_location(
        self,
        old_location: str,
        new_location: str,
    ) -> None:
        """Called when location changes.
        
        Args:
            old_location: Previous location
            new_location: New location
        """
        # Refresh article list for new location
        article_list = self.query_one("#article-list", ArticleList)
        article_list.refresh_articles(new_location)

    def watch_is_loading(
        self,
        old_state: bool,
        new_state: bool,
    ) -> None:
        """Called when loading state changes.
        
        Args:
            old_state: Previous loading state
            new_state: New loading state
        """
        # Show/hide loading indicator
        self.query_one("#loading").display = new_state

    def action_next_article(self) -> None:
        """Move to next article."""
        self.selected_article_id += 1

    def action_prev_article(self) -> None:
        """Move to previous article."""
        if self.selected_article_id > 0:
            self.selected_article_id -= 1

    def action_archive_article(self) -> None:
        """Archive current article."""
        article = self.get_article(self.selected_article_id)
        self.client.move_article(article["id"], "archive")
        self.current_location = "inbox"  # Triggers watch_current_location

    def get_article(self, article_id: int) -> dict:
        """Get article by ID."""
        # Implementation...
        pass
```

---

## 6. ADD PROPER LOGGING

### src/rwreader/logging_config.py

```python
"""Logging configuration for rwreader."""

import logging
import logging.handlers
from pathlib import Path
from typing import Optional


def setup_logging(
    log_level: str = "INFO",
    log_file: Optional[Path] = None,
) -> logging.Logger:
    """Set up logging with console and file handlers.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_file: Optional file path for logging
        
    Returns:
        Configured logger instance
    """
    # Create logger
    logger = logging.getLogger("rwreader")
    logger.setLevel(getattr(logging, log_level.upper()))

    # Format
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
```

### Usage in client.py

```python
"""API client with structured logging."""

import logging
from typing import List

logger = logging.getLogger("rwreader")


class Client:
    """API client."""

    def get_articles(self, limit: int = 100) -> List[dict]:
        """Get articles with logging.
        
        Args:
            limit: Maximum articles
            
        Returns:
            List of articles
        """
        logger.debug(f"Fetching articles with limit={limit}")
        
        try:
            response = self._make_request("GET", "/documents")
            articles = response.json()["results"]
            logger.info(f"Successfully fetched {len(articles)} articles")
            return articles
        except ReadwiseAuthError:
            logger.error("Authentication failed - invalid token")
            raise
        except ReadwiseRateLimit as e:
            logger.warning(f"Rate limited - retry after {e.retry_after}s")
            raise
        except Exception as e:
            logger.exception(f"Unexpected error fetching articles: {e}")
            raise
```

---

## Summary

These implementations provide:

1. **Tests** - Full test coverage patterns
2. **Modern Textual** - Updated version with new features
3. **Exception Hierarchy** - Clean error handling
4. **Type Safety** - Complete type hints
5. **Reactive State** - Automatic UI updates
6. **Logging** - Comprehensive logging

Start with these in priority order and integrate incrementally.

