from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from jev_annotator.snapshot import sanitize, snapshot_csp, snapshot_path

if TYPE_CHECKING:
    from pathlib import Path

URL = "https://example.test/form?x=1&y=2"
BASE = '<base href="https://example.test/form?x=1&amp;y=2">'


@pytest.mark.parametrize(
    "tag", ["script", "noscript", "template", "iframe", "frameset", "object", "applet", "portal"]
)
def test_drops_active_elements_and_their_contents(tag: str) -> None:
    html = f'<html><head></head><body><{tag}><input name="bad">secret</{tag}><input name="ok">'
    result = sanitize(html, URL)
    assert "secret" not in result
    assert 'name="bad"' not in result
    assert 'name="ok"' in result
    assert f"<{tag}" not in result


def test_void_elements_refresh_links_and_old_base() -> None:
    result = sanitize(
        '<head><base href="https://evil.test"><META HTTP-EQUIV="ReFrEsH" content="0">'
        '<meta charset="utf-8"><link rel="preload" href="/x">'
        '<link rel="StyleSheet" href="/a.css"></head><frame><embed><input name="ok">',
        URL,
    )
    assert result.startswith(f"<head>{BASE}")
    assert result.count("<base ") == 1
    assert '<meta charset="utf-8">' in result
    assert "refresh" not in result.casefold()
    assert "preload" not in result
    assert '<link rel="StyleSheet" href="/a.css">' in result
    assert '<input name="ok">' in result
    assert "<frame" not in result
    assert "<embed" not in result


@pytest.mark.parametrize("attribute", ["href", "src", "action", "xlink:href"])
@pytest.mark.parametrize(
    "url",
    [
        " javascript:alert(1)",
        "VBScript:x",
        "data:text/html,x",
        "java\nscript:x",
        "java&#9;script:x",
    ],
)
def test_unsafe_url_attributes(attribute: str, url: str) -> None:
    result = sanitize(f'<a {attribute}="{url}" title="ok">text</a>', URL)
    assert result.endswith('<a title="ok">text</a>')


def test_drops_events_and_submission_attributes_but_keeps_image_data() -> None:
    result = sanitize(
        '<form action="/submit" onsubmit="bad()"><input id="first" name="n" type="text"'
        ' onclick="bad()" ONFOCUS="bad()" srcdoc="bad" formaction="/other" ping="/ping" required>'
        '<img src="data:image/png;base64,AA"><img src="data:text/html,bad">'
        '<a href="https://example.test/ok">ok</a></form>',
        URL,
    )
    assert "bad" not in result
    assert "formaction" not in result
    assert "ping" not in result
    assert '<form action="/submit">' in result
    assert '<input id="first" name="n" type="text" required>' in result
    assert '<img src="data:image/png;base64,AA"><img>' in result
    assert '<a href="https://example.test/ok">' in result


@pytest.mark.parametrize("prefix", ["", "<!DOCTYPE html>", "<!DOCTYPE html><html>", "<html>"])
def test_creates_missing_head_and_keeps_controls_in_order(prefix: str) -> None:
    controls = (
        '<label for="a">A &amp; B</label><input id="a">'
        '<select name="b"><option>1</option></select><textarea name="c">&lt;x&gt;</textarea>'
    )
    assert sanitize(prefix + controls, URL) == prefix.lower() + f"<head>{BASE}</head>" + controls


@pytest.mark.parametrize(
    ("html", "ending"),
    [
        ('<input name="a"><script>unclosed', '<input name="a">'),
        ('<template><div>bad</template><input name="a">', '<input name="a">'),
        ('<script/> <input name="a"/>', ' <input name="a">'),
        ("<p/>x<!-- hidden --><input disabled>", "<p></p>x<input disabled>"),
        ("<object><object>bad</object></object><input>", "<input>"),
        ("<object></bogus>bad</object><input>", "<input>"),
        ("<head></head><head></head><input>", "<head></head><input>"),
        ('<input name="a"', ""),
    ],
)
def test_malformed_html_is_inert(html: str, ending: str) -> None:
    result = sanitize(html, URL)
    assert result.endswith(ending)
    assert "bad" not in result
    assert result.count(BASE) == 1


def test_snapshot_paths_refuse_traversal_and_external_symlinks(tmp_path: Path) -> None:
    assert snapshot_path(tmp_path, "ec/example.json") == tmp_path / "html/ec/example.html"
    for key in ["../x.json", "/x.json", "ec/x", "ec/a/b.json", "ec/../../x.json"]:
        assert snapshot_path(tmp_path, key) is None
    (tmp_path / "html").mkdir()
    (tmp_path / "html/ec").symlink_to(tmp_path)
    assert snapshot_path(tmp_path, "ec/example.json") is None


def test_csp_online_and_offline() -> None:
    assert snapshot_csp() == (
        "sandbox allow-same-origin; default-src 'none'; style-src 'unsafe-inline' https:; "
        "img-src https: data:; font-src https: data:; form-action 'none'; "
        "base-uri https:; frame-ancestors 'self'"
    )
    assert snapshot_csp(styles=False) == (
        "sandbox allow-same-origin; default-src 'none'; style-src 'unsafe-inline'; "
        "img-src data:; font-src data:; form-action 'none'; base-uri https:; frame-ancestors 'self'"
    )
