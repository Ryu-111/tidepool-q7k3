"""Collect rendered HTML with robots permission and paced, atomic writes."""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, Final
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from jev_annotator.snapshot import snapshot_path

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator, Mapping
    from pathlib import Path

    from jev_annotator.corpus import Page

USER_AGENT: Final = "jev-autofill-research/0.1 (form structure survey)"
_INTERVAL: Final = 2.0
_TIMEOUT: Final = 60


def robots_allowed(url: str) -> bool:
    """Read robots with a timeout; apply robotparser's HTTP error semantics.

    Raises:
        OSError: If robots cannot be reached because of a network error.
    """
    source = urlsplit(url)
    robots_url = f"{source.scheme}://{source.netloc}/robots.txt"
    parser = RobotFileParser(robots_url)
    request = Request(robots_url, headers={"User-Agent": USER_AGENT})  # noqa: S310 -- HTTPS caller
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 -- HTTPS source checked below
            parser.parse(response.read().decode("utf-8", errors="replace").splitlines())
    except HTTPError as error:
        error.close()
        if error.code in {401, 403}:
            return False
        if 400 <= error.code < 500:  # noqa: PLR2004 -- robotparser HTTP semantics
            return True
        raise
    return parser.can_fetch(USER_AGENT, url)


def render_page(script: Path, url: str, output: Path) -> bool:
    """Run the existing throwaway-profile renderer without echoing third-party HTML."""
    try:
        result = subprocess.run(  # noqa: S603 -- fixed local script, no shell interpolation
            [str(script), url, str(output)],
            capture_output=True,
            check=False,
            timeout=_TIMEOUT,
        )
    except subprocess.TimeoutExpired:
        return False
    return result.returncode == 0 and output.stat().st_size > 0


@dataclass(frozen=True, slots=True)
class Fetcher:
    """Small injectable I/O boundaries; tests need neither networking nor Chrome."""

    robots: Callable[[str], bool] = robots_allowed
    render: Callable[[Path, str, Path], bool] = render_page
    wait: Callable[[float], None] = time.sleep


def _fetch(corpus: Path, page: Page, fetcher: Fetcher) -> str:
    target = snapshot_path(corpus, page.key)
    url = urlsplit(page.url)
    if target is None or url.scheme != "https" or not url.hostname:
        return "skipped: invalid key or non-HTTPS URL"
    if not fetcher.robots(page.url):
        return "skipped: robots disallowed"
    target.parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(dir=target.parent, suffix=".html", delete=False) as temporary:
        output = target.parent / temporary.name
    try:
        if not fetcher.render(corpus / "render.sh", page.url, output) or output.stat().st_size == 0:
            return "render failed"
        output.replace(target)
    finally:
        output.unlink(missing_ok=True)
    return "saved"


def fetch_pages(
    corpus: Path,
    pages: Mapping[str, Page],
    *,
    force: bool = False,
    limit: int | None = None,
    fetcher: Fetcher | None = None,
) -> Iterator[str]:
    """Yield one progress line per page; limit counts attempted missing/forced snapshots."""
    fetcher = fetcher or Fetcher()
    attempted = 0
    for page in pages.values():
        target = snapshot_path(corpus, page.key)
        if target is not None and target.is_file() and not force:
            yield f"{page.key}: skipped: exists\n"
            continue
        if limit is not None and attempted >= limit:
            break
        if attempted:
            fetcher.wait(_INTERVAL)
        attempted += 1
        try:
            status = _fetch(corpus, page, fetcher)
        except (OSError, ValueError) as error:
            status = f"skipped: fetch failed ({type(error).__name__})"
        yield f"{page.key}: {status}\n"
