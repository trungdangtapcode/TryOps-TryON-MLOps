# Data Governance

## Data Zones

- `data/raw`: source files, never mutated.
- `data/validated`: data that passed schema and quality checks.
- `data/processed`: model-ready preprocessing outputs.
- `samples`: tiny checked-in examples for policy and demo scaffolding.

## Dataset Manifest Requirements

Each image entry must include:

- `id`
- `path`
- `split`
- `checksum`
- `license`

Dataset-level license and usage restrictions are tracked in:

```text
configs/dataset_licenses.json
```

The supply-chain report audits that inventory and writes the result to:

```text
artifacts/eval/supply_chain/supply_chain_report.json
```

Runtime ingestion can also attach:

- `format`
- `width`
- `height`
- `color_mode`
- `size_bytes`

Allowed splits:

- `train`
- `validation`
- `test`
- `demo`
- `calibration`

## Privacy Rules

- Do not commit private person images.
- Use public or synthetic demo assets.
- Store uploaded images only as long as needed for the demo.
- Keep request metadata without storing unsafe personal content.
- Reject unsupported, oversized, corrupted, or too-small images before model inference.

## Current Dataset License Decisions

- Synthetic demo data is allowed for local smoke tests and demos only.
- VITON-HD is treated as research/non-commercial only under CC-BY-NC-4.0 and is not stored here.
- Dress Code is treated as non-commercial academic only, not available to private companies, and is not stored here.
- User-uploaded images are transient inference inputs and are not training data without separate consent.
