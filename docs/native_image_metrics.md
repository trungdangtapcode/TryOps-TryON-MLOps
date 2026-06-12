# Native Image Metrics

Date: 2026-06-11

## Purpose

TryOps now has a second verified low-level integration: a dependency-free C++ image metric CLI.

Path:

```text
native/cpp/tryops_image_metrics/src/tryops_image_metrics_cli.cpp
```

Verified command:

```bash
make native-image-metrics-sample
```

## Metrics

The native CLI receives raw RGB bytes through a stable line-based wire format and computes:

- MSE
- PSNR
- 64-bit dHash Hamming distance
- dHash similarity
- edge-delta proxy

The Python metric path computes the same lightweight perceptual proxies and adds the native result
block to VTON comparison artifacts when the binary exists.

## Why This Exists

LPIPS and CLIP similarity require neural models and extra dependencies. The roadmap allows another
perceptual similarity metric if dependencies allow, so dHash is used as a dependency-free local
proxy. It is not a replacement for LPIPS, CLIP, or human review; it is an auditable local metric that
can run inside the current sandbox and be verified by C++.

## Evidence

The comparison artifact includes the native block here:

```text
artifacts/eval/vton_comparison/comparison.json
```

Example fields:

- `metrics_against_person.dhash_similarity`
- `metrics_against_person.edge_delta`
- `metrics_against_person.native.available`
- `metrics_against_person.native.schema_version`
