from __future__ import annotations

import json
from datetime import UTC, datetime
from http.server import ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from jev_annotator import __main__ as cli
from jev_annotator import api
from jev_annotator.corpus import fingerprint
from jev_annotator.feedback import FeedbackError, load_feedback, parse_feedback
from jev_annotator.report import render_feedback, score_feedback
from jev_annotator.server import AnnotatorHandler
from jev_annotator.store import LabelStore, field_key

if TYPE_CHECKING:
    from pathlib import Path

    from jev_annotator.corpus import Page

FILL = "00000000-0000-4000-8000-000000000001"
SECOND_FILL = "00000000-0000-4000-8000-000000000002"
KEY = f"feedback/{FILL}"
AT = 1790000000000
DESCRIPTOR: dict[str, object] = {
    "type": "text",
    "caption": "姓",
    "ariaLabel": "名字",
    "placeholder": "試験",
    "name": "family",
    "htmlId": "family-id",
    "context": "お名前",
    "group": "登録",
    "autocomplete": "family-name",
    "maxLength": -1,
    "options": [],
}


def record(index: int = 3, /, **changes: object) -> dict[str, object]:
    return {
        "fill": FILL,
        "at": AT,
        "origin": "https://example.test",
        "id": index,
        "kind": "FAMILY",
        "source": "jev",
        "confidence": 0.93,
        "filled": True,
        "outcome": "kept",
        "field": DESCRIPTOR,
        **changes,
    }


def export(path: Path, outcomes: list[object]) -> Path:
    path.write_text(json.dumps({"version": 1, "outcomes": outcomes}), encoding="utf-8")
    return path


def test_feedback_pages_preserve_descriptors_and_raw_indexes(tmp_path: Path) -> None:
    select = DESCRIPTOR | {"type": "select", "maxLength": 12, "options": ["選択", "試験"]}
    path = export(
        tmp_path / "feedback.json",
        [
            record(),
            record(9, field=select, confidence=None, source="local"),
            record(
                1, fill=SECOND_FILL, kind="UNKNOWN", source="none", filled=False, outcome="typed"
            ),
        ],
    )
    feedback = load_feedback(path)
    assert feedback.skipped == 0
    assert list(feedback.pages) == [KEY, f"feedback/{SECOND_FILL}"]
    page = feedback.pages[KEY]
    assert (page.category, page.host, page.url) == (
        "feedback",
        "example.test",
        "https://example.test",
    )
    assert page.fetched_at == datetime.fromtimestamp(AT / 1000, UTC).isoformat()
    assert page.field_count == 2
    form = page.forms[0]
    assert form.number == 0
    assert not form.outside_form
    first, second = form.fields
    assert (first.index, second.index) == (3, 9)
    assert (first.tag, first.type, first.label, first.near, first.legend) == (
        "input",
        "text",
        "姓",
        ("お名前",),
        "登録",
    )
    assert (first.name, first.html_id, first.aria_label, first.placeholder, first.autocomplete) == (
        "family",
        "family-id",
        "名字",
        "試験",
        "family-name",
    )
    assert (first.maxlength, second.maxlength, second.tag, second.options) == (
        "",
        "12",
        "select",
        ("選択", "試験"),
    )
    assert first.fingerprint == fingerprint(DESCRIPTOR)
    assert second.fingerprint == fingerprint(select)
    assert first.recorded is not None
    assert first.recorded.kind == "FAMILY"
    assert second.recorded is not None
    assert second.recorded.confidence is None


@pytest.mark.parametrize(
    "raw",
    [
        [],
        {},
        {"version": 1},
        {"version": 1, "outcomes": [], "extra": 1},
        {"version": 2, "outcomes": []},
        {"version": True, "outcomes": []},
        {"version": 1.0, "outcomes": []},
        {"version": "1", "outcomes": []},
        {"version": 1, "outcomes": {}},
    ],
)
def test_feedback_rejects_wrong_document_shape(raw: object) -> None:
    with pytest.raises(FeedbackError, match="feedback:"):
        parse_feedback(raw)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("fill", "not-a-uuid"),
        ("fill", 3),
        ("fill", "x" * 201),
        ("at", True),
        ("at", -1),
        ("at", 1.5),
        ("at", 1 << 54),
        ("at", (1 << 53) - 1),
        ("id", True),
        ("id", -1),
        ("id", "3"),
        ("origin", "javascript:alert(1)"),
        ("origin", "http://example.test"),
        ("origin", "https://user:password@example.test"),
        ("origin", "https://example.test/path"),
        ("origin", "https://example.test?q=1"),
        ("origin", "https://example.test#x"),
        ("origin", "https://"),
        ("origin", "https://[broken"),
        ("origin", "https://example.test:65536"),
        ("origin", "https://example.test:0"),
        ("origin", "https://exa\tmple.test"),
        ("origin", "https://exa\x00mple.test"),
        ("origin", "https://example.test\\path"),
        ("origin", "https://example.test<>"),
        ("kind", "NOPE"),
        ("kind", []),
        ("source", "other"),
        ("source", None),
        ("confidence", True),
        ("confidence", "0.9"),
        ("confidence", -0.1),
        ("confidence", 1.1),
        ("confidence", float("nan")),
        ("confidence", float("inf")),
        ("filled", 1),
        ("outcome", "other"),
        ("outcome", None),
        ("field", []),
    ],
)
def test_feedback_skips_malformed_record_fields(key: str, value: object) -> None:
    feedback = parse_feedback({"version": 1, "outcomes": [record(**{key: value}), record()]})
    assert feedback.skipped == 1
    assert feedback.pages[KEY].field_count == 1


