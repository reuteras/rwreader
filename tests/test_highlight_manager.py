"""Tests for the highlight_manager module."""

import json
from unittest.mock import MagicMock, patch

from rwreader.utils.highlight_manager import (
    create_reader_highlight,
    delete_highlight,
    find_html_fragment,
    get_highlights_for_document,
    inject_highlights_into_markdown,
)

# ── inject_highlights_into_markdown ──────────────────────────────────────────


class TestInjectHighlightsIntoMarkdown:
    """Tests for inject_highlights_into_markdown."""

    def test_no_highlights_returns_unchanged(self) -> None:
        """Empty highlights list leaves markdown unchanged."""
        md = "# Title\n\nSome paragraph text."
        assert inject_highlights_into_markdown(md, []) == md

    def test_appends_highlights_section(self) -> None:
        """A Highlights section is always appended when highlights exist."""
        md = "# Title\n\nSome text."
        result = inject_highlights_into_markdown(
            md, [{"content": "Some text.", "notes": None}]
        )
        assert "## Highlights" in result
        assert "> Some text." in result

    def test_inline_marker_added_when_text_found(self) -> None:
        """Highlight text found in the markdown gets ⟦…⟧ markers."""
        para = "The quick brown fox jumps over the lazy dog."
        md = f"# Title\n\n{para}"
        result = inject_highlights_into_markdown(md, [{"content": para, "notes": None}])
        assert "⟦" in result
        assert "⟧" in result

    def test_notes_appear_in_highlights_section(self) -> None:
        """Highlight notes are rendered below the quoted text."""
        md = "# Title\n\nHere is text."
        highlights = [{"content": "Here is text.", "notes": "My annotation"}]
        result = inject_highlights_into_markdown(md, highlights)
        assert "Note: My annotation" in result

    def test_null_notes_not_rendered(self) -> None:
        """A null notes value produces no Note: line."""
        md = "# Title\n\nSome text."
        result = inject_highlights_into_markdown(
            md, [{"content": "Some text.", "notes": None}]
        )
        assert "Note:" not in result

    def test_missing_content_field_skipped(self) -> None:
        """Highlights with no content are silently skipped."""
        md = "# Title\n\nSome text."
        result = inject_highlights_into_markdown(md, [{"content": None, "notes": None}])
        assert "## Highlights" not in result

    def test_multiple_highlights(self) -> None:
        """Multiple highlights all appear in the Highlights section."""
        md = "# Title\n\nFirst paragraph.\n\nSecond paragraph."
        highlights = [
            {"content": "First paragraph.", "notes": None},
            {"content": "Second paragraph.", "notes": None},
        ]
        result = inject_highlights_into_markdown(md, highlights)
        assert result.count(">") >= len(highlights)


# ── find_html_fragment ────────────────────────────────────────────────────────


class TestFindHtmlFragment:
    """Tests for find_html_fragment."""

    def test_exact_paragraph_match(self) -> None:
        """Returns the matching <p> element when text is found."""
        html = "<html><body><p>Hello world sentence here.</p></body></html>"
        result = find_html_fragment(html, "Hello world sentence here.")
        assert "<p>" in result
        assert "Hello world" in result

    def test_fallback_when_not_found(self) -> None:
        """Falls back to <p>text</p> when no element matches."""
        html = "<html><body><p>Different text entirely.</p></body></html>"
        result = find_html_fragment(html, "Something completely different")
        assert result == "<p>Something completely different</p>"

    def test_empty_html_fallback(self) -> None:
        """Empty html_content always triggers the fallback."""
        result = find_html_fragment("", "Any text here")
        assert result == "<p>Any text here</p>"

    def test_whitespace_normalisation(self) -> None:
        """Handles extra whitespace in both html and search text."""
        html = "<body><p>Some  text   with  spaces.</p></body>"
        result = find_html_fragment(html, "Some text with spaces.")
        assert "Some" in result


# ── get_highlights_for_document ───────────────────────────────────────────────


