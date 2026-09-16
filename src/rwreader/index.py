"""Local SQLite index of Readwise Reader document metadata.

The index stores only metadata (no article bodies) so that overview screens can
answer questions such as "how many unread items per location" or "which sites
do I save most from" without re-fetching whole categories from the API.

It is a secondary store: the live screens keep fetching from the API and write
what they receive into the index as a side effect.  Everything here uses only
the standard library.
"""

import json
import logging
import sqlite3
import threading
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

logger: logging.Logger = logging.getLogger(name=__name__)

SCHEMA_VERSION = 1

# Column order matters: it is shared by the CREATE TABLE and the upsert below.
_COLUMNS: tuple[str, ...] = (
    "id",
    "title",
    "url",
    "source_url",
    "author",
    "site_name",
    "category",
    "location",
    "tags",
    "word_count",
    "created_at",
    "updated_at",
    "saved_at",
    "last_moved_at",
    "published_date",
    "first_opened_at",
    "last_opened_at",
    "reading_progress",
    "summary",
    "notes",
    "image_url",
    "parent_id",
    "indexed_at",
)

_ORDERABLE: frozenset[str] = frozenset(
    {
        "saved_at",
        "created_at",
        "updated_at",
        "last_moved_at",
        "published_date",
        "word_count",
        "title",
        "site_name",
        "reading_progress",
    }
)

_CREATE_SQL = f"""
CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
CREATE TABLE IF NOT EXISTS documents (
    {", ".join(_COLUMNS)},
    PRIMARY KEY (id)
);
CREATE INDEX IF NOT EXISTS idx_documents_location ON documents (location);
CREATE INDEX IF NOT EXISTS idx_documents_category ON documents (category);
CREATE INDEX IF NOT EXISTS idx_documents_site ON documents (site_name);
"""


def _now_iso() -> str:
    """Return the current UTC time in ISO 8601 format."""
    return datetime.now(tz=UTC).isoformat()


def _as_text(value: Any) -> str:
    """Coerce an API value to text for storage, mapping None to empty string."""
    if value is None:
        return ""
    return str(value)


def tag_names(value: Any) -> list[str]:
    """Normalise the many shapes tags arrive in to a sorted list of names.

    Args:
        value: A list of names, a list of dicts with a ``name`` key, a dict of
            name to tag object (as returned by the Reader API), or None.

    Returns:
        Sorted list of unique tag names.
    """
    names: set[str] = set()
    if isinstance(value, dict):
        for key, item in value.items():
            name = getattr(item, "name", None)
            if name is None and isinstance(item, dict):
                name = item.get("name")
            names.add(str(name or key))
    elif isinstance(value, list | tuple | set):
        for item in value:
            if isinstance(item, str):
                names.add(item)
            elif isinstance(item, dict) and item.get("name"):
                names.add(str(item["name"]))
            else:
                name = getattr(item, "name", None)
                if name:
                    names.add(str(name))
    return sorted(n for n in names if n)


