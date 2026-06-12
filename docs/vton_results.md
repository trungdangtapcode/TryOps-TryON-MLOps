# VTON Baseline Results

## Current Result

The current repository has a deterministic naive overlay baseline. It is not the final virtual try-on model, but it exercises the full MLOps path:

- Input validation.
- PNG metadata extraction.
- Preflight cache key.
- Person and garment normalization.
- Output generation.
- Latency measurement.
- Stage-level latency measurement.
- Output checksum.
- JSON sidecar report.
- Comparison across two configurations.
- dHash and edge-delta perceptual proxy metrics.
- Native C++ image metric evidence when the CLI has been built.
- Garment-patch similarity proxy plus verified Transformers CLIP garment-image/text scoring.
- Failure-gallery artifact.
- Advanced native evaluation evidence for identity, masked garment fidelity, pose consistency, fairness gaps, and Bradley-Terry ranking.

## Verified Command

```bash
make vton-compare-sample
make vton-advanced-eval-sample
```

## Latest Synthetic Comparison

Two configurations are compared:

| Run | Behavior | Expected Weakness |
| --- | --- | --- |
| `naive_standard` | Smaller garment, higher torso placement | Edge blending failure |
| `naive_wide_lower` | Wider garment, lower placement | Edge blending, body distortion, pose failure |

The generated comparison writes:

- `artifacts/eval/vton_comparison/comparison.json`
- `artifacts/eval/vton_comparison/error_gallery.json`
- `artifacts/eval/vton_comparison/naive_standard.png`
- `artifacts/eval/vton_comparison/naive_wide_lower.png`
- `artifacts/eval/vton_advanced/vton_advanced_eval_report.json`

## Latest Advanced Evaluation

`make vton-advanced-eval-sample` runs the native C++ evaluator and currently records:

- identity embedding-proxy score
- garment-region masked fidelity score
- pose-consistency score
- seeded skin-tone and body-type fairness gaps
- Bradley-Terry preference winner from `samples/eval/vton_preference_study.json`
- generated model-card bias and limitation notes

## Strengths

- Fully reproducible with no GPU and no model download.
- Produces real image artifacts.
- Captures latency and lineage.
- Captures stage latency and native metric evidence.
- Captures local garment-preservation evidence.
- Captures local advanced-evaluation and fairness evidence.
- Gives a baseline for future CatVTON/IDM-VTON comparison.
- Demonstrates why naive overlays are insufficient for real VTON.

## Failures

- No generative blending.
- No body parsing.
- No pose-aware garment warping.
- No occlusion handling.
- No texture-aware boundary repair.
- Neural CLIP is verified on the seeded sample, but not yet run as a fixed-set benchmark with confidence intervals.
- Identity and fairness evidence currently uses deterministic local proxies and seeded slices, not a representative human panel.
- Only PNG input is supported by the local lightweight baseline.

## Future Work

1. Add CatVTON adapter.
2. Add IDM-VTON stretch adapter.
3. Run CLIP/OpenCLIP garment-image or garment-text similarity across the fixed VTON benchmark with pinned local model weights and confidence intervals.
4. Replace the seeded preference fixture with a representative human preference study.
5. Promote only a model that passes garment fidelity, identity preservation, fairness, artifact-rate, latency, and governance gates.
