from __future__ import annotations

import argparse
import importlib.util
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tryops.pipelines.vton_remote import DEFAULT_REAL_VTON_URL  # noqa: E402


class _LiveProcess:
    def poll(self) -> None:
        return None


def _load_router_module():
    spec = importlib.util.spec_from_file_location(
        "serve_fashn_vton_router_for_tests",
        ROOT / "scripts" / "serve_fashn_vton_router.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("could not load router module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FashnRouterConfigTests(unittest.TestCase):
    def test_blank_worker_env_uses_real_router_defaults(self) -> None:
        router = _load_router_module()
        args = argparse.Namespace(
            host="0.0.0.0",
            port=18100,
            weights_dir=ROOT / "artifacts" / "models" / "fashn-vton-1.5",
            worker_python=Path(sys.executable),
            service_script=ROOT / "scripts" / "serve_fashn_vton.py",
            worker_transport="unix",
            worker_socket_dir=Path("artifacts/runtime/fashn-workers"),
            worker_base_port=43100,
            gpu_ids="0",
            workers_config=None,
            preload=True,
        )

        with patch.dict(
            os.environ,
            {
                "TRYOPS_FASHN_GPU_IDS": "",
                "TRYOPS_FASHN_WORKER_TRANSPORT": "",
                "TRYOPS_FASHN_WORKER_SOCKET_DIR": "",
                "TRYOPS_FASHN_WORKER_BASE_PORT": "",
                "TRYOPS_FASHN_WORKER_PRELOAD": "",
                "TRYOPS_FASHN_REQUIRE_CUDA": "",
                "TRYOPS_FASHN_ALLOW_CPU_FALLBACK": "",
                "FASHN_VTON_PYTHON": "artifacts/venvs/fashn-vton/bin/python",
            },
            clear=False,
        ):
            config = router._load_config(args)

        self.assertEqual(config.port, 18100)
        self.assertEqual(config.worker_python, (ROOT / "artifacts/venvs/fashn-vton/bin/python").absolute())
        self.assertTrue(config.preload)
        self.assertTrue(config.require_cuda)
        self.assertFalse(config.allow_cpu_fallback)
        self.assertEqual(len(config.workers), 1)
        self.assertEqual(config.workers[0].gpu_id, "0")
        self.assertEqual(config.workers[0].transport, "unix")
        self.assertEqual(config.workers[0].socket_path, Path("artifacts/runtime/fashn-workers/fashn-gpu0.sock"))

    def test_api_default_points_to_router_not_debug_worker(self) -> None:
        self.assertEqual(DEFAULT_REAL_VTON_URL, "http://host.docker.internal:18100")

    def test_router_round_robins_equal_load_workers(self) -> None:
        router_module = _load_router_module()
        workers = [
            router_module.WorkerConfig(
                worker_id=f"test-worker-{suffix}",
                gpu_id=f"test-gpu-{suffix}",
                gpu_uuid="",
                transport="unix",
                socket_path=Path(f"artifacts/runtime/fashn-workers/test-worker-{suffix}.sock"),
                host="127.0.0.1",
                port=None,
                log_file=Path(f"artifacts/logs/fashn-vton-worker-test-worker-{suffix}.log"),
                pid_file=Path(f"artifacts/runtime/fashn-vton-worker-test-worker-{suffix}.pid"),
                structured_log=Path(f"artifacts/logs/fashn_vton_worker_test-worker-{suffix}_events.jsonl"),
            )
            for suffix in ("a", "b", "c")
        ]
        config = router_module.RouterConfig(
            host="0.0.0.0",
            port=18100,
            weights_dir=ROOT / "artifacts" / "models" / "fashn-vton-1.5",
            worker_python=Path(sys.executable),
            service_script=ROOT / "scripts" / "serve_fashn_vton.py",
            registry_path=Path("artifacts/runtime/fashn-vton-workers.json"),
            structured_log=Path("artifacts/logs/fashn_vton_router_events.jsonl"),
            preload=True,
            require_cuda=True,
            allow_cpu_fallback=False,
            workers=workers,
        )
        fashn_router = router_module.FashnVtonRouter(config, router_module.StructuredEventLogger(None))
        for worker in fashn_router.workers:
            worker.ready = True
            worker.process = _LiveProcess()

        claimed = []
        for _ in range(5):
            worker = fashn_router.claim_worker()
            self.assertIsNotNone(worker)
            assert worker is not None
            claimed.append(worker.config.worker_id)
            with worker.lock:
                worker.inflight = max(0, worker.inflight - 1)

        self.assertEqual(
            claimed,
            ["test-worker-a", "test-worker-b", "test-worker-c", "test-worker-a", "test-worker-b"],
        )


if __name__ == "__main__":
    unittest.main()
