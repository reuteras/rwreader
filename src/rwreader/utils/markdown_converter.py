"""HTML to Markdown conversion utilities for rwreader."""

import logging
import re
from datetime import datetime
from http import HTTPStatus

from bs4 import BeautifulSoup
from markdownify import markdownify as md

logger: logging.Logger = logging.getLogger(name=__name__)


def render_html_to_markdown(html_content: str) -> str:  # noqa: PLR0911, PLR0912, PLR0915
    """Convert HTML to well-formatted markdown with enhanced fallbacks.

    Args:
        html_content: HTML content to convert

    Returns:
        Formatted markdown content
    """
    if not html_content:
        return "*No content available. Try opening the article in browser.*"

    try:
        # Add some debug logging to help diagnose issues
        logger.debug(
            f"Converting HTML to markdown, content length: {len(html_content)}"
        )
        if len(html_content) > HTTPStatus.OK:
            logger.debug(f"HTML content preview: {html_content[:200]}...")
        else:
            logger.debug(f"HTML content: {html_content}")

        # First, try a very simple check for HTML tags in the content
        if not re.search(r"<[a-z]+[^>]*>", html_content, re.IGNORECASE):
            logger.debug(
                "Content doesn't appear to have HTML tags, using as plain text"
            )
            return html_content

        # Parse HTML with BeautifulSoup - use html.parser which is more forgiving
        soup = BeautifulSoup(markup=html_content, features="html.parser")

        # Replace images with text descriptions
        for img in soup.find_all("img"):
            if img.get("src"):
                # Create a text placeholder for images
                img_alt = img.get("alt", "No description")
                img_placeholder = f"[Image: {img_alt}]"
                img.replace_with(soup.new_string(img_placeholder))

        # Clean up code blocks for proper rendering
        for pre in soup.find_all("pre"):
            # Extract the code language if available
            code_tag = pre.find("code")
            if code_tag and code_tag.get("class"):
                classes = code_tag.get("class")
                language = ""
                if classes:
                    for cls in classes:
                        if cls.startswith("language-"):
                            language = cls.replace("language-", "")
                            break

                if language:
                    # Mark the code block with language
                    code_content = code_tag.get_text()
                    pre.replace_with(
                        soup.new_string(f"```{language}\n{code_content}\n```")
                    )

        # Convert to markdown using markdownify
        # Fallback to simple string extraction if markdownify fails
        try:
            markdown_text = md(str(soup))
        except Exception as conv_error:
            logger.error(
                f"Markdownify error: {conv_error}, falling back to basic text extraction"
            )

            # Try to extract text from the soup object
            try:
                markdown_text = soup.get_text(separator="\n\n")
            except Exception as soup_error:
                logger.error(
                    f"Soup.get_text error: {soup_error}, using raw content as fallback"
                )
                markdown_text = html_content

            # If markdown_text is still empty or too short, try direct raw content
            if len(markdown_text.strip()) < 20:  # noqa: PLR2004
                logger.debug("Extracted text too short, using raw content")
                markdown_text = html_content

        # Clean up the markdown
        markdown_text = _clean_markdown(markdown_text)

        # Log the result size
        logger.debug(f"Converted markdown size: {len(markdown_text)}")
        if len(markdown_text) > 200:  # noqa: PLR2004
            logger.debug(f"Markdown preview: {markdown_text[:200]}...")

        # Final check - if markdown is too short, return the raw HTML
        if len(markdown_text.strip()) < 20:  # noqa: PLR2004
            logger.warning(
                f"Final markdown too short '{markdown_text}', using raw HTML"
            )
            # Return the raw HTML as is - it might be useful to see
            return f"```html\n{html_content}\n```"

        return markdown_text

    except Exception as e:
        logger.error(f"Error converting HTML to markdown: {e}", exc_info=True)
        # Try a very basic fallback if BeautifulSoup fails
        try:
            # First attempt: Just remove HTML tags with regex and return as plain text
            text = re.sub(r"<[^>]+>", " ", html_content)
            text = re.sub(r"\s+", " ", text).strip()

            # If the text is too short after removing tags, show raw HTML
            if len(text) < 50:  # noqa: PLR2004
                return f"*Error rendering HTML content properly. Raw HTML shown below:*\n\n```html\n{html_content}\n```"
            else:
                return f"*Error rendering content: {e}*\n\n{text}"
        except:
            # Ultimate fallback: show the raw HTML
            return f"*Error processing content. Raw HTML shown below:*\n\n```html\n{html_content}\n```"


