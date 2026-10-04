#!/usr/bin/env python3
"""Synthetic UI test only; refuses physical devices, never reads an existing password vault."""
from pathlib import Path
import os
import re
import subprocess
import time
import uuid
import xml.etree.ElementTree as ET

ADB = Path(os.environ.get("ANDROID_HOME", str(Path.home() / "Library/Android/sdk"))) / "platform-tools/adb"
SERIAL = os.environ.get("PROBE_SERIAL", "emulator-5554")
if not re.fullmatch(r"emulator-\d+", SERIAL):
    raise SystemExit("This automated probe test only operates on an emulator.")

def adb(*args):
    return subprocess.check_output(["rtk", "proxy", str(ADB), "-s", SERIAL, *args], text=True, timeout=30)

def nodes():
    for _ in range(3):
        adb("shell", "rm", "-f", "/data/local/tmp/jev-probe-ui.xml")
        result = adb("shell", "uiautomator", "dump", "/data/local/tmp/jev-probe-ui.xml")
        if "UI hierchary dumped to:" in result:
            try:
                return ET.fromstring(adb("shell", "cat", "/data/local/tmp/jev-probe-ui.xml")).iter("node")
            except ET.ParseError:
                pass  # retry a fresh dump, never accept an empty/truncated hierarchy
        time.sleep(.5)
    raise SystemExit("No fresh UI hierarchy available")

def find(text, click=False, ensure_checked=False, scroll=False):
    for _attempt in range(4):
        candidates = sorted(nodes(), key=lambda n: n.get("text", "").casefold() != text.casefold())
        for node in candidates:
            if text.casefold() in node.get("text", "").casefold():
                x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds")))
                if x2 <= x1 or y2 <= y1:
                    continue
                if click and (not ensure_checked or node.get("checked") != "true"):
                    adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
                return
        if scroll:
            adb("shell", "input", "swipe", "500", "1700", "500", "800", "300")
        time.sleep(.3)
    raise SystemExit(f"UI assertion failed: {text}")

