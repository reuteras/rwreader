"""Hybrid client module using both readwise-api and direct API access."""

import logging
import os
import requests
from typing import Any, Dict, List, Optional, Tuple

# Import from the readwise library
import readwise
from readwise.model import Document

logger: logging.Logger = logging.getLogger(name=__name__)

class ReadwiseClient:
    """Hybrid client for interacting with the Readwise Reader API."""
    
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
        
        logger.debug("Initialized hybrid Readwise client")
        
        # Initialize category caches
        self._inbox_cache = None
        self._later_cache = None
        self._archive_cache = None
        self._article_cache = {}
    
    def get_inbox(self) -> List[Dict[str, Any]]:
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
            params = {
                "archived": "false",
                "saved_for_later": "false"
            }
            
            articles = self._fetch_articles_with_params(params)
            
            logger.debug(f"Fetched {len(articles)} inbox articles")
            self._inbox_cache = articles
            return articles
        except Exception as e:
            logger.error(f"Error fetching inbox: {e}")
            return []

    def get_later(self) -> List[Dict[str, Any]]:
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
            params = {
                "archived": "false",
                "saved_for_later": "true"
            }
            
            articles = self._fetch_articles_with_params(params)
            
            logger.debug(f"Fetched {len(articles)} later articles")
            self._later_cache = articles
            return articles
        except Exception as e:
            logger.error(f"Error fetching later: {e}")
            return []
            
    def get_archive(self) -> List[Dict[str, Any]]:
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
            params = {
                "archived": "true"
            }
            
            articles = self._fetch_articles_with_params(params)
            
            logger.debug(f"Fetched {len(articles)} archive articles")
            self._archive_cache = articles
            return articles
        except Exception as e:
            logger.error(f"Error fetching archive: {e}")
            return []
    
    def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Get full article content.
        
        Args:
            article_id: ID of the article to retrieve
            
        Returns:
            Article data in dict format or None if not found
        """
        if article_id in self._article_cache:
            logger.debug(f"Using cached data for article {article_id}")
            return self._article_cache[article_id]
        
        try:
            logger.debug(f"Fetching article {article_id}")
            # Use direct API call for better control
            url = f"{self.base_url}books/{article_id}/"
            
            response = requests.get(
                url,
                headers={"Authorization": f"Token {self.token}"}
            )
            response.raise_for_status()
            
            article = response.json()
            
            # Store in cache
            self._article_cache[article_id] = article
            logger.debug(f"Successfully fetched article {article_id}")
            return article
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
        return self._update_article(article_id, {
            "archived": False,
            "saved_for_later": False
        })
    
    def move_to_later(self, article_id: str) -> bool:
        """Move article to Later.
        
        Args:
            article_id: ID of the article to move
            
        Returns:
            True if successful, False otherwise
        """
        return self._update_article(article_id, {
            "archived": False,
            "saved_for_later": True
        })
    
    def move_to_archive(self, article_id: str) -> bool:
        """Move article to Archive.
        
        Args:
            article_id: ID of the article to move
            
        Returns:
            True if successful, False otherwise
        """
        return self._update_article(article_id, {
            "archived": True
        })
    
    def toggle_read(self, article_id: str, read: bool) -> bool:
        """Toggle read/unread status of an article.
        
        Args:
            article_id: ID of the article to update
            read: True to mark as read, False for unread
            
        Returns:
            True if successful, False otherwise
        """
        return self._update_article(article_id, {
            "state": "finished" if read else "reading"
        })
    
    def _update_article(self, article_id: str, data: Dict[str, Any]) -> bool:
        """Update an article with the given data.
        
        Args:
            article_id: ID of the article to update
            data: Data to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            logger.debug(f"Updating article {article_id} with data: {data}")
            
            # Direct API call to update the article
            url = f"{self.base_url}books/{article_id}/"
            
            response = requests.patch(
                url,
                headers={"Authorization": f"Token {self.token}"},
                json=data
            )
            response.raise_for_status()
            
            # Update cache if needed
            if article_id in self._article_cache:
                for key, value in data.items():
                    self._article_cache[article_id][key] = value
                    
                # Handle special cases
                if "state" in data:
                    self._article_cache[article_id]["read"] = data["state"] == "finished"
            
            # Invalidate category caches
            self._invalidate_cache()
            
            logger.debug(f"Successfully updated article {article_id}")
            return True
        except Exception as e:
            logger.error(f"Error updating article {article_id}: {e}")
            return False
    
    def _fetch_articles_with_params(self, params: Dict[str, str]) -> List[Dict[str, Any]]:
        """Fetch articles with the given parameters.
        
        Args:
            params: Query parameters
            
        Returns:
            List of articles
        """
        url = f"{self.base_url}books/"
        articles = []
        
        try:
            # Add page size parameter
            params["page_size"] = "50"
            
            # Make initial request
            response = requests.get(
                url,
                headers={"Authorization": f"Token {self.token}"},
                params=params
            )
            response.raise_for_status()
            
            data = response.json()
            articles.extend(data.get("results", []))
            
            # Handle pagination if needed
            next_url = data.get("next")
            while next_url:
                response = requests.get(
                    next_url,
                    headers={"Authorization": f"Token {self.token}"}
                )
                response.raise_for_status()
                
                data = response.json()
                articles.extend(data.get("results", []))
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