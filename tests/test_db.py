from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops import db  # noqa: E402


class DbTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "t.db"
        db.init_db(self.path)
        self.conn = db.connect(self.path)

    def tearDown(self) -> None:
        self.conn.close()
        self._tmp.cleanup()

    def test_request_roundtrip_and_list(self) -> None:
        rid = db.insert_request(self.conn, {
            "kind": "llm", "model_alias": "baseline", "adapter": "real",
            "input_summary": "what is mlops", "output_summary": "...",
            "latency_ms": 120.0, "vram_gb": 0.28, "energy_wh": 0.001,
            "cost_usd": 0.0001, "quality": 0.83,
        })
        got = db.get_request(self.conn, rid)
        self.assertEqual(got["kind"], "llm")
        self.assertEqual(got["quality"], 0.83)
        self.assertEqual(len(db.list_requests(self.conn, kind="llm")), 1)
        self.assertEqual(len(db.list_requests(self.conn, kind="vton")), 0)

    def test_feedback_and_dashboard(self) -> None:
        rid = db.insert_request(self.conn, {"kind": "vton", "latency_ms": 3200.0,
                                            "vram_gb": 2.8, "quality": 0.6})
        db.insert_feedback(self.conn, {"request_id": rid, "rating": 5, "label": "good"})
        summary = db.dashboard_summary(self.conn)
        self.assertEqual(summary["total_requests"], 1)
        self.assertEqual(summary["vton"]["requests"], 1)
        self.assertEqual(summary["feedback"]["count"], 1)
        self.assertEqual(summary["feedback"]["avg_rating"], 5.0)

    def test_model_upsert_and_audit(self) -> None:
        mid = db.upsert_model(self.conn, {"name": "catvton", "workload": "vton",
                                          "stage": "candidate", "metrics": {"fid": 12.0}})
        db.upsert_model(self.conn, {"id": mid, "name": "catvton", "workload": "vton",
                                    "stage": "champion", "signed": 1, "approved": 1})
        models = db.list_models(self.conn)
        self.assertEqual(len(models), 1)
        self.assertEqual(models[0]["stage"], "champion")
        self.assertEqual(models[0]["signed"], 1)
        db.insert_audit(self.conn, actor="admin", action="promote", target=mid)
        self.assertEqual(len(db.list_audit(self.conn)), 1)

    def test_init_is_idempotent(self) -> None:
        db.init_db(self.path)  # second call must not error
        self.assertIsNotNone(db.dashboard_summary(self.conn))


if __name__ == "__main__":
    unittest.main()
