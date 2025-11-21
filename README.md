# rwreader - Readwise Reader TUI

A modern, keyboard-driven terminal user interface (TUI) for [Readwise Reader](https://readwise.io/reader). Built with [Textual](https://github.com/Textualize/textual), `rwreader` lets you efficiently browse, read, and manage your saved articles from the command line.

## Features

- **Browse Library**: Navigate your entire Readwise Reader library with smooth keyboard controls
- **Multiple Views**: Organize articles by Inbox, Later, Feed, and Archive categories
- **Read Articles**: Display formatted article content with syntax highlighting
- **Vim-style Navigation**: Use j/k for navigation, with arrow keys as fallback
- **Link Management**: Extract, save, and share article links to Readwise
- **1Password Integration**: Securely store and retrieve your Readwise API token via 1Password CLI
- **Dark/Light Themes**: Toggle between dark and light mode on the fly
- **Progressive Loading**: Efficient loading with "Load More" functionality
- **Offline Caching**: Smart caching reduces unnecessary API calls

## Installation

### Prerequisites

- Python 3.11+ (< 3.14 due to dependency compatibility)
- Readwise Reader account with API token
- (Optional) [1Password CLI](https://developer.1password.com/docs/cli) for secure credential management

### Install from PyPI

```bash
pip install rwreader
```

### Install from source

```bash
git clone https://github.com/reuteras/rwreader.git
cd rwreader
pip install -e .
```

## Quick Start

### 1. Create configuration file

Create `~/.rwreader.toml`:

```toml
[readwise]
token = "your_readwise_token"

[display]
default_theme = "dark"
```

### 2. Run the application

```bash
rwreader
```

## Configuration

### Full configuration example

```toml
[general]
# Size of the local cache in bytes (default: 10000)
cache_size = 10000

[readwise]
# Your Readwise Reader API token
# Can use "op read op://vault/item/field" for 1Password integration
token = "your_token_here"

[display]
# Theme: "dark" or "light" (default: "dark")
default_theme = "dark"

# Font size: "small", "medium", "large" (default: "medium")
font_size = "medium"

# Content width in characters (default: 80)
reading_width = 80
```

### 1Password CLI Integration

Store your Readwise token securely in 1Password:

```toml
[readwise]
# 1Password CLI will be called with this command
token = "op read op://Personal/Readwise/credential"
```

Ensure 1Password CLI is installed and authenticated:
```bash
op signin my.1password.com user@example.com
```

### Environment Variables

You can also set the token via environment variable:
```bash
export READWISE_TOKEN="your_token_here"
rwreader
```

## Keyboard Shortcuts

### Navigation

| Key | Action |
|-----|--------|
| `j` / `↓` | Move down in current pane |
| `k` / `↑` | Move up in current pane |
| `J` | Next category |
| `K` | Previous category |
| `Tab` | Focus next pane (Navigation → Articles → Content) |
| `Shift+Tab` | Focus previous pane |

### Jump to Category

| Key | Category |
|-----|----------|
| `I` | Go to Inbox |
| `F` | Go to Feed |
| `L` | Go to Later |
| `A` | Go to Archive |

### Article Actions

| Key | Action |
|-----|--------|
| `a` | Move to Archive |
| `l` | Move to Later |
| `i` | Move to Inbox |
| `o` | Open in browser |
| `m` | Show metadata |
| `M` | Maximize content pane |
| `D` | Delete article |

### Link Management

| Key | Action |
|-----|--------|
| `Ctrl+O` | Open article links (choose which to open) |
| `Ctrl+S` | Save link (download) |
| `Ctrl+L` | Add link to Readwise |
| `Ctrl+Shift+L` | Add link to Readwise and open |

### App Controls

| Key | Action |
|-----|--------|
| `h` / `?` | Show/hide help |
| `d` | Toggle dark/light mode |
| `c` | Clear content pane |
| `G` / `,` | Refresh all data |
| `Space` | Load more articles |
| `q` | Quit |

## Development

### Setup

```bash
# Clone and navigate to directory
git clone https://github.com/reuteras/rwreader.git
cd rwreader

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install with dev dependencies
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest
```

### Code Quality

```bash
# Format code
uv run ruff format .

# Lint and auto-fix
uv run ruff check --fix .

# Type checking
mypy src/rwreader/
```

### Running in Development

```bash
# Standard mode
rwreader

# Debug mode with verbose logging
rwreader --debug

# With specific log level
rwreader --info
```

## Architecture

The application follows a three-pane layout:

1. **Navigation Pane** (left): Categories with article counts
2. **Articles Pane** (middle): List of articles in selected category
3. **Content Pane** (right): Full article content with formatting

### Key Components

- **TUI Framework**: Textual for terminal UI
- **API Client**: Custom Readwise API client with caching
- **Markdown Rendering**: Rich text formatting for article content
- **Configuration**: TOML-based config with 1Password support

## Troubleshooting

### "Invalid or expired token"

- Verify your Readwise token is correct
- Check 1Password CLI is authenticated: `op signin`
- Ensure token has Reader API access in Readwise settings

### "No articles loading"

- Check your internet connection
- Try `G` to manually refresh
- Check logs: `rwreader --debug 2>&1 | tail -f ~/.rwreader/logs/rwreader.log`

### Configuration file not found

- Create `~/.rwreader.toml` with required fields
- Use `rwreader --create-config PATH` to generate a template

### Python 3.14 compatibility

- Some dependencies don't yet support Python 3.14
- Use Python 3.11, 3.12, or 3.13

## License

MIT License - see [LICENSE](LICENSE) file for details

## Contributing

Contributions are welcome! Please feel free to submit pull requests.

## Acknowledgements

- [Readwise](https://readwise.io) - For Reader service and API
- [Textual](https://github.com/Textualize/textual) - For the excellent TUI framework
- [1Password CLI](https://developer.1password.com/docs/cli) - For secure credential management

## Support

For issues and feature requests, please use [GitHub Issues](https://github.com/reuteras/rwreader/issues).
