"""Help screen for rwreader."""

from textual import events
from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import MarkdownViewer

HELP_TEXT = """# Readwise Reader TUI Help

## Navigation Model
Readwise Reader TUI uses a single-window, stack-based navigation:
1. **Category List** → Select a category (Inbox, Later, Shortlist, Feed, Archive)
2. **Article List** → Select an article to read
3. **Article Reader** → Read the article with J/K navigation

## Category List Screen
- **j / k**: Navigate categories
- **Enter**: Select category and view articles
- **,**: Refresh category counts
- **v**: Open the library dashboard (overview, inbox aging, sources, tags)
- **h / ?**: Show/hide this help
- **d**: Toggle dark mode
- **q**: Quit

## Dashboard Screen (v from the category list)
Reads from a local index of document metadata, kept up to date as you browse.
- **Left / Right**: Switch tabs (Overview, Inbox aging, Sources, Tags)
- **j / k**: Navigate rows
- **Enter**: Drill into a filtered, read-only article list for the selected
  row (a location, an age bucket, a source or a tag)
- **,**: Recompute the tables from the local index (no API calls)
- **s**: Full sync — fetch every document from the API once, so locations
  you have not browsed yet (e.g. an unvisited Archive) are included
- **Escape / Backspace**: Back to category list

## Article List Screen
- **j / k**: Navigate articles
- **Enter**: Read selected article
- **a**: Move article to Archive
- **l**: Move article to Later
- **i**: Move article to Inbox
- **s**: Move article to Shortlist
- **D**: Delete article (with confirmation)
- **o**: Open article in Readwise Reader browser
- **O**: Open original source URL in browser
- **,**: Refresh article list
- **space**: Load more articles
- **Escape / Backspace**: Back to category list
- **h / ?**: Show/hide this help
- **d**: Toggle dark mode
- **q**: Quit

## Article Reader Screen
- **J / K**: Navigate to next/previous article (uppercase!)
- **j / k**: Scroll article content down / up
- **g / G**: Jump to top / bottom of article
- **Ctrl+K / Ctrl+J**: Move highlight cursor to previous / next paragraph
- **h**: Highlight paragraph at cursor (remove via Readwise web UI)
- **a**: Move article to Archive
- **l**: Move article to Later
- **i**: Move article to Inbox
- **s**: Move article to Shortlist
- **D**: Delete article (with confirmation)
- **o**: Open article in Readwise Reader browser
- **O**: Open original source URL in browser
- **Ctrl+L**: Show links in article
- **Ctrl+E**: Extract menu (links, attachments, code blocks, indicators, references)
- **Escape / Backspace**: Back to article list
- **?**: Show/hide this help
- **d**: Toggle dark mode
- **q**: Quit

## Extracting (Ctrl+E in the reader)
- **Links**: open one in the browser, or save one (or all with **S**) to Readwise
- **Attachments**: download linked PDFs, media, images and archives to the
  configured download folder
- **Code blocks**: copy a fenced block to the clipboard or save it to a file
- **Indicators of compromise**: IPs, domains, URLs, emails, hashes and CVEs found
  in the text, with defanged forms restored; copy or export as CSV/JSON
- **References**: DOIs, arXiv IDs, GitHub repositories and RFCs

## Highlighting (requires readwise CLI in PATH)
The current paragraph is shown with a `>` marker on the left.  Use **Ctrl+K / Ctrl+J** to
move the cursor between paragraphs, then press **h** to create a Readwise highlight.
Existing highlights appear in a **Highlights** section at the bottom of the article
and are marked inline with ⟦…⟧.  To remove a highlight, use the Readwise web UI.

## Library Categories
- **📥 Inbox**: Default location for new articles
- **⏰ Later**: Articles saved for reading later
- **⭐ Shortlist**: Articles you want to get to first
- **📰 Feed**: Your RSS feed (unread only)
- **📦 Archive**: Articles you've finished with

## Tips
- Use **J / K** (uppercase) in the reader to navigate between articles without going back
- Use **Escape** or **Backspace** to go back at any level
- Articles are automatically marked as read when opened
- The app uses progressive loading - use **space** to load more articles
- Use **,** (comma) to refresh data from the API

## About
Readwise Reader TUI is a terminal user interface for accessing your Readwise Reader library.
Version 2.0 - Single-window navigation model.
"""


class HelpScreen(Screen):
    """A screen that displays help information."""

    def compose(self) -> ComposeResult:
        """Compose the help screen content."""
        yield MarkdownViewer(markdown=HELP_TEXT, id="help-content")

    def on_key(self, event: events.Key) -> None:
        """Handle key presses on the help screen."""
        # Close the help screen on any key press except navigation keys
        if event.key not in ["up", "down", "page_up", "page_down"]:
            event.prevent_default()
            self.app.pop_screen()
