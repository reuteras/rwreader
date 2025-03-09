"""HTML to Markdown conversion utilities for rwreader."""

import logging
import re
from datetime import datetime

from bs4 import BeautifulSoup
from markdownify import markdownify as md

logger: logging.Logger = logging.getLogger(name=__name__)


def render_html_to_markdown(html_content: str) -> str:
    """Convert HTML to well-formatted markdown with enhanced link handling.

    Args:
        html_content: HTML content to convert

    Returns:
        Formatted markdown content
    """
    if not html_content:
        return "*No content available. Try opening the article in browser.*"

    try:
        # Parse HTML with BeautifulSoup
        soup = BeautifulSoup(markup=html_content, features="html.parser")

        # Replace images with text descriptions
        for img in soup.find_all(name="img"):
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
                    pre.replace_with(soup.new_string(f"```{language}\n{code_content}\n```"))

        # Convert to markdown using markdownify
        markdown_text = md(str(soup))

        # Clean up the markdown
        markdown_text = _clean_markdown(markdown_text)

        return markdown_text
    except Exception as e:
        logger.error(f"Error converting HTML to markdown: {e}")
        return f"*Error rendering content: {e}*"


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
    markdown_text = re.sub(r'```\s+([a-zA-Z0-9]+)\s*\n', r'```\1\n', markdown_text)

    # Ensure there are blank lines before and after headings
    markdown_text = re.sub(r'([^\n])\n(#{1,6} )', r'\1\n\n\2', markdown_text)
    markdown_text = re.sub(r'(#{1,6} .*)\n([^\n])', r'\1\n\n\2', markdown_text)

    # Ensure proper spacing around lists
    markdown_text = re.sub(r'([^\n])\n(- |\* |[0-9]+\. )', r'\1\n\n\2', markdown_text)

    # Ensure proper spacing around code blocks
    markdown_text = re.sub(r'([^\n])\n```', r'\1\n\n```', markdown_text)
    markdown_text = re.sub(r'```\n([^\n])', r'```\n\n\1', markdown_text)

    # Remove some xmlns attributes that might be present
    markdown_text = re.sub(r'xml encoding="UTF-8"', "", markdown_text, flags=re.IGNORECASE)

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
        is_html = bool(re.search(r'<[a-z][^>]*>', content, re.IGNORECASE))
        
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
            md_links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', content)
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
    text = re.sub(r'\[([^\]]*)\]', r'\\[\1]', text)
    
    # Escape other markdown formatting characters
    chars_to_escape = ['*', '_', '`', '#']
    for char in chars_to_escape:
        text = text.replace(char, f'\\{char}')
        
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
            timestamp_int = int(float(timestamp_str))
            # Convert from seconds to datetime
            dt = datetime.fromtimestamp(timestamp_int)
        else:
            # Try to parse as ISO format
            dt = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            
        # Format based on locale
        return dt.strftime("%c")
    except Exception as e:
        logger.error(f"Error formatting timestamp '{timestamp}': {e}")
        return str(timestamp) if timestamp else ""  # Return original if parsing fails