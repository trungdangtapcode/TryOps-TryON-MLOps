# Responsible AI Risk Mapping

Date: 2026-06-11

Run:

```bash
make governance-sample
```

Artifacts:

- `configs/governance_risk_controls.json`
- `artifacts/eval/governance/governance_report.json`

## Framework Sources

TryOps maps local risks to:

- NIST AI RMF: Govern, Map, Measure, and Manage.
- OWASP Top 10 for LLM Applications 2025.

The generated report records source URLs and produces machine-checkable coverage for both
frameworks.

## NIST AI RMF Mapping

The current risk register is mapped to NIST AI RMF functions:

| Risk | NIST Functions | Evidence |
| --- | --- | --- |
| VTON model is too heavy for available hardware | MAP, MEASURE, MANAGE | degraded-mode examples, async jobs, native preprocessing |
| LLM quantization breaks quality | MAP, MEASURE, MANAGE | golden prompts, quality gates, fallback routing |
| Dataset license is unclear | GOVERN, MAP, MANAGE | dataset inventory, data cards, synthetic demo data |
| Promotion is manual and subjective | GOVERN, MEASURE, MANAGE | policy-as-code, approvals, native policy bridge |
| Security evidence is missing | GOVERN, MAP, MEASURE, MANAGE | SBOM policy requirement, security cases, limitation tracking |
| Monitoring is superficial | MAP, MEASURE, MANAGE | metrics, Grafana dashboards, drift reports, structured logs |

## OWASP LLM Top 10 2025 Mapping

TryOps maps all ten OWASP 2025 LLM risks to local controls:

| OWASP ID | Risk | Local Controls |
| --- | --- | --- |
| LLM01:2025 | Prompt Injection | prompt-injection prompts, refusal behavior, security cases |
| LLM02:2025 | Sensitive Information Disclosure | refusal behavior, privacy boundary, sanitized logs |
| LLM03:2025 | Supply Chain | model-source documentation, SBOM policy requirement, limitation tracking |
| LLM04:2025 | Data and Model Poisoning | manifest validation, checksums, fixed evaluation sets |
| LLM05:2025 | Improper Output Handling | structured output mode, response schema, quality checks |
| LLM06:2025 | Excessive Agency | no external tools in baseline, safe aliases, approval gates |
| LLM07:2025 | System Prompt Leakage | hidden-instruction refusal, no system prompt persistence, security cases |
| LLM08:2025 | Vector and Embedding Weaknesses | retrieval excluded from current scope, documented future-work boundary |
| LLM09:2025 | Misinformation | expected-characteristic scoring, model card limitations |
| LLM10:2025 | Unbounded Consumption | max token validation, timeouts, quota checks, load tests |

## VTON Bias and Representation Limitations

The local VTON examples are synthetic and useful for reproducible smoke evidence, but they do not
represent the full range of body types, skin tones, poses, garment categories, cultural clothing, or
accessibility needs. This prevents any claim that the current VTON baseline is fair or broadly
representative.

Before adding real datasets or user-uploaded examples, the project must document:

- dataset license and consent constraints;
- garment category coverage;
- demographic and pose coverage where known;
- excluded populations or use cases;
- retention and deletion rules for person images;
- known failure modes such as identity shift, body-shape distortion, sleeve artifacts, and texture loss.

## Residual Risk

Open residual risks:

- Real neural VTON may exceed local latency or memory budgets.
- Quantized LLM quality has not been measured because neural model variants have not run locally.
- The Syft/Trivy/Cosign CI workflow and native contract evidence exist, but local Syft, Trivy, and
  Cosign execution artifacts are not generated in this workspace.
- Production telemetry exporters and durable log stores are not connected yet.
- Drift reports use deterministic local sample windows, not live production windows.
- Human approval and feedback workflows are still simulated through metadata and reports.

These residual risks should remain visible in the final report and demo narrative. They do not block
local proof of the MLOps contract, but they do block claims of production readiness.
