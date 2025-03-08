"""UI helper functions for rwreader."""

import logging
from typing import Any

logger: logging.Logger = logging.getLogger(name=__name__)


def safe_set_text_style(item: Any, style: str | None) -> None:
    """Safely set text style for a UI item with validation.

    Args:
        item: UI item to apply the style to
        style: Style to apply (e.g., "bold", "none", "italic")
    """
    # Validate the style before applying
    valid_styles = ["bold", "none", "italic", "underline", "strike", "reverse"]

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


def format_article_content(article: dict[str, Any]) -> str:
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
        for content_field in ["content", "html", "text", "document"]:
            if article.get(content_field):
                content = article[content_field]
                break

        # Get metadata with safe defaults
        url = article.get("url", article.get("source_url", ""))
        author = article.get("author", article.get("creator", ""))
        site_name = article.get("site_name", article.get("domain", ""))
        summary = article.get("summary", "")
        published_date = article.get("published_date", "")
        word_count = article.get("word_count", 0)

        # Determine category
        category = (
            "Archive"
            if article.get("archived", True)
            else ("Later" if article.get("saved_for_later", False) else "Inbox")
        )

        # Format markdown content
        header = f"# {title}\n\n"

        # Add metadata
        metadata = []
        if author:
            metadata.append(f"*By {author}*")
        if site_name:
            metadata.append(f"*From {site_name}*")
        if published_date:
            metadata.append(f"*Published: {published_date}*")
        if word_count and isinstance(word_count, int | float):
            metadata.append(f"*{word_count} words*")
        metadata.append(f"*Category: {category}*")

        if metadata:
            header += " | ".join(metadata) + "\n\n"

        if url:
            header += f"*[Original Article]({url})*\n\n"

        if summary:
            header += f"**Summary**: {summary}\n\n"

        header += "---\n\n"

        # Add placeholder if no content
        if not content:
            content = "*No content available. Try opening the article in browser.*"

        return header + content

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
            and isinstance(reading_progress, int | float)
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
