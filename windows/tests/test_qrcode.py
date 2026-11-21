import unittest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from inputbridge import qrcode  # noqa: E402


class TestQrCode(unittest.TestCase):
    def test_format_bits(self) -> None:
        self.assertEqual(qrcode._format_bits(), 0x77C4)

    def test_matrix_size(self) -> None:
        matrix = qrcode.make_matrix({"h": "192.168.1.10", "p": 27123, "t": "0" * 32, "v": 1})
        self.assertEqual(len(matrix), 37)
        self.assertTrue(all(len(row) == 37 for row in matrix))

    def test_payload_limit(self) -> None:
        with self.assertRaises(ValueError):
            qrcode.make_matrix({"v": 1, "h": "x" * 200, "p": 27123, "t": "0" * 32})


if __name__ == "__main__":
    unittest.main()
