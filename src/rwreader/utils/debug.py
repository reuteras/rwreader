"""Debugging utilities for rwreader."""

import json
import logging
from typing import Any, Dict, List, Optional

logger: logging.Logger = logging.getLogger(name=__name__)

def print_api_response(response: Any, prefix: str = "API Response") -> None:
    """Log an API response for debugging.
    
    Args:
        response: Response to log
        prefix: Prefix for the log message
    """
    try:
        # Try to convert to a string for logging
        if hasattr(response, "json"):
            # For httpx response objects
            data = response.json()
            logger.debug(f"{prefix} (JSON): {json.dumps(data, indent=2)}")
        elif isinstance(response, (dict, list)):
            # For dictionaries and lists
            logger.debug(f"{prefix}: {json.dumps(response, indent=2)}")
        else:
            # For other objects
            logger.debug(f"{prefix}: {response}")
    except Exception as e:
        logger.error(f"Error logging API response: {e}")

def inspect_readwise_categories(client) -> None:
    """Inspect Readwise categories and log results.
    
    Args:
        client: ReadwiseClient instance to use
    """
    try:
        # Test each category
        categories = ["inbox", "later", "archive"]
        
        for category in categories:
            logger.debug(f"Testing category: {category}")
            
            # Get articles for this category
            articles = client.get_library_by_category(category=category)
            
            # Log results
            logger.debug(f"  Found {len(articles)} articles")
            
            # Log some sample articles
            if articles:
                for i, article in enumerate(articles[:3]):
                    logger.debug(f"  Sample article {i+1}:")
                    logger.debug(f"    ID: {article.get('id')}")
                    logger.debug(f"    Title: {article.get('title', 'Untitled')}")
                    logger.debug(f"    Archived: {article.get('archived', False)}")
                    logger.debug(f"    Saved for Later: {article.get('saved_for_later', False)}")
                    logger.debug(f"    Read: {article.get('read', False)}")
                    logger.debug(f"    State: {article.get('state', 'unknown')}")
    except Exception as e:
        logger.error(f"Error inspecting Readwise categories: {e}")

# Add this method to the ReadwiseClient class
def debug_api_call(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> None:
    """Make a direct API call for debugging purposes.
    
    Args:
        endpoint: API endpoint to call (e.g., "books")
        params: Optional query parameters
    """
    try:
        full_url = f"{self.base_url}{endpoint}/"
        logger.debug(f"Debug API call to: {full_url} with params: {params}")
        
        response = self.session.get(full_url, params=params)
        response.raise_for_status()
        
        # Log the raw response
        logger.debug(f"Raw response status: {response.status_code}")
        
        # Try to parse as JSON
        try:
            data = response.json()
            
            # Log summary info
            if isinstance(data, dict):
                if "count" in data:
                    logger.debug(f"Total count: {data['count']}")
                if "results" in data:
                    logger.debug(f"Results count: {len(data['results'])}")
                    logger.debug(f"First few results: {data['results'][:3]}")
                else:
                    logger.debug(f"Keys in response: {list(data.keys())}")
            elif isinstance(data, list):
                logger.debug(f"List response with {len(data)} items")
                logger.debug(f"First few items: {data[:3]}")
            
            # Log detailed response for debugging
            logger.debug(f"Full response data: {json.dumps(data, indent=2)}")
            
            return data
        except json.JSONDecodeError:
            logger.error("Response was not valid JSON")
            logger.debug(f"Response text: {response.text}")
            return None
    except Exception as e:
        logger.error(f"Error in debug API call: {e}")
        return None
