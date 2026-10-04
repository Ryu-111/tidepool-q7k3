from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from jev_annotator.corpus import Page, load_corpus
from jev_annotator.store import LabelStore
from tests.sample import PAGE

if TYPE_CHECKING:
    from pathlib import Path


@pytest.fixture
def corpus(tmp_path: Path) -> Path:
    root = tmp_path / "corpus"
    (root / "raw" / "ec").mkdir(parents=True)
    (root / "raw" / "ec" / "example.json").write_text(json.dumps(PAGE), encoding="utf-8")
    (root / "eval").mkdir()
    (root / "eval" / "usable.txt").write_text("raw/ec/example.json\n", encoding="utf-8")
    return root


@pytest.fixture
def pages(corpus: Path) -> dict[str, Page]:
    return load_corpus(corpus, corpus / "eval" / "usable.txt")


@pytest.fixture
def store(tmp_path: Path) -> LabelStore:
    return LabelStore(tmp_path / "labels" / "labels.json")
