"""Utilities for sanitizing sensitive information in logs."""

import json
import re
import copy
from typing import Any, Dict, List, Union

def sanitize_headers(headers: Dict[str, str]) -> Dict[str, str]:
    """Sanitize headers by redacting sensitive information.
    
    Args:
        headers: Dict of headers to sanitize
        
    Returns:
        Sanitized headers dict
    """
    sanitized = {}
    sensitive_headers = [
        "authorization", "cookie", "set-cookie", "x-api-key", 
        "token", "api-key", "auth", "session", "csrf"
    ]
    
    for key, value in headers.items():
        lower_key = key.lower()
        if any(sensitive in lower_key for sensitive in sensitive_headers):
            sanitized[key] = "*** REDACTED ***"
        else:
            sanitized[key] = value
            
    return sanitized

def sanitize_api_response(data: Any) -> Any:
    """Sanitize API response data by redacting sensitive fields.
    
    Args:
        data: Response data to sanitize
        
    Returns:
        Sanitized data
    """
    if data is None:
        return None
        
    if isinstance(data, (str, bytes)):
        # Try to parse as JSON
        try:
            parsed = json.loads(data)
            sanitized = sanitize_api_response(parsed)
            return json.dumps(sanitized)
        except (json.JSONDecodeError, TypeError):
            # If it's not valid JSON, redact any tokens
            return redact_tokens_in_text(data)
    
    if isinstance(data, dict):
        sanitized = {}
        sensitive_keys = [
            "token", "api_key", "apikey", "key", "secret", "password", 
            "auth", "authorization", "session", "cookie", "credential"
        ]
        
        for key, value in data.items():
            lower_key = key.lower()
            if any(sensitive in lower_key for sensitive in sensitive_keys):
                sanitized[key] = "*** REDACTED ***"
            else:
                sanitized[key] = sanitize_api_response(value)
                
        return sanitized
    
    if isinstance(data, list):
        return [sanitize_api_response(item) for item in data]
    
    # Return primitive types as is
    return data

def redact_tokens_in_text(text: Union[str, bytes]) -> Union[str, bytes]:
    """Redact tokens and other sensitive patterns in text.
    
    Args:
        text: Text to redact
        
    Returns:
        Text with sensitive information redacted
    """
    if isinstance(text, bytes):
        try:
            text_str = text.decode('utf-8')
            redacted_str = redact_tokens_in_text(text_str)
            return redacted_str.encode('utf-8')
        except UnicodeDecodeError:
            # Can't decode, return as is
            return text
            
    if not isinstance(text, str):
        # Not a string, return as is
        return text
        
    # Patterns for common sensitive information
    patterns = [
        # API tokens and keys (usually long alphanumeric strings)
        r'[\'"]?(?:api_?key|token|auth|secret|password)[\'"]?\s*[:=]\s*[\'"]([a-zA-Z0-9_\-\.]{20,})[\'"]',
        
        # Bearer tokens
        r'[Bb]earer\s+([a-zA-Z0-9_\-\.]{20,})',
        
        # Basic auth
        r'[Bb]asic\s+([a-zA-Z0-9+/=]{10,})',
        
        # URLs with embedded credentials
        r'https?://(?:[^:@]+:([^@]+))@[^/]+'
    ]
    
    # Apply each pattern
    redacted = text
    for pattern in patterns:
        redacted = re.sub(pattern, r'*** REDACTED ***', redacted)
        
    return redacted

def sanitize_log_message(message: Any) -> Any:
    """Sanitize a log message by redacting sensitive information.
    
    Args:
        message: Log message to sanitize
        
    Returns:
        Sanitized log message
    """
    if isinstance(message, dict):
        if "headers" in message:
            sanitized = copy.deepcopy(message)
            sanitized["headers"] = sanitize_headers(message["headers"])
            return sanitized
        else:
            return sanitize_api_response(message)
    elif isinstance(message, (str, bytes)):
        return redact_tokens_in_text(message)
    else:
        # For other types, convert to string and check
        try:
            str_message = str(message)
            return redact_tokens_in_text(str_message)
        except Exception:
            return message