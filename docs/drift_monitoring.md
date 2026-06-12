# Drift Monitoring

Date: 2026-06-11

TryOps now has dependency-free local drift reports for the two production input surfaces:

- VTON image metadata distributions.
- LLM prompt length and topic distributions.

Run:

```bash
make drift-sample
```

Artifacts:

- `artifacts/eval/drift/image_metadata_drift.json`
- `artifacts/eval/drift/prompt_topic_drift.json`
- `artifacts/eval/drift/drift_summary.json`

## Method

The local drift module compares a reference window and a current window. It computes per-feature
distribution distance, then declares dataset-level drift when enough features cross the configured
threshold.

Implemented feature groups:

- VTON numerical metadata: width, height, aspect ratio, pixel count, and file size.
- VTON categorical metadata: role, image format, and color mode.
- LLM prompt descriptors: character length, estimated token length, expected-check count, and topic.

The distance metric is Hellinger distance over fixed histograms or categorical distributions. This
keeps the local evidence standard-library friendly and deterministic. The production path can later
replace or augment it with Evidently data drift and text descriptor reports.

## Privacy Boundary

The reports store aggregate statistics and category counts. They do not write raw prompt text,
uploaded image paths, user IDs, or image bytes.

## Research Basis

- Evidently compares reference and current datasets for individual column drift and can combine
  column results into dataset-level drift.
- Evidently recommends descriptors such as text length for text data evaluation and drift monitoring.

Sources:

- https://docs.evidentlyai.com/metrics/explainer_drift
- https://docs.evidentlyai.com/docs/library/descriptors

## Current Limitation

The local sample uses deterministic simulated current windows so it can run without production
traffic. Before using drift as an alert gate, replace the sample window with real request metadata
from sanitized telemetry or batch evaluation artifacts.
