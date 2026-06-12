# Known Limitations

- Rust gateway build/test/smoke now pass locally, including native TLS smoke, but the gateway is
  still a local single-node artifact rather than a hardened multi-node edge deployment with
  external identity-provider federation and distributed quota admission validation.
- Go is installed and the Go controller plus guardrail sidecar build and smoke locally.
- The VTON and LLM model endpoints are still stubs.
- Real datasets are not downloaded or committed.
- Current metrics are sample/evidence metrics, not real benchmark results.
- Docker Compose services run locally for the smoke path, but the stack is still a single-node local
  profile rather than a hardened cluster deployment.
- DVC/MinIO data versioning is verified locally through `make dvc-minio-sample`; a clean-machine
  `dvc pull` restore drill is still future hardening.
- MLflow integration is designed but not yet writing to a live MLflow server.
- Grafana dashboards are provisioned locally, but model-quality and some cost/capacity panels still need production metric exporters.
- The local semantic cache uses deterministic lexical embeddings; production should replace this with neural embeddings plus FAISS/Qdrant or an equivalent vector index.
- Continuous-batching evidence is currently a native C++ scheduler model seeded from local LLM
  sensitivity artifacts; production serving claims still require a live vLLM benchmark with real
  request traces.
- vLLM serving is now probeable through native Go, and the machine has an NVIDIA L4 GPU, but the
  current report is skipped because the `vllm` binary/package is absent and no vLLM endpoint is
  serving at the default URL.
- GPTQ/AWQ candidates are verified through native Go against real Qwen2.5-0.5B quantized repos,
  but live loading is not run because `gptqmodel`/`auto_gptq` and `awq`/`autoawq` are absent.
- GGUF is validated as a native C++ artifact preflight over a real SmolLM2 Q2_K `.gguf` file, but
  live llama.cpp generation was not run because `llama-cli` is not installed in this workspace.
- The VTON advanced evaluator uses native deterministic identity/fidelity proxies and a seeded
  fairness/preference fixture; production claims require a pinned neural face-embedding model,
  learned perceptual metrics, and a representative human evaluation panel.
- The Rust quota gateway now supports optional local file durability, Postgres usage upsert
  mirroring, Valkey-compatible counter mirroring, and hashed tenant snapshots, but distributed
  multi-gateway atomic admission, outage policy, and restore drills still need production validation.
- Drift reports are generated from deterministic local sample windows, not live production request windows yet.
- Chaos drills are deterministic local SLI-window injections, not live Kubernetes Chaos Mesh or
  LitmusChaos experiments yet.
- Admin API-key authorization is a local least-privilege simulation with static demo keys. PA060 now
  has native plan-mode evidence for hash-only API-key rotation, Vault/External Secrets manifests,
  and Kubernetes workload identity, but production OIDC/JWKS plus live Vault secret fetch/rotation
  still need to be exercised.
- A local SPDX SBOM fallback is generated, `make vulnerability-scan-sample` runs the available `npm audit` check for `web/`, and `.github/workflows/ci.yml` plus `make native-ci-contract-sample` define the Syft/Trivy/Cosign production path, but Syft, Trivy, Grype, pip-audit, gitleaks, osv-scanner, and Cosign are not installed in this workspace.
- Model provenance uses a local DSSE-shaped digest bundle verified by native C++; real Sigstore
  keyless OIDC identity and Rekor transparency-log proof are not generated locally yet.
- Local vulnerability evidence is partial: npm audit found 0 web vulnerabilities, but Python, container, OS-package, secret, and misconfiguration scans still need production scanners.
