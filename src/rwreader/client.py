"""Hybrid client module using both readwise-api and direct API access with rate limiting."""

import logging
import os
import time
from typing import Any

import requests

logger: logging.Logger = logging.getLogger(name=__name__)

RATE_LIMIT = 429


class RateLimiter:
    """Tracks API requests and handles rate limiting."""

    def __init__(self, requests_per_minute: int = 20) -> None:
        """Initialize the rate limiter.

        Args:
            requests_per_minute: Maximum API requests allowed per minute
        """
        self.requests_per_minute = requests_per_minute
        self.request_timestamps: list[float] = []
        self.retry_after = None

    def wait_if_needed(self) -> None:
        """Wait if we've hit rate limits or have a retry-after directive."""
        current_time = time.time()

        # If we have a retry-after directive, honor it
        if self.retry_after is not None:
            wait_until = self.retry_after
            if current_time < wait_until:
                wait_time = wait_until - current_time
                logger.info(
                    f"Rate limit hit: waiting for {wait_time:.2f} seconds per Retry-After header"
                )
                time.sleep(wait_time)
            self.retry_after = None

        # Clear old request timestamps
        minute_ago = current_time - 60
        self.request_timestamps = [t for t in self.request_timestamps if t > minute_ago]

        # If we're at or above the limit, wait
        if len(self.request_timestamps) >= self.requests_per_minute:
            # Calculate how long until the oldest request is a minute old
            oldest_timestamp = self.request_timestamps[0]
            wait_time = (oldest_timestamp + 60) - current_time
            if wait_time > 0:
                logger.info(
                    f"Rate limit approaching: waiting for {wait_time:.2f} seconds"
                )
                time.sleep(wait_time)

    def add_request(self) -> None:
        """Record a new API request."""
        self.request_timestamps.append(time.time())

    def handle_429(self, response: requests.Response) -> None:
        """Handle a 429 Too Many Requests response.

        Args:
            response: The HTTP response with the 429 status
        """
        # Parse retry-after header if available
        retry_after = response.headers.get("Retry-After")

        if retry_after:
            try:
                # Retry-After can be seconds or a timestamp
                seconds = int(retry_after)
                self.retry_after = time.time() + seconds
                logger.warning(
                    f"Rate limit exceeded. Will retry after {seconds} seconds"
                )
            except ValueError:
                # If it's not an integer, it could be HTTP date format
                # For simplicity, we'll use a default of 60 seconds in this case
                self.retry_after = time.time() + 60
                logger.warning("Rate limit exceeded. Using default 60 second wait")
        else:
            # Default wait of 60 seconds if Retry-After header is missing
            self.retry_after = time.time() + 60
            logger.warning(
                "Rate limit exceeded with no Retry-After header. Using default 60 second wait"
            )


