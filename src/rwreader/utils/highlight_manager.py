"""Highlight manager using the readwise CLI tool."""

import json
import logging
import os
import re
import subprocess
from typing import Any

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

_CLI_CACHE: dict[str, Any] = {"checked": False, "path": None}

# Sentinel string that only the Node.js readwise CLI outputs in its help.
_CLI_FINGERPRINT = "reader-get-document-highlights"


def _find_node_readwise_cli() -> str | None:
    """Scan PATH for the Node.js readwise CLI.

    The project's venv also installs a Python `readwise` binary that does not
    support Reader commands.  We probe each candidate with `--help` and return
    the first one whose output contains the Reader-specific command name.
    """
    path_dirs = os.environ.get("PATH", "").split(os.pathsep)
    for dir_path in path_dirs:
        candidate = os.path.join(dir_path, "readwise")
        if not os.path.isfile(candidate) or not os.access(candidate, os.X_OK):
            continue
        try:
            probe = subprocess.run(
                [candidate, "--help"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if _CLI_FINGERPRINT in probe.stdout or _CLI_FINGERPRINT in probe.stderr:
                logger.debug(f"Found Node.js readwise CLI at {candidate!r}")
                return candidate
        except Exception:
            continue
    return None


def get_cli_path() -> str | None:
    """Return the path to the Node.js readwise CLI, caching the result."""
    if not _CLI_CACHE["checked"]:
        _CLI_CACHE["path"] = _find_node_readwise_cli()
        _CLI_CACHE["checked"] = True
        if not _CLI_CACHE["path"]:
            logger.debug("Node.js readwise CLI not found in PATH")
    return str(_CLI_CACHE["path"]) if _CLI_CACHE["path"] else None


def is_readwise_cli_available() -> bool:
    """Return True if the readwise CLI is available in PATH."""
    return get_cli_path() is not None


def get_highlights_for_document(document_id: str) -> list[dict[str, Any]]:
    """Fetch Reader highlights for a specific document by ID.

    Uses `reader-get-document-highlights` which returns highlights scoped
    directly to the document — no URL matching required.

    Args:
        document_id: Reader document ID (e.g. "01krjdv9s8yjt0tnrmy6xh1kah").

    Returns:
        List of highlight dicts with keys: id, content, tags, notes.
        Returns empty list on error or if CLI is unavailable.
    """
    cli = get_cli_path()
    logger.debug(f"get_highlights_for_document: cli={cli!r} document_id={document_id!r}")
    if not cli or not document_id:
        return []

    cmd = [cli, "--json", "reader-get-document-highlights", f"--document-id={document_id}"]
    logger.debug(f"Running: {' '.join(cmd)}")
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        logger.debug(f"returncode={result.returncode} stdout={result.stdout[:200]!r} stderr={result.stderr[:200]!r}")
        if result.returncode != 0:
            logger.error(f"readwise CLI error: {result.stderr[:200]}")
            return []

        data = json.loads(result.stdout)
        logger.debug(f"Parsed {len(data) if isinstance(data, list) else 'non-list'} highlights")
        return data if isinstance(data, list) else []

    except subprocess.TimeoutExpired:
        logger.error("Timeout fetching highlights from readwise CLI")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"JSON decode error from readwise CLI: {e} — stdout was: {result.stdout[:200]!r}")
        return []
    except Exception as e:
        logger.error(f"Error fetching highlights: {e}")
        return []


def find_html_fragment(html_content: str, paragraph_text: str) -> str:
    """Find the HTML element in html_content whose plain text best matches paragraph_text.

    Falls back to ``<p>paragraph_text</p>`` when no element is found.

    Args:
        html_content: Full HTML of the article.
        paragraph_text: Plain-text paragraph from the markdown view.

    Returns:
        An HTML string suitable for ``reader-create-highlight --html-content``.
    """
    if not html_content:
        return f"<p>{paragraph_text}</p>"

    normalized_target = re.sub(r"\s+", " ", paragraph_text).strip()
    try:
        soup = BeautifulSoup(html_content, "html.parser")
        for tag in soup.find_all(["p", "li", "blockquote"]):
            tag_text = re.sub(r"\s+", " ", tag.get_text()).strip()
            if normalized_target == tag_text or normalized_target in tag_text:
                return str(tag)
    except Exception as e:
        logger.debug(f"HTML fragment lookup failed: {e}")

    return f"<p>{paragraph_text}</p>"


def create_reader_highlight(
    document_id: str,
    html_fragment: str,
) -> tuple[bool, str]:
    """Create a Reader document highlight via the CLI.

    Uses ``reader-create-highlight`` which attaches the highlight directly to
    the Reader document (visible in the web UI and via
    ``reader-get-document-highlights``).

    Args:
        document_id: Reader document ID.
        html_fragment: Exact HTML element to highlight (e.g. ``<p>…</p>``).

    Returns:
        Tuple of (success, message).
    """
    cli = get_cli_path()
    if not cli:
        return False, "readwise CLI not available"

    try:
        result = subprocess.run(
            [
                cli,
                "--json",
                "reader-create-highlight",
                f"--document-id={document_id}",
                f"--html-content={html_fragment}",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0:
            return True, "Highlight created"
        logger.error(f"reader-create-highlight error: {result.stderr[:200]}")
        return False, result.stderr[:100]
    except subprocess.TimeoutExpired:
        return False, "Timeout creating highlight"
    except Exception as e:
        logger.error(f"Error creating highlight: {e}")
        return False, str(e)


def delete_reader_highlight(highlight_id: str) -> tuple[bool, str]:
    """Delete a Reader highlight via the Readwise API.

    The CLI has no ``reader-delete-highlight`` command, so we call the
    Readwise v3 API directly using the token stored in ``READWISE_TOKEN``.

    Args:
        highlight_id: String ID of the Reader highlight to delete.

    Returns:
        Tuple of (success, message).
    """
    token = os.environ.get("READWISE_TOKEN", "")
    if not token:
        return False, "READWISE_TOKEN not set"

    url = f"https://readwise.io/api/v3/highlights/{highlight_id}/"
    try:
        response = requests.delete(
            url,
            headers={"Authorization": f"Token {token}"},
            timeout=15,
        )
        if response.status_code in (200, 204):
            return True, "Highlight deleted"
        logger.error(f"Reader highlight delete API error {response.status_code}: {response.text[:200]}")
        return False, f"API error {response.status_code}"
    except requests.RequestException as e:
        logger.error(f"Error deleting Reader highlight: {e}")
        return False, str(e)


def delete_highlight(highlight_id: str | int) -> tuple[bool, str]:
    """Delete a Readwise highlight via the CLI.

    Args:
        highlight_id: ID of the highlight to delete (string for Reader highlights,
                      int for classic Readwise highlights).

    Returns:
        Tuple of (success, message).
    """
    cli = get_cli_path()
    if not cli:
        return False, "readwise CLI not available"

    try:
        result = subprocess.run(
            [
                cli,
                "readwise-delete-highlight",
                "--json",
                "--highlight-id",
                str(highlight_id),
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0:
            return True, "Highlight deleted"
        logger.error(f"readwise delete-highlight error: {result.stderr[:200]}")
        return False, f"CLI error: {result.stderr[:100]}"
    except subprocess.TimeoutExpired:
        return False, "Timeout deleting highlight"
    except Exception as e:
        logger.error(f"Error deleting highlight: {e}")
        return False, str(e)


def inject_highlights_into_markdown(
    markdown: str,
    highlights: list[dict[str, Any]],
) -> str:
    """Inject highlight markers into markdown content.

    Tries to bold-mark matching highlight text inline, then appends a
    dedicated Highlights section at the end of the article.

    Args:
        markdown: Base markdown content of the article.
        highlights: List of highlight dicts from the readwise CLI.

    Returns:
        Modified markdown with inline markers and appended Highlights section.
    """
    if not highlights:
        return markdown

    modified = markdown

    # Best-effort inline marking: collapse whitespace before comparing.
    for highlight in highlights:
        text = (highlight.get("content") or "").strip()
        if not text or len(text) < 10:  # noqa: PLR2004
            continue
        normalized = re.sub(r"\s+", " ", text)
        if normalized in modified:
            modified = modified.replace(normalized, f"**⟦{normalized}⟧**", 1)

    # Append a dedicated Highlights section only if there is renderable content.
    entries = ""
    for highlight in highlights:
        text = (highlight.get("content") or "").strip()
        if not text:
            continue
        notes = (highlight.get("notes") or "").strip()
        entries += f"> {text}\n\n"
        if notes:
            entries += f"*Note: {notes}*\n\n"

    if entries:
        modified += f"\n\n---\n\n## Highlights\n\n{entries}"

    return modified