class TestGetHighlightsForDocument:
    """Tests for get_highlights_for_document."""

    @patch("rwreader.utils.highlight_manager.get_cli_path", return_value=None)
    def test_returns_empty_when_no_cli(self, _mock: MagicMock) -> None:
        """Returns empty list immediately when CLI is unavailable."""
        assert get_highlights_for_document("doc123") == []

    @patch("rwreader.utils.highlight_manager.get_cli_path", return_value=None)
    def test_returns_empty_for_empty_document_id(self, _mock: MagicMock) -> None:
        """Returns empty list for empty document_id."""
        assert get_highlights_for_document("") == []

    @patch("rwreader.utils.highlight_manager.subprocess.run")
    @patch(
        "rwreader.utils.highlight_manager.get_cli_path",
        return_value="/usr/bin/readwise",
    )
    def test_parses_list_response(self, _cli: MagicMock, mock_run: MagicMock) -> None:
        """Parses a JSON list returned by the CLI."""
        payload = [{"id": "abc", "content": "Some text", "tags": [], "notes": None}]
        mock_run.return_value = MagicMock(
            returncode=0, stdout=json.dumps(payload), stderr=""
        )
        result = get_highlights_for_document("doc123")
        assert len(result) == 1
        assert result[0]["content"] == "Some text"

    @patch("rwreader.utils.highlight_manager.subprocess.run")
    @patch(
        "rwreader.utils.highlight_manager.get_cli_path",
        return_value="/usr/bin/readwise",
    )
    def test_returns_empty_on_cli_error(
        self, _cli: MagicMock, mock_run: MagicMock
    ) -> None:
        """Returns empty list when CLI exits with non-zero code."""
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        assert get_highlights_for_document("doc123") == []

    @patch("rwreader.utils.highlight_manager.subprocess.run")
    @patch(
        "rwreader.utils.highlight_manager.get_cli_path",
        return_value="/usr/bin/readwise",
    )
    def test_returns_empty_on_invalid_json(
        self, _cli: MagicMock, mock_run: MagicMock
    ) -> None:
        """Returns empty list when CLI output is not valid JSON."""
        mock_run.return_value = MagicMock(returncode=0, stdout="not-json", stderr="")
        assert get_highlights_for_document("doc123") == []

    @patch("rwreader.utils.highlight_manager.subprocess.run")
    @patch(
        "rwreader.utils.highlight_manager.get_cli_path",
        return_value="/usr/bin/readwise",
    )
    def test_returns_empty_on_timeout(
        self, _cli: MagicMock, mock_run: MagicMock
    ) -> None:
        """Returns empty list on subprocess timeout."""
        mock_run.side_effect = __import__("subprocess").TimeoutExpired(
            cmd="readwise", timeout=20
        )
        assert get_highlights_for_document("doc123") == []


# ── create_reader_highlight ───────────────────────────────────────────────────


class TestCreateReaderHighlight:
    """Tests for create_reader_highlight."""

    @patch("rwreader.utils.highlight_manager.get_cli_path", return_value=None)
    def test_fails_without_cli(self, _mock: MagicMock) -> None:
        """Returns failure when CLI is not available."""
        success, msg = create_reader_highlight("doc123", "<p>text</p>")
        assert not success
        assert "not available" in msg

    @patch("rwreader.utils.highlight_manager.subprocess.run")
    @patch(
        "rwreader.utils.highlight_manager.get_cli_path",
        return_value="/usr/bin/readwise",
    )
    def test_success(self, _cli: MagicMock, mock_run: MagicMock) -> None:
        """Returns success when CLI exits with code 0."""
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        success, msg = create_reader_highlight("doc123", "<p>Some text</p>")
        assert success
        assert "created" in msg.lower()

    @patch("rwreader.utils.highlight_manager.subprocess.run")
    @patch(
        "rwreader.utils.highlight_manager.get_cli_path",
        return_value="/usr/bin/readwise",
    )
    def test_failure_returns_stderr(self, _cli: MagicMock, mock_run: MagicMock) -> None:
        """Returns failure when CLI exits with non-zero code."""
        mock_run.return_value = MagicMock(
            returncode=1, stdout="", stderr="Server error"
        )
        success, _msg = create_reader_highlight("doc123", "<p>text</p>")
        assert not success

    @patch("rwreader.utils.highlight_manager.subprocess.run")
    @patch(
        "rwreader.utils.highlight_manager.get_cli_path",
        return_value="/usr/bin/readwise",
    )
    def test_passes_document_id_and_html(
        self, _cli: MagicMock, mock_run: MagicMock
    ) -> None:
        """Verifies the CLI is called with the correct arguments."""
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        create_reader_highlight("mydocid", "<p>highlight me</p>")
        args = mock_run.call_args[0][0]
        assert any("mydocid" in a for a in args)
        assert any("highlight me" in a for a in args)


# ── delete_highlight ──────────────────────────────────────────────────────────


class TestDeleteHighlight:
    """Tests for delete_highlight."""

    @patch("rwreader.utils.highlight_manager.get_cli_path", return_value=None)
    def test_fails_without_cli(self, _mock: MagicMock) -> None:
        """Returns failure when CLI is not available."""
        success, _msg = delete_highlight("abc123")
        assert not success

    @patch("rwreader.utils.highlight_manager.subprocess.run")
    @patch(
        "rwreader.utils.highlight_manager.get_cli_path",
        return_value="/usr/bin/readwise",
    )
    def test_success_with_string_id(self, _cli: MagicMock, mock_run: MagicMock) -> None:
        """Accepts Reader-style string highlight IDs."""
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        success, _ = delete_highlight("01krjrsjt8bq9k7yjyy47tkagn")
        assert success

    @patch("rwreader.utils.highlight_manager.subprocess.run")
    @patch(
        "rwreader.utils.highlight_manager.get_cli_path",
        return_value="/usr/bin/readwise",
    )
    def test_success_with_int_id(self, _cli: MagicMock, mock_run: MagicMock) -> None:
        """Accepts classic Readwise integer highlight IDs."""
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        success, _ = delete_highlight(12345)
        assert success
