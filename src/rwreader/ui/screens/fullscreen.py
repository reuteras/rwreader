"""Fullscreen content screens for ttrsscli."""

from collections.abc import Generator
from typing import Any

from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import TextArea

from ..widgets.linkable_markdown_viewer import (
    ALLOW_IN_FULL_SCREEN,
    LinkableMarkdownViewer,
)


class FullScreenMarkdown(Screen):
    """A full-screen Markdown viewer."""

    def __init__(self, markdown_content: str) -> None:
        """Initialize the full-screen Markdown viewer.

        Args:
            markdown_content: Markdown content to display
        """
        super().__init__()
        self.markdown_content: str = markdown_content

    def compose(self) -> ComposeResult:
        """Define the content layout of the full-screen Markdown viewer."""
        # Use our Rich markdown view instead of the standard LinkableMarkdownViewer
        yield LinkableMarkdownViewer(
            markdown=self.markdown_content,
            show_table_of_contents=False,
            open_links=False,
        )

    def on_key(self, event) -> None:
        """Close the full-screen Markdown viewer on any key press except navigation keys.

        Args:
            event: Key event
        """
        if event.key in ALLOW_IN_FULL_SCREEN:
            pass
        else:
            self.app.pop_screen()


class FullScreenTextArea(Screen):
    """A full-screen TextArea."""

    def __init__(self, text: str) -> None:
        """Initialize the full-screen TextArea.

        Args:
            text: Text to display
        """
        super().__init__()
        self.text: str = text

    def compose(self) -> Generator[TextArea, Any, None]:
        """Define the content layout of the full-screen TextArea."""
        yield TextArea.code_editor(text=self.text, language="markdown", read_only=True)

    def on_key(self, event) -> None:
        """Close the full-screen TextArea on any key press except navigation keys.

        Args:
            event: Key event
        """
        event.prevent_default()
        if event.key in ALLOW_IN_FULL_SCREEN:
            pass
        else:
            self.app.pop_screen()
