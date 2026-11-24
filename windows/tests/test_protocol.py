import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inputbridge.protocol import (  # noqa: E402
    PROTOCOL_VERSION,
    ProtocolError,
    SequenceTracker,
    decode_line,
    encode_line,
    make_message,
    pairing_token,
    verify,
)


class TestProtocol(unittest.TestCase):
    def test_encrypted_roundtrip(self) -> None:
        token = pairing_token("123456")
        msg = make_message("input", {"kind": "key", "vk": 65}, "session-1", 1, token)
        self.assertEqual(msg["v"], PROTOCOL_VERSION)
        self.assertNotIn("payload", msg)
        line = decode_line(encode_line(msg).strip(), token)
        self.assertEqual(line["payload"]["vk"], 65)
        self.assertTrue(verify(line, token, min_seq=1).ok)

    def test_tamper_detected(self) -> None:
        token = pairing_token("123456")
        msg = make_message("input", {"kind": "key", "vk": 65}, "session-1", 1, token)
        encoded = bytearray(encode_line(msg).strip())
        encoded[-2] ^= 1
        with self.assertRaises(ProtocolError):
            decode_line(bytes(encoded), token)

    def test_wrong_token_rejected(self) -> None:
        msg = make_message("heartbeat", {}, "s", 1, pairing_token("123456"))
        with self.assertRaises(ProtocolError):
            decode_line(encode_line(msg).strip(), pairing_token("999999"))

    def test_legacy_signed_pairing(self) -> None:
        token = pairing_token("123456")
        msg = make_message("pair_request", {"deviceName": "phone"}, "s", 1, token)
        self.assertEqual(msg["v"], 1)
        line = decode_line(encode_line(msg).strip())
        self.assertTrue(verify(line, token, min_seq=1).ok)

    def test_unsigned_error(self) -> None:
        msg = make_message("error", {"message": "rescan"}, "s", 1, None)
        self.assertNotIn("sig", msg)
        self.assertEqual(decode_line(encode_line(msg).strip())["type"], "error")

    def test_sequence_tracker(self) -> None:
        token = pairing_token("123456")
        tracker = SequenceTracker()
        msg = decode_line(
            encode_line(make_message("heartbeat", {}, "s", 1, token)).strip(), token
        )
        self.assertTrue(tracker.check(msg).ok)
        self.assertFalse(tracker.check(msg).ok)
        msg2 = decode_line(
            encode_line(make_message("heartbeat", {}, "s", 2, token)).strip(), token
        )
        self.assertTrue(tracker.check(msg2).ok)

    def test_max_size(self) -> None:
        with self.assertRaises(ProtocolError):
            encode_line({"type": "input", "payload": {"data": "x" * 70000}})


if __name__ == "__main__":
    unittest.main()
