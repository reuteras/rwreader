"""Tests for ArticleReaderScreen helper methods."""

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
