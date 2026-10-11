"""Tests for ArticleReaderScreen helper methods."""

from unittest.mock import Mock, patch

import pytest
from textual.app import App

from rwreader.ui.screens.article_reader import ArticleReaderScreen

_TWO_PARAGRAPHS = 2


class TestParseParagraphs:
    """Tests for ArticleReaderScreen._parse_paragraphs (static method)."""

    def test_empty_markdown(self) -> None:
        """Empty input returns an empty list."""
        assert ArticleReaderScreen._parse_paragraphs("") == []

    def test_basic_paragraphs(self) -> None:
        """Two long-enough paragraphs are both returned."""
        md = (
            "First paragraph that is long enough to be included here.\n\n"
            "Second paragraph that is also long enough to be included."
        )
        result = ArticleReaderScreen._parse_paragraphs(md)
        assert len(result) == _TWO_PARAGRAPHS
        assert "First paragraph" in result[0]
        assert "Second paragraph" in result[1]

    def test_skips_headings(self) -> None:
        """Heading blocks are excluded."""
        md = (
            "# Heading One\n\n"
            "## Heading Two\n\n"
            "Actual content paragraph long enough to be included here."
        )
        result = ArticleReaderScreen._parse_paragraphs(md)
        assert len(result) == 1
        assert "Actual content" in result[0]

    def test_skips_code_fences(self) -> None:
        """Code fences are excluded."""
        md = (
            "Normal text that is long enough to be included in results.\n\n"
            "```python\nx = 1\n```"
        )
        result = ArticleReaderScreen._parse_paragraphs(md)
        assert len(result) == 1
        assert "Normal text" in result[0]

    def test_skips_horizontal_rules(self) -> None:
        """Horizontal rules are excluded."""
        md = "---\n\nParagraph content that is long enough to be included here.\n"
        result = ArticleReaderScreen._parse_paragraphs(md)
        assert len(result) == 1
        assert "Paragraph content" in result[0]

    def test_skips_blockquotes(self) -> None:
        """Blockquote blocks are excluded (they represent existing highlights)."""
        md = (
            "> Quoted text that would otherwise be long enough to count.\n\n"
            "Normal paragraph that is long enough to be included here."
        )
        result = ArticleReaderScreen._parse_paragraphs(md)
        assert len(result) == 1
        assert "Normal paragraph" in result[0]

    def test_skips_short_blocks(self) -> None:
        """Blocks shorter than the minimum length are excluded."""
        md = "Short.\n\nThis paragraph is definitely long enough to be included in results."
        result = ArticleReaderScreen._parse_paragraphs(md)
        assert len(result) == 1
        assert "long enough" in result[0]

    def test_skips_tables(self) -> None:
        """Table rows (starting with |) are excluded."""
        md = "| Col1 | Col2 |\n|------|------|\n| a    | b    |\n\nReal paragraph content long enough here."
        result = ArticleReaderScreen._parse_paragraphs(md)
        assert all("Col1" not in p for p in result)

    def test_multiline_paragraph_preserved(self) -> None:
        """A paragraph spanning multiple lines is returned as one block."""
        md = "Line one of the paragraph.\nLine two of the paragraph.\nLine three.\n"
        result = ArticleReaderScreen._parse_paragraphs(md)
        assert len(result) == 1
        assert "Line one" in result[0]
        assert "Line two" in result[0]


class _HostApp(App[None]):
    """Minimal app used to host ArticleReaderScreen under test."""

    def __init__(self, client: Mock) -> None:
        super().__init__()
        self.client = client


class TestSeenState:
    """Opening marks an article seen; U toggles it."""

    @pytest.mark.asyncio
    async def test_open_marks_seen_and_toggle_marks_unread(self) -> None:
        """Loading an unopened article marks it read; U marks it unread again."""
        listed = {"id": "a1", "title": "One", "first_opened_at": ""}
        client = Mock()
        client.get_article.return_value = {
            "id": "a1",
            "title": "One",
            "content": "Body text",
            "first_opened_at": "",
        }
        client.mark_seen.return_value = True
        app = _HostApp(client)
        with patch(
            "rwreader.ui.screens.article_reader.is_readwise_cli_available",
            return_value=False,
        ):
            async with app.run_test() as pilot:
                screen = ArticleReaderScreen(
                    article=listed,
                    article_list=[listed],
                    current_index=0,
                    category="archive",
                )
                app.push_screen(screen)
                await pilot.pause()
                await app.workers.wait_for_complete()
                await pilot.pause()
                client.mark_seen.assert_called_once_with(article_id="a1", seen=True)
                assert listed["first_opened_at"]
                assert screen.article["first_opened_at"]

                await pilot.press("U")
                await pilot.pause()
                client.mark_seen.assert_called_with(article_id="a1", seen=False)
                assert listed["first_opened_at"] == ""

    @pytest.mark.asyncio
    async def test_already_opened_article_is_not_marked(self) -> None:
        """An article that was opened before triggers no API call."""
        listed = {"id": "a1", "title": "One", "first_opened_at": "2026-01-01"}
        client = Mock()
        client.get_article.return_value = dict(listed, content="Body text")
        app = _HostApp(client)
        with patch(
            "rwreader.ui.screens.article_reader.is_readwise_cli_available",
            return_value=False,
        ):
            async with app.run_test() as pilot:
                app.push_screen(
                    ArticleReaderScreen(
                        article=listed,
                        article_list=[listed],
                        current_index=0,
                        category="archive",
                    )
                )
                await pilot.pause()
                await app.workers.wait_for_complete()
                await pilot.pause()
                client.mark_seen.assert_not_called()
