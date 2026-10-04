#!/usr/bin/env python3
"""Transfer a private key to the explicitly opened emulator-only, one-shot memory channel."""
import socket
import sys
import re
from live_check import read_key, CheckError
from smoke import adb, nodes


def main():
    port = None
    try:
        if adb("shell", "getprop", "ro.hardware").strip() != "ranchu":
            raise CheckError("検証用エミュレーター以外には転送しません。")
        key = read_key()
        name = None
        for _ in range(3):
            for node in nodes():
                match = re.fullmatch(r"受信待機中: (jevprobe-key-[0-9a-f]{32})", node.get("text", ""))
                if node.get("package") == "dev.ryu.jevprobe" and match:
                    name = match[1]
                    break
            if name:
                break
        if not name:
            raise CheckError("検証アプリの受信待機完了を確認できませんでした。未送信です。")
        port = int(adb("forward", "tcp:0", "localabstract:" + name).strip())
        with socket.create_connection(("127.0.0.1", port), timeout=5) as stream:
            stream.sendall(key.encode("ascii") + b"\n")
            with stream.makefile("rb") as response:
                if response.readline(4) != b"OK\n":
                    raise CheckError("エミュレーターがキーを受信できませんでした。")
        print("PASS: エミュレーターのメモリへキーを転送しました。値の表示・保存はしていません。")
    except CheckError as error:
        print(str(error), file=sys.stderr)
        return 1
    except Exception:
        print("キー転送失敗。アプリで受信待機を開始してください。", file=sys.stderr)
        return 1
    finally:
        if port is not None:
            adb("forward", "--remove", "tcp:" + str(port))
    return 0


if __name__ == "__main__":
    sys.exit(main())
