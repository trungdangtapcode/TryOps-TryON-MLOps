"""Real Transformers-backed LLM inference for lab benchmarks.

This module executes a genuine open-source instruct model and emits the same
``tryops.llm_generation.v1`` artifact shape as other LLM adapters. It fails
closed when torch, transformers, the GPU, or model weights are unavailable.
"""

from __future__ import annotations

from time import perf_counter
from typing import Any

from .llm_baseline import (
    REAL_MODEL_TARGET,
    _safety_flags,
    classify_prompt,
    estimate_local_cost,
    estimate_tokens,
)
from .llm_phase_timing import build_phase_timing

# Loaded models are cached per-process so a benchmark over many prompts pays the
# load cost once. The production serving path uses vLLM; this is the lab layer.
_MODEL_CACHE: dict[str, Any] = {}

REAL_ADAPTER = "transformers-real"
REAL_VERSION = "0.1.0"


def real_model_available() -> bool:
    """Return True only if torch + transformers import cleanly."""

    try:
        import torch  # noqa: F401
        import transformers  # noqa: F401
    except Exception:
        return False
    return True


def _build_quant_config(quantization: str):
    """Return a BitsAndBytesConfig for ``8bit``/``4bit`` or None for ``none``."""

    if quantization in {"none", "fp16", "fp32"}:
        return None
    import torch
    from transformers import BitsAndBytesConfig

    if quantization == "8bit":
        return BitsAndBytesConfig(load_in_8bit=True)
    if quantization == "4bit":
        return BitsAndBytesConfig(
            load_in_4bit=True,
            bnb_4bit_quant_type="nf4",
            bnb_4bit_compute_dtype=torch.float16,
            bnb_4bit_use_double_quant=True,
        )
    raise ValueError(f"unsupported quantization '{quantization}'")


def load_model(model_id: str, quantization: str = "none", *, cache: bool = True) -> tuple[Any, Any, str]:
    """Load a tokenizer+model, optionally quantized. ``cache=False`` for Pareto
    sweeps that need to free VRAM between variants for accurate measurement."""

    key = f"{model_id}|{quantization}"
    if cache and key in _MODEL_CACHE:
        return _MODEL_CACHE[key]

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    device = "cuda" if torch.cuda.is_available() else "cpu"
    quant_config = _build_quant_config(quantization) if device == "cuda" else None
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    if quant_config is not None:
        # bitsandbytes places weights on the GPU itself; no .to(device) needed.
        model = AutoModelForCausalLM.from_pretrained(
            model_id, quantization_config=quant_config, device_map={"": 0}
        )
    else:
        dtype = torch.float16 if device == "cuda" else torch.float32
        model = AutoModelForCausalLM.from_pretrained(model_id, dtype=dtype).to(device)
    model.eval()
    loaded = (tokenizer, model, device)
    if cache:
        _MODEL_CACHE[key] = loaded
    return loaded


def _load(model_id: str) -> tuple[Any, Any, str]:
    return load_model(model_id, "none", cache=True)


def clear_model_cache() -> None:
    """Drop cached models and free CUDA memory (used between Pareto variants)."""

    _MODEL_CACHE.clear()
    try:
        import gc

        import torch

        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    except Exception:
        pass


def generate_once(
    tokenizer: Any,
    model: Any,
    device: str,
    prompt: str,
    *,
    max_tokens: int = 128,
) -> dict[str, Any]:
    """Run one greedy generation on a pre-loaded model and measure real metrics.

    Returns text plus measured latency, decode tokens/sec, and peak GPU VRAM.
    """

    import torch

    messages = [{"role": "user", "content": str(prompt)}]
    input_started = perf_counter()
    try:
        input_ids = tokenizer.apply_chat_template(
            messages, add_generation_prompt=True, return_tensors="pt"
        ).to(device)
    except Exception:
        input_ids = tokenizer(str(prompt), return_tensors="pt").input_ids.to(device)
    attention_mask = torch.ones_like(input_ids)
    prompt_prepare_ms = max((perf_counter() - input_started) * 1000.0, 0.001)

    if device == "cuda":
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.synchronize()
    started = perf_counter()
    with torch.no_grad():
        generated = model.generate(
            input_ids,
            attention_mask=attention_mask,
            max_new_tokens=max_tokens,
            do_sample=False,
            pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
        )
    if device == "cuda":
        torch.cuda.synchronize()
    elapsed_ms = max((perf_counter() - started) * 1000.0, 0.001)

    new_tokens = generated[0][input_ids.shape[1] :]
    text = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
    output_tokens = int(new_tokens.shape[0])
    gpu_memory_gb = (
        round(torch.cuda.max_memory_allocated() / 1e9, 6) if device == "cuda" else 0.0
    )
    return {
        "text": text,
        "latency_ms": round(elapsed_ms, 3),
        "tokens_per_second": round(output_tokens / max(elapsed_ms / 1000.0, 0.001), 6),
        "generated_tokens": output_tokens,
        "gpu_memory_gb": gpu_memory_gb,
        "phase_timing": build_phase_timing(
            input_tokens=int(input_ids.shape[1]),
            output_tokens=output_tokens,
            prefill_ms=prompt_prepare_ms,
            decode_ms=elapsed_ms,
            source="transformers-generate",
            semantics="transformers_proxy_prompt_prepare_plus_generate",
            total_latency_ms=prompt_prepare_ms + elapsed_ms,
            notes=[
                "Prompt preparation is measured separately.",
                "Transformers model.generate does not expose internal prefill/decode split through this contract; decode_ms is full generate wall time.",
            ],
        ),
    }


