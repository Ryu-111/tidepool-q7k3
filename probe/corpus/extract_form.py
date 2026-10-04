#!/usr/bin/env python3
"""Extract the value-free structure of the forms in one HTML page.

Usage: extract_form.py <html-file> <source-url> <category> > out.json

Only structure is kept: control kind, name/id, placeholder, autocomplete, maxlength, required,
option captions, and the label or nearby page text that describes each control. Current values,
hidden inputs, and form action paths are never written.
"""
import json
import re
import sys
from datetime import datetime, timedelta, timezone
from html.parser import HTMLParser
from urllib.parse import urlparse

MAX_TEXT = 60
MAX_OPTIONS = 60
NEAR_TEXTS = 3
CONTROL_ATTRS = ("name", "id", "placeholder", "autocomplete", "maxlength", "inputmode",
                 "pattern", "aria-label", "title")
SKIP_TYPES = {"hidden", "submit", "button", "reset", "image", "file"}
SKIP_TAGS = {"script", "style", "noscript", "template", "svg"}


def clean(text):
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:MAX_TEXT]


class FormParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.forms = []
        self.current = None  # fields of the form being parsed, or None outside a <form>
        self.orphans = []  # controls outside any <form>
        self.skip = 0
        self.texts = []  # recent visible text snippets, for label inference
        self.labels_for = {}  # id -> label text
        self.label_stack = []  # open <label> elements: [for_id, text parts, controls inside]
        self.legend = None
        self.in_legend = False
        self.select = None
        self.option = None
        self.textarea = None

    def fields(self):
        return self.current if self.current is not None else self.orphans

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag in SKIP_TAGS:
            self.skip += 1
            return
        if self.skip:
            return
        if tag == "form":
            self.current = []
            self.forms.append({"fields": self.current})
        elif tag == "label":
            self.label_stack.append([a.get("for"), [], []])
        elif tag == "legend":
            self.in_legend = True
            self.legend = ""
        elif tag == "input":
            kind = a.get("type", "text").lower()
            if kind in SKIP_TYPES:
                return
            field = self.control("input", kind, a)
            if kind in ("radio", "checkbox"):
                field["value"] = clean(a.get("value"))
            self.fields().append(field)
        elif tag == "select":
            self.select = self.control("select", "select", a)
            self.select["options"] = []
            self.fields().append(self.select)
        elif tag == "option" and self.select is not None:
            self.option = []
        elif tag == "textarea":
            self.textarea = self.control("textarea", "textarea", a)
            self.fields().append(self.textarea)

    def control(self, tag, kind, a):
        field = {"tag": tag, "type": kind}
        for key in CONTROL_ATTRS:
            if a.get(key):
                field[key] = clean(a[key])
        if "required" in a:
            field["required"] = True
        if self.label_stack:
            self.label_stack[-1][2].append(field)
        if self.legend:
            field["legend"] = self.legend
        field["near"] = self.texts[-NEAR_TEXTS:]
        return field

    def handle_endtag(self, tag):
        if tag in SKIP_TAGS:
            self.skip = max(0, self.skip - 1)
            return
        if self.skip:
            return
        if tag == "form":
            self.current = None
        elif tag == "label" and self.label_stack:
            for_id, parts, inside = self.label_stack.pop()
            text = clean(" ".join(parts))
            if for_id:
                self.labels_for[for_id] = text
            for field in inside:
                field.setdefault("label", text)
        elif tag == "legend":
            self.in_legend = False
            self.legend = clean(self.legend)
        elif tag == "fieldset":
            self.legend = None
        elif tag == "option" and self.option is not None:
            if len(self.select["options"]) < MAX_OPTIONS:
                self.select["options"].append(clean(" ".join(self.option)))
            self.option = None
        elif tag == "select":
            self.select = None
        elif tag == "textarea":
            self.textarea = None

    def handle_data(self, data):
        if self.skip or self.textarea is not None:
            return  # textarea content is a value, never kept
        text = clean(data)
        if not text:
            return
        if self.option is not None:
            self.option.append(text)
            return
        if self.in_legend:
            self.legend += " " + text
        for label in self.label_stack:
            label[1].append(text)
        self.texts.append(text)
        del self.texts[:-NEAR_TEXTS * 2]

    def result(self):
        forms = [f for f in self.forms if f["fields"]]
        if self.orphans:
            forms.append({"fields": self.orphans, "outside_form": True})
        for form in forms:
            for field in form["fields"]:
                if "label" not in field and field.get("id") in self.labels_for:
                    field["label"] = self.labels_for[field["id"]]
        return forms


def main():
    path, url, category = sys.argv[1:4]
    raw = open(path, "rb").read()
    charset = re.search(rb'charset=["\']?([A-Za-z0-9_-]+)', raw[:4096])
    encoding = charset.group(1).decode() if charset else "utf-8"
    try:
        html = raw.decode(encoding, errors="replace")
    except LookupError:
        html = raw.decode("utf-8", errors="replace")
    parser = FormParser()
    parser.feed(html)
    forms = parser.result()
    jst = timezone(timedelta(hours=9))
    out = {
        "source_url": url,
        "source_host": urlparse(url).hostname,
        "category": category,
        "fetched_at": datetime.now(jst).isoformat(timespec="seconds"),
        "field_count": sum(len(f["fields"]) for f in forms),
        "forms": forms,
    }
    json.dump(out, sys.stdout, ensure_ascii=False, indent=1)
    print()


if __name__ == "__main__":
    main()
