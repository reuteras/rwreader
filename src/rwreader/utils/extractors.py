"""Pure extraction helpers for article content.

Every function here takes text (HTML or markdown) and returns plain data.
Nothing touches the network or the UI, so the whole module is trivially
testable and reusable from other front ends.

Extractors:

* :func:`extract_links` - hyperlinks, cleaned and deduplicated
* :func:`extract_attachments` - downloadable files (documents, media, archives)
* :func:`extract_code_blocks` - fenced code blocks from markdown
* :func:`extract_indicators` - indicators of compromise (IPs, domains, hashes...)
* :func:`extract_references` - DOIs, arXiv IDs, GitHub repositories, RFCs
"""

import csv
import io
import ipaddress
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

# ── Links ──────────────────────────────────────────────────────────────────

_TRACKING_PARAM_PREFIXES: tuple[str, ...] = ("utm_", "mc_", "pk_", "matomo_")
_TRACKING_PARAMS: frozenset[str] = frozenset(
    {
        "fbclid",
        "gclid",
        "dclid",
        "msclkid",
        "igshid",
        "yclid",
        "twclid",
        "ref",
        "ref_src",
        "ref_url",
        "referrer",
        "source",
        "_ga",
        "_gl",
        "_hsenc",
        "_hsmi",
        "hsCtaTracking",
        "mkt_tok",
        "oly_anon_id",
        "oly_enc_id",
        "s_cid",
        "vero_id",
        "wickedid",
    }
)
_SKIP_SCHEMES: tuple[str, ...] = ("javascript:", "mailto:", "tel:", "data:", "#")
_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


@dataclass(frozen=True)
class ExtractedLink:
    """A hyperlink found in an article."""

    text: str
    url: str
    domain: str


def clean_url(url: str) -> str:
    """Strip tracking query parameters and fragments from a URL.

    Args:
        url: Absolute URL.

    Returns:
        The URL without fragment and without known tracking parameters. The
        remaining query parameters keep their order.
    """
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return url.strip()
    kept = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key not in _TRACKING_PARAMS
        and not key.lower().startswith(_TRACKING_PARAM_PREFIXES)
    ]
    return urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            parsed.params,
            urlencode(kept, doseq=True),
            "",
        )
    )


def _is_skippable(href: str) -> bool:
    """True for anchors, javascript, mailto and other non-navigable hrefs."""
    lowered = href.strip().lower()
    return not lowered or lowered.startswith(_SKIP_SCHEMES)


def _resolve(href: str, base_url: str | None) -> str | None:
    """Resolve a possibly relative href against the base URL; None if unusable."""
    href = href.strip()
    if _is_skippable(href):
        return None
    if base_url:
        href = urljoin(base_url, href)
    parsed = urlparse(href)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None
    return clean_url(href)


def extract_links(
    html: str | None = None,
    markdown: str | None = None,
    base_url: str | None = None,
    exclude_domains: Iterable[str] = (),
) -> list[ExtractedLink]:
    """Extract hyperlinks from article content.

    HTML is preferred because markdown conversion can mangle link text. When
    no HTML is available the markdown ``[text](url)`` syntax is parsed instead.

    Args:
        html: Article HTML, if available.
        markdown: Article markdown, used when ``html`` is empty.
        base_url: URL of the article, used to resolve relative links.
        exclude_domains: Domains to drop, for example the article's own site.

    Returns:
        Links in order of first appearance, deduplicated by cleaned URL, with
        anchors, mailto/javascript links and tracking parameters removed.
    """
    raw: list[tuple[str, str]] = []
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for anchor in soup.find_all("a"):
            href = anchor.get("href")
            if not isinstance(href, str):
                continue
            raw.append((anchor.get_text(" ", strip=True), href))
    elif markdown:
        for match in _MARKDOWN_LINK_RE.finditer(markdown):
            raw.append((match.group(1).strip(), match.group(2).strip()))

    excluded = {d.lower().removeprefix("www.") for d in exclude_domains if d}
    seen: set[str] = set()
    links: list[ExtractedLink] = []
    for text, href in raw:
        url = _resolve(href, base_url)
        if url is None or url in seen:
            continue
        domain = urlparse(url).netloc.lower().removeprefix("www.")
        if domain in excluded:
            continue
        seen.add(url)
        links.append(ExtractedLink(text=text or url, url=url, domain=domain))
    return links


