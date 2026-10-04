from __future__ import annotations

import http.client
import json
import threading
from typing import TYPE_CHECKING

import pytest

from jev_annotator.server import serve, static_files
from tests.sample import PAGE_KEY

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from jev_annotator.corpus import Page
    from jev_annotator.store import LabelStore


@pytest.fixture
def port(pages: dict[str, Page], store: LabelStore, tmp_path: Path) -> Iterator[int]:
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<!doctype html>", encoding="utf-8")
    (web / "main.js").write_text("export {};", encoding="utf-8")
    server = serve(pages, store, static_files(web, tmp_path / "missing"), 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


def request(
    port: int,
    method: str,
    path: str,
    body: object = None,
    headers: dict[str, str] | None = None,
) -> tuple[int, dict[str, str], object]:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    payload = None if body is None else json.dumps(body).encode()
    sent = {"Content-Type": "application/json"} if payload is not None else {}
    sent |= headers or {}
    connection.request(method, path, body=payload, headers=sent)
    response = connection.getresponse()
    raw = response.read()
    connection.close()
    content_type = response.getheader("Content-Type") or ""
    decoded: object = json.loads(raw) if content_type.startswith("application/json") else raw
    return response.status, dict(response.getheaders()), decoded


def test_serves_the_ui_with_a_strict_policy(port: int) -> None:
    status, headers, body = request(port, "GET", "/")
    assert status == 200
    assert body == b"<!doctype html>"
    assert "script-src 'self'" in headers["Content-Security-Policy"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    status, headers, _ = request(port, "GET", "/static/main.js")
    assert (status, headers["Content-Type"]) == (200, "text/javascript; charset=utf-8")
    assert request(port, "GET", "/static/../conftest.py")[0] == 404
    assert request(port, "GET", "/index.html")[0] == 404


def test_state_and_page_report_progress(port: int) -> None:
    status, _, state = request(port, "GET", "/api/state")
    assert status == 200
    assert isinstance(state, dict)
    assert state["pages"] == [
        {
            "category": "ec",
            "host": "example.test",
            "key": PAGE_KEY,
            "fields": 5,
            "labelled": 0,
            "done": False,
        },
    ]
    status, _, page = request(port, "GET", f"/api/page?key={PAGE_KEY}")
    assert status == 200
    assert isinstance(page, dict)
    assert page["url"] == "https://example.test/entry"
    assert request(port, "GET", "/api/page?key=../../x")[0] == 404


def test_label_put_then_clear(port: int, store: LabelStore) -> None:
    body = {"page": PAGE_KEY, "form": 0, "index": 1, "kind": "FAMILY", "note": "n"}
    status, _, result = request(port, "PUT", "/api/label", body)
    assert status == 200
    assert result == {
        "answer": {"kind": "FAMILY", "unsure": False, "note": "n", "stale": False},
        "progress": {"key": PAGE_KEY, "fields": 5, "labelled": 1, "done": False},
    }
    assert store.labels()[f"{PAGE_KEY}#0#1"].kind == "FAMILY"
    status, _, result = request(port, "PUT", "/api/label", body | {"kind": None})
    assert status == 200
    assert isinstance(result, dict)
    assert result["answer"] is None
    status, _, result = request(port, "PUT", "/api/done", {"page": PAGE_KEY, "done": True})
    assert (status, store.done_pages()) == (200, frozenset({PAGE_KEY}))


def test_page_marks_labels_whose_field_changed(port: int, store: LabelStore) -> None:
    store.put(f"{PAGE_KEY}#0#1", "FAMILY", unsure=False, note="", fingerprint="old")
    _, _, page = request(port, "GET", f"/api/page?key={PAGE_KEY}")
    assert isinstance(page, dict)
    first = page["forms"][0]["fields"][0]
    assert first["answer"]["stale"] is True


@pytest.mark.parametrize(
    ("body", "status"),
    [
        ({"page": "nope", "form": 0, "index": 1, "kind": "FAMILY"}, 404),
        ({"page": PAGE_KEY, "form": 0, "index": 0, "kind": "FAMILY"}, 404),
        ({"page": PAGE_KEY, "form": True, "index": 1, "kind": "FAMILY"}, 400),
        ({"page": PAGE_KEY, "form": 0, "index": "1", "kind": "FAMILY"}, 400),
        ({"page": PAGE_KEY, "form": 0, "index": 1, "kind": "NOPE"}, 400),
        ({"page": PAGE_KEY, "form": 0, "index": 1, "kind": 3}, 400),
        ({"page": PAGE_KEY, "form": 0, "index": 1, "kind": "EMAIL", "unsure": "yes"}, 400),
        ([], 400),
    ],
)
def test_label_rejects_invalid_requests(port: int, body: object, status: int) -> None:
    assert request(port, "PUT", "/api/label", body)[0] == status


def test_done_requires_a_boolean(port: int) -> None:
    assert request(port, "PUT", "/api/done", {"page": PAGE_KEY, "done": 1})[0] == 400


def test_writes_refuse_cross_site_and_non_json_requests(port: int, store: LabelStore) -> None:
    body = {"page": PAGE_KEY, "form": 0, "index": 1, "kind": "FAMILY"}
    evil = {"Origin": "https://evil.example"}
    assert request(port, "PUT", "/api/label", body, evil)[0] == 403
    assert request(port, "PUT", "/api/label", body, {"Host": "evil.example"})[0] == 403
    assert request(port, "GET", "/api/state", headers={"Host": "rebind.example"})[0] == 421
    assert request(port, "PUT", "/api/label", body, {"Content-Type": "text/plain"})[0] == 415
    assert request(port, "PUT", "/api/nope", body)[0] == 404
    assert store.labels() == {}


def test_writes_refuse_oversized_and_invalid_bodies(port: int) -> None:
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    connection.request(
        "PUT", "/api/label", body=b"{not json", headers={"Content-Type": "application/json"}
    )
    assert connection.getresponse().status == 400
    connection.close()
    big = {"page": PAGE_KEY, "note": "x" * 20_000}
    assert request(port, "PUT", "/api/label", big)[0] == 413
