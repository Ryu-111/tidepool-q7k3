"""Persist labels as one JSON file, rewritten atomically on every change."""

from __future__ import annotations

import json
import os
import tempfile
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from jev_annotator.kinds import BY_NAME

FORMAT_VERSION: Final = 1
MAX_NOTE_LENGTH: Final = 500


class StoreError(ValueError):
    """The label file or a requested change is invalid."""


@dataclass(frozen=True, slots=True)
class Label:
    """The annotator's answer for one field.

    Attributes:
        kind: A name from ``kinds.KINDS``.
        unsure: The annotator was not confident; reports leave these out.
        note: Free text for later review.
        fingerprint: ``corpus.fingerprint`` of the field when it was labelled.
        updated_at: ISO 8601 time of the last change.
    """

    kind: str
    unsure: bool
    note: str
    fingerprint: str
    updated_at: str


def field_key(page: str, form: int, index: int) -> str:
    """Stable key of one field: ``<page>#<form>#<raw index>``."""
    return f"{page}#{form}#{index}"


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _label(key: str, raw: object) -> Label:
    if not isinstance(raw, dict):
        msg = f"label {key!r} is not an object"
        raise StoreError(msg)
    kind, unsure, note = raw.get("kind"), raw.get("unsure"), raw.get("note")
    stamp, updated = raw.get("fingerprint"), raw.get("updated_at")
    if not (
        isinstance(kind, str)
        and kind in BY_NAME
        and isinstance(unsure, bool)
        and isinstance(note, str)
        and isinstance(stamp, str)
        and isinstance(updated, str)
    ):
        msg = f"label {key!r} is malformed"
        raise StoreError(msg)
    return Label(kind, unsure, note, stamp, updated)


def _string_set(raw: object, what: str) -> set[str]:
    if not isinstance(raw, list) or not all(isinstance(item, str) for item in raw):
        msg = f"{what} is not a list of strings"
        raise StoreError(msg)
    return {item for item in raw if isinstance(item, str)}


class LabelStore:
    """Thread-safe label file. Reads happen once at start; every write replaces the file."""

    def __init__(self, path: Path) -> None:
        self._path = path
        self._lock = threading.Lock()
        self._labels: dict[str, Label] = {}
        self._done: set[str] = set()
        if path.exists():
            self._read()

    @property
    def path(self) -> Path:
        """Where the labels are stored."""
        return self._path

    def _read(self) -> None:
        try:
            decoded: object = json.loads(self._path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            msg = f"{self._path}: {error}"
            raise StoreError(msg) from error
        if not isinstance(decoded, dict) or decoded.get("version") != FORMAT_VERSION:
            msg = f"{self._path}: not a version {FORMAT_VERSION} label file"
            raise StoreError(msg)
        labels = decoded.get("labels")
        if not isinstance(labels, dict):
            msg = f"{self._path}: 'labels' is not an object"
            raise StoreError(msg)
        self._labels = {str(key): _label(str(key), value) for key, value in labels.items()}
        self._done = _string_set(decoded.get("done_pages"), "'done_pages'")

    def _write(self) -> None:
        document = {
            "version": FORMAT_VERSION,
            "labels": {key: asdict(self._labels[key]) for key in sorted(self._labels)},
            "done_pages": sorted(self._done),
        }
        self._path.parent.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(dir=self._path.parent, suffix=".tmp")
        temporary = Path(name)
        try:
            with os.fdopen(handle, "w", encoding="utf-8") as stream:
                json.dump(document, stream, ensure_ascii=False, indent=1)
                stream.write("\n")
            temporary.replace(self._path)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise

    def labels(self) -> dict[str, Label]:
        """A snapshot of every label, by field key."""
        with self._lock:
            return dict(self._labels)

    def done_pages(self) -> frozenset[str]:
        """Pages the annotator marked as finished."""
        with self._lock:
            return frozenset(self._done)

    def put(
        self,
        key: str,
        kind: str,
        *,
        unsure: bool,
        note: str,
        fingerprint: str,
    ) -> Label:
        """Create or replace the label of one field.

        Raises:
            StoreError: If ``kind`` is unknown or ``note`` is too long.
        """
        if kind not in BY_NAME:
            msg = f"unknown kind: {kind!r}"
            raise StoreError(msg)
        if len(note) > MAX_NOTE_LENGTH:
            msg = f"note is longer than {MAX_NOTE_LENGTH} characters"
            raise StoreError(msg)
        label = Label(kind, unsure, note.strip(), fingerprint, _now())
        with self._lock:
            self._labels[key] = label
            self._write()
        return label

    def clear(self, key: str) -> None:
        """Remove the label of one field, if any."""
        with self._lock:
            if self._labels.pop(key, None) is not None:
                self._write()

    def set_done(self, page: str, *, done: bool) -> None:
        """Mark or unmark a page as finished."""
        with self._lock:
            if done:
                self._done.add(page)
            else:
                self._done.discard(page)
            self._write()
