"""UI helper functions for rwreader."""

import logging
import re
from typing import Any, Literal

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
    valid_styles: list[str] = [
        "bold",
        "none",
        "italic",
        "underline",
        "strike",
        "reverse",
    ]

    # If style is None or empty, use "none" as default
    if not style:
        style = "none"

    # Only apply if it's a valid style
    if style in valid_styles:
        try:
            item.styles.text_style = style
        except Exception as e:
            logger.error(msg=f"Error setting text style '{style}': {e}")
    else:
        logger.warning(msg=f"Attempted to apply invalid text style: '{style}'")
        # Apply default as fallback
        try:
            item.styles.text_style = "none"
        except Exception as e:
            logger.error(msg=f"Error setting fallback text style: {e}")


def format_article_content(article: dict[str, Any]) -> str:  # noqa: PLR0912, PLR0915
    """Format article data into markdown content with enhanced error handling and fallbacks.

    Args:
        article: The article data dictionary

    Returns:
        Formatted markdown content
    """
    try:
        # Extract article details with safe defaults
        title: str = article.get("title", "Untitled")
        content: str = ""

        # Try different possible content fields with added debugging
        html_content: str | None = None
        content_field_used: str | None = None

        # Define all possible content field names
        html_content_fields: list[str] = [
            "html_content",
            "full_html",
            "html",
            "fullHtml",
            "webContent",
        ]
        plain_content_fields: list[str] = [
            "content",
            "text",
            "full_text",
            "article_text",
            "document",
            "body",
            "articleContent",
            "fullText",
        ]

        # Try to find HTML content first (higher quality)
        for field in html_content_fields:
            if (
                article.get(field)
                and isinstance(article[field], str)
                and len(article[field]) > 0
            ):
                html_content = article[field]
                content_field_used = field
                break

        # If no HTML content found, try plain content fields
        if not html_content:
            for field in plain_content_fields:
                if (
                    article.get(field)
                    and isinstance(article[field], str)
                    and len(article[field]) > 0
                ):
                    content = article[field]
                    content_field_used = field
                    break

        # If still no content found, try any field that might contain text
        if not html_content and not content:
            # Find the largest string field that might contain content
            largest_field: str | None = None
            largest_size = 0
            for field, value in article.items():
                if isinstance(value, str) and len(value) > 100:  # noqa: PLR2004
                    if field not in ["id", "title", "url", "author", "site_name"]:
                        if len(value) > largest_size:
                            largest_size: int = len(value)
                            largest_field = field

            if largest_field:
                content = article[largest_field]
                content_field_used = largest_field

        # Last resort: check for raw attribute text
        if not html_content and not content and hasattr(article, "__dict__"):
            for attr_name, attr_value in article.__dict__.items():
                if isinstance(attr_value, str) and len(attr_value) > 100:  # noqa: PLR2004
                    if attr_name not in ["id", "title", "url", "author", "site_name"]:
                        content = attr_value
                        content_field_used = f"__dict__.{attr_name}"
                        break

        # If no content found, log a clear warning
        if not html_content and not content:
            logger.warning("NO CONTENT FOUND IN ARTICLE - All content fields are empty")

        # Use html_content if available, otherwise use content
        raw_content = html_content if html_content else content

        # Get metadata with safe defaults
        url: str = article.get("url", article.get("source_url", ""))
        author: str = article.get("author", article.get("creator", ""))
        site_name: str = article.get("site_name", article.get("domain", ""))
        summary: str = article.get("summary", "")
        published_date: str = format_timestamp(article.get("published_date", ""))
        created_at: str = format_timestamp(article.get("created_at", ""))
        updated_at: str = format_timestamp(article.get("updated_at", ""))
        word_count: str | int = article.get("word_count", 0)

        # Determine category
        category: Literal["Archive"] | Literal["Later"] | Literal["Inbox"] = (
            "Archive"
            if article.get("archived", True)
            else ("Later" if article.get("saved_for_later", False) else "Inbox")
        )

        # Format markdown content
        header: str = f"# {escape_markdown_formatting(text=title)}\n\n"

        # Add metadata
        metadata: list[str] = []
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
        if word_count and isinstance(word_count, int | float):
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
        content_markdown: str = ""
        if raw_content:
            # Look for common HTML indicators
            is_html = False
            if isinstance(raw_content, str):
                lower_content: str = raw_content.lower()
                if (
                    "<html" in lower_content
                    or "<body" in lower_content
                    or "<div" in lower_content
                    or "<p>" in lower_content
                    or content_field_used in ["html_content", "full_html"]
                    or raw_content.strip().startswith("<")
                ):
                    is_html = True

            if is_html:
                # Convert HTML to markdown
                try:
                    content_markdown = render_html_to_markdown(html_content=raw_content)

                    # Check if the content actually contains real text
                    text_content: str = re.sub(
                        pattern=r"[\s\n\r\t]+", repl=" ", string=content_markdown
                    ).strip()
                    if len(text_content) < 10:  # noqa: PLR2004
                        # Try again treating as plain text
                        content_markdown = raw_content
                        logger.debug(msg="Falling back to raw content as plain text")
                except Exception as e:
                    logger.error(msg=f"Error converting HTML to markdown: {e}")
                    # Use raw content as fallback
                    content_markdown = raw_content
                    logger.debug(msg="Using raw content after HTML conversion error")
            else:
                # Use raw content as is
                content_markdown = raw_content
                logger.debug(
                    msg=f"Using raw content as plain text, size: {len(content_markdown)}"
                )

            # Final check - if content is still empty or too short, show an error
            if not content_markdown or len(content_markdown.strip()) < 10:  # noqa: PLR2004
                logger.warning(msg=f"Final content too short: '{content_markdown}'")
                content_markdown = (
                    "*The article content appears to be empty or could not be properly retrieved.*\n\n"
                    + "This might be due to:\n"
                    + "* Readwise API limitations\n"
                    + "* Content protection on the original site\n"
                    + "* An error in content processing\n\n"
                    + "Try opening the article in your browser instead."
                )
        else:
            content_markdown = (
                "*No content available. Try opening the article in browser.*"
            )

        return header + content_markdown

    except Exception as e:
        logger.error(msg=f"Error formatting article content: {e}", exc_info=True)
        return "# Error Formatting Content\n\nThere was an error preparing the article content. Please try again."


def safe_get_article_display_title(article: dict[str, Any]) -> str:
    """Safely create a display title for an article with proper error handling.

    Args:
        article: The article data dictionary

    Returns:
        Formatted display title
    """
    try:
        title: str = article.get("title", "Untitled")
        site_name: str = article.get("site_name", "")
        reading_progress: str | int = article.get("reading_progress", 0)
        is_read: bool = article.get("read", False) or article.get("state") == "finished"

        # Format the title with metadata
        display_title: str = title

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
        logger.error(msg=f"Error creating display title: {e}")
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
    replacements: list[tuple[str, str]] = [
        ("\0", ""),  # Null bytes
        ("\r", ""),  # Carriage returns
        ("", ""),  # Empty string - handled by default return
    ]

    result: str = text
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
        logger.warning(msg=f"Received invalid article data: {type(data)}")
        return {"title": "Invalid Article", "id": "invalid"}

    # Ensure required fields exist
    required_fields: list[str] = ["id", "title"]
    for field in required_fields:
        if field not in data:
            data[field] = f"Missing {field}" if field != "id" else "unknown"

    return data