class DocumentIndex:
    """Thread-safe SQLite-backed index of document metadata."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        """Open (or create) the index database.

        Args:
            path: Database file path, or ``":memory:"`` for a throwaway index.
        """
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        with self._lock:
            self._conn.executescript(_CREATE_SQL)
            self._conn.execute(
                "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
                (str(SCHEMA_VERSION),),
            )
            self._conn.commit()

    # ── Meta ──────────────────────────────────────────────────────────────

    def get_meta(self, key: str) -> str | None:
        """Return a metadata value or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT value FROM meta WHERE key = ?", (key,)
            ).fetchone()
        return row["value"] if row else None

    def set_meta(self, key: str, value: str) -> None:
        """Store a metadata value."""
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                (key, value),
            )
            self._conn.commit()

    @property
    def last_sync(self) -> datetime | None:
        """Timestamp of the last completed sync, or None."""
        value = self.get_meta("last_sync")
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    def mark_synced(self, when: datetime | None = None) -> None:
        """Record that a sync completed."""
        stamp = (when or datetime.now(tz=UTC)).isoformat()
        self.set_meta("last_sync", stamp)

    # ── Writes ────────────────────────────────────────────────────────────

    @staticmethod
    def _row_from_article(article: dict[str, Any]) -> tuple[Any, ...]:
        """Build a tuple in ``_COLUMNS`` order from an article dict."""
        location = article.get("location") or ""
        if not location:
            # Older article dicts only carry the derived booleans.
            if article.get("archived"):
                location = "archive"
            elif article.get("saved_for_later"):
                location = "later"
        word_count = article.get("word_count") or 0
        try:
            word_count = int(word_count)
        except (TypeError, ValueError):
            word_count = 0
        progress = article.get("reading_progress") or 0
        try:
            progress = float(progress)
        except (TypeError, ValueError):
            progress = 0.0
        return (
            str(article.get("id", "")),
            _as_text(article.get("title")),
            _as_text(article.get("url")),
            _as_text(article.get("source_url")),
            _as_text(article.get("author")),
            _as_text(article.get("site_name")),
            _as_text(article.get("category")),
            location,
            json.dumps(tag_names(article.get("tags"))),
            word_count,
            _as_text(article.get("created_at")),
            _as_text(article.get("updated_at")),
            _as_text(article.get("saved_at")),
            _as_text(article.get("last_moved_at")),
            _as_text(article.get("published_date")),
            _as_text(article.get("first_opened_at")),
            _as_text(article.get("last_opened_at")),
            progress,
            _as_text(article.get("summary")),
            _as_text(article.get("notes")),
            _as_text(article.get("image_url")),
            _as_text(article.get("parent_id")),
            _now_iso(),
        )

    def upsert_many(self, articles: Iterable[dict[str, Any]]) -> int:
        """Insert or replace article metadata rows.

        Args:
            articles: Article dicts as produced by the client.

        Returns:
            Number of rows written.
        """
        rows = [self._row_from_article(a) for a in articles if a.get("id")]
        if not rows:
            return 0
        placeholders = ", ".join("?" for _ in _COLUMNS)
        sql = f"INSERT OR REPLACE INTO documents ({', '.join(_COLUMNS)}) VALUES ({placeholders})"
        with self._lock:
            self._conn.executemany(sql, rows)
            self._conn.commit()
        return len(rows)

    def set_location(self, article_id: str, location: str) -> None:
        """Update the stored location of one document after a move."""
        with self._lock:
            self._conn.execute(
                "UPDATE documents SET location = ?, last_moved_at = ?, indexed_at = ? WHERE id = ?",
                (location, _now_iso(), _now_iso(), article_id),
            )
            self._conn.commit()

    def delete(self, article_id: str) -> None:
        """Remove one document from the index."""
        with self._lock:
            self._conn.execute("DELETE FROM documents WHERE id = ?", (article_id,))
            self._conn.commit()

    def prune_except(self, keep_ids: Iterable[str]) -> int:
        """Delete every document whose id is not in ``keep_ids``.

        Used after a full sync so documents deleted remotely disappear locally.

        Returns:
            Number of rows removed.
        """
        keep = set(keep_ids)
        with self._lock:
            existing = [
                row["id"] for row in self._conn.execute("SELECT id FROM documents")
            ]
            stale = [(doc_id,) for doc_id in existing if doc_id not in keep]
            if stale:
                self._conn.executemany("DELETE FROM documents WHERE id = ?", stale)
                self._conn.commit()
        return len(stale)

    def clear(self) -> None:
        """Remove all documents and the sync marker."""
        with self._lock:
            self._conn.execute("DELETE FROM documents")
            self._conn.execute("DELETE FROM meta WHERE key = 'last_sync'")
            self._conn.commit()

    # ── Reads ─────────────────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
        """Convert a row to a plain dict with tags decoded."""
        data = dict(row)
        try:
            data["tags"] = json.loads(data.get("tags") or "[]")
        except (TypeError, ValueError):
            data["tags"] = []
        data["archived"] = data.get("location") == "archive"
        data["saved_for_later"] = data.get("location") == "later"
        return data

    def get(self, article_id: str) -> dict[str, Any] | None:
        """Return one document's metadata or None."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM documents WHERE id = ?", (article_id,)
            ).fetchone()
        return self._row_to_dict(row) if row else None

    def count(self) -> int:
        """Total number of indexed documents."""
        with self._lock:
            row = self._conn.execute("SELECT COUNT(*) AS n FROM documents").fetchone()
        return int(row["n"])

    def count_by_location(self, unread_only: bool = False) -> dict[str, int]:
        """Count documents per location.

        Args:
            unread_only: Count only documents that have never been opened.

        Returns:
            Mapping of location to count. Locations with no documents are absent.
        """
        sql = "SELECT location, COUNT(*) AS n FROM documents"
        if unread_only:
            sql += " WHERE first_opened_at = ''"
        sql += " GROUP BY location"
        with self._lock:
            rows = self._conn.execute(sql).fetchall()
        return {row["location"]: int(row["n"]) for row in rows}

    def words_by_location(self) -> dict[str, int]:
        """Sum of word counts per location."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT location, COALESCE(SUM(word_count), 0) AS n FROM documents GROUP BY location"
            ).fetchall()
        return {row["location"]: int(row["n"]) for row in rows}

    def query(  # noqa: PLR0913, PLR0917
        self,
        location: str | None = None,
        category: str | None = None,
        tag: str | None = None,
        site_name: str | None = None,
        unread_only: bool = False,
        order_by: str = "saved_at",
        descending: bool = True,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Return document metadata matching the given filters.

        Args:
            location: Reader location (new, later, shortlist, archive, feed).
            category: Document category (article, rss, pdf, ...).
            tag: Only documents carrying this tag.
            site_name: Only documents from this site.
            unread_only: Only documents never opened.
            order_by: Column to sort by; must be one of the known columns.
            descending: Sort direction.
            limit: Maximum rows to return.

        Returns:
            List of document dicts.

        Raises:
            ValueError: If ``order_by`` is not a sortable column.
        """
        if order_by not in _ORDERABLE:
            raise ValueError(f"Cannot order by {order_by!r}")
        clauses: list[str] = []
        params: list[Any] = []
        if location:
            clauses.append("location = ?")
            params.append(location)
        if category:
            clauses.append("category = ?")
            params.append(category)
        if site_name:
            clauses.append("site_name = ?")
            params.append(site_name)
        if unread_only:
            clauses.append("first_opened_at = ''")
        sql = "SELECT * FROM documents"
        if clauses:
            sql += " WHERE " + " AND ".join(clauses)
        sql += f" ORDER BY {order_by} {'DESC' if descending else 'ASC'}"
        if limit is not None and tag is None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        results = [self._row_to_dict(row) for row in rows]
        if tag is not None:
            results = [r for r in results if tag in r["tags"]]
            if limit is not None:
                results = results[: int(limit)]
        return results

    def tag_counts(self, location: str | None = None) -> list[tuple[str, int]]:
        """Count documents per tag, most common first.

        Args:
            location: Restrict to one location.

        Returns:
            List of (tag, count) tuples sorted by count then name.
        """
        sql = "SELECT tags FROM documents"
        params: list[Any] = []
        if location:
            sql += " WHERE location = ?"
            params.append(location)
        counts: dict[str, int] = {}
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        for row in rows:
            try:
                names = json.loads(row["tags"] or "[]")
            except (TypeError, ValueError):
                continue
            for name in names:
                counts[name] = counts.get(name, 0) + 1
        return sorted(counts.items(), key=lambda item: (-item[1], item[0]))

    def site_counts(
        self, location: str | None = None, limit: int | None = None
    ) -> list[tuple[str, int]]:
        """Count documents per site, most common first.

        Args:
            location: Restrict to one location.
            limit: Maximum number of sites to return.

        Returns:
            List of (site_name, count) tuples.
        """
        sql = "SELECT site_name, COUNT(*) AS n FROM documents WHERE site_name != ''"
        params: list[Any] = []
        if location:
            sql += " AND location = ?"
            params.append(location)
        sql += " GROUP BY site_name ORDER BY n DESC, site_name ASC"
        if limit is not None:
            sql += " LIMIT ?"
            params.append(int(limit))
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [(row["site_name"], int(row["n"])) for row in rows]

    def category_counts(self, location: str | None = None) -> list[tuple[str, int]]:
        """Count documents per document category (article, rss, pdf, ...)."""
        sql = "SELECT category, COUNT(*) AS n FROM documents"
        params: list[Any] = []
        if location:
            sql += " WHERE location = ?"
            params.append(location)
        sql += " GROUP BY category ORDER BY n DESC, category ASC"
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
        return [(row["category"] or "unknown", int(row["n"])) for row in rows]

    def close(self) -> None:
        """Close the database connection."""
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error as e:
                logger.debug(f"Error closing index: {e}")
