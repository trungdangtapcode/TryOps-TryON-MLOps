# Multi-GPU FASHN Serving Plan

## Goal

Run real FASHN VTON inference across multiple GPUs without presenting fallback, mock, CPU, or demo behavior as production.

The design must:

- Keep the API separate from model inference.
- Route jobs only to ready real-model workers.
- Pin each worker to a specific GPU.
- Expose per-worker health, readiness, logs, and metrics.
- Monitor GPU, host, process, queue, and job lifecycle telemetry in Grafana.
- Fail closed when no real model worker is available.

## Current State

The current local stack starts FASHN through a host-side router:

```text
API container
  -> http://host.docker.internal:18100
  -> host FASHN router
  -> private host worker sockets
  -> NVIDIA GPU
```

Current files:

- Router PID: `artifacts/runtime/fashn-vton-router.pid`
- Worker registry: `artifacts/runtime/fashn-vton-workers.json`
- Router raw log: `artifacts/logs/fashn-vton-router.log`
- Worker raw logs: `artifacts/logs/fashn-vton-worker-*.log`
- Router structured log: `artifacts/logs/fashn_vton_router_events.jsonl`
- API-side `TRYOPS_REAL_VTON_URL` events: `artifacts/logs/api_events.jsonl`
- Worker structured logs: `artifacts/logs/fashn_vton_worker_*_events.jsonl`
- API env: `TRYOPS_REAL_VTON_URL=http://host.docker.internal:18100`
- Default router port: `FASHN_VTON_ROUTER_PORT=18100`
- Direct single-worker debug port: `FASHN_VTON_PORT=18101`

This implements the router abstraction and per-worker process model. Remaining production work is deeper GPU/process exporters, Grafana panels for those metrics, and a deployment-manager layer for non-local environments.

## Abstraction Model

Expose one logical model endpoint to the rest of TryOps:

```env
TRYOPS_REAL_VTON_URL=http://host.docker.internal:18100
```

Everything behind that endpoint is an implementation detail owned by the FASHN serving layer.

```text
API
  -> TRYOPS_REAL_VTON_URL
  -> FASHN router/supervisor
      -> worker registry
      -> private worker GPU 0
      -> private worker GPU 1
      -> private worker GPU 2
```

The app should not know worker ports, GPU IDs, socket paths, or how many workers exist. Prometheus should not need to know per-worker host ports either. The router/supervisor should export aggregated per-worker metrics with labels like `worker_id`, `gpu_id`, and `gpu_uuid`.

Recommended abstraction boundaries:

| Layer | Stable contract | Hidden implementation detail |
| --- | --- | --- |
| API to model serving | `TRYOPS_REAL_VTON_URL` | worker count, worker ports, GPU assignment |
| Router to workers | worker registry | Unix sockets, ephemeral loopback ports, process PIDs |
| Prometheus to serving | router `/metrics` | individual worker scrape endpoints |
| Grafana to logs | Loki labels and `job_id`/`request_id` | raw worker file paths |
| Hardware telemetry | exporter service names | host exporter ports |

Local worker discovery should be generated from a small high-level config, not hardcoded URLs:

```env
TRYOPS_FASHN_ROUTER_BIND=127.0.0.1:18100
TRYOPS_FASHN_GPU_IDS=0,1,2
TRYOPS_FASHN_WORKER_TRANSPORT=unix
TRYOPS_FASHN_WORKER_SOCKET_DIR=artifacts/runtime/fashn-workers
TRYOPS_FASHN_WORKER_MAX_CONCURRENCY=1
```

The router/supervisor expands that into private workers:

```text
gpu0 -> artifacts/runtime/fashn-workers/gpu0.sock
gpu1 -> artifacts/runtime/fashn-workers/gpu1.sock
gpu2 -> artifacts/runtime/fashn-workers/gpu2.sock
```

If Unix sockets are not implemented yet, use ephemeral or loopback-only ports internally, but keep them out of `.env`, `PORT.md`, Prometheus config, and API config.

## Worker Configuration Design

