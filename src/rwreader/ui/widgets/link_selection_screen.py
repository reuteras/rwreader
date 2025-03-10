"""Link selection screen for rwreader."""

import logging
import webbrowser
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlparse

import httpx
from textual.app import ComposeResult
from textual.binding import Binding
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

    BINDINGS: list[Binding | tuple[str, str] | tuple[str, str, str]] = [  # noqa: RUF012
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
        self.links: list[tuple[str, str]] = links or []
        self.action: Literal["browser"] | Literal["readwise"] | Literal["download"] = (
            action
        )
        self.open_after_save: bool = open_after_save
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

        yield Static(content=f"# {title}\n\nPress ESC to go back", id="link-title")

        # Handle empty links list
        if not self.links:
            yield Static(content="No links found in article", id="no-links")
            return

        # Loading indicator (hidden initially)
        yield LoadingIndicator(id="loading-indicator")

        # Create a list view with all links
        link_items: list[ListItem] = []
        for i, (title, url) in enumerate(iterable=self.links):
            display_text: str = f"{title}\n{url}"
            link_items.append(
                ListItem(Static(content=display_text, markup=False), id=f"link_{i}")
            )

        link_list = ListView(*link_items, id="link-list")
        yield link_list

        # Add a footer with instructions
        yield Footer()

    def on_mount(self) -> None:
        """Set focus to the list view and hide loading indicator."""
        if self.links:
            link_list: ListView = self.query_one(
                selector="#link-list", expect_type=ListView
            )
            link_list.focus()

        # Hide loading indicator initially
        loading: LoadingIndicator = self.query_one(
            selector="#loading-indicator", expect_type=LoadingIndicator
        )
        loading.display = False

    def action_cancel(self) -> None:
        """Close the screen without taking action."""
        self.dismiss()

    def action_select(self) -> None:
        """Process the selected link."""
        if not self.links:
            self.dismiss()
            return

        link_list: ListView = self.query_one(
            selector="#link-list", expect_type=ListView
        )
        if link_list.index is None:
            self.app.notify(
                message="No link selected", title="Error", severity="warning"
            )
            self.dismiss()
            return

        try:
            index: int = link_list.index
            if index < 0 or index >= len(self.links):
                self.app.notify(
                    message="Invalid selection", title="Error", severity="error"
                )
                self.dismiss()
                return

            # Get the selected link
            _, url = self.links[index]

            # Process based on action type
            if self.action == "browser":
                self._open_in_browser(url=url)
            elif self.action == "download":
                self._download_file(url=url)
            elif self.action == "readwise":
                self._save_to_readwise(url=url)

            self.dismiss()
        except Exception as e:
            logger.error(msg=f"Error processing link selection: {e}")
            self.app.notify(message=f"Error: {e}", title="Error", severity="error")
            self.dismiss()

    def _open_in_browser(self, url: str) -> None:
        """Open the URL in a web browser.

        Args:
            url: URL to open
        """
        webbrowser.open(url=url)
        self.app.notify(message="Opening link in browser", title="Browser")

    def _download_file(self, url: str) -> None:
        """Download a file from the URL.

        Args:
            url: URL to download
        """
        try:
            # Show loading indicator
            loading: LoadingIndicator = self.query_one(
                selector="#loading-indicator", expect_type=LoadingIndicator
            )
            loading.display = True

            # Extract filename from URL
            filename: str = Path(urlparse(url=url).path).name
            if not filename:
                filename = "downloaded_file"

            # Download path from configuration
            download_folder = Path(
                getattr(
                    self.configuration, "download_folder", Path.home() / "Downloads"
                )
            )
            download_path: Path = download_folder / filename

            # Download the file
            with self.http_client.stream(method="GET", url=url) as response:
                response.raise_for_status()
                with open(file=download_path, mode="wb") as f:
                    for chunk in response.iter_bytes():
                        f.write(chunk)

            # Hide loading indicator
            loading.display = False

            self.app.notify(
                message=f"File downloaded to {download_path}", title="Download"
            )
        except Exception as e:
            # Hide loading indicator
            loading = self.query_one(
                selector="#loading-indicator", expect_type=LoadingIndicator
            )
            loading.display = False

            logger.error(msg=f"Error downloading file: {e}")
            self.app.notify(
                message=f"Error downloading file: {e}", title="Error", severity="error"
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
                message="No Readwise token configured", title="Error", severity="error"
            )
            return

        try:
            # Show loading indicator
            loading: LoadingIndicator = self.query_one(
                selector="#loading-indicator", expect_type=LoadingIndicator
            )
            loading.display = True

            # Save the document
            success, response = self.client.save_document(url=url)

            # Hide loading indicator
            loading.display = False

            if success:
                self.app.notify(message="Link saved to Readwise", title="Readwise")

                # Open in browser if requested
                if self.open_after_save and hasattr(response, "url") and response.url:
                    webbrowser.open(url=response.url)
            else:
                error_msg: str = getattr(response, "error", "Unknown error")
                self.app.notify(
                    message=f"Error saving to Readwise: {error_msg}",
                    title="Error",
                    severity="error",
                )
        except Exception as e:
            # Hide loading indicator
            loading = self.query_one(
                selector="#loading-indicator", expect_type=LoadingIndicator
            )
            loading.display = False

            logger.error(msg=f"Error saving to Readwise: {e}")
            self.app.notify(
                message=f"Error saving to Readwise: {e}",
                title="Error",
                severity="error",
            )
