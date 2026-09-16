"""Tests for the local document index."""

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from rwreader.index import DocumentIndex, tag_names

# Test constants
DOC_COUNT_3 = 3
DOC_COUNT_2 = 2
WORDS_INBOX = 1500
WORDS_LATER = 300


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


@pytest.fixture
def index() -> Generator[DocumentIndex, None, None]:
    """In-memory index."""
    idx = DocumentIndex(":memory:")
    yield idx
    idx.close()


class TestTagNames:
    """Tests for tag normalisation."""

    def test_none(self) -> None:
        """None yields an empty list."""
        assert tag_names(None) == []

    def test_list_of_strings(self) -> None:
        """A list of names is sorted and deduplicated."""
        assert tag_names(["b", "a", "b"]) == ["a", "b"]

    def test_dict_of_tag_objects(self) -> None:
        """The API returns a dict keyed by tag name with objects as values."""

        class Tag:
            def __init__(self, name: str) -> None:
                self.name = name

        assert tag_names({"security": Tag("security"), "python": Tag("python")}) == [
            "python",
            "security",
        ]

    def test_dict_of_dicts_and_fallback_to_key(self) -> None:
        """Dict values may be dicts; when no name is present, the key is used."""
        assert tag_names({"x": {"name": "named"}, "y": {}}) == ["named", "y"]

    def test_list_of_dicts(self) -> None:
        """A list of dicts with name keys works too."""
        assert tag_names([{"name": "one"}, {"other": 1}]) == ["one"]


