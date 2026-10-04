#!/usr/bin/env python3
"""Flatten extracted corpus JSON into the evidence Chrome would pass to Android autofill.

One line per control: page, index, shape, then key=value evidence (label, placeholder, aria-label,
name, id, autocomplete, maxlength). Radios and checkboxes are dropped: Chrome does not pass radios,
and checkboxes are consents, not profile fields.
"""
import glob
import json
import sys

SHAPES = {"text": "TEXT", "tel": "TEL", "email": "EMAIL", "number": "NUMBER", "password": "PASSWORD",
          "date": "DATE", "select": "LIST", "textarea": "TEXT", "search": "TEXT", "url": "TEXT"}


def clean(value):
    return str(value).replace("\t", " ").replace("\x1f", " ").replace("\n", " ")


def main(paths):
    for path in paths:
        page = json.load(open(path))
        for number, form in enumerate(page["forms"]):
          index = 0
          for field in form["fields"]:
                shape = SHAPES.get(field["type"])
                if shape is None:
                    continue
                label = field.get("label") or (field.get("near") or [""])[-1]
                evidence = [("label", label)] + [(k, field[k]) for k in
                            ("placeholder", "aria-label", "name", "id", "autocomplete", "maxlength")
                            if field.get(k)]
                print("\t".join([f"{path}#{number}", str(index), shape,
                                 "\x1f".join(f"{k}={clean(v)}" for k, v in evidence if v)]))
                index += 1


if __name__ == "__main__":
    main(sys.argv[1:] or sorted(glob.glob("raw/*/*.json")))
