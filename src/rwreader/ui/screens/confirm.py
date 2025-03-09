"""Confirmation dialog screens for rwreader."""

from typing import Any

from textual.app import ComposeResult
from textual.containers import Container, Horizontal
from textual.screen import ModalScreen
from textual.widgets import Button, Static


class ConfirmScreen(ModalScreen):
    """Modal screen for confirming actions like deletion."""

    BINDINGS = [  # noqa: RUF012
        ("escape", "cancel", "Cancel"),
        ("enter", "confirm", "Confirm"),
    ]

    def __init__(
        self,
        title: str = "Confirm",
        message: str = "Are you sure?",
        on_confirm=None,
        data: Any = None,
        variant: str = "error",
    ) -> None:
        """Initialize the confirmation screen.

        Args:
            title: Title of the confirmation dialog
            message: Message to display
            on_confirm: Callback function to run on confirmation
            data: Optional data to pass to the callback
            variant: Button variant (error, primary, success)
        """
        super().__init__()
        self.dialog_title = title
        self.message = message
        self.on_confirm = on_confirm
        self.data = data
        self.variant = variant

    def compose(self) -> ComposeResult:
        """Define the content layout of the confirmation screen."""
        with Container(id="confirm-container"):
            yield Static(f"# {self.dialog_title}", id="confirm-title")
            yield Static(self.message, id="confirm-message")
            with Horizontal(id="confirm-buttons"):
                yield Button("Confirm", id="confirm-button", variant=self.variant)
                yield Button("Cancel", id="cancel-button")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Handle button presses."""
        if event.button.id == "confirm-button":
            self.action_confirm()
        elif event.button.id == "cancel-button":
            self.action_cancel()

    def action_confirm(self) -> None:
        """Confirm the action and call the callback."""
        # Pop this screen first
        result = {"confirmed": True, "data": self.data}

        # Call the callback if provided
        if self.on_confirm:
            try:
                self.on_confirm(self.data)
            except Exception as e:
                self.app.notify(f"Error: {e}", title="Error", severity="error")

        self.dismiss(result)

    def action_cancel(self) -> None:
        """Cancel the action."""
        self.dismiss({"confirmed": False})


class DeleteArticleScreen(ConfirmScreen):
    """Specialized confirmation screen for article deletion."""

    def __init__(self, article_id: str, article_title: str) -> None:
        """Initialize the delete article confirmation screen.

        Args:
            article_id: ID of the article to delete
            article_title: Title of the article for the confirmation message
        """
        # Truncate title if too long
        if len(article_title) > 50:
            display_title = article_title[:47] + "..."
        else:
            display_title = article_title

        super().__init__(
            title="Delete Article",
            message=f"Are you sure you want to delete this article?\n\n**{display_title}**\n\nThis action cannot be undone.",
            data=article_id,
            variant="error",
        )
