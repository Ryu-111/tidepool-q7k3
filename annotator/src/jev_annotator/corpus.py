"""Read the value-free form structure collected under ``probe/corpus/raw``."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from pathlib import Path

# Controls nobody fills from a profile; the same set ``eval/jev-eval.ts`` drops.
SKIPPED_TYPES: Final = frozenset(
    {"hidden", "submit", "button", "reset", "image", "file", "checkbox", "radio"},
)


class CorpusError(ValueError):
    """The corpus files are missing or not in the expected shape."""


@dataclass(frozen=True, slots=True)
class Recorded:
    """The extension's value-free decision and the user's subsequent action."""

    kind: str
    source: str
    confidence: float | None
    outcome: str


@dataclass(frozen=True, slots=True)
class Field:
    """One fillable control.

    ``index`` is the position in the form's raw ``fields`` array, which stays stable whatever
    a classifier chooses to skip.
    """

    index: int
    tag: str
    type: str
    name: str
    html_id: str
    label: str
    near: tuple[str, ...]
    legend: str
    placeholder: str
    autocomplete: str
    aria_label: str
    title: str
    maxlength: str
    inputmode: str
    pattern: str
    required: bool
    options: tuple[str, ...]
    fingerprint: str
    recorded: Recorded | None = None


@dataclass(frozen=True, slots=True)
class Form:
    """The fillable controls of one ``<form>`` (or of controls outside any form)."""

    number: int
    outside_form: bool
    fields: tuple[Field, ...]


@dataclass(frozen=True, slots=True)
class Page:
    """One collected page; ``key`` is its path relative to ``raw/``."""

    key: str
    category: str
    host: str
    url: str
    fetched_at: str
    forms: tuple[Form, ...]

    @property
    def field_count(self) -> int:
        """Number of fillable controls on the page."""
        return sum(len(form.fields) for form in self.forms)


def _text(raw: dict[str, object], key: str) -> str:
    value = raw.get(key)
    return value if isinstance(value, str) else ""


def _texts(raw: dict[str, object], key: str) -> tuple[str, ...]:
    value = raw.get(key)
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str))


def _objects(raw: dict[str, object], key: str, where: str) -> list[dict[str, object]]:
    value = raw.get(key)
    if not isinstance(value, list):
        msg = f"{where}: {key!r} is not a list"
        raise CorpusError(msg)
    items: list[dict[str, object]] = []
    for item in value:
        if not isinstance(item, dict):
            msg = f"{where}: {key!r} holds a non-object"
            raise CorpusError(msg)
        items.append({str(k): v for k, v in item.items()})
    return items


def fingerprint(raw: dict[str, object]) -> str:
    """Short digest of a raw field, to notice when a labelled field changed after re-collection."""
    canonical = json.dumps(raw, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


def _field(index: int, raw: dict[str, object]) -> Field:
    return Field(
        index=index,
        tag=_text(raw, "tag"),
        type=_text(raw, "type"),
        name=_text(raw, "name"),
        html_id=_text(raw, "id"),
        label=_text(raw, "label"),
        near=_texts(raw, "near"),
        legend=_text(raw, "legend"),
        placeholder=_text(raw, "placeholder"),
        autocomplete=_text(raw, "autocomplete"),
        aria_label=_text(raw, "aria-label"),
        title=_text(raw, "title"),
        maxlength=_text(raw, "maxlength"),
        inputmode=_text(raw, "inputmode"),
        pattern=_text(raw, "pattern"),
        required=raw.get("required") is True,
        options=_texts(raw, "options"),
        fingerprint=fingerprint(raw),
    )


def parse_page(key: str, raw: object) -> Page:
    """Build a page from one decoded JSON document."""
    if not isinstance(raw, dict):
        msg = f"{key}: top level is not an object"
        raise CorpusError(msg)
    page: dict[str, object] = {str(k): v for k, v in raw.items()}
    forms: list[Form] = []
    for number, form in enumerate(_objects(page, "forms", key)):
        fields = tuple(
            _field(index, field)
            for index, field in enumerate(_objects(form, "fields", f"{key}#{number}"))
            if _text(field, "type") not in SKIPPED_TYPES
        )
        forms.append(Form(number, form.get("outside_form") is True, fields))
    return Page(
        key=key,
        category=_text(page, "category"),
        host=_text(page, "source_host"),
        url=_text(page, "source_url"),
        fetched_at=_text(page, "fetched_at"),
        forms=tuple(forms),
    )


def _listed(corpus: Path, page_list: Path) -> list[Path]:
    lines = page_list.read_text(encoding="utf-8").splitlines()
    return [corpus / line.strip() for line in lines if line.strip()]


def load_corpus(corpus: Path, page_list: Path | None = None) -> dict[str, Page]:
    """Load the pages named in ``page_list`` (paths relative to ``corpus``), or all of ``raw/``.

    Raises:
        CorpusError: If ``raw/`` is missing, a listed file lies outside it, or a file is malformed.
    """
    raw_dir = (corpus / "raw").resolve()
    if not raw_dir.is_dir():
        msg = f"no corpus at {raw_dir}"
        raise CorpusError(msg)
    paths = _listed(corpus, page_list) if page_list else sorted(raw_dir.glob("*/*.json"))
    pages: dict[str, Page] = {}
    for path in paths:
        resolved = path.resolve()
        if not resolved.is_relative_to(raw_dir):
            msg = f"{path} is outside {raw_dir}"
            raise CorpusError(msg)
        key = resolved.relative_to(raw_dir).as_posix()
        try:
            decoded: object = json.loads(resolved.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            msg = f"{key}: {error}"
            raise CorpusError(msg) from error
        pages[key] = parse_page(key, decoded)
    return pages
