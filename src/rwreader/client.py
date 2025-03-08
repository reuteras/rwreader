"""Client module for rwreader."""

import logging
from typing import Any, Dict, List, Optional

import httpx

from .cache import LimitedSizeDict

logger: logging.Logger = logging.getLogger(name=__name__)

class ReadwiseClient:
    """Client for interacting with the Readwise Reader API."""
    
    def __init__(self, token: str, cache_size: int = 1000) -> None:
        """Initialize the Readwise Reader client.
        
        Args:
            token: Readwise API token
            cache_size: Maximum number of items to store in cache
        """
        self.token = token
        # Use the correct API endpoint for Readwise Reader
        self.base_url = "https://readwise.io/api/v2/"
        self.session = httpx.Client(
            headers={"Authorization": f"Token {token}"},
            timeout=30.0,
            follow_redirects=True
        )
        self.cache = LimitedSizeDict(max_size=cache_size)
        
        # Log API version info
        logger.debug(f"Initializing Readwise client with API base URL: {self.base_url}")
    
    def get_library(self, query: Optional[str] = None, 
                   page: int = 1, page_size: int = 50, 
                   location: str = "new") -> List[Dict[str, Any]]:
        """Get library items with optional filtering.
        
        Args:
            query: Optional search query
            page: Page number for pagination
            page_size: Number of items per page
            location: Filter by location (new, archive)
            
        Returns:
            List of library items
        """
        cache_key = f"library_{query}_{page}_{page_size}_{location}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # For Reader, use the books endpoint
        endpoint = "books"
        
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        # Add location filter if provided
        if location == "archive":
            params["archived"] = "true"
        
        if query:
            params["query"] = query
            
        try:
            full_url = f"{self.base_url}{endpoint}/"
            logger.debug(f"Fetching library from: {full_url} with params: {params}")
            
            response = self.session.get(full_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Handle different response formats
            results = data.get("results", [])
            if not results and isinstance(data, list):
                results = data
                
            self.cache[cache_key] = results
            return results
        except httpx.HTTPError as e:
            logger.error(f"Error fetching library: {e}")
            return []
    
    def get_article(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Get full article content.
        
        Args:
            article_id: ID of the article to retrieve
            
        Returns:
            Article data or None if not found
        """
        cache_key = f"article_{article_id}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            full_url = f"{self.base_url}books/{article_id}/"
            logger.debug(f"Fetching article from: {full_url}")
            
            response = self.session.get(full_url)
            response.raise_for_status()
            article = response.json()
            
            # For consistent API, ensure some standard fields are present
            if "content" not in article and "html" in article:
                article["content"] = article["html"]
            
            if "title" not in article and "full_title" in article:
                article["title"] = article["full_title"]
                
            self.cache[cache_key] = article
            return article
        except httpx.HTTPError as e:
            logger.error(f"Error fetching article {article_id}: {e}")
            return None
    
    def get_collections(self) -> List[Dict[str, Any]]:
        """Get user collections.
        
        Returns:
            List of collections
        """
        cache_key = "collections"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        try:
            # Try different collection endpoints
            endpoints = ["folders", "tags"]
            collections = []
            
            for endpoint in endpoints:
                full_url = f"{self.base_url}{endpoint}/"
                logger.debug(f"Trying to fetch collections from: {full_url}")
                
                try:
                    response = self.session.get(full_url)
                    response.raise_for_status()
                    data = response.json()
                    
                    # Handle different response formats
                    if "results" in data:
                        items = data.get("results", [])
                    elif isinstance(data, list):
                        items = data
                    else:
                        items = []
                    
                    # Standardize the format
                    for item in items:
                        if "name" not in item and "title" in item:
                            item["name"] = item["title"]
                        elif "name" not in item and "tag" in item:
                            item["name"] = item["tag"]
                        
                        # Add source information
                        item["source"] = endpoint
                    
                    collections.extend(items)
                    logger.debug(f"Found {len(items)} collections from {endpoint}")
                    
                except httpx.HTTPError as e:
                    logger.debug(f"Failed to fetch from {endpoint}: {e}")
            
            # If we got collections, cache them
            if collections:
                self.cache[cache_key] = collections
                
            return collections
        except Exception as e:
            logger.error(f"Error fetching collections: {e}")
            return []
    
    def get_collection_items(self, collection_id: str, 
                           page: int = 1, page_size: int = 50) -> List[Dict[str, Any]]:
        """Get items in a collection.
        
        Args:
            collection_id: ID of the collection
            page: Page number for pagination
            page_size: Number of items per page
            
        Returns:
            List of items in the collection
        """
        cache_key = f"collection_{collection_id}_{page}_{page_size}"
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        params = {
            "page": page,
            "page_size": page_size,
        }
        
        try:
            # First, check if we know the source of this collection
            collection_source = None
            collections = self.get_collections()
            for collection in collections:
                if str(collection.get("id")) == str(collection_id):
                    collection_source = collection.get("source")
                    break
            
            # If we know the source, use the appropriate endpoint
            if collection_source:
                endpoint = collection_source
            else:
                # Try to guess based on the ID format
                if collection_id.isdigit():
                    endpoint = "folders"
                else:
                    endpoint = "tags"
            
            full_url = f"{self.base_url}{endpoint}/{collection_id}/books/"
            logger.debug(f"Fetching collection items from: {full_url}")
            
            response = self.session.get(full_url, params=params)
            response.raise_for_status()
            data = response.json()
            
            # Handle different response formats
            if "results" in data:
                items = data.get("results", [])
            elif isinstance(data, list):
                items = data
            else:
                items = []
                
            self.cache[cache_key] = items
            return items
        except httpx.HTTPError as e:
            logger.error(f"Error fetching collection items: {e}")
            return []
    
    def update_article_status(self, article_id: str, 
                             archived: Optional[bool] = None, 
                             read: Optional[bool] = None) -> bool:
        """Update article status.
        
        Args:
            article_id: ID of the article to update
            archived: Set archived status
            read: Set read status
            
        Returns:
            True if successful, False otherwise
        """
        data = {}
        if archived is not None:
            data["archived"] = archived
        if read is not None:
            data["state"] = "finished" if read else "reading"
            
        if not data:
            return True  # Nothing to update
            
        try:
            full_url = f"{self.base_url}books/{article_id}/"
            logger.debug(f"Updating article status at: {full_url} with data: {data}")
            
            response = self.session.patch(full_url, json=data)
            response.raise_for_status()
            
            # Update cache if we have this article cached
            cache_key = f"article_{article_id}"
            if cache_key in self.cache:
                article = self.cache[cache_key]
                if archived is not None:
                    article["archived"] = archived
                if read is not None:
                    article["state"] = "finished" if read else "reading"
                    article["read"] = read  # For our internal API consistency
                self.cache[cache_key] = article
                
            # Invalidate library cache as it might have changed
            self._invalidate_library_cache()
                
            return True
        except httpx.HTTPError as e:
            logger.error(f"Error updating article {article_id}: {e}")
            return False
    
    def mark_as_read(self, article_id: str) -> bool:
        """Mark article as read.
        
        Args:
            article_id: ID of the article to mark as read
            
        Returns:
            True if successful, False otherwise
        """
        return self.update_article_status(article_id=article_id, read=True)
    
    def mark_as_unread(self, article_id: str) -> bool:
        """Mark article as unread.
        
        Args:
            article_id: ID of the article to mark as unread
            
        Returns:
            True if successful, False otherwise
        """
        return self.update_article_status(article_id=article_id, read=False)
    
    def archive_article(self, article_id: str) -> bool:
        """Archive an article.
        
        Args:
            article_id: ID of the article to archive
            
        Returns:
            True if successful, False otherwise
        """
        return self.update_article_status(article_id=article_id, archived=True)
    
    def unarchive_article(self, article_id: str) -> bool:
        """Unarchive an article.
        
        Args:
            article_id: ID of the article to unarchive
            
        Returns:
            True if successful, False otherwise
        """
        return self.update_article_status(article_id=article_id, archived=False)
    
    def _invalidate_library_cache(self) -> None:
        """Invalidate library-related cache entries."""
        keys_to_remove = [k for k in self.cache if k.startswith("library_")]
        for key in keys_to_remove:
            del self.cache[key]
            
        # Also invalidate collection items as they might have changed
        keys_to_remove = [k for k in self.cache if k.startswith("collection_")]
        for key in keys_to_remove:
            del self.cache[key]
    
    def clear_cache(self) -> None:
        """Clear the entire cache."""
        self.cache.clear()
        
    def close(self) -> None:
        """Close the HTTP session."""
        self.session.close()