def group_links_by_domain(
    links: Iterable[ExtractedLink],
) -> dict[str, list[ExtractedLink]]:
    """Group links by domain, preserving first-appearance order of domains."""
    grouped: dict[str, list[ExtractedLink]] = {}
    for link in links:
        grouped.setdefault(link.domain, []).append(link)
    return grouped


# ── Attachments ────────────────────────────────────────────────────────────

_ATTACHMENT_KINDS: dict[str, frozenset[str]] = {
    "document": frozenset({"pdf", "epub", "mobi", "djvu", "ps"}),
    "audio": frozenset({"mp3", "m4a", "ogg", "oga", "opus", "wav", "flac", "aac"}),
    "video": frozenset({"mp4", "m4v", "webm", "mkv", "mov", "avi"}),
    "image": frozenset({"png", "jpg", "jpeg", "gif", "webp", "svg", "bmp", "tiff"}),
    "archive": frozenset({"zip", "tar", "gz", "tgz", "bz2", "xz", "7z", "rar"}),
    "data": frozenset({"csv", "json", "xml", "yaml", "yml", "txt", "ipynb"}),
}


@dataclass(frozen=True)
class Attachment:
    """A downloadable file linked from an article."""

    text: str
    url: str
    kind: str
    extension: str


def _attachment_kind(url: str) -> tuple[str, str] | None:
    """Return (kind, extension) for a URL whose path ends in a known extension."""
    path = urlparse(url).path
    if "." not in path.rsplit("/", 1)[-1]:
        return None
    extension = path.rsplit(".", 1)[-1].lower()
    for kind, extensions in _ATTACHMENT_KINDS.items():
        if extension in extensions:
            return kind, extension
    return None


def extract_attachments(
    html: str | None = None,
    links: Iterable[ExtractedLink] = (),
    base_url: str | None = None,
) -> list[Attachment]:
    """Find downloadable files: linked documents, media, archives and images.

    Args:
        html: Article HTML; ``<img>``, ``<audio>``, ``<video>`` and ``<source>``
            elements are scanned in addition to links.
        links: Already-extracted hyperlinks to classify.
        base_url: URL of the article, used to resolve relative sources.

    Returns:
        Attachments in order of first appearance, deduplicated by URL.
    """
    candidates: list[tuple[str, str]] = [(link.text, link.url) for link in links]
    if html:
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup.find_all(["img", "audio", "video", "source"]):
            src = tag.get("src")
            if not isinstance(src, str):
                continue
            alt = tag.get("alt")
            label = alt if isinstance(alt, str) and alt else src.rsplit("/", 1)[-1]
            candidates.append((label, src))

    seen: set[str] = set()
    attachments: list[Attachment] = []
    for text, href in candidates:
        url = _resolve(href, base_url)
        if url is None or url in seen:
            continue
        kind = _attachment_kind(url)
        if kind is None:
            continue
        seen.add(url)
        attachments.append(
            Attachment(text=text or url, url=url, kind=kind[0], extension=kind[1])
        )
    return attachments


# ── Code blocks ────────────────────────────────────────────────────────────

_FENCE_RE = re.compile(r"^```[ \t]*([\w+#.-]*)[ \t]*\n(.*?)^```[ \t]*$", re.M | re.S)

_LANGUAGE_EXTENSIONS: dict[str, str] = {
    "python": "py",
    "py": "py",
    "bash": "sh",
    "sh": "sh",
    "shell": "sh",
    "zsh": "sh",
    "console": "sh",
    "javascript": "js",
    "js": "js",
    "typescript": "ts",
    "ts": "ts",
    "json": "json",
    "yaml": "yaml",
    "yml": "yaml",
    "toml": "toml",
    "rust": "rs",
    "go": "go",
    "c": "c",
    "cpp": "cpp",
    "c++": "cpp",
    "csharp": "cs",
    "java": "java",
    "kotlin": "kt",
    "ruby": "rb",
    "powershell": "ps1",
    "ps1": "ps1",
    "sql": "sql",
    "html": "html",
    "css": "css",
    "xml": "xml",
    "markdown": "md",
    "md": "md",
    "dockerfile": "Dockerfile",
    "makefile": "mk",
    "text": "txt",
    "txt": "txt",
}


