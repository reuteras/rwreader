"""Tests for the markdown_converter module."""

from rwreader.utils.markdown_converter import (
    extract_links,
    format_timestamp,
    render_html_to_markdown,
)

# Test constants
LINK_COUNT_2 = 2


class TestRenderHTMLToMarkdown:
    """Test cases for render_html_to_markdown function."""

    def test_empty_content(self) -> None:
        """Test rendering empty content."""
        result = render_html_to_markdown("")
        assert "No content available" in result

    def test_none_content(self) -> None:
        """Test rendering None content."""
        result = render_html_to_markdown(None)  # type: ignore
        assert "No content available" in result

    def test_plain_text_without_html(self) -> None:
        """Test rendering plain text without HTML tags."""
        plain_text = "This is plain text without any HTML"
        result = render_html_to_markdown(plain_text)
        assert result == plain_text

    def test_simple_html_conversion(self) -> None:
        """Test converting simple HTML to markdown."""
        html = "<p>Hello <strong>world</strong></p>"
        result = render_html_to_markdown(html)
        assert "Hello" in result
        assert "world" in result

    def test_html_with_paragraph(self) -> None:
        """Test HTML with paragraphs."""
        html = "<p>First paragraph</p><p>Second paragraph</p>"
        result = render_html_to_markdown(html)
        assert "First paragraph" in result
        assert "Second paragraph" in result

    def test_html_with_link(self) -> None:
        """Test HTML with links."""
        html = '<p>Check out <a href="https://example.com">this link</a></p>'
        result = render_html_to_markdown(html)
        assert "this link" in result

    def test_html_with_heading(self) -> None:
        """Test HTML with headings."""
        html = "<h1>Main Title</h1><h2>Subtitle</h2><p>Content</p>"
        result = render_html_to_markdown(html)
        assert "Main Title" in result
        assert "Subtitle" in result

    def test_html_with_list(self) -> None:
        """Test HTML with lists."""
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = render_html_to_markdown(html)
        assert "Item 1" in result
        assert "Item 2" in result

    def test_html_with_image(self) -> None:
        """Test HTML with image replacement."""
        html = '<p>This is an article with an image: <img src="image.jpg" alt="Test image"> and some more text here.</p>'
        result = render_html_to_markdown(html)
        assert "[Image:" in result
        assert "Test image" in result

    def test_html_with_image_no_alt(self) -> None:
        """Test HTML with image without alt text."""
        html = '<img src="image.jpg">'
        result = render_html_to_markdown(html)
        assert "[Image:" in result

    def test_very_short_content_returns_raw_html(self) -> None:
        """Test that very short markdown returns raw HTML."""
        html = "<p>Hi</p>"
        result = render_html_to_markdown(html)
        # Very short content gets wrapped in code block
        assert "```html" in result or "Hi" in result


class TestExtractLinks:
    """Test cases for extract_links function."""

    def test_extract_no_links(self) -> None:
        """Test extracting links from HTML with no links."""
        html = "<p>No links here</p>"
        links = extract_links(html)
        assert links == []

    def test_extract_single_link(self) -> None:
        """Test extracting a single link."""
        html = '<a href="https://example.com">Example</a>'
        links = extract_links(html)
        assert len(links) == 1
        assert links[0] == ("Example", "https://example.com")

    def test_extract_multiple_links(self) -> None:
        """Test extracting multiple links."""
        html = """
        <p><a href="https://example.com">Example</a></p>
        <p><a href="https://test.com">Test</a></p>
        """
        links = extract_links(html)
        assert len(links) == LINK_COUNT_2
        assert any(link[1] == "https://example.com" for link in links)
        assert any(link[1] == "https://test.com" for link in links)

    def test_extract_link_without_text(self) -> None:
        """Test extracting link without text uses URL as text."""
        html = '<a href="https://example.com"></a>'
        links = extract_links(html)
        assert len(links) == 1
        assert links[0] == ("https://example.com", "https://example.com")

    def test_extract_link_with_nested_elements(self) -> None:
        """Test extracting link with nested elements."""
        html = '<a href="https://example.com"><strong>Bold</strong> Link</a>'
        links = extract_links(html)
        assert len(links) == 1
        assert "Link" in links[0][0]

    def test_extract_empty_html(self) -> None:
        """Test extracting from empty HTML."""
        links = extract_links("")
        assert links == []

    def test_extract_none_html(self) -> None:
        """Test extracting from None."""
        links = extract_links(None)  # type: ignore
        assert links == []

    def test_extract_relative_urls(self) -> None:
        """Test extracting relative URLs."""
        html = '<a href="/relative/path">Relative</a>'
        links = extract_links(html)
        assert len(links) == 1
        assert links[0] == ("Relative", "/relative/path")

    def test_extract_duplicate_links(self) -> None:
        """Test that duplicate links are included."""
        html = """
        <a href="https://example.com">First</a>
        <a href="https://example.com">Second</a>
        """
        links = extract_links(html)
        assert len(links) == LINK_COUNT_2
        assert all(link[1] == "https://example.com" for link in links)


class TestFormatTimestamp:
    """Test cases for format_timestamp function."""

    def test_format_valid_timestamp(self) -> None:
        """Test formatting a valid timestamp."""
        timestamp = "2024-01-15T10:30:00Z"
        result = format_timestamp(timestamp)
        assert "2024" in result
        assert "Jan" in result or "01" in result

    def test_format_empty_timestamp(self) -> None:
        """Test formatting empty timestamp."""
        result = format_timestamp("")
        assert result == ""

    def test_format_none_timestamp(self) -> None:
        """Test formatting None timestamp."""
        result = format_timestamp(None)  # type: ignore
        assert result == ""

    def test_format_invalid_timestamp(self) -> None:
        """Test formatting invalid timestamp returns original string."""
        result = format_timestamp("not-a-date")
        assert result == "not-a-date"

    def test_format_different_formats(self) -> None:
        """Test formatting different timestamp formats."""
        timestamps = [
            "2024-01-15T10:30:00Z",
            "2024-01-15T10:30:00",
            "2024-01-15",
        ]
        for ts in timestamps:
            result = format_timestamp(ts)
            # Should at least not crash and return something
            assert result is not None
            assert len(result) > 0
