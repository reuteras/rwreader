"""Screens for the reader's Extract menu: code blocks and indicators."""

import logging
import re
from pathlib import Path
from typing import Any, ClassVar

from textual.app import ComposeResult
from textual.binding import Binding
from textual.screen import ModalScreen
from textual.widgets import DataTable, Label, ListItem, ListView, Static

from ...utils.extractors import CodeBlock, Indicator, format_indicators

logger = logging.getLogger(__name__)

# Menu entries: (key, label, description)
EXTRACT_OPTIONS: list[tuple[str, str, str]] = [
    ("links", "Links", "Open a link from the article in the browser"),
    ("links_readwise", "Links → Readwise", "Save a link from the article to Reader"),
    ("attachments", "Attachments", "Download linked PDFs, media, images and archives"),
    ("code", "Code blocks", "Copy or save fenced code blocks"),
    ("indicators", "Indicators of compromise", "IPs, domains, URLs, hashes, CVEs"),
    ("references", "References", "DOIs, arXiv IDs, GitHub repos and RFCs"),
]

_MAX_SLUG_LENGTH = 40


def slugify(text: str) -> str:
    """Make a short, filesystem-safe slug from a title."""
    slug = re.sub(r"[^\w]+", "-", text.lower()).strip("-")
    return slug[:_MAX_SLUG_LENGTH].rstrip("-") or "article"


def unique_path(folder: Path, stem: str, extension: str) -> Path:
    """Return a path in ``folder`` that does not exist yet."""
    candidate = folder / f"{stem}.{extension}"
    counter = 2
    while candidate.exists():
        candidate = folder / f"{stem}-{counter}.{extension}"
        counter += 1
    return candidate


def _folder_from_config(configuration: Any) -> Path:
    """Read the download folder from configuration with a safe fallback."""
    folder = getattr(configuration, "download_folder", None)
    if isinstance(folder, str | Path):
        return Path(folder).expanduser()
    return Path.home() / "Downloads"


