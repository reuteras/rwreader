"""Client module for Readwise Reader using the improved v3 API with careful parameter handling."""

import datetime
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any, cast

import readwise
import requests
from readwise.api import ReadwiseReader
from readwise.model import Document

from .exceptions import (
    ArticleError,
    ReadwiseAuthenticationError,
    ReadwiseRateLimitError,
    ReadwiseServerError,
)

logger: logging.Logger = logging.getLogger(name=__name__)


async def create_readwise_client(token: str) -> "ReadwiseClient":
    """Create a ReadwiseClient instance asynchronously.

    Args:
        token: Readwise API token

    Returns:
        ReadwiseClient instance
    """
    return ReadwiseClient(token=token)


class ReadwiseClient:
    """Client for interacting with the Readwise Reader API with efficient caching."""

    def __init__(self, token: str) -> None:
        """Initialize the Readwise Reader client.

        Args:
            token: Readwise API token
            cache_size: Maximum number of items to store in cache
        """
        # Store token for API calls
        self.token: str = token

        # Set token environment variable (required by readwise-api)
        os.environ["READWISE_TOKEN"] = token

        # Initialize category caches with pagination support
        self._category_cache: dict[str, dict[str, Any]] = {
            "inbox": {"data": [], "last_updated": 0, "complete": False},
            "feed": {"data": [], "last_updated": 0, "complete": False},
            "later": {"data": [], "last_updated": 0, "complete": False},
            "archive": {
                "data": [],
                "last_updated": 0,
                "complete": False,
                "timeframe": "month",
            },
        }

        # Cache for individual articles
        self._article_cache: dict[str, dict[str, Any]] = {}

        # Cache expiry time (1 hour)
        self._cache_expiry = 3600

        # API request timeout (seconds)
        self._timeout = 30

        # Thread executor for concurrent API requests
        self._executor = ThreadPoolExecutor(max_workers=3)

        # Create the ReadwiseReader client
        self._api = ReadwiseReader(token=token)

    def get_inbox(
        self, refresh: bool = False, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Get articles in the Inbox (new location in Readwise).

        Args:
            refresh: Force refresh even if cached data exists
            limit: Maximum number of items to return

        Returns:
            List of inbox articles in dict format
        """
        return self._get_category(
            cache_key="inbox", api_location="new", refresh=refresh, limit=limit
        )

    def get_feed(
        self, refresh: bool = False, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Get articles in the Feed.

        Args:
            refresh: Force refresh even if cached data exists
            limit: Maximum number of items to return

        Returns:
            List of feed articles in dict format
        """
        return self._get_category(
            cache_key="feed", api_location="feed", refresh=refresh, limit=limit
        )

    def get_later(
        self, refresh: bool = False, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Get articles in Later.

        Args:
            refresh: Force refresh even if cached data exists
            limit: Maximum number of items to return

        Returns:
            List of later articles in dict format
        """
        return self._get_category(
            cache_key="later", api_location="later", refresh=refresh, limit=limit
        )

    def get_archive(
        self, refresh: bool = False, limit: int | None = None, timeframe: str = "month"
    ) -> list[dict[str, Any]]:
        """Get articles in the Archive with date filtering.

        Args:
            refresh: Force refresh even if cached data exists
            limit: Maximum number of items to return
            timeframe: Time period to fetch (day, week, month, year)

        Returns:
            List of archived articles in dict format
        """
        cache: dict[str, Any] = self._category_cache["archive"]

        # Check if we should use the cache (and if timeframe matches)
        current_time: float = time.time()
        cache_age: float = current_time - cache["last_updated"]

        if (
            not refresh
            and cache["data"]
            and cache_age < self._cache_expiry
            and cache.get("timeframe") == timeframe
        ):
            data = cast(list[dict[str, Any]], cache["data"])
            return data[:limit] if limit else data

        try:
            # Calculate the date range based on timeframe
            updated_after: datetime.datetime = self._get_date_for_timeframe(
                timeframe=timeframe
            )

            # Get documents without withHtmlContent first to avoid potential issues
            try:
                documents: list[Document] = self._api.get_documents(
                    location="archive", updated_after=updated_after
                )

                # Convert to our internal format
                articles: list[dict[str, Any]] = [
                    self._convert_document_to_dict(document=doc) for doc in documents
                ]

                # Update the cache
                cache["data"] = articles
                cache["last_updated"] = current_time
                cache["complete"] = True
                cache["timeframe"] = timeframe

                # Update the article cache
                for article in articles:
                    self._article_cache[article["id"]] = article

                return articles[:limit] if limit else articles

            except Exception as e:
                logger.error(msg=f"Error in get_documents for archive: {e}")
                # Return whatever we have in the cache
                data = cast(list[dict[str, Any]], cache["data"])
                return data[:limit] if limit else data

        except Exception as e:
            logger.error(msg=f"Error fetching archive: {e}")
            # Return whatever we have in the cache
            data = cast(list[dict[str, Any]], cache["data"])
            return data[:limit] if limit else data

    def _get_date_for_timeframe(self, timeframe: str) -> datetime.datetime:
        """Get a date based on the specified timeframe.

        Args:
            timeframe: Time period to fetch (day, week, month, year)

        Returns:
            A datetime representing the start of the timeframe
        """
        now: datetime.datetime = datetime.datetime.now()

        if timeframe == "day":
            return now - datetime.timedelta(days=1)
        elif timeframe == "week":
            return now - datetime.timedelta(days=7)
        elif timeframe == "month":
            return now - datetime.timedelta(days=31)
        elif timeframe == "year":
            return now - datetime.timedelta(days=365)
        else:
            logger.warning(msg=f"Invalid timeframe: {timeframe}, using month")
            return now - datetime.timedelta(days=30)

    def _get_category(
        self,
        cache_key: str,
        api_location: str,
        refresh: bool = False,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Get articles for a specific category with improved caching and performance.

        Args:
            cache_key: Category key for cache (inbox, feed, later)
            api_location: Location value for readwise-api (new, feed, later)
            refresh: Force refresh even if cached data exists
            limit: Maximum number of items to return

        Returns:
            List of articles in dict format
        """
        cache: dict[str, Any] = self._category_cache[cache_key]

        # Check if we should use the cache
        current_time: float = time.time()
        cache_age: float = current_time - cache["last_updated"]

        # Only use cache if: not refreshing, has data, and not expired
        if not refresh and cache["data"] and cache_age < self._cache_expiry:
            data = cast(list[dict[str, Any]], cache["data"])
            return data[:limit] if limit else data

        # Get fresh data from the API

        # If we've already completed a full load and we're not explicitly refreshing,
        # just update the timestamp and return the cached data
        if cache["complete"] and not refresh:
            data = cast(list[dict[str, Any]], cache["data"])
            return data[:limit] if limit else data

        try:
            # If refreshing, reset the cache
            if refresh:
                cache["data"] = []
                cache["complete"] = False

            # Get documents without withHtmlContent first to avoid potential issues
            try:
                # Add a timeout to prevent hanging
                documents: list[Document] = self._api.get_documents(
                    location=api_location
                )

                # Convert documents to our expected format - use a more efficient method
                # for large datasets
                articles: list[dict[str, Any]] = [
                    self._convert_document_to_dict(document=doc) for doc in documents
                ]

                # Update the cache
                cache["data"] = articles
                cache["last_updated"] = current_time
                cache["complete"] = True

                return articles[:limit] if limit else articles

            except Exception as e:
                error_msg = str(e).lower()
                logger.error(msg=f"Error in get_documents for {cache_key}: {e}")

                # Check for specific error types that should raise exceptions
                if (
                    "401" in error_msg
                    or "unauthorized" in error_msg
                    or "authentication" in error_msg
                ):
                    raise ReadwiseAuthenticationError(
                        f"Authentication failed for {cache_key}: {e}"
                    ) from e
                elif "429" in error_msg or "rate limit" in error_msg:
                    raise ReadwiseRateLimitError(
                        f"Rate limit exceeded for {cache_key}: {e}"
                    ) from e
                elif (
                    "500" in error_msg
                    or "502" in error_msg
                    or "503" in error_msg
                    or "server error" in error_msg
                ):
                    raise ReadwiseServerError(
                        f"Readwise server error for {cache_key}: {e}"
                    ) from e
                else:
                    # For non-critical errors (404, network issues, etc.), return cached data (even if empty)
                    # This preserves backward compatibility
                    data = cast(list[dict[str, Any]], cache["data"])
                    return data[:limit] if limit else data

        except (
            ReadwiseAuthenticationError,
            ReadwiseRateLimitError,
            ReadwiseServerError,
        ):
            # Re-raise critical exceptions
            raise
        except Exception as e:
            logger.error(msg=f"Unexpected error fetching {cache_key}: {e}")
            # Return cached data (even if empty) for unexpected errors
            # This maintains backward compatibility with the original behavior
            data = cast(list[dict[str, Any]], cache["data"])
            return data[:limit] if limit else data

    def _convert_document_to_dict(self, document: Any) -> dict[str, Any]:
        """Convert a Document object from readwise-api to a dictionary format.

        Args:
            document: The Document object from readwise-api

        Returns:
            Article data in dict format
        """
        try:
            # Convert document attributes to our dictionary format
            article_dict: dict[str, Any] = {
                "id": document.id,
                "title": document.title or "Untitled",
                "url": document.url or "",
                "author": document.author or "",
                "site_name": document.site_name or "",
                "word_count": document.word_count or 0,
                "created_at": document.created_at or "",
                "updated_at": document.updated_at or "",
                "published_date": document.published_date or "",
                "summary": document.summary or "",
                "content": document.content or "",  # Basic content
                "source_url": document.source_url or "",
                "first_opened_at": document.first_opened_at or "",
                "last_opened_at": document.last_opened_at or "",
                "archived": document.location == "archive",
                "saved_for_later": document.location == "later",
                # Add additional fields for compatibility with the existing code
                "read": document.reading_progress >= 95  # noqa: PLR2004
                if document.reading_progress
                else False,
                "state": "finished"
                if (document.reading_progress and document.reading_progress >= 95)  # noqa: PLR2004
                else "reading",
                "reading_progress": document.reading_progress or 0,
            }
            return article_dict
        except Exception as e:
            logger.error(msg=f"Error converting document to dict: {e}")
            # Try to create a minimal fallback dictionary
            try:
                return {
                    "id": getattr(document, "id", "unknown"),
                    "title": getattr(document, "title", "Error Loading Document"),
                    "url": getattr(document, "url", ""),
                    "archived": getattr(document, "location", "") == "archive",
                    "saved_for_later": getattr(document, "location", "") == "later",
                    "read": False,
                    "state": "reading",
                }
            except Exception as nested_e:
                logger.error(
                    f"Severe error in fallback dictionary creation: {nested_e}"
                )
                # Raise ArticleError if we can't even create a fallback
                raise ArticleError(
                    f"Failed to convert document to dictionary: {e}"
                ) from e

    def get_article(self, article_id: str) -> dict[str, Any] | None:  # noqa: PLR0912, PLR0915
        """Get full article content with enhanced debugging.

        Args:
            article_id: ID of the article to retrieve

        Returns:
            Article data in dict format or None if not found
        """
        # First, check if full article (with content) is in cache
        if article_id in self._article_cache:
            cached_article = self._article_cache[article_id]
            # Check if the article in cache has content or html_content
            if cached_article.get("content") or cached_article.get("html_content"):
                return cached_article

        try:
            # Get document by ID first without html content
            document: Document | None = None
            try:
                document = self._api.get_document_by_id(id=article_id)
            except Exception as doc_error:
                error_msg = str(doc_error).lower()
                logger.error(msg=f"Error getting document by ID: {doc_error}")

                # Check for critical error types only
                if (
                    "401" in error_msg
                    or "unauthorized" in error_msg
                    or "authentication" in error_msg
                ):
                    raise ReadwiseAuthenticationError(
                        f"Authentication failed getting article {article_id}: {doc_error}"
                    ) from doc_error
                elif "429" in error_msg or "rate limit" in error_msg:
                    raise ReadwiseRateLimitError(
                        f"Rate limit exceeded getting article {article_id}: {doc_error}"
                    ) from doc_error
                elif (
                    "500" in error_msg
                    or "502" in error_msg
                    or "503" in error_msg
                    or "server error" in error_msg
                ):
                    raise ReadwiseServerError(
                        f"Readwise server error getting article {article_id}: {doc_error}"
                    ) from doc_error
                # For 404 and other errors, let document remain None and return None below

            if document:
                # Create base article dict from the document
                article: dict[str, Any] = self._convert_document_to_dict(document)

                try:
                    # Make a direct API call with withHtmlContent
                    params: dict[str, str] = {
                        "id": article_id,
                        "withHtmlContent": "true",
                    }
                    response: requests.Response = requests.get(
                        url=f"{self._api.URL_BASE}/list/",
                        headers={"Authorization": f"Token {self.token}"},
                        params=params,
                        timeout=self._timeout,
                    )
                    response.raise_for_status()
                    data = response.json()

                    if data.get("count", 0) > 0 and data.get("results", []):
                        first_result = data["results"][0]

                        # Try to get content from various fields
                        content_found = False

                        # Check for HTML content first
                        if first_result.get("html_content"):
                            article["html_content"] = first_result["html_content"]
                            content_found = True
                        elif first_result.get("full_html"):
                            article["html_content"] = first_result["full_html"]
                            content_found = True
                        elif first_result.get("content"):
                            article["content"] = first_result["content"]
                            content_found = True

                        # If no standard content fields found, try other potential fields
                        if not content_found:
                            for field in [
                                "text",
                                "article_text",
                                "full_text",
                                "html",
                                "document",
                                "body",
                                "article_content",
                            ]:
                                if (
                                    first_result.get(field)
                                    and isinstance(first_result[field], str)
                                    and len(first_result[field]) > 0
                                ):
                                    article["content"] = first_result[field]
                                    content_found = True
                                    break

                            # Last resort: try to get content from any large string field
                            if not content_found:
                                # Find the largest string field that might contain content
                                largest_field = None
                                largest_size: int = 0
                                for field, value in first_result.items():
                                    if (
                                        isinstance(value, str)
                                        and len(value) > largest_size
                                        and field not in ["id", "title", "url"]
                                    ):
                                        largest_size = len(value)
                                        largest_field = field

                                if (
                                    largest_field and largest_size > 100  # noqa: PLR2004
                                ):  # Only use if reasonably large
                                    article["content"] = first_result[largest_field]
                                    content_found = True

                    # If we still don't have content, try a desperate measure: raw content from document
                    if (
                        not article.get("html_content")
                        and not article.get("content")
                        and hasattr(document, "content")
                        and document.content
                    ):
                        article["content"] = document.content

                except requests.HTTPError as http_err:
                    # Handle critical HTTP errors only
                    status_code = (
                        http_err.response.status_code if http_err.response else None
                    )
                    logger.error(msg=f"HTTP error fetching article content: {http_err}")

                    if status_code == 401:  # noqa: PLR2004
                        raise ReadwiseAuthenticationError(
                            f"Authentication failed getting content for {article_id}"
                        ) from http_err
                    elif status_code == 429:  # noqa: PLR2004
                        raise ReadwiseRateLimitError(
                            f"Rate limit exceeded fetching content for {article_id}"
                        ) from http_err
                    elif status_code and status_code >= 500:  # noqa: PLR2004
                        raise ReadwiseServerError(
                            f"Server error fetching content for {article_id}",
                            status_code=status_code,
                        ) from http_err
                    # For 404 and other errors, try to use content from original document as fallback
                    elif hasattr(document, "content") and document.content:
                        article["content"] = document.content
                except Exception as e:
                    logger.error(msg=f"Error fetching HTML content: {e}")
                    # Try to use any content from the original document as fallback
                    if hasattr(document, "content") and document.content:
                        article["content"] = document.content

                # Store in cache
                self._article_cache[article_id] = article
                return article
            else:
                logger.warning(msg=f"No article found with ID {article_id}")
                return None

        except Exception as e:
            logger.error(msg=f"Error fetching article {article_id}: {e}")

            # Return what we have in cache even if incomplete
            if article_id in self._article_cache:
                logger.warning(
                    msg=f"Returning cached article for {article_id} without full content"
                )
                return self._article_cache[article_id]

            return None

    def move_to_inbox(self, article_id: str) -> bool:
        """Move article to Inbox.

        Args:
            article_id: ID of the article to move

        Returns:
            True if successful, False otherwise
        """
        try:
            success, response = readwise.update_document_location(
                document_id=article_id,
                location="new",  # 'new' is the v3 API name for inbox
            )

            if success:
                # Update cache
                if article_id in self._article_cache:
                    self._article_cache[article_id]["archived"] = False
                    self._article_cache[article_id]["saved_for_later"] = False

                self._invalidate_cache()
                return True
            else:
                logger.error(
                    msg=f"Failed to move article {article_id} to inbox: {response}"
                )
                return False

        except Exception as e:
            logger.error(msg=f"Error moving article {article_id} to inbox: {e}")
            return False

    def move_to_later(self, article_id: str) -> bool:
        """Move article to Later.

        Args:
            article_id: ID of the article to move

        Returns:
            True if successful, False otherwise
        """
        try:
            # Call the update_document_location function
            success, response = readwise.update_document_location(
                document_id=article_id, location="later"
            )

            if success:
                # Update cache
                if article_id in self._article_cache:
                    self._article_cache[article_id]["archived"] = False
                    self._article_cache[article_id]["saved_for_later"] = True

                self._invalidate_cache()
                return True
            else:
                logger.error(
                    msg=f"Failed to move article {article_id} to later: {response}"
                )
                return False

        except Exception as e:
            logger.error(msg=f"Error moving article {article_id} to later: {e}")
            return False

    def move_to_archive(self, article_id: str) -> bool:
        """Move article to Archive.

        Args:
            article_id: ID of the article to move

        Returns:
            True if successful, False otherwise
        """
        try:
            # Call the update_document_location function
            success, response = readwise.update_document_location(
                document_id=article_id, location="archive"
            )

            if success:
                # Update cache
                if article_id in self._article_cache:
                    self._article_cache[article_id]["archived"] = True
                    self._article_cache[article_id]["saved_for_later"] = False

                self._invalidate_cache()
                return True
            else:
                logger.error(
                    msg=f"Failed to move article {article_id} to archive: {response}"
                )
                return False

        except Exception as e:
            logger.error(msg=f"Error moving article {article_id} to archive: {e}")
            return False

    def delete_article(self, article_id: str) -> bool:
        """Delete an article from Readwise.

        Args:
            article_id: ID of the article to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            # Call the delete_document function
            readwise.delete_document(document_id=article_id)

            # if article_id in self._article_cache:
            #    del self._article_cache[article_id]
            return True

        except Exception as e:
            logger.error(msg=f"Error deleting article {article_id}: {e}")
            return False

    def get_more_articles(self, category: str) -> list[dict[str, Any]]:
        """Get the next page of articles for a category.

        Args:
            category: Category to fetch more articles for

        Returns:
            List of newly loaded articles
        """
        # For archive, we can try using a longer timeframe
        if category == "archive":
            current_timeframe = self._category_cache["archive"].get(
                "timeframe", "month"
            )

            # Try to expand the timeframe
            if current_timeframe == "day":
                new_timeframe = "week"
            elif current_timeframe == "week":
                new_timeframe = "month"
            elif current_timeframe == "month":
                new_timeframe = "year"
            else:
                new_timeframe = current_timeframe  # Keep current timeframe

            # Reload with new timeframe if different
            if new_timeframe != current_timeframe:
                return self.get_archive(refresh=True, timeframe=new_timeframe)
            else:
                # If already using longest timeframe, just refresh
                return self.get_archive(refresh=True)

        # For other categories, just force a refresh
        self._invalidate_cache_for_category(category)

        if category == "inbox":
            return self.get_inbox(refresh=True)
        elif category == "feed":
            return self.get_feed(refresh=True)
        elif category == "later":
            return self.get_later(refresh=True)
        else:
            logger.error(msg=f"Unknown category: {category}")
            return []

    def _invalidate_cache_for_category(self, category: str) -> None:
        """Invalidate cache for a specific category.

        Args:
            category: Category to invalidate
        """
        if category in self._category_cache:
            # Preserve the timeframe for archive
            timeframe = (
                self._category_cache[category].get("timeframe", "month")
                if category == "archive"
                else None
            )

            self._category_cache[category] = {
                "data": [],
                "last_updated": 0,
                "complete": False,
            }

            # Restore timeframe for archive
            if category == "archive" and timeframe:
                self._category_cache[category]["timeframe"] = timeframe

    def _invalidate_cache(self) -> None:
        """Invalidate all caches."""
        for category in self._category_cache:
            self._invalidate_cache_for_category(category=category)

    def clear_cache(self) -> None:
        """Clear the entire cache."""
        self._invalidate_cache()
        self._article_cache = {}

    def get_feed_count(self) -> int:
        """Get count of unread articles in the Feed efficiently.

        Returns:
            Number of unread feed articles
        """
        try:
            # Try to get from cache first
            feed_cache = self._category_cache.get("feed", {})
            feed_data = feed_cache.get("data", [])

            if feed_data:
                # Count unread articles (first_opened_at is empty)
                return len([a for a in feed_data if a.get("first_opened_at") == ""])

            # If no cache, make a lightweight API call
            documents: list[Document] = self._api.get_documents(location="feed")
            unread_count = len([doc for doc in documents if not doc.first_opened_at])

            return unread_count
        except Exception as e:
            logger.error(f"Error getting feed count: {e}")
            return 0

    def get_later_count(self) -> int:
        """Get count of articles in Later efficiently.

        Returns:
            Number of articles in Later
        """
        try:
            # Try to get from cache first
            later_cache = self._category_cache.get("later", {})
            later_data = later_cache.get("data", [])

            if later_data:
                return len(later_data)

            # If no cache, make a lightweight API call
            documents: list[Document] = self._api.get_documents(location="later")
            return len(documents)
        except Exception as e:
            logger.error(f"Error getting later count: {e}")
            return 0

    def save_document(  # noqa: PLR0913, PLR0912
        self,
        url: str,
        html: str | None = None,
        title: str | None = None,
        author: str | None = None,
        summary: str | None = None,
        published_date: str | None = None,
        image_url: str | None = None,
        location: str | None = None,
        category: str | None = None,
        saved_using: str | None = None,
        tags: list[str] | None = None,
        notes: str | None = None,
        should_clean_html: bool = False,
    ) -> tuple[bool, Any]:
        """Save a document to Readwise Reader.

        Args:
            url: Document URL (required). Can include query parameters.
            html: Custom HTML content to save. If provided, Readwise uses this
                  instead of scraping the URL. Optional.
            title: Override document title. Optional.
            author: Override document author. Optional.
            summary: Document summary/description. Optional.
            published_date: ISO 8601 formatted publication date. Optional.
            image_url: Cover/thumbnail image URL. Optional.
            location: Initial location in Readwise. One of: "new", "later",
                      "archive", "feed". Optional, defaults to "new".
            category: Document type. One of: "article", "email", "rss",
                      "highlight", "note", "pdf", "epub", "tweet", "video".
                      Optional.
            saved_using: String identifying the source/tool that saved this.
                         Example: "rwreader-html-redownload". Optional.
            tags: List of tag strings to apply. Optional.
            notes: Top-level document note. Optional.
            should_clean_html: Whether Readwise should auto-clean the provided HTML.
                              Only used if html is provided. Defaults to False.

        Returns:
            Tuple of (success: bool, response: PostResponse)
        """
        try:
            logger.debug(msg="Saving document to Readwise using direct HTTP request")
            # Build the payload manually to avoid validation issues
            payload_dict: dict[str, Any] = {"url": url}

            if html is not None:
                payload_dict["html"] = html
                payload_dict["should_clean_html"] = should_clean_html
            if title is not None:
                payload_dict["title"] = title
            if author is not None:
                payload_dict["author"] = author
            if summary is not None:
                payload_dict["summary"] = summary
            if published_date is not None:
                payload_dict["published_date"] = published_date
            if image_url is not None:
                payload_dict["image_url"] = image_url
            if location is not None:
                payload_dict["location"] = location
            if category is not None:
                payload_dict["category"] = category
            if saved_using is not None:
                payload_dict["saved_using"] = saved_using
            if tags is not None:
                payload_dict["tags"] = tags
            if notes is not None:
                payload_dict["notes"] = notes

            # Make the direct HTTP request to avoid the readwise-api validation issues
            http_response: requests.Response = requests.post(
                url=f"{self._api.URL_BASE}/save/",
                headers={"Authorization": f"Token {self.token}"},
                json=payload_dict,
                timeout=self._timeout,
            )

            logger.debug(msg=f"Readwise API response status: {http_response.status_code}")

            # Check response status - both 200 (OK) and 201 (Created) are success
            if http_response.status_code in (HTTPStatus.OK, HTTPStatus.CREATED):
                response_data = http_response.json()
                # Create a simple object with id and url attributes
                response = SimpleNamespace(id=response_data.get("id"), url=response_data.get("url"))
                logger.info(msg=f"Successfully saved document with ID: {response.id}")
                self._invalidate_cache()
                return True, response
            else:
                try:
                    error_data = http_response.json()
                    logger.error(
                        msg=f"Error saving document to Readwise (status {http_response.status_code}): {error_data}"
                    )
                except Exception:
                    logger.error(
                        msg=f"Error saving document to Readwise (status {http_response.status_code}): {http_response.text}"
                    )

                return False, None

        except Exception as e:
            logger.error(msg=f"Error saving document to Readwise: {e}", exc_info=True)
            # Return a tuple with success=False and None for response
            return False, None

    def close(self) -> None:
        """Close the client and clean up resources."""
        try:
            self._executor.shutdown(wait=False)
        except Exception as e:
            logger.error(msg=f"Error shutting down executor: {e}")
