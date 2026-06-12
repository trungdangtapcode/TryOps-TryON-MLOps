# VTON Evaluation Plan

## Metrics

Use a mix of quantitative proxies and human review:

- Garment fidelity.
- Identity preservation.
- Realism.
- Artifact severity.
- Latency.
- Memory footprint where available.
- Cost estimate per 100 generations.

## Implemented Lightweight Metrics

The current repository includes:

- Mean squared error.
- PSNR.
- Global luma SSIM approximation.
- Difference hash distance and similarity.
- Edge-delta proxy.
- Optional native C++ metric block when `artifacts/native/tryops_image_metrics_cli` exists.
- Native advanced VTON evaluation block when `artifacts/native/tryops_vton_eval_cli` exists.

These are smoke-test metrics, not a replacement for LPIPS, CLIP similarity, or human review. SSIM is included because the original structural similarity work was designed as a perceptual-quality alternative to pure error visibility metrics. dHash is included as a lightweight perceptual-hash proxy that can be verified in both Python and native C++ without neural dependencies.

Garment similarity is tracked separately from person-image structural metrics. The current local path compares the generated garment patch against the source garment, and `make vton-clip-similarity-sample` verifies neural CLIP scoring with the Transformers CLIP backend on the seeded sample. Production claims still need a fixed benchmark set, pinned local model weights, and confidence intervals.

Advanced VTON evaluation is now tracked in:

```bash
make vton-advanced-eval-sample
```

The sample writes `artifacts/eval/vton_advanced/vton_advanced_eval_report.json` and updates the generated model card. The native C++ evaluator computes:

- identity preservation as a face-region embedding proxy distance
- garment-region masked fidelity from the overlay patch
- pose consistency from torso-alignment geometry
- skin-tone and body-type slice quality gaps
- Bradley-Terry strengths over the seeded preference-study fixture

These are local production-contract metrics. Production identity and perceptual-quality claims should replace the proxy feature extractor with pinned ArcFace/InsightFace and LPIPS/OpenCLIP-style neural metrics at benchmark scale, and should replace the seeded fairness fixture with a licensed, representative evaluation set.

## Human Rubric

Each output receives 1 to 5 points for:

| Dimension | 1 | 3 | 5 |
| --- | --- | --- | --- |
| Realism | Clearly broken or artificial | Mostly plausible with visible artifacts | Looks natural |
| Garment fidelity | Texture/shape mostly lost | Some details preserved | Color, texture, and structure preserved |
| Identity preservation | Person identity or body shape badly changed | Minor identity/body distortion | Person identity and body shape preserved |
| Fit and alignment | Garment badly misplaced | Minor misalignment | Garment aligns with body and pose |
| Background consistency | Background disrupted | Small local artifacts | Background remains stable |

## Failure Labels

- `texture_loss`
- `sleeve_distortion`
- `identity_shift`
- `pose_failure`
- `background_artifact`
- `garment_color_shift`
- `body_shape_distortion`
- `edge_blending_failure`
- `occlusion_failure`
- `unsupported_pose`

## Promotion Rule

A VTON candidate should not become champion unless:

- Mean garment fidelity is at least 0.72.
- Mean identity preservation is at least 0.70.
- Artifact rate is at most 0.12.
- p95 latency is at most 12 seconds.
- Human review does not reveal a repeated severe failure mode.
