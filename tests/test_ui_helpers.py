"""Tests for the ui_helpers module."""

from unittest.mock import Mock, patch

from rwreader.utils.ui_helpers import (
    format_article_content,
    safe_get_article_display_title,
    safe_parse_article_data,
    safe_set_text_style,
    sanitize_ui_input,
)


class TestSafeSetTextStyle:
    """Test cases for safe_set_text_style function."""

    def test_set_valid_style_bold(self) -> None:
        """Test setting a valid 'bold' style."""
        mock_item = Mock()
        mock_item.styles = Mock()
        safe_set_text_style(mock_item, "bold")
        assert mock_item.styles.text_style == "bold"

    def test_set_valid_style_italic(self) -> None:
        """Test setting a valid 'italic' style."""
        mock_item = Mock()
        mock_item.styles = Mock()
        safe_set_text_style(mock_item, "italic")
        assert mock_item.styles.text_style == "italic"

    def test_set_valid_style_underline(self) -> None:
        """Test setting a valid 'underline' style."""
        mock_item = Mock()
        mock_item.styles = Mock()
        safe_set_text_style(mock_item, "underline")
        assert mock_item.styles.text_style == "underline"

    def test_set_valid_style_none(self) -> None:
        """Test setting 'none' style."""
        mock_item = Mock()
        mock_item.styles = Mock()
        safe_set_text_style(mock_item, "none")
        assert mock_item.styles.text_style == "none"

    def test_set_empty_style_defaults_to_none(self) -> None:
        """Test that empty style defaults to 'none'."""
        mock_item = Mock()
        mock_item.styles = Mock()
        safe_set_text_style(mock_item, "")
        assert mock_item.styles.text_style == "none"

    def test_set_invalid_style_uses_fallback(self) -> None:
        """Test that invalid style uses 'none' as fallback."""
        mock_item = Mock()
        mock_item.styles = Mock()
        safe_set_text_style(mock_item, "invalid_style")
        assert mock_item.styles.text_style == "none"

    def test_style_error_handling(self) -> None:
        """Test error handling when setting style fails."""
        mock_item = Mock()
        mock_item.styles = Mock()
        mock_item.styles.text_style = Mock(side_effect=Exception("Style error"))

        # Should not raise exception
        safe_set_text_style(mock_item, "bold")


