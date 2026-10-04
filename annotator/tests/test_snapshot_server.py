from __future__ import annotations

import threading
from typing import TYPE_CHECKING

import pytest

from jev_annotator.server import serve
from jev_annotator.snapshot import snapshot_csp
from tests.sample import PAGE_KEY
from tests.test_server import request

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from jev_annotator.corpus import Page
    from jev_annotator.store import LabelStore


@pytest.fixture
def preview_port(corpus: Path, pages: dict[str, Page], store: LabelStore) -> Iterator[int]:
    server = serve(pages, store, {}, 0, corpus)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()
    thread.join()


def write_snapshot(corpus: Path) -> Path:
    path = corpus / "html" / "ec" / "example.html"
    path.parent.mkdir(parents=True)
    path.write_text('<html><head></head><script>bad()</script><input name="ok">', encoding="utf-8")
    return path


@pytest.mark.parametrize("query", ["", "&styles=1", "&styles=0"])
def test_snapshot_headers_and_sanitization(preview_port: int, corpus: Path, query: str) -> None:
    write_snapshot(corpus)
    status, headers, body = request(preview_port, "GET", f"/snapshot?key={PAGE_KEY}{query}")
    assert status == 200
    assert headers["Content-Type"] == "text/html; charset=utf-8"
    assert headers["Content-Security-Policy"] == snapshot_csp(styles=query != "&styles=0")
    assert headers["Referrer-Policy"] == "no-referrer"
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Cache-Control"] == "no-store"
    assert body == b'<html><head><base href="https://example.test/entry"></head><input name="ok">'


def test_page_snapshot_flag_tracks_file(preview_port: int, corpus: Path) -> None:
    _, headers, page = request(preview_port, "GET", f"/api/page?key={PAGE_KEY}")
    assert isinstance(page, dict)
    assert page["snapshot"] is False
    assert "frame-src 'self'" in headers["Content-Security-Policy"]
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    path = write_snapshot(corpus)
    _, _, page = request(preview_port, "GET", f"/api/page?key={PAGE_KEY}")
    assert isinstance(page, dict)
    assert page["snapshot"] is True
    path.unlink()
    _, _, page = request(preview_port, "GET", f"/api/page?key={PAGE_KEY}")
    assert isinstance(page, dict)
    assert page["snapshot"] is False


@pytest.mark.parametrize("key", [PAGE_KEY, "ec/unknown.json", "../secret.json", ""])
def test_unknown_snapshots_return_json_404(preview_port: int, key: str) -> None:
    status, headers, body = request(preview_port, "GET", f"/snapshot?key={key}")
    assert status == 404
    assert headers["Content-Type"] == "application/json; charset=utf-8"
    assert body == {"error": "unknown snapshot"}
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]


def test_snapshot_checks_host(preview_port: int, corpus: Path) -> None:
    write_snapshot(corpus)
    status, _, body = request(
        preview_port, "GET", f"/snapshot?key={PAGE_KEY}", headers={"Host": "evil.test"}
    )
    assert (status, body) == (421, {"error": "unexpected Host header"})


def test_existing_file_for_unknown_page_is_not_served(preview_port: int, corpus: Path) -> None:
    path = write_snapshot(corpus)
    path.rename(path.with_name("unknown.html"))
    assert request(preview_port, "GET", "/snapshot?key=ec/unknown.json")[0] == 404


def test_snapshot_rejects_symlinks_outside_html(
    preview_port: int, corpus: Path, tmp_path: Path
) -> None:
    path = write_snapshot(corpus)
    outside = tmp_path / "secret.html"
    outside.write_text("secret", encoding="utf-8")
    path.unlink()
    path.symlink_to(outside)
    assert request(preview_port, "GET", f"/snapshot?key={PAGE_KEY}")[0] == 404
    _, _, page = request(preview_port, "GET", f"/api/page?key={PAGE_KEY}")
    assert isinstance(page, dict)
    assert page["snapshot"] is False
