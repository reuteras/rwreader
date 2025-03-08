"""Status widget to display API rate limit information."""

import time

from textual.widgets import Static


class APIStatusWidget(Static):
    """Widget that displays API rate limit status."""

    DEFAULT_CSS = """
    APIStatusWidget {
        height: auto;
        dock: bottom;
        padding: 0 1;
        background: $primary-background;
        color: $text;
        border-top: solid $primary;
        display: none;
    }

    APIStatusWidget.warning {
        background: $warning;
        color: $text;
        display: block;
    }

    APIStatusWidget.error {
        background: $error;
        color: $text;
        display: block;
    }

    APIStatusWidget.info {
        background: $primary-background;
        color: $text;
        display: block;
    }
    """

    # Update the initialization to disable markup
    def __init__(self, name: str = "") -> None:
        """Initialize the widget."""
        # Initialize with empty string and markup disabled
        super().__init__("", name=name, markup=False)
        self.retry_time = None
        self.status: str = "hidden"
        self._update_timer = self.set_interval(1, self._update_countdown)

    # Update all methods that call update() to escape square brackets if needed
    def show_rate_limit(self, retry_after: int, message: str | None = None) -> None:
        """Show rate limit information.

        Args:
            retry_after: Seconds until retry is allowed
            message: Optional custom message
        """
        self.retry_time = time.time() + retry_after
        if message is None:
            message = f"API rate limit reached. Please wait {retry_after} seconds before continuing."
        self.update(message)
        self.add_class("warning")
        self.status = "warning"

    def _update_countdown(self) -> None:
        """Update the countdown timer if showing a rate limit warning."""
        if self.retry_time is not None:
            remaining = max(0, self.retry_time - time.time())
            if remaining <= 0:
                self.hide()
            else:
                message = f"API rate limit reached. Please wait {int(remaining)} seconds before continuing."
                self.update(message)

    def show_error(self, message: str) -> None:
        """Show an error message.

        Args:
            message: Error message to display
        """
        self.retry_time = None
        self.update(message)
        self.add_class("error")
        self.remove_class("warning")
        self.remove_class("info")
        self.status = "error"

    def show_info(self, message: str) -> None:
        """Show an informational message.

        Args:
            message: Information to display
        """
        self.retry_time = None
        self.update(message)
        self.add_class("info")
        self.remove_class("warning")
        self.remove_class("error")
        self.status = "info"

    def hide(self) -> None:
        """Hide the status widget."""
        self.retry_time = None
        self.remove_class("warning")
        self.remove_class("error")
        self.remove_class("info")
        self.status = "hidden"