@dataclass(frozen=True)
class CodeBlock:
    """A fenced code block."""

    language: str
    code: str

    @property
    def line_count(self) -> int:
        """Number of lines in the block."""
        return len(self.code.splitlines())

    @property
    def extension(self) -> str:
        """A file extension suited to the block's language."""
        return _LANGUAGE_EXTENSIONS.get(self.language.lower(), "txt")


def extract_code_blocks(markdown: str) -> list[CodeBlock]:
    """Extract fenced code blocks from markdown.

    Args:
        markdown: Markdown text.

    Returns:
        Code blocks in document order. Empty blocks are skipped.
    """
    blocks: list[CodeBlock] = []
    for match in _FENCE_RE.finditer(markdown or ""):
        code = match.group(2).rstrip("\n")
        if not code.strip():
            continue
        blocks.append(CodeBlock(language=match.group(1).lower(), code=code))
    return blocks


# ── Indicators of compromise ───────────────────────────────────────────────


def _fix_scheme(match: re.Match[str]) -> str:
    """Turn hxxp(s):// and h[tt]p(s):// back into http(s)://."""
    return match.group(0).lower().replace("xx", "tt").replace("[tt]", "tt")


_DEFANG_PATTERNS: list[tuple[re.Pattern[str], str | Callable[[re.Match[str]], str]]] = [
    (re.compile(r"hxxps?://|h\[tt\]ps?://", re.I), _fix_scheme),
    (re.compile(r"\[(?:\.|dot)\]|\((?:\.|dot)\)|\{(?:\.|dot)\}|\s+dot\s+", re.I), "."),
    (re.compile(r"\[://\]"), "://"),
    (re.compile(r"\[:\]"), ":"),
    (re.compile(r"\[@\]|\(@\)|\{@\}"), "@"),
    (re.compile(r"\\\."), "."),
]

_IPV4_RE = re.compile(r"(?<![\w.])(?:\d{1,3}\.){3}\d{1,3}(?![\w.])")
_IPV6_RE = re.compile(r"(?<![\w:])(?:[0-9a-f]{0,4}:){2,7}[0-9a-f]{0,4}(?![\w:])", re.I)
_SHA512_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{128}(?![0-9a-f])", re.I)
_SHA256_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{64}(?![0-9a-f])", re.I)
_SHA1_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{40}(?![0-9a-f])", re.I)
_MD5_RE = re.compile(r"(?<![0-9a-f])[0-9a-f]{32}(?![0-9a-f])", re.I)
_CVE_RE = re.compile(r"\bCVE-\d{4}-\d{4,7}\b", re.I)
_EMAIL_RE = re.compile(r"\b[\w.+-]+@(?:[\w-]+\.)+[a-z]{2,}\b", re.I)
_URL_RE = re.compile(r"\bhttps?://[^\s<>\"'`\]\)}]+", re.I)
_DOMAIN_RE = re.compile(
    r"\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,24}\b", re.I
)
_HEX_ONLY_RE = re.compile(r"^[0-9]+$")

# "Domains" that are really file names or common false positives.
_NOT_TLDS: frozenset[str] = frozenset(
    {
        "txt", "html", "htm", "php", "asp", "aspx", "jsp", "py", "js", "ts",
        "tsx", "jsx", "json", "md", "rst", "png", "jpg", "jpeg", "gif", "svg",
        "webp", "ico", "css", "scss", "xml", "yml", "yaml", "toml", "ini",
        "cfg", "conf", "log", "csv", "sql", "exe", "dll", "sys", "bin", "dat",
        "so", "dylib", "sh", "bat", "ps1", "cmd", "vbs", "rs", "go", "java",
        "cs", "cpp", "hpp", "c", "h", "rb", "pl", "lua", "kt", "swift", "m",
        "zip", "tar", "gz", "tgz", "bz2", "xz", "7z", "rar", "iso", "img",
        "dmg", "pkg", "deb", "rpm", "msi", "apk", "jar", "war", "class",
        "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "rtf",
        "mp3", "mp4", "wav", "avi", "mkv", "mov", "webm", "ogg", "flac",
        "lock", "pem", "crt", "key", "pub", "asc", "sig", "bak", "tmp", "pyc",
        "egg", "whl", "env", "example", "local", "internal", "test", "invalid",
        "localhost", "lan", "home", "corp",
    }
)  # fmt: skip

INDICATOR_KINDS: tuple[str, ...] = (
    "ipv4",
    "ipv6",
    "domain",
    "url",
    "email",
    "md5",
    "sha1",
    "sha256",
    "sha512",
    "cve",
)


