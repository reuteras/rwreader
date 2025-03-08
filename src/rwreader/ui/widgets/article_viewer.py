"""Custom article viewer widget for rwreader."""

import logging
import webbrowser

from textual import on
from textual.widgets import Markdown, MarkdownViewer

logger: logging.Logger = logging.getLogger(name=__name__)

class ArticleViewer(MarkdownViewer):
    """A custom markdown viewer for displaying articles with enhanced functionality."""

    def __init__(self, markdown: str = "", **kwargs) -> None:
        """Initialize the article viewer.
        
        Args:
            markdown: Initial markdown content to display
            **kwargs: Additional arguments for the MarkdownViewer
        """
        super().__init__(
            markdown=markdown,
            show_table_of_contents=False,
            **kwargs
        )
        
    def update_content(self, markdown: str) -> None:
        """Update the article content.
        
        Args:
            markdown: New markdown content to display
        """
        self.document.update(markdown)

    @on(Markdown.LinkClicked)
    def handle_link_click(self, event: Markdown.LinkClicked) -> None:
        """Open links in the default web browser.
        
        Args:
            event: The link clicked event
        """
        if event.href:
            try:
                event.prevent_default()
                webbrowser.open(url=event.href)
                self.app.notify(message=f"Opening: {event.href}", title="Browser")
            except Exception as e:
                logger.error(f"Error opening link: {e}")
                self.app.notify(message=f"Error opening link: {e}", title="Error", severity="error")
