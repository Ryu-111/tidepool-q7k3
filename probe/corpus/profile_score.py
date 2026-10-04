#!/usr/bin/env python3
"""Print how many fields of an extracted form JSON look like profile fields (name, address, ...).

Usage: profile_score.py <json>...   A page is useful for the corpus when the score is >= 4.
"""
import json
import re
import sys

PROFILE = re.compile(
    r"氏名|お名前|名前|姓|名|フリガナ|ふりがな|カナ|かな|郵便|〒|住所|都道府県|市区町村|番地|"
    r"建物|マンション|電話|携帯|TEL|メール|生年月日|誕生|性別|年齢|会社|勤務先|部署|"
    r"zip|postal|post|addr|pref|city|tel|phone|mail|birth|sex|gender|kana|name",
    re.IGNORECASE)
NOT_PROFILE = re.compile(r"検索|search|keyword|キーワード|password|パスワード", re.IGNORECASE)


def text_of(field):
    parts = [field.get(k, "") for k in ("label", "name", "id", "placeholder", "autocomplete",
                                         "aria-label", "legend")]
    return " ".join(parts + field.get("near", [])[-1:])


def score(path):
    data = json.load(open(path))
    fields = [f for form in data["forms"] for f in form["fields"]
              if f["type"] not in ("checkbox",)]
    return sum(1 for f in fields if PROFILE.search(text_of(f)) and not NOT_PROFILE.search(text_of(f)))


if __name__ == "__main__":
    for path in sys.argv[1:]:
        print(f"{score(path)}\t{path}")
