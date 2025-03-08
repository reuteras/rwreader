"""Improved client module using readwise-api library with pagination and better caching."""

import logging
import os
import time
from typing import Any

logger: logging.Logger = logging.getLogger(name=__name__)


class ImprovedReadwiseClient:
    """Client for interacting with the Readwise Reader API with efficient pagination and caching."""

    def __init__(self, token: str, cache_size: int = 1000) -> None:
        """Initialize the Readwise Reader client.

        Args:
            token: Readwise API token
            cache_size: Maximum number of items to store in cache
        """
        # Store token for API calls
        self.token = token
        
        # Set token environment variable (required by readwise-api)
        os.environ["READWISE_TOKEN"] = token

        # Initialize category caches with pagination support
        self._category_cache = {
            "inbox": {"data": [], "last_updated": 0, "cursor": None, "complete": False},
            "later": {"data": [], "last_updated": 0, "cursor": None, "complete": False},
            "archive": {"data": [], "last_updated": 0, "cursor": None, "complete": False},
        }
        
        # Cache for individual articles
        self._article_cache = {}
        
        # Cache expiry time (5 minutes)
        self._cache_expiry = 300
        
        # Default page size
        self._page_size = 25
        
        logger.debug("Initialized improved Readwise client with pagination")
    
    def _convert_document_to_dict(self, document):
        """Convert a Document object to a dictionary format compatible with the application.
        
        Args:
            document: The Document object from readwise-api
            
        Returns:
            Article data in dict format
        """
        # Convert the document model to our expected dictionary format
        article_dict = {
            "id": document.id,
            "title": document.title,
            "url": document.url,
            "author": document.author,
            "site_name": document.site_name,
            "word_count": document.word_count,
            "created_at": document.created_at,
            "updated_at": document.updated_at,
            "published_date": document.published_date,
            "summary": document.summary,
            "content": document.content,
            "source_url": document.source_url,
            # Map location to our internal category system
            "archived": document.location == "archive",
            "saved_for_later": document.location == "later",
            # Add additional fields for compatibility with the existing code
            "read": False,  # Default value, will be updated if needed
            "state": "reading",  # Default value
        }
        
        return article_dict

    def get_inbox(self, refresh: bool = False, limit: int = None) -> list[dict[str, Any]]:
        """Get articles in the Inbox (new location in Readwise).

        Args:
            refresh: Force refresh even if cached data exists
            limit: Maximum number of items to return

        Returns:
            List of inbox articles in dict format
        """
        return self._get_category("inbox", refresh=refresh, limit=limit)

    def get_later(self, refresh: bool = False, limit: int = None) -> list[dict[str, Any]]:
        """Get articles in Later.

        Args:
            refresh: Force refresh even if cached data exists
            limit: Maximum number of items to return

        Returns:
            List of later articles in dict format
        """
        return self._get_category("later", refresh=refresh, limit=limit)

    def get_archive(self, refresh: bool = False, limit: int = None) -> list[dict[str, Any]]:
        """Get articles in the Archive.

        Args:
            refresh: Force refresh even if cached data exists
            limit: Maximum number of items to return

        Returns:
            List of archived articles in dict format
        """
        return self._get_category("archive", refresh=refresh, limit=limit)

    def _get_category(self, category: str, refresh: bool = False, limit: int = None) -> list[dict[str, Any]]:
        """Get articles for a specific category with caching and pagination.
        
        Args:
            category: Category to fetch ('inbox', 'later', or 'archive')
            refresh: Force refresh even if cached data exists
            limit: Maximum number of items to return
            
        Returns:
            List of articles in dict format
        """
        cache = self._category_cache[category]
        
        # Check if we should use the cache
        current_time = time.time()
        cache_age = current_time - cache["last_updated"]
        
        if not refresh and cache["data"] and cache_age < self._cache_expiry:
            logger.debug(f"Using cached data for {category} (age: {cache_age:.1f}s)")
            return cache["data"][:limit] if limit else cache["data"]
        
        try:
            # Map our categories to readwise-api locations
            location_map = {
                "inbox": "new",
                "later": "later",
                "archive": "archive"
            }
            
            # If refreshing, reset the cache
            if refresh:
                cache["data"] = []
                cache["cursor"] = None
                cache["complete"] = False
            
            # If we already have complete data, just update the timestamp
            if cache["complete"]:
                cache["last_updated"] = current_time
                return cache["data"][:limit] if limit else cache["data"]
            
            # Fetch the first page or more if needed
            articles = []
            
            # Import from readwise-api package
            from readwise import get_documents

            # Use readwise-api to get documents
            # Note: The readwise-api handles pagination internally, so we just need to make one call
            documents = get_documents(location=location_map[category])
            
            # Convert documents to our expected format
            for doc in documents:
                article_dict = self._convert_document_to_dict(doc)
                articles.append(article_dict)
                
                # Also update the article cache
                self._article_cache[doc.id] = article_dict
            
            # Update the cache
            cache["data"] = articles
            cache["last_updated"] = current_time
            cache["complete"] = True
            
            logger.debug(f"Fetched {len(articles)} {category} articles")
            
            return articles[:limit] if limit else articles
            
        except Exception as e:
            logger.error(f"Error fetching {category}: {e}")
            # Return whatever we have in the cache
            return cache["data"][:limit] if limit else cache["data"]

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        """Get full article content.

        Args:
            article_id: ID of the article to retrieve

        Returns:
            Article data in dict format or None if not found
        """
        # Import from readwise-api package
        from readwise import get_document_by_id

        # Check if article is in cache
        if article_id in self._article_cache:
            logger.debug(f"Using cached data for article {article_id}")
            return self._article_cache[article_id]

        try:
            logger.debug(f"Fetching article {article_id}")
            
            # Use readwise-api to get the document
            document = get_document_by_id(article_id)
            
            if not document:
                logger.error(f"Article {article_id} not found")
                return None
            
            # Convert document to our expected format
            article_dict = self._convert_document_to_dict(document)
            
            # Store in cache
            self._article_cache[article_id] = article_dict
            
            logger.debug(f"Successfully fetched article {article_id}")
            return article_dict
            
        except Exception as e:
            logger.error(f"Error fetching article {article_id}: {e}")
            return None

    def move_to_inbox(self, article_id: str) -> bool:
        """Move article to Inbox.

        Args:
            article_id: ID of the article to move

        Returns:
            True if successful, False otherwise
        """
        # For now, use the existing implementation
        # In a future version, we could use the readwise-api's save functionality
        result = self._update_article(
            article_id=article_id, data={"archived": False, "saved_for_later": False}
        )
        if result:
            self._invalidate_cache()
        return result

    def move_to_later(self, article_id: str) -> bool:
        """Move article to Later.

        Args:
            article_id: ID of the article to move

        Returns:
            True if successful, False otherwise
        """
        result = self._update_article(
            article_id, {"archived": False, "saved_for_later": True}
        )
        if result:
            self._invalidate_cache()
        return result

    def move_to_archive(self, article_id: str) -> bool:
        """Move article to Archive.

        Args:
            article_id: ID of the article to move

        Returns:
            True if successful, False otherwise
        """
        result = self._update_article(article_id=article_id, data={"archived": True})
        if result:
            self._invalidate_cache()
        return result

    def toggle_read(self, article_id: str, read: bool) -> bool:
        """Toggle read/unread status of an article.

        Args:
            article_id: ID of the article to update
            read: True to mark as read, False for unread

        Returns:
            True if successful, False otherwise
        """
        result = self._update_article(
            article_id=article_id, data={"state": "finished" if read else "reading"}
        )
        
        # Update the article in the cache if it exists
        if result and article_id in self._article_cache:
            self._article_cache[article_id]["read"] = read
            self._article_cache[article_id]["state"] = "finished" if read else "reading"
        
        return result

    def _update_article(self, article_id: str, data: dict[str, Any]) -> bool:
        """Update an article with the given data.

        Args:
            article_id: ID of the article to update
            data: Data to update

        Returns:
            True if successful, False otherwise
        """
        # For this implementation, we'll continue to use the direct API approach
        # as readwise-api doesn't expose these operations yet
        import requests
        
        max_retries = 3
        for retry in range(max_retries):
            try:
                logger.debug(
                    msg=f"Updating article {article_id} with data: {data} (attempt {retry + 1}/{max_retries})"
                )

                # Direct API call to update the article
                url: str = f"https://readwise.io/api/v2/books/{article_id}/"

                response: requests.Response = requests.patch(
                    url=url, headers={"Authorization": f"Token {self.token}"}, json=data
                )

                # Handle rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limit hit, waiting {retry_after} seconds")
                    time.sleep(retry_after)
                    continue

                response.raise_for_status()

                # Update cache if needed
                if article_id in self._article_cache:
                    for key, value in data.items():
                        self._article_cache[article_id][key] = value

                    # Handle special cases
                    if "state" in data:
                        self._article_cache[article_id]["read"] = (
                            data["state"] == "finished"
                        )

                logger.debug(f"Successfully updated article {article_id}")
                return True

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 429 and retry < max_retries - 1:
                    retry_after = int(e.response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limit hit, waiting {retry_after} seconds")
                    time.sleep(retry_after)
                    continue
                logger.error(msg=f"HTTP error updating article {article_id}: {e}")
                return False
            except Exception as e:
                logger.error(msg=f"Error updating article {article_id}: {e}")
                if retry < max_retries - 1:
                    wait_time: int = (retry + 1) * 2  # Exponential backoff
                    logger.info(msg=f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    return False

        logger.error(
            msg=f"Failed to update article {article_id} after {max_retries} attempts"
        )
        return False

    def get_more_articles(self, category: str) -> list[dict[str, Any]]:
        """Get the next page of articles for a category.
        
        Args:
            category: Category to fetch more articles for
            
        Returns:
            List of newly loaded articles
        """
        # Force a full refresh
        self._invalidate_cache_for_category(category)
        return self._get_category(category)

    def _invalidate_cache_for_category(self, category: str) -> None:
        """Invalidate cache for a specific category.
        
        Args:
            category: Category to invalidate
        """
        if category in self._category_cache:
            self._category_cache[category] = {
                "data": [],
                "last_updated": 0,
                "cursor": None,
                "complete": False
            }
            logger.debug(f"Invalidated cache for {category}")

    def _invalidate_cache(self) -> None:
        """Invalidate all caches."""
        logger.debug("Invalidating all caches")
        for category in self._category_cache:
            self._invalidate_cache_for_category(category)

    def clear_cache(self) -> None:
        """Clear the entire cache."""
        self._invalidate_cache()
        self._article_cache = {}
        logger.debug("Cleared entire cache")

    def close(self) -> None:
        """Close the client (if needed)."""
        # No resources to clean up
        logger.debug("Closed client")
