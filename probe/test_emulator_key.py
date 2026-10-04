"""Check that secrets are sent only after our app has bound an unpredictable socket."""
import contextlib
import io
import unittest
import xml.etree.ElementTree as ET
from unittest.mock import MagicMock, patch
import emulator_key


class KeyChannelTest(unittest.TestCase):
    def transfer(self, package, name):
        node = ET.Element("node", {"package": package, "text": "受信待機中: " + name})
        def adb(*args):
            return "ranchu" if args[0] == "shell" else "12345"
        connection = MagicMock()
        stream = connection.return_value.__enter__.return_value
        stream.makefile.return_value.__enter__.return_value.readline.return_value = b"OK\n"
        with patch.object(emulator_key, "adb", side_effect=adb) as commands, \
             patch.object(emulator_key, "nodes", return_value=[node]), \
             patch.object(emulator_key, "read_key", return_value="SYNTHETIC_KEY"), \
             patch.object(emulator_key.socket, "create_connection", connection), \
             contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            result = emulator_key.main()
        return result, commands, connection, stream

    def test_foreign_app_and_fixed_socket_are_rejected_before_transmission(self):
        for package, name in [("other.app", "jevprobe-key-" + "a" * 32),
                              ("dev.ryu.jevprobe", "jevprobe-key")]:
            result, commands, connection, _ = self.transfer(package, name)
            self.assertEqual(result, 1)
            connection.assert_not_called()
            self.assertFalse(any(c.args[0] == "forward" for c in commands.call_args_list))

    def test_bound_nonce_channel_uses_stream_not_command_arguments(self):
        name = "jevprobe-key-" + "a" * 32
        result, commands, _, stream = self.transfer("dev.ryu.jevprobe", name)
        self.assertEqual(result, 0)
        commands.assert_any_call("forward", "tcp:0", "localabstract:" + name)
        commands.assert_any_call("forward", "--remove", "tcp:12345")
        stream.sendall.assert_called_once_with(b"SYNTHETIC_KEY\n")
        self.assertNotIn("SYNTHETIC_KEY", str(commands.call_args_list))


if __name__ == "__main__":
    unittest.main()
