from __future__ import annotations

import io
import subprocess
from dataclasses import replace
from email.message import Message
from typing import TYPE_CHECKING
from urllib.error import HTTPError, URLError

import pytest

from jev_annotator import __main__, fetch
from jev_annotator.__main__ import main
from jev_annotator.fetch import USER_AGENT, Fetcher, fetch_pages, render_page, robots_allowed
from tests.sample import PAGE_KEY

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping
    from pathlib import Path
    from urllib.request import Request

    from jev_annotator.corpus import Page


def render_success(_script: Path, _url: str, output: Path) -> bool:
    output.write_text('<input name="synthetic">', encoding="utf-8")
    return True


def render_failure(_script: Path, _url: str, output: Path) -> bool:
    output.write_text("incomplete", encoding="utf-8")
    return False


@pytest.mark.parametrize(
    ("allowed", "renderer", "status"),
    [
        (False, render_success, "skipped: robots disallowed"),
        (True, render_failure, "render failed"),
        (True, render_success, "saved"),
    ],
)
def test_fetch_status_and_atomic_output(
    corpus: Path,
    pages: dict[str, Page],
    *,
    allowed: bool,
    renderer: Callable[[Path, str, Path], bool],
    status: str,
) -> None:
    fetcher = Fetcher(robots=lambda _url: allowed, render=renderer)
    assert list(fetch_pages(corpus, pages, fetcher=fetcher)) == [f"{PAGE_KEY}: {status}\n"]
    target = corpus / "html/ec/example.html"
    assert target.is_file() == (status == "saved")
    assert list((corpus / "html/ec").glob("*.html")) == ([target] if status == "saved" else [])


def test_skip_existing_force_and_failed_replacement(corpus: Path, pages: dict[str, Page]) -> None:
    target = corpus / "html/ec/example.html"
    target.parent.mkdir(parents=True)
    target.write_text("old", encoding="utf-8")

    def unexpected(_url: str) -> bool:
        pytest.fail("existing snapshots must not query robots")

    assert list(fetch_pages(corpus, pages, fetcher=Fetcher(robots=unexpected))) == [
        f"{PAGE_KEY}: skipped: exists\n"
    ]
    fetcher = Fetcher(robots=lambda _url: True, render=render_failure)
    assert "render failed" in "".join(fetch_pages(corpus, pages, force=True, fetcher=fetcher))
    assert target.read_text(encoding="utf-8") == "old"
    fetcher = replace(fetcher, render=render_success)
    assert "saved" in "".join(fetch_pages(corpus, pages, force=True, fetcher=fetcher))
    assert target.read_text(encoding="utf-8") == '<input name="synthetic">'


def test_limit_and_pacing(corpus: Path, pages: dict[str, Page]) -> None:
    original = pages[PAGE_KEY]
    many = {f"ec/{i}.json": replace(original, key=f"ec/{i}.json") for i in range(3)}
    waits: list[float] = []
    fetcher = Fetcher(robots=lambda _url: True, render=render_success, wait=waits.append)
    assert list(fetch_pages(corpus, many, limit=0, fetcher=fetcher)) == []
    assert len(list(fetch_pages(corpus, many, limit=2, fetcher=fetcher))) == 2
    assert waits == [2.0]
    waits.clear()
    lines = list(fetch_pages(corpus, many, limit=1, fetcher=fetcher))
    assert len(lines) == 3
    assert lines[0].endswith("skipped: exists\n")
    assert lines[2].endswith("saved\n")
    assert waits == []


@pytest.mark.parametrize("url", ["http://example.test", "https:///missing", "not a URL"])
def test_only_https_pages_are_fetched(corpus: Path, pages: dict[str, Page], url: str) -> None:
    page = replace(pages[PAGE_KEY], url=url)

    def unexpected(_url: str) -> bool:
        pytest.fail("invalid URLs must not query robots")

    result = list(fetch_pages(corpus, {PAGE_KEY: page}, fetcher=Fetcher(robots=unexpected)))
    assert "non-HTTPS" in result[0]


