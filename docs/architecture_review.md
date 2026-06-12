# Architecture Review: What Breaks First?

## Likely Failure Points

- GPU or model dependency unavailable during demo.
- Dataset license or download path unclear.
- VTON model latency too high for synchronous UI.
- LLM quantization dependency incompatible with local hardware.
- Monitoring looks decorative instead of tied to real requests.
- Promotion evidence exists in docs but not artifacts.
- Rust toolchain missing on evaluator machine.

## Controls Added

- Local `make smoke` path.
- Generated promotion evidence artifacts.
- Cached/degraded-mode design.
- Native C++ policy module that compiles with available `g++`.
- Go controller/guardrail services verified locally; Rust gateway artifact benchmarked as target
  production boundary.
- Risk register and governance docs.

## Next Hardening Moves

- Add real request metrics endpoint.
- Add registry metadata persistence.
- Add explicit release log and rollback command.
- Add seeded UI or CLI demo path.
- Add Rust toolchain bootstrap notes and CI rebuild for the gateway.
