# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.1] - 2024-01-XX

### Added
- J/k vim-style navigation in content pane for scrolling article text
- Explicit key bindings to LinkableMarkdownViewer widget for better keyboard support
- Enhanced pyproject.toml with comprehensive classifiers for PyPI
- Improved documentation and configuration examples
- Python version specification (>=3.11,<3.14) to handle dependency constraints

### Fixed
- J/k navigation not working in content pane (now supports scroll-based widgets)
- Linting issues in test suite (magic values, import ordering)
- Missing docstrings in test modules
- Outdated keyboard shortcuts in documentation
- Python version requirement clarification (was 3.9+, now 3.11+)
- Import statement ordering in test configuration

### Changed
- Improved action handlers to support both list-based and scroll-based widgets
- Updated README with accurate and comprehensive keyboard shortcut documentation
- Enhanced keyboard shortcut tables with proper formatting
- Added troubleshooting section to documentation
- Improved 1Password CLI integration documentation

## [0.1.0] - 2024-01-XX

### Added
- Initial release of rwreader
- Three-pane TUI layout (Navigation, Articles, Content)
- Terminal user interface using Textual framework
- Integration with Readwise Reader API
- Article browsing across multiple categories (Inbox, Later, Feed, Archive)
- Article navigation and content viewing with markdown formatting
- Keyboard-driven interface with vim-style keybindings
- Dark/light theme support
- 1Password CLI integration for secure token storage
- Caching system to reduce API calls
- Progressive loading with "Load More" functionality
- Article metadata display
- Link extraction and management
  - Open links in browser
  - Save links for later
  - Add links to Readwise
- Configuration via TOML file
- Help system with keyboard shortcut reference
- Article deletion with confirmation
- Refresh functionality for updating library data
- Comprehensive error handling and logging
- Type hints throughout codebase
- Test infrastructure with pytest
- CI/CD with GitHub Actions
- Code quality checks with ruff linting

### Features

#### Navigation
- Move between articles with j/k or arrow keys
- Navigate between categories with J/K
- Jump directly to categories with I/F/L/A shortcuts
- Tab-based pane navigation
- Automatic focus management

#### Article Management
- Move articles between categories
- Delete articles with confirmation
- View article metadata (title, author, source, word count, etc.)
- Display reading progress
- Mark articles as read/unread (via status tracking)

#### Content Viewing
- Syntax-highlighted markdown rendering
- Article content with proper formatting
- Maximizable content pane for full-screen reading
- Word wrapping and configurable reading width
- Link highlighting and interaction

#### Configuration
- TOML-based configuration file
- Support for 1Password CLI credential management
- Customizable theme, font size, and reading width
- Cache size configuration
- Environment variable support for token

#### User Experience
- Responsive keyboard controls
- Dark and light theme toggle
- Smooth scrolling and navigation
- Loading indicators for long operations
- Background count updates for Feed and Later
- Smart caching to minimize network requests
- Error messages with helpful context

---

## Upcoming

### Planned Features
- Search functionality
- Tagging and filtering
- Batch operations (move multiple articles)
- Sync status indicators
- Custom color schemes
- Plugin system for extending functionality
