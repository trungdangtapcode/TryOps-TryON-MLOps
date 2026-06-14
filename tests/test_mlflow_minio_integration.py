from __future__ import annotations

import sys
import tempfile
import unittest
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops import db  # noqa: E402
from tryops.mlflow_integration import mlflow_status  # noqa: E402


class MLflowMinIOIntegrationTests(unittest.TestCase):
    def test_compose_initializes_minio_bucket_before_mlflow(self) -> None:
        compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
        self.assertIn("minio-init:", compose)
        self.assertIn("mc mb --ignore-existing local/tryops-artifacts", compose)
        self.assertIn("minio-init:", compose)
        self.assertIn("service_completed_successfully", compose)
        self.assertIn("--artifacts-destination s3://tryops-artifacts/mlflow", compose)
        self.assertNotIn("--default-artifact-root s3://tryops-artifacts/mlflow", compose)

    def test_mlflow_can_be_disabled_without_importing_client(self) -> None:
        old_value = os.environ.get("TRYOPS_MLFLOW_ENABLED")
        os.environ["TRYOPS_MLFLOW_ENABLED"] = "0"
        try:
            status = mlflow_status()
        finally:
            if old_value is None:
                os.environ.pop("TRYOPS_MLFLOW_ENABLED", None)
            else:
                os.environ["TRYOPS_MLFLOW_ENABLED"] = old_value
        self.assertEqual(status["status"], "disabled")

    def test_db_model_mirror_persists_mlflow_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "tryops.db"
            db.init_db(db_path)
            conn = db.connect(db_path)
            try:
                db.upsert_model(
                    conn,
                    {
                        "id": "mlflow:vton-demo",
                        "name": "catvton",
                        "workload": "vton",
                        "stage": "champion",
                        "version": "1",
                        "signed": 1,
                        "approved": 1,
                        "metrics": {"garment_fidelity": 0.91},
                        "mlflow_tracking_uri": "http://mlflow:5000",
                        "mlflow_run_id": "run-123",
                        "mlflow_experiment_id": "exp-1",
                        "mlflow_model_name": "tryops.vton.catvton",
                        "mlflow_model_version": "3",
                        "mlflow_artifact_uri": "mlflow-artifacts:/1/run-123/artifacts",
                        "mlflow_model_uri": "models:/tryops.vton.catvton/3",
                        "mlflow_run_url": "http://127.0.0.1:15000/#/experiments/1/runs/run-123",
                        "mlflow_model_url": "http://127.0.0.1:15000/#/models/tryops.vton.catvton/versions/3",
                        "artifact_backend": "minio",
                    },
                )
                model = db.list_models(conn)[0]
            finally:
                conn.close()
        self.assertEqual(model["mlflow_run_id"], "run-123")
        self.assertEqual(model["mlflow_model_version"], "3")
        self.assertEqual(model["artifact_backend"], "minio")
        self.assertEqual(model["metrics"]["garment_fidelity"], 0.91)


if __name__ == "__main__":
    unittest.main()
