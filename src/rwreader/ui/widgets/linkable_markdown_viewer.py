"""Custom markdown viewer with link handling and search functionality for rwreader."""

import logging
import re
import time
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
    """An extended MarkdownViewer that allows web links to be clicked or managed and supports text search."""

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

        # Search functionality
        self.current_search: str | None = None
        self.search_matches: list[
            tuple[int, int]
        ] = []  # List of (line, column) positions
        self.current_match_index: int = -1
        self.original_markdown: str = kwargs.get("markdown", "")
        self.is_highlighting: bool = (
            False  # Flag to track if we're in highlighting mode
        )

    def extract_links(self, markdown_text: str) -> list[tuple[str, str]]:
        """Extract markdown links from text.

        Args:
            markdown_text: Markdown text to extract links from

        Returns:
            List of tuples with link text and URL
        """
        links: list[tuple[str, str]] = []

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
            # Don't update if we're in the middle of highlighting
            if self.is_highlighting:
                logger.debug(
                    msg="Skipping update_content because highlighting is active"
                )
                return

            # Ensure markdown is never empty or None
            if not markdown:
                markdown = "# Content Not Available\n\nThe article content could not be loaded."

            # Store the original markdown
            self.original_markdown = markdown

            # Reset search state
            self.current_search = None
            self.search_matches = []
            self.current_match_index = -1

            # Update the document
            self.document.update(markdown=markdown)

            # Force refresh
            self.document._cache.clear()
            self.refresh(layout=True)

            # Re-extract links from the new content
            self.extracted_links = self.extract_links(markdown_text=markdown)

            # Log the update
            logger.debug(msg="Updated markdown content and reset search state")

        except Exception as e:
            logger.error(msg=f"Error updating markdown content: {e}")
            # Attempt to set a simple error message as fallback
            try:
                self.document.update(
                    markdown="**Error loading content**\n\nPlease try again or check logs."
                )
                self.refresh(layout=True)
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

    def search_text(self, query: str) -> None:
        """Search for text in the markdown content and highlight matches.

        Args:
            query: Text to search for
        """
        if not query or not self.original_markdown:
            return

        # Set highlighting flag to prevent concurrent updates
        self.is_highlighting = True

        try:
            # Reset search state
            self.current_search = query
            self.search_matches = []
            self.current_match_index = -1

            # First find all the matches
            logger.debug(msg=f"Searching for '{query}' in content")

            # Find all matches in the markdown text
            lines = self.original_markdown.split("\n")
            for line_num, line in enumerate(lines):
                # Search case-insensitively
                for match in re.finditer(re.escape(query), line, re.IGNORECASE):
                    self.search_matches.append((line_num, match.start()))

            # Check if we found any matches
            if not self.search_matches:
                # No matches found
                if hasattr(self.app, "notify"):
                    self.app.notify(
                        message=f"No matches found for '{query}'",
                        title="Search Results",
                        severity="warning",
                        timeout=5,
                    )
                # Clear any previous highlighting
                self.document.update(markdown=self.original_markdown)
                return

            # Log matches found
            logger.debug(msg=f"Found {len(self.search_matches)} matches for '{query}'")

            # Go to the first match
            self.current_match_index = 0
            self._scroll_to_current_match()  # This will handle the highlighting

        except Exception as e:
            logger.error(msg=f"Error in search_text: {e}")
            # Show error notification
            if hasattr(self.app, "notify"):
                try:
                    self.app.notify(
                        message=f"Search error: {e}",
                        title="Error",
                        severity="error",
                        timeout=5,
                    )
                except Exception:
                    pass
            # Restore original content
            try:
                self.document.update(markdown=self.original_markdown)
            except Exception:
                pass
        finally:
            # Always reset highlighting flag when done
            self.is_highlighting = False

    def _highlight_matches(self, query: str) -> None:
        """This method is no longer used directly - scrolling function now handles all highlighting."""
        # Instead of duplicating highlighting logic,
        # we'll just call the scroll method which does a better job of highlighting
        try:
            # Navigate to the first match
            if self.search_matches:
                self.current_match_index = 0
                self._scroll_to_current_match()
            # If no matches, just notify
            elif hasattr(self.app, "notify"):
                self.app.notify(
                    message=f"No matches found for '{query}'",
                    title="Search Results",
                    severity="warning",
                    timeout=5,
                )
        except Exception as e:
            logger.error(msg=f"Error in _highlight_matches redirect: {e}")
            # No need to do anything else, as this is just a redirect

    def goto_next_match(self) -> None:
        """Navigate to the next search match."""
        if not self.search_matches:
            return

        # Move to the next match (wrapping around if needed)
        self.current_match_index = (self.current_match_index + 1) % len(
            self.search_matches
        )
        self._scroll_to_current_match()

    def goto_previous_match(self) -> None:
        """Navigate to the previous search match."""
        if not self.search_matches:
            return

        # Move to the previous match (wrapping around if needed)
        self.current_match_index = (self.current_match_index - 1) % len(
            self.search_matches
        )
        self._scroll_to_current_match()

    def _scroll_to_current_match(self) -> None:
        """Scroll to the current match and highlight it with special markers."""
        if not self.search_matches or self.current_match_index < 0:
            return

        try:
            # Set highlighting flag to prevent other updates
            self.is_highlighting = True

            # Get the line and column of the current match
            line, column = self.search_matches[self.current_match_index]

            # Calculate line position (directly in pixels)
            # Use a larger value to ensure we get the right position
            # Default line height might be too small
            estimated_line_height = 24  # Larger fixed value for more reliable scrolling
            y_position = line * estimated_line_height

            logger.debug(f"Scrolling to match at line {line}, position {y_position}px")

            # Highlight all matches including the current match (differently)
            if self.current_search:
                # First create a copy of the original content
                updated_content = self.original_markdown

                # Use MUCH more visible markers - plain text for maximum compatibility
                # Regular match marker - standard brackets with text description
                regular_marker_start = "["
                regular_marker_end = "]"

                # Current match marker - very obvious asterisks and text
                current_marker_start = "*****["
                current_marker_end = "]*****"

                # Step 1: Find all matches and prepare replacements
                matches_positions = []
                for m in re.finditer(
                    re.escape(self.current_search), updated_content, re.IGNORECASE
                ):
                    matches_positions.append((m.start(), m.end()))

                # Step 2: Replace all matches, with special handling for current match
                # Important: Replace from end to beginning to avoid position shifts
                result = updated_content
                matches_positions.sort(reverse=True)  # Process from end to start

                for i, (start, end) in enumerate(matches_positions):
                    match_text = updated_content[start:end]
                    # Check if this is our current match
                    if (
                        i == len(matches_positions) - 1 - self.current_match_index
                    ):  # Reversed index
                        # Current match - special marker with asterisks
                        replacement = (
                            f"{current_marker_start}{match_text}{current_marker_end}"
                        )
                    else:
                        # Regular match - just simple brackets
                        replacement = (
                            f"{regular_marker_start}{match_text}{regular_marker_end}"
                        )

                    # Apply replacement
                    result = result[:start] + replacement + result[end:]

                # Apply and log
                logger.debug(
                    msg=f"Updating content to show match {self.current_match_index + 1} of {len(self.search_matches)}"
                )

                # Update the document
                self.document.update(markdown=result)

                # Force a refresh to make sure changes are visible
                self.document._cache.clear()
                self.refresh(layout=True)

                # Wait a brief moment for rendering
                time.sleep(0.1)  # Use synchronous sleep instead of asyncio

            # Scroll to the position - more aggressively
            try:
                # First try scrolling with a large offset to ensure visibility
                self.scroll_y = max(0, y_position - 100)  # Direct scrolling

                # Force an immediate visual refresh
                self.refresh(layout=True)

                # Also try the standard method as backup
                self.scroll_to(y=max(0, y_position - 100), animate=False)

                logger.debug(f"Scrolled to y-position: {y_position}")
            except Exception as scroll_error:
                logger.error(msg=f"Error scrolling: {scroll_error}")

            # Notify user about the current position - with longer timeout
            if hasattr(self.app, "notify"):
                try:
                    self.app.notify(
                        message=f"Match {self.current_match_index + 1} of {len(self.search_matches)}",
                        title="Search",
                        timeout=10,  # Even longer timeout
                    )
                except Exception as notify_error:
                    logger.error(msg=f"Error showing notification: {notify_error}")

                    # As a fallback, print to console
                    print(
                        f"SEARCH: Match {self.current_match_index + 1} of {len(self.search_matches)}"
                    )

        except Exception as e:
            logger.error(msg=f"Error in _scroll_to_current_match: {e}")
            # Try to restore highlighting
            try:
                if self.current_search:
                    self._highlight_matches(self.current_search)
            except Exception:
                # Last resort
                try:
                    self.document.update(markdown=self.original_markdown)
                except Exception:
                    pass
        finally:
            # Always reset highlighting flag
            self.is_highlighting = False

    def clear_search(self) -> None:
        """Clear the current search results and restore original content."""
        # Set flag to prevent interruptions
        self.is_highlighting = True

        try:
            # Check if we had a search active
            had_active_search = self.current_search is not None

            # Reset search state
            self.current_search = None
            self.search_matches = []
            self.current_match_index = -1

            # Restore original content if we have it
            if hasattr(self, "original_markdown") and self.original_markdown:
                # Log action
                logger.debug(msg="Clearing search and restoring original content")

                # Fully reset by updating the document with original content
                self.document.update(markdown=self.original_markdown)

                # Force a refresh to ensure the changes are visible
                self.document._cache.clear()
                self.refresh(layout=True)

                # Notify user only if we had an active search
                if had_active_search and hasattr(self.app, "notify"):
                    try:
                        self.app.notify(
                            message="Search cleared", title="Search", timeout=3
                        )
                    except Exception as notify_error:
                        logger.error(msg=f"Error showing notification: {notify_error}")

        except Exception as e:
            logger.error(msg=f"Error clearing search: {e}")
            # If simple reset fails, try more aggressive approaches
            try:
                # Try a two-step reset
                self.document.update(markdown="# Content loading...\n\nPlease wait...")
                self.refresh(layout=True)

                # Then restore original content
                self.document.update(markdown=self.original_markdown)
                self.refresh(layout=True)
            except Exception as nested_e:
                logger.error(msg=f"Failed to restore content: {nested_e}")
        finally:
            # Always reset highlighting flag
            self.is_highlighting = False
