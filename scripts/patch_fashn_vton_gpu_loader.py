#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


DEFAULT_REPO = Path("artifacts/external/fashn-vton-1.5")
MARKER = "_load_tryon_model_gpu_first"


OLD_IMPORT = """import logging
import os
"""

NEW_IMPORT = """import gc
import inspect
import logging
import os
"""

OLD_SETUP = '''    def _setup_tryon_model(self):
        """Load the TryOn model."""
        model_path = os.path.join(self.weights_dir, "model.safetensors")
        self.logger.info(f"Loading TryOnModel from {model_path}")

        self.tryon_model = TryOnModel()
        state_dict = load_checkpoint(model_path, device=str(self.device))
        self.tryon_model.load_state_dict(state_dict)
        self.tryon_model.to(self.device, dtype=self.inference_dtype).eval()

        self.logger.info("TryOnModel loaded")
'''

NEW_SETUP = '''    def _setup_tryon_model(self):
        """Load the TryOn model."""
        model_path = os.path.join(self.weights_dir, "model.safetensors")
        self.logger.info(f"Loading TryOnModel from {model_path}")

        gpu_first_load = os.environ.get("FASHN_VTON_GPU_FIRST_LOAD", "1").strip().lower()
        if self.device.type == "cuda" and gpu_first_load not in {"0", "false", "no", "off"}:
            try:
                self.tryon_model = self._load_tryon_model_gpu_first(model_path)
                self.logger.info("TryOnModel loaded with GPU-first checkpoint assignment")
                return
            except Exception as exc:
                self.logger.warning("GPU-first TryOnModel load failed; using fallback loader: %s", exc)
                self._release_load_cache()

        self.tryon_model = TryOnModel()
        self.tryon_model.to(self.device, dtype=self.inference_dtype)
        state_dict = None
        try:
            state_dict = load_checkpoint(model_path, device=str(self.device))
            self.tryon_model.load_state_dict(state_dict)
        finally:
            del state_dict
            self._release_load_cache()
        self.tryon_model.eval()

        self.logger.info("TryOnModel loaded")

    def _load_tryon_model_gpu_first(self, model_path: str):
        """Build the large module without CPU tensors, then bind CUDA checkpoint tensors."""
        assign_supported = "assign" in inspect.signature(torch.nn.Module.load_state_dict).parameters
        if assign_supported:
            with torch.device("meta"):
                model = TryOnModel()
            load_kwargs = {"assign": True}
        elif hasattr(torch.nn.Module, "to_empty"):
            with torch.device("meta"):
                model = TryOnModel()
            model.to_empty(device=self.device)
            load_kwargs = {}
        else:
            raise RuntimeError("PyTorch does not support assign=True or to_empty for GPU-first loading")

        state_dict = None
        try:
            state_dict = load_checkpoint(model_path, device=str(self.device))
            model.load_state_dict(state_dict, **load_kwargs)
        finally:
            del state_dict
            self._release_load_cache()
        model.to(self.device, dtype=self.inference_dtype).eval()
        self._release_load_cache()
        return model

    def _release_load_cache(self):
        gc.collect()
        if self.device.type == "cuda":
            torch.cuda.empty_cache()
'''


def patch_pipeline(repo: Path) -> bool:
    pipeline_path = repo / "src" / "fashn_vton" / "pipeline.py"
    if not pipeline_path.exists():
        raise FileNotFoundError(f"FASHN pipeline not found: {pipeline_path}")

    text = pipeline_path.read_text(encoding="utf-8")
    if MARKER in text:
        print(f"FASHN VTON GPU-first loader already patched: {pipeline_path}")
        return False

    if OLD_IMPORT not in text:
        raise RuntimeError("Could not find expected import block in FASHN pipeline.py")
    text = text.replace(OLD_IMPORT, NEW_IMPORT, 1)

    if OLD_SETUP not in text:
        raise RuntimeError("Could not find expected _setup_tryon_model block in FASHN pipeline.py")
    text = text.replace(OLD_SETUP, NEW_SETUP, 1)

    pipeline_path.write_text(text, encoding="utf-8")
    print(f"Patched FASHN VTON GPU-first loader: {pipeline_path}")
    return True


def main() -> int:
    repo = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_REPO
    patch_pipeline(repo)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
