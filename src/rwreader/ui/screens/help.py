"""Help screen for rwreader."""

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import MarkdownViewer

HELP_TEXT = """# Readwise Reader TUI Help

## Navigation
- **j / k**: Navigate up and down in the current pane
- **Arrow keys**: Navigate in the current pane
- **tab / shift+tab**: Navigate between panes

## Article Actions
- **r**: Toggle read/unread status
- **a**: Move article to Archive
- **l**: Move article to Later
- **i**: Move article to Inbox
- **o**: Open article in browser
- **m**: Show detailed article metadata

## App Controls
- **h / ?**: Show/hide this help
- **d**: Toggle dark mode
- **c**: Clear content pane
- **G / ,**: Refresh data
- **q**: Quit

## Library Categories
- **Inbox**: Default location for new articles
- **Later**: Articles saved for reading later
- **Archive**: Articles you've finished with

## Tips
- Articles are automatically marked as read when opened (configurable)
- Links in articles can be clicked to open in browser
- Use the 'm' key to view all available metadata for an article
- When an article is displayed, you can move it to any category with a single keystroke

## Debug
- **Ctrl+R**: Reset cache and reload all data
- **Ctrl+D**: Dump debug information to log file

## About
Readwise Reader TUI is a terminal user interface for accessing your Readwise Reader library.
"""


class HelpScreen(Screen):
    """A screen that displays help information."""

    def compose(self) -> ComposeResult:
        """Compose the help screen content."""
        yield MarkdownViewer(markdown=HELP_TEXT, id="help-content")

    def on_key(self, event) -> None:
        """Handle key presses on the help screen."""
        # Close the help screen on any key press except navigation keys
        if event.key not in ["up", "down", "page_up", "page_down"]:
            event.prevent_default()
            self.app.pop_screen()
