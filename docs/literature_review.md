# Literature Review Notes

This is the living research table for the roadmap. It turns the original source list into implementation requirements.

| Area | Source | Key Point | TryOps Requirement |
| --- | --- | --- | --- |
| MLOps maturity | Google Cloud MLOps CI/CD/CT architecture, https://docs.cloud.google.com/architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning | Production ML needs automated data validation, model validation, metadata, continuous delivery, and continuous training. | Pipelines must create evaluation evidence before promotion. |
| MLOps maturity | Azure MLOps maturity model, https://learn.microsoft.com/en-us/azure/architecture/ai-ml/guide/mlops-maturity-model | Higher maturity includes automated releases, tracked experiments, versioned code/models, production metrics, and retraining triggers. | TryOps targets maturity level 3-4 behavior in local form. |
| Model lifecycle | MLflow Model Registry, https://mlflow.org/docs/latest/ml/model-registry/ | Registry centralizes model lifecycle, versions, aliases, tags, and lineage. | Use champion/challenger/candidate/rejected aliases and metadata. |
| Technical debt | Hidden Technical Debt in ML Systems, https://papers.nips.cc/paper_files/paper/2015/hash/86df7dcfd896fcaf2674f757a2463eba-Abstract.html | ML systems accumulate debt through data dependencies, glue code, configuration, feedback loops, and monitoring gaps. | Keep data contracts, policy gates, lineage, and monitoring as first-class deliverables. |
| Governance | NIST AI RMF, https://www.nist.gov/itl/ai-risk-management-framework | AI risk must be governed, mapped, measured, and managed. | Maintain risk register and evidence-backed model promotion. |
| LLM security | OWASP Top 10 for LLM Applications, https://owasp.org/www-project-top-10-for-large-language-model-applications/ | LLM systems face prompt injection, data leakage, supply-chain, excessive agency, and overreliance risks. | Add prompt/security test cases and block unsafe promotion. |
| Supply chain | SLSA, https://slsa.dev/spec/v1.1/about | Stronger supply chains need provenance and tamper-resistant artifacts. | Generate SBOM/signature evidence where tooling exists. |
| VTON baseline | VITON-HD, https://arxiv.org/abs/2103.16874 | High-resolution VTON needs handling of misalignment and preservation of details. | Keep VITON-HD/HR-VITON as classical baseline fallback. |
| VTON dataset | Dress Code, https://arxiv.org/abs/2204.08532 | Multi-category high-resolution VTON introduces broader garment coverage. | Treat multi-category support as stretch; first demo can focus on upper-body. |
| VTON quality | HR-VITON, https://arxiv.org/abs/2206.14180 | Occlusion and misalignment are major failure modes. | Build failure gallery labels for occlusion, sleeve distortion, and misalignment. |
| Diffusion VTON | StableVITON, https://arxiv.org/abs/2312.01725 | Latent diffusion can learn semantic correspondence for try-on. | Compare diffusion-based quality against classical fallback when hardware allows. |
| Diffusion VTON | IDM-VTON, https://arxiv.org/abs/2403.05139 | Modern diffusion VTON improves authenticity in the wild. | Candidate primary visual demo if dependencies/hardware work. |
| Garment fidelity | FLDM-VTON, https://arxiv.org/abs/2404.14162 | Faithful garment detail preservation is central. | Add garment fidelity as required promotion metric. |
| Simpler VTON | CatVTON, https://arxiv.org/abs/2407.15886 | Simpler concatenation-based diffusion can reduce preprocessing burden. | Preferred first VTON research target because it supports MLOps simplicity. |
| LLM quantization | GPTQ, https://arxiv.org/abs/2210.17323 | One-shot post-training quantization can compress generative transformers. | Benchmark GPTQ variant if compatible model exists. |
| LLM quantization | SmoothQuant, https://arxiv.org/abs/2211.10438 | Activation smoothing enables efficient W8A8 quantization. | Document as production option, especially for hardware-backed inference. |
| LLM quantization | AWQ, https://arxiv.org/abs/2306.00978 | Protecting salient weights/channels helps 4-bit quality retention. | Benchmark AWQ or AWQ-prequantized model where available. |
| LLM acceleration | FlashAttention, https://arxiv.org/abs/2205.14135 | IO-aware attention reduces memory traffic and improves speed. | Track whether selected serving runtime uses optimized attention kernels. |
| LLM serving | vLLM, https://docs.vllm.ai/en/latest/ | vLLM provides high-throughput serving, batching, prefix caching, quantization options, and OpenAI-compatible APIs. | Use vLLM as optimized LLM serving target. |
| Native gateway | Axum docs, https://docs.rs/axum/latest/axum/ | Axum uses Tokio/Hyper/Tower and supports modular middleware such as tracing, auth, timeouts, and limits. | Rust gateway is the target production API boundary. |
| Native controller | Kubebuilder book, https://book.kubebuilder.io/ | Kubernetes APIs support declarative resources, validation, authz, self-healing, and reconciliation. | Go controller is the target platform reconciler for promotion/deployment state. |
| Observability | OpenTelemetry Rust, https://opentelemetry.io/docs/languages/rust/ | Rust services can emit standard traces and metrics through OpenTelemetry. | Rust gateway should export trace context and request IDs. |
| Inference runtime | Triton Inference Server, https://docs.nvidia.com/deeplearning/triton-inference-server/user-guide/docs/index.html | Triton supports multiple backends, HTTP/gRPC, batching, metrics, tracing, and model repositories. | Use Triton as stretch serving path for VTON/ONNX/TensorRT. |
| Inference runtime | ONNX Runtime, https://onnxruntime.ai/docs/ | ONNX Runtime supports cross-platform inference, multiple languages, hardware execution providers, and graph optimizations. | Export smaller models to ONNX when feasible for native/runtime serving. |

