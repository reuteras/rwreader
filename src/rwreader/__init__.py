"""Main module for rwreader package."""

from .exceptions import (
    ArticleError,
    CacheError,
    ConfigurationError,
    ReadwiseAPIError,
    ReadwiseAuthenticationError,
    ReadwiseNotFoundError,
    ReadwiseRateLimitError,
    ReadwiseServerError,
    RWReaderError,
)
from .main import main

__all__: list[str] = [
    "ArticleError",
    "CacheError",
    "ConfigurationError",
    "RWReaderError",
    "ReadwiseAPIError",
    "ReadwiseAuthenticationError",
    "ReadwiseNotFoundError",
    "ReadwiseRateLimitError",
    "ReadwiseServerError",
    "main",
]

if __name__ == "__main__":
    main()  # pragma: no cover