def test_network_and_render_exceptions_skip_and_cleanup(
    corpus: Path, pages: dict[str, Page]
) -> None:
    def unreachable(_url: str) -> bool:
        msg = "synthetic network failure"
        raise URLError(msg)

    assert "fetch failed (URLError)" in "".join(
        fetch_pages(corpus, pages, fetcher=Fetcher(robots=unreachable))
    )

    def broken(_script: Path, _url: str, output: Path) -> bool:
        output.write_text("partial", encoding="utf-8")
        msg = "synthetic failure"
        raise OSError(msg)

    assert "fetch failed (OSError)" in "".join(
        fetch_pages(corpus, pages, fetcher=Fetcher(robots=lambda _url: True, render=broken))
    )
    assert list((corpus / "html/ec").iterdir()) == []


def test_empty_render_is_not_saved(corpus: Path, pages: dict[str, Page]) -> None:
    fetcher = Fetcher(robots=lambda _url: True, render=lambda _script, _url, _out: True)
    assert "render failed" in "".join(fetch_pages(corpus, pages, fetcher=fetcher))


@pytest.mark.parametrize("code", [401, 403, 404, 410, 500])
def test_robots_http_semantics(monkeypatch: pytest.MonkeyPatch, code: int) -> None:
    def denied(_request: Request, *, timeout: int) -> io.BytesIO:
        assert timeout > 0
        url = "https://example.test/robots.txt"
        raise HTTPError(url, code, "synthetic", Message(), None)

    monkeypatch.setattr(fetch, "urlopen", denied)
    if code == 500:
        with pytest.raises(HTTPError):
            robots_allowed("https://example.test/form")
    else:
        assert robots_allowed("https://example.test/form") == (code not in {401, 403})


def test_robots_rules_and_user_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    def read(request: Request, *, timeout: int) -> io.BytesIO:
        assert request.full_url == "https://example.test/robots.txt"
        assert request.get_header("User-agent") == USER_AGENT
        assert timeout > 0
        return io.BytesIO(b"User-agent: *\nDisallow: /private\n")

    monkeypatch.setattr(fetch, "urlopen", read)
    assert robots_allowed("https://example.test/form")
    assert not robots_allowed("https://example.test/private/form")


@pytest.mark.parametrize("exit_code", [0, 1])
def test_renderer_wrapper(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, exit_code: int) -> None:
    script, output = tmp_path / "render.sh", tmp_path / "out.html"

    def run(
        command: list[str], *, capture_output: bool, check: bool, timeout: int
    ) -> subprocess.CompletedProcess[bytes]:
        assert command == [str(script), "https://example.test/form", str(output)]
        assert capture_output
        assert not check
        assert timeout > 0
        output.write_text("<html>", encoding="utf-8")
        return subprocess.CompletedProcess(command, exit_code, b"", b"")

    monkeypatch.setattr(subprocess, "run", run)
    assert render_page(script, "https://example.test/form", output) == (exit_code == 0)


def test_renderer_timeout(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    def run(
        command: list[str], *, capture_output: bool, check: bool, timeout: int
    ) -> subprocess.CompletedProcess[bytes]:
        assert capture_output
        assert not check
        raise subprocess.TimeoutExpired(command, timeout)

    monkeypatch.setattr(subprocess, "run", run)
    assert not render_page(tmp_path / "render.sh", "https://example.test", tmp_path / "out.html")


def test_fetch_cli_options(
    corpus: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def collect(
        root: Path, pages: Mapping[str, Page], *, force: bool, limit: int | None
    ) -> Iterator[str]:
        assert root == corpus
        assert list(pages) == [PAGE_KEY]
        assert force
        assert limit == 1
        yield f"{PAGE_KEY}: saved\n"

    monkeypatch.setattr(__main__, "fetch_pages", collect)
    assert (
        main(
            [
                "--corpus",
                str(corpus),
                "--pages",
                "eval/usable.txt",
                "fetch-pages",
                "--force",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    assert capsys.readouterr().out == f"{PAGE_KEY}: saved\n"
    assert not (corpus / "labels").exists()


def test_fetch_cli_rejects_negative_limit() -> None:
    with pytest.raises(SystemExit) as error:
        main(["fetch-pages", "--limit", "-1"])
    assert error.value.code == 2
