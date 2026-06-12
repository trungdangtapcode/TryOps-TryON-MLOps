# Risk Register

| ID | Risk | Impact | Control |
| --- | --- | --- | --- |
| R001 | VTON model is too heavy for available hardware | Demo becomes unreliable | Use cached outputs, async jobs, and a smaller benchmark set |
| R002 | LLM quantization breaks quality | Optimization claim becomes weak | Keep baseline comparison and quality gate |
| R003 | Dataset license is unclear | Results cannot be presented safely | Record licenses in data cards |
| R004 | Promotion is manual and subjective | MLOps story weakens | Enforce policy-as-code gate |
| R005 | Security evidence is missing | Enterprise story weakens | Generate SBOM, scan with Trivy, sign artifacts |
| R006 | Monitoring is superficial | Production story weakens | Instrument real API requests and model metadata |

## Framework Mapping

Generated evidence:

```bash
make governance-sample
```

Artifact:

```text
artifacts/eval/governance/governance_report.json
```

Current framework coverage:

- NIST AI RMF functions: Govern, Map, Measure, Manage.
- OWASP Top 10 for LLM Applications 2025: LLM01 through LLM10.
- Responsible-AI limitations: VTON representation, VTON visual harm, LLM reliability, and local-only operational evidence.

Details:

- `configs/governance_risk_controls.json`
- `docs/responsible_ai_risk_mapping.md`