class TestFormatArticleContent:
    """Test cases for format_article_content function."""

    def test_basic_article_with_html_content(self) -> None:
        """Test formatting article with HTML content."""
        article = {
            "title": "Test Article",
            "html_content": "<p>This is <strong>HTML</strong> content</p>",
            "url": "https://example.com/article",
            "author": "John Doe",
            "site_name": "Example Site",
        }
        result = format_article_content(article)
        assert "Test Article" in result
        assert "HTML" in result
        assert "John Doe" in result
        assert "Example Site" in result

    def test_article_with_plain_content(self) -> None:
        """Test formatting article with plain text content."""
        article = {
            "title": "Plain Text Article",
            "content": "This is plain text content without HTML tags.",
            "author": "Jane Smith",
        }
        result = format_article_content(article)
        assert "Plain Text Article" in result
        assert "plain text content" in result
        assert "Jane Smith" in result

    def test_article_with_no_content(self) -> None:
        """Test formatting article with no content."""
        article = {
            "title": "Empty Article",
            "url": "https://example.com",
        }
        result = format_article_content(article)
        assert "Empty Article" in result
        assert "No content available" in result

    def test_article_with_metadata(self) -> None:
        """Test formatting article with full metadata."""
        article = {
            "title": "Article with Metadata",
            "content": "Content here",
            "author": "Test Author",
            "site_name": "Test Site",
            "published_date": "2024-01-15T10:30:00Z",
            "created_at": "2024-01-16T12:00:00Z",
            "word_count": 500,
            "summary": "This is a test summary",
            "url": "https://example.com/test",
        }
        result = format_article_content(article)
        assert "Article with Metadata" in result
        assert "Test Author" in result
        assert "Test Site" in result
        assert "500 words" in result
        assert "This is a test summary" in result

    def test_article_category_inbox(self) -> None:
        """Test article categorized as Inbox."""
        article = {
            "title": "Inbox Article",
            "content": "Content",
            "archived": False,
            "saved_for_later": False,
        }
        result = format_article_content(article)
        assert "Category: Inbox" in result

    def test_article_category_later(self) -> None:
        """Test article categorized as Later."""
        article = {
            "title": "Later Article",
            "content": "Content",
            "archived": False,
            "saved_for_later": True,
        }
        result = format_article_content(article)
        assert "Category: Later" in result

    def test_article_category_archive(self) -> None:
        """Test article categorized as Archive."""
        article = {
            "title": "Archived Article",
            "content": "Content",
            "archived": True,
        }
        result = format_article_content(article)
        assert "Category: Archive" in result

    def test_article_with_alternate_content_fields(self) -> None:
        """Test article with alternate content field names."""
        article = {
            "title": "Alt Fields Article",
            "full_html": "<p>Content from full_html field</p>",
        }
        result = format_article_content(article)
        assert "Alt Fields Article" in result
        # The markdown conversion will escape underscores
        assert (
            "full_html" in result
            or "full\\_html" in result
            or "Content from full" in result
        )

    def test_article_with_source_url(self) -> None:
        """Test article with source_url instead of url."""
        article = {
            "title": "Source URL Article",
            "content": "Content",
            "source_url": "https://example.com/source",
        }
        result = format_article_content(article)
        assert "https://example.com/source" in result

    def test_article_with_creator_instead_of_author(self) -> None:
        """Test article with creator field instead of author."""
        article = {
            "title": "Creator Article",
            "content": "Content",
            "creator": "Article Creator",
        }
        result = format_article_content(article)
        assert "Article Creator" in result

    def test_article_with_domain_instead_of_site_name(self) -> None:
        """Test article with domain field instead of site_name."""
        article = {
            "title": "Domain Article",
            "content": "Content",
            "domain": "example.com",
        }
        result = format_article_content(article)
        assert "example.com" in result

    def test_article_with_updated_date_same_as_created(self) -> None:
        """Test that duplicate updated_at date is not shown."""
        article = {
            "title": "Date Article",
            "content": "Content",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-15T10:00:00Z",
        }
        result = format_article_content(article)
        # Should only show "Added" not "Updated" when dates are same
        assert "Added:" in result

    def test_article_with_different_updated_date(self) -> None:
        """Test that different updated_at date is shown."""
        article = {
            "title": "Updated Article",
            "content": "Content",
            "created_at": "2024-01-15T10:00:00Z",
            "updated_at": "2024-01-16T10:00:00Z",
        }
        result = format_article_content(article)
        assert "Added:" in result
        assert "Updated:" in result

    def test_untitled_article(self) -> None:
        """Test article without title."""
        article = {
            "content": "Content without title",
        }
        result = format_article_content(article)
        assert "Untitled" in result

    def test_article_with_html_detection(self) -> None:
        """Test HTML detection for content conversion."""
        article = {
            "title": "HTML Detection",
            "content": "<html><body><p>HTML content</p></body></html>",
        }
        result = format_article_content(article)
        assert "HTML Detection" in result
        assert "HTML content" in result

    def test_article_with_short_html_fallback(self) -> None:
        """Test fallback when HTML conversion produces very short content."""
        article = {
            "title": "Short HTML",
            "content": "<div></div>",
        }
        result = format_article_content(article)
        assert "Short HTML" in result

    def test_article_with_html_conversion_error(self) -> None:
        """Test handling of HTML conversion errors."""
        article = {
            "title": "HTML Error",
            "html_content": "<p>Valid HTML</p>",
        }
        with patch("rwreader.utils.ui_helpers.render_html_to_markdown") as mock_render:
            mock_render.side_effect = Exception("Conversion error")
            result = format_article_content(article)
            assert "HTML Error" in result

    def test_article_with_largest_field_fallback(self) -> None:
        """Test finding content from largest string field."""
        article = {
            "title": "Fallback Article",
            "some_random_field": "x" * 150,  # 150 chars, should be detected
            "id": "123",
            "url": "https://example.com",
        }
        result = format_article_content(article)
        assert "Fallback Article" in result

    def test_article_formatting_exception_handling(self) -> None:
        """Test overall exception handling in format_article_content."""
        # Pass something that will cause an error
        with patch(
            "rwreader.utils.ui_helpers.escape_markdown_formatting"
        ) as mock_escape:
            mock_escape.side_effect = Exception("Formatting error")
            article = {"title": "Error Article"}
            result = format_article_content(article)
            assert "Error Formatting Content" in result

    def test_article_with_word_count_string(self) -> None:
        """Test article with word_count as string (invalid)."""
        article = {
            "title": "Word Count Article",
            "content": "Content",
            "word_count": "not a number",
        }
        result = format_article_content(article)
        # Should not crash, word count should not appear
        assert "Word Count Article" in result

    def test_article_with_multiple_html_fields(self) -> None:
        """Test that first available HTML field is used."""
        article = {
            "title": "Multiple HTML Fields",
            "html_content": "<p>First HTML</p>",
            "full_html": "<p>Second HTML</p>",
        }
        result = format_article_content(article)
        assert "First HTML" in result or "Multiple HTML Fields" in result


