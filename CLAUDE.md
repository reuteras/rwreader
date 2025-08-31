# CLAUDE.md - Project Information for rwreader

## Project Overview
**rwreader** is a terminal-based user interface (TUI) application for accessing and managing your Readwise Reader library. Built using the Textual framework, it provides a clean, keyboard-driven interface for browsing, reading, and organizing articles from the command line.

## Architecture & Technology Stack

- **Language**: Python 3.11+
- **Main Framework**: Textual (for TUI)
- **Build System**: uv for dependency management and build
- **Configuration**: TOML-based configuration files
- **API Integration**: Custom Readwise API client
- **Package Management**: uv with lock file

## Project Structure

```
src/rwreader/
├── main.py                 # Main entry point and CLI setup
├── config.py              # Configuration handling with 1Password CLI support
├── client.py              # Readwise API client
├── cache.py               # Caching functionality
├── ui/
│   ├── app.py             # Main TUI application class (1277 lines - core functionality)
│   ├── screens/           # Modal screens (help, confirmation, etc.)
│   └── widgets/           # Custom UI widgets
└── utils/
    ├── markdown_converter.py  # Article content formatting
    └── ui_helpers.py          # UI utility functions
```

## Key Features

- **Three-pane layout**: Navigation, article list, content viewer
- **Progressive loading**: Initial 20 items with load-more functionality
- **Article management**: Move between Inbox, Later, Feed, Archive
- **Link extraction**: Extract and interact with article links
- **Browser integration**: Open articles/links in default browser
- **1Password CLI support**: Secure token management
- **Keyboard-driven navigation**: Vim-like shortcuts
- **Dark/light theme support**

## Configuration

- **Config file**: `~/.rwreader.toml`
- **Main sections**: `[general]`, `[readwise]`, `[display]`
- **1Password integration**: Token can use `op read` commands
- **Logging**: Located in `~/.rwreader/logs/rwreader.log`

## Entry Points & Commands

- **Main command**: `rwreader` (defined in pyproject.toml scripts)
- **Config creation**: `rwreader --create-config PATH`
- **Version**: `rwreader --version`
- **Debug logging**: `rwreader --debug` or `rwreader --info`

## Development Commands

Based on pyproject.toml analysis:

### Code Quality & Formatting

```bash
# Linting and formatting (using ruff)
uv ruff check .                    # Lint code
uv ruff format .                   # Format code
uv ruff check --fix .              # Auto-fix linting issues

# Type checking (mypy is configured)
mypy src/rwreader/

# Run with development dependencies
uv pip install -e ".[dev]"     # Install in development mode
```

### Testing

No testing implemented.

### Running & Development

```bash
# Install and run
uv pip install -e .            # Install in editable mode
rwreader                       # Run the application

# Development server (Textual has dev tools)
textual run --dev src/rwreader/main.py    # Run with Textual dev tools
```

## Key Dependencies

- **textual>=0.27.0**: TUI framework
- **httpx>=0.24.0**: HTTP client
- **toml>=0.10.2**: Configuration parsing
- **rich>=13.3.5**: Rich text and formatting
- **python-dotenv>=1.0.1**: Environment variables
- **markdownify>=1.1.0**: HTML to Markdown conversion
- **readwise-api**: Custom Readwise API (from git source)

## Development Dependencies

- **ruff>=0.9.10**: Linting and formatting
- **textual-dev>=1.7.0**: Textual development tools

## Important Notes for Development

### Code Style

- **Ruff configuration**: Extensive linting rules including Pylint, pyflakes, isort, pydocstyle
- **Line length**: 88 characters (Black-compatible)
- **Target Python**: 3.11+
- **Docstring style**: Google format
- **Type hints**: Required (`disallow_untyped_defs = true`)

### Key Files to Understand

1. **src/rwreader/ui/app.py**: Core application logic (1277 lines) - main TUI class with all keyboard bindings and UI logic
2. **src/rwreader/client.py**: API client for Readwise integration
3. **src/rwreader/config.py**: Configuration management with 1Password CLI support
4. **src/rwreader/main.py**: Entry point with error handling and logging setup

### Architecture Patterns

- **Progressive loading**: Articles load in batches with "load more" functionality
- **Three-pane layout**: Navigation → Articles → Content
- **Event-driven UI**: Textual event handling for keyboard shortcuts
- **Caching**: Client-side caching for API responses
- **Error handling**: Comprehensive error handling with user notifications

### Keyboard Shortcuts (from app.py bindings)

- Navigation: j/k, tab/shift+tab, F/I/L/A (categories) and J/K up/down for categories
- Article actions: a/l/i (move), o (open), m/M (metadata/maximize)
- Link actions: ctrl+o/s/l (open/save/readwise links)  
- App controls: ?/h (help), d (dark mode), G/, (refresh), q (quit)

### Security Considerations

- Token handling via 1Password CLI (`op read` commands)
- No hardcoded credentials
- Logging configured to avoid sensitive data

### Typical Development Workflow

1. **Setup**: `uv pip install -e ".[dev]"`
2. **Code**: Edit in src/rwreader/
3. **Format**: `ruff format .`
4. **Lint**: `ruff check --fix .`
5. **Test**: Run application with `rwreader --debug`
6. **Type check**: `mypy src/rwreader/`

This is a well-structured Python TUI application with modern development practices, comprehensive error handling, and a clean architecture suitable for CLI-based article management.
