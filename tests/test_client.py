"""Tests for the client module."""

import datetime
import time
from collections.abc import Generator
from unittest.mock import Mock, patch

import pytest
import requests

from rwreader.client import ReadwiseClient, create_readwise_client
from rwreader.index import DocumentIndex
from rwreader.sync import AdaptivePacer, SyncProgress

# Test constants
CACHE_EXPIRY_SECONDS = 3600
TIMEOUT_SECONDS = 30
ARTICLE_COUNT_2 = 2
ARTICLE_COUNT_3 = 3
ARTICLE_COUNT_5 = 5
SECONDS_IN_DAY = 86300
WEEK_DAYS_MIN = 6
WEEK_DAYS_MAX = 7
MONTH_DAYS_MIN = 30
MONTH_DAYS_MAX = 31
YEAR_DAYS_MIN = 364
YEAR_DAYS_MAX = 365
# Index sync tests
SYNCED_FIRST_PAGE = 2
SYNCED_TOTAL = 3
CALLS_AFTER_ONE_RATE_LIMIT = 2
CALLS_UNTIL_GIVE_UP = 6  # first try + 5 retries


def _list_page(ids: list[str], cursor: str | None) -> Mock:
    """Build a mocked ``/list/`` response holding documents with ``ids``."""
    results = [
        {
            "id": doc_id,
            "url": f"https://readwise.io/{doc_id}",
            "title": f"Doc {doc_id}",
            "author": None,
            "source": None,
            "category": "article",
            "location": "new",
            "tags": None,
            "site_name": None,
            "word_count": 10,
            "created_at": "2026-01-01T00:00:00Z",
            "updated_at": "2026-01-01T00:00:00Z",
            "notes": None,
            "published_date": None,
            "summary": None,
            "image_url": None,
            "content": None,
            "source_url": None,
            "parent_id": None,
            "saved_at": "2026-01-01T00:00:00Z",
            "last_moved_at": "2026-01-01T00:00:00Z",
            "reading_progress": 0,
            "first_opened_at": None,
            "last_opened_at": None,
        }
        for doc_id in ids
    ]
    response = Mock(status_code=200, headers={})
    response.json.return_value = {
        "count": len(results),
        "nextPageCursor": cursor,
        "results": results,
    }
    return response


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
def mock_readwise_api() -> Generator[Mock, None, None]:
    """Create a mock ReadwiseReader API."""
    with patch("rwreader.client.ReadwiseReader") as mock_api:
        yield mock_api


