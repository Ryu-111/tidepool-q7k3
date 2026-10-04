"""Synthetic corpus page shared by the tests."""

from __future__ import annotations

# Synthetic structure only; no real page is copied into the tests.
PAGE: dict[str, object] = {
    "source_url": "https://example.test/entry",
    "source_host": "example.test",
    "category": "ec",
    "fetched_at": "2026-10-04T10:00:00+09:00",
    "field_count": 7,
    "forms": [
        {
            "fields": [
                {"tag": "input", "type": "hidden", "name": "token", "near": []},
                {"tag": "input", "type": "text", "name": "sei", "near": ["お名前"], "label": "姓"},
                {"tag": "input", "type": "radio", "name": "sex", "near": ["性別"]},
                {"tag": "input", "type": "datetime-local", "name": "visit", "near": ["来店日"]},
                {
                    "tag": "select",
                    "type": "select",
                    "name": "pref",
                    "near": ["住所"],
                    "options": ["選択", "東京都"],
                    "required": True,
                },
                {"tag": "input", "type": "email", "name": "mail", "near": ["メール"]},
            ],
        },
        {"outside_form": True, "fields": [{"tag": "input", "type": "search", "near": ["検索"]}]},
    ],
}
PAGE_KEY = "ec/example.json"
