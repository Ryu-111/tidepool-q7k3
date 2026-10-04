from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jev_annotator.__main__ import default_corpus, main
from jev_annotator.report import ReportError, render, score
from jev_annotator.store import field_key
from tests.sample import PAGE_KEY

if TYPE_CHECKING:
    from pathlib import Path

    from jev_annotator.corpus import Page
    from jev_annotator.store import LabelStore


def label_all(store: LabelStore) -> None:
    # Raw indexes 1 (姓), 3 (datetime-local), 4 (都道府県), 5 (メール); form 1 index 0 (search).
    for (form, index), kind in {
        (0, 1): "FAMILY",
        (0, 3): "OTHER",
        (0, 4): "REGION",
        (0, 5): "EMAIL",
        (1, 0): "OTHER",
    }.items():
        store.put(field_key(PAGE_KEY, form, index), kind, unsure=False, note="", fingerprint="")


def test_probe_format_skips_types_to_tsv_drops(pages: dict[str, Page], store: LabelStore) -> None:
    label_all(store)
    store.put(field_key(PAGE_KEY, 0, 5), "EMAIL", unsure=True, note="", fingerprint="")
    # to_tsv.py drops datetime-local, so its index 2 is raw index 4 and 3 is raw index 5.
    lines = [
        f"raw/{PAGE_KEY}#0\t0\tFULL_NAME\tTEXT\tlabel=姓",
        f"raw/{PAGE_KEY}#0\t1\tUNKNOWN\tLIST\tlabel=住所",
        f"raw/{PAGE_KEY}#0\t2\tEMAIL\tEMAIL\tlabel=メール",
        f"raw/{PAGE_KEY}#1\t0\tCITY\tTEXT\tlabel=検索",
        "raw/ec/other.json#0\t0\tEMAIL\tTEXT\tlabel=x",
    ]
    result = score(pages, store.labels(), lines)["probe"]
    assert (result.correct, result.wrong, result.missed, result.spurious) == (0, 1, 1, 1)
    text = render({"probe": result})
    assert "FAMILY -> FULL_NAME" in text
    assert "REGION -> UNKNOWN" in text


def test_jev_format_scores_each_column(pages: dict[str, Page], store: LabelStore) -> None:
    label_all(store)
    header = "page\tform\tno\tlocal\tjev\tconf\tfinal\tsource"
    lines = [
        header,
        f"{PAGE_KEY}\t0\t0\tFAMILY\t\t\tFAMILY\tlocal",
        f"{PAGE_KEY}\t0\t1\tUNKNOWN\tUNKNOWN\t0.9\tUNKNOWN\tnone",
        f"{PAGE_KEY}\t0\t2\tUNKNOWN\tREGION\t0.9\tREGION\tjev",
    ]
    scores = score(pages, store.labels(), lines)
    assert scores["local"].correct == 2
    assert scores["local"].missed == 1
    assert scores["final"].correct == 3


def test_bad_prediction_files_are_reported(pages: dict[str, Page], store: LabelStore) -> None:
    label_all(store)
    with pytest.raises(ReportError, match="CorpusEval"):
        score(pages, store.labels(), ["nonsense"])
    with pytest.raises(ReportError, match="beyond"):
        score(pages, store.labels(), [f"raw/{PAGE_KEY}#0\t9\tEMAIL"])
    assert score(pages, store.labels(), []) == {}
    assert "No labelled field" in render({})


def test_cli_report(
    corpus: Path,
    tmp_path: Path,
    store: LabelStore,
    capsys: pytest.CaptureFixture[str],
) -> None:
    label_all(store)
    predictions = tmp_path / "pred.tsv"
    predictions.write_text(f"raw/{PAGE_KEY}#0\t0\tFAMILY\tTEXT\n", encoding="utf-8")
    args = ["--corpus", str(corpus), "--labels", str(store.path)]
    assert main([*args, "report", str(predictions)]) == 0
    assert "[probe] 1 labelled fields" in capsys.readouterr().out
    assert main([*args, "report", str(tmp_path / "missing.tsv")]) == 1
    assert "jev-annotator:" in capsys.readouterr().err


def test_default_corpus_falls_back_to_the_main_checkout(tmp_path: Path) -> None:
    main_root = tmp_path / "repo"
    (main_root / "probe" / "corpus" / "raw").mkdir(parents=True)
    worktree = main_root / ".claude" / "worktrees" / "w"
    (worktree / "probe" / "corpus").mkdir(parents=True)  # tracked scripts only, no raw/
    assert default_corpus(main_root) == main_root / "probe" / "corpus"
    assert default_corpus(worktree) == worktree / "probe" / "corpus"
    (worktree / ".git").write_text(f"gitdir: {main_root}/.git/worktrees/w\n", encoding="utf-8")
    assert default_corpus(worktree) == main_root / "probe" / "corpus"
    (worktree / ".git").write_text(f"gitdir: {tmp_path}/elsewhere\n", encoding="utf-8")
    assert default_corpus(worktree) == worktree / "probe" / "corpus"
