#!/usr/bin/env python3
"""Build the exact upstream SDK locally for ARM64 Android; no GitHub credentials required."""
from pathlib import Path
import os
import shutil
import subprocess

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "sdk-internal"
COMMIT = "8b9fa3e2672633a2170116cc9fe66f7637850839"
VERSION = "3.0.0-jev-local-8b9fa3e2"


def main():
    revision = subprocess.check_output(
        ["rtk", "proxy", "git", "-C", str(SOURCE), "rev-parse", "HEAD"], text=True).strip()
    if revision != COMMIT:
        raise SystemExit("SDK checkout does not match the Android dependency revision.")
    env = os.environ.copy()
    env.pop("GITHUB_TOKEN", None)
    env.pop("GH_TOKEN", None)
    env["RUSTUP_TOOLCHAIN"] = "1.98.0"
    env["JAVA_HOME"] = env.get("JAVA_HOME", "/Applications/Android Studio.app/Contents/jbr/Contents/Home")
    env["ANDROID_HOME"] = env.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk"))
    llvm = Path(env["ANDROID_HOME"]) / "ndk/28.2.13676358/toolchains/llvm/prebuilt/darwin-x86_64/bin"
    clang = str(llvm / "aarch64-linux-android29-clang")
    env.update(CARGO_TARGET_AARCH64_LINUX_ANDROID_LINKER=clang,
               CC_aarch64_linux_android=clang,
               AR_aarch64_linux_android=str(llvm / "llvm-ar"))

    def run(*args, cwd=SOURCE):
        subprocess.run(["rtk", "proxy", *map(str, args)], cwd=cwd, env=env, check=True)

    run("cargo", "build", "--locked", "-p", "bitwarden-uniffi", "--release", "--target", "aarch64-linux-android")
    kotlin = SOURCE / "crates/bitwarden-uniffi/kotlin"
    native = kotlin / "sdk/src/main/jniLibs/arm64-v8a/libbitwarden_uniffi.so"
    native.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / "target/aarch64-linux-android/release/libbitwarden_uniffi.so", native)
    run("cargo", "run", "--locked", "-p", "uniffi-bindgen", "--", "generate", native,
        "--language", "kotlin", "--no-format", "--out-dir", kotlin / "sdk/src/main/java")
    run("./gradlew", "--no-daemon", "sdk:publishToMavenLocal", "-Pversion=" + VERSION, cwd=kotlin)
    print("Built local ARM64 SDK " + VERSION + "; no remote publishing performed.")


if __name__ == "__main__":
    main()
