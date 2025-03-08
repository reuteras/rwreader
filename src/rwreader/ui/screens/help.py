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
- **a**: Toggle archive status
- **o**: Open article in browser

## App Controls
- **h / ?**: Show/hide this help
- **d**: Toggle dark mode
- **c**: Clear content pane
- **G / ,**: Refresh data
- **q**: Quit

## Collections and Library
- The left pane shows your library and collections
- Select "All Items" to view your unarchived articles
- Select "Archive" to view archived articles
- Select a collection to view its contents

## Tips
- Articles are automatically marked as read when opened (configurable)
- Links in articles can be clicked to open in browser
- Filter by collection to focus on specific content

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