@dataclass(frozen=True)
class Indicator:
    """An indicator of compromise found in text."""

    kind: str
    value: str
    defanged: bool = False


def refang(text: str) -> str:
    """Undo common defanging so indicators can be matched.

    Handles ``hxxp``, ``[.]``, ``(.)``, ``{.}``, `` dot ``, ``[:]``, ``[@]``
    and backslash-escaped dots.

    Args:
        text: Text possibly containing defanged indicators.

    Returns:
        The text with defanging reversed.
    """
    result = text
    for pattern, replacement in _DEFANG_PATTERNS:
        result = pattern.sub(replacement, result)
    return result


def _valid_ipv4(value: str) -> bool:
    """True if the dotted quad is a real IPv4 address."""
    try:
        ipaddress.IPv4Address(value)
    except ValueError:
        return False
    return True


def _valid_ipv6(value: str) -> bool:
    """True if the candidate is a real IPv6 address with at least three groups."""
    if value.count(":") < 2:  # noqa: PLR2004
        return False
    try:
        ipaddress.IPv6Address(value)
    except ValueError:
        return False
    return True


def _plausible_domain(value: str, ipv4s: set[str]) -> bool:
    """Filter out file names, version strings and IPs matched as domains."""
    if value in ipv4s:
        return False
    labels = value.lower().split(".")
    if labels[-1] in _NOT_TLDS:
        return False
    if all(_HEX_ONLY_RE.match(label) for label in labels):
        return False
    return len(labels) >= 2  # noqa: PLR2004


def _strip_markdown_link_targets(markdown: str) -> str:
    """Replace ``[text](url)`` with ``text`` so only visible content is scanned."""
    return _MARKDOWN_LINK_RE.sub(lambda m: m.group(1), markdown)


def extract_indicators(  # noqa: PLR0912
    text: str,
    exclude_domains: Iterable[str] = (),
    strip_link_targets: bool = True,
) -> list[Indicator]:
    """Extract indicators of compromise from visible text.

    Defanged forms are refanged and flagged. Hyperlink targets in markdown are
    ignored by default because they are navigation, not indicators; defanged
    or bare indicators in the body text are what threat reports contain.

    Args:
        text: Markdown or plain text.
        exclude_domains: Domains (and their subdomains) to ignore, for example
            the article's own site.
        strip_link_targets: Drop ``(url)`` parts of markdown links before scanning.

    Returns:
        Indicators grouped by kind in :data:`INDICATOR_KINDS` order, each
        value appearing once (the defanged flag is set if any occurrence was
        defanged).
    """
    if not text:
        return []
    source = _strip_markdown_link_targets(text) if strip_link_targets else text
    fanged = refang(source)
    source_lower = source.lower()
    excluded = tuple(d.lower().removeprefix("www.") for d in exclude_domains if d)

    def is_excluded(host: str) -> bool:
        host = host.lower().removeprefix("www.")
        return any(host == d or host.endswith("." + d) for d in excluded)

    found: dict[tuple[str, str], bool] = {}

    def add(kind: str, value: str) -> None:
        key = (kind, value)
        defanged = value.lower() not in source_lower
        found[key] = found.get(key, False) or defanged

    ipv4s: set[str] = set()
    for match in _IPV4_RE.finditer(fanged):
        if _valid_ipv4(match.group(0)):
            ipv4s.add(match.group(0))
            add("ipv4", match.group(0))

    for match in _IPV6_RE.finditer(fanged):
        candidate = match.group(0)
        if _valid_ipv6(candidate):
            add("ipv6", candidate.lower())

    for match in _URL_RE.finditer(fanged):
        url = match.group(0).rstrip(".,;:!?'\")]}>")
        host = urlparse(url).hostname or ""
        if host and not is_excluded(host):
            add("url", url)

    for match in _EMAIL_RE.finditer(fanged):
        email = match.group(0)
        if not is_excluded(email.rsplit("@", 1)[-1]):
            add("email", email.lower())

    for match in _DOMAIN_RE.finditer(fanged):
        domain = match.group(0).lower()
        if _plausible_domain(domain, ipv4s) and not is_excluded(domain):
            add("domain", domain)

    for kind, pattern in (
        ("sha512", _SHA512_RE),
        ("sha256", _SHA256_RE),
        ("sha1", _SHA1_RE),
        ("md5", _MD5_RE),
    ):
        for match in pattern.finditer(fanged):
            add(kind, match.group(0).lower())

    for match in _CVE_RE.finditer(fanged):
        add("cve", match.group(0).upper())

    order = {kind: i for i, kind in enumerate(INDICATOR_KINDS)}
    return [
        Indicator(kind=kind, value=value, defanged=defanged)
        for (kind, value), defanged in sorted(
            found.items(), key=lambda item: (order[item[0][0]], item[0][1])
        )
    ]


