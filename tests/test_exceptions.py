"""Tests for the exceptions module."""

import pytest

from rwreader.exceptions import (
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


class TestRWReaderError:
    """Test cases for RWReaderError base exception."""

    def test_rwreader_error_creation(self) -> None:
        """Test creating RWReaderError."""
        error = RWReaderError("Test error message")
        assert str(error) == "Test error message"
        assert isinstance(error, Exception)

    def test_rwreader_error_inheritance(self) -> None:
        """Test that all custom exceptions inherit from RWReaderError."""
        assert issubclass(ConfigurationError, RWReaderError)
        assert issubclass(ReadwiseAPIError, RWReaderError)
        assert issubclass(CacheError, RWReaderError)
        assert issubclass(ArticleError, RWReaderError)


class TestConfigurationError:
    """Test cases for ConfigurationError."""

    def test_configuration_error_creation(self) -> None:
        """Test creating ConfigurationError."""
        error = ConfigurationError("Invalid configuration")
        assert str(error) == "Invalid configuration"
        assert isinstance(error, RWReaderError)

    def test_configuration_error_raise(self) -> None:
        """Test raising ConfigurationError."""
        with pytest.raises(ConfigurationError) as exc_info:
            raise ConfigurationError("Missing required field")
        assert "Missing required field" in str(exc_info.value)


class TestReadwiseAPIError:
    """Test cases for ReadwiseAPIError."""

    def test_api_error_with_status_code(self) -> None:
        """Test creating ReadwiseAPIError with status code."""
        error = ReadwiseAPIError("API error", status_code=500)
        assert str(error) == "API error"
        assert error.status_code == 500

    def test_api_error_without_status_code(self) -> None:
        """Test creating ReadwiseAPIError without status code."""
        error = ReadwiseAPIError("Generic API error")
        assert str(error) == "Generic API error"
        assert error.status_code is None

    def test_api_error_inheritance(self) -> None:
        """Test API error hierarchy."""
        assert issubclass(ReadwiseAuthenticationError, ReadwiseAPIError)
        assert issubclass(ReadwiseNotFoundError, ReadwiseAPIError)
        assert issubclass(ReadwiseRateLimitError, ReadwiseAPIError)
        assert issubclass(ReadwiseServerError, ReadwiseAPIError)


class TestReadwiseAuthenticationError:
    """Test cases for ReadwiseAuthenticationError."""

    def test_auth_error_default_message(self) -> None:
        """Test AuthenticationError with default message."""
        error = ReadwiseAuthenticationError()
        assert "Authentication failed" in str(error)
        assert error.status_code == 401

    def test_auth_error_custom_message(self) -> None:
        """Test AuthenticationError with custom message."""
        error = ReadwiseAuthenticationError("Invalid API token")
        assert str(error) == "Invalid API token"
        assert error.status_code == 401

    def test_auth_error_raise(self) -> None:
        """Test raising AuthenticationError."""
        with pytest.raises(ReadwiseAuthenticationError) as exc_info:
            raise ReadwiseAuthenticationError("Token expired")
        assert exc_info.value.status_code == 401


class TestReadwiseNotFoundError:
    """Test cases for ReadwiseNotFoundError."""

    def test_not_found_error_basic(self) -> None:
        """Test NotFoundError with basic message."""
        error = ReadwiseNotFoundError("Article not found")
        assert str(error) == "Article not found"
        assert error.status_code == 404
        assert error.resource_id is None

    def test_not_found_error_with_id(self) -> None:
        """Test NotFoundError with resource ID."""
        error = ReadwiseNotFoundError("Article not found", resource_id="article_123")
        assert str(error) == "Article not found"
        assert error.status_code == 404
        assert error.resource_id == "article_123"

    def test_not_found_error_raise(self) -> None:
        """Test raising NotFoundError."""
        with pytest.raises(ReadwiseNotFoundError) as exc_info:
            raise ReadwiseNotFoundError("Resource missing", resource_id="xyz")
        assert exc_info.value.resource_id == "xyz"


class TestReadwiseRateLimitError:
    """Test cases for ReadwiseRateLimitError."""

    def test_rate_limit_error_default(self) -> None:
        """Test RateLimitError with default message."""
        error = ReadwiseRateLimitError()
        assert "Rate limit exceeded" in str(error)
        assert error.status_code == 429
        assert error.retry_after is None

    def test_rate_limit_error_with_retry(self) -> None:
        """Test RateLimitError with retry_after."""
        error = ReadwiseRateLimitError(retry_after=60)
        assert error.status_code == 429
        assert error.retry_after == 60

    def test_rate_limit_error_custom_message(self) -> None:
        """Test RateLimitError with custom message and retry."""
        error = ReadwiseRateLimitError(
            "Too many requests", retry_after=120
        )
        assert str(error) == "Too many requests"
        assert error.retry_after == 120

    def test_rate_limit_error_raise(self) -> None:
        """Test raising RateLimitError."""
        with pytest.raises(ReadwiseRateLimitError) as exc_info:
            raise ReadwiseRateLimitError(retry_after=30)
        assert exc_info.value.retry_after == 30


class TestReadwiseServerError:
    """Test cases for ReadwiseServerError."""

    def test_server_error_default_status(self) -> None:
        """Test ServerError with default status code."""
        error = ReadwiseServerError("Internal server error")
        assert str(error) == "Internal server error"
        assert error.status_code == 500

    def test_server_error_custom_status(self) -> None:
        """Test ServerError with custom status code."""
        error = ReadwiseServerError("Service unavailable", status_code=503)
        assert str(error) == "Service unavailable"
        assert error.status_code == 503

    def test_server_error_raise(self) -> None:
        """Test raising ServerError."""
        with pytest.raises(ReadwiseServerError) as exc_info:
            raise ReadwiseServerError("Gateway timeout", status_code=504)
        assert exc_info.value.status_code == 504


class TestCacheError:
    """Test cases for CacheError."""

    def test_cache_error_creation(self) -> None:
        """Test creating CacheError."""
        error = CacheError("Cache operation failed")
        assert str(error) == "Cache operation failed"
        assert isinstance(error, RWReaderError)

    def test_cache_error_raise(self) -> None:
        """Test raising CacheError."""
        with pytest.raises(CacheError) as exc_info:
            raise CacheError("Cache is full")
        assert "Cache is full" in str(exc_info.value)


class TestArticleError:
    """Test cases for ArticleError."""

    def test_article_error_creation(self) -> None:
        """Test creating ArticleError."""
        error = ArticleError("Failed to parse article")
        assert str(error) == "Failed to parse article"
        assert isinstance(error, RWReaderError)

    def test_article_error_raise(self) -> None:
        """Test raising ArticleError."""
        with pytest.raises(ArticleError) as exc_info:
            raise ArticleError("Invalid article format")
        assert "Invalid article format" in str(exc_info.value)


class TestExceptionCatchAll:
    """Test cases for catching exceptions."""

    def test_catch_all_rwreader_errors(self) -> None:
        """Test catching all RWReaderError subclasses."""
        exceptions_to_test = [
            ConfigurationError("config error"),
            ReadwiseAPIError("api error"),
            ReadwiseAuthenticationError(),
            ReadwiseNotFoundError("not found"),
            ReadwiseRateLimitError(),
            ReadwiseServerError("server error"),
            CacheError("cache error"),
            ArticleError("article error"),
        ]

        for exception in exceptions_to_test:
            with pytest.raises(RWReaderError):
                raise exception

    def test_exception_chain(self) -> None:
        """Test exception chaining."""
        try:
            try:
                raise ReadwiseAuthenticationError("Invalid token")
            except ReadwiseAuthenticationError as e:
                raise ConfigurationError("Configuration issue") from e
        except ConfigurationError as final_error:
            assert isinstance(final_error.__cause__, ReadwiseAuthenticationError)
            assert "Invalid token" in str(final_error.__cause__)
