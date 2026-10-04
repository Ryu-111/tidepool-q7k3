#!/usr/bin/env python3
"""Build the personal unpacked Chrome extension; no secrets or vault files are packaged."""
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
CLIENTS = Path(os.environ.get("JEV_CLIENTS_DIR") or ROOT / "clients")
RUNTIME = ROOT / ".tools/node-v24.17.0-darwin-arm64/bin"
# The archive may be published as a release: refuse anything that looks like a credential.
SECRET = re.compile(
    rb"sk-or-[A-Za-z0-9-]{8,}|sk-ant-[A-Za-z0-9-]{8,}|BEGIN [A-Z ]*PRIVATE KEY|"
    rb"OPENROUTER_API_KEY=\S|gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}"
)


def package():
    build = CLIENTS / "apps/browser/build"
    manifest_file = build / "manifest.json"
    manifest = json.loads(manifest_file.read_text())
    assert manifest["manifest_version"] == 3
    # Give this personal build its own identity, separate from the installed store extension.
    manifest["name"] = "Jev Autofill — personal development build"
    manifest["short_name"] = "Jev Autofill"
    # A fixed public key pins the extension ID, so reloading from another folder (e.g. a CI ZIP)
    # keeps chrome.storage.local (vault login, Jev key). Only the public half exists; it is not
    # a secret, and unpacked loading needs no private key.
    manifest["key"] = (ROOT / "scripts/chrome-extension-key.pub").read_text().strip()
    manifest.pop("update_url", None)
    manifest_file.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    dist = ROOT / "chrome-dist"
    dist.mkdir(exist_ok=True)
    archive = dist / "jev-autofill-chrome.zip"
    files = [path for path in sorted(build.rglob("*")) if path.is_file()]
    for path in files:
        if SECRET.search(path.read_bytes()):
            raise SystemExit(f"Refusing to package {path.relative_to(build)}: looks like a secret.")
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as z:
        for path in files:
            z.write(path, path.relative_to(build))
    # Chrome loads the unpacked copy in chrome-dist; refresh it so a reload picks up this build.
    if "--zip-only" in sys.argv[1:]:
        print("Archive:", archive)
        print("SHA256:", hashlib.sha256(archive.read_bytes()).hexdigest())
        return
    unpacked = dist / "jev-autofill-chrome"
    if unpacked.exists():
        shutil.rmtree(unpacked)
    shutil.copytree(build, unpacked)
    print("Unpacked extension:", unpacked)
    print("Archive:", archive)
    print("SHA256:", hashlib.sha256(archive.read_bytes()).hexdigest())


if __name__ == "__main__":
    if not (CLIENTS / "package.json").exists():
        raise SystemExit(f"No clients checkout at {CLIENTS}; set JEV_CLIENTS_DIR to its absolute path.")
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
    # Local shells route commands through rtk; CI runners do not have it.
    runner = ["rtk", "proxy"] if shutil.which("rtk") else []
    subprocess.run([*runner, "npm", "run", "build:chrome", "--workspace", "@bitwarden/browser",
                    "--", "--stats", "errors-only"], cwd=CLIENTS, env=env, check=True)
    package()
