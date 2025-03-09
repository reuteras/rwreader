"""Custom markdown viewer with link handling for rwreader."""

import logging
import re
import webbrowser

from textual import on
from textual.widgets import Markdown, MarkdownViewer

logger: logging.Logger = logging.getLogger(name=__name__)

# Keys allowed in fullscreen mode for navigation
ALLOW_IN_FULL_SCREEN: list[str] = [
    "arrow_up",
    "arrow_down",
    "page_up",
    "page_down",
    "down",
    "up",
    "right",
    "left",
    "enter",
]


class LinkableMarkdownViewer(MarkdownViewer):
    """An extended MarkdownViewer that allows web links to be clicked or managed."""

    def __init__(self, **kwargs) -> None:
        """Initialize the LinkableMarkdownViewer.

        Args:
            **kwargs: Additional arguments for MarkdownViewer
        """
        # Handle the open_links parameter - default to False
        self.open_links = kwargs.pop("open_links", False)

        # Initialize parent class
        super().__init__(**kwargs)

        # Track extracted links
        self.extracted_links: list[tuple[str, str]] = []

        # Extract links when markdown is set
        if kwargs.get("markdown"):
            self.extracted_links = self.extract_links(markdown_text=kwargs["markdown"])

    def extract_links(self, markdown_text: str) -> list[tuple[str, str]]:
        """Extract markdown links from text.

        Args:
            markdown_text: Markdown text to extract links from

        Returns:
            List of tuples with link text and URL
        """
        links = []

        # Match markdown links of the form [text](url)
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"
        for match in re.finditer(pattern=link_pattern, string=markdown_text):
            link_text = match.group(1).strip()
            link_url = match.group(2).strip()
            links.append((link_text, link_url))

        # Match HTML links of the form <a href="url">text</a>
        html_link_pattern = r'<a\s+href="([^"]+)"[^>]*>([^<]+)</a>'
        for match in re.finditer(pattern=html_link_pattern, string=markdown_text):
            link_url: str = match.group(1).strip()
            link_text: str = match.group(2).strip()
            links.append((link_text, link_url))

        return links

    def update_content(self, markdown: str) -> None:
        """Update the markdown content.

        Args:
            markdown: New markdown content to display
        """
        try:
            # Ensure markdown is never empty or None
            if not markdown:
                markdown = "# Content Not Available\n\nThe article content could not be loaded."

            # Update the document
            self.document.update(markdown=markdown)

            # Re-extract links from the new content
            self.extracted_links = self.extract_links(markdown_text=markdown)
        except Exception as e:
            logger.error(msg=f"Error updating markdown content: {e}")
            # Attempt to set a simple error message as fallback
            try:
                self.document.update(
                    markdown="**Error loading content**\n\nPlease try again or check logs."
                )
            except Exception as nested_e:
                logger.error(
                    msg=f"Failed to set error message in markdown viewer: {nested_e}"
                )

    @on(message_type=Markdown.LinkClicked)
    def handle_link(self, event: Markdown.LinkClicked) -> None:
        """Open links in the default web browser or handle them as configured.

        Args:
            event: Link clicked event
        """
        if event.href:
            event.prevent_default()

            if self.open_links:
                # Open directly in browser
                webbrowser.open(url=event.href)
                # Notify the user
                if hasattr(self.app, "notify"):
                    self.app.notify(message=f"Opening: {event.href}", title="Browser")
            elif hasattr(self.app, "handle_link_click"):
                self.app.handle_link_click(link=event.href)  # type: ignore
            elif hasattr(self.app, "action_open_article_url"):
                self.app.action_open_article_url()  # type: ignore
