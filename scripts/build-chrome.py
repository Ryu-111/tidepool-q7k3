#!/usr/bin/env python3
"""Build the personal unpacked Chrome extension; no secrets or vault files are packaged."""
import hashlib
import json
import os
import shutil
from pathlib import Path
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CLIENTS = ROOT / "clients"
RUNTIME = ROOT / ".tools/node-v24.17.0-darwin-arm64/bin"


def package():
    build = CLIENTS / "apps/browser/build"
    manifest_file = build / "manifest.json"
    manifest = json.loads(manifest_file.read_text())
    assert manifest["manifest_version"] == 3
    # Give this personal build its own identity, separate from the installed store extension.
    manifest["name"] = "Jev Autofill — personal development build"
    manifest["short_name"] = "Jev Autofill"
    manifest.pop("key", None)
    manifest.pop("update_url", None)
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    dist = ROOT / "chrome-dist"
    dist.mkdir(exist_ok=True)
    archive = dist / "jev-autofill-chrome.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(build.rglob("*")):
            if path.is_file():
                z.write(path, path.relative_to(build))
    # Chrome loads the unpacked copy in chrome-dist; refresh it so a reload picks up this build.
    unpacked = dist / "jev-autofill-chrome"
    if unpacked.exists():
        shutil.rmtree(unpacked)
    shutil.copytree(build, unpacked)
    print("Unpacked extension:", unpacked)
    print("Archive:", archive)
    print("SHA256:", hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__ == "__main__":
    env = dict(os.environ)
    # Production mode minifies the bundles; the development bundles make the popup open slowly.
    env["NODE_ENV"] = "production"
    if RUNTIME.exists():
        env["PATH"] = str(RUNTIME) + os.pathsep + env.get("PATH", "")
    config = CLIENTS / "apps/browser/config/local.json"
    if not config.exists():
        config.write_text('{"devFlags":{"managedEnvironment":null}}\n')
    # Normal hosted-account selection must remain available in this personal development build.
    if json.loads(config.read_text()).get("devFlags", {}).get("managedEnvironment") is not None:
        raise SystemExit("Local config forces a managed server; inspect it before building.")
    subprocess.run(["rtk", "proxy", "npm", "run", "build:chrome", "--workspace", "@bitwarden/browser",
                    "--", "--stats", "errors-only"], cwd=CLIENTS, env=env, check=True)
    package()