Use a two-level config:

1. Simple `.env` knobs for local defaults.
2. Optional worker config file for datacenter or multi-GPU hosts.

The API should never consume this worker config directly. Only the FASHN router/supervisor reads it.

### Local Minimal Config

For a local multi-GPU workstation, this is enough:

```env
TRYOPS_REAL_VTON_URL=http://host.docker.internal:18100
TRYOPS_FASHN_ROUTER_BIND=127.0.0.1:18100
TRYOPS_FASHN_GPU_IDS=0,1,2
TRYOPS_FASHN_WORKER_MAX_CONCURRENCY=1
TRYOPS_FASHN_WORKER_TRANSPORT=unix
TRYOPS_FASHN_WORKER_SOCKET_DIR=artifacts/runtime/fashn-workers
TRYOPS_FASHN_WORKER_PRELOAD=1
TRYOPS_FASHN_REQUIRE_CUDA=1
TRYOPS_FASHN_ALLOW_CPU_FALLBACK=0
```

The router expands `TRYOPS_FASHN_GPU_IDS=0,1,2` into generated workers:

| Generated worker | CUDA pin | Private endpoint | Public exposure |
| --- | --- | --- | --- |
| `gpu0` | `CUDA_VISIBLE_DEVICES=0` | `artifacts/runtime/fashn-workers/gpu0.sock` | none |
| `gpu1` | `CUDA_VISIBLE_DEVICES=1` | `artifacts/runtime/fashn-workers/gpu1.sock` | none |
| `gpu2` | `CUDA_VISIBLE_DEVICES=2` | `artifacts/runtime/fashn-workers/gpu2.sock` | none |

The only stable endpoint remains:

```env
TRYOPS_REAL_VTON_URL=http://host.docker.internal:18100
```

### Datacenter Worker Config File

For a shared machine, prefer an explicit config file because GPU index ordering can change. Use GPU UUIDs when available.

Proposed file:

```text
configs/fashn-workers.local.yml
```

Example:

```yaml
schema_version: tryops.fashn_workers.v1

router:
  bind: "127.0.0.1:18100"
  public_url_for_api: "http://host.docker.internal:18100"
  worker_transport: "unix"
  worker_socket_dir: "artifacts/runtime/fashn-workers"
  registry_path: "artifacts/runtime/fashn-vton-workers.json"
  routing_policy: "least_inflight"
  request_timeout_seconds: 240
  no_ready_worker_status: 503

defaults:
  weights_dir: "artifacts/models/fashn-vton-1.5"
  python: "artifacts/venvs/fashn-vton/bin/python"
  require_cuda: true
  allow_cpu_fallback: false
  gpu_first_load: true
  preload: true
  max_concurrency: 1
  min_available_host_memory_mb: 4096
  startup_timeout_seconds: 300
  request_timeout_seconds: 240
  cuda_module_loading: "LAZY"
  pytorch_cuda_alloc_conf: "expandable_segments:True"

workers:
  - worker_id: "fashn-gpu0"
    gpu_id: "0"
    gpu_uuid: "GPU-REPLACE-WITH-NVIDIA-SMI-UUID"
    enabled: true
    socket_path: "artifacts/runtime/fashn-workers/fashn-gpu0.sock"
    pid_file: "artifacts/runtime/fashn-vton-worker-fashn-gpu0.pid"
    log_file: "artifacts/logs/fashn-vton-worker-fashn-gpu0.log"
    structured_log_file: "artifacts/logs/fashn_vton_worker_fashn-gpu0_events.jsonl"

  - worker_id: "fashn-gpu1"
    gpu_id: "1"
    gpu_uuid: "GPU-REPLACE-WITH-NVIDIA-SMI-UUID"
    enabled: true
    socket_path: "artifacts/runtime/fashn-workers/fashn-gpu1.sock"
    pid_file: "artifacts/runtime/fashn-vton-worker-fashn-gpu1.pid"
    log_file: "artifacts/logs/fashn-vton-worker-fashn-gpu1.log"
    structured_log_file: "artifacts/logs/fashn_vton_worker_fashn-gpu1_events.jsonl"
```

