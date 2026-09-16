"""Link selection screen."""

import asyncio
import logging
import re
import webbrowser
from functools import partial
from pathlib import Path
from typing import Any, ClassVar
from urllib.parse import ParseResult, urlparse

import httpx2 as httpx
from textual import work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import Label, ListItem, ListView

logger = logging.getLogger(name=__name__)


class LinkSelectionScreen(ModalScreen):
    """Modal screen to show extracted links and allow selection."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
        ("enter", "select", "Select"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("S", "save_all_readwise", "Save all to Readwise"),
    ]

    def __init__(
        self,
        configuration: Any,
        links: list[tuple[str, str]] | None,
        open_links: str = "browser",
        open: bool = False,
        title: str | None = None,
    ) -> None:
        """Initialize the link selection screen.

        Args:
            configuration: App configuration
            links: List of tuples with link title and URL
            open_links: Action to perform on selected link
            open: Whether to open the link after saving to Readwise
            title: Optional heading replacing the default for ``open_links``
        """
        super().__init__()
        self.links: Any = links or []  # Ensure links is never None
        self.open_links: str = open_links
        self.open: bool = open
        self.configuration: Any = configuration
        self.title_text: str | None = title
        self.selected_index = 0

    def compose(self) -> ComposeResult:
        """Define the content layout of the link selection screen."""
        if self.title_text:
            title = self.title_text
        elif self.open_links == "browser":
            title = "Select a link to open (ESC to go back, S saves all to Readwise):"
        elif self.open_links == "download":
            title = "Select a file to download (ESC to go back):"
        elif self.open_links == "readwise":
            title = "Select a link to save to Readwise (ESC to go back, S saves all):"
        else:
            title = "Select a link (ESC to go back):"

        yield Label(title)

        # Handle empty links list
        if not self.links:
            yield Label("No links found in article")
            return

        # Create a list view with all links
        link_select = ListView(
            *[
                ListItem(Label(self._format_link_item(link=link)))
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

    def action_cursor_down(self) -> None:
        """Move the highlight down."""
        self.query_one(selector="#link-list", expect_type=ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move the highlight up."""
        self.query_one(selector="#link-list", expect_type=ListView).action_cursor_up()

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
                    url = domain[: max_line_length - 3] + "..."
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

    def _sanitize_filename(self, filename: str) -> str:
        """Sanitize filename to prevent path traversal and injection.

        Args:
            filename: Raw filename from URL

        Returns:
            Sanitized filename safe for filesystem use
        """
        # Remove any path components (keep only basename)
        filename = Path(filename).name

        # Remove or replace dangerous characters
        # Allow only alphanumeric, dash, underscore, dot
        filename = re.sub(r"[^\w\-.]", "_", filename)

        # Remove leading dots (hidden files)
        filename = filename.lstrip(".")

        # Limit length
        max_length = 200
        if len(filename) > max_length:
            # Keep extension if present
            if "." in filename:
                name, ext = filename.rsplit(".", 1)
                filename = name[: max_length - len(ext) - 1] + "." + ext
            else:
                filename = filename[:max_length]

        # Default if empty
        if not filename:
            filename = "downloaded_file"

        return filename

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

    def _download_folder(self) -> Path:
        """Download folder from configuration, defaulting to ~/Downloads."""
        folder = getattr(self.configuration, "download_folder", None)
        if isinstance(folder, str | Path):
            return Path(folder).expanduser()
        return Path.home() / "Downloads"

    def _download_target(self, link: str) -> Path | None:
        """Compute a safe, non-clobbering path inside the download folder."""
        folder = self._download_folder()
        raw_filename: str = Path(urlparse(url=link).path).name or "downloaded_file"
        filename = self._sanitize_filename(raw_filename)
        download_path = (folder / filename).resolve()
        try:
            download_path.relative_to(folder.resolve())
        except ValueError:
            logger.error(msg=f"Path traversal attempt detected: {filename}")
            return None
        stem, dot, ext = filename.rpartition(".")
        counter = 2
        while download_path.exists():
            candidate = (
                f"{stem}-{counter}{dot}{ext}" if dot else f"{filename}-{counter}"
            )
            download_path = folder / candidate
            counter += 1
        return download_path

    def download_file(self, link: str) -> None:
        """Download a file from the given URL in a background thread.

        The worker is attached to the app so it survives this modal closing.

        Args:
            link: URL to download
        """
        download_path = self._download_target(link)
        if download_path is None:
            self.notify(
                title="Download Error",
                message="Invalid filename",
                timeout=5,
                severity="error",
            )
            return

        app = self.app
        app.notify(title="Download", message=f"Downloading {download_path.name}…")

        def run() -> None:
            try:
                download_path.parent.mkdir(parents=True, exist_ok=True)
                with (
                    httpx.Client(follow_redirects=True, timeout=60) as client,
                    client.stream(method="GET", url=link) as response,
                ):
                    response.raise_for_status()
                    with open(file=download_path, mode="wb") as f:
                        for chunk in response.iter_bytes():
                            f.write(chunk)
            except httpx.HTTPError as e:
                logger.error(msg=f"HTTP error downloading file: {e}")
                app.call_from_thread(
                    app.notify,
                    title="Download Error",
                    message=f"HTTP error downloading file: {e!s}",
                    timeout=5,
                    severity="error",
                )
                return
            except Exception as e:
                logger.error(msg=f"Error downloading file: {e}")
                app.call_from_thread(
                    app.notify,
                    title="Download Error",
                    message=f"Error downloading file: {e!s}",
                    timeout=5,
                    severity="error",
                )
                return
            app.call_from_thread(
                app.notify,
                title="Downloaded",
                message=f"File downloaded to {download_path}",
                timeout=5,
            )

        app.run_worker(run, thread=True, exclusive=False, name="download")

    @work
    async def action_save_all_readwise(self) -> None:
        """Save every listed link to Readwise after confirmation."""
        client = getattr(self.app, "client", None)
        if client is None:
            self.notify(title="Readwise", message="API client not available.")
            return
        urls = [url for _, url in self.links if url]
        if not urls:
            self.notify(title="Readwise", message="No links to save.")
            return

        from .confirm import ConfirmScreen  # noqa: PLC0415

        result = await self.app.push_screen_wait(
            ConfirmScreen(
                title="Save to Readwise",
                message=f"Save all {len(urls)} links to your Reader inbox?",
                variant="primary",
            )
        )
        if not result or not result.get("confirmed"):
            return

        loop = asyncio.get_event_loop()
        saved = 0
        failed = 0
        for url in urls:
            success, _ = await loop.run_in_executor(
                None, partial(client.save_document, url=url)
            )
            if success:
                saved += 1
            else:
                failed += 1
        self.notify(
            title="Readwise",
            message=f"Saved {saved} links" + (f", {failed} failed" if failed else ""),
            severity="warning" if failed else "information",
        )

    def _save_to_readwise(self, link: str) -> None:
        """Save the selected link to Readwise.

        Args:
            link: URL to save
        """
        client = getattr(self.app, "client", None)
        if client is None:
            self.notify(
                title="Readwise",
                message="API client not available.",
                timeout=5,
                severity="error",
            )
            return

        try:
            self.notify(title="Readwise", message="Saving link...", timeout=2)
            success, response = client.save_document(url=link)

            if success and response and response.url and response.id:
                self.notify(
                    title="Readwise",
                    message="Link saved to Readwise.",
                    timeout=5,
                )
                if self.open:
                    webbrowser.open(url=response.url)
            else:
                self.notify(
                    title="Readwise",
                    message="Error saving link to Readwise.",
                    timeout=5,
                    severity="error",
                )
        except Exception as err:
            logger.error(msg=f"Error saving to Readwise: {err}")
            self.notify(
                title="Readwise",
                message=f"Error: {err!s}",
                timeout=5,
                severity="error",
            )
