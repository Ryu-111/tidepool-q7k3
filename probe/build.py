#!/usr/bin/env python3
"""Build only the isolated probe using installed SDK tools, without Gradle or package credentials."""
from pathlib import Path
import os
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parent
SDK = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk")))
JDK = Path(os.environ.get("JAVA_HOME", "/Applications/Android Studio.app/Contents/jbr/Contents/Home"))
TOOLS = SDK / "build-tools/36.0.0"
ANDROID = SDK / "platforms/android-34/android.jar"
BUILD = ROOT / ".build"
ENV = {**os.environ, "JAVA_HOME": str(JDK)}

def run(*args):
    subprocess.run(["rtk", "proxy", *map(str, args)], cwd=ROOT, env=ENV, check=True)

def main():
    for required in (TOOLS / "aapt2", ANDROID, JDK / "bin/javac"):
        if not required.exists():
            raise SystemExit(f"Missing build prerequisite: {required}")
    BUILD.mkdir(exist_ok=True)
    for name in ("classes", "dex", "tests"):
        target = BUILD / name
        if target.exists():
            shutil.rmtree(target)
        target.mkdir()
    run(JDK / "bin/javac", "--release", "8", "-encoding", "UTF-8", "-d", BUILD / "tests",
        ROOT / "src/dev/ryu/jevprobe/Policy.java", ROOT / "src/dev/ryu/jevprobe/Profile.java",
        ROOT / "test/dev/ryu/jevprobe/PolicyTest.java")
    run(JDK / "bin/java", "-cp", BUILD / "tests", "dev.ryu.jevprobe.PolicyTest")
    run(TOOLS / "aapt2", "compile", "--dir", ROOT / "res", "-o", BUILD / "resources.zip")
    run(TOOLS / "aapt2", "link", "-I", ANDROID, "--manifest", ROOT / "AndroidManifest.xml",
        "-o", BUILD / "unsigned.apk", BUILD / "resources.zip")
    run(JDK / "bin/javac", "--release", "8", "-encoding", "UTF-8", "-classpath", ANDROID,
        "-d", BUILD / "classes", *sorted((ROOT / "src").rglob("*.java")))
    run(JDK / "bin/jar", "cf", BUILD / "classes.jar", "-C", BUILD / "classes", ".")
    run(TOOLS / "d8", "--lib", ANDROID, "--min-api", "29", "--output", BUILD / "dex", BUILD / "classes.jar")
    with zipfile.ZipFile(BUILD / "unsigned.apk", "a", zipfile.ZIP_DEFLATED) as apk:
        for dex in sorted((BUILD / "dex").glob("*.dex")):
            apk.write(dex, dex.name)
    run(TOOLS / "zipalign", "-f", "4", BUILD / "unsigned.apk", BUILD / "aligned.apk")
    keystore = BUILD / "probe-debug.jks"
    if not keystore.exists():
        # Public Android debug-key convention; never a production signing identity.
        run(JDK / "bin/keytool", "-genkeypair", "-keystore", keystore, "-alias", "androiddebugkey",
            "-storepass", "android", "-keypass", "android", "-keyalg", "RSA", "-keysize", "2048",
            "-validity", "365", "-dname", "CN=Jev Dummy Probe,O=Development,C=JP")
    run(TOOLS / "apksigner", "sign", "--ks", keystore, "--ks-pass", "pass:android",
        "--out", BUILD / "jev-probe.apk", BUILD / "aligned.apk")
    run(TOOLS / "apksigner", "verify", BUILD / "jev-probe.apk")
    print(f"Built and verified: {BUILD / 'jev-probe.apk'}")

if __name__ == "__main__":
    main()
