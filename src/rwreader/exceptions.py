"""Custom exceptions for rwreader."""


class RWReaderError(Exception):
    """Base exception for all rwreader errors."""

    pass


class ConfigurationError(RWReaderError):
    """Raised when there's an error with configuration."""

    pass


class ReadwiseAPIError(RWReaderError):
    """Base exception for Readwise API errors."""

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialize ReadwiseAPIError.

        Args:
            message: Error message
            status_code: HTTP status code if applicable
        """
        super().__init__(message)
        self.status_code = status_code


class ReadwiseAuthenticationError(ReadwiseAPIError):
    """Raised when authentication fails (401)."""

    def __init__(
        self, message: str = "Authentication failed. Check your API token."
    ) -> None:
        """Initialize ReadwiseAuthenticationError.

        Args:
            message: Error message
        """
        super().__init__(message, status_code=401)


class ReadwiseNotFoundError(ReadwiseAPIError):
    """Raised when a resource is not found (404)."""

    def __init__(self, message: str, resource_id: str | None = None) -> None:
        """Initialize ReadwiseNotFoundError.

        Args:
            message: Error message
            resource_id: ID of the resource that wasn't found
        """
        super().__init__(message, status_code=404)
        self.resource_id = resource_id


class ReadwiseRateLimitError(ReadwiseAPIError):
    """Raised when rate limit is exceeded (429)."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please try again later.",
        retry_after: int | None = None,
    ) -> None:
        """Initialize ReadwiseRateLimitError.

        Args:
            message: Error message
            retry_after: Seconds to wait before retrying
        """
        super().__init__(message, status_code=429)
        self.retry_after = retry_after


class ReadwiseServerError(ReadwiseAPIError):
    """Raised when server returns 5xx error."""

    def __init__(self, message: str, status_code: int = 500) -> None:
        """Initialize ReadwiseServerError.

        Args:
            message: Error message
            status_code: HTTP status code
        """
        super().__init__(message, status_code=status_code)


class CacheError(RWReaderError):
    """Raised when there's an error with caching operations."""

    pass


class ArticleError(RWReaderError):
    """Raised when there's an error processing an article."""

    pass
