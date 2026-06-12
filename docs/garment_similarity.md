# Garment Similarity

## Purpose

Garment similarity checks whether a generated VTON output preserves the source garment. It is separate from person-image structural metrics because a VTON output can remain structurally close to the input person while losing garment color, texture, or placement.

## Research Basis

CLIP and OpenCLIP are useful for this because they encode images and text into a shared embedding space. The local neural path now supports Hugging Face Transformers CLIP as the verified backend and OpenCLIP as the open-source checkpoint target when `open_clip` and pinned weights are available.

Current source references:

- `https://github.com/openai/CLIP`
- `https://github.com/mlfoundations/open_clip`
- `https://huggingface.co/docs/transformers/model_doc/clip`
- `https://arxiv.org/abs/2103.00020`

## Implemented Local Path

The local implementation has two layers:

- `proxy`: always-on deterministic garment-patch similarity.
- `clip`: optional neural CLIP execution. `transformers_clip` is verified locally with `openai/clip-vit-base-patch32`; `open_clip` remains supported when `open_clip_torch` and model weights are installed.

The proxy crops the generated output using the baseline overlay metadata, resizes the source garment to the crop, and combines:

- dHash similarity.
- Global structural similarity.
- RGB histogram intersection.
- Edge similarity.

The proxy is not CLIP. It remains useful as a dependency-free smoke metric, while the neural CLIP path provides image-image and image-text similarity when enabled.

## Commands

Run the local similarity sample:

```bash
make vton-garment-similarity-sample
```

Run manually:

```bash
PYTHONPATH=src python scripts/evaluate_garment_similarity.py GARMENT.png OUTPUT.png --report OUTPUT.png.json --prompt "a blue striped shirt"
```

Run the verified Transformers CLIP backend:

```bash
make vton-clip-similarity-sample
```

Enable OpenCLIP explicitly:

```bash
TRYOPS_ENABLE_OPENCLIP=1 PYTHONPATH=src python scripts/evaluate_garment_similarity.py GARMENT.png OUTPUT.png --report OUTPUT.png.json --prompt "a blue striped shirt" --enable-openclip --clip-backend open_clip
```

Neural CLIP is not enabled by default because pretrained weights may need a network download, and production runs should pin local model artifacts.

## Output Evidence

VTON comparison artifacts now include:

- `runs[].garment_similarity.proxy`
- `runs[].garment_similarity.clip`
- `winner_by_garment_similarity_proxy`
- `artifacts/eval/vton_clip/garment_clip_similarity.json` for the standalone verified neural sample

When CLIP is not enabled or dependencies are unavailable, `clip.available` remains false and the artifact records the dependency status and reason. The verified local neural sample currently records `clip.available=true`, `backend=transformers_clip`, `image_similarity=1.0`, and the best text prompt for the seeded garment.

## Completion Status

This completes D013 for local feasibility: a CLIP-compatible model is installed through Transformers, runs against the seeded VTON sample, and produces verified image-image plus image-text similarity scores. The production-grade next step is broader fixed-set evaluation with confidence intervals and pinned local checkpoints.
