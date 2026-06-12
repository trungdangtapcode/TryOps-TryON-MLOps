# VTON Preflight Layer

## Purpose

The VTON preflight layer prepares the project for real CatVTON, IDM-VTON, VITON-HD, or HR-VITON integration without pretending that model inference is complete.

It currently handles:

- Person image validation.
- Garment image validation.
- PNG and JPEG format detection.
- Width, height, color-mode metadata extraction.
- Size limits.
- SHA-256 checksums.
- Deterministic cache key generation.
- Preflight latency measurement.
- JSON cache artifact creation.

## Why This Matters

Real VTON models are heavy and have fragile preprocessing requirements. This layer gives the MLOps platform a stable safety and evidence boundary before the model runtime:

1. Invalid input is rejected before GPU work.
2. Request metadata can be logged without storing private image content.
3. Cache keys make repeated preprocessing reproducible.
4. Later model outputs can link back to validated input metadata and checksums.

## Command

```bash
PYTHONPATH=src python scripts/run_vton_preflight.py PERSON.png GARMENT.png --cache-dir artifacts/cache/vton_preflight
```

## Current Limitations

- It does not resize pixels yet.
- It does not perform segmentation, pose estimation, or human parsing.
- It does not run a VTON model.
- It supports PNG/JPEG metadata only.

## Next Step

Add an actual model adapter interface:

```text
VtonAdapter
  -> validate inputs through preflight
  -> call CatVTON or fallback model
  -> write output image
  -> write lineage and metric record
```

