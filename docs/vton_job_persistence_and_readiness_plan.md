# VTON Job Persistence And Readiness Plan

## Context

After submitting two images in the Try-On Studio, the UI showed a VTON job. After a browser refresh, the visible job row disappeared. Investigation shows this is not only a frontend display issue. The backend did persist the job, but the UI currently reloads only active jobs and filters completed/failed jobs away. The observed job also remained stuck in `running`, which points to a runtime readiness issue in the real FASHN VTON service.

## Evidence

- Browser/API logs show `POST /v1/vton/jobs` was called.
- Browser/API logs show repeated polling of `GET /v1/vton/jobs/job-eb4884a5-e628-458c-bb0e-edab2a6a4c8c`.
- Postgres table `jobs` contains the job row:
  - `id`: `job-eb4884a5-e628-458c-bb0e-edab2a6a4c8c`
  - `kind`: `vton`
  - `account_id`: `acct_8d55bae69d4a391e`
  - `status`: `running`
- Postgres table `requests` had no completed VTON request row for that job.
- FASHN service log shows CUDA/model readiness problems:
  - `Using device: cuda`
  - NVIDIA driver is too old.
  - GPU-first model load failed and entered a fallback loader path.
- UI code currently fetches account jobs with `status=active`.
- UI code filters visible jobs to `accepted`, `queued`, and `running`.

## Findings

| Bug | Evidence | Fix | Expected |
|---|---|---|---|
| Job row disappears after browser refresh | `web/src/App.tsx` fetches `accountJobs("active", 20)`, and local cache stores only active jobs. | Fetch recent jobs with `status=all` or `queued,running,completed,failed`; keep recent jobs in local storage. | After F5, recent jobs are still visible. |
| Completed/failed jobs are filtered away in VTON Studio | `VtonStudio` builds `visibleJobs` using `.filter(isActiveVtonJob)`. | Show recent job activity, but compute active slot count separately. | Completed and failed jobs remain visible with their final status. |
| Account page hides job history | `AccountDashboardView` also filters job list to active statuses. | Show recent persisted jobs on the account page. | Workspace job history remains visible after reload. |
| Job can remain stuck as `running` | DB row is persisted as `running`, but no result row exists and FASHN logs show model load trouble. | Add stale-job recovery: mark jobs older than timeout/grace as failed with a clear `stale_running_job` error. | No permanent running jobs after worker failure, API restart, or blocked model load. |
| FASHN accepts work before real model readiness is proven | `/health` reports `loaded: false`; first request triggers CUDA/model load and can block. | Add readiness/preload gate before accepting jobs. Require model load success when real VTON is configured. | Bad CUDA/driver/model setup fails before creating long-running user jobs. |
| GPU failure can enter a weaker loader path | FASHN log says GPU-first load failed and then uses fallback loader. | Add `TRYOPS_FASHN_ALLOW_CPU=0` default and fail closed when CUDA is required. | No silent CPU or alternate implementation is presented as production VTON. |

## Implementation Plan

1. Patch frontend job loading.
   - Change `accountJobs("active", 20)` to request recent jobs, not only active jobs.
   - Preserve recent completed/failed/running jobs in `localStorage`.
   - Keep active job count calculation separate from visible job history.

2. Patch VTON Studio job display.
   - Remove active-only filtering from the visible job feed.
   - Keep `isActiveVtonJob` only for slot counting and polling decisions.
   - Update empty text from "No active try-on jobs" to "No recent try-on jobs."

3. Patch account dashboard job display.
   - Show recent persisted jobs instead of active-only jobs.
   - Keep slot/concurrency metrics based only on active statuses.

4. Patch backend stale job recovery.
   - Add a stale running job detector for persisted jobs.
   - When a job exceeds its timeout plus grace period, return and persist `failed`.
   - Error code should be explicit, for example `stale_running_job`.

5. Patch FASHN service readiness.
   - Add a load/preflight endpoint or startup preload path.
   - If CUDA is required and unavailable, fail before accepting VTON inference.
   - Report clear readiness fields: `loaded`, `cuda_available`, `driver_compatible`, `ready_for_inference`.

6. Add tests.
   - UI/type-level behavior: job list keeps completed/failed jobs in recent activity.
   - API behavior: `status=all` returns persisted completed/failed/running jobs.
   - Backend behavior: stale running jobs become failed.
   - FASHN readiness behavior: CUDA-required mode rejects CPU/driver fallback.

7. Verify.
   - Run Python focused tests for jobs/API.
   - Run `web` typecheck.
   - Submit a real VTON job, refresh the browser, and confirm the job remains visible.
   - Confirm a bad CUDA/model setup fails fast with an explicit error instead of a hidden running job.

## Expected End State

- A job shown in the UI is backed by a persisted backend row.
- Refreshing the browser does not erase recent job activity.
- Completed jobs stay visible and provide an output link.
- Failed jobs stay visible and show the real error.
- A real model readiness failure cannot look like an indefinitely running user job.
- No deterministic, CPU, mock, or fallback path is silently presented as production VTON.
