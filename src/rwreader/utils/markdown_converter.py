"""HTML to Markdown conversion utilities for rwreader."""

import logging
import re
from datetime import datetime
from http import HTTPStatus
from urllib.parse import quote, urlparse

import httpx
from bs4 import BeautifulSoup
from markdownify import markdownify as md

logger: logging.Logger = logging.getLogger(name=__name__)


def render_html_to_markdown(html_content: str) -> str:  # noqa: PLR0911, PLR0912
    """Convert HTML to well-formatted markdown with enhanced fallbacks.

    Args:
        html_content: HTML content to convert

    Returns:
        Formatted markdown content
    """
    if not html_content:
        return "*No content available. Try opening the article in browser.*"

    try:
        if len(html_content) > HTTPStatus.OK:
            logger.debug(msg=f"HTML content preview: {html_content[:200]}...")
        else:
            logger.debug(msg=f"HTML content: {html_content}")

        # First, try a very simple check for HTML tags in the content
        if not re.search(
            pattern=r"<[a-z]+[^>]*>", string=html_content, flags=re.IGNORECASE
        ):
            logger.debug(
                msg="Content doesn't appear to have HTML tags, using as plain text"
            )
            return html_content

        # Parse HTML with BeautifulSoup - use html.parser which is more forgiving
        soup = BeautifulSoup(markup=html_content, features="html.parser")

        # Replace images with text descriptions
        for img in soup.find_all(name="img"):
            if img.get("src"):  # type: ignore
                # Create a text placeholder for images
                img_alt = img.get("alt", "No description")  # type: ignore
                img_placeholder: str = f"[Image: {img_alt}]"
                img.replace_with(soup.new_string(img_placeholder))

        # Clean up code blocks for proper rendering
        for pre in soup.find_all(name="pre"):
            # Extract the code language if available
            code_tag: str = pre.find("code")  # type: ignore
            if code_tag and code_tag.get("class"):  # type: ignore
                classes: str = code_tag.get("class")  # type: ignore
                language = ""
                if classes:
                    for cls in classes:
                        if cls.startswith("language-"):
                            language: str = cls.replace("language-", "")
                            break

                if language:
                    # Mark the code block with language
                    code_content: str = code_tag.get_text()  # type: ignore
                    pre.replace_with(
                        soup.new_string(s=f"```{language}\n{code_content}\n```")
                    )

        # Convert to markdown using markdownify
        # Fallback to simple string extraction if markdownify fails
        try:
            markdown_text = md(html=str(object=soup))
        except Exception as conv_error:
            logger.error(
                msg=f"Markdownify error: {conv_error}, falling back to basic text extraction"
            )

            # Try to extract text from the soup object
            try:
                markdown_text = soup.get_text(separator="\n\n")
            except Exception as soup_error:
                logger.error(
                    msg=f"Soup.get_text error: {soup_error}, using raw content as fallback"
                )
                markdown_text = html_content

            # If markdown_text is still empty or too short, try direct raw content
            if len(markdown_text.strip()) < 20:  # noqa: PLR2004
                markdown_text: str = html_content

        # Clean up the markdown
        markdown_text = _clean_markdown(markdown_text=markdown_text)

        # Final check - if markdown is too short, return the raw HTML
        if len(markdown_text.strip()) < 20:  # noqa: PLR2004
            # Return the raw HTML as is - it might be useful to see
            return f"```html\n{html_content}\n```"

        return markdown_text

    except Exception as e:
        logger.error(msg=f"Error converting HTML to markdown: {e}", exc_info=True)
        # Try a very basic fallback if BeautifulSoup fails
        try:
            # First attempt: Just remove HTML tags with regex and return as plain text
            text: str = re.sub(pattern=r"<[^>]+>", repl=" ", string=html_content)
            text = re.sub(pattern=r"\s+", repl=" ", string=text).strip()

            # If the text is too short after removing tags, show raw HTML
            if len(text) < 50:  # noqa: PLR2004
                return f"*Error rendering HTML content properly. Raw HTML shown below:*\n\n```html\n{html_content}\n```"
            else:
                return f"*Error rendering content: {e}*\n\n{text}"
        except:  # noqa E722
            # Ultimate fallback: show the raw HTML
            return f"*Error processing content. Raw HTML shown below:*\n\n```html\n{html_content}\n```"


def _remove_anchor_links(markdown_text: str) -> str:
    """Remove anchor links that point to headings (e.g., [#](https://example.com#heading)).

    These links are not useful in a TUI context as they typically link to headings
    within the same article.

    Args:
        markdown_text: Markdown text that may contain anchor links

    Returns:
        Markdown text with anchor links removed
    """
    # Match patterns like [#](url#heading) or [^](url#heading) etc.
    # Remove the entire link syntax, leaving just the text if it's not just a symbol
    markdown_text = re.sub(
        pattern=r"\[([#^\s*])\]\([^)]*#[^)]*\)",
        repl="",
        string=markdown_text,
    )
    return markdown_text