Set:

```env
TRYOPS_FASHN_WORKERS_CONFIG=configs/fashn-workers.local.yml
TRYOPS_REAL_VTON_URL=http://host.docker.internal:18100
```

### GPU ID Selection

Prefer GPU UUID over index in datacenter environments.

Find UUIDs:

```bash
nvidia-smi --query-gpu=index,uuid,name,memory.total --format=csv
```

Why UUID matters:

- `CUDA_VISIBLE_DEVICES=0` is process-local.
- Physical GPU ordering can change after driver changes, BIOS changes, MIG changes, or container runtime changes.
- UUIDs give operators a stable mapping from worker to physical device.

The supervisor should:

1. Read the config.
2. Validate each configured GPU exists.
3. Refuse duplicate GPU assignments unless explicitly allowed.
4. Resolve `gpu_uuid` to the correct CUDA visible device.
5. Start each worker with exactly one visible GPU.
6. Write the resolved runtime registry.

Generated registry example:

```json
{
  "schema_version": "tryops.fashn_worker_registry.v1",
  "router": {
    "bind": "127.0.0.1:18100"
  },
  "workers": [
    {
      "worker_id": "fashn-gpu0",
      "gpu_id": "0",
      "gpu_uuid": "GPU-...",
      "pid": 12345,
      "endpoint": "unix://artifacts/runtime/fashn-workers/fashn-gpu0.sock",
      "ready": true,
      "model_loaded": true,
      "max_concurrency": 1
    }
  ]
}
```

The registry is for router and operator debugging only. It is not an API contract.

### Worker Process Environment

Each worker should be launched with an isolated environment:

```env
CUDA_VISIBLE_DEVICES=<resolved-gpu>
TRYOPS_FASHN_WORKER_ID=fashn-gpu0
TRYOPS_FASHN_GPU_ID=0
TRYOPS_FASHN_GPU_UUID=GPU-...
TRYOPS_FASHN_REQUIRE_CUDA=1
TRYOPS_FASHN_ALLOW_CPU_FALLBACK=0
TRYOPS_FASHN_MIN_AVAILABLE_MB=4096
TRYOPS_FASHN_STRUCTURED_LOG_PATH=artifacts/logs/fashn_vton_worker_fashn-gpu0_events.jsonl
FASHN_VTON_GPU_FIRST_LOAD=1
CUDA_MODULE_LOADING=LAZY
PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
```

The worker command should be generated by the supervisor, not manually typed by operators.

### Config Validation Rules

The supervisor must fail before starting workers if:

- `TRYOPS_FASHN_REQUIRE_CUDA=1` and no NVIDIA GPU is visible.
- Any enabled worker has no valid `gpu_id` or `gpu_uuid`.
- Two enabled workers use the same physical GPU and sharing is not explicitly enabled.
- The FASHN weights file is missing.
- The FASHN Python environment is missing.
- A socket path or PID path collides with another worker.
- `allow_cpu_fallback` is true while production mode is enabled.
- `max_concurrency` is greater than `1` unless the worker has been tested for concurrent inference.

### Recommended Defaults

Use conservative defaults:

| Setting | Default | Reason |
| --- | --- | --- |
| `max_concurrency` | `1` | FASHN inference is GPU-memory-heavy. |
| `preload` | `true` | Readiness should prove the real model loads before accepting jobs. |
| `require_cuda` | `true` | Production must not silently run CPU fallback. |
| `allow_cpu_fallback` | `false` | Avoid fallback-as-product. |
| `routing_policy` | `least_inflight` | Long jobs need queue-aware routing. |
| `worker_transport` | `unix` | Avoid public worker ports. |
| `request_timeout_seconds` | `240` | Bound stuck requests. |
| `startup_timeout_seconds` | `300` | Model load can be slow but should not hang forever. |

## Implementation Readiness

This plan is good to implement now if the first implementation stays narrow:

