from __future__ import annotations

import json
import os
import re
from pathlib import Path

import pytest

from jev_annotator.corpus import CorpusError, Page, load_corpus, parse_page
from jev_annotator.kinds import KINDS, OTHER, mask_of, same_answer
from jev_annotator.store import LabelStore, StoreError, field_key
from tests.sample import PAGE_KEY

CLIENTS = Path(os.environ.get("JEV_CLIENTS_DIR") or Path(__file__).resolve().parents[2] / "clients")
KINDS_TS = CLIENTS / "apps/browser/src/autofill/jev/jev-kinds.ts"


def test_load_keeps_raw_indexes_and_drops_unfillable_controls(pages: dict[str, Page]) -> None:
    page = pages[PAGE_KEY]
    assert page.host == "example.test"
    assert [f.index for f in page.forms[0].fields] == [1, 3, 4, 5]
    assert page.forms[1].outside_form
    assert page.field_count == 5
    select = page.forms[0].fields[2]
    assert select.options == ("選択", "東京都")
    assert select.required


def test_load_without_page_list_reads_all_raw_files(corpus: Path) -> None:
    assert list(load_corpus(corpus)) == [PAGE_KEY]


def test_load_rejects_a_list_entry_outside_raw(corpus: Path, tmp_path: Path) -> None:
    (tmp_path / "secret.json").write_text("{}", encoding="utf-8")
    listing = corpus / "eval" / "bad.txt"
    listing.write_text("../secret.json\n", encoding="utf-8")
    with pytest.raises(CorpusError, match="outside"):
        load_corpus(corpus, listing)


def test_load_reports_missing_corpus_and_bad_json(tmp_path: Path, corpus: Path) -> None:
    with pytest.raises(CorpusError, match="no corpus"):
        load_corpus(tmp_path / "nowhere")
    (corpus / "raw" / "ec" / "broken.json").write_text("{", encoding="utf-8")
    with pytest.raises(CorpusError, match=r"broken\.json"):
        load_corpus(corpus)


@pytest.mark.parametrize(
    "document",
    [[], {"forms": "x"}, {"forms": [1]}, {"forms": [{"fields": None}]}],
)
def test_parse_rejects_malformed_documents(document: object) -> None:
    with pytest.raises(CorpusError):
        parse_page("ec/x.json", document)


def test_kind_masks_treat_other_as_unknown_and_era_year_as_year() -> None:
    assert same_answer(OTHER, "UNKNOWN")
    assert same_answer("BIRTH_ERA_YEAR", "BIRTH_YEAR")
    assert not same_answer("POSTAL", "POSTAL_1")
    with pytest.raises(ValueError, match="unknown kind"):
        mask_of("NOPE")


@pytest.mark.skipif(not KINDS_TS.is_file(), reason="clients/ checkout not present")
def test_kind_names_match_the_chrome_extension() -> None:
    source = KINDS_TS.read_text(encoding="utf-8")
    block = source[source.index("KIND_MASKS = {") : source.index("} as const")]
    names = re.findall(r"^\s+([A-Z_0-9]+):", block, flags=re.MULTILINE)
    assert {k.name for k in KINDS} - {OTHER} == set(names) - {"UNKNOWN"}


def test_store_round_trips_and_writes_atomically(store: LabelStore) -> None:
    key = field_key(PAGE_KEY, 0, 1)
    store.put(key, "FAMILY", unsure=True, note=" check ", fingerprint="abc")
    store.set_done(PAGE_KEY, done=True)
    reopened = LabelStore(store.path)
    label = reopened.labels()[key]
    assert (label.kind, label.unsure, label.note, label.fingerprint) == (
        "FAMILY",
        True,
        "check",
        "abc",
    )
    assert reopened.done_pages() == {PAGE_KEY}
    assert [p.name for p in store.path.parent.iterdir()] == ["labels.json"]
    reopened.clear(key)
    reopened.set_done(PAGE_KEY, done=False)
    assert LabelStore(store.path).labels() == {}
    assert LabelStore(store.path).done_pages() == frozenset()


def test_store_rejects_bad_changes(store: LabelStore) -> None:
    with pytest.raises(StoreError, match="unknown kind"):
        store.put("k", "NOPE", unsure=False, note="", fingerprint="f")
    with pytest.raises(StoreError, match="longer"):
        store.put("k", "EMAIL", unsure=False, note="x" * 501, fingerprint="f")
    assert not store.path.exists()


@pytest.mark.parametrize(
    "content",
    [
        "{",
        json.dumps({"version": 2, "labels": {}}),
        json.dumps({"version": 1, "labels": []}),
        json.dumps({"version": 1, "labels": {"k": {"kind": "NOPE"}}, "done_pages": []}),
        json.dumps({"version": 1, "labels": {"k": 3}, "done_pages": []}),
        json.dumps({"version": 1, "labels": {}, "done_pages": [1]}),
    ],
)
def test_store_refuses_a_corrupt_file(tmp_path: Path, content: str) -> None:
    path = tmp_path / "labels.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(StoreError):
        LabelStore(path)