def _convert_underline_headers_to_hash(markdown_text: str) -> str:
    """Convert underline-style headers (====, ----) to hash-style headers (#, ##).

    This converts headers like:
        Title
        =====
    to:
        ## Title

    And headers like:
        Subtitle
        --------
    to:
        ### Subtitle

    Args:
        markdown_text: Markdown text that may contain underline-style headers

    Returns:
        Markdown text with hash-style headers
    """
    lines = markdown_text.split("\n")
    result = []
    i = 0

    while i < len(lines):
        if i + 1 < len(lines):
            current_line = lines[i].rstrip()
            next_line = lines[i + 1].rstrip()

            # Check if next line is a header underline
            if current_line and next_line:
                # Check for "====" pattern (level 2 header / ##)
                if re.match(pattern=r"^=+$", string=next_line):
                    result.append(f"## {current_line}")
                    i += 2
                    continue
                # Check for "----" pattern (level 3 header / ###)
                elif re.match(pattern=r"^-+$", string=next_line):
                    result.append(f"### {current_line}")
                    i += 2
                    continue

        result.append(lines[i])
        i += 1

    return "\n".join(result)


def _clean_markdown(markdown_text: str) -> str:
    """Clean up markdown text for better readability.

    Args:
        markdown_text: Raw markdown text

    Returns:
        Cleaned markdown text
    """
    # Remove anchor links to headings
    markdown_text = _remove_anchor_links(markdown_text=markdown_text)

    # Convert underline-style headers to hash-style headers
    markdown_text = _convert_underline_headers_to_hash(markdown_text=markdown_text)

    # Replace multiple consecutive blank lines with a single one
    markdown_text = re.sub(pattern=r"\n{3,}", repl="\n\n", string=markdown_text)

    # Fix code blocks that might have been malformed
    markdown_text = re.sub(
        pattern=r"```\s+([a-zA-Z0-9]+)\s*\n", repl=r"```\1\n", string=markdown_text
    )

    # Ensure there are blank lines before and after headings
    markdown_text = re.sub(
        pattern=r"([^\n])\n(#{1,6} )", repl=r"\1\n\n\2", string=markdown_text
    )
    markdown_text = re.sub(
        pattern=r"(#{1,6} .*)\n([^\n])", repl=r"\1\n\n\2", string=markdown_text
    )

    # Ensure proper spacing around lists
    markdown_text = re.sub(
        pattern=r"([^\n])\n(- |\* |[0-9]+\. )", repl=r"\1\n\n\2", string=markdown_text
    )

    # Ensure proper spacing around code blocks
    markdown_text = re.sub(
        pattern=r"([^\n])\n```", repl=r"\1\n\n```", string=markdown_text
    )
    markdown_text = re.sub(
        pattern=r"```\n([^\n])", repl=r"```\n\n\1", string=markdown_text
    )

    # Remove some xmlns attributes that might be present
    markdown_text = re.sub(
        pattern=r'xml encoding="UTF-8"',
        repl="",
        string=markdown_text,
        flags=re.IGNORECASE,
    )

    return markdown_text


def extract_links(content: str) -> list[tuple[str, str]]:
    """Extract links from HTML or markdown content.

    Args:
        content: HTML or markdown content

    Returns:
        List of tuples with link title and URL
    """
    links: list[tuple[str, str]] = []
    if not content:
        return links

    try:
        # Parse with BeautifulSoup
        soup = BeautifulSoup(markup=content, features="html.parser")

        # Find all links
        for link in soup.find_all(name="a"):
            try:
                href: str = str(link.get("href", ""))  # type: ignore
                if href:
                    text: str = link.get_text().strip()
                    if not text:
                        text = href
                    links.append((text, href))
            except Exception as e:
                logger.debug(msg=f"Error processing link: {e}")

        return links
    except Exception as e:
        logger.error(msg=f"Error extracting links: {e}")
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
    text = re.sub(pattern=r"\[([^\]]*)\]", repl=r"\\[\1]", string=text)

    # Escape other markdown formatting characters
    chars_to_escape: list[str] = ["*", "_", "`", "#"]
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
        timestamp_str = str(object=timestamp)

        # Check if timestamp is a unix timestamp (numeric string)
        if timestamp_str.isdigit() or isinstance(timestamp, (int | float)):
            timestamp_val = float(timestamp_str)

            # Check if timestamp is in milliseconds (13 digits) and convert to seconds if needed
            if (
                timestamp_val > 10000000000  # noqa: PLR2004
            ):  # Timestamps in milliseconds are typically > 10^12
                timestamp_val: float = timestamp_val / 1000

            # Convert from seconds to datetime
            dt: datetime = datetime.fromtimestamp(timestamp=timestamp_val)
        else:
            # Try to parse as ISO format
            dt = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))

        # Format based on locale
        return dt.strftime(format="%c")
    except Exception as e:
        logger.error(msg=f"Error formatting timestamp '{timestamp}': {e}")
        return str(object=timestamp) if timestamp else ""


