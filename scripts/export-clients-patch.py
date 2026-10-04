#!/usr/bin/env python3
"""Export the local clients/ changes as clients-patch/jev.patch for the Chrome CI build.

clients/ is a separate checkout of bitwarden/clients and is not part of this repository. CI
checks out the upstream commit in clients-patch/UPSTREAM and applies this patch, so the patch
must hold every change: committed, uncommitted and untracked (ignored files such as
apps/browser/config/local.json are left out).

Usage: export-clients-patch.py [--check]   --check fails if the stored patch is out of date.
"""
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CLIENTS = Path(os.environ.get("JEV_CLIENTS_DIR") or ROOT / "clients")
OUT = ROOT / "clients-patch"
# Refuse anything that looks like a credential; the patch is published with this repository.
SECRET = re.compile(
    rb"sk-or-[A-Za-z0-9-]{8,}|sk-ant-[A-Za-z0-9-]{8,}|BEGIN [A-Z ]*PRIVATE KEY|"
    rb"OPENROUTER_API_KEY=\S|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[0-9A-Z]{16}"
)
# Files that must never be published, whatever they contain.
FORBIDDEN = re.compile(
    r"(^|/)(\.env(\..*)?|user\.properties|local\.json|[^/]*credentials[^/]*)$|"
    r"\.(jks|keystore|p12|pfx|pem|key)$"
)


def git(*args: str, ok: tuple[int, ...] = (0,)) -> str:
    result = subprocess.run(["git", "-C", str(CLIENTS), *args], capture_output=True, text=True)
    if result.returncode not in ok:
        raise SystemExit(f"git {' '.join(args)} failed:\n{result.stderr}")
    return result.stdout


def changed_files(base: str) -> list[str]:
    tracked = git("diff", "--name-only", "--diff-filter=d", "-z", base).split("\0")
    untracked = git("ls-files", "--others", "--exclude-standard", "-z").split("\0")
    return [path for path in tracked + untracked if path]


def check_sources(files: list[str]) -> None:
    """Refuse forbidden file names and scan every changed file's raw bytes, binaries included."""
    for path in files:
        if FORBIDDEN.search(path):
            raise SystemExit(f"Refusing to export {path}: credential-like file name.")
        if SECRET.search((CLIENTS / path).read_bytes()):
            raise SystemExit(f"Refusing to export {path}: it contains something like a secret.")


def build_patch(base: str) -> str:
    parts = [git("diff", "--binary", base)]
    for path in git("ls-files", "--others", "--exclude-standard", "-z").split("\0"):
        if path:
            # --no-index exits 1 when the files differ, which is always the case here.
            parts.append(git("diff", "--binary", "--no-index", "/dev/null", path, ok=(0, 1)))
    return "".join(parts)


def main() -> None:
    base = (OUT / "UPSTREAM").read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{40}", base):
        raise SystemExit("clients-patch/UPSTREAM must hold one full commit SHA")
    if not (CLIENTS / ".git").exists():
        raise SystemExit(f"No clients checkout at {CLIENTS}; set JEV_CLIENTS_DIR to its absolute path.")
    git("cat-file", "-e", f"{base}^{{commit}}")
    check_sources(changed_files(base))
    patch = build_patch(base)
    if SECRET.search(patch.encode()):
        raise SystemExit("The patch contains something that looks like a secret; not written.")
    target = OUT / "jev.patch"
    if "--check" in sys.argv[1:]:
        if not target.exists() or target.read_text() != patch:
            raise SystemExit("clients-patch/jev.patch is out of date; run export-clients-patch.py")
        print("clients-patch/jev.patch is up to date.")
        return
    target.write_text(patch)
    files = re.findall(r"^diff --git a/(\S+)", patch, flags=re.MULTILINE)
    print(f"Wrote {target.relative_to(ROOT)}: {len(files)} files against {base[:12]}")
    for name in files:
        print(" ", name)


if __name__ == "__main__":
    main()