class TestDocumentIndex:
    """Tests for DocumentIndex."""

    def test_creates_file_and_parent_dir(self, tmp_path: Path) -> None:
        """A file-backed index creates its parent directory."""
        path = tmp_path / "nested" / "index.db"
        idx = DocumentIndex(path)
        try:
            assert path.exists()
            assert idx.get_meta("schema_version") == "1"
        finally:
            idx.close()

    def test_upsert_and_get(self, index: DocumentIndex) -> None:
        """Documents round-trip through the index with tags decoded."""
        written = index.upsert_many([_article("a", tags=["python", "tui"])])
        assert written == 1
        doc = index.get("a")
        assert doc is not None
        assert doc["title"] == "Title a"
        assert doc["tags"] == ["python", "tui"]
        assert doc["location"] == "new"
        assert doc["archived"] is False
        assert doc["saved_for_later"] is False

    def test_upsert_replaces_existing(self, index: DocumentIndex) -> None:
        """Re-upserting the same id updates the row instead of duplicating it."""
        index.upsert_many([_article("a")])
        index.upsert_many([_article("a", title="Changed", location="archive")])
        assert index.count() == 1
        doc = index.get("a")
        assert doc is not None
        assert doc["title"] == "Changed"
        assert doc["archived"] is True

    def test_upsert_skips_articles_without_id(self, index: DocumentIndex) -> None:
        """Articles without an id are ignored."""
        assert index.upsert_many([{"title": "no id"}]) == 0
        assert index.count() == 0

    def test_location_derived_from_legacy_flags(self, index: DocumentIndex) -> None:
        """Old-style dicts with only archived/saved_for_later still get a location."""
        index.upsert_many(
            [
                {"id": "x", "archived": True},
                {"id": "y", "saved_for_later": True},
            ]
        )
        assert index.get("x")["location"] == "archive"  # type: ignore[index]
        assert index.get("y")["location"] == "later"  # type: ignore[index]

    def test_bad_numeric_values_are_coerced(self, index: DocumentIndex) -> None:
        """Non-numeric word counts and progress fall back to zero."""
        index.upsert_many([_article("a", word_count="lots", reading_progress="n/a")])
        doc = index.get("a")
        assert doc is not None
        assert doc["word_count"] == 0
        assert doc["reading_progress"] == 0.0

    def test_set_location_and_delete(self, index: DocumentIndex) -> None:
        """Moves and deletes are reflected."""
        index.upsert_many([_article("a")])
        index.set_location("a", "shortlist")
        assert index.get("a")["location"] == "shortlist"  # type: ignore[index]
        index.delete("a")
        assert index.get("a") is None

    def test_count_by_location(self, index: DocumentIndex) -> None:
        """Counts are grouped by location, optionally unread only."""
        index.upsert_many(
            [
                _article("a", location="new"),
                _article("b", location="new", first_opened_at="2024-01-02T00:00:00Z"),
                _article("c", location="later"),
            ]
        )
        assert index.count_by_location() == {"new": DOC_COUNT_2, "later": 1}
        assert index.count_by_location(unread_only=True) == {"new": 1, "later": 1}

    def test_words_by_location(self, index: DocumentIndex) -> None:
        """Word counts are summed per location."""
        index.upsert_many(
            [
                _article("a", location="new", word_count=1000),
                _article("b", location="new", word_count=500),
                _article("c", location="later", word_count=300),
            ]
        )
        assert index.words_by_location() == {"new": WORDS_INBOX, "later": WORDS_LATER}

    def test_query_filters(self, index: DocumentIndex) -> None:
        """Query supports location, category, site, tag and unread filters."""
        index.upsert_many(
            [
                _article("a", location="new", category="article", tags=["sec"]),
                _article("b", location="new", category="pdf", site_name="other.org"),
                _article("c", location="later", tags=["sec", "go"]),
                _article("d", location="new", first_opened_at="2024-01-02T00:00:00Z"),
            ]
        )
        assert {d["id"] for d in index.query(location="new")} == {"a", "b", "d"}
        assert [d["id"] for d in index.query(category="pdf")] == ["b"]
        assert [d["id"] for d in index.query(site_name="other.org")] == ["b"]
        assert {d["id"] for d in index.query(tag="sec")} == {"a", "c"}
        assert [d["id"] for d in index.query(tag="sec", limit=1)] == ["a"]
        assert {d["id"] for d in index.query(location="new", unread_only=True)} == {
            "a",
            "b",
        }

    def test_query_ordering_and_limit(self, index: DocumentIndex) -> None:
        """Ordering honours direction and limit."""
        index.upsert_many(
            [
                _article("a", word_count=10),
                _article("b", word_count=30),
                _article("c", word_count=20),
            ]
        )
        assert [d["id"] for d in index.query(order_by="word_count")] == ["b", "c", "a"]
        assert [
            d["id"] for d in index.query(order_by="word_count", descending=False)
        ] == ["a", "c", "b"]
        assert len(index.query(order_by="word_count", limit=2)) == DOC_COUNT_2

    def test_query_rejects_unknown_order_column(self, index: DocumentIndex) -> None:
        """Ordering by an arbitrary string is refused (no SQL injection surface)."""
        with pytest.raises(ValueError, match="Cannot order by"):
            index.query(order_by="id; DROP TABLE documents")

    def test_tag_counts(self, index: DocumentIndex) -> None:
        """Tags are counted across documents, most common first."""
        index.upsert_many(
            [
                _article("a", tags=["sec", "go"]),
                _article("b", tags=["sec"]),
                _article("c", location="later", tags=["sec", "aaa"]),
            ]
        )
        assert index.tag_counts() == [("sec", DOC_COUNT_3), ("aaa", 1), ("go", 1)]
        assert index.tag_counts(location="later") == [("aaa", 1), ("sec", 1)]

    def test_site_counts(self, index: DocumentIndex) -> None:
        """Sites are counted, blanks skipped, limit honoured."""
        index.upsert_many(
            [
                _article("a", site_name="one.com"),
                _article("b", site_name="one.com"),
                _article("c", site_name="two.com"),
                _article("d", site_name=""),
            ]
        )
        assert index.site_counts() == [("one.com", DOC_COUNT_2), ("two.com", 1)]
        assert index.site_counts(limit=1) == [("one.com", DOC_COUNT_2)]

    def test_site_counts_with_unread(self, index: DocumentIndex) -> None:
        """Total and unread are both reported per site, filterable by location."""
        index.upsert_many(
            [
                _article("a", site_name="one.com", location="new"),
                _article(
                    "b",
                    site_name="one.com",
                    location="new",
                    first_opened_at="2024-01-02T00:00:00Z",
                ),
                _article("c", site_name="two.com", location="later"),
                _article("d", site_name=""),
            ]
        )
        assert index.site_counts_with_unread() == [
            ("one.com", DOC_COUNT_2, 1),
            ("two.com", 1, 1),
        ]
        assert index.site_counts_with_unread(location="new") == [
            ("one.com", DOC_COUNT_2, 1)
        ]
        assert index.site_counts_with_unread(limit=1) == [("one.com", DOC_COUNT_2, 1)]

    def test_category_counts(self, index: DocumentIndex) -> None:
        """Document categories are counted; empty ones show as unknown."""
        index.upsert_many(
            [
                _article("a", category="article"),
                _article("b", category="article"),
                _article("c", category=""),
            ]
        )
        assert index.category_counts() == [("article", DOC_COUNT_2), ("unknown", 1)]

    def test_prune_except(self, index: DocumentIndex) -> None:
        """Documents not in the keep set are removed."""
        index.upsert_many([_article("a"), _article("b"), _article("c")])
        removed = index.prune_except(["a"])
        assert removed == DOC_COUNT_2
        assert index.count() == 1

    def test_last_sync_roundtrip(self, index: DocumentIndex) -> None:
        """The sync marker is stored and parsed back."""
        assert index.last_sync is None
        when = datetime(2024, 5, 1, 12, 0, tzinfo=UTC)
        index.mark_synced(when)
        assert index.last_sync == when
        index.set_meta("last_sync", "garbage")
        assert index.last_sync is None

    def test_clear(self, index: DocumentIndex) -> None:
        """Clear removes documents and the sync marker."""
        index.upsert_many([_article("a")])
        index.mark_synced()
        index.clear()
        assert index.count() == 0
        assert index.last_sync is None

    def test_close_is_idempotent(self, index: DocumentIndex) -> None:
        """Closing twice does not raise."""
        index.close()
        index.close()
