"""Tests for the client module."""

import datetime
import time
from unittest.mock import Mock, patch

import pytest

from rwreader.client import ReadwiseClient, create_readwise_client

# Test constants
CACHE_EXPIRY_SECONDS = 3600
TIMEOUT_SECONDS = 30
ARTICLE_COUNT_2 = 2
ARTICLE_COUNT_3 = 3
SECONDS_IN_DAY = 86300
WEEK_DAYS_MIN = 6
WEEK_DAYS_MAX = 7
MONTH_DAYS_MIN = 30
MONTH_DAYS_MAX = 31
YEAR_DAYS_MIN = 364
YEAR_DAYS_MAX = 365


@pytest.fixture
def mock_document() -> Mock:
    """Create a mock Document object."""
    doc = Mock()
    doc.id = "doc_123"
    doc.title = "Test Article"
    doc.url = "https://example.com/article"
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
def mock_readwise_api() -> Mock:
    """Create a mock ReadwiseReader API."""
    with patch("rwreader.client.ReadwiseReader") as mock_api:
        yield mock_api


class TestCreateReadwiseClient:
    """Test cases for create_readwise_client function."""

    @pytest.mark.asyncio
    async def test_create_readwise_client(self) -> None:
        """Test creating ReadwiseClient asynchronously."""
        with patch.dict("os.environ", {}, clear=True):
            with patch("rwreader.client.ReadwiseReader"):
                client = await create_readwise_client(token="test_token")

                assert isinstance(client, ReadwiseClient)
                assert client.token == "test_token"


