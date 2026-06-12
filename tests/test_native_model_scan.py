from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.native_model_scan import scan_model_artifacts, write_minimal_safetensors  # noqa: E402


class NativeModelScanTests(unittest.TestCase):
    def test_fallback_accepts_valid_safetensors_and_support_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config = root / "config.json"
            config.write_text("{}", encoding="utf-8")
            weight = write_minimal_safetensors(root / "model.safetensors")
            scan = scan_model_artifacts(
                [config, weight],
                cli_path=root / "missing-native-scan",
            )

        self.assertTrue(scan["passed"])
        self.assertTrue(scan["safe_tensors_only"])
        self.assertEqual(scan["summary"]["safetensors_files"], 1)
        self.assertEqual(scan["summary"]["unsafe_file_count"], 0)

    def test_fallback_rejects_pickle_family_weights(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            unsafe = root / "pytorch_model.bin"
            unsafe.write_bytes(b"\x80\x04GLOBAL\nos\nsystem\n.")
            scan = scan_model_artifacts(
                [unsafe],
                cli_path=root / "missing-native-scan",
            )

        self.assertFalse(scan["passed"])
        self.assertEqual(scan["summary"]["unsafe_file_count"], 1)
        self.assertIn("MODEL-PICKLE-FORMAT-BLOCKED", {finding["id"] for finding in scan["findings"]})


if __name__ == "__main__":
    unittest.main()
