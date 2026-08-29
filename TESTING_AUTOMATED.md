# Automated Testing Guide

## Overview

RWReader has **198 automated tests** covering critical functionality. Tests use pytest and run automatically on every PR via GitHub Actions.

## Test Statistics

- **Total Tests**: 198 (182 unit + 16 integration, of which 2 integration tests are skipped)
- **Test Files**: 9
- **Lines of Test Code**: ~2,800
- **Current Coverage**: 17% overall (40% when running only the fast/non-integration suite; target: 50%+)

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

Two markers are registered in `pyproject.toml`:

- `unit`: Fast unit tests with mocked dependencies (registered for use, but not currently applied to any test — every test that isn't marked `integration` is treated as a unit test)
- `integration`: Slower Textual `Pilot`-driven end-to-end tests (all use a mocked API client, so none hit the real Readwise API)

### CI/CD

Tests run automatically on:

- Every push to `main`
- Every pull request

The CI workflow runs on Python 3.11, 3.12, and 3.13:

1. Runs linting (`ruff check`, `ruff format --check`)
2. Runs type checking (mypy) — currently `continue-on-error: true`, so type errors don't fail the build
3. Runs tests, excluding integration tests (`-m "not integration"`), with coverage reporting
4. Checks coverage threshold (currently 10%, enforced with `--cov-fail-under=10`)

See `.github/workflows/tests.yml` for configuration. Note that integration tests are **not** run in CI — only locally via `pytest -m integration`.

## Test Structure

```text
tests/
├── conftest.py                    # Shared fixtures
├── test_client.py                 # API client tests (24 tests)
├── test_config.py                 # Configuration tests (15 tests)
├── test_cache.py                  # Caching logic tests (12 tests)
├── test_markdown_converter.py     # Markdown processing tests (25 tests)
├── test_highlight_manager.py      # Highlight extraction/formatting tests (24 tests)
├── test_article_reader.py         # Article reader screen tests (9 tests)
├── test_ui_helpers.py             # UI utility tests (47 tests)
├── test_exceptions.py             # Error handling tests (26 tests)
└── test_app_integration.py        # End-to-end integration tests (16 tests, Textual Pilot)
```

## Coverage by Module

Figures below are from the full run (unit + integration). Running only the fast suite
(`pytest -m "not integration"`) currently yields ~40% overall, since several screens are
exercised almost entirely by the Pilot-driven integration tests.

### High Coverage (>60%)

- ✅ `ui/app.py`: 59%
- ✅ `exceptions.py`: 69%
- ✅ `ui/screens/help.py`: 64%

### Medium Coverage (20-60%)

- ⚠️ `cache.py`: 50%
- ⚠️ `ui/screens/fullscreen.py`: 52%
- ⚠️ `ui/screens/confirm.py`: 35%
- ⚠️ `ui/screens/save_improved.py`: 34%
- ⚠️ `ui/widgets/linkable_markdown_viewer.py`: 31%
- ⚠️ `main.py`: 25%

### Low Coverage (<20%)

- ❌ `client.py`: 12%
- ❌ `config.py`: 13%
- ❌ `markdown_converter.py`: 13%
- ❌ `highlight_manager.py`: 14%
- ❌ `ui/screens/link_screens.py`: 15%
- ❌ `ui/screens/article_reader.py`: 16%
- ❌ `ui/screens/article_list.py`: 17%
- ❌ `ui/screens/category_list.py`: 19%
- ❌ `ui_helpers.py`: 8%

### Zero Coverage (Needs Tests)

- ❌ UI widgets: `api_status.py`, `article_viewer.py`, `load_more.py`

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
    temp_config_dir,  # Temporary config directory
    sample_article_dict,  # Sample article data
    mock_readwise_document,  # Mock API document
    clean_environment,  # Clean env vars
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

All 198 tests currently pass (182 unit + 14 integration), with 2 integration tests skipped.

### Skipped Tests

- **Tests**: `test_move_article_to_archive`, `test_move_article_to_later` (both in `test_app_integration.py`)
- **Problem**: Textual's test `Pilot` times out when widgets are removed and recreated during `populate_list()`
- **Impact**: The underlying functionality works correctly in the real app; only the test harness is affected
- **Status**: Skipped with `@pytest.mark.skip` and an explanatory reason
- **Future**: Investigate an alternative way to assert on list repopulation that avoids the widget-lifecycle timeout

### Type Checking Not Enforced in CI

- **Problem**: `mypy src/rwreader --ignore-missing-imports` currently reports 37 errors across 13 files
- **Impact**: The CI type-checking step runs with `continue-on-error: true`, so these errors don't fail builds
- **Future**: Fix outstanding mypy errors and remove `continue-on-error` from the workflow

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
