# Automated Testing Guide

## Overview

RWReader has **166 automated tests** covering critical functionality. Tests use pytest and run automatically on every PR via GitHub Actions.

## Test Statistics

- **Total Tests**: 166
- **Test Files**: 8
- **Lines of Test Code**: ~2,400
- **Current Coverage**: 13% (target: 50%+)

## Running Tests

### Quick Start

```bash
# Run all tests (excluding slow integration tests)
uv run pytest

# Run with coverage report
uv run pytest --cov=rwreader --cov-report=html

# Run only unit tests (fast)
uv run pytest -m "not integration"

# Run only integration tests (slow, hits API)
uv run pytest -m integration

# Run specific test file
uv run pytest tests/test_client.py

# Run with verbose output
uv run pytest -v

# Stop on first failure
uv run pytest -x
```

### Test Markers

Tests are marked with categories:

- `@pytest.mark.unit`: Fast unit tests with mocked dependencies
- `@pytest.mark.integration`: Slow tests that may hit real APIs

### CI/CD

Tests run automatically on:
- Every push to `main`
- Every pull request

The CI workflow:
1. Runs linting (ruff)
2. Runs type checking (mypy)
3. Runs unit tests (excluding integration)
4. Generates coverage report
5. Checks coverage threshold (currently 10%)

See `.github/workflows/tests.yml` for configuration.

## Test Structure

```text
tests/
├── conftest.py                    # Shared fixtures
├── test_client.py                 # API client tests
├── test_config.py                 # Configuration tests
├── test_cache.py                  # Caching logic tests
├── test_markdown_converter.py     # Markdown processing tests
├── test_ui_helpers.py             # UI utility tests
├── test_exceptions.py             # Error handling tests
└── test_app_integration.py        # End-to-end integration tests
```

## Coverage by Module

### High Coverage (>75%)
- ✅ `config.py`: 77%
- ✅ `exceptions.py`: 88%
- ✅ `cache.py`: 94%

### Medium Coverage (10-50%)
- ⚠️ `markdown_converter.py`: 10%
- ⚠️ `ui_helpers.py`: 7%
- ⚠️ Various screens: 0-52%

### Zero Coverage (Needs Tests)
- ❌ UI screens: `article_list.py`, `article_reader.py`, `category_list.py`
- ❌ UI widgets: `api_status.py`, `article_viewer.py`, `linkable_markdown_viewer.py`

## Writing Tests

### Unit Test Example

```python
import pytest
from unittest.mock import Mock, patch
from rwreader.client import ReadwiseClient

@pytest.mark.unit
def test_get_inbox_from_cache(mock_api):
    """Test getting inbox articles from cache."""
    with patch.dict("os.environ", {}, clear=True):
        client = ReadwiseClient(token="test_token")

        # Pre-populate cache
        client._category_cache["inbox"]["data"] = [
            {"id": "1", "title": "Article 1"},
            {"id": "2", "title": "Article 2"},
        ]
        client._category_cache["inbox"]["last_updated"] = time.time()

        articles = client.get_inbox()

        assert len(articles) == 2
        assert articles[0]["title"] == "Article 1"
```

### Integration Test Example

```python
import pytest
from textual.pilot import Pilot

@pytest.mark.asyncio
@pytest.mark.integration
async def test_app_startup(app_with_mock_client):
    """Test that app starts successfully."""
    app = app_with_mock_client
    async with app.run_test() as pilot:
        assert app.is_running
        await pilot.pause()
```

### Using Fixtures

Common fixtures from `conftest.py`:

```python
def test_with_fixtures(
    temp_config_dir,           # Temporary config directory
    sample_article_dict,        # Sample article data
    mock_readwise_document,     # Mock API document
    clean_environment          # Clean env vars
):
    # Your test code
    pass
```

## Test Best Practices

1. **Mock External Dependencies**: Don't hit real APIs in unit tests
2. **Use Fixtures**: Reuse common test data and setup
3. **Test One Thing**: Each test should verify one behavior
4. **Clear Names**: Test names should describe what they test
5. **Fast Tests**: Unit tests should run in milliseconds
6. **Mark Integration Tests**: Use `@pytest.mark.integration` for slow tests

## Regression Tests

Tests for previously fixed bugs:

### Planned (Need to Add)
- [ ] Test for duplicate widget ID prevention (Issues #24, #30)
- [ ] Test for category refresh (Issues #26, #28)
- [ ] Test for delete action worker context (Issue #32)
- [ ] Test for article list on_resume (Issue #34)

### Template for Regression Test

```python
@pytest.mark.unit
def test_regression_issue_24_duplicate_widget_ids():
    """Regression test for Issue #24: Duplicate widget IDs on refresh.

    Previously, refreshing categories would cause duplicate ID errors.
    This test ensures widget IDs are properly released.
    """
    # Test code here
    pass
```

## Debugging Tests

### Run with Debug Output

```bash
# Show print statements
uv run pytest -s

# Show full error traces
uv run pytest --tb=long

# Show local variables in traces
uv run pytest --showlocals

# Run with pdb on failure
uv run pytest --pdb
```

### Check Coverage Details

```bash
# Generate HTML coverage report
uv run pytest --cov=rwreader --cov-report=html

# Open in browser
open htmlcov/index.html
```

### Running Specific Tests

```bash
# Run single test function
uv run pytest tests/test_client.py::TestReadwiseClient::test_get_inbox_from_cache

# Run all tests in a class
uv run pytest tests/test_client.py::TestReadwiseClient

# Run tests matching pattern
uv run pytest -k "cache"
```

## Recent Fixes

### Test Isolation (Fixed in PR #37)
- **Problem**: Tests were prompting for 1Password login and hitting real Readwise API
- **Root Cause**: `app_with_mock_client` fixture was creating `RWReader()` which loaded real `Configuration`
- **Solution**: Mock `Configuration` class before creating app in test fixture
- **Status**: ✅ Fixed - All tests now run without 1Password prompts or real API calls

## Known Issues

### Integration Tests Architectural Mismatch
- **Problem**: 12 integration tests fail due to architectural changes
- **Examples**:
  - Tests expect widgets like `#articles` and `#navigation` that don't exist in default screen
  - Tests expect `app.current_category` attribute removed in refactoring
- **Impact**: Tests marked with `@pytest.mark.integration` currently fail
- **Status**: Tests are properly isolated (no real API calls), but need updates to match current architecture
- **Future**: Refactor integration tests to match current three-screen architecture (CategoryList, ArticleList, ArticleReader)

### Outdated Tests (Skipped)
- **Problem**: Some tests expect deprecated attributes
- **Example**: `test_navigate_between_categories` expects `app.current_category`
- **Status**: Skipped with `@pytest.mark.skip` and TODO to refactor
- **Future**: Update tests to check screen state instead of app attributes

## Contributing

When adding new features:

1. **Write tests first** (TDD approach)
2. **Ensure tests pass**: `uv run pytest`
3. **Check coverage**: `uv run pytest --cov`
4. **Add regression tests** for bugs
5. **Mark integration tests** appropriately

## CI/CD Status

View test results:
- GitHub Actions: Check PR "Checks" tab
- Coverage Reports: See PR comments (if Codecov configured)

## Future Improvements

1. **Increase Coverage**: Target 50%+ overall
2. **Add UI Tests**: Test Textual screens and widgets
3. **Performance Tests**: Measure response times
4. **Mutation Testing**: Verify test quality
5. **Property-Based Testing**: Use Hypothesis for edge cases

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [Textual testing guide](https://textual.textualize.io/guide/testing/)

## Questions?

See `TESTING.md` for manual testing scenarios and debug procedures.