class ReadwiseClient:
    """Hybrid client for interacting with the Readwise Reader API with rate limiting."""

    def __init__(self, token: str, cache_size: int = 1000) -> None:
        """Initialize the Readwise Reader client.

        Args:
            token: Readwise API token
            cache_size: Maximum number of items to store in cache (not used with library)
        """
        # Store token for direct API calls
        self.token = token

        # Set token environment variable (required by readwise-api)
        os.environ["READWISE_TOKEN"] = token

        # Base URL for direct API calls (v2 for document operations)
        self.base_url = "https://readwise.io/api/v2/"

        # Initialize rate limiter (20 requests per minute per Readwise docs)
        self.rate_limiter = RateLimiter(requests_per_minute=20)

        logger.debug("Initialized hybrid Readwise client with rate limiting")

        # Initialize category caches
        self._inbox_cache = None
        self._later_cache = None
        self._archive_cache = None
        self._article_cache = {}

    def get_inbox(self) -> list[dict[str, Any]]:
        """Get articles in the Inbox (unarchived, not saved for later).

        Returns:
            List of inbox articles in dict format
        """
        if self._inbox_cache is not None:
            logger.debug("Using cached data for inbox")
            return self._inbox_cache

        try:
            logger.debug("Fetching inbox articles")
            # Use direct API call for more precise filtering
            params = {"archived": "false", "saved_for_later": "false"}

            articles = self._fetch_articles_with_params(params)

            logger.debug(f"Fetched {len(articles)} inbox articles")
            self._inbox_cache = articles
            return articles
        except Exception as e:
            logger.error(f"Error fetching inbox: {e}")
            return []

    def get_later(self) -> list[dict[str, Any]]:
        """Get articles in Later (unarchived, saved for later).

        Returns:
            List of later articles in dict format
        """
        if self._later_cache is not None:
            logger.debug("Using cached data for later")
            return self._later_cache

        try:
            logger.debug("Fetching later articles")
            # Use direct API call for more precise filtering
            params = {"archived": "false", "saved_for_later": "true"}

            articles = self._fetch_articles_with_params(params)

            logger.debug(f"Fetched {len(articles)} later articles")
            self._later_cache = articles
            return articles
        except Exception as e:
            logger.error(f"Error fetching later: {e}")
            return []

    def get_archive(self) -> list[dict[str, Any]]:
        """Get articles in the Archive.

        Returns:
            List of archived articles in dict format
        """
        if self._archive_cache is not None:
            logger.debug("Using cached data for archive")
            return self._archive_cache

        try:
            logger.debug("Fetching archive articles")
            # Use direct API call
            params = {"archived": "true"}

            articles = self._fetch_articles_with_params(params)

            logger.debug(f"Fetched {len(articles)} archive articles")
            self._archive_cache = articles
            return articles
        except Exception as e:
            logger.error(f"Error fetching archive: {e}")
            return []

    def get_article(self, article_id: str) -> dict[str, Any] | None:
        """Get full article content.

        Args:
            article_id: ID of the article to retrieve

        Returns:
            Article data in dict format or None if not found
        """
        if article_id in self._article_cache:
            logger.debug(f"Using cached data for article {article_id}")
            return self._article_cache[article_id]

        max_retries = 3
        for retry in range(max_retries):
            try:
                logger.debug(
                    f"Fetching article {article_id} (attempt {retry + 1}/{max_retries})"
                )

                # Wait if we need to respect rate limits
                self.rate_limiter.wait_if_needed()

                # Use direct API call for better control
                url = f"{self.base_url}books/{article_id}/"

                response = requests.get(
                    url, headers={"Authorization": f"Token {self.token}"}
                )

                # Record this request
                self.rate_limiter.add_request()

                # Handle rate limiting
                if response.status_code == RATE_LIMIT:
                    self.rate_limiter.handle_429(response)
                    # Continue to the next retry attempt
                    continue

                response.raise_for_status()

                article = response.json()

                # Store in cache
                self._article_cache[article_id] = article
                logger.debug(f"Successfully fetched article {article_id}")
                return article

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == RATE_LIMIT and retry < max_retries - 1:
                    self.rate_limiter.handle_429(e.response)
                    continue
                logger.error(f"HTTP error fetching article {article_id}: {e}")
                return None
            except Exception as e:
                logger.error(f"Error fetching article {article_id}: {e}")
                if retry < max_retries - 1:
                    wait_time = (retry + 1) * 2  # Exponential backoff
                    logger.info(f"Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    return None

        logger.error(
            f"Failed to fetch article {article_id} after {max_retries} attempts"
        )
        return None

    def move_to_inbox(self, article_id: str) -> bool:
        """Move article to Inbox.

        Args:
            article_id: ID of the article to move

        Returns:
            True if successful, False otherwise
        """
        return self._update_article(
            article_id=article_id, data={"archived": False, "saved_for_later": False}
        )

    def move_to_later(self, article_id: str) -> bool:
        """Move article to Later.

        Args:
            article_id: ID of the article to move

        Returns:
            True if successful, False otherwise
        """
        return self._update_article(
            article_id, {"archived": False, "saved_for_later": True}
        )

    def move_to_archive(self, article_id: str) -> bool:
        """Move article to Archive.

        Args:
            article_id: ID of the article to move

        Returns:
            True if successful, False otherwise
        """
        return self._update_article(article_id=article_id, data={"archived": True})

    def toggle_read(self, article_id: str, read: bool) -> bool:
        """Toggle read/unread status of an article.

        Args:
            article_id: ID of the article to update
            read: True to mark as read, False for unread

        Returns:
            True if successful, False otherwise
        """
        return self._update_article(
            article_id=article_id, data={"state": "finished" if read else "reading"}
        )

    def _update_article(self, article_id: str, data: dict[str, Any]) -> bool:
        """Update an article with the given data.

        Args:
            article_id: ID of the article to update
            data: Data to update

        Returns:
            True if successful, False otherwise
        """
        max_retries = 3
        for retry in range(max_retries):
            try:
                logger.debug(
                    msg=f"Updating article {article_id} with data: {data} (attempt {retry + 1}/{max_retries})"
                )

                # Wait if we need to respect rate limits
                self.rate_limiter.wait_if_needed()

                # Direct API call to update the article
                url: str = f"{self.base_url}books/{article_id}/"

                response: requests.Response = requests.patch(
                    url=url, headers={"Authorization": f"Token {self.token}"}, json=data
                )

                # Record this request
                self.rate_limiter.add_request()

                # Handle rate limiting
                if response.status_code == RATE_LIMIT:
                    self.rate_limiter.handle_429(response)
                    # Continue to the next retry attempt
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

                # Invalidate category caches
                self._invalidate_cache()

                logger.debug(f"Successfully updated article {article_id}")
                return True

            except requests.exceptions.HTTPError as e:
                if e.response.status_code == RATE_LIMIT and retry < max_retries - 1:
                    self.rate_limiter.handle_429(e.response)
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

    def _fetch_articles_with_params(
        self, params: dict[str, str]
    ) -> list[dict[str, Any]]:
        """Fetch articles with the given parameters.

        Args:
            params: Query parameters

        Returns:
            List of articles
        """
        url: str = f"{self.base_url}books/"
        articles = []

        try:
            # Add page size parameter
            params["page_size"] = "50"

            # Make initial request with rate limiting
            next_url: str = url
            while next_url:
                # Respect rate limits
                self.rate_limiter.wait_if_needed()

                # Make the request
                if next_url == url:
                    # First request - include parameters
                    response: requests.Response = requests.get(
                        url=url,
                        headers={"Authorization": f"Token {self.token}"},
                        params=params,
                    )
                else:
                    # Pagination - use the full URL
                    response = requests.get(
                        url=next_url, headers={"Authorization": f"Token {self.token}"}
                    )

                # Record this request
                self.rate_limiter.add_request()

                # Handle rate limiting
                if response.status_code == RATE_LIMIT:
                    self.rate_limiter.handle_429(response)
                    # Don't update the URL, retry the same request
                    continue

                response.raise_for_status()

                data = response.json()
                articles.extend(data.get("results", []))

                # Get the next URL for pagination
                next_url = data.get("next")

            return articles
        except Exception as e:
            logger.error(f"Error fetching articles: {e}")
            raise

    def _invalidate_cache(self) -> None:
        """Invalidate all caches."""
        logger.debug("Invalidating all caches")
        self._inbox_cache = None
        self._later_cache = None
        self._archive_cache = None

    def clear_cache(self) -> None:
        """Clear the entire cache."""
        self._invalidate_cache()
        self._article_cache = {}
        logger.debug("Cleared entire cache")

    def close(self) -> None:
        """Close the client (if needed)."""
        # No resources to clean up
        logger.debug("Closed client")
