"""UI helper functions for rwreader."""

import logging
from typing import Any

from ..utils.markdown_converter import (
    escape_markdown_formatting,
    format_timestamp,
    render_html_to_markdown,
)

logger: logging.Logger = logging.getLogger(name=__name__)


def safe_set_text_style(item: Any, style: str) -> None:
    """Safely set text style for a UI item with validation.

    Args:
        item: UI item to apply the style to
        style: Style to apply (e.g., "bold", "none", "italic")
    """
    # Validate the style before applying
    valid_styles: list[str] = ["bold", "none", "italic", "underline", "strike", "reverse"]

    # If style is None or empty, use "none" as default
    if not style:
        style = "none"

    # Only apply if it's a valid style
    if style in valid_styles:
        try:
            item.styles.text_style = style
        except Exception as e:
            logger.error(f"Error setting text style '{style}': {e}")
    else:
        logger.warning(f"Attempted to apply invalid text style: '{style}'")
        # Apply default as fallback
        try:
            item.styles.text_style = "none"
        except Exception as e:
            logger.error(f"Error setting fallback text style: {e}")


def format_article_content(article: dict[str, Any]) -> str:  # noqa: PLR0912, PLR0915
    """Format article data into markdown content with error checking.

    Args:
        article: The article data dictionary

    Returns:
        Formatted markdown content
    """
    try:
        # Extract article details with safe defaults
        title = article.get("title", "Untitled")
        content = ""

        # Try different possible content fields
        html_content = None
        for content_field in ["html_content", "content", "html", "text", "document"]:
            if article.get(content_field):
                if content_field == "html_content":
                    html_content = article[content_field]
                    break
                content = article[content_field]
                break

        # Use html_content if available, otherwise use content
        raw_content = html_content if html_content else content

        # Get metadata with safe defaults
        url = article.get("url", article.get("source_url", ""))
        author = article.get("author", article.get("creator", ""))
        site_name = article.get("site_name", article.get("domain", ""))
        summary = article.get("summary", "")
        published_date = format_timestamp(article.get("published_date", ""))
        created_at = format_timestamp(article.get("created_at", ""))
        updated_at = format_timestamp(article.get("updated_at", ""))
        word_count = article.get("word_count", 0)

        # Determine category
        category = (
            "Archive"
            if article.get("archived", True)
            else ("Later" if article.get("saved_for_later", False) else "Inbox")
        )

        # Format markdown content
        header = f"# {escape_markdown_formatting(title)}\n\n"

        # Add metadata
        metadata = []
        if author:
            metadata.append(f"*By {escape_markdown_formatting(author)}*")
        if site_name:
            metadata.append(f"*From {escape_markdown_formatting(site_name)}*")
        if published_date:
            metadata.append(f"*Published: {published_date}*")
        if created_at:
            metadata.append(f"*Added: {created_at}*")
        if updated_at and updated_at != created_at:
            metadata.append(f"*Updated: {updated_at}*")
        if word_count and isinstance(word_count, (int | float)):
            metadata.append(f"*{word_count} words*")
        metadata.append(f"*Category: {category}*")

        if metadata:
            header += " | ".join(metadata) + "\n\n"

        if url:
            header += f"*[Original Article]({url})*\n\n"

        if summary:
            header += f"**Summary**: {escape_markdown_formatting(summary)}\n\n"

        header += "---\n\n"

        # Convert HTML to markdown if content is in HTML format
        if raw_content:
            # Check if content looks like HTML
            if isinstance(raw_content, str) and ("<html" in raw_content.lower() or "<body" in raw_content.lower() or "<div" in raw_content.lower()):
                content_markdown = render_html_to_markdown(raw_content)
            else:
                content_markdown = raw_content
        else:
            content_markdown = "*No content available. Try opening the article in browser.*"

        return header + content_markdown

    except Exception as e:
        logger.error(f"Error formatting article content: {e}")
        return "# Error Formatting Content\n\nThere was an error preparing the article content. Please try again."


def safe_get_article_display_title(article: dict[str, Any]) -> str:
    """Safely create a display title for an article with proper error handling.

    Args:
        article: The article data dictionary

    Returns:
        Formatted display title
    """
    try:
        title = article.get("title", "Untitled")
        site_name = article.get("site_name", "")
        reading_progress = article.get("reading_progress", 0)
        is_read = article.get("read", False) or article.get("state") == "finished"

        # Format the title with metadata
        display_title = title

        if site_name:
            display_title += f" ({site_name})"

        # Add reading progress or read status
        if (
            reading_progress
            and isinstance(reading_progress, (int | float))
            and 0 < reading_progress < 100  # noqa: PLR2004
        ):
            display_title += f" - {reading_progress}%"
        elif is_read:
            display_title += " - Read"

        return display_title
    except Exception as e:
        logger.error(f"Error creating display title: {e}")
        return "Article (Error loading title)"


def sanitize_ui_input(text: str | None) -> str:
    """Sanitize input for UI components.

    Args:
        text: Text to sanitize

    Returns:
        Sanitized text safe for UI display
    """
    if text is None:
        return ""

    # Replace any problematic characters or sequences
    replacements = [
        ("\0", ""),  # Null bytes
        ("\r", ""),  # Carriage returns
        ("", ""),  # Empty string - handled by default return
    ]

    result = text
    for old, new in replacements:
        result = result.replace(old, new)

    return result if result else "No content"


def safe_parse_article_data(data: Any) -> dict[str, Any]:
    """Safely parse and validate article data.

    Args:
        data: Article data to parse

    Returns:
        Validated article dictionary
    """
    if not data or not isinstance(data, dict):
        logger.warning(f"Received invalid article data: {type(data)}")
        return {"title": "Invalid Article", "id": "invalid"}

    # Ensure required fields exist
    required_fields = ["id", "title"]
    for field in required_fields:
        if field not in data:
            data[field] = f"Missing {field}" if field != "id" else "unknown"

    return data