def _clean_markdown(markdown_text: str) -> str:
    """Clean up markdown text for better readability.

    Args:
        markdown_text: Raw markdown text

    Returns:
        Cleaned markdown text
    """
    # Replace multiple consecutive blank lines with a single one
    markdown_text = re.sub(r"\n{3,}", "\n\n", markdown_text)

    # Fix code blocks that might have been malformed
    markdown_text = re.sub(r"```\s+([a-zA-Z0-9]+)\s*\n", r"```\1\n", markdown_text)

    # Ensure there are blank lines before and after headings
    markdown_text = re.sub(r"([^\n])\n(#{1,6} )", r"\1\n\n\2", markdown_text)
    markdown_text = re.sub(r"(#{1,6} .*)\n([^\n])", r"\1\n\n\2", markdown_text)

    # Ensure proper spacing around lists
    markdown_text = re.sub(r"([^\n])\n(- |\* |[0-9]+\. )", r"\1\n\n\2", markdown_text)

    # Ensure proper spacing around code blocks
    markdown_text = re.sub(r"([^\n])\n```", r"\1\n\n```", markdown_text)
    markdown_text = re.sub(r"```\n([^\n])", r"```\n\n\1", markdown_text)

    # Remove some xmlns attributes that might be present
    markdown_text = re.sub(
        r'xml encoding="UTF-8"', "", markdown_text, flags=re.IGNORECASE
    )

    return markdown_text


def extract_links(content: str) -> list[tuple[str, str]]:
    """Extract links from HTML or markdown content.

    Args:
        content: HTML or markdown content

    Returns:
        List of tuples with link title and URL
    """
    links = []
    if not content:
        return links

    try:
        # Determine if content is HTML (look for HTML tags)
        is_html = bool(re.search(r"<[a-z][^>]*>", content, re.IGNORECASE))

        # Parse with BeautifulSoup
        soup = BeautifulSoup(markup=content, features="html.parser")

        # Find all links
        for link in soup.find_all("a"):
            try:
                href = link.get("href", "")
                if href:
                    text = link.get_text().strip()
                    if not text:
                        text = href
                    links.append((text, href))
            except Exception as e:
                logger.debug(f"Error processing link: {e}")

        # If no links found and not HTML, try to extract markdown links
        if not links and not is_html:
            # Extract markdown links with regex: [text](url)
            md_links = re.findall(r"\[([^\]]+)\]\(([^)]+)\)", content)
            links.extend(md_links)

        return links
    except Exception as e:
        logger.error(f"Error extracting links: {e}")
        return links


def escape_markdown_formatting(text: str) -> str:
    """Escape special markdown formatting characters in text.

    Args:
        text: Text to escape

    Returns:
        Escaped text
    """
    if not text:
        return ""

    # Escape square brackets that might be interpreted as markup
    text = re.sub(r"\[([^\]]*)\]", r"\\[\1]", text)

    # Escape other markdown formatting characters
    chars_to_escape = ["*", "_", "`", "#"]
    for char in chars_to_escape:
        text = text.replace(char, f"\\{char}")

    return text


def format_timestamp(timestamp: str | int | float | None) -> str:
    """Convert timestamp to a human-readable format using the current locale.

    Args:
        timestamp: Timestamp string, int, or float (ISO format or unix timestamp)

    Returns:
        Formatted date string
    """
    if timestamp is None:
        return ""

    try:
        # Convert to string if it's not already
        timestamp_str = str(timestamp)

        # Check if timestamp is a unix timestamp (numeric string)
        if timestamp_str.isdigit() or isinstance(timestamp, (int | float)):
            timestamp_val = float(timestamp_str)

            # Check if timestamp is in milliseconds (13 digits) and convert to seconds if needed
            if (
                timestamp_val > 10000000000  # noqa: PLR2004
            ):  # Timestamps in milliseconds are typically > 10^12
                timestamp_val = timestamp_val / 1000

            # Convert from seconds to datetime
            dt = datetime.fromtimestamp(timestamp_val)
        else:
            # Try to parse as ISO format
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Format based on locale
        return dt.strftime("%c")
    except Exception as e:
        logger.error(f"Error formatting timestamp '{timestamp}': {e}")
        return str(timestamp) if timestamp else ""  # Return original if parsing fails
