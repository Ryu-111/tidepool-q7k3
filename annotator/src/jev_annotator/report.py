"""Score classifier output against the labels.

Two prediction formats are read, each mapped back to the raw field index by replaying the
classifier's own skip rule:

- ``CorpusEval`` (probe Policy): no header; ``raw/<page>#<form>``, index, kind, ... per line.
  Its index counts only the types ``eval/to_tsv.py`` keeps.
- ``jev-eval.ts`` (Chrome extension): header line starting with ``page``; columns ``local``,
  ``jev`` and ``final`` are scored separately. Its index counts the fields ``corpus.SKIPPED_TYPES``
  keeps, which is also the annotator's field list.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Final

from jev_annotator.corpus import SKIPPED_TYPES
from jev_annotator.feedback import OUTCOMES
from jev_annotator.kinds import OTHER, UNKNOWN, mask_of
from jev_annotator.store import Label, field_key

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from jev_annotator.corpus import Page

# Types eval/to_tsv.py passes to CorpusEval.
_PROBE_TYPES: Final = frozenset(
    {"text", "tel", "email", "number", "password", "date", "select", "textarea", "search", "url"},
)
_MIN_PROBE_COLUMNS: Final = 3
_JEV_COLUMNS: Final = ("local", "jev", "final")


class ReportError(ValueError):
    """The prediction file is not in a known format."""


@dataclass(slots=True)
class Score:
    """Outcome counts of one prediction column against the labels.

    ``wrong`` (a different profile value would be filled) is the costly error; ``missed`` leaves
    a profile field empty; ``spurious`` fills a field that should stay empty.
    """

    correct: int = 0
    wrong: int = 0
    missed: int = 0
    spurious: int = 0
    confusions: Counter[tuple[str, str]] = field(default_factory=Counter)

    @property
    def total(self) -> int:
        """Labelled fields the prediction file covered."""
        return self.correct + self.wrong + self.missed + self.spurious

    def add(self, label: str, predicted: str) -> None:
        """Count one labelled field."""
        expected, got = mask_of(label), mask_of(predicted or UNKNOWN)
        if expected == got:
            self.correct += 1
            return
        self.confusions[label, predicted or UNKNOWN] += 1
        if expected == 0:
            self.spurious += 1
        elif got == 0:
            self.missed += 1
        else:
            self.wrong += 1


def _index_maps(pages: Mapping[str, Page]) -> dict[tuple[str, int], tuple[list[int], list[int]]]:
    """Per (page, form): raw indexes in CorpusEval order and in jev-eval order."""
    maps: dict[tuple[str, int], tuple[list[int], list[int]]] = {}
    for page in pages.values():
        for form in page.forms:
            probe = [f.index for f in form.fields if f.type in _PROBE_TYPES]
            jev = [f.index for f in form.fields if f.type not in SKIPPED_TYPES]
            maps[page.key, form.number] = (probe, jev)
    return maps


def _probe_rows(lines: Iterable[list[str]]) -> Iterable[tuple[str, int, int, dict[str, str]]]:
    for cells in lines:
        if len(cells) < _MIN_PROBE_COLUMNS or "#" not in cells[0]:
            msg = f"not a CorpusEval line: {cells[:3]}"
            raise ReportError(msg)
        page, _, form = cells[0].removeprefix("raw/").rpartition("#")
        yield page, int(form), int(cells[1]), {"probe": cells[2]}


def _jev_rows(
    header: list[str],
    lines: Iterable[list[str]],
) -> Iterable[tuple[str, int, int, dict[str, str]]]:
    columns = {name: header.index(name) for name in ("page", "form", "no", *_JEV_COLUMNS)}
    for cells in lines:
        kinds = {name: cells[columns[name]] for name in _JEV_COLUMNS}
        yield cells[columns["page"]], int(cells[columns["form"]]), int(cells[columns["no"]]), kinds


def score(
    pages: Mapping[str, Page],
    labels: Mapping[str, Label],
    prediction_lines: list[str],
) -> dict[str, Score]:
    """Score each prediction column; unsure labels and unlabelled fields are left out.

    Raises:
        ReportError: If the file format is unknown or a line names an unknown form.
    """
    rows = [line.split("\t") for line in prediction_lines if line.strip()]
    if not rows:
        return {}
    jev_format = rows[0][0] == "page"
    entries = _jev_rows(rows[0], rows[1:]) if jev_format else _probe_rows(rows)
    maps = _index_maps(pages)
    scores: dict[str, Score] = {}
    for page, form, position, kinds in entries:
        order = maps.get((page, form))
        if order is None:
            continue  # a page outside the annotated set
        indexes = order[1] if jev_format else order[0]
        if position >= len(indexes):
            msg = f"{page}#{form}: index {position} beyond {len(indexes)} fields"
            raise ReportError(msg)
        label = labels.get(field_key(page, form, indexes[position]))
        if label is None or label.unsure:
            continue
        for column, predicted in kinds.items():
            scores.setdefault(column, Score()).add(label.kind, predicted)
    return scores


def render(scores: Mapping[str, Score], top: int = 15) -> str:
    """Plain-text summary of ``score`` output."""
    if not scores:
        return "No labelled field matched the predictions.\n"
    lines: list[str] = []
    for column, result in scores.items():
        total = result.total
        lines.append(f"[{column}] {total} labelled fields")
        for name in ("correct", "wrong", "missed", "spurious"):
            count: int = getattr(result, name)
            lines.append(f"  {name:<9}{count:>6}  {count / total:6.1%}")
        lines.append("  most frequent errors (label -> predicted):")
        lines.extend(
            f"    {count:>4}  {label} -> {predicted}"
            for (label, predicted), count in result.confusions.most_common(top)
        )
    lines.append(f"(label {OTHER} matches prediction {UNKNOWN}; unsure labels are excluded)")
    return "\n".join(lines) + "\n"


def score_feedback(
    pages: Mapping[str, Page],
    labels: Mapping[str, Label],
) -> dict[str, Score]:
    """Score recorded decisions by user action; unsure and unlabelled fields are excluded."""
    scores = {outcome: Score() for outcome in OUTCOMES}
    for page in pages.values():
        for form in page.forms:
            for control in form.fields:
                label = labels.get(field_key(page.key, form.number, control.index))
                recorded = control.recorded
                if recorded is not None and label is not None and not label.unsure:
                    scores[recorded.outcome].add(label.kind, recorded.kind)
    return scores


def render_feedback(scores: Mapping[str, Score]) -> str:
    """Overall score plus labelled and differing decisions for each user action."""
    overall = Score()
    for result in scores.values():
        overall.correct += result.correct
        overall.wrong += result.wrong
        overall.missed += result.missed
        overall.spurious += result.spurious
        overall.confusions.update(result.confusions)
    summary = render({"recorded": overall} if overall.total else {})
    lines = ["[outcomes] labelled / different"]
    lines.extend(
        f"  {outcome:<9}{result.total:>6} / {result.total - result.correct}"
        for outcome, result in scores.items()
    )
    return summary + "\n".join(lines) + "\n"