class ExtractMenuScreen(ModalScreen[str | None]):
    """Modal menu listing the available extractions."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Cancel"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
    ]

    def __init__(self, counts: dict[str, int] | None = None) -> None:
        """Initialize the menu.

        Args:
            counts: Optional number of items per option key, shown in the label.
        """
        super().__init__()
        self.counts = counts or {}

    def compose(self) -> ComposeResult:
        """Build the option list."""
        yield Label("Extract from article (Esc to go back):", id="extract-title")
        items = []
        for key, label, description in EXTRACT_OPTIONS:
            count = self.counts.get(key)
            suffix = f" ({count})" if count is not None else ""
            item = ListItem(Label(f"{label}{suffix}\n{description}"))
            item.data = key  # type: ignore[attr-defined]
            items.append(item)
        yield ListView(*items, id="extract-list")

    def on_mount(self) -> None:
        """Focus the list."""
        self.query_one("#extract-list", ListView).focus()

    def action_cursor_down(self) -> None:
        """Move down."""
        self.query_one("#extract-list", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move up."""
        self.query_one("#extract-list", ListView).action_cursor_up()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Return the chosen option key."""
        self.dismiss(getattr(event.item, "data", None))

    def action_cancel(self) -> None:
        """Close without choosing."""
        self.dismiss(None)


class CodeBlockScreen(ModalScreen[None]):
    """List the article's code blocks; copy one or save it to a file."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Close"),
        ("j", "cursor_down", "Down"),
        ("k", "cursor_up", "Up"),
        ("enter", "copy", "Copy"),
        ("c", "copy", "Copy"),
        ("s", "save", "Save to file"),
    ]

    def __init__(
        self, blocks: list[CodeBlock], article_title: str, configuration: Any
    ) -> None:
        """Initialize the screen.

        Args:
            blocks: Code blocks to show.
            article_title: Used for saved file names.
            configuration: App configuration (for the download folder).
        """
        super().__init__()
        self.blocks = blocks
        self.article_title = article_title
        self.configuration = configuration

    def compose(self) -> ComposeResult:
        """Build the list and preview."""
        yield Label("Code blocks — Enter/c copy, s save, Esc close", id="extract-title")
        items = []
        for number, block in enumerate(self.blocks, start=1):
            language = block.language or "text"
            first_line = block.code.strip().splitlines()[0][:60]
            items.append(
                ListItem(
                    Label(
                        f"{number}. {language} ({block.line_count} lines)\n{first_line}"
                    )
                )
            )
        yield ListView(*items, id="extract-list")
        yield Static("", id="code-preview", markup=False)

    def on_mount(self) -> None:
        """Focus the list and show the first preview."""
        self.query_one("#extract-list", ListView).focus()
        self._update_preview(0)

    def _current(self) -> CodeBlock | None:
        """The highlighted block, if any."""
        index = self.query_one("#extract-list", ListView).index
        if index is None or not (0 <= index < len(self.blocks)):
            return None
        return self.blocks[index]

    def _update_preview(self, index: int | None) -> None:
        """Show the first lines of the highlighted block."""
        preview = self.query_one("#code-preview", Static)
        if index is None or not (0 <= index < len(self.blocks)):
            preview.update("")
            return
        lines = self.blocks[index].code.splitlines()
        shown = "\n".join(lines[:12])
        if len(lines) > 12:  # noqa: PLR2004
            shown += f"\n… ({len(lines) - 12} more lines)"
        preview.update(shown)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        """Refresh the preview when the highlight moves."""
        self._update_preview(event.list_view.index)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Enter copies the block."""
        self.action_copy()

    def action_cursor_down(self) -> None:
        """Move down."""
        self.query_one("#extract-list", ListView).action_cursor_down()

    def action_cursor_up(self) -> None:
        """Move up."""
        self.query_one("#extract-list", ListView).action_cursor_up()

    def action_copy(self) -> None:
        """Copy the highlighted block to the clipboard."""
        block = self._current()
        if block is None:
            return
        self.app.copy_to_clipboard(block.code)
        self.notify(f"Copied {block.line_count} lines", title="Code")

    def action_save(self) -> None:
        """Save the highlighted block into the download folder."""
        block = self._current()
        if block is None:
            return
        index = self.query_one("#extract-list", ListView).index or 0
        folder = _folder_from_config(self.configuration)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = unique_path(
                folder, f"{slugify(self.article_title)}-{index + 1}", block.extension
            )
            path.write_text(block.code + "\n", encoding="utf-8")
        except OSError as e:
            logger.error(f"Error saving code block: {e}")
            self.notify(f"Could not save: {e}", title="Code", severity="error")
            return
        self.notify(f"Saved to {path}", title="Code")

    def action_cancel(self) -> None:
        """Close the screen."""
        self.dismiss(None)


class IndicatorScreen(ModalScreen[None]):
    """Table of indicators of compromise with copy and export actions."""

    BINDINGS: ClassVar[list[Binding | tuple[str, str] | tuple[str, str, str]]] = [
        ("escape", "cancel", "Close"),
        ("c", "copy_text", "Copy as text"),
        ("s", "save_csv", "Save CSV"),
        ("J", "save_json", "Save JSON"),
    ]

    def __init__(
        self,
        indicators: list[Indicator],
        article_title: str,
        configuration: Any,
    ) -> None:
        """Initialize the screen.

        Args:
            indicators: Indicators to show.
            article_title: Used for exported file names.
            configuration: App configuration (for the download folder).
        """
        super().__init__()
        self.indicators = indicators
        self.article_title = article_title
        self.configuration = configuration

    def compose(self) -> ComposeResult:
        """Build the table."""
        yield Label(
            f"{len(self.indicators)} indicators — Enter copy value, c copy all, "
            "s save CSV, J save JSON, Esc close",
            id="extract-title",
        )
        table: DataTable[str] = DataTable(id="indicator-table", cursor_type="row")
        yield table

    def on_mount(self) -> None:
        """Populate and focus the table."""
        table = self.query_one("#indicator-table", DataTable)
        table.add_columns("kind", "value", "defanged")
        for item in self.indicators:
            table.add_row(item.kind, item.value, "yes" if item.defanged else "")
        table.focus()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Enter on a row copies its value (the table owns the Enter key)."""
        self.action_copy_value()

    def action_copy_value(self) -> None:
        """Copy the highlighted indicator's value."""
        table = self.query_one("#indicator-table", DataTable)
        row = table.cursor_row
        if row is None or not (0 <= row < len(self.indicators)):
            return
        value = self.indicators[row].value
        self.app.copy_to_clipboard(value)
        self.notify(f"Copied {value}", title="Indicators")

    def action_copy_text(self) -> None:
        """Copy every indicator as grouped plain text."""
        self.app.copy_to_clipboard(format_indicators(self.indicators, "text"))
        self.notify(f"Copied {len(self.indicators)} indicators", title="Indicators")

    def _save(self, fmt: str, extension: str) -> None:
        """Write the indicators to the download folder."""
        folder = _folder_from_config(self.configuration)
        try:
            folder.mkdir(parents=True, exist_ok=True)
            path = unique_path(
                folder, f"{slugify(self.article_title)}-indicators", extension
            )
            path.write_text(format_indicators(self.indicators, fmt), encoding="utf-8")
        except OSError as e:
            logger.error(f"Error saving indicators: {e}")
            self.notify(f"Could not save: {e}", title="Indicators", severity="error")
            return
        self.notify(f"Saved to {path}", title="Indicators")

    def action_save_csv(self) -> None:
        """Save as CSV."""
        self._save("csv", "csv")

    def action_save_json(self) -> None:
        """Save as JSON."""
        self._save("json", "json")

    def action_cancel(self) -> None:
        """Close the screen."""
        self.dismiss(None)
