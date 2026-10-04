#!/usr/bin/env python3
"""One synthetic Jev request. Read a private local key without printing it or provider bodies."""
from pathlib import Path
import json
import math
import os
import stat
import sys
import urllib.error
import urllib.request

KEY_FILE = Path(__file__).resolve().parent.parent / ".env"
ENDPOINT = "https://openrouter.ai/api/v1/systemone"


class CheckError(Exception):
    """Only fixed, non-sensitive messages may be displayed."""


def read_key(path=KEY_FILE):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise CheckError("APIキーファイルを開けません。") from None
    with os.fdopen(fd, "rb") as stream:
        info = os.fstat(stream.fileno())
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                or info.st_mode & 0o077 or info.st_nlink != 1 or info.st_size > 8192):
            raise CheckError(".envは自分が所有する通常ファイル・権限600で用意してください。")
        raw = stream.read(8193)
    try:
        content = raw.decode("utf-8")
    except UnicodeError:
        raise CheckError(".envの形式が不正です。") from None
    lines = [line.strip() for line in content.splitlines() if line.strip() and not line.lstrip().startswith("#")]
    if len(lines) != 1 or not lines[0].startswith("OPENROUTER_API_KEY="):
        raise CheckError(".envにはOPENROUTER_API_KEY=の1行だけ設定してください。")
    key = lines[0].partition("=")[2].strip()
    if not key:
        raise CheckError("APIキーは未設定です。.envの=の右側に貼り付けてください。")
    if len(key) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in key) or any(c in key for c in "\"'"):
        raise CheckError("APIキーは引用符・空白なしの1行で設定してください。")
    return key


def payload():
    # Same closed vocabulary as Jev.java; no real user/page data is read by this script.
    return {
        "model": "jev-latest",
        "state": {"fields": [{"id": 0, "type": "TEXT", "hints": ["EMAIL"]}]},
        "questions": {
            "f0": {
                "type": "choice",
                "instructions": "Choose the semantic kind for field 0 from the sanitized field table. Choose UNKNOWN if ambiguous.",
                "criteria": {"EMAIL": "EMAIL", "UNKNOWN": "UNKNOWN"},
            }
        },
    }


def validate(body):
    try:
        response = json.loads(body)
        answers = response["answers"]
        if not isinstance(answers, dict) or set(answers) != {"f0"}:
            raise ValueError()
        answer = answers["f0"]
        if answer["type"] != "choice" or answer["choice"] not in ("EMAIL", "UNKNOWN"):
            raise ValueError()
        confidence = answer["confidence"]
        probabilities = answer["probabilities"]
        if not isinstance(probabilities, dict) or set(probabilities) != {"EMAIL", "UNKNOWN"}:
            raise ValueError()
        for value in [confidence, *probabilities.values()]:
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 <= value <= 1:
                raise ValueError()
        if abs(sum(probabilities.values()) - 1) > .001:
            raise ValueError()
        if probabilities[answer["choice"]] < max(probabilities.values()):
            raise ValueError()
        if answer["choice"] != "EMAIL" or confidence < .90:
            raise CheckError("API応答は受信しましたが、ダミー判定の合格条件を満たしませんでした。")
    except (KeyError, TypeError, ValueError, OverflowError):
        raise CheckError("API応答の形式・選択肢・確率の検証に失敗しました。") from None


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise CheckError("APIのリダイレクトを拒否しました。")


def check():
    key = read_key()
    request = urllib.request.Request(
        ENDPOINT, data=json.dumps(payload()).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Authorization": "Bearer " + key},
    )
    opener = urllib.request.build_opener(NoRedirect())
    try:
        with opener.open(request, timeout=15) as response:
            if response.status != 200:
                raise CheckError("APIが成功応答を返しませんでした。")
            body = response.read(65537)
        if len(body) > 65536:
            raise CheckError("API応答のサイズ上限を超えました。")
        validate(body)
    except urllib.error.HTTPError as error:
        raise CheckError(f"API接続失敗（HTTP {error.code}）。認証・利用枠を確認してください。") from None
    except (urllib.error.URLError, OSError, TimeoutError):
        raise CheckError("API接続失敗（ネットワーク／TLS／タイムアウト）。") from None
    print("PASS: Jev実通信・合成した欄情報の分類。キーと応答本文は表示・保存していません。")


if __name__ == "__main__":
    try:
        check()
    except CheckError as error:
        print(str(error), file=sys.stderr)
        sys.exit(1)
