"""Tests for the Extract menu screens and link download target handling."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from textual.app import App

from rwreader.ui.screens.extract_screens import (
    EXTRACT_OPTIONS,
    CodeBlockScreen,
    ExtractMenuScreen,
    IndicatorScreen,
    slugify,
    unique_path,
)
from rwreader.ui.screens.link_screens import LinkSelectionScreen
from rwreader.utils.extractors import CodeBlock, Indicator

_OPTION_COUNT = 6


class _HostApp(App[None]):
    """Minimal app used to host modal screens under test."""

    def __init__(self) -> None:
        super().__init__()
        self.clipboard_text = ""
        self.result: str | None = "unset"

    def copy_to_clipboard(self, text: str) -> None:
        """Capture clipboard writes instead of emitting OSC 52."""
        self.clipboard_text = text


class TestHelpers:
    """Tests for slugify and unique_path."""

    def test_slugify(self) -> None:
        """Titles become short, safe, lowercase slugs."""
        assert slugify("Hello, World! 2024/09") == "hello-world-2024-09"
        assert slugify("!!!") == "article"
        assert len(slugify("x" * 100)) <= 40  # noqa: PLR2004

    def test_unique_path(self, tmp_path: Path) -> None:
        """Existing files are never overwritten."""
        first = unique_path(tmp_path, "a", "txt")
        assert first == tmp_path / "a.txt"
        first.write_text("1")
        second = unique_path(tmp_path, "a", "txt")
        assert second == tmp_path / "a-2.txt"
        second.write_text("2")
        assert unique_path(tmp_path, "a", "txt") == tmp_path / "a-3.txt"


class TestExtractMenuScreen:
    """Tests for the Extract menu."""

    @pytest.mark.asyncio
    async def test_lists_options_with_counts_and_returns_choice(self) -> None:
        """All options are listed, counts shown, Enter returns the chosen key."""
        app = _HostApp()
        async with app.run_test() as pilot:
            counts = {key: 3 for key, _, _ in EXTRACT_OPTIONS}

            def on_dismiss(choice: str | None) -> None:
                app.result = choice

            app.push_screen(ExtractMenuScreen(counts=counts), on_dismiss)
            await pilot.pause()
            assert isinstance(app.screen, ExtractMenuScreen)
            list_view = app.screen.query_one("#extract-list")
            assert len(list_view.children) == _OPTION_COUNT
            await pilot.press("j", "j", "enter")
            await pilot.pause()
            assert app.result == EXTRACT_OPTIONS[2][0]

    @pytest.mark.asyncio
    async def test_escape_returns_none(self) -> None:
        """Escape closes the menu with no choice."""
        app = _HostApp()
        async with app.run_test() as pilot:

            def on_dismiss(choice: str | None) -> None:
                app.result = choice

            app.push_screen(ExtractMenuScreen(), on_dismiss)
            await pilot.pause()
            await pilot.press("escape")
            await pilot.pause()
            assert app.result is None


class TestCodeBlockScreen:
    """Tests for the code block screen."""

    @pytest.mark.asyncio
    async def test_copy_and_save(self, tmp_path: Path) -> None:
        """Enter copies the highlighted block; s writes it to the download folder."""
        blocks = [
            CodeBlock("python", "print(1)\nprint(2)"),
            CodeBlock("", "plain text"),
        ]
        config = SimpleNamespace(download_folder=tmp_path / "dl")
        app = _HostApp()
        async with app.run_test() as pilot:
            app.push_screen(CodeBlockScreen(blocks, "My Article: Test", config))
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.clipboard_text == "print(1)\nprint(2)"

            await pilot.press("j", "s")
            await pilot.pause()
            saved = tmp_path / "dl" / "my-article-test-2.txt"
            assert saved.read_text() == "plain text\n"

            await pilot.press("k", "s")
            await pilot.pause()
            assert (tmp_path / "dl" / "my-article-test-1.py").read_text() == (
                "print(1)\nprint(2)\n"
            )


class TestIndicatorScreen:
    """Tests for the indicator screen."""

    @pytest.mark.asyncio
    async def test_copy_value_copy_all_and_exports(self, tmp_path: Path) -> None:
        """Row copy, bulk copy, CSV and JSON export all work."""
        indicators = [
            Indicator("ipv4", "8.8.8.8", defanged=True),
            Indicator("cve", "CVE-2024-1"),
        ]
        config = SimpleNamespace(download_folder=str(tmp_path))
        app = _HostApp()
        async with app.run_test() as pilot:
            app.push_screen(IndicatorScreen(indicators, "Report", config))
            await pilot.pause()
            await pilot.press("enter")
            await pilot.pause()
            assert app.clipboard_text == "8.8.8.8"

            await pilot.press("c")
            await pilot.pause()
            assert app.clipboard_text == "# ipv4\n8.8.8.8\n\n# cve\nCVE-2024-1"

            await pilot.press("s", "J")
            await pilot.pause()
            csv_text = (tmp_path / "report-indicators.csv").read_text()
            assert csv_text.splitlines()[1] == "ipv4,8.8.8.8,true"
            json_text = (tmp_path / "report-indicators.json").read_text()
            assert '"value": "CVE-2024-1"' in json_text


class TestLinkSelectionDownloadTarget:
    """Tests for LinkSelectionScreen download path handling."""

    def test_target_inside_folder_and_no_clobber(self, tmp_path: Path) -> None:
        """Targets land in the configured folder and get a suffix when taken."""
        config = SimpleNamespace(download_folder=tmp_path)
        screen = LinkSelectionScreen(
            configuration=config, links=[], open_links="download"
        )
        target = screen._download_target("https://e.com/files/report.pdf?x=1")
        assert target == tmp_path / "report.pdf"
        target.write_bytes(b"x")
        assert screen._download_target("https://e.com/report.pdf") == (
            tmp_path / "report-2.pdf"
        )

    def test_missing_config_falls_back_to_downloads(self) -> None:
        """A configuration without download_folder uses ~/Downloads."""
        screen = LinkSelectionScreen(configuration=object(), links=[])
        assert screen._download_folder() == Path.home() / "Downloads"

    def test_url_without_filename(self, tmp_path: Path) -> None:
        """A bare host URL gets a default file name."""
        config = SimpleNamespace(download_folder=tmp_path)
        screen = LinkSelectionScreen(configuration=config, links=[])
        assert screen._download_target("https://e.com/") == tmp_path / "downloaded_file"