def generate_real_response(
    *,
    prompt: str,
    model_alias: str = "champion",
    max_tokens: int = 256,
    structured: bool = True,
    model_id: str = REAL_MODEL_TARGET,
) -> dict[str, Any]:
    """Generate a real LLM response without deterministic fallback."""

    clean_prompt = str(prompt).strip()
    if not clean_prompt:
        raise ValueError("prompt cannot be empty")

    if not real_model_available():
        raise RuntimeError("real LLM inference requires torch and transformers")

    try:
        import torch

        tokenizer, model, device = _load(model_id)

        messages = [{"role": "user", "content": clean_prompt}]
        input_started = perf_counter()
        try:
            input_ids = tokenizer.apply_chat_template(
                messages, add_generation_prompt=True, return_tensors="pt"
            ).to(device)
        except Exception:
            input_ids = tokenizer(clean_prompt, return_tensors="pt").input_ids.to(device)
        prompt_prepare_ms = max((perf_counter() - input_started) * 1000.0, 0.001)

        if device == "cuda":
            torch.cuda.reset_peak_memory_stats()
            torch.cuda.synchronize()

        attention_mask = torch.ones_like(input_ids)
        started = perf_counter()
        with torch.no_grad():
            generated = model.generate(
                input_ids,
                attention_mask=attention_mask,
                max_new_tokens=max_tokens,
                do_sample=False,
                pad_token_id=tokenizer.pad_token_id or tokenizer.eos_token_id,
            )
        if device == "cuda":
            torch.cuda.synchronize()
        elapsed_ms = max((perf_counter() - started) * 1000.0, 0.001)

        new_tokens = generated[0][input_ids.shape[1] :]
        decoded = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()
        output_token_count = int(new_tokens.shape[0])
        tokens_per_second = output_token_count / max(elapsed_ms / 1000.0, 0.001)
        gpu_memory_gb = (
            round(torch.cuda.max_memory_allocated() / 1e9, 6) if device == "cuda" else 0.0
        )
    except Exception as exc:
        raise RuntimeError(f"real LLM inference failed: {type(exc).__name__}: {exc}") from exc

    prompt_class = classify_prompt(clean_prompt)
    safety = _safety_flags(clean_prompt, decoded)
    cost_estimate = estimate_local_cost(
        input_tokens=estimate_tokens(clean_prompt),
        output_tokens=output_token_count,
    )
    cost_estimate["basis"] = "local real Transformers inference; replace with measured infrastructure cost"
    phase_timing = build_phase_timing(
        input_tokens=int(input_ids.shape[1]),
        output_tokens=output_token_count,
        prefill_ms=prompt_prepare_ms,
        decode_ms=elapsed_ms,
        source="transformers-generate",
        semantics="transformers_proxy_prompt_prepare_plus_generate",
        total_latency_ms=prompt_prepare_ms + elapsed_ms,
        notes=[
            "Prompt preparation is measured separately.",
            "Transformers model.generate does not expose internal prefill/decode split through this contract; decode_ms is full generate wall time.",
        ],
    )

    payload: dict[str, Any] = {
        "schema_version": "tryops.llm_generation.v1",
        "status": "completed",
        "model": {
            "alias": model_alias,
            "name": model_id,
            "version": REAL_VERSION,
            "adapter": REAL_ADAPTER,
            "real_model_target": model_id,
            "target_license": "Apache-2.0",
            "device": device,
            "dtype": "float16" if device == "cuda" else "float32",
        },
        "prompt": {
            "characters": len(clean_prompt),
            "estimated_tokens": estimate_tokens(clean_prompt),
            "class": prompt_class,
        },
        "output": {
            "text": decoded,
            "estimated_tokens": output_token_count,
            "truncated": output_token_count >= max_tokens,
        },
        "metrics": {
            "latency_ms": round(elapsed_ms, 3),
            "tokens_per_second": round(tokens_per_second, 6),
            "memory_gb": gpu_memory_gb,
            "gpu_memory_gb": gpu_memory_gb,
            "generated_tokens": output_token_count,
            "phase_timing": phase_timing,
        },
        "cost_estimate": cost_estimate,
        "safety": safety,
    }
    if structured:
        payload["structured_answer"] = {
            "intent": prompt_class,
            "text": decoded,
        }
    return payload