1. Add worker `/ready` and `/metrics` to the existing single-worker service.
2. Add config parsing and validation.
3. Add the router/supervisor with private workers.
4. Point `TRYOPS_REAL_VTON_URL` to the router.
5. Add Grafana panels after metrics are real.

Do not start by adding many host ports or a public worker pool. That would make the shared datacenter problem worse.

## Target Local Architecture

For the current workstation-style deployment, keep one router endpoint on the host because the FASHN workers also run on the host. Workers should be private implementation details behind that router.

```text
API container
  -> http://host.docker.internal:18100
  -> host FASHN router/supervisor
      -> private worker GPU 0
      -> private worker GPU 1
      -> private worker GPU 2
```

The supervisor pins each worker with `CUDA_VISIBLE_DEVICES`. Operators should start the logical service, not hand-maintain worker ports:

```bash
TRYOPS_FASHN_GPU_IDS=0,1,2 make fashn-vton-router-bg
```

The API should point to the router:

```env
TRYOPS_REAL_VTON_URL=http://host.docker.internal:18100
```

### Host Worker, Private Endpoint

In the current local design, FASHN workers still run on the host because they need direct access to the NVIDIA driver, CUDA runtime, and the existing FASHN virtual environment.

That does not mean every worker gets a public host port.

```text
host process with GPU access:
  CUDA_VISIBLE_DEVICES=0 -> worker gpu0 -> private socket
  CUDA_VISIBLE_DEVICES=1 -> worker gpu1 -> private socket
  CUDA_VISIBLE_DEVICES=2 -> worker gpu2 -> private socket

single stable host endpoint:
  127.0.0.1:18100 -> FASHN router/supervisor
```

Docker sees only the router:

```text
API container -> http://host.docker.internal:18100
```

The worker sockets or private loopback endpoints are owned by the router/supervisor. They are not part of the public port contract and should not appear in frontend config, API config, Prometheus scrape config, or shared-host user documentation.

## Target Production Architecture

For production beyond one workstation, move routing onto the internal serving network.

```text
Gateway
  -> API / job queue
  -> internal FASHN router
      -> fashn-vton-worker-gpu-0
      -> fashn-vton-worker-gpu-1
      -> fashn-vton-worker-gpu-2
```

Production endpoint:

```env
TRYOPS_REAL_VTON_URL=http://fashn-vton-router:18100
```

For Kubernetes or similar orchestration:

- One worker pod per GPU, or one pod per MIG slice if MIG is used.
- Use GPU resource requests and limits.
- Use service DNS instead of `host.docker.internal`.
- Use readiness gates that prove the model is loaded on CUDA.
- Use DCGM exporter on GPU nodes.
- Use Prometheus service discovery for router and workers.

## Router Requirements

A plain round-robin load balancer is not enough for long-running VTON jobs. The router must be queue-aware.

Worker selection should consider:

- `/ready` status.
- real model loaded.
- CUDA available.
- in-flight jobs.
- configured max concurrency.
- recent failure count.
- available GPU memory if exposed by worker metrics.
- worker cooldown after OOM, CUDA, or driver errors.

Minimum routing policy:

```text
eligible workers = ready workers with in_flight < max_concurrency
choose worker with lowest in_flight
tie-break by oldest successful completion or lowest recent latency
if no eligible workers, return 503 and do not create fake output
```

Later routing policy:

```text
score = in_flight_weight
      + gpu_vram_pressure_weight
      + recent_failure_weight
      + latency_weight

choose lowest score
```

## Worker Requirements

Each FASHN worker must expose:

- `GET /health`: process alive, config visible.
- `GET /ready`: CUDA runtime usable, model loaded, worker accepting jobs.
- `GET /metrics`: Prometheus metrics.
- `POST /v1/vton/infer`: real model inference only.

Those endpoints do not need public host ports. They can be served over Unix sockets or loopback-only ports that only the router/supervisor knows.

Fail-closed rules:

