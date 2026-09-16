"""Tests for the pure extraction helpers."""

import json
from typing import ClassVar

import pytest

from rwreader.utils.extractors import (
    INDICATOR_KINDS,
    Attachment,
    CodeBlock,
    ExtractedLink,
    Indicator,
    Reference,
    clean_url,
    extract_attachments,
    extract_code_blocks,
    extract_indicators,
    extract_links,
    extract_references,
    format_indicators,
    group_links_by_domain,
    refang,
    to_link_tuples,
)

# Test constants
TWO = 2
THREE = 3
FOUR = 4
FIVE = 5


class TestCleanUrl:
    """Tests for clean_url."""

    def test_strips_tracking_and_fragment(self) -> None:
        """utm_*, fbclid and the fragment go; other params stay in order."""
        url = "https://Example.com/p?utm_source=x&id=2&fbclid=abc&b=1#frag"
        assert clean_url(url) == "https://example.com/p?id=2&b=1"

    def test_keeps_blank_values_and_plain_urls(self) -> None:
        """A URL without tracking is unchanged apart from case normalisation."""
        assert clean_url("https://example.com/a?x=") == "https://example.com/a?x="
        assert clean_url("https://example.com/a") == "https://example.com/a"

    def test_prefix_matching_is_case_insensitive(self) -> None:
        """UTM_Campaign is still a tracking parameter."""
        assert clean_url("https://e.com/?UTM_Campaign=1&k=v") == "https://e.com/?k=v"


class TestExtractLinks:
    """Tests for extract_links."""

    def test_html_preferred_and_cleaned(self) -> None:
        """Relative links resolve, anchors/mailto/javascript are skipped, dedupe by URL."""
        html = (
            '<a href="/rel?utm_source=x&id=2#f">Rel</a>'
            '<a href="#top">top</a>'
            '<a href="mailto:a@b.com">mail</a>'
            '<a href="javascript:void(0)">js</a>'
            '<a href="https://other.org/x">Other</a>'
            '<a href="https://other.org/x?utm_medium=y">Other again</a>'
            "<a>no href</a>"
        )
        links = extract_links(html=html, base_url="https://www.example.com/post")
        assert links == [
            ExtractedLink("Rel", "https://www.example.com/rel?id=2", "example.com"),
            ExtractedLink("Other", "https://other.org/x", "other.org"),
        ]

    def test_markdown_fallback(self) -> None:
        """Without HTML, markdown links are parsed; empty text falls back to URL."""
        md = 'See [here](https://x.org/p "title") and [](https://y.org/q).'
        links = extract_links(markdown=md)
        assert [link.url for link in links] == ["https://x.org/p", "https://y.org/q"]
        assert links[1].text == "https://y.org/q"

    def test_exclude_domains(self) -> None:
        """Excluded domains match with or without www."""
        html = '<a href="https://www.mysite.com/a">a</a><a href="https://z.io/b">b</a>'
        links = extract_links(html=html, exclude_domains=["mysite.com"])
        assert [link.domain for link in links] == ["z.io"]

    def test_non_http_schemes_dropped(self) -> None:
        """Ftp and file links are not returned."""
        html = '<a href="ftp://host/f">f</a><a href="file:///etc/passwd">p</a>'
        assert extract_links(html=html) == []

    def test_empty_inputs(self) -> None:
        """No content yields no links."""
        assert extract_links() == []
        assert extract_links(html="", markdown="") == []

    def test_group_by_domain(self) -> None:
        """Grouping preserves first-appearance order of domains."""
        links = [
            ExtractedLink("a", "https://b.com/1", "b.com"),
            ExtractedLink("b", "https://a.com/1", "a.com"),
            ExtractedLink("c", "https://b.com/2", "b.com"),
        ]
        grouped = group_links_by_domain(links)
        assert list(grouped) == ["b.com", "a.com"]
        assert len(grouped["b.com"]) == TWO


class TestExtractAttachments:
    """Tests for extract_attachments."""

    def test_classifies_links_and_media(self) -> None:
        """Documents, media and images are found from links and media tags."""
        links = [
            ExtractedLink("Paper", "https://e.com/paper.PDF", "e.com"),
            ExtractedLink("Page", "https://e.com/page", "e.com"),
            ExtractedLink("Zip", "https://e.com/a.zip?dl=1", "e.com"),
        ]
        html = (
            '<img src="/img/pic.png" alt="A picture">'
            '<video><source src="https://cdn.e.com/clip.mp4"></video>'
            '<audio src="https://cdn.e.com/talk.mp3"></audio>'
            '<img src="https://e.com/paper.PDF">'
        )
        result = extract_attachments(html=html, links=links, base_url="https://e.com/")
        assert [(a.kind, a.extension, a.url) for a in result] == [
            ("document", "pdf", "https://e.com/paper.PDF"),
            ("archive", "zip", "https://e.com/a.zip?dl=1"),
            ("image", "png", "https://e.com/img/pic.png"),
            ("video", "mp4", "https://cdn.e.com/clip.mp4"),
            ("audio", "mp3", "https://cdn.e.com/talk.mp3"),
        ]
        assert result[2].text == "A picture"

    def test_no_extension_or_unknown(self) -> None:
        """Paths without a known extension are ignored."""
        links = [
            ExtractedLink("x", "https://e.com/dir.v2/file", "e.com"),
            ExtractedLink("y", "https://e.com/thing.weird", "e.com"),
        ]
        assert extract_attachments(links=links) == []


class TestExtractCodeBlocks:
    """Tests for extract_code_blocks."""

    def test_fenced_blocks(self) -> None:
        """Language is captured and empty blocks are skipped."""
        md = (
            "Intro\n\n```python\nprint('hi')\nx = 1\n```\n\n"
            "```\nplain\n```\n\n```bash\n\n```\n\n```C++\nint x;\n```\n"
        )
        blocks = extract_code_blocks(md)
        assert [b.language for b in blocks] == ["python", "", "c++"]
        assert blocks[0].line_count == TWO
        assert blocks[0].extension == "py"
        assert blocks[1].extension == "txt"
        assert blocks[2].extension == "cpp"

    def test_unclosed_fence_ignored(self) -> None:
        """An unterminated fence produces nothing."""
        assert extract_code_blocks("```python\nprint(1)\n") == []
        assert extract_code_blocks("") == []

    def test_code_block_dataclass(self) -> None:
        """Helper properties work on a bare CodeBlock."""
        block = CodeBlock(language="Rust", code="fn main() {}\n")
        assert block.extension == "rs"
        assert block.line_count == 1


class TestRefang:
    """Tests for refang."""

    @pytest.mark.parametrize(
        ("defanged", "expected"),
        [
            ("hxxp://evil[.]com", "http://evil.com"),
            ("hXXps://evil(.)com/x", "https://evil.com/x"),
            ("h[tt]ps://evil{.}com", "https://evil.com"),
            ("evil dot com", "evil.com"),
            ("evil[dot]com", "evil.com"),
            ("http[:]//evil.com", "http://evil.com"),
            ("http[://]evil.com", "http://evil.com"),
            ("user[@]evil.com", "user@evil.com"),
            ("1[.]2[.]3[.]4", "1.2.3.4"),
            (r"evil\.com", "evil.com"),
        ],
    )
    def test_patterns(self, defanged: str, expected: str) -> None:
        """Each common defanging style is reversed."""
        assert refang(defanged) == expected

    def test_plain_text_unchanged(self) -> None:
        """Text without defanging is returned as is."""
        assert refang("nothing to see http://a.b/c") == "nothing to see http://a.b/c"


class TestExtractIndicators:
    """Tests for extract_indicators."""

    SAMPLE = (
        "C2 at hxxps://evil[.]example[.]net/gate.php and 8[.]8[.]8[.]8 plus 10.0.0.1 "
        "and 999.1.1.1. Mail bad[@]evil.net. "
        "MD5 d41d8cd98f00b204e9800998ecf8427e, "
        "SHA1 da39a3ee5e6b4b0d3255bfef95601890afd80709, "
        "SHA256 E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855. "
        "CVE-2024-1234 and cve-2023-99999. IPv6 2001:db8::1 at 12:30:00. "
        "Files config.json, README.md, version 1.2.3 and mysite.com/about. "
        "[link](https://tracker.example.org/x)"
    )

    def test_kinds_and_defanged_flags(self) -> None:
        """Every kind is found once, ordered by kind, with defanged flags."""
        found = {(i.kind, i.value): i.defanged for i in extract_indicators(self.SAMPLE)}
        assert found[("ipv4", "8.8.8.8")] is True
        assert found[("ipv4", "10.0.0.1")] is False
        assert ("ipv4", "999.1.1.1") not in found
        assert found[("ipv6", "2001:db8::1")] is False
        assert found[("url", "https://evil.example.net/gate.php")] is True
        assert found[("domain", "evil.example.net")] is True
        assert found[("domain", "mysite.com")] is False
        assert found[("email", "bad@evil.net")] is True
        assert found[("md5", "d41d8cd98f00b204e9800998ecf8427e")] is False
        assert found[("sha1", "da39a3ee5e6b4b0d3255bfef95601890afd80709")] is False
        assert (
            found[
                (
                    "sha256",
                    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                )
            ]
            is False
        )
        assert found[("cve", "CVE-2024-1234")] is False
        assert found[("cve", "CVE-2023-99999")] is False
        # File names, times and markdown link targets are not indicators
        assert ("domain", "config.json") not in found
        assert ("domain", "readme.md") not in found
        assert ("domain", "tracker.example.org") not in found
        assert ("url", "https://tracker.example.org/x") not in found

    def test_order_follows_kind_then_value(self) -> None:
        """Results are grouped by kind in the documented order."""
        kinds = [i.kind for i in extract_indicators(self.SAMPLE)]
        assert kinds == sorted(kinds, key=INDICATOR_KINDS.index)

    def test_exclude_domains_covers_subdomains_urls_and_emails(self) -> None:
        """Excluding a domain drops its subdomains, URLs and email addresses."""
        text = (
            "See https://blog.mysite.com/x and news.mysite.com and me@mysite.com "
            "but keep other.org and https://other.org/y"
        )
        result = extract_indicators(text, exclude_domains=["www.mysite.com"])
        values = {i.value for i in result}
        assert values == {"other.org", "https://other.org/y"}

    def test_link_targets_can_be_included(self) -> None:
        """strip_link_targets=False scans hyperlink URLs too."""
        text = "[c2](https://evil.net/panel)"
        assert extract_indicators(text) == []
        result = extract_indicators(text, strip_link_targets=False)
        assert {(i.kind, i.value) for i in result} == {
            ("domain", "evil.net"),
            ("url", "https://evil.net/panel"),
        }

    def test_hashes_do_not_overlap(self) -> None:
        """A SHA256 is not also reported as two MD5s or a SHA1."""
        sha256 = "a" * 64
        result = extract_indicators(f"hash {sha256} end")
        assert [(i.kind, i.value) for i in result] == [("sha256", sha256)]

    def test_url_trailing_punctuation_stripped(self) -> None:
        """Sentence punctuation after a URL is not part of it."""
        result = extract_indicators("Go to https://evil.net/path). Then stop.")
        assert ("url", "https://evil.net/path") in {(i.kind, i.value) for i in result}

    def test_empty(self) -> None:
        """Empty text yields nothing."""
        assert extract_indicators("") == []


class TestFormatIndicators:
    """Tests for format_indicators."""

    ITEMS: ClassVar[list[Indicator]] = [
        Indicator("ipv4", "1.1.1.1"),
        Indicator("ipv4", "8.8.8.8", defanged=True),
        Indicator("cve", "CVE-2024-1"),
    ]

    def test_text(self) -> None:
        """Text output groups by kind with a blank line between groups."""
        assert format_indicators(self.ITEMS, "text") == (
            "# ipv4\n1.1.1.1\n8.8.8.8\n\n# cve\nCVE-2024-1"
        )

    def test_csv(self) -> None:
        """CSV has a header and one row per indicator."""
        lines = format_indicators(self.ITEMS, "csv").splitlines()
        assert lines[0] == "kind,value,defanged"
        assert lines[2] == "ipv4,8.8.8.8,true"
        assert len(lines) == FOUR

    def test_json(self) -> None:
        """JSON is a list of objects with kind, value and defanged."""
        data = json.loads(format_indicators(self.ITEMS, "json"))
        assert data[1] == {"kind": "ipv4", "value": "8.8.8.8", "defanged": True}

    def test_unknown_format(self) -> None:
        """Unknown formats raise."""
        with pytest.raises(ValueError, match="Unknown format"):
            format_indicators(self.ITEMS, "xml")


class TestExtractReferences:
    """Tests for extract_references."""

    def test_all_kinds(self) -> None:
        """DOI, arXiv, GitHub and RFC references are found with canonical URLs."""
        text = (
            "See doi:10.1000/xyz123. arXiv:2101.00001v2 and arxiv.org/abs/2101.00002 "
            "plus https://github.com/reuteras/rwreader/issues/1, "
            "github.com/reuteras/rwreader.git and github.com/features/copilot. "
            "RFC 8446, RFC-2616 and RFC8446 again."
        )
        refs = extract_references(text)
        assert refs == [
            Reference("doi", "10.1000/xyz123", "https://doi.org/10.1000/xyz123"),
            Reference("arxiv", "2101.00001v2", "https://arxiv.org/abs/2101.00001v2"),
            Reference("arxiv", "2101.00002", "https://arxiv.org/abs/2101.00002"),
            Reference(
                "github", "reuteras/rwreader", "https://github.com/reuteras/rwreader"
            ),
            Reference("rfc", "RFC 8446", "https://www.rfc-editor.org/rfc/rfc8446"),
            Reference("rfc", "RFC 2616", "https://www.rfc-editor.org/rfc/rfc2616"),
        ]

    def test_empty(self) -> None:
        """Empty text yields nothing."""
        assert extract_references("") == []


class TestToLinkTuples:
    """Tests for to_link_tuples."""

    def test_mixed_items(self) -> None:
        """Each supported type becomes a (label, url) tuple; others are skipped."""
        items = [
            ExtractedLink("A", "https://a", "a"),
            Attachment("file", "https://f.pdf", "document", "pdf"),
            Reference("rfc", "RFC 1", "https://r/1"),
            "not supported",
        ]
        assert to_link_tuples(items) == [
            ("A", "https://a"),
            ("[document] file", "https://f.pdf"),
            ("[rfc] RFC 1", "https://r/1"),
        ]