class TestReadwiseClient:
    """Test cases for ReadwiseClient class."""

    @patch("rwreader.client.ReadwiseReader")
    def test_init(self, mock_api: Mock) -> None:
        """Test ReadwiseClient initialization."""
        with patch.dict("os.environ", {}, clear=True):
            client = ReadwiseClient(token="test_token_123")

            assert client.token == "test_token_123"
            assert client._cache_expiry == CACHE_EXPIRY_SECONDS
            assert client._timeout == TIMEOUT_SECONDS
            assert "inbox" in client._category_cache
            assert "feed" in client._category_cache
            assert "later" in client._category_cache
            assert "archive" in client._category_cache

    @patch("rwreader.client.ReadwiseReader")
    def test_get_inbox_from_cache(self, mock_api: Mock, mock_document: Mock) -> None:
        """Test getting inbox articles from cache."""
        with patch.dict("os.environ", {}, clear=True):
            client = ReadwiseClient(token="test_token")

            # Pre-populate cache
            client._category_cache["inbox"]["data"] = [
                {"id": "1", "title": "Article 1"},
                {"id": "2", "title": "Article 2"},
            ]
            client._category_cache["inbox"]["last_updated"] = time.time()

            articles = client.get_inbox()

            assert len(articles) == ARTICLE_COUNT_2
            assert articles[0]["id"] == "1"
            # Should not call API since cache is fresh
            mock_api.return_value.get_documents.assert_not_called()

    @patch("rwreader.client.ReadwiseReader")
    def test_get_inbox_fresh_data(
        self, mock_api_class: Mock, mock_document: Mock
    ) -> None:
        """Test getting inbox articles with fresh API call."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_api.get_documents.return_value = [mock_document]

            client = ReadwiseClient(token="test_token")
            articles = client.get_inbox(refresh=True)

            assert len(articles) == 1
            assert articles[0]["id"] == "doc_123"
            assert articles[0]["title"] == "Test Article"
            mock_api.get_documents.assert_called_once_with(location="new")

    @patch("rwreader.client.ReadwiseReader")
    def test_get_feed(self, mock_api_class: Mock, mock_document: Mock) -> None:
        """Test getting feed articles."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_api.get_documents.return_value = [mock_document]

            client = ReadwiseClient(token="test_token")
            articles = client.get_feed(refresh=True)

            assert len(articles) == 1
            mock_api.get_documents.assert_called_once_with(location="feed")

    @patch("rwreader.client.ReadwiseReader")
    def test_get_later(self, mock_api_class: Mock, mock_document: Mock) -> None:
        """Test getting later articles."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_api.get_documents.return_value = [mock_document]

            client = ReadwiseClient(token="test_token")
            articles = client.get_later(refresh=True)

            assert len(articles) == 1
            mock_api.get_documents.assert_called_once_with(location="later")

    @patch("rwreader.client.ReadwiseReader")
    def test_get_archive(self, mock_api_class: Mock, mock_document: Mock) -> None:
        """Test getting archive articles."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_api.get_documents.return_value = [mock_document]

            client = ReadwiseClient(token="test_token")
            articles = client.get_archive(refresh=True, timeframe="week")

            assert len(articles) == 1
            # Verify updated_after parameter was passed
            call_args = mock_api.get_documents.call_args
            assert call_args[1]["location"] == "archive"
            assert "updated_after" in call_args[1]

    @patch("rwreader.client.ReadwiseReader")
    def test_get_archive_with_limit(
        self, mock_api_class: Mock, mock_document: Mock
    ) -> None:
        """Test getting archive articles with limit."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = Mock()
            mock_api_class.return_value = mock_api

            # Create multiple mock documents
            docs = []
            for i in range(5):
                doc = Mock()
                doc.id = f"doc_{i}"
                doc.title = f"Article {i}"
                doc.url = "https://example.com"
                doc.author = "Author"
                doc.site_name = "Site"
                doc.word_count = 1000
                doc.created_at = "2024-01-01T00:00:00Z"
                doc.updated_at = "2024-01-02T00:00:00Z"
                doc.published_date = "2024-01-01"
                doc.summary = "Summary"
                doc.content = "Content"
                doc.source_url = "https://example.com"
                doc.first_opened_at = ""
                doc.last_opened_at = ""
                doc.location = "archive"
                doc.reading_progress = 0
                docs.append(doc)

            mock_api.get_documents.return_value = docs

            client = ReadwiseClient(token="test_token")
            articles = client.get_archive(refresh=True, limit=ARTICLE_COUNT_3)

            assert len(articles) == ARTICLE_COUNT_3
            assert articles[0]["id"] == "doc_0"

    @patch("rwreader.client.ReadwiseReader")
    def test_get_date_for_timeframe(self, mock_api: Mock) -> None:
        """Test _get_date_for_timeframe method."""
        with patch.dict("os.environ", {}, clear=True):
            client = ReadwiseClient(token="test_token")

            now = datetime.datetime.now()

            day_date = client._get_date_for_timeframe("day")
            # Check within a small margin for timing issues
            assert 0 <= (now - day_date).days <= 1
            assert (now - day_date).total_seconds() >= SECONDS_IN_DAY  # At least ~23.9 hours

            week_date = client._get_date_for_timeframe("week")
            assert WEEK_DAYS_MIN <= (now - week_date).days <= WEEK_DAYS_MAX

            month_date = client._get_date_for_timeframe("month")
            assert MONTH_DAYS_MIN <= (now - month_date).days <= MONTH_DAYS_MAX

            year_date = client._get_date_for_timeframe("year")
            assert YEAR_DAYS_MIN <= (now - year_date).days <= YEAR_DAYS_MAX

    @patch("rwreader.client.ReadwiseReader")
    def test_convert_document_to_dict(
        self, mock_api: Mock, mock_document: Mock
    ) -> None:
        """Test converting Document to dict."""
        with patch.dict("os.environ", {}, clear=True):
            client = ReadwiseClient(token="test_token")

            article_dict = client._convert_document_to_dict(mock_document)

            assert article_dict["id"] == "doc_123"
            assert article_dict["title"] == "Test Article"
            assert article_dict["url"] == "https://example.com/article"
            assert article_dict["author"] == "Test Author"
            assert article_dict["archived"] is False
            assert article_dict["saved_for_later"] is False

    @patch("rwreader.client.ReadwiseReader")
    def test_convert_document_to_dict_archived(self, mock_api: Mock) -> None:
        """Test converting archived Document to dict."""
        with patch.dict("os.environ", {}, clear=True):
            doc = Mock()
            doc.id = "archived_123"
            doc.title = "Archived Article"
            doc.location = "archive"
            doc.url = "https://example.com"
            doc.author = ""
            doc.site_name = ""
            doc.word_count = 500
            doc.created_at = ""
            doc.updated_at = ""
            doc.published_date = ""
            doc.summary = ""
            doc.content = ""
            doc.source_url = ""
            doc.first_opened_at = ""
            doc.last_opened_at = ""
            doc.reading_progress = 100

            client = ReadwiseClient(token="test_token")
            article_dict = client._convert_document_to_dict(doc)

            assert article_dict["archived"] is True
            assert article_dict["read"] is True

    @patch("rwreader.client.ReadwiseReader")
    @patch("requests.get")
    def test_get_article(
        self, mock_get: Mock, mock_api_class: Mock, mock_document: Mock
    ) -> None:
        """Test getting a single article by ID."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_api.URL_BASE = "https://readwise.io/api/v3"
            mock_api.get_document_by_id.return_value = mock_document

            # Mock the requests.get call for HTML content
            mock_response = Mock()
            mock_response.json.return_value = {
                "count": 1,
                "results": [{"html_content": "<p>Full HTML content</p>"}],
            }
            mock_response.raise_for_status = Mock()
            mock_get.return_value = mock_response

            client = ReadwiseClient(token="test_token")
            article = client.get_article("doc_123")

            assert article is not None
            assert article["id"] == "doc_123"
            assert article["html_content"] == "<p>Full HTML content</p>"
            mock_api.get_document_by_id.assert_called_once_with(id="doc_123")

    @patch("rwreader.client.ReadwiseReader")
    def test_get_article_from_cache(
        self, mock_api_class: Mock, mock_document: Mock
    ) -> None:
        """Test getting article from cache."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = Mock()
            mock_api_class.return_value = mock_api

            client = ReadwiseClient(token="test_token")

            # Pre-populate article cache
            client._article_cache["cached_123"] = {
                "id": "cached_123",
                "title": "Cached Article",
                "content": "Cached content",
            }

            article = client.get_article("cached_123")

            assert article is not None
            assert article["id"] == "cached_123"
            assert article["title"] == "Cached Article"
            # Should not call API
            mock_api.get_document_by_id.assert_not_called()

    @patch("rwreader.client.readwise.update_document_location")
    @patch("rwreader.client.ReadwiseReader")
    def test_move_to_inbox(self, mock_api: Mock, mock_update: Mock) -> None:
        """Test moving article to inbox."""
        with patch.dict("os.environ", {}, clear=True):
            mock_update.return_value = (True, {"status": "success"})

            client = ReadwiseClient(token="test_token")
            success = client.move_to_inbox("article_123")

            assert success is True
            mock_update.assert_called_once_with(
                document_id="article_123", location="new"
            )

    @patch("rwreader.client.readwise.update_document_location")
    @patch("rwreader.client.ReadwiseReader")
    def test_move_to_later(self, mock_api: Mock, mock_update: Mock) -> None:
        """Test moving article to later."""
        with patch.dict("os.environ", {}, clear=True):
            mock_update.return_value = (True, {"status": "success"})

            client = ReadwiseClient(token="test_token")
            success = client.move_to_later("article_123")

            assert success is True
            mock_update.assert_called_once_with(
                document_id="article_123", location="later"
            )

    @patch("rwreader.client.readwise.update_document_location")
    @patch("rwreader.client.ReadwiseReader")
    def test_move_to_archive(self, mock_api: Mock, mock_update: Mock) -> None:
        """Test moving article to archive."""
        with patch.dict("os.environ", {}, clear=True):
            mock_update.return_value = (True, {"status": "success"})

            client = ReadwiseClient(token="test_token")
            success = client.move_to_archive("article_123")

            assert success is True
            mock_update.assert_called_once_with(
                document_id="article_123", location="archive"
            )

    @patch("rwreader.client.readwise.update_document_location")
    @patch("rwreader.client.ReadwiseReader")
    def test_move_to_inbox_failure(self, mock_api: Mock, mock_update: Mock) -> None:
        """Test failed move operation."""
        with patch.dict("os.environ", {}, clear=True):
            mock_update.return_value = (False, {"error": "API error"})

            client = ReadwiseClient(token="test_token")
            success = client.move_to_inbox("article_123")

            assert success is False

    @patch("rwreader.client.readwise.delete_document")
    @patch("rwreader.client.ReadwiseReader")
    def test_delete_article(self, mock_api: Mock, mock_delete: Mock) -> None:
        """Test deleting an article."""
        with patch.dict("os.environ", {}, clear=True):
            mock_delete.return_value = None  # delete_document doesn't return anything

            client = ReadwiseClient(token="test_token")
            success = client.delete_article("article_123")

            assert success is True
            mock_delete.assert_called_once_with(document_id="article_123")

    @patch("rwreader.client.readwise.delete_document")
    @patch("rwreader.client.ReadwiseReader")
    def test_delete_article_failure(self, mock_api: Mock, mock_delete: Mock) -> None:
        """Test failed delete operation."""
        with patch.dict("os.environ", {}, clear=True):
            mock_delete.side_effect = Exception("API error")

            client = ReadwiseClient(token="test_token")
            success = client.delete_article("article_123")

            assert success is False

    @patch("rwreader.client.ReadwiseReader")
    def test_invalidate_cache(self, mock_api: Mock) -> None:
        """Test cache invalidation."""
        with patch.dict("os.environ", {}, clear=True):
            client = ReadwiseClient(token="test_token")

            # Populate caches
            client._category_cache["inbox"]["data"] = [{"id": "1"}]
            client._category_cache["feed"]["data"] = [{"id": "2"}]

            client._invalidate_cache()

            assert client._category_cache["inbox"]["data"] == []
            assert client._category_cache["feed"]["data"] == []

    @patch("rwreader.client.ReadwiseReader")
    def test_clear_cache(self, mock_api: Mock) -> None:
        """Test clearing entire cache including article cache."""
        with patch.dict("os.environ", {}, clear=True):
            client = ReadwiseClient(token="test_token")

            # Populate caches
            client._category_cache["inbox"]["data"] = [{"id": "1"}]
            client._article_cache["article_1"] = {"id": "article_1"}

            client.clear_cache()

            assert client._category_cache["inbox"]["data"] == []
            assert len(client._article_cache) == 0

    @patch("rwreader.client.ReadwiseReader")
    def test_get_feed_count(self, mock_api_class: Mock) -> None:
        """Test getting feed count."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = Mock()
            mock_api_class.return_value = mock_api

            # Create mock documents with unread articles
            docs = []
            for i in range(3):
                doc = Mock()
                doc.first_opened_at = "" if i < 2 else "2024-01-01"  # 2 unread
                docs.append(doc)

            mock_api.get_documents.return_value = docs

            client = ReadwiseClient(token="test_token")
            count = client.get_feed_count()

            assert count == 2

    @patch("rwreader.client.ReadwiseReader")
    def test_get_later_count(self, mock_api_class: Mock) -> None:
        """Test getting later count."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = Mock()
            mock_api_class.return_value = mock_api

            # Create 5 mock documents
            docs = [Mock() for _ in range(5)]
            mock_api.get_documents.return_value = docs

            client = ReadwiseClient(token="test_token")
            count = client.get_later_count()

            assert count == 5

    @patch("rwreader.client.ReadwiseReader")
    def test_close(self, mock_api: Mock) -> None:
        """Test closing the client."""
        with patch.dict("os.environ", {}, clear=True):
            client = ReadwiseClient(token="test_token")

            # Mock the executor
            client._executor = Mock()

            client.close()

            client._executor.shutdown.assert_called_once_with(wait=False)

    @patch("rwreader.client.ReadwiseReader")
    def test_cache_expiry(self, mock_api_class: Mock, mock_document: Mock) -> None:
        """Test that expired cache triggers fresh API call."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = Mock()
            mock_api_class.return_value = mock_api
            mock_api.get_documents.return_value = [mock_document]

            client = ReadwiseClient(token="test_token")

            # Populate cache with old timestamp
            client._category_cache["inbox"]["data"] = [{"id": "old"}]
            client._category_cache["inbox"]["last_updated"] = time.time() - 7200  # 2 hours ago

            articles = client.get_inbox()

            # Should fetch fresh data since cache is expired
            mock_api.get_documents.assert_called_once()
            assert len(articles) == 1
            assert articles[0]["id"] == "doc_123"
