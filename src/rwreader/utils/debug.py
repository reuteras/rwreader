"""Debug functions for the client."""

import json
import logging
from typing import Any, Dict, Optional

from ..utils.sanitize import sanitize_log_message, sanitize_headers, sanitize_api_response

logger: logging.Logger = logging.getLogger(name=__name__)

def safe_debug_log(msg: str, obj: Any = None) -> None:
    """Log a debug message with sanitized object information.
    
    Args:
        msg: The message to log
        obj: The object to log (will be sanitized)
    """
    if obj is not None:
        sanitized = sanitize_log_message(obj)
        if isinstance(sanitized, (dict, list)):
            logger.debug(f"{msg}: {json.dumps(sanitized, indent=2)}")
        else:
            logger.debug(f"{msg}: {sanitized}")
    else:
        logger.debug(msg)

def print_api_response_safe(response: Any, prefix: str = "API Response") -> None:
    """Log an API response for debugging with sensitive information redacted.
    
    Args:
        response: Response to log
        prefix: Prefix for the log message
    """
    try:
        # Try to convert to a string for logging
        if hasattr(response, "json") and hasattr(response, "headers"):
            # For httpx response objects
            # Log status code and headers (sanitized)
            safe_debug_log(f"{prefix} status: {response.status_code}")
            safe_debug_log(f"{prefix} headers", dict(response.headers))
            
            # Log the JSON body (sanitized)
            try:
                data = response.json()
                safe_debug_log(f"{prefix} (JSON)", data)
            except ValueError:
                # Not JSON, log text content (sanitized)
                content = response.text if hasattr(response, "text") else str(response)
                safe_debug_log(f"{prefix} (text)", content)
        elif isinstance(response, (dict, list)):
            # For dictionaries and lists
            safe_debug_log(prefix, response)
        else:
            # For other objects
            safe_debug_log(f"{prefix}", str(response))
    except Exception as e:
        logger.error(f"Error logging API response: {e}")

def debug_api_call_safe(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> Any:
    """Make a direct API call for debugging purposes with sanitized logging.
    
    Args:
        endpoint: API endpoint to call (e.g., "books")
        params: Optional query parameters
        
    Returns:
        Response data or None on error
    """
    try:
        full_url = f"{self.base_url}{endpoint}/"
        safe_debug_log(f"Debug API call to: {full_url} with params", params)
        
        response = self.session.get(full_url, params=params)
        response.raise_for_status()
        
        # Log the raw response
        safe_debug_log(f"Raw response status: {response.status_code}")
        safe_debug_log("Response headers", dict(response.headers))
        
        # Try to parse as JSON
        try:
            data = response.json()
            
            # Log summary info
            if isinstance(data, dict):
                if "count" in data:
                    safe_debug_log(f"Total count: {data['count']}")
                if "results" in data:
                    safe_debug_log(f"Results count: {len(data['results'])}")
                    safe_debug_log(f"First few results (sanitized)", 
                                  sanitize_api_response(data['results'][:3]))
                else:
                    safe_debug_log(f"Keys in response: {list(data.keys())}")
            elif isinstance(data, list):
                safe_debug_log(f"List response with {len(data)} items")
                if data:
                    safe_debug_log(f"First few items (sanitized)", 
                                  sanitize_api_response(data[:3]))
            
            # Log detailed response for debugging (sanitized)
            safe_debug_log(f"Full response data (sanitized)", sanitize_api_response(data))
            
            return data
        except json.JSONDecodeError:
            logger.error("Response was not valid JSON")
            safe_debug_log(f"Response text (sanitized)", 
                          sanitize_log_message(response.text if hasattr(response, "text") else str(response)))
            return None
    except Exception as e:
        logger.error(f"Error in debug API call: {e}")
        return None

# Replacement for dump_debug_info method
def dump_debug_info_safe(self) -> None:
    """Dump debugging information to the log with sensitive data redacted."""
    try:
        # Test each category
        safe_debug_log("=== DEBUG INFORMATION ===")
        
        # User info
        try:
            user_response = self.session.get(f"{self.base_url}user/")
            user_response.raise_for_status()
            user_data = user_response.json()
            safe_debug_log("User info (sanitized)", sanitize_api_response(user_data))
        except Exception as e:
            logger.error(f"Error fetching user info: {e}")
        
        # Category counts
        for category in ["inbox", "later", "archive"]:
            try:
                if category == "inbox":
                    params = {"archived": "false", "saved_for_later": "false", "page_size": 1}
                elif category == "later":
                    params = {"archived": "false", "saved_for_later": "true", "page_size": 1}
                else:  # archive
                    params = {"archived": "true", "page_size": 1}
                
                count_response = self.session.get(f"{self.base_url}books/", params=params)
                count_response.raise_for_status()
                count_data = count_response.json()
                
                if "count" in count_data:
                    safe_debug_log(f"{category.capitalize()} count: {count_data['count']}")
                safe_debug_log(f"{category.capitalize()} query params", params)
            except Exception as e:
                logger.error(f"Error fetching {category} count: {e}")
        
        safe_debug_log("=== END DEBUG INFORMATION ===")
    except Exception as e:
        logger.error(f"Error in dump_debug_info: {e}")