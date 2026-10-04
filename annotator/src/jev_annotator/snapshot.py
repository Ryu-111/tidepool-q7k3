"""Sanitize local rendered pages for a script-free, sandboxed preview."""

from __future__ import annotations

from html import escape
from html.parser import HTMLParser
from pathlib import Path
from typing import Final, override
from unicodedata import category

_DROP: Final = frozenset(
    {
        "script",
        "noscript",
        "template",
        "iframe",
        "frame",
        "frameset",
        "object",
        "embed",
        "applet",
        "portal",
        "base",
    }
)
_VOID: Final = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
        "frame",
    }
)
_URL_ATTRS: Final = frozenset({"href", "src", "action", "xlink:href"})


def snapshot_path(corpus: Path, key: str) -> Path | None:
    """Map a corpus key to HTML, refusing traversal and escaping symlinks."""
    relative = Path(key)
    if relative.suffix != ".json" or len(relative.parts) != 2 or ".." in relative.parts:  # noqa: PLR2004 -- category/name key
        return None
    root = (corpus / "html").resolve()
    path = (root / relative.with_suffix(".html")).resolve()
    return path if path.is_relative_to(root) else None


def _safe_attribute(tag: str, name: str, value: str | None) -> bool:
    if name.startswith("on") or name in {"srcdoc", "formaction", "ping"}:
        return False
    if name not in _URL_ATTRS or value is None:
        return True
    normalized = "".join(char for char in value.strip() if category(char) != "Cc").casefold()
    if tag == "img" and name == "src" and normalized.startswith("data:image/"):
        return True
    return not normalized.startswith(("javascript:", "vbscript:", "data:"))


def _drop(tag: str, attrs: list[tuple[str, str | None]]) -> bool:
    attributes = dict(attrs)
    if tag == "meta":
        return (attributes.get("http-equiv") or "").strip().casefold() == "refresh"
    if tag == "link":
        return "stylesheet" not in (attributes.get("rel") or "").casefold().split()
    return tag in _DROP


class _Sanitizer(HTMLParser):
    """Serialize parsed HTML with active content removed and one trusted base."""

    def __init__(self, source_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.blocked: list[str] = []
        self.base = f'<base href="{escape(source_url, quote=True)}">'
        self.has_head = False
        self.head_position = 0

    @override
    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if self.blocked or _drop(tag, attrs):
            if tag not in _VOID:
                self.blocked.append(tag)
            return
        rendered = "".join(
            f" {name}" if value is None else f' {name}="{escape(value, quote=True)}"'
            for name, value in attrs
            if _safe_attribute(tag, name, value)
        )
        self.parts.append(f"<{tag}{rendered}>")
        if tag == "head" and not self.has_head:
            self.parts.append(self.base)
            self.has_head = True
        elif tag == "html":
            self.head_position = len(self.parts)

    @override
    def handle_startendtag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.handle_starttag(tag, attrs)
        if tag not in _VOID:
            self.handle_endtag(tag)

    @override
    def handle_endtag(self, tag: str) -> None:
        if self.blocked:
            if tag in self.blocked:
                del self.blocked[len(self.blocked) - 1 - self.blocked[::-1].index(tag) :]
        elif tag not in _DROP and tag not in _VOID:
            self.parts.append(f"</{tag}>")

    @override
    def handle_data(self, data: str) -> None:
        if not self.blocked:
            self.parts.append(escape(data, quote=False))

    @override
    def handle_decl(self, decl: str) -> None:
        if not self.blocked and decl.casefold() == "doctype html":
            self.parts.append("<!doctype html>")
            self.head_position = len(self.parts)

    def result(self) -> str:
        """Insert a missing head without changing the order of controls."""
        if not self.has_head:
            self.parts.insert(self.head_position, f"<head>{self.base}</head>")
        return "".join(self.parts)


def sanitize(html: str, source_url: str) -> str:
    """Remove active HTML and preserve controls in document order."""
    parser = _Sanitizer(source_url)
    parser.feed(html)
    parser.close()
    return parser.result()


def snapshot_csp(*, styles: bool = True) -> str:
    """Allow HTTPS presentation assets only when online styles are enabled."""
    remote = " https:" if styles else ""
    return (
        f"sandbox allow-same-origin; default-src 'none'; style-src 'unsafe-inline'{remote}; "
        f"img-src{remote} data:; font-src{remote} data:; form-action 'none'; "
        "base-uri https:; frame-ancestors 'self'"
    )