- If CUDA is unavailable, worker is not ready.
- If the model cannot load, worker is not ready.
- If CPU fallback is attempted, worker fails startup unless explicitly allowed for non-production testing.
- If GPU memory is below configured threshold, worker returns 503.
- If worker crashes during a job, the API job must become failed or retryable, not permanently running.

## Metrics

### Worker Metrics

Each worker should expose:

```text
tryops_fashn_worker_ready{worker_id,gpu_id} 1
tryops_fashn_worker_inflight{worker_id,gpu_id}
tryops_fashn_worker_requests_total{worker_id,gpu_id,status}
tryops_fashn_worker_latency_ms_bucket{worker_id,gpu_id}
tryops_fashn_worker_model_loaded{worker_id,gpu_id}
tryops_fashn_worker_errors_total{worker_id,gpu_id,error_code}
tryops_fashn_worker_cuda_available{worker_id,gpu_id}
tryops_fashn_worker_gpu_memory_allocated_bytes{worker_id,gpu_id}
tryops_fashn_worker_gpu_memory_reserved_bytes{worker_id,gpu_id}
```

### Router Metrics

The router should expose:

```text
tryops_fashn_router_requests_total{status}
tryops_fashn_router_selected_worker_total{worker_id,gpu_id}
tryops_fashn_router_rejections_total{reason}
tryops_fashn_router_worker_ready{worker_id,gpu_id}
tryops_fashn_router_worker_inflight{worker_id,gpu_id}
tryops_fashn_router_worker_recent_failures{worker_id,gpu_id}
```

### Hardware Metrics

Prometheus should scrape:

| Exporter | Port | Purpose |
| --- | --- | --- |
| NVIDIA DCGM exporter | `9400` | GPU utilization, VRAM, power, temperature, XID errors. |
| node exporter | `9100` | Host CPU, RAM, disk, network. |
| process exporter | `9256` | Per-process CPU/RSS for FASHN and vLLM. |
| cAdvisor | custom non-conflicting port | Container resource usage. |

Key GPU queries:

```promql
DCGM_FI_DEV_GPU_UTIL
DCGM_FI_DEV_FB_USED
DCGM_FI_DEV_FB_FREE
DCGM_FI_DEV_POWER_USAGE
DCGM_FI_DEV_GPU_TEMP
DCGM_FI_DEV_XID_ERRORS
```

For the local Compose stack, prefer exporter containers on the Compose network instead of publishing more host ports:

```text
prometheus
  -> fashn-router metrics through host.docker.internal:18100
  -> dcgm-exporter:9400
  -> node-exporter:9100
  -> process-exporter:9256
```

Only the router needs a stable host-facing port in the local host-worker design. Hardware exporters should be service names inside the observability profile whenever possible.

## Grafana Dashboard Plan

Create a new dashboard:

```text
TryOps Inference Hardware
```

First row:

- Ready workers.
- Active VTON jobs.
- GPU utilization max.
- GPU VRAM pressure max.
- FASHN error rate.
- Queue age p95.

Second row:

- GPU utilization by device.
- GPU memory used by device.
- GPU temperature and power.
- XID errors.

Third row:

- Worker in-flight jobs.
- Worker latency p50/p95.
- Worker request status.
- Router selected worker distribution.

Fourth row:

- Host CPU/RAM.
- FASHN process RSS.
- Docker container CPU/RAM.
- Disk pressure for `artifacts/`.

Log panels:

- FASHN worker logs by `worker_id`.
- Router decision logs.
- Failed jobs by `job_id`.
- CUDA/OOM/XID-related errors.

## Ports And Service Names

Recommended local public/stable surface:

| Component | Port | Scope |
| --- | --- | --- |
| FASHN router | `18100` | Local host. API container calls through `host.docker.internal:18100`. |
| FASHN router | `fashn-vton-router:18100` | Production/internal network. |

Private implementation details:

