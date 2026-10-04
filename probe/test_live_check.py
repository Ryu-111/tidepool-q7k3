import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock
import live_check


class LiveCheckTests(unittest.TestCase):
    def test_private_file_and_invalid_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text("OPENROUTER_API_KEY=synthetic-test-only\n")
            path.chmod(0o600)
            self.assertEqual(live_check.read_key(path), "synthetic-test-only")
            path.chmod(0o644)
            with self.assertRaises(live_check.CheckError):
                live_check.read_key(path)
            path.chmod(0o600)
            for content in ("OPENROUTER_API_KEY=", "OPENROUTER_API_KEY=a\nOTHER=b", "export OPENROUTER_API_KEY=a",
                            "OPENROUTER_API_KEY=\"value\"", "OPENROUTER_API_KEY=one two", "TYPESAFE_API_KEY=wrong-provider"):
                path.write_text(content)
                with self.assertRaises(live_check.CheckError):
                    live_check.read_key(path)
            link = Path(directory) / "link"
            link.symlink_to(path)
            with self.assertRaises(live_check.CheckError):
                live_check.read_key(link)
            link.unlink()
            os.link(path, link)
            with self.assertRaises(live_check.CheckError):
                live_check.read_key(path)

    def test_response_validation(self):
        answer = {"type": "choice", "choice": "EMAIL", "confidence": .99,
                  "probabilities": {"EMAIL": .99, "UNKNOWN": .01}}
        def body(value):
            return json.dumps({"answers": {"f0": value}}).encode()
        live_check.validate(body(answer))
        for replacement in ({"choice": "PASSWORD"}, {"confidence": True}, {"confidence": "0.99"},
                            {"confidence": .1}, {"confidence": float("nan")},
                            {"probabilities": {"EMAIL": .99, "UNKNOWN": .99}},
                            {"probabilities": {"EMAIL": .01, "UNKNOWN": .99}},
                            {"probabilities": {"EMAIL": 1, "PASSWORD": 0}}):
            with self.assertRaises(live_check.CheckError):
                live_check.validate(body({**answer, **replacement}))
        for invalid in (b"not-json", b"[]", b"null", b'{"answers":{}}'):
            with self.assertRaises(live_check.CheckError):
                live_check.validate(invalid)

    def test_transport_fixed_destination_and_no_key_in_body(self):
        body = b'{"answers":{"f0":{"type":"choice","choice":"EMAIL","confidence":0.99,"probabilities":{"EMAIL":0.99,"UNKNOWN":0.01}}}}'
        response = mock.MagicMock(status=200)
        response.read.return_value = body
        response.__enter__.return_value = response
        opener = mock.Mock()
        opener.open.return_value = response
        with mock.patch.object(live_check, "read_key", return_value="SYNTHETIC_PRIVATE_TOKEN"), \
                mock.patch.object(live_check.urllib.request, "build_opener", return_value=opener), \
                mock.patch("builtins.print") as output:
            live_check.check()
            request = opener.open.call_args.args[0]
            self.assertEqual(request.full_url, "https://openrouter.ai/api/v1/systemone")
            self.assertNotIn(b"SYNTHETIC_PRIVATE_TOKEN", request.data)
            self.assertNotIn("SYNTHETIC_PRIVATE_TOKEN", str(output.call_args_list))

    def test_redirect_blocked(self):
        with self.assertRaises(live_check.CheckError):
            live_check.NoRedirect().redirect_request(None, None, 302, "", {}, "https://example.invalid")


if __name__ == "__main__":
    unittest.main()
