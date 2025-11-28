# Testing Guide for rwreader

This document provides comprehensive information about testing the rwreader application.

## Table of Contents

- [Overview](#overview)
- [Test Structure](#test-structure)
- [Running Tests](#running-tests)
- [Test Coverage](#test-coverage)
- [Writing Tests](#writing-tests)
- [Continuous Integration](#continuous-integration)
- [Troubleshooting](#troubleshooting)

## Overview

The rwreader project uses **pytest** as its testing framework with comprehensive test coverage across all components. The test suite includes:

- **Unit tests** for individual modules (client, config, cache, etc.)
- **Integration tests** for the TUI application
- **Mocking** for external dependencies (Readwise API, 1Password CLI)
- **Async tests** using pytest-asyncio for async operations
- **Coverage reporting** with pytest-cov

### Test Statistics

- **154 tests** covering core functionality
- **43% code coverage** with room for improvement
- **Multiple test categories**: unit, integration, and functional tests

## Test Structure

```
tests/
├── __init__.py
├── conftest.py                    # Shared fixtures
├── test_app_integration.py        # TUI app integration tests
├── test_cache.py                  # Cache module tests
├── test_client.py                 # Readwise API client tests
├── test_config.py                 # Configuration handling tests
├── test_exceptions.py             # Custom exception tests
├── test_markdown_converter.py     # Markdown conversion tests
└── test_ui_helpers.py             # UI utility function tests
```

## Running Tests

### Prerequisites

```bash
# Create virtual environment and install dependencies
uv venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
uv pip install -e .
uv pip install pytest pytest-cov pytest-asyncio mypy types-requests textual-dev toml
```

### Basic Test Commands

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run with coverage
pytest --cov=rwreader --cov-report=term-missing

# Run specific test file
pytest tests/test_client.py

# Run specific test
pytest tests/test_client.py::TestReadwiseClient::test_get_inbox_from_cache
```

## Test Coverage

Current overall coverage: **43%**

High coverage modules:
- cache.py: 100%
- exceptions.py: 100%
- ui_helpers.py: 92%
- config.py: 88%

Areas needing more tests:
- UI screens (article_list, article_reader)
- UI widgets (api_status, article_viewer, load_more)
- Client error handling

## Continuous Integration

The project uses GitHub Actions for automated testing:
- Tests run on Ubuntu, macOS, and Windows
- Python versions: 3.11, 3.12, 3.13
- Includes linting, type checking, and test coverage

See `.github/workflows/test.yml` for details.

## Writing Tests

Example test structure:

```python
import pytest
from unittest.mock import Mock

class TestMyFeature:
    """Test cases for my feature."""

    def test_basic_functionality(self, sample_fixture):
        """Test that basic functionality works."""
        # Arrange
        input_data = "test"

        # Act
        result = my_function(input_data)

        # Assert
        assert result == expected_output
```

For more details, see the test files in the `tests/` directory.