class TestCreateReadwiseClient:
    """Test cases for create_readwise_client function."""

    @pytest.mark.asyncio
    async def test_create_readwise_client(self) -> None:
        """Test creating ReadwiseClient asynchronously."""
        with (
            patch.dict("os.environ", {}, clear=True),
            patch("rwreader.client.ReadwiseReader"),
        ):
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
    def test_get_shortlist(self, mock_api_class: Mock, mock_document: Mock) -> None:
        """Test getting shortlist articles."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = mock_api_class.return_value
            mock_api.get_documents.return_value = [mock_document]

            client = ReadwiseClient(token="test_token")
            articles = client.get_shortlist()

            assert len(articles) == 1
            mock_api.get_documents.assert_called_with(location="shortlist")

    @patch("rwreader.client.ReadwiseReader")
    def test_get_more_articles_shortlist_and_unknown(
        self, mock_api_class: Mock, mock_document: Mock
    ) -> None:
        """Load-more refreshes the shortlist and rejects unknown categories."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = mock_api_class.return_value
            mock_api.get_documents.return_value = [mock_document]

            client = ReadwiseClient(token="test_token")
            assert len(client.get_more_articles("shortlist")) == 1
            mock_api.get_documents.assert_called_with(location="shortlist")
            assert client.get_more_articles("bogus") == []

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

            now = datetime.datetime.now(datetime.UTC)

            day_date = client._get_date_for_timeframe("day")
            # Check within a small margin for timing issues
            assert 0 <= (now - day_date).days <= 1
            assert (
                now - day_date
            ).total_seconds() >= SECONDS_IN_DAY  # At least ~23.9 hours

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
    def test_convert_document_to_dict_extra_fields(self, mock_api: Mock) -> None:
        """Location, category, tags, notes and timestamps are preserved."""
        with patch.dict("os.environ", {}, clear=True):
            doc = Mock()
            doc.id = "doc_x"
            doc.title = "Tagged"
            doc.url = "https://example.com"
            doc.author = ""
            doc.site_name = ""
            doc.word_count = 10
            doc.created_at = ""
            doc.updated_at = ""
            doc.published_date = ""
            doc.summary = ""
            doc.content = ""
            doc.source_url = ""
            doc.first_opened_at = ""
            doc.last_opened_at = ""
            doc.location = "shortlist"
            doc.reading_progress = 0
            doc.category = "pdf"
            sec_tag = Mock()
            sec_tag.name = "sec"
            doc.tags = {"sec": sec_tag, "go": {}}
            doc.notes = "a note"
            doc.image_url = "https://example.com/img.png"
            doc.saved_at = "2024-03-01T00:00:00Z"
            doc.last_moved_at = "2024-03-02T00:00:00Z"
            doc.parent_id = "parent"
            doc.source = "reader-web"

            client = ReadwiseClient(token="test_token")
            article = client._convert_document_to_dict(doc)

            assert article["location"] == "shortlist"
            assert article["category"] == "pdf"
            assert article["tags"] == ["go", "sec"]
            assert article["notes"] == "a note"
            assert article["image_url"] == "https://example.com/img.png"
            assert article["saved_at"] == "2024-03-01T00:00:00Z"
            assert article["last_moved_at"] == "2024-03-02T00:00:00Z"
            assert article["parent_id"] == "parent"
            assert article["source"] == "reader-web"
            assert article["archived"] is False
            assert article["saved_for_later"] is False

    @patch("rwreader.client.ReadwiseReader")
    def test_convert_document_to_dict_tolerates_missing_extras(
        self, mock_api: Mock, mock_document: Mock
    ) -> None:
        """Documents without the newer attributes still convert cleanly."""
        with patch.dict("os.environ", {}, clear=True):
            client = ReadwiseClient(token="test_token")
            article = client._convert_document_to_dict(mock_document)
            # Mock() returns Mock objects for unknown attributes; they must not leak
            assert article["category"] == ""
            assert article["tags"] == []
            assert article["notes"] == ""
            assert article["location"] == "new"

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

    @patch("rwreader.client.requests.patch")
    @patch("rwreader.client.ReadwiseReader")
    def test_move_to_shortlist(self, mock_api: Mock, mock_patch: Mock) -> None:
        """Shortlist moves go straight to the v3 update endpoint."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api.return_value.URL_BASE = "https://readwise.io/api/v3"
            mock_patch.return_value = Mock(status_code=200, text="")

            client = ReadwiseClient(token="test_token")
            client._article_cache["article_123"] = {"id": "article_123"}
            success = client.move_to_shortlist("article_123")

            assert success is True
            mock_patch.assert_called_once()
            kwargs = mock_patch.call_args.kwargs
            assert kwargs["url"].endswith("/update/article_123/")
            assert kwargs["json"] == {"location": "shortlist"}
            assert kwargs["headers"]["Authorization"] == "Token test_token"
            assert client._article_cache["article_123"]["location"] == "shortlist"

    @patch("rwreader.client.requests.patch")
    @patch("rwreader.client.ReadwiseReader")
    def test_move_to_shortlist_failure(self, mock_api: Mock, mock_patch: Mock) -> None:
        """A non-2xx response or a network error yields False."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api.return_value.URL_BASE = "https://readwise.io/api/v3"
            client = ReadwiseClient(token="test_token")

            mock_patch.return_value = Mock(status_code=400, text="bad request")
            assert client.move_to_shortlist("article_123") is False

            mock_patch.side_effect = requests.ConnectionError("down")
            assert client.move_to_shortlist("article_123") is False

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
            mock_delete.side_effect = requests.ConnectionError("API error")

            client = ReadwiseClient(token="test_token")
            success = client.delete_article("article_123")

            assert success is False

    @patch("rwreader.client.readwise.delete_document")
    @patch("rwreader.client.readwise.update_document_location")
    @patch("rwreader.client.ReadwiseReader")
    def test_index_write_through(
        self,
        mock_api_class: Mock,
        mock_update: Mock,
        mock_delete: Mock,
        mock_document: Mock,
    ) -> None:
        """Fetches, moves and deletes are mirrored into the local index."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = mock_api_class.return_value
            mock_api.get_documents.return_value = [mock_document]
            mock_update.return_value = (True, {})
            mock_delete.return_value = None

            index = DocumentIndex(":memory:")
            client = ReadwiseClient(token="test_token", index=index)

            client.get_inbox()
            assert index.get("doc_123")["location"] == "new"  # type: ignore[index]

            client.get_archive()
            assert index.count() == 1

            client.move_to_archive("doc_123")
            assert index.get("doc_123")["location"] == "archive"  # type: ignore[index]

            client.move_to_later("doc_123")
            assert index.get("doc_123")["location"] == "later"  # type: ignore[index]

            client.move_to_inbox("doc_123")
            assert index.get("doc_123")["location"] == "new"  # type: ignore[index]

            client.delete_article("doc_123")
            assert index.get("doc_123") is None

            client.close()

    @patch("rwreader.client.ReadwiseReader")
    def test_index_errors_do_not_break_fetch(
        self, mock_api_class: Mock, mock_document: Mock
    ) -> None:
        """A failing index never breaks the API path."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api = mock_api_class.return_value
            mock_api.get_documents.return_value = [mock_document]

            index = Mock()
            index.upsert_many.side_effect = RuntimeError("disk full")
            index.set_location.side_effect = RuntimeError("disk full")
            client = ReadwiseClient(token="test_token", index=index)

            assert len(client.get_inbox()) == 1
            with patch(
                "rwreader.client.readwise.update_document_location",
                return_value=(True, {}),
            ):
                assert client.move_to_archive("doc_123") is True

    @patch("rwreader.client.ReadwiseReader")
    def test_sync_index_full_then_incremental(self, mock_api_class: Mock) -> None:
        """A full sync pages through, prunes and records the sync time."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api_class.return_value.URL_BASE = "https://readwise.io/api/v3"
            index = DocumentIndex(":memory:")
            index.upsert_many([{"id": "stale", "title": "gone remotely"}])
            client = ReadwiseClient(token="test_token", index=index)
            pages = [_list_page(["a", "b"], "cur1"), _list_page(["c"], None)]

            with patch("rwreader.client.requests.get", side_effect=pages) as get:
                written = client.sync_index(pacer=AdaptivePacer(interval=0))

            assert written == SYNCED_TOTAL
            assert get.call_args_list[0].kwargs["params"] == {}
            assert get.call_args_list[1].kwargs["params"] == {"pageCursor": "cur1"}
            assert index.get("stale") is None
            assert index.get("c") is not None
            assert index.last_sync is not None
            assert index.get_sync_state() is None

            first_sync = index.last_sync
            with patch(
                "rwreader.client.requests.get", return_value=_list_page(["a"], None)
            ) as get:
                assert client.sync_index(pacer=AdaptivePacer(interval=0)) == 1
            params = get.call_args.kwargs["params"]
            assert params["updatedAfter"] == first_sync.isoformat()
            assert index.get("b") is not None  # incremental sync never prunes
            client.close()

    @patch("rwreader.client.ReadwiseReader")
    def test_sync_index_backs_off_on_rate_limit(self, mock_api_class: Mock) -> None:
        """A 429 slows the pacer down and the same page is retried."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api_class.return_value.URL_BASE = "https://readwise.io/api/v3"
            client = ReadwiseClient(token="test_token", index=DocumentIndex())
            limited = Mock(status_code=429, headers={"Retry-After": "0"})
            pacer = AdaptivePacer(interval=0.001)
            updates: list[SyncProgress] = []

            with patch(
                "rwreader.client.requests.get",
                side_effect=[limited, _list_page(["a"], None)],
            ) as get:
                written = client.sync_index(
                    full=True, progress=updates.append, pacer=pacer
                )

            assert written == 1
            assert get.call_count == CALLS_AFTER_ONE_RATE_LIMIT
            assert pacer.interval == pytest.approx(0.002)
            assert updates[0].reason == "rate limited"
            assert updates[0].waiting > 0
            assert updates[-1].done is True
            client.close()

    @patch("rwreader.client.ReadwiseReader")
    def test_sync_index_resumes_after_stop(self, mock_api_class: Mock) -> None:
        """Stopping keeps the cursor; the next sync continues from it."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api_class.return_value.URL_BASE = "https://readwise.io/api/v3"
            index = DocumentIndex(":memory:")
            first = ReadwiseClient(token="test_token", index=index)

            def stop_after_first_page(update: SyncProgress) -> None:
                first._stop_sync.set()

            with patch(
                "rwreader.client.requests.get",
                return_value=_list_page(["a", "b"], "cur1"),
            ):
                written = first.sync_index(
                    full=True,
                    progress=stop_after_first_page,
                    pacer=AdaptivePacer(interval=0),
                )
            assert written == SYNCED_FIRST_PAGE
            state = index.get_sync_state()
            assert state is not None
            assert state["cursor"] == "cur1"
            assert index.last_sync is None

            second = ReadwiseClient(token="test_token", index=index)
            with patch(
                "rwreader.client.requests.get", return_value=_list_page(["c"], None)
            ) as get:
                assert (
                    second.sync_index(pacer=AdaptivePacer(interval=0)) == SYNCED_TOTAL
                )
            assert get.call_args.kwargs["params"] == {"pageCursor": "cur1"}
            assert index.get_sync_state() is None
            assert index.last_sync is not None
            assert {"a", "b", "c"} <= {d["id"] for d in index.query()}
            second.close()

    @patch("rwreader.client.ReadwiseReader")
    def test_sync_index_without_index(self, mock_api_class: Mock) -> None:
        """Sync is a no-op when no index is attached."""
        with patch.dict("os.environ", {}, clear=True):
            client = ReadwiseClient(token="test_token")
            with patch("rwreader.client.requests.get") as get:
                assert client.sync_index() == 0
            get.assert_not_called()

    @patch("rwreader.client.ReadwiseReader")
    def test_sync_index_gives_up_after_repeated_failures(
        self, mock_api_class: Mock
    ) -> None:
        """Persistent network errors are raised after a few retries."""
        with patch.dict("os.environ", {}, clear=True):
            mock_api_class.return_value.URL_BASE = "https://readwise.io/api/v3"
            index = DocumentIndex()
            client = ReadwiseClient(token="test_token", index=index)
            with (
                patch(
                    "rwreader.client.requests.get",
                    side_effect=requests.ConnectionError("down"),
                ) as get,
                pytest.raises(requests.ConnectionError),
            ):
                client.sync_index(pacer=AdaptivePacer(interval=0))
            assert get.call_count == CALLS_UNTIL_GIVE_UP
            assert index.get_sync_state() is not None  # resumable
            client.close()

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
                doc.first_opened_at = (
                    "" if i < ARTICLE_COUNT_2 else "2024-01-01"
                )  # 2 unread
                docs.append(doc)

            mock_api.get_documents.return_value = docs

            client = ReadwiseClient(token="test_token")
            count = client.get_feed_count()

            assert count == ARTICLE_COUNT_2

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

            assert count == ARTICLE_COUNT_5

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
            client._category_cache["inbox"]["last_updated"] = (
                time.time() - 7200
            )  # 2 hours ago

            articles = client.get_inbox()

            # Should fetch fresh data since cache is expired
            mock_api.get_documents.assert_called_once()
            assert len(articles) == 1
            assert articles[0]["id"] == "doc_123"


class TestMarkSeen:
    """Tests for ReadwiseClient.mark_seen."""

    @patch("rwreader.client.readwise.update_document_seen")
    @patch("rwreader.client.ReadwiseReader")
    def test_mark_seen_updates_cache_and_index(
        self, mock_api: Mock, mock_update: Mock
    ) -> None:
        """A successful call updates the article cache and the local index."""
        mock_update.return_value = (True, {})
        index = DocumentIndex(":memory:")
        index.upsert_many([{"id": "a1", "location": "archive", "first_opened_at": ""}])
        client = ReadwiseClient(token="test_token", index=index)
        client._article_cache["a1"] = {"id": "a1", "first_opened_at": ""}

        assert client.mark_seen("a1") is True
        mock_update.assert_called_once_with(document_id="a1", seen=True)
        assert client._article_cache["a1"]["first_opened_at"]
        assert index.query(unread_only=True) == []

        assert client.mark_seen("a1", seen=False) is True
        assert client._article_cache["a1"]["first_opened_at"] == ""
        assert [d["id"] for d in index.query(unread_only=True)] == ["a1"]

    @patch("rwreader.client.readwise.update_document_seen")
    @patch("rwreader.client.ReadwiseReader")
    def test_mark_seen_failure_leaves_state(
        self, mock_api: Mock, mock_update: Mock
    ) -> None:
        """A failed or raising API call returns False and changes nothing."""
        mock_update.return_value = (False, {"error": "nope"})
        client = ReadwiseClient(token="test_token")
        client._article_cache["a1"] = {"id": "a1", "first_opened_at": ""}
        assert client.mark_seen("a1") is False
        assert client._article_cache["a1"]["first_opened_at"] == ""

        mock_update.side_effect = requests.ConnectionError("down")
        assert client.mark_seen("a1") is False