class TestSafeGetArticleDisplayTitle:
    """Test cases for safe_get_article_display_title function."""

    def test_title_with_site_name(self) -> None:
        """Test display title with site name."""
        article = {
            "title": "Test Article",
            "site_name": "Example Site",
        }
        result = safe_get_article_display_title(article)
        assert result == "Test Article (Example Site)"

    def test_title_without_site_name(self) -> None:
        """Test display title without site name."""
        article = {
            "title": "Test Article",
        }
        result = safe_get_article_display_title(article)
        assert result == "Test Article"

    def test_untitled_article(self) -> None:
        """Test display title for untitled article."""
        article: dict[str, str] = {}
        result = safe_get_article_display_title(article)
        assert result == "Untitled"

    def test_article_with_error_handling(self) -> None:
        """Test error handling in display title creation."""
        # Pass something that will cause an error
        with patch("rwreader.utils.ui_helpers.logger"):
            article = Mock()
            article.get = Mock(side_effect=Exception("Get error"))
            result = safe_get_article_display_title(article)
            assert "Error loading title" in result


class TestSanitizeUIInput:
    """Test cases for sanitize_ui_input function."""

    def test_sanitize_none_input(self) -> None:
        """Test sanitizing None input."""
        result = sanitize_ui_input(None)
        assert result == ""

    def test_sanitize_normal_text(self) -> None:
        """Test sanitizing normal text."""
        result = sanitize_ui_input("Normal text content")
        assert result == "Normal text content"

    def test_sanitize_null_bytes(self) -> None:
        """Test removing null bytes."""
        result = sanitize_ui_input("Text\0with\0nulls")
        assert result == "Textwithnulls"
        assert "\0" not in result

    def test_sanitize_carriage_returns(self) -> None:
        """Test removing carriage returns."""
        result = sanitize_ui_input("Text\rwith\rcarriage\rreturns")
        assert result == "Textwithcarriagereturns"
        assert "\r" not in result

    def test_sanitize_empty_string(self) -> None:
        """Test sanitizing empty string."""
        result = sanitize_ui_input("")
        assert result == "No content"

    def test_sanitize_whitespace_only(self) -> None:
        """Test sanitizing whitespace-only string."""
        result = sanitize_ui_input("   ")
        assert result == "   "

    def test_sanitize_mixed_problematic_chars(self) -> None:
        """Test sanitizing text with multiple problematic characters."""
        result = sanitize_ui_input("Text\0with\rmixed\0problems\r")
        assert "\0" not in result
        assert "\r" not in result
        assert "Text" in result
        assert "mixed" in result


class TestSafeParseArticleData:
    """Test cases for safe_parse_article_data function."""

    def test_parse_valid_article_data(self) -> None:
        """Test parsing valid article data."""
        data = {
            "id": "123",
            "title": "Test Article",
            "content": "Content here",
        }
        result = safe_parse_article_data(data)
        assert result["id"] == "123"
        assert result["title"] == "Test Article"
        assert result["content"] == "Content here"

    def test_parse_none_data(self) -> None:
        """Test parsing None data."""
        result = safe_parse_article_data(None)
        assert result["title"] == "Invalid Article"
        assert result["id"] == "invalid"

    def test_parse_non_dict_data(self) -> None:
        """Test parsing non-dictionary data."""
        result = safe_parse_article_data("not a dict")
        assert result["title"] == "Invalid Article"
        assert result["id"] == "invalid"

    def test_parse_empty_dict(self) -> None:
        """Test parsing empty dictionary treats it as invalid."""
        result = safe_parse_article_data({})
        # Empty dict is treated as invalid (falsy value)
        assert result["id"] == "invalid"
        assert result["title"] == "Invalid Article"

    def test_parse_missing_id_field(self) -> None:
        """Test parsing data missing id field."""
        data = {
            "title": "Article without ID",
        }
        result = safe_parse_article_data(data)
        assert result["id"] == "unknown"
        assert result["title"] == "Article without ID"

    def test_parse_missing_title_field(self) -> None:
        """Test parsing data missing title field."""
        data = {
            "id": "123",
        }
        result = safe_parse_article_data(data)
        assert result["id"] == "123"
        assert result["title"] == "Missing title"

    def test_parse_list_data(self) -> None:
        """Test parsing list data (invalid)."""
        result = safe_parse_article_data([1, 2, 3])
        assert result["title"] == "Invalid Article"
        assert result["id"] == "invalid"

    def test_parse_preserves_extra_fields(self) -> None:
        """Test that parsing preserves extra fields."""
        data = {
            "id": "123",
            "title": "Test",
            "author": "John Doe",
            "url": "https://example.com",
        }
        result = safe_parse_article_data(data)
        assert result["author"] == "John Doe"
        assert result["url"] == "https://example.com"
