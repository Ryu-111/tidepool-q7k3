"""Loopback-only HTTP server for the annotation UI.

The corpus holds third-party page text, so the server only binds to loopback, checks ``Host``
(against DNS rebinding) and ``Origin`` plus a JSON content type on writes (against cross-site
requests), and sends a strict Content-Security-Policy.
"""

from __future__ import annotations

import json
import mimetypes
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING, ClassVar, Final, override
from urllib.parse import parse_qs, urlsplit

from jev_annotator import api
from jev_annotator.snapshot import sanitize, snapshot_csp, snapshot_path

if TYPE_CHECKING:
    from pathlib import Path

    from jev_annotator.corpus import Page
    from jev_annotator.store import LabelStore

MAX_BODY: Final = 16 * 1024
LOOPBACK_HOSTS: Final = frozenset({"127.0.0.1", "localhost"})
SECURITY_HEADERS: Final = {
    "Content-Security-Policy": (
        "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; "
        "img-src 'self'; frame-src 'self'; base-uri 'none'; "
        "form-action 'none'; frame-ancestors 'none'"
    ),
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-store",
}


def static_files(*directories: Path) -> dict[str, Path]:
    """Map ``/static/<name>`` to the top-level files of ``directories`` (later ones win)."""
    files: dict[str, Path] = {}
    for directory in directories:
        if directory.is_dir():
            files.update({p.name: p for p in sorted(directory.iterdir()) if p.is_file()})
    return files


type Writer = Callable[[Mapping[str, Page], LabelStore, object], api.Json]
WRITERS: Final[dict[str, Writer]] = {"/api/label": api.put_label, "/api/done": api.put_done}


@dataclass(frozen=True, slots=True)
class Context:
    """What a request handler serves."""

    pages: Mapping[str, Page]
    store: LabelStore
    files: Mapping[str, Path]
    corpus: Path | None = None


class AnnotatorHandler(BaseHTTPRequestHandler):
    """Routes requests; ``make_handler`` binds a ``Context`` to a subclass."""

    context: ClassVar[Context]
    server_version = "jev-annotator"
    sys_version = ""

    @override
    def log_message(self, format: str, *args: object) -> None:
        """Keep the console quiet; requests carry nothing worth logging."""

    def _send(
        self, status: HTTPStatus, body: bytes, content_type: str, *, csp: str | None = None
    ) -> None:
        self.send_response(status)
        for name, value in SECURITY_HEADERS.items():
            self.send_header(name, csp if name == "Content-Security-Policy" and csp else value)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: HTTPStatus, document: object) -> None:
        body = json.dumps(document, ensure_ascii=False).encode()
        self._send(status, body, "application/json; charset=utf-8")

    def _error(self, status: HTTPStatus, message: str) -> None:
        self._json(status, {"error": message})

    def _own_origin(self) -> str | None:
        host = self.headers.get("Host", "")
        name, _, port = host.rpartition(":")
        address = self.server.server_address
        own_port = address[1] if isinstance(address, tuple) else None
        if name in LOOPBACK_HOSTS and port == str(own_port):
            return f"http://{host}"
        return None

    def do_GET(self) -> None:
        """Serve the UI, its assets and the read-only API."""
        if self._own_origin() is None:
            self._error(HTTPStatus.MISDIRECTED_REQUEST, "unexpected Host header")
            return
        url = urlsplit(self.path)
        context = self.context
        try:
            if url.path == "/api/state":
                self._json(HTTPStatus.OK, api.state(context.pages, context.store))
            elif url.path == "/api/page":
                key = parse_qs(url.query).get("key", [""])[0]
                detail = api.page_detail(context.pages, context.store, key)
                file = self._snapshot_file(key)
                detail["snapshot"] = file is not None and file.is_file()
                self._json(HTTPStatus.OK, detail)
            elif url.path == "/snapshot":
                query = parse_qs(url.query)
                self._snapshot(
                    query.get("key", [""])[0], styles=query.get("styles", ["1"])[0] != "0"
                )
            else:
                self._static(url.path)
        except api.ApiError as error:
            self._error(error.status, error.message)

    def _snapshot_file(self, key: str) -> Path | None:
        corpus = self.context.corpus
        return (
            snapshot_path(corpus, key) if corpus is not None and key in self.context.pages else None
        )

    def _snapshot(self, key: str, *, styles: bool) -> None:
        file = self._snapshot_file(key)
        try:
            if file is None:
                raise FileNotFoundError
            html = file.read_text(encoding="utf-8", errors="replace")
        except OSError as error:
            raise api.ApiError(HTTPStatus.NOT_FOUND, "unknown snapshot") from error
        body = sanitize(html, self.context.pages[key].url).encode()
        self._send(HTTPStatus.OK, body, "text/html; charset=utf-8", csp=snapshot_csp(styles=styles))

    def _static(self, path: str) -> None:
        name = "index.html" if path == "/" else path.removeprefix("/static/")
        is_static = path == "/" or path.startswith("/static/")
        file = self.context.files.get(name) if is_static else None
        if file is None:
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        content_type = mimetypes.guess_type(file.name)[0] or "application/octet-stream"
        if content_type.startswith("text/") or content_type.endswith("javascript"):
            content_type += "; charset=utf-8"
        self._send(HTTPStatus.OK, file.read_bytes(), content_type)

    def _read_json(self) -> object:
        content_type = self.headers.get("Content-Type", "")
        if content_type.split(";")[0].strip().lower() != "application/json":
            raise api.ApiError(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "send application/json")
        length_header = self.headers.get("Content-Length", "0")
        length = int(length_header) if length_header.isdigit() else 0
        if not 0 < length <= MAX_BODY:
            raise api.ApiError(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "body size out of range")
        try:
            decoded: object = json.loads(self.rfile.read(length))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise api.ApiError(HTTPStatus.BAD_REQUEST, "invalid JSON") from error
        return decoded

    def do_PUT(self) -> None:
        """Apply one change to the labels."""
        origin = self._own_origin()
        if origin is None or self.headers.get("Origin", origin) != origin:
            self._error(HTTPStatus.FORBIDDEN, "cross-origin write refused")
            return
        writer = WRITERS.get(urlsplit(self.path).path)
        if writer is None:
            self._error(HTTPStatus.NOT_FOUND, "not found")
            return
        try:
            body = self._read_json()
            self._json(HTTPStatus.OK, writer(self.context.pages, self.context.store, body))
        except api.ApiError as error:
            self._error(error.status, error.message)


def make_handler(
    pages: Mapping[str, Page],
    store: LabelStore,
    files: Mapping[str, Path],
    corpus: Path | None = None,
) -> type[AnnotatorHandler]:
    """Build a handler class bound to one corpus, label store and set of static files."""

    class Bound(AnnotatorHandler):
        context = Context(pages, store, files, corpus)

    return Bound


def serve(
    pages: Mapping[str, Page],
    store: LabelStore,
    files: Mapping[str, Path],
    port: int,
    corpus: Path | None = None,
) -> ThreadingHTTPServer:
    """Create (but do not start) the server on ``127.0.0.1:port``; port 0 picks a free one."""
    return ThreadingHTTPServer(("127.0.0.1", port), make_handler(pages, store, files, corpus))