def format_indicators(indicators: Iterable[Indicator], fmt: str = "text") -> str:
    """Render indicators as text, CSV or JSON.

    Args:
        indicators: Indicators to render.
        fmt: ``"text"`` (grouped, one value per line), ``"csv"``
            (kind,value,defanged) or ``"json"`` (list of objects).

    Returns:
        The rendered string.

    Raises:
        ValueError: For an unknown format.
    """
    items = list(indicators)
    if fmt == "text":
        lines: list[str] = []
        current = ""
        for item in items:
            if item.kind != current:
                if lines:
                    lines.append("")
                lines.append(f"# {item.kind}")
                current = item.kind
            lines.append(item.value)
        return "\n".join(lines)
    if fmt == "csv":
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["kind", "value", "defanged"])
        for item in items:
            writer.writerow([item.kind, item.value, str(item.defanged).lower()])
        return buffer.getvalue()
    if fmt == "json":
        return json.dumps([asdict(item) for item in items], indent=2)
    raise ValueError(f"Unknown format: {fmt!r}")


# ── References ─────────────────────────────────────────────────────────────

_DOI_RE = re.compile(r"\b10\.\d{4,9}/[^\s\"'<>()\[\]]+", re.I)
_ARXIV_RE = re.compile(
    r"(?:arxiv:\s*|arxiv\.org/(?:abs|pdf)/)(\d{4}\.\d{4,5}(?:v\d+)?)", re.I
)
_GITHUB_RE = re.compile(
    r"github\.com/([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+?)(?=[/#?\s\"'<>)\]]|$)", re.I
)
_RFC_RE = re.compile(r"\bRFC[ -]?(\d{3,5})\b", re.I)
_GITHUB_NON_REPOS: frozenset[str] = frozenset(
    {"features", "topics", "settings", "orgs", "marketplace", "sponsors", "about"}
)


@dataclass(frozen=True)
class Reference:
    """A citation-like reference found in text."""

    kind: str
    value: str
    url: str


def extract_references(text: str) -> list[Reference]:
    """Extract DOIs, arXiv identifiers, GitHub repositories and RFC numbers.

    Args:
        text: Markdown or plain text (link targets are included in the scan).

    Returns:
        References in order of first appearance, deduplicated by URL.
    """
    if not text:
        return []
    seen: set[str] = set()
    refs: list[Reference] = []

    def add(kind: str, value: str, url: str) -> None:
        if url in seen:
            return
        seen.add(url)
        refs.append(Reference(kind=kind, value=value, url=url))

    for match in _DOI_RE.finditer(text):
        doi = match.group(0).rstrip(".,;:")
        add("doi", doi, f"https://doi.org/{doi}")
    for match in _ARXIV_RE.finditer(text):
        arxiv_id = match.group(1)
        add("arxiv", arxiv_id, f"https://arxiv.org/abs/{arxiv_id}")
    for match in _GITHUB_RE.finditer(text):
        repo = match.group(1).removesuffix(".git")
        owner = repo.split("/", 1)[0].lower()
        if owner in _GITHUB_NON_REPOS:
            continue
        add("github", repo, f"https://github.com/{repo}")
    for match in _RFC_RE.finditer(text):
        number = match.group(1)
        add("rfc", f"RFC {number}", f"https://www.rfc-editor.org/rfc/rfc{number}")
    return refs


def to_link_tuples(items: Iterable[Any]) -> list[tuple[str, str]]:
    """Convert extracted objects to ``(label, url)`` tuples for link screens."""
    tuples: list[tuple[str, str]] = []
    for item in items:
        if isinstance(item, ExtractedLink):
            tuples.append((item.text, item.url))
        elif isinstance(item, Attachment):
            tuples.append((f"[{item.kind}] {item.text}", item.url))
        elif isinstance(item, Reference):
            tuples.append((f"[{item.kind}] {item.value}", item.url))
    return tuples
