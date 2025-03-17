"""Link selection screen."""

import logging
import os
from typing import Any
from urllib.parse import ParseResult, urlparse

import httpx
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView

logger = logging.getLogger(name=__name__)


class LinkSelectionScreen(ModalScreen):
    """Modal screen to show extracted links and allow selection."""

    BINDINGS = [  # noqa: RUF012
        ("escape", "cancel", "Cancel"),
        ("enter", "select", "Select"),
    ]

    def __init__(self, configuration, links, open_links="browser", open=False) -> None:
        """Initialize the link selection screen.

        Args:
            configuration: App configuration
            links: List of tuples with link title and URL
            open_links: Action to perform on selected link
            open: Whether to open the link after saving to Readwise
        """
        super().__init__()
        self.links: Any = links or []  # Ensure links is never None
        self.open_links: str = open_links
        self.open: bool = open
        self.configuration: Any = configuration
        self.selected_index = 0
        self.http_client = httpx.Client(follow_redirects=True)

    def compose(self) -> ComposeResult:
        """Define the content layout of the link selection screen."""
        if self.open_links == "browser":
            title = "Select a link to open (ESC to go back):"
        elif self.open_links == "download":
            title = "Select a link to download (ESC to go back):"
        elif self.open_links == "readwise":
            title = "Select a link to save to Readwise (ESC to go back):"
        else:
            title = "Select a link (ESC to go back):"

        yield Label(renderable=title)

        # Handle empty links list
        if not self.links:
            yield Label(renderable="No links found in article")
            return

        # Create a list view with all links
        link_select = ListView(
            *[
                ListItem(Label(renderable=self._format_link_item(link=link)))
                for link in self.links
            ],
            id="link-list",
        )

        # Calculate width based on longest link
        longest_link: int = (
            max(len(self._format_link_item(link)) for link in self.links)
            if self.links
            else 40
        )

        link_select.styles.align_horizontal = "left"
        link_select.styles.width = min(longest_link + 6, 120)
        link_select.styles.max_width = "100%"
        yield link_select

    def on_mount(self) -> None:
        """Set focus to the list view when screen is mounted."""
        link_list: ListView = self.query_one(
            selector="#link-list", expect_type=ListView
        )
        link_list.focus()

    def _format_link_item(self, link: tuple) -> str:
        """Format a link for display in the list.

        Args:
            link: Tuple of (title, url)

        Returns:
            Formatted link string
        """
        title, url = link

        # Ensure neither value is None
        title = title or "No title"
        url = url or "No URL"

        # Truncate long titles and URLs for better display
        max_line_length = 80

        if len(title) > max_line_length:
            title = title[: max_line_length - 3] + "..."

        if len(url) > max_line_length:
            # Try to keep the domain and part of the path
            try:
                parsed: ParseResult = urlparse(url=url)
                domain: str = parsed.netloc
                path: str = parsed.path

                if len(domain) + 10 >= max_line_length:  # If domain itself is very long
                    url: str = domain[: max_line_length - 3] + "..."
                else:
                    # Keep domain and truncate path
                    path_max: int = max_line_length - len(domain) - 10
                    path_truncated: str = (
                        path[:path_max] + "..." if len(path) > path_max else path
                    )
                    url = f"{domain}{path_truncated}"
            except Exception:
                # Fall back to simple truncation if URL parsing fails
                url = url[: max_line_length - 3] + "..."

        return f"{title}\n{url}"

    def action_cancel(self) -> None:
        """Close the screen without taking action."""
        self.app.pop_screen()

    def action_select(self) -> None:
        """Process the selected link."""
        link_list: ListView = self.query_one(
            selector="#link-list", expect_type=ListView
        )
        if link_list.index is None or not self.links:
            self.notify(
                title="Error", message="No link selected", timeout=3, severity="error"
            )
            self.app.pop_screen()
            return

        try:
            index: int = link_list.index
            if index < 0 or index >= len(self.links):
                self.notify(
                    title="Error",
                    message="Invalid selection",
                    timeout=3,
                    severity="error",
                )
                self.app.pop_screen()
                return

            link = self.links[index][1]
            if not link:
                self.notify(
                    title="Error",
                    message="Selected link has no URL",
                    timeout=3,
                    severity="error",
                )
                self.app.pop_screen()
                return

            self._process_link(link=link)
            self.app.pop_screen()
        except Exception as e:
            logger.error(msg=f"Error processing selection: {e}")
            self.notify(
                title="Error", message=f"Error: {e!s}", timeout=3, severity="error"
            )
            self.app.pop_screen()

    def _process_link(self, link: str) -> None:
        """Process the selected link based on open_links setting.

        Args:
            link: The URL to process
        """
        if self.open_links == "browser":
            import webbrowser

            webbrowser.open(url=link)
            self.notify(title="Opening", message="Opening link in browser", timeout=3)
        elif self.open_links == "download":
            self.download_file(link=link)
        elif self.open_links == "readwise":
            self._save_to_readwise(link=link)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Handle list view selection.

        Args:
            event: Selection event
        """
        try:
            # Process the selected item
            if event.list_view and len(self.links) > 0:
                index = event.list_view.index
                if index is not None and 0 <= index < len(self.links):
                    link = self.links[index][1]
                    if link:
                        self._process_link(link=link)

            # Close the screen
            self.app.pop_screen()
        except Exception as e:
            logger.error(msg=f"Error handling link selection: {e}")
            self.notify(
                title="Error", message=f"Error: {e!s}", timeout=3, severity="error"
            )
            self.app.pop_screen()

    def download_file(self, link: str) -> None:
        """Download a file from the given URL using httpx.

        Args:
            link: URL to download
        """
        try:
            from pathlib import Path
            from urllib.parse import urlparse

            # Extract filename from URL
            filename: str = Path(urlparse(url=link).path).name
            if not filename:
                filename = "downloaded_file"

            # Download the file
            download_path = self.configuration.download_folder / filename

            with self.http_client.stream(method="GET", url=link) as response:
                response.raise_for_status()
                with open(file=download_path, mode="wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)

            self.notify(
                title="Downloaded",
                message=f"File downloaded to {download_path}",
                timeout=5,
            )
        except httpx.HTTPError as e:
            logger.error(msg=f"HTTP error downloading file: {e}")
            self.notify(
                title="Download Error",
                message=f"HTTP error downloading file: {e!s}",
                timeout=5,
                severity="error",
            )
        except Exception as e:
            logger.error(msg=f"Error downloading file: {e}")
            self.notify(
                title="Download Error",
                message=f"Error downloading file: {e!s}",
                timeout=5,
                severity="error",
            )

    def _save_to_readwise(self, link: str) -> None:
        """Save the selected link to Readwise.

        Args:
            link: URL to save
        """
        try:
            os.environ["READWISE_TOKEN"] = self.configuration.readwise_token
            import readwise
            from readwise.model import PostResponse

            # Show a progress indicator during the API call
            self.app.push_screen(screen="progress")

            # Save to Readwise
            response: tuple[bool, PostResponse] = readwise.save_document(url=link)

            # Remove progress screen
            self.app.pop_screen()

            if response[1].url and response[1].id:
                self.notify(
                    title="Readwise",
                    message="Link saved to Readwise.",
                    timeout=5,
                )
                if self.open:
                    import webbrowser

                    webbrowser.open(url=response[1].url)
            else:
                self.notify(
                    title="Readwise",
                    message="Error saving link to Readwise.",
                    timeout=5,
                    severity="error",
                )
        except Exception as err:
            # Make sure to remove progress screen if there's an error
            if isinstance(self.screen, "ProgressScreen"):  # type: ignore
                self.app.pop_screen()

            logger.error(msg=f"Error saving to Readwise: {err}")
            self.notify(
                title="Readwise",
                message=f"Error: {err!s}",
                timeout=5,
                severity="error",
            )
