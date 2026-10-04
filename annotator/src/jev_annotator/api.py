"""JSON views and changes behind the HTTP endpoints, kept free of HTTP for testing."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from http import HTTPStatus
from typing import TYPE_CHECKING

from jev_annotator.kinds import KINDS
from jev_annotator.store import Label, LabelStore, StoreError, field_key

if TYPE_CHECKING:
    from collections.abc import Mapping

    from jev_annotator.corpus import Field, Page

type Json = dict[str, object]


@dataclass(frozen=True, slots=True)
class ApiError(Exception):
    """A request the API refuses, with the HTTP status to answer."""

    status: HTTPStatus
    message: str


def _label_json(label: Label | None, field: Field) -> Json | None:
    if label is None:
        return None
    return {
        "kind": label.kind,
        "unsure": label.unsure,
        "note": label.note,
        "stale": label.fingerprint != field.fingerprint,
    }


def _field_json(field: Field, label: Label | None) -> Json:
    return {
        "index": field.index,
        "tag": field.tag,
        "type": field.type,
        "name": field.name,
        "htmlId": field.html_id,
        "label": field.label,
        "near": list(field.near),
        "legend": field.legend,
        "placeholder": field.placeholder,
        "autocomplete": field.autocomplete,
        "ariaLabel": field.aria_label,
        "title": field.title,
        "maxlength": field.maxlength,
        "inputmode": field.inputmode,
        "pattern": field.pattern,
        "required": field.required,
        "options": list(field.options),
        "answer": _label_json(label, field),
        "recorded": asdict(field.recorded) if field.recorded is not None else None,
    }


def _progress(page: Page, labels: Mapping[str, Label], done: frozenset[str]) -> Json:
    labelled = sum(
        1
        for form in page.forms
        for field in form.fields
        if field_key(page.key, form.number, field.index) in labels
    )
    return {
        "key": page.key,
        "fields": page.field_count,
        "labelled": labelled,
        "done": page.key in done,
    }


def state(pages: Mapping[str, Page], store: LabelStore) -> Json:
    """Kinds and every page with its progress, for the sidebar."""
    labels, done = store.labels(), store.done_pages()
    return {
        "kinds": [{"name": k.name, "group": k.group, "label": k.label} for k in KINDS],
        "pages": [
            {"category": page.category, "host": page.host, **_progress(page, labels, done)}
            for page in pages.values()
        ],
        "labelFile": str(store.path),
    }


def _page(pages: Mapping[str, Page], key: object) -> Page:
    page = pages.get(key) if isinstance(key, str) else None
    if page is None:
        raise ApiError(HTTPStatus.NOT_FOUND, "unknown page")
    return page


def page_detail(pages: Mapping[str, Page], store: LabelStore, key: str) -> Json:
    """One page with its forms, fields and current labels."""
    page = _page(pages, key)
    labels = store.labels()
    return {
        "key": page.key,
        "category": page.category,
        "host": page.host,
        "url": page.url,
        "fetchedAt": page.fetched_at,
        "forms": [
            {
                "number": form.number,
                "outsideForm": form.outside_form,
                "fields": [
                    _field_json(f, labels.get(field_key(page.key, form.number, f.index)))
                    for f in form.fields
                ],
            }
            for form in page.forms
        ],
        "progress": _progress(page, labels, store.done_pages()),
    }


def _integer(value: object, name: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool):
        raise ApiError(HTTPStatus.BAD_REQUEST, f"{name} must be an integer")
    return value


def _find_field(page: Page, form_number: int, index: int) -> Field:
    for form in page.forms:
        if form.number != form_number:
            continue
        for field in form.fields:
            if field.index == index:
                return field
    raise ApiError(HTTPStatus.NOT_FOUND, "unknown field")


def _body(body: object) -> Json:
    if not isinstance(body, dict):
        raise ApiError(HTTPStatus.BAD_REQUEST, "body must be a JSON object")
    return {str(k): v for k, v in body.items()}


def put_label(pages: Mapping[str, Page], store: LabelStore, body: object) -> Json:
    """Set (``kind`` is a name) or clear (``kind`` is null) the label of one field."""
    request = _body(body)
    page = _page(pages, request.get("page"))
    form = _integer(request.get("form"), "form")
    field = _find_field(page, form, _integer(request.get("index"), "index"))
    key = field_key(page.key, form, field.index)
    kind, unsure, note = request.get("kind"), request.get("unsure", False), request.get("note", "")
    if not isinstance(unsure, bool) or not isinstance(note, str):
        raise ApiError(HTTPStatus.BAD_REQUEST, "unsure must be a boolean and note a string")
    if kind is None:
        store.clear(key)
        label = None
    elif isinstance(kind, str):
        try:
            label = store.put(key, kind, unsure=unsure, note=note, fingerprint=field.fingerprint)
        except StoreError as error:
            raise ApiError(HTTPStatus.BAD_REQUEST, str(error)) from error
    else:
        raise ApiError(HTTPStatus.BAD_REQUEST, "kind must be a string or null")
    return {
        "answer": _label_json(label, field),
        "progress": _progress(page, store.labels(), store.done_pages()),
    }


def put_done(pages: Mapping[str, Page], store: LabelStore, body: object) -> Json:
    """Mark or unmark a page as finished."""
    request = _body(body)
    page = _page(pages, request.get("page"))
    done = request.get("done")
    if not isinstance(done, bool):
        raise ApiError(HTTPStatus.BAD_REQUEST, "done must be a boolean")
    store.set_done(page.key, done=done)
    return {"progress": _progress(page, store.labels(), store.done_pages())}