| Component | Preferred transport | Scope |
| --- | --- | --- |
| FASHN worker GPU 0..N | Unix socket under `artifacts/runtime/fashn-workers/` | Private to router/supervisor. |
| FASHN worker fallback transport | Ephemeral or loopback-only TCP | Private to router/supervisor. |
| DCGM exporter | `dcgm-exporter:9400` | Compose/Kubernetes observability network. |
| node exporter | `node-exporter:9100` | Compose/Kubernetes observability network. |
| process exporter | `process-exporter:9256` | Compose/Kubernetes observability network. |

Avoid making worker ports part of the public contract. If a worker must use TCP during early implementation, allocate it from a configured base range inside the router and write it to a runtime registry file, for example:

```json
{
  "workers": [
    {"worker_id": "gpu0", "gpu_id": "0", "endpoint": "http://127.0.0.1:43101"},
    {"worker_id": "gpu1", "gpu_id": "1", "endpoint": "http://127.0.0.1:43102"}
  ]
}
```

That registry file is consumed by the router only. It should not be referenced by the API, frontend, Prometheus scrape config, or user documentation.

## Implementation Phases

### Phase 1: Document and Expose Current Boundary

Status: implemented for the local stack.

- Update `PORT.md` to show that FASHN is host-side.
- Document why container-only monitoring is incomplete.
- Document local manual checks with `ps`, `nvidia-smi`, and `nvidia-smi pmon`.

Acceptance:

- Operators understand that the router `18100` and its workers are host-side.
- Operators understand that the multi-GPU target replaces public worker ports with one router endpoint.
- Operators know that Docker stats do not cover real FASHN GPU process usage.

### Phase 2: Add Worker Readiness and Metrics

Add to `scripts/serve_fashn_vton.py`:

- `/ready`
- `/metrics`
- worker id env, for example `TRYOPS_FASHN_WORKER_ID`
- GPU id env, for example `TRYOPS_FASHN_GPU_ID`
- real CUDA/model readiness status
- in-flight counter
- request counters
- latency histogram or summary
- error counters

Acceptance:

- In direct single-worker development mode, `/ready` fails until CUDA and model are ready.
- In routed mode, `GET /ready` on the router reports readiness only when at least one real worker is ready.
- Router `/metrics` exposes per-worker metrics with `worker_id`, `gpu_id`, and `gpu_uuid` labels.
- Worker never reports ready when it is on CPU fallback.

### Phase 3: Add Multi-Worker Supervisor

Add Make targets:

```text
make fashn-vton-router-bg
make fashn-vton-router-stop
make fashn-vton-workers-status
```

The supervisor should create private worker processes from `TRYOPS_FASHN_GPU_IDS`. Each worker should have separate:

- PID file
- raw log
- structured log
- worker id
- GPU id
- private socket or private loopback endpoint

Example artifact layout:

```text
artifacts/runtime/fashn-vton-router.pid
artifacts/runtime/fashn-vton-workers.json
artifacts/runtime/fashn-vton-worker-gpu0.pid
artifacts/runtime/fashn-vton-worker-gpu1.pid
artifacts/runtime/fashn-workers/gpu0.sock
artifacts/runtime/fashn-workers/gpu1.sock
artifacts/logs/fashn-vton-worker-gpu0.log
artifacts/logs/fashn-vton-worker-gpu1.log
artifacts/logs/fashn_vton_worker_gpu0_events.jsonl
artifacts/logs/fashn_vton_worker_gpu1_events.jsonl
```

Acceptance:

- Multiple workers can run at the same time.
- Each worker uses only its assigned GPU.
- API still sees only `TRYOPS_REAL_VTON_URL`.
- Prometheus can get per-worker metrics from router `/metrics`.
- Stopping one worker does not stop other workers or unrelated user training jobs.

### Phase 4: Add FASHN Router

Implement a small internal router service:

- `GET /health`
- `GET /ready`
- `GET /metrics`
- `POST /v1/vton/infer`

Router config:

```env
TRYOPS_FASHN_ROUTER_PORT=18100
TRYOPS_FASHN_GPU_IDS=0,1,2
TRYOPS_FASHN_WORKER_TRANSPORT=unix
TRYOPS_FASHN_WORKER_SOCKET_DIR=artifacts/runtime/fashn-workers
TRYOPS_REAL_VTON_URL=http://host.docker.internal:18100
```

