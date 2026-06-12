# Month 1 Execution Plan

## Current Sprint

Goal: turn the roadmap into a real foundation.

Completed in this scaffold:

- Repository structure
- Open-source stack decision
- Promotion policy gate
- Sample passing and failing VTON candidates
- Dataset manifest validation component
- VTON and LLM metric summarizers
- Lineage record builder
- API skeleton
- Compose file for core services
- Local promotion pipeline that writes evidence artifacts
- Native C++ policy engine with tests
- Rust gateway scaffold
- Go controller scaffold
- C4 architecture diagrams
- VTON and LLM model-choice ADRs
- Dataset inventory and ingestion utilities
- Standard-library tests

## Verified Commands

```bash
make test
make validate-sample
make pipeline-sample
make native-cpp-test
make native-tooling
make smoke
```

Generated evidence path:

```text
reports/generated/vton-catvton-2026-06-11-001/
```

Generated files:

- `promotion_decision.json`
- `data_validation.json`
- `lineage.json`
- `registry_entry.json`
- `model_card.md`
- `data_card.md`

## Next Sprint

1. Add real dataset manifest examples.
2. Add model card and data card templates.
3. Add MLflow tracking integration around policy decisions.
4. Add Prometheus metrics endpoint to the API.
5. Choose the first VTON model path: CatVTON first, VITON-HD fallback.
6. Choose the first LLM path: small instruct model plus vLLM benchmark if hardware supports it.