def _validate_url(url: str) -> None:
    """Validate that a URL is safe to use.

    Args:
        url: URL to validate

    Raises:
        ValueError: If URL is invalid or unsafe
    """
    if not url or not isinstance(url, str):
        raise ValueError("URL must be a non-empty string")

    try:
        parsed = urlparse(url)

        # Check for required components
        if not parsed.scheme or not parsed.netloc:
            raise ValueError("URL must have a scheme (http/https) and network location")

        # Only allow HTTP and HTTPS
        if parsed.scheme not in ("http", "https"):
            raise ValueError(
                f"Only HTTP and HTTPS URLs are allowed, got: {parsed.scheme}"
            )

        # Warn about localhost/private IPs to prevent SSRF
        netloc_lower = parsed.netloc.lower()
        private_patterns = [
            "localhost",
            "127.0.0.1",
            "0.0.0.0",
            "::1",
            "169.254",  # Link-local
        ]
        if any(pattern in netloc_lower for pattern in private_patterns):
            logger.warning(msg=f"URL uses local/private network: {url}")

    except Exception as e:
        raise ValueError(f"Invalid URL: {e}") from e


async def download_and_convert_html(
    url: str,
    method: str = "service",
    service_url: str = "https://r.jina.ai/$url",
    timeout: int = 30,
) -> str:
    """Download HTML from URL and convert to markdown.

    Args:
        url: URL to download HTML from
        method: Conversion method - "direct" (local markdownify) or "service" (external service)
        service_url: Service URL template (use $url placeholder for actual URL)
        timeout: Request timeout in seconds

    Returns:
        Markdown content

    Raises:
        ValueError: If URL is invalid or method is unknown
        httpx.RequestError: If network request fails
    """
    if not url:
        raise ValueError("URL cannot be empty")

    if method not in ("direct", "service"):
        raise ValueError(f"Unknown method: {method}. Must be 'direct' or 'service'")

    # Validate the URL before processing
    _validate_url(url)

    try:
        if method == "service":
            return await _convert_via_service(
                url=url, service_url=service_url, timeout=timeout
            )
        else:
            return await _convert_via_direct_download(url=url, timeout=timeout)
    except Exception as e:
        logger.error(msg=f"Error downloading and converting HTML from {url}: {e}")
        raise


async def _convert_via_service(url: str, service_url: str, timeout: int) -> str:
    """Convert HTML via external service like Jina API.

    Args:
        url: Original article URL
        service_url: Service URL template with $url placeholder
        timeout: Request timeout in seconds

    Returns:
        Markdown content from service

    Raises:
        httpx.RequestError: If service request fails
        ValueError: If service URL template is invalid
    """
    try:
        # Validate service_url template
        if not service_url or "$url" not in service_url:
            raise ValueError(
                "Service URL must contain $url placeholder for article URL"
            )

        # URL-encode the article URL for safe inclusion
        encoded_url = quote(url, safe=":/?#[]@!$&'()*+,;=")

        # Replace $url placeholder with properly encoded URL
        service_request_url = service_url.replace("$url", encoded_url)

        # Validate the resulting service request URL
        _validate_url(service_request_url)

        logger.debug(msg=f"Calling service for URL: {url} (encoded: {encoded_url})")

        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url=service_request_url)
            response.raise_for_status()
            # Service like Jina returns markdown directly
            return response.text
    except httpx.HTTPError as e:
        logger.error(msg=f"Service request failed: {e}")
        raise
    except ValueError as e:
        logger.error(msg=f"Invalid service URL configuration: {e}")
        raise


async def _convert_via_direct_download(url: str, timeout: int) -> str:
    """Download HTML directly and convert using local markdownify.

    Args:
        url: Article URL to download
        timeout: Request timeout in seconds

    Returns:
        Converted markdown content

    Raises:
        httpx.RequestError: If download fails
    """
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            # Download the HTML with proper headers
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }

            logger.debug(msg=f"Downloading HTML from: {url}")
            response = await client.get(url=url, headers=headers)
            response.raise_for_status()

            logger.debug(msg=f"Successfully downloaded {len(response.text)} bytes")

            # Convert HTML to markdown
            markdown = render_html_to_markdown(html_content=response.text)
            return markdown
    except httpx.HTTPError as e:
        logger.error(msg=f"Failed to download HTML from {url}: {e}")
        raise
