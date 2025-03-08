# rwreader - Readwise Reader TUI

`rwreader` is a terminal-based application that provides a text user interface (TUI) for accessing and reading articles from your [Readwise Reader](https://readwise.io/reader) library. Built using [Textual](https://github.com/Textualize/textual), `rwreader` allows you to navigate and read your saved articles efficiently from the command line.

## Features

- **Browse Library**: View your Readwise Reader library and collections
- **Read Articles**: View article content in a formatted text view
- **Basic Actions**: Mark articles as read/unread, archive/unarchive
- **Keyboard Navigation**: Use intuitive keyboard shortcuts for fast browsing
- **Open in Browser**: Open the original article in your default web browser

## Installation

### Prerequisites

- Python 3.9+
- Readwise Reader account with API token
- (Optional) [1Password CLI](https://developer.1password.com/docs/cli) for secure credential management

### Install from source

```bash
# Clone the repository
git clone https://github.com/yourusername/rwreader.git
cd rwreader

# Install the package
pip install -e .
```

### Configuration

Create a configuration file at `~/.rwreader.toml` with the following content:

```toml
[general]
cache_size = 10000
default_theme = "dark"
auto_mark_read = true

[readwise]
token = "your_readwise_token"  # Or use 1Password CLI integration

[display]
font_size = "medium"
reading_width = 80
```

Replace `your_readwise_token` with your Readwise API token, which you can obtain from your Readwise Reader settings.

### Running the application

```bash
rwreader
```

## Keyboard Shortcuts

```
## Navigation
- j / k: Navigate up and down in the current pane
- Arrow keys: Navigate in the current pane
- tab / shift+tab: Navigate between panes

## Article Actions
- r: Toggle read/unread status
- a: Toggle archive status
- o: Open article in browser

## App Controls
- h / ?: Show/hide help
- d: Toggle dark mode
- c: Clear content pane
- G / ,: Refresh data
- q: Quit
```

## Development

### Setting up the development environment

```bash
# Create a virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install development dependencies
pip install -e ".[dev]"
```

### Running tests

```bash
pytest
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgements

- [Readwise](https://readwise.io) for providing the Reader service and API
- [Textual](https://github.com/Textualize/textual) for the TUI framework
- [ttrsscli](https://github.com/reuteras/ttrsscli) for inspiration
