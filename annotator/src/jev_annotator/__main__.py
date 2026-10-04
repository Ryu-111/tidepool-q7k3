"""Command line: ``serve`` the annotation UI or ``report`` predictions against the labels."""

from __future__ import annotations

import argparse
import sys
import webbrowser
from pathlib import Path
from typing import Final

from jev_annotator.corpus import CorpusError, Page, load_corpus
from jev_annotator.feedback import FeedbackError, load_feedback
from jev_annotator.fetch import fetch_pages
from jev_annotator.report import ReportError, render, render_feedback, score, score_feedback
from jev_annotator.server import serve, static_files
from jev_annotator.store import LabelStore, StoreError

_PACKAGE: Final = Path(__file__).resolve().parent
_APP_ROOT: Final = _PACKAGE.parents[1]
_WEB: Final = _APP_ROOT / "web"
_CORPUS: Final = Path("probe") / "corpus"


def default_corpus(repo_root: Path) -> Path:
    """``probe/corpus`` of the repository, or of the main checkout when run from a worktree.

    The collected data (``raw/``) is kept out of Git, so a linked worktree (whose ``.git`` is a
    file pointing at ``<main>/.git/worktrees/<name>``) has none of its own.
    """
    own = repo_root / _CORPUS
    marker = repo_root / ".git"
    if (own / "raw").is_dir() or not marker.is_file():
        return own
    pointer = marker.read_text(encoding="utf-8").strip().removeprefix("gitdir:").strip()
    git_dir = Path(pointer)
    if git_dir.parent.name != "worktrees":
        return own
    main_corpus = git_dir.parents[2] / _CORPUS
    return main_corpus if (main_corpus / "raw").is_dir() else own


def _limit(value: str) -> int:
    limit = int(value)
    if limit < 0:
        msg = "limit must be nonnegative"
        raise argparse.ArgumentTypeError(msg)
    return limit


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="jev-annotator", description=__doc__)
    parser.add_argument(
        "--corpus",
        type=Path,
        default=default_corpus(_APP_ROOT.parent),
        help="probe/corpus dir (default: this checkout's, else the main checkout's)",
    )
    parser.add_argument(
        "--pages",
        type=Path,
        help="page list relative to the corpus (default: eval/usable.txt if present, else raw/)",
    )
    parser.add_argument(
        "--labels",
        type=Path,
        help="label file (default: <corpus>/labels/labels.json, kept out of Git)",
    )
    parser.add_argument("--feedback", type=Path, help="add fills from a correction export JSON")
    commands = parser.add_subparsers(dest="command")
    serve_command = commands.add_parser("serve", help="run the annotation UI (default)")
    serve_command.add_argument("--port", type=int, default=8790)
    serve_command.add_argument("--no-browser", action="store_true")
    report_command = commands.add_parser("report", help="score a prediction TSV")
    report_command.add_argument("predictions", type=Path)
    feedback_command = commands.add_parser("report-feedback", help="score a correction export JSON")
    feedback_command.add_argument("export", type=Path)
    fetch_command = commands.add_parser("fetch-pages", help="save rendered HTML snapshots")
    fetch_command.add_argument("--force", action="store_true")
    fetch_command.add_argument("--limit", type=_limit)
    return parser


def _serve(args: argparse.Namespace, corpus: Path, store: LabelStore) -> int:
    files = static_files(_WEB / "static", _WEB / "dist")
    if "main.js" not in files:
        sys.stderr.write("web/dist/main.js is missing: run `npm run build` in annotator/web\n")
        return 1
    pages = _pages(args, corpus)
    port: int = getattr(args, "port", 8790)
    server = serve(pages, store, files, port, corpus)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    sys.stdout.write(f"{len(pages)} pages, labels in {store.path}\nOpen {url} (Ctrl+C to stop)\n")
    if not getattr(args, "no_browser", False):
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def _page_list(args: argparse.Namespace, corpus: Path) -> Path | None:
    pages: Path | None = args.pages
    if pages is not None:
        return corpus / pages
    usable = corpus / "eval" / "usable.txt"
    return usable if usable.is_file() else None


def _feedback_pages(path: Path) -> dict[str, Page]:
    feedback = load_feedback(path)
    sys.stderr.write(f"feedback: {feedback.skipped} malformed outcomes skipped\n")
    return feedback.pages


def _pages(args: argparse.Namespace, corpus: Path) -> dict[str, Page]:
    pages = load_corpus(corpus, _page_list(args, corpus))
    feedback: Path | None = args.feedback
    if feedback is not None:
        pages.update(_feedback_pages(feedback))
    return pages


def main(argv: list[str] | None = None) -> int:
    """Entry point; returns the process exit code."""
    args = _parser().parse_args(argv)
    corpus: Path = args.corpus.resolve()
    labels: Path = args.labels or corpus / "labels" / "labels.json"
    try:
        if args.command == "fetch-pages":
            pages = load_corpus(corpus, _page_list(args, corpus))
            for line in fetch_pages(corpus, pages, force=args.force, limit=args.limit):
                sys.stdout.write(line)
                sys.stdout.flush()
            return 0
        store = LabelStore(labels)
        if args.command == "report":
            predictions: Path = args.predictions
            pages = _pages(args, corpus)
            lines = predictions.read_text(encoding="utf-8").splitlines()
            sys.stdout.write(render(score(pages, store.labels(), lines)))
            return 0
        if args.command == "report-feedback":
            export: Path = args.export
            pages = _feedback_pages(export)
            sys.stdout.write(render_feedback(score_feedback(pages, store.labels())))
            return 0
        return _serve(args, corpus, store)
    except (CorpusError, StoreError, ReportError, FeedbackError, OSError) as error:
        sys.stderr.write(f"jev-annotator: {error}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