def main():
    original = adb("shell", "settings", "get", "secure", "autofill_service").strip()
    debug_port = None
    try:
        chrome = os.environ.get("PROBE_CHROME") == "1"
        if chrome:
            version = re.search(r"versionName=(\d+)", adb("shell", "dumpsys", "package", "com.android.chrome"))
            if not version or int(version[1]) < 135:
                raise SystemExit("Chrome 135 or later required")
            adb("reverse", "tcp:8765", "tcp:8765")
        adb("shell", "am", "force-stop", "dev.ryu.jevprobe")
        adb("shell", "settings", "put", "secure", "autofill_service", "dev.ryu.jevprobe/.ProbeService")
        adb("shell", "am", "start", "-n", "dev.ryu.jevprobe/.MainActivity")
        find("自己テスト: PASS")
        live = os.environ.get("PROBE_LIVE") == "1"
        if live:
            from emulator_key import main as transfer_key
            find("Macからキーを受信", True)
            if transfer_key() != 0:
                raise SystemExit("Key transfer failed")
            find("受信完了")
            find("APIキーをメモリに設定", True)  # empty input must preserve the received key
            find("設定は変更していません")
        # PROBE_PAGE selects a synthetic pattern page, e.g. patterns/split.html (Chrome only).
        page = os.environ.get("PROBE_PAGE", "")
        if page and (not chrome or not re.fullmatch(r"patterns/[a-z]+\.html", page)):
            raise SystemExit("PROBE_PAGE must be patterns/<name>.html and requires PROBE_CHROME=1")
        if chrome:
            url = "http://localhost:8765/" + page + "?run=" + uuid.uuid4().hex
            adb("shell", "am", "start", "-a", "android.intent.action.VIEW", "-d", url, "-p", "com.android.chrome")
            find(os.environ.get("PROBE_FOCUS", "姓"), True)
            debug_port = adb("forward", "tcp:0", "localabstract:chrome_devtools_remote").strip()
            verify = ["rtk", "proxy", "node", str(Path(__file__).with_name("verify-chrome.mjs")), debug_port, url]
            subprocess.run([*verify, "ready"], check=True, timeout=15)
        else:
            find("同梱のダミーフォームを開く", True, scroll=True)
            find("自動入力候補を表示", True)
        def fill_once(button):
            find("Jev 検証: ダミー情報を一括入力", True)
            find("Jevで判定する" if live else "ローカル判定で確認", True)
            find("JEV LIVE" if live else "LOCAL")
            skipped = live and any("照会対象なし" in n.get("text", "") for n in nodes())
            # Unknown occupancy is deliberately unchecked. Authorize only the empty demo fields:
            # the five fixed ones on the original page, every fillable field on a pattern page.
            if page:
                approved = 0
                for node in list(nodes()):
                    if (node.get("class") == "android.widget.CheckBox" and node.get("enabled") == "true"
                            and node.get("checked") != "true"
                            and re.match(r"(［Jev］)?欄 \d+: ", node.get("text", ""))):
                        x1, y1, x2, y2 = map(int, re.findall(r"\d+", node.get("bounds")))
                        adb("shell", "input", "tap", str((x1 + x2) // 2), str((y1 + y2) // 2))
                        approved += 1
                print(f"Approved {approved} pattern fields")
            else:
                for field in ("FAMILY", "GIVEN", "POSTAL", "STREET", "PASSWORD"):
                    find(": " + field + " →", True, ensure_checked=True)
            find(button, True, scroll=True)
            # A FillResponse authentication may require a second dataset selection on some OS versions.
            # Chrome shows that chip noticeably later than native views, so wait up to ~10 s.
            for _ in range(20):
                if any(n.get("text") == "ダミー情報" for n in nodes()):
                    find("ダミー情報", True)
                    break
                time.sleep(.3)
            else:
                print("NOTE: second dataset chip not seen; relying on direct fill")
            return skipped
        jev_skipped = fill_once("確認してダミー情報を一括入力")
        if os.environ.get("PROBE_REFILL") == "1":
            # A zip-to-address widget rewrites the address after the batch fill. Reopen the
            # flow and refill everything except the postal code, which does not re-trigger it.
            time.sleep(2)
            if "mInputShown=true" in adb("shell", "dumpsys", "input_method"):
                adb("shell", "input", "keyevent", "BACK")
            # Autofilled fields offer no new suggestion; the field the widget rewrote does.
            label = os.environ.get("PROBE_REFILL_FOCUS", "市区町村・番地")
            for _ in range(3):
                # A long press on the rewritten input (just below its label) re-enters it the way
                # a user would; a plain tap on the label did not start a new request in Chrome.
                box = next((n.get("bounds") for n in nodes() if n.get("text", "") == label), None)
                if box is None:
                    raise SystemExit("UI assertion failed: " + label)
                x1, y1, x2, y2 = map(int, re.findall(r"\d+", box))
                adb("shell", "input", "swipe", "540", str(y2 + 50), "540", str(y2 + 50), "1000")
                time.sleep(2)
                if any("Jev 検証" in n.get("text", "") for n in nodes()):
                    break
                adb("shell", "input", "keyevent", "BACK")
            fill_once("郵便番号以外を再入力")
            print("Refilled without postal code")
        if "mInputShown=true" in adb("shell", "dumpsys", "input_method"):
            adb("shell", "input", "keyevent", "BACK")
        if chrome:
            # Chrome applies the dataset asynchronously after the chip is tapped; poll briefly.
            for attempt in range(5):
                if subprocess.run([*verify, "filled"], timeout=15,
                                  stderr=subprocess.DEVNULL if attempt < 4 else None).returncode == 0:
                    break
                if attempt == 4:
                    raise SystemExit("Chrome fill verification failed")
                time.sleep(1)
        else:
            find("入力結果を検証", True, scroll=True)
            find("PASS: 5項目一括入力")
        if live:
            print("Jev queried: " + ("no (all fields resolved locally)" if jev_skipped else "yes"))
        print("PASS: " + ("JEV LIVE" if live else "LOCAL")
              + (" Chrome" if chrome else " native")
              + (f" {page} filled every expected field" if page
                 else " fixture filled 5 fields, preserved existing value and hidden field"))
    finally:
        adb("shell", "am", "force-stop", "dev.ryu.jevprobe")  # discard in-memory key
        if original in ("", "null"):
            adb("shell", "settings", "delete", "secure", "autofill_service")
        else:
            adb("shell", "settings", "put", "secure", "autofill_service", original)
        adb("shell", "rm", "-f", "/data/local/tmp/jev-probe-ui.xml")
        if chrome:
            adb("reverse", "--remove", "tcp:8765")
        if debug_port:
            adb("forward", "--remove", "tcp:" + debug_port)

if __name__ == "__main__":
    main()
