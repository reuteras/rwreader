"""Tests for the cache module."""

import pytest

from rwreader.cache import LimitedSizeDict


class TestLimitedSizeDict:
    """Test cases for LimitedSizeDict class."""

    def test_init(self) -> None:
        """Test initialization of LimitedSizeDict."""
        cache = LimitedSizeDict(max_size=5)
        assert cache.max_size == 5
        assert len(cache) == 0

    def test_add_items_within_limit(self) -> None:
        """Test adding items within the size limit."""
        cache = LimitedSizeDict(max_size=3)
        cache["key1"] = "value1"
        cache["key2"] = "value2"
        cache["key3"] = "value3"

        assert len(cache) == 3
        assert cache["key1"] == "value1"
        assert cache["key2"] == "value2"
        assert cache["key3"] == "value3"

    def test_evict_oldest_when_full(self) -> None:
        """Test that oldest item is evicted when cache is full."""
        cache = LimitedSizeDict(max_size=3)
        cache["key1"] = "value1"
        cache["key2"] = "value2"
        cache["key3"] = "value3"
        cache["key4"] = "value4"  # This should evict key1

        assert len(cache) == 3
        assert "key1" not in cache
        assert cache["key2"] == "value2"
        assert cache["key3"] == "value3"
        assert cache["key4"] == "value4"

    def test_update_existing_key(self) -> None:
        """Test updating an existing key moves it to end."""
        cache = LimitedSizeDict(max_size=3)
        cache["key1"] = "value1"
        cache["key2"] = "value2"
        cache["key3"] = "value3"

        # Update key1, moving it to the end
        cache["key1"] = "new_value1"

        # Add key4, which should evict key2 (now oldest)
        cache["key4"] = "value4"

        assert len(cache) == 3
        assert "key2" not in cache  # key2 should be evicted
        assert cache["key1"] == "new_value1"
        assert cache["key3"] == "value3"
        assert cache["key4"] == "value4"

    def test_max_size_one(self) -> None:
        """Test cache with max_size of 1."""
        cache = LimitedSizeDict(max_size=1)
        cache["key1"] = "value1"
        assert len(cache) == 1
        assert cache["key1"] == "value1"

        cache["key2"] = "value2"
        assert len(cache) == 1
        assert "key1" not in cache
        assert cache["key2"] == "value2"

    def test_order_preservation(self) -> None:
        """Test that order is preserved according to insertion/update."""
        cache = LimitedSizeDict(max_size=3)
        cache["a"] = 1
        cache["b"] = 2
        cache["c"] = 3

        # Check order
        assert list(cache.keys()) == ["a", "b", "c"]

        # Update 'a' to move it to end
        cache["a"] = 10
        assert list(cache.keys()) == ["b", "c", "a"]

    def test_contains(self) -> None:
        """Test the 'in' operator."""
        cache = LimitedSizeDict(max_size=3)
        cache["key1"] = "value1"

        assert "key1" in cache
        assert "key2" not in cache

    def test_get_method(self) -> None:
        """Test the get method with default values."""
        cache = LimitedSizeDict(max_size=3)
        cache["key1"] = "value1"

        assert cache.get("key1") == "value1"
        assert cache.get("key2") is None
        assert cache.get("key2", "default") == "default"

    def test_pop_method(self) -> None:
        """Test popping items from cache."""
        cache = LimitedSizeDict(max_size=3)
        cache["key1"] = "value1"
        cache["key2"] = "value2"

        value = cache.pop("key1")
        assert value == "value1"
        assert "key1" not in cache
        assert len(cache) == 1

    def test_clear_method(self) -> None:
        """Test clearing the cache."""
        cache = LimitedSizeDict(max_size=3)
        cache["key1"] = "value1"
        cache["key2"] = "value2"

        cache.clear()
        assert len(cache) == 0
        assert "key1" not in cache

    def test_keys_values_items(self) -> None:
        """Test keys(), values(), and items() methods."""
        cache = LimitedSizeDict(max_size=3)
        cache["a"] = 1
        cache["b"] = 2

        assert list(cache.keys()) == ["a", "b"]
        assert list(cache.values()) == [1, 2]
        assert list(cache.items()) == [("a", 1), ("b", 2)]

    def test_multiple_evictions(self) -> None:
        """Test multiple evictions in sequence."""
        cache = LimitedSizeDict(max_size=2)
        cache["key1"] = "value1"
        cache["key2"] = "value2"
        cache["key3"] = "value3"  # Evicts key1
        cache["key4"] = "value4"  # Evicts key2

        assert len(cache) == 2
        assert "key1" not in cache
        assert "key2" not in cache
        assert cache["key3"] == "value3"
        assert cache["key4"] == "value4"