@pytest.mark.parametrize(
    "key",
    [
        "type",
        "caption",
        "ariaLabel",
        "placeholder",
        "name",
        "htmlId",
        "context",
        "group",
        "autocomplete",
    ],
)
@pytest.mark.parametrize("value", [None, 3, "x" * 201])
def test_descriptor_requires_short_strings(key: str, value: object) -> None:
    feedback = parse_feedback(
        {
            "version": 1,
            "outcomes": [record(field=DESCRIPTOR | {key: value})],
        }
    )
    assert feedback.skipped == 1
    assert feedback.pages == {}


@pytest.mark.parametrize(
    "descriptor",
    [
        {},
        DESCRIPTOR | {"extra": "x"},
        DESCRIPTOR | {"maxLength": True},
        DESCRIPTOR | {"maxLength": "12"},
        DESCRIPTOR | {"maxLength": 1 << 54},
        DESCRIPTOR | {"options": "x"},
        DESCRIPTOR | {"options": [3]},
        DESCRIPTOR | {"options": ["x" * 201]},
    ],
)
def test_descriptor_shape_and_options_are_validated(descriptor: object) -> None:
    assert parse_feedback({"version": 1, "outcomes": [record(field=descriptor)]}).skipped == 1


def test_duplicate_and_conflicting_outcomes_do_not_replace_fields() -> None:
    missing = record()
    del missing["filled"]
    feedback = parse_feedback(
        {
            "version": 1,
            "outcomes": [
                record(),
                record(),
                record(4, origin="https://other.test"),
                record(5, at=AT + 1),
                record(6),
                None,
                missing,
                record(7, value="never accepted"),
            ],
        }
    )
    assert feedback.skipped == 5
    assert [f.index for f in feedback.pages[KEY].forms[0].fields] == [3, 5, 6]
    assert feedback.pages[KEY].fetched_at == datetime.fromtimestamp(AT / 1000, UTC).isoformat()


def test_string_boundaries_and_fractional_timestamp() -> None:
    descriptor: dict[str, object] = dict.fromkeys(DESCRIPTOR, "x" * 200)
    descriptor.update({"maxLength": -2, "options": ["x" * 200]})
    page = parse_feedback(
        {
            "version": 1,
            "outcomes": [
                record(
                    at=AT + 123, confidence=1, field=descriptor, origin="https://example.test:8443"
                ),
            ],
        }
    ).pages[KEY]
    assert page.fetched_at.endswith(".123000+00:00")
    assert page.forms[0].fields[0].maxlength == ""
    assert page.forms[0].fields[0].recorded is not None


@pytest.mark.parametrize("content", [b"{", b"\xff", b"[" * 2000, b"9" * 5000])
def test_invalid_json_has_a_clear_error(tmp_path: Path, content: bytes) -> None:
    path = tmp_path / "bad.json"
    path.write_bytes(content)
    with pytest.raises(FeedbackError, match="invalid feedback JSON"):
        load_feedback(path)


def first_field(document: api.Json) -> api.Json:
    forms = document["forms"]
    assert isinstance(forms, list)
    form: object = forms[0]
    assert isinstance(form, dict)
    fields: object = form["fields"]
    assert isinstance(fields, list)
    control: object = fields[0]
    assert isinstance(control, dict)
    return {str(key): value for key, value in control.items()}


def test_api_records_and_labels_use_the_existing_store(
    pages: dict[str, Page],
    store: LabelStore,
) -> None:
    pages.update(parse_feedback({"version": 1, "outcomes": [record()]}).pages)
    result = api.page_detail(pages, store, KEY)
    assert first_field(result)["recorded"] == {
        "kind": "FAMILY",
        "source": "jev",
        "confidence": 0.93,
        "outcome": "kept",
    }
    corpus_page = next(p for p in pages.values() if p.category != "feedback")
    assert first_field(api.page_detail(pages, store, corpus_page.key))["recorded"] is None
    answer = api.put_label(pages, store, {"page": KEY, "form": 0, "index": 3, "kind": "GIVEN"})
    assert answer["answer"] == {"kind": "GIVEN", "unsure": False, "note": "", "stale": False}
    assert LabelStore(store.path).labels()[field_key(KEY, 0, 3)].kind == "GIVEN"


