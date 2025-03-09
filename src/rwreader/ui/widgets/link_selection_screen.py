"""Link selection screen for rwreader."""

import logging
import webbrowser
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from textual.app import ComposeResult
from textual.screen import ModalScreen
from textual.widgets import (
    Footer,
    ListItem,
    ListView,
    LoadingIndicator,
    Static,
)

logger: logging.Logger = logging.getLogger(name=__name__)


class LinkSelectionScreen(ModalScreen):
    """Modal screen to show extracted links and allow selection."""

    BINDINGS = [
        ("escape", "cancel", "Cancel"),
        ("enter", "select", "Select"),
    ]

    def __init__(
        self,
        links: list[tuple[str, str]],
        configuration: Any,
        action: Literal["browser", "readwise", "download"] = "browser",
        open_after_save: bool = False,
    ) -> None:
        """Initialize the link selection screen.

        Args:
            links: List of tuples with link title and URL
            configuration: App configuration
            action: Action to perform on selected link (browser, readwise, download)
            open_after_save: Whether to open the link after saving to Readwise
        """
        super().__init__()
        self.links = links or []
        self.action = action
        self.open_after_save = open_after_save
        self.configuration = configuration
        self.http_client = httpx.Client(follow_redirects=True)

    def compose(self) -> ComposeResult:
        """Define the content layout of the link selection screen."""
        # Determine title based on action
        if self.action == "browser":
            title = "Select a link to open in browser"
        elif self.action == "download":
            title = "Select a link to download"
        elif self.action == "readwise":
            title = "Select a link to save to Readwise"
        else:
            title = "Select a link"

        yield Static(f"# {title}\n\nPress [ESC] to go back", id="link-title")

        # Handle empty links list
        if not self.links:
            yield Static("No links found in article", id="no-links")
            return

        # Loading indicator (hidden initially)
        yield LoadingIndicator(id="loading-indicator")

        # Create a list view with all links
        link_items = []
        for i, (title, url) in enumerate(self.links):
            display_text = f"{title}\n{url}"
            link_items.append(
                ListItem(Static(display_text, markup=False), id=f"link_{i}")
            )

        link_list = ListView(*link_items, id="link-list")
        yield link_list

        # Add a footer with instructions
        yield Footer()

    def on_mount(self) -> None:
        """Set focus to the list view and hide loading indicator."""
        if self.links:
            link_list = self.query_one("#link-list", ListView)
            link_list.focus()

        # Hide loading indicator initially
        loading = self.query_one("#loading-indicator", LoadingIndicator)
        loading.display = False

    def action_cancel(self) -> None:
        """Close the screen without taking action."""
        self.dismiss()

    def action_select(self) -> None:
        """Process the selected link."""
        if not self.links:
            self.dismiss()
            return

        link_list = self.query_one("#link-list", ListView)
        if link_list.index is None:
            self.app.notify("No link selected", title="Error", severity="warning")
            self.dismiss()
            return

        try:
            index = link_list.index
            if index < 0 or index >= len(self.links):
                self.app.notify("Invalid selection", title="Error", severity="error")
                self.dismiss()
                return

            # Get the selected link
            _, url = self.links[index]

            # Process based on action type
            if self.action == "browser":
                self._open_in_browser(url)
            elif self.action == "download":
                self._download_file(url)
            elif self.action == "readwise":
                self._save_to_readwise(url)

            self.dismiss()
        except Exception as e:
            logger.error(f"Error processing link selection: {e}")
            self.app.notify(f"Error: {e}", title="Error", severity="error")
            self.dismiss()

    def _open_in_browser(self, url: str) -> None:
        """Open the URL in a web browser.

        Args:
            url: URL to open
        """
        webbrowser.open(url)
        self.app.notify("Opening link in browser", title="Browser")

    def _download_file(self, url: str) -> None:
        """Download a file from the URL.

        Args:
            url: URL to download
        """
        try:
            # Show loading indicator
            loading = self.query_one("#loading-indicator", LoadingIndicator)
            loading.display = True

            # Extract filename from URL
            filename = Path(urlparse(url).path).name
            if not filename:
                filename = "downloaded_file"

            # Download path from configuration
            download_folder = getattr(
                self.configuration, "download_folder", Path.home() / "Downloads"
            )
            download_path = download_folder / filename

            # Download the file
            with self.http_client.stream("GET", url) as response:
                response.raise_for_status()
                with open(download_path, "wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)

            # Hide loading indicator
            loading.display = False

            self.app.notify(f"File downloaded to {download_path}", title="Download")
        except Exception as e:
            # Hide loading indicator
            loading = self.query_one("#loading-indicator", LoadingIndicator)
            loading.display = False

            logger.error(f"Error downloading file: {e}")
            self.app.notify(
                f"Error downloading file: {e}", title="Error", severity="error"
            )

    def _save_to_readwise(self, url: str) -> None:
        """Save the URL to Readwise.

        Args:
            url: URL to save
        """
        if (
            not hasattr(self.configuration, "readwise_token")
            or not self.configuration.readwise_token
        ):
            self.app.notify(
                "No Readwise token configured", title="Error", severity="error"
            )
            return

        try:
            # Show loading indicator
            loading = self.query_one("#loading-indicator", LoadingIndicator)
            loading.display = True

            # Import readwise and use the API
            import readwise

            # Save the document
            success, response = readwise.save_document(url=url)

            # Hide loading indicator
            loading.display = False

            if success:
                self.app.notify("Link saved to Readwise", title="Readwise")

                # Open in browser if requested
                if self.open_after_save and hasattr(response, "url") and response.url:
                    webbrowser.open(response.url)
            else:
                error_msg = getattr(response, "error", "Unknown error")
                self.app.notify(
                    f"Error saving to Readwise: {error_msg}",
                    title="Error",
                    severity="error",
                )
        except Exception as e:
            # Hide loading indicator
            loading = self.query_one("#loading-indicator", LoadingIndicator)
            loading.display = False

            logger.error(f"Error saving to Readwise: {e}")
            self.app.notify(
                f"Error saving to Readwise: {e}", title="Error", severity="error"
            )
