import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inputbridge.protocol import (  # noqa: E402
    ProtocolError,
    SequenceTracker,
    decode_line,
    encode_line,
    make_message,
    pairing_token,
    sign,
    verify,
)


class TestProtocol(unittest.TestCase):
    def test_roundtrip_and_signature(self) -> None:
        token = pairing_token("123456")
        msg = make_message("input", {"kind": "key", "vk": 65}, "session-1", 1, token)
        line = decode_line(encode_line(msg).strip())
        self.assertTrue(verify(line, token, min_seq=1).ok)

    def test_tamper_detected(self) -> None:
        token = pairing_token("123456")
        msg = make_message("input", {"kind": "key", "vk": 65}, "session-1", 1, token)
        msg["payload"]["vk"] = 66
        self.assertFalse(verify(msg, token, min_seq=1).ok)

    def test_wrong_token_rejected(self) -> None:
        msg = make_message("heartbeat", {}, "s", 1, pairing_token("123456"))
        self.assertFalse(verify(msg, pairing_token("999999"), min_seq=1).ok)

    def test_sequence_tracker(self) -> None:
        tracker = SequenceTracker()
        msg = make_message("heartbeat", {}, "s", 1, pairing_token("123456"))
        self.assertTrue(tracker.check(msg).ok)
        self.assertFalse(tracker.check(msg).ok)
        msg2 = make_message("heartbeat", {}, "s", 2, pairing_token("123456"))
        self.assertTrue(tracker.check(msg2).ok)

    def test_max_size(self) -> None:
        with self.assertRaises(ProtocolError):
            encode_line({"type": "input", "payload": {"data": "x" * 70000}})


if __name__ == "__main__":
    unittest.main()