def labelled_feedback(tmp_path: Path, store: LabelStore) -> Path:
    path = export(
        tmp_path / "feedback.json",
        [
            record(0),
            record(1, outcome="kept", kind="UNKNOWN"),
            record(2, outcome="edited"),
            record(3, outcome="edited"),
            record(4, outcome="cleared"),
            record(5, outcome="typed", kind="UNKNOWN"),
            record(6, outcome="typed"),
            record(7),
        ],
    )
    for index, kind in enumerate(
        ["FAMILY", "OTHER", "GIVEN", "FAMILY", "OTHER", "EMAIL", "FAMILY"]
    ):
        store.put(field_key(KEY, 0, index), kind, unsure=index == 6, note="", fingerprint="")
    return path


def test_feedback_report_counts_classification_errors_by_action(
    tmp_path: Path,
    store: LabelStore,
    pages: dict[str, Page],
) -> None:
    path = labelled_feedback(tmp_path, store)
    pages.update(load_feedback(path).pages)
    scores = score_feedback(pages, store.labels())
    assert [(s.total, s.total - s.correct) for s in scores.values()] == [
        (2, 0),
        (2, 1),
        (1, 1),
        (1, 1),
    ]
    assert scores["edited"].wrong == 1
    assert scores["cleared"].spurious == 1
    assert scores["typed"].missed == 1
    text = render_feedback(scores)
    assert "[recorded] 6 labelled fields" in text
    assert "FAMILY -> UNKNOWN" not in text
    assert "EMAIL -> UNKNOWN" in text
    assert "kept          2 / 0" in text
    assert "edited        2 / 1" in text
    assert "No labelled field" in render_feedback(score_feedback({}, {}))


def test_cli_feedback_report_exit_codes(
    corpus: Path,
    tmp_path: Path,
    store: LabelStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    path = labelled_feedback(tmp_path, store)
    args = ["--corpus", str(corpus), "--labels", str(store.path)]
    assert cli.main([*args, "report-feedback", str(path)]) == 0
    captured = capsys.readouterr()
    assert "[recorded] 6 labelled fields" in captured.out
    assert "0 malformed outcomes skipped" in captured.err
    bad = tmp_path / "bad.json"
    bad.write_text('{"version":2,"outcomes":[]}', encoding="utf-8")
    assert cli.main([*args, "report-feedback", str(bad)]) == 1
    assert "expected version 1" in capsys.readouterr().err
    assert cli.main([*args, "report-feedback", str(tmp_path / "missing.json")]) == 1
    assert "jev-annotator:" in capsys.readouterr().err
    # Scoring an export needs only the export and the labels, not the corpus.
    assert (
        cli.main(
            [
                "--corpus",
                str(tmp_path / "absent"),
                "--labels",
                str(store.path),
                "report-feedback",
                str(path),
            ]
        )
        == 0
    )
    assert "[recorded] 6 labelled fields" in capsys.readouterr().out


def test_cli_serve_includes_feedback_and_counts_skipped_records(
    corpus: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    web = tmp_path / "web"
    (web / "dist").mkdir(parents=True)
    (web / "dist" / "main.js").write_text("export {};", encoding="utf-8")
    monkeypatch.setattr(cli, "_WEB", web)
    path = export(tmp_path / "feedback.json", [record(), record(kind="NOPE")])

    def stop(server: ThreadingHTTPServer) -> None:
        handler = server.RequestHandlerClass
        assert isinstance(handler, type)
        assert issubclass(handler, AnnotatorHandler)
        assert handler.context.pages[KEY].field_count == 1
        assert len(handler.context.pages) == 2
        raise KeyboardInterrupt

    monkeypatch.setattr(ThreadingHTTPServer, "serve_forever", stop)
    args = [
        "--corpus",
        str(corpus),
        "--feedback",
        str(path),
        "serve",
        "--port",
        "0",
        "--no-browser",
    ]
    assert cli.main(args) == 0
    captured = capsys.readouterr()
    assert "2 pages" in captured.out
    assert "1 malformed outcomes skipped" in captured.err
    path.write_text("[]", encoding="utf-8")
    assert cli.main(args) == 1
    assert "unexpected object shape" in capsys.readouterr().err
    monkeypatch.setattr(cli, "_WEB", tmp_path / "missing")
    assert cli.main(args) == 1
    assert "main.js is missing" in capsys.readouterr().err
