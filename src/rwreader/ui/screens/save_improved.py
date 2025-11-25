"""Confirmation dialog for saving improved version to Readwise."""

from typing import ClassVar

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label, Static

CONTENT_PREVIEW_LENGTH = 200


class SaveImprovedScreen(ModalScreen[dict]):
    """Confirmation dialog for saving improved version to Readwise."""

    BINDINGS: ClassVar[list[tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
        ("enter", "confirm", "Confirm"),
    ]

    def __init__(
        self,
        original_url: str,
        readwise_url: str,
        content_preview: str,
    ) -> None:
        """Initialize the save improved dialog.

        Args:
            original_url: Original article source URL
            readwise_url: Link to original Readwise document
            content_preview: Preview of content to be saved
        """
        super().__init__()
        self.original_url = original_url
        self.readwise_url = readwise_url
        # Limit preview to first CONTENT_PREVIEW_LENGTH chars
        self.content_preview = (
            content_preview[:CONTENT_PREVIEW_LENGTH] + "..."
            if len(content_preview) > CONTENT_PREVIEW_LENGTH
            else content_preview
        )

    def compose(self) -> ComposeResult:
        """Compose the dialog layout."""
        yield Static("Save Improved Version to Readwise", id="title")
        with Vertical(id="content"):
            yield Label(f"Original URL: {self.original_url}")
            yield Label("")
            yield Label("This will create a new document with:")
            yield Label("• Modified URL: [original]?source=rwreader-improved")
            yield Label("• Cleaned HTML content")
            yield Label("• Link to original in summary")
            yield Label("• Tags: rwreader, improved")
            yield Label("")
            yield Label("Preview:")
            yield Static(self.content_preview, id="preview")
            yield Label("")
            with Horizontal(id="buttons"):
                yield Button("Save", variant="primary", id="save")
                yield Button("Cancel", variant="default", id="cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses.

        Args:
            event: Button pressed event
        """
        if event.button.id == "save":
            self.dismiss({"confirmed": True})
        else:
            self.dismiss({"confirmed": False})

    def action_confirm(self) -> None:
        """Confirm saving."""
        self.dismiss({"confirmed": True})

    def action_cancel(self) -> None:
        """Cancel saving."""
        self.dismiss({"confirmed": False})
