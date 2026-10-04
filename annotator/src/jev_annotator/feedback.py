"""Validate value-free correction exports and expose their fills as corpus pages."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Final
from urllib.parse import urlsplit
from uuid import UUID

from jev_annotator.corpus import Field, Form, Page, Recorded, fingerprint
from jev_annotator.kinds import BY_NAME, UNKNOWN

if TYPE_CHECKING:
    from pathlib import Path

OUTCOMES: Final = ("kept", "edited", "cleared", "typed")
_SOURCES: Final = ("local", "jev", "none")
_TEXT_KEYS: Final = (
    "type",
    "caption",
    "ariaLabel",
    "placeholder",
    "name",
    "htmlId",
    "context",
    "group",
    "autocomplete",
)
_RECORD_KEYS: Final = frozenset(
    {"fill", "at", "origin", "id", "kind", "source", "confidence", "filled", "outcome", "field"},
)
_MAX_TEXT: Final = 200
_MAX_INTEGER: Final = (1 << 53) - 1
_ORIGIN: Final = re.compile(r"https://(?:[A-Za-z0-9._-]+|\[[0-9a-fA-F:.]+\])(?::[0-9]+)?")


class FeedbackError(ValueError):
    """The export is not a version 1 feedback document."""


@dataclass(frozen=True, slots=True)
class Feedback:
    """Imported pages and the number of malformed records left out."""

    pages: dict[str, Page]
    skipped: int


def _object(value: object, keys: frozenset[str]) -> dict[str, object]:
    if not isinstance(value, dict) or value.keys() != keys:
        msg = "unexpected object shape"
        raise ValueError(msg)
    return {str(key): item for key, item in value.items()}


def _text(value: object) -> str:
    if not isinstance(value, str) or len(value) > _MAX_TEXT:
        msg = "expected a string of at most 200 characters"
        raise ValueError(msg)
    return value


def _integer(value: object) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or abs(value) > _MAX_INTEGER:
        msg = "expected a safe integer"
        raise ValueError(msg)
    return value


def _choice(value: object, choices: tuple[str, ...]) -> str:
    text = _text(value)
    if text not in choices:
        msg = "unknown choice"
        raise ValueError(msg)
    return text


def _confidence(value: object) -> float | None:
    if value is None:
        return None
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        msg = "expected confidence between 0 and 1 or null"
        raise ValueError(msg)
    return float(value)


def _origin(value: object) -> tuple[str, str]:
    text = _text(value)
    url = urlsplit(text)
    if _ORIGIN.fullmatch(text) is None or not url.hostname:
        msg = "expected an HTTPS origin"
        raise ValueError(msg)
    # Accessing port also rejects malformed or out-of-range ports.
    if url.port == 0:
        msg = "invalid origin port"
        raise ValueError(msg)
    return text, url.hostname


def _field(raw: object, index: int, recorded: Recorded) -> Field:
    descriptor = _object(raw, frozenset((*_TEXT_KEYS, "maxLength", "options")))
    text = {key: _text(descriptor[key]) for key in _TEXT_KEYS}
    maximum = _integer(descriptor["maxLength"])
    options = descriptor["options"]
    if not isinstance(options, list):
        msg = "expected an options list"
        raise TypeError(msg)
    labels = tuple(_text(option) for option in options)
    return Field(
        index=index,
        tag="select" if text["type"] == "select" else "input",
        type=text["type"],
        name=text["name"],
        html_id=text["htmlId"],
        label=text["caption"],
        near=(text["context"],),
        legend=text["group"],
        placeholder=text["placeholder"],
        autocomplete=text["autocomplete"],
        aria_label=text["ariaLabel"],
        title="",
        maxlength=str(maximum) if maximum >= 0 else "",
        inputmode="",
        pattern="",
        required=False,
        options=labels,
        fingerprint=fingerprint(descriptor),
        recorded=recorded,
    )


def _record(value: object) -> Page:
    raw = _object(value, _RECORD_KEYS)
    fill = _text(raw["fill"])
    if str(UUID(fill)) != fill:
        msg = "expected a canonical fill UUID"
        raise ValueError(msg)
    at, index = _integer(raw["at"]), _integer(raw["id"])
    if at < 0 or index < 0 or not isinstance(raw["filled"], bool):
        msg = "invalid timestamp, index or filled flag"
        raise ValueError(msg)
    url, host = _origin(raw["origin"])
    recorded = Recorded(
        _choice(raw["kind"], (*BY_NAME, UNKNOWN)),
        _choice(raw["source"], _SOURCES),
        _confidence(raw["confidence"]),
        _choice(raw["outcome"], OUTCOMES),
    )
    return Page(
        f"feedback/{fill}",
        "feedback",
        host,
        url,
        datetime.fromtimestamp(at / 1000, UTC).isoformat(),
        (Form(number=0, outside_form=False, fields=(_field(raw["field"], index, recorded),)),),
    )


def parse_feedback(raw: object) -> Feedback:
    """Reject invalid documents; skip malformed records, duplicates and conflicting fills.

    Raises:
        FeedbackError: If the top-level shape or version is wrong.
    """
    try:
        document = _object(raw, frozenset({"version", "outcomes"}))
    except ValueError as error:
        msg = f"feedback: {error}"
        raise FeedbackError(msg) from error
    version, outcomes = document["version"], document["outcomes"]
    if not isinstance(version, int) or isinstance(version, bool) or version != 1:
        msg = "feedback: expected version 1"
        raise FeedbackError(msg)
    if not isinstance(outcomes, list):
        msg = "feedback: expected an outcomes list"
        raise FeedbackError(msg)
    pages: dict[str, Page] = {}
    skipped = 0
    for value in outcomes:
        try:
            page = _record(value)
        except (ValueError, TypeError, OverflowError, OSError):
            skipped += 1
            continue
        previous = pages.get(page.key)
        if previous is not None:
            fields = previous.forms[0].fields
            new = page.forms[0].fields[0]
            if previous.url != page.url or any(item.index == new.index for item in fields):
                skipped += 1
                continue
            page = Page(
                page.key,
                page.category,
                page.host,
                page.url,
                previous.fetched_at,
                (Form(number=0, outside_form=False, fields=(*fields, new)),),
            )
        pages[page.key] = page
    return Feedback(pages, skipped)


def load_feedback(path: Path) -> Feedback:
    """Read a correction export without including its contents in errors.

    Raises:
        FeedbackError: If the document cannot be decoded or validated.
    """
    try:
        decoded: object = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, RecursionError) as error:
        msg = f"{path}: invalid feedback JSON"
        raise FeedbackError(msg) from error
    return parse_feedback(decoded)