Acceptance:

- API calls only the router.
- Router sends jobs only to ready workers.
- Router returns 503 if no real worker is available.
- Router `/metrics` exports router and per-worker metrics.
- Router emits structured routing decisions with `job_id`, `request_id`, `worker_id`, and `gpu_id`.

### Phase 5: Add Hardware Exporters

Add observability services or host instructions for:

- DCGM exporter.
- node exporter.
- process exporter.

Prometheus scrape jobs should use service names, plus only the single host router endpoint for the local host-worker mode:

```yaml
- job_name: tryops-fashn-router
  static_configs:
    - targets: ["host.docker.internal:18100"]

- job_name: tryops-dcgm
  static_configs:
    - targets: ["dcgm-exporter:9400"]

- job_name: tryops-node
  static_configs:
    - targets: ["node-exporter:9100"]

- job_name: tryops-process
  static_configs:
    - targets: ["process-exporter:9256"]
```

Acceptance:

- Grafana shows GPU utilization, VRAM, temperature, and power.
- Grafana shows host CPU/RAM/disk.
- Grafana shows FASHN process RSS/CPU.

### Phase 6: Add Grafana Hardware Dashboard

Create:

```text
infra/grafana/dashboards/tryops-inference-hardware.json
```

Update dashboard validator and tests so this dashboard is required.

Acceptance:

- Dashboard validation passes.
- Dashboard has Prometheus datasource UID `prometheus`.
- Dashboard includes worker, router, GPU, host, and process panels.

### Phase 7: Production Serving Migration

Replace host-loopback serving with internal service DNS when ready:

```env
TRYOPS_REAL_VTON_URL=http://fashn-vton-router:18100
```

Possible backends:

- GPU-enabled Docker Compose service on a dedicated inference host.
- Kubernetes deployment with one worker pod per GPU.
- Triton Inference Server if the model can be packaged into a compatible backend.
- KServe if the platform already uses Kubernetes model serving.
- Ray Serve if dynamic Python model routing is needed.

Acceptance:

- No production dependency on `host.docker.internal`.
- Workers are supervised by the platform.
- Readiness and metrics are scrapeable by service discovery.
- Deployment can roll workers without losing job state.

## Alerting Plan

Add alerts for:

- No ready FASHN workers.
- GPU VRAM above 90 percent for 5 minutes.
- GPU utilization above 95 percent with growing queue.
- Any XID error.
- Worker error rate above threshold.
- Job queue age p95 above threshold.
- Job stuck in running longer than timeout.
- Router 503 rate above threshold.
- FASHN process RSS growth across completed jobs.

## Operational Runbook

When jobs fail or stall:

1. Check the job in the UI for `job_id` and `request_id`.
2. Search Grafana Loki for the `job_id`.
3. Check router decision logs for selected worker and GPU.
4. Check worker logs for CUDA/model errors.
5. Check GPU dashboard for VRAM, XID, temperature, and power.
6. Check process dashboard for FASHN RSS growth.
7. If one worker is bad, drain or stop only that worker.
8. Do not restart the GPU, Docker daemon, or unrelated training processes unless explicitly approved.

## Acceptance Criteria

The multi-GPU serving design is production-ready only when all criteria are true:

- API points to a router, not a single worker.
- Every worker is pinned to exactly one GPU.
- Router refuses jobs when no real model worker is ready.
- Worker readiness proves CUDA and model load success.
- CPU fallback is disabled by default.
- Per-worker logs include `job_id`, `request_id`, `worker_id`, and `gpu_id`.
- Grafana shows GPU, host, process, router, worker, queue, and job lifecycle telemetry.
- Prometheus alerts cover no-ready-worker, queue age, GPU errors, worker failures, and stale jobs.
- Restarting one worker does not stop unrelated workers or other users' training processes.
- No mock, fallback, deterministic baseline, or placeholder output is reachable from the production route.
