# VTON Naive Baseline

## Purpose

The naive overlay baseline is a deterministic local VTON adapter. It is not the final CatVTON or IDM-VTON model. Its job is to make the MLOps lifecycle executable before heavyweight model dependencies are installed.

## What It Does

1. Runs VTON preflight validation.
2. Reads PNG person and garment images.
3. Normalizes the person image to RGB.
4. Builds optional mask and pose preprocessing artifacts.
5. Resizes the garment with nearest-neighbor scaling.
6. Overlays the garment in a deterministic torso region.
7. Writes a PNG output.
8. Writes a JSON sidecar with preprocessing, latency, output checksum, and lineage.

## Commands

Create synthetic demo inputs and run the baseline:

```bash
make vton-baseline-sample
```

Compare two baseline configurations and generate an error gallery:

```bash
make vton-compare-sample
```

Run manually:

```bash
PYTHONPATH=src python scripts/run_vton_baseline.py PERSON.png GARMENT.png --output artifacts/demo/vton/output.png
```

## Output Evidence

The baseline report includes:

- Model name and version.
- Person and garment metadata.
- Person and garment checksums.
- Preflight cache key.
- Person normalization metadata.
- Garment normalization metadata.
- Optional person and garment mask metadata.
- Optional heuristic pose hints.
- Native C++ preprocessing evidence when the CLI is built.
- Overlay region.
- Output checksum.
- Latency.
- Adapter lineage.

## Why This Is Useful

This baseline is intentionally simple, but it gives the platform:

- A real callable VTON module.
- A real output artifact.
- A local demo path.
- A testable API adapter.
- Latency measurement.
- Lineage before real model integration.

## Next Target

Replace or augment this adapter with CatVTON first. Keep IDM-VTON as the higher-visual-quality stretch target and VITON-HD or HR-VITON as the classical fallback.
