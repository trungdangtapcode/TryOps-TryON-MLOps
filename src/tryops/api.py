from __future__ import annotations

import base64
import binascii
import json
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from tryops.api_contracts import (
    MAX_IMAGE_BYTES,
    attach_response_metadata,
    readiness_state,
    request_id_from_payload,
    structured_error,
    validate_llm_payload,
    validate_vton_payload,
)
from tryops.artifacts import (
    artifact_url,
    artifact_media_type,
    load_json_artifact,
    resolve_artifact_path,
    with_artifact_urls,
)
from tryops.auth import authenticate_api_key, authorize_admin_payload, build_rbac_session
from tryops.contracts import ModelCandidate
from tryops.evaluation_artifacts import load_evaluation_index
from tryops.experiments import (
    DEFAULT_EXPERIMENT_ID,
    normalize_experiment_analysis_variants,
    normalize_experiment_variants,
    normalize_guardrail_thresholds,
    normalize_holdback,
)
from tryops.guardrails import evaluate_egress_guardrails, evaluate_ingress_guardrails, merge_guardrail_verdicts
from tryops.jobs import VTON_JOB_QUEUE, render_job_metrics
from tryops.lineage import build_lineage_record
from tryops.native_experiment_stats import analyze_with_native_experiment_stats
from tryops.observability import record_api_observation, render_prometheus_metrics, sanitize_payload_metadata
from tryops.pipelines.llm_baseline import estimate_tokens, generate_baseline_response
from tryops.pipelines.vton_baseline import run_naive_overlay_baseline
from tryops.pipelines.vton_remote import RealVtonUnavailableError, run_remote_fashn_vton
from tryops.policy import evaluate_promotion
from tryops.quota import check_and_record_quota
from tryops.quota_read_model import load_quota_read_model
from tryops.routing import build_experiment_routing_decision, build_routing_decision
from tryops.semantic_cache import GLOBAL_SEMANTIC_CACHE, build_cache_metadata
from tryops.simple_image import PNG_SIGNATURE, read_png_rgb, write_png_rgb
from tryops.timeouts import RequestTimeoutError, run_with_timeout, timeout_details
from tryops.vton_native_bridge import build_native_vton_execution_evidence

try:
    from fastapi import FastAPI, Response
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import FileResponse
except ImportError:  # pragma: no cover - optional runtime dependency
    FastAPI = None  # type: ignore[assignment]
    CORSMiddleware = None  # type: ignore[assignment]
    Response = None  # type: ignore[assignment]
    FileResponse = None  # type: ignore[assignment]


def create_app() -> Any:
    if FastAPI is None:
        raise RuntimeError("FastAPI is not installed. Install the project api dependencies first.")

    app = FastAPI(
        title="TryOps Console API",
        version="0.1.0",
        description="Enterprise MLOps control plane for VTON and optimized LLM serving.",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_methods=["*"],
        allow_headers=["*"],
        allow_credentials=False,
    )

    @app.get("/api/health")
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/health")
    def health_v1() -> dict[str, str]:
        return health()

    
    from fastapi import Request
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.responses import JSONResponse

    class PayloadSizeLimitMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > 10 * 1024 * 1024:
                return JSONResponse(
                    status_code=413,
                    content=structured_error(
                        request_id="unknown",
                        code="payload_too_large",
                        message="request payload exceeded 10MB limit",
                        workload="api"
                    )
                )
            return await call_next(request)

    app.add_middleware(PayloadSizeLimitMiddleware)

    
    @app.get("/api/lineage/{id}")
    def get_lineage(id: str, api_key: str = None) -> dict[str, Any]:
        auth = authenticate_api_key(api_key, required_scope="lineage:read")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "lineage")
        return {"status": "ok", "data": {"id": id, "hashes": {}}}

    @app.get("/api/auth/session")
    @app.get("/v1/auth/session")
    def get_auth_session(api_key: str = None) -> dict[str, Any]:
        auth = authenticate_api_key(api_key, required_scope="session:read")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "session")
        return {"status": "ok", "data": build_rbac_session(auth["principal"])}

    def health_v1() -> dict[str, str]:
        return health()

    @app.get("/api/ready")
    @app.get("/ready")
    @app.get("/v1/ready")
    def ready() -> dict[str, Any]:
        return readiness_state()

    @app.get("/api/metrics")
    @app.get("/metrics")
    @app.get("/v1/metrics")
    def metrics() -> Any:
        body = render_prometheus_metrics() + render_job_metrics()
        if Response is None:
            return body
        return Response(body, media_type="text/plain; version=0.0.4")

    @app.post("/api/promotion/evaluate")
    @app.post("/promotion/evaluate")
    @app.post("/v1/promotion/evaluate")
    def promotion_evaluate(payload: dict[str, Any]) -> dict[str, Any]:
        request_id = request_id_from_payload(payload)
        auth = authorize_admin_payload(payload, required_scope="promotion:evaluate")
        if not auth["allowed"]:
            return _admin_auth_error(request_id, auth, "promotion")
        try:
            candidate = ModelCandidate.from_dict(payload["candidate"])
            decision = evaluate_promotion(candidate, target_stage=payload.get("target_stage", "staging"))
            response = decision.to_dict()
            response["request_id"] = request_id
            response["auth"] = auth
            return response
        except (KeyError, TypeError, ValueError) as exc:
            return structured_error(
                request_id=request_id,
                code="invalid_promotion_request",
                message=str(exc),
                workload="promotion",
            )

    @app.post("/api/lineage")
    @app.post("/lineage")
    @app.post("/v1/lineage")
    def lineage(payload: dict[str, Any]) -> dict[str, Any]:
        request_id = request_id_from_payload(payload)
        auth = authorize_admin_payload(payload, required_scope="lineage:create")
        if not auth["allowed"]:
            return _admin_auth_error(request_id, auth, "lineage")
        try:
            candidate = ModelCandidate.from_dict(payload["candidate"])
            record = build_lineage_record(
                candidate,
                request_id=request_id,
                output_uri=str(payload["output_uri"]),
            )
            record["auth"] = auth
            return record
        except (KeyError, TypeError, ValueError) as exc:
            return structured_error(
                request_id=request_id,
                code="invalid_lineage_request",
                message=str(exc),
                workload="lineage",
            )

    @app.post("/api/vton/upload")
    @app.post("/vton/upload")
    @app.post("/v1/vton/upload")
    def vton_upload(payload: dict[str, Any]) -> dict[str, Any]:
        request_id = request_id_from_payload(payload)
        auth = authorize_admin_payload(payload, required_scope="admin:read")
        if not auth["allowed"]:
            return _admin_auth_error(request_id, auth, "vton_upload")
        try:
            upload = _store_vton_upload(payload)
        except ValueError as exc:
            return structured_error(
                request_id=request_id,
                code="invalid_vton_upload",
                message=str(exc),
                workload="vton",
            )
        return {
            "api_version": "v1",
            "request_id": request_id,
            "status": "uploaded",
            "workload": "vton",
            "data": upload,
            "auth": auth,
        }

    @app.post("/api/vton/infer")
    @app.post("/vton/infer")
    @app.post("/v1/vton/infer")
    def vton_infer(payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "/v1/vton/infer"
        started = perf_counter()
        request_id = request_id_from_payload(payload)
        clean, errors = validate_vton_payload(payload)
        if errors:
            response = structured_error(
                request_id=request_id,
                code="invalid_vton_request",
                message="VTON request validation failed",
                details=errors,
                workload="vton",
            )
            _record(endpoint, request_id, "vton", clean["model_alias"], started, payload, response)
            return response
        routing = build_routing_decision(
            workload="vton",
            request_id=request_id,
            requested_alias=clean["model_alias"],
            routing_mode=clean["routing_mode"],
            canary_percent=clean["canary_percent"],
        )
        quota = check_and_record_quota(
            user_id=clean["user_id"],
            plan=clean["quota_plan"],
            workload="vton",
            request_units=1,
            record=False,
        )
        if not quota["allowed"]:
            response = structured_error(
                request_id=request_id,
                code="quota_exceeded",
                message="VTON quota exceeded",
                details=quota["checks"],
                workload="vton",
            )
            response["quota"] = quota
            _record(endpoint, request_id, "vton", routing["primary_alias"], started, payload, response)
            return response
        adapter = str(payload.get("adapter", routing["primary_adapter"]))
        if adapter != routing["primary_adapter"]:
            response = structured_error(
                request_id=request_id,
                code="unsupported_vton_adapter",
                message=f"unsupported VTON adapter '{adapter}'",
                details=[{"field": "adapter", "message": "use a supported model_alias instead"}],
                workload="vton",
            )
            _record(endpoint, request_id, "vton", routing["primary_alias"], started, payload, response)
            return response
        try:
            report = run_with_timeout(
                lambda: _run_vton_adapter(
                    adapter=adapter,
                    clean=clean,
                ),
                timeout_ms=clean["timeout_ms"],
                operation_name="vton-infer",
            )
            native_vton = build_native_vton_execution_evidence(
                report=report,
                person_image_path=clean["person_image_path"],
            )
            report["native_execution"] = native_vton
            if native_vton["quality_score"] is not None:
                report["metrics"]["native_quality_score"] = native_vton["quality_score"]
            report["metrics"]["native_image_quality"] = native_vton["image_metrics"]
            _write_vton_report_sidecar(report)
            quota = check_and_record_quota(
                user_id=clean["user_id"],
                plan=clean["quota_plan"],
                workload="vton",
                request_units=1,
            )
            response = {
                "status": "completed",
                "adapter": adapter,
                "routing": routing,
                "quota": quota,
                "native_vton": native_vton,
                "report": report,
            }
            attach_response_metadata(
                response,
                request_id=request_id,
                workload="vton",
                model_alias=routing["primary_alias"],
            )
            _record(endpoint, request_id, "vton", routing["primary_alias"], started, payload, response)
            return response
        except RequestTimeoutError as exc:
            response = structured_error(
                request_id=request_id,
                code="timeout_exceeded",
                message="VTON inference timed out",
                details=timeout_details(exc),
                workload="vton",
            )
            response["routing"] = routing
            response["quota"] = quota
            _record(endpoint, request_id, "vton", routing["primary_alias"], started, payload, response)
            return response
        except RealVtonUnavailableError as exc:
            response = structured_error(
                request_id=request_id,
                code="real_vton_unavailable",
                message=str(exc),
                details=[{"field": "model_alias", "message": "use baseline only for diagnostics"}],
                workload="vton",
            )
            response["routing"] = routing
            response["quota"] = quota
            _record(endpoint, request_id, "vton", routing["primary_alias"], started, payload, response)
            return response
        except (OSError, ValueError) as exc:
            response = structured_error(
                request_id=request_id,
                code="vton_inference_failed",
                message=str(exc),
                workload="vton",
            )
            _record(endpoint, request_id, "vton", routing["primary_alias"], started, payload, response)
            return response

    @app.post("/api/vton/jobs")
    @app.post("/vton/jobs")
    @app.post("/v1/vton/jobs")
    def vton_job_submit(payload: dict[str, Any]) -> dict[str, Any]:
        request_id = request_id_from_payload(payload)
        clean, errors = validate_vton_payload(payload)
        if errors:
            return structured_error(
                request_id=request_id,
                code="invalid_vton_job_request",
                message="VTON job request validation failed",
                details=errors,
                workload="vton",
            )
        return VTON_JOB_QUEUE.submit(
            workload="vton",
            request_id=request_id,
            payload={**payload, "request_id": request_id},
            runner=vton_infer,
            payload_metadata=sanitize_payload_metadata(workload="vton", payload=clean),
        )

    @app.get("/api/vton/jobs/{job_id}")
    @app.get("/vton/jobs/{job_id}")
    @app.get("/v1/vton/jobs/{job_id}")
    def vton_job_status(job_id: str) -> dict[str, Any]:
        snapshot = VTON_JOB_QUEUE.get(job_id)
        if snapshot is None:
            return structured_error(
                request_id="unknown",
                code="job_not_found",
                message=f"VTON job '{job_id}' was not found",
                workload="vton",
            )
        return snapshot

    @app.post("/api/llm/generate")
    @app.post("/llm/generate")
    @app.post("/v1/llm/generate")
    def llm_generate(payload: dict[str, Any]) -> dict[str, Any]:
        endpoint = "/v1/llm/generate"
        started = perf_counter()
        request_id = request_id_from_payload(payload)
        clean, errors = validate_llm_payload(payload)
        if errors:
            response = structured_error(
                request_id=request_id,
                code="invalid_llm_request",
                message="LLM request validation failed",
                details=errors,
                workload="llm",
            )
            _record(endpoint, request_id, "llm", clean["model_alias"], started, payload, response)
            return response
        ingress_guardrails = evaluate_ingress_guardrails(
            prompt=clean["prompt"],
            max_tokens=clean["max_tokens"],
            structured=clean["structured"],
        )
        if ingress_guardrails["verdict"]["blocked"]:
            response = structured_error(
                request_id=request_id,
                code="guardrail_blocked",
                message="LLM request blocked by runtime guardrail",
                details=ingress_guardrails["verdict"]["findings"],
                workload="llm",
            )
            response["guardrails"] = ingress_guardrails["verdict"]
            _record(endpoint, request_id, "llm", clean["model_alias"], started, payload, response)
            return response
        try:
            if clean["routing_mode"] in {"experiment_ab", "experiment_bandit"}:
                routing = build_experiment_routing_decision(
                    workload="llm",
                    request_id=request_id,
                    experiment_id=clean["experiment_id"],
                    variants=clean["experiment_variants"],
                    mode="ab" if clean["routing_mode"] == "experiment_ab" else "bandit",
                    holdback_percent=clean["experiment_holdback_percent"],
                    guardrail_thresholds=clean["experiment_guardrail_thresholds"],
                )
            else:
                routing = build_routing_decision(
                    workload="llm",
                    request_id=request_id,
                    requested_alias=clean["model_alias"],
                    routing_mode=clean["routing_mode"],
                    canary_percent=clean["canary_percent"],
                    shadow=clean["shadow"],
                    fallback_enabled=clean["fallback_enabled"],
                    route_health={
                        "baseline": "ready",
                        "champion": "ready" if clean["optimized_available"] else "unavailable",
                        "challenger": "ready" if clean["optimized_available"] else "unavailable",
                        "candidate": "ready" if clean["optimized_available"] else "unavailable",
                    },
                )
            quota = check_and_record_quota(
                user_id=clean["user_id"],
                plan=clean["quota_plan"],
                workload="llm",
                request_units=1,
                estimated_tokens=estimate_tokens(ingress_guardrails["prompt_for_generation"]) + clean["max_tokens"],
            )
            if not quota["allowed"]:
                response = structured_error(
                    request_id=request_id,
                    code="quota_exceeded",
                    message="LLM quota exceeded",
                    details=quota["checks"],
                    workload="llm",
                )
                response["quota"] = quota
                _record(endpoint, request_id, "llm", routing["primary_alias"], started, payload, response)
                return response
            generation_prompt = ingress_guardrails["prompt_for_generation"]
            cache_prompt = f"model={routing['primary_alias']} structured={clean['structured']} prompt={generation_prompt}"
            cache_allowed = clean["semantic_cache_enabled"] and not ingress_guardrails["redaction"].replacements
            cache_lookup: dict[str, Any] | None = None
            cached_generation: dict[str, Any] | None = None
            if cache_allowed:
                cache_lookup = GLOBAL_SEMANTIC_CACHE.lookup(
                    cache_prompt,
                    threshold=clean["semantic_cache_threshold"],
                )
                matched_entry_id = str(cache_lookup.get("lookup", {}).get("matched_entry_id", ""))
                cached_generation = GLOBAL_SEMANTIC_CACHE.get_generation(matched_entry_id) if matched_entry_id else None

            if cached_generation is not None:
                response = cached_generation
                response["semantic_cache"] = build_cache_metadata(
                    lookup=cache_lookup or {},
                    matched_generation=cached_generation,
                )
            else:
                response = run_with_timeout(
                    lambda: generate_baseline_response(
                        prompt=generation_prompt,
                        model_alias=routing["primary_alias"],
                        max_tokens=clean["max_tokens"],
                        structured=clean["structured"],
                    ),
                    timeout_ms=clean["timeout_ms"],
                    operation_name="llm-generate",
                )
                if cache_allowed and cache_lookup is not None:
                    response["semantic_cache"] = build_cache_metadata(lookup=cache_lookup)
            response["routing"] = routing
            response["quota"] = quota
            if cached_generation is None and "shadow_alias" in routing:
                shadow = run_with_timeout(
                    lambda: generate_baseline_response(
                        prompt=generation_prompt,
                        model_alias=str(routing["shadow_alias"]),
                        max_tokens=clean["max_tokens"],
                        structured=False,
                    ),
                    timeout_ms=clean["timeout_ms"],
                    operation_name="llm-shadow",
                )
                response["shadow_evaluation"] = {
                    "status": shadow["status"],
                    "model_alias": routing["shadow_alias"],
                    "adapter": routing["shadow_adapter"],
                    "metrics": shadow["metrics"],
                    "output_tokens": shadow["output"]["estimated_tokens"],
                    "safety": shadow["safety"],
                }
            egress_guardrails = evaluate_egress_guardrails(
                generation=response,
                redaction=ingress_guardrails["redaction"],
                structured=clean["structured"],
            )
            combined_guardrails = merge_guardrail_verdicts(
                ingress_guardrails["verdict"],
                egress_guardrails["verdict"],
            )
            if egress_guardrails["verdict"]["blocked"]:
                blocked = structured_error(
                    request_id=request_id,
                    code="guardrail_output_blocked",
                    message="LLM output blocked by runtime guardrail",
                    details=egress_guardrails["verdict"]["findings"],
                    workload="llm",
                )
                blocked["routing"] = routing
                blocked["quota"] = quota
                blocked["guardrails"] = combined_guardrails
                _record(endpoint, request_id, "llm", routing["primary_alias"], started, payload, blocked)
                return blocked
            response = egress_guardrails["generation"]
            if cached_generation is None and cache_allowed:
                GLOBAL_SEMANTIC_CACHE.put(prompt=cache_prompt, generation=response)
            response["guardrails"] = combined_guardrails
            attach_response_metadata(
                response,
                request_id=request_id,
                workload="llm",
                model_alias=routing["primary_alias"],
            )
            _record(endpoint, request_id, "llm", routing["primary_alias"], started, payload, response)
            return response
        except RequestTimeoutError as exc:
            response = structured_error(
                request_id=request_id,
                code="timeout_exceeded",
                message="LLM generation timed out",
                details=timeout_details(exc),
                workload="llm",
            )
            response["routing"] = routing
            response["quota"] = quota
            _record(endpoint, request_id, "llm", routing["primary_alias"], started, payload, response)
            return response
        except (KeyError, RuntimeError, TypeError, ValueError) as exc:
            response = structured_error(
                request_id=request_id,
                code="llm_generation_failed",
                message=str(exc),
                workload="llm",
            )
            _record(endpoint, request_id, "llm", clean["model_alias"], started, payload, response)
            return response

    @app.get("/api/experiments/summary")
    @app.get("/v1/experiments/summary")
    def get_experiment_summary(api_key: str = None) -> dict[str, Any]:
        auth = authenticate_api_key(api_key, required_scope="admin:read")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "experiments")
        routing_report = _optional_json_artifact("artifacts/eval/experiments/online_experiment_report.json")
        analysis_report = _optional_json_artifact("artifacts/eval/experiments/online_experiment_analysis_report.json")
        passed = bool(routing_report.get("passed")) and bool(analysis_report.get("passed"))
        native_ready = (
            routing_report.get("decisions", {})
            .get("bandit", {})
            .get("experiment", {})
            .get("source")
            == "native_cpp_cli"
        ) and (
            analysis_report.get("native_experiment_stats", {}).get("source") == "native_cpp_cli"
        )
        return {
            "status": "ok",
            "data": {
                "schema_version": "tryops.experiment_console.v1",
                "experiment_id": routing_report.get("decisions", {})
                .get("bandit", {})
                .get("experiment_id", DEFAULT_EXPERIMENT_ID),
                "production_ready": passed and native_ready,
                "routing_report": routing_report,
                "analysis_report": analysis_report,
            },
        }

    @app.post("/api/experiments/route")
    @app.post("/v1/experiments/route")
    def experiment_route(payload: dict[str, Any]) -> dict[str, Any]:
        request_id = request_id_from_payload(payload)
        auth = authorize_admin_payload(payload, required_scope="admin:read")
        if not auth["allowed"]:
            return _admin_auth_error(request_id, auth, "experiments")
        try:
            mode = str(payload.get("mode", "bandit"))
            if mode not in {"ab", "bandit"}:
                raise ValueError("mode must be 'ab' or 'bandit'")
            decision = build_experiment_routing_decision(
                workload=str(payload.get("workload", "llm")),
                request_id=request_id,
                experiment_id=str(payload.get("experiment_id", DEFAULT_EXPERIMENT_ID)),
                variants=normalize_experiment_variants(payload.get("variants")),
                mode=mode,
                holdback_percent=float(payload.get("holdback_percent", 5.0)),
                guardrail_thresholds=normalize_guardrail_thresholds(payload.get("guardrail_thresholds")),
            )
            return {"status": "ok", "request_id": request_id, "data": decision, "auth": auth}
        except (RuntimeError, TypeError, ValueError) as exc:
            return structured_error(
                request_id=request_id,
                code="experiment_route_failed",
                message=str(exc),
                workload="experiments",
            )

    @app.post("/api/experiments/analyze")
    @app.post("/v1/experiments/analyze")
    def experiment_analyze(payload: dict[str, Any]) -> dict[str, Any]:
        request_id = request_id_from_payload(payload)
        auth = authorize_admin_payload(payload, required_scope="admin:read")
        if not auth["allowed"]:
            return _admin_auth_error(request_id, auth, "experiments")
        try:
            stats = analyze_with_native_experiment_stats(
                holdback=normalize_holdback(payload.get("holdback")),
                variants=normalize_experiment_analysis_variants(payload.get("variants")),
                experiment_id=str(payload.get("experiment_id", DEFAULT_EXPERIMENT_ID)),
                confidence=float(payload.get("confidence", 0.95)),
                alpha=float(payload.get("alpha", 0.05)),
                beta=float(payload.get("beta", 0.20)),
                min_detectable_effect=float(payload.get("min_detectable_effect", 0.05)),
                min_sample_size=float(payload.get("min_sample_size", 100.0)),
            )
            return {"status": "ok", "request_id": request_id, "data": stats, "auth": auth}
        except (RuntimeError, TypeError, ValueError) as exc:
            return structured_error(
                request_id=request_id,
                code="experiment_analysis_failed",
                message=str(exc),
                workload="experiments",
            )

    @app.get("/api/history")
    def get_history(api_key: str = None, kind: str = None, limit: int = 50) -> dict[str, Any]:
        auth = authenticate_api_key(api_key, required_scope="admin:read")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "history")
        from tryops import db
        conn = db.connect()
        try:
            reqs = db.list_requests(conn, kind=kind, limit=limit)
            return {"status": "ok", "data": reqs}
        finally:
            conn.close()

    @app.get("/api/request/{id}")
    def get_single_request(id: str, api_key: str = None) -> dict[str, Any]:
        auth = authenticate_api_key(api_key, required_scope="admin:read")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "request")
        from tryops import db
        conn = db.connect()
        try:
            req = db.get_request(conn, id)
            if not req:
                return structured_error(
                    request_id="unknown",
                    code="request_not_found",
                    message="request not found",
                    workload="api"
                )
            return {"status": "ok", "data": req}
        finally:
            conn.close()

    @app.post("/api/feedback")
    def post_feedback(payload: dict[str, Any]) -> dict[str, Any]:
        from tryops import db
        conn = db.connect()
        try:
            fid = db.insert_feedback(conn, payload)
            # also insert audit entry
            db.insert_audit(
                conn, 
                actor=payload.get("user_id", "anonymous"), 
                action="submit_feedback", 
                target=payload.get("request_id", "unknown"),
                detail=fid
            )
            return {"status": "ok", "id": fid}
        finally:
            conn.close()

    @app.get("/api/dashboard")
    def get_dashboard(api_key: str = None) -> dict[str, Any]:
        auth = authenticate_api_key(api_key, required_scope="admin:read")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "dashboard")
        from tryops import db
        conn = db.connect()
        try:
            return db.dashboard_summary(conn)
        finally:
            conn.close()

    @app.get("/api/quota/summary")
    @app.get("/v1/quota/summary")
    def get_quota_summary(api_key: str = None) -> dict[str, Any]:
        auth = authenticate_api_key(api_key, required_scope="admin:read")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "quota")
        try:
            return {"status": "ok", "data": load_quota_read_model()}
        except (OSError, ValueError) as exc:
            return structured_error(
                request_id="unknown",
                code="quota_read_model_unavailable",
                message=str(exc),
                workload="quota",
            )

    @app.get("/api/evaluations/summary")
    @app.get("/v1/evaluations/summary")
    def get_evaluation_summary(api_key: str = None) -> dict[str, Any]:
        auth = authenticate_api_key(api_key, required_scope="admin:read")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "evaluations")
        try:
            return {"status": "ok", "data": load_evaluation_index()}
        except (OSError, ValueError) as exc:
            return structured_error(
                request_id="unknown",
                code="evaluation_index_unavailable",
                message=str(exc),
                workload="evaluations",
            )

    @app.get("/api/vton/comparison")
    @app.get("/v1/vton/comparison")
    def get_vton_comparison(api_key: str = None) -> dict[str, Any]:
        auth = authenticate_api_key(api_key, required_scope="admin:read")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "vton_comparison")
        try:
            report = load_json_artifact("artifacts/eval/vton_comparison/comparison.json")
            return {"status": "ok", "data": with_artifact_urls(report)}
        except (OSError, ValueError) as exc:
            return structured_error(
                request_id="unknown",
                code="vton_comparison_unavailable",
                message=str(exc),
                workload="vton",
            )

    @app.get("/api/incidents/workflow")
    @app.get("/v1/incidents/workflow")
    def get_incident_workflow(api_key: str = None) -> dict[str, Any]:
        auth = authenticate_api_key(api_key, required_scope="promotion:evaluate")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "incidents")
        try:
            report = load_json_artifact("artifacts/eval/incidents/native_incident_workflow.json")
            return {"status": "ok", "data": report}
        except (OSError, ValueError) as exc:
            return structured_error(
                request_id="unknown",
                code="incident_workflow_unavailable",
                message=str(exc),
                workload="incidents",
            )

    @app.get("/api/artifacts/file")
    @app.get("/v1/artifacts/file")
    def get_artifact_file(path: str, api_key: str = None) -> Any:
        auth = authenticate_api_key(api_key, required_scope="admin:read")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "artifact")
        try:
            artifact_path = resolve_artifact_path(path)
            media_type = artifact_media_type(artifact_path)
            if FileResponse is None:
                raise RuntimeError("FastAPI file responses are unavailable")
            return FileResponse(artifact_path, media_type=media_type)
        except (OSError, RuntimeError, ValueError) as exc:
            return structured_error(
                request_id="unknown",
                code="artifact_unavailable",
                message=str(exc),
                workload="artifact",
            )

    @app.get("/api/models")
    def get_models(api_key: str = None) -> dict[str, Any]:
        auth = authenticate_api_key(api_key, required_scope="admin:read")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "models")
        from tryops import db
        conn = db.connect()
        try:
            models = db.list_models(conn)
            return {"status": "ok", "data": models}
        finally:
            conn.close()

    @app.post("/api/models/{id}/promote")
    def promote_model(id: str, payload: dict[str, Any]) -> dict[str, Any]:
        auth = authorize_admin_payload(payload, required_scope="promotion:evaluate")
        if not auth["allowed"]:
            return _admin_auth_error("unknown", auth, "models")
        from tryops import db
        conn = db.connect()
        try:
            record = payload.copy()
            record["id"] = id
            db.upsert_model(conn, record)
            db.insert_audit(
                conn,
                actor=payload.get("user_id", "anonymous"),
                action="promote_model",
                target=id,
                detail=record.get("stage", "unknown")
            )
            return {"status": "ok"}
        finally:
            conn.close()

    return app


def _record(
    endpoint: str,
    request_id: str,
    workload: str,
    model_alias: str,
    started_at: float,
    payload: dict[str, Any],
    response: dict[str, Any],
) -> None:
    event = record_api_observation(
        endpoint=endpoint,
        request_id=request_id,
        workload=workload,
        model_alias=model_alias,
        status=str(response.get("status", "unknown")),
        started_at=started_at,
        payload=payload,
        response=response,
    )
    response["trace"] = event["trace"]

    from tryops import db
    import sqlite3
    try:
        conn = db.connect()
        latency_ms = (perf_counter() - started_at) * 1000
        
        input_summary = None
        output_summary = None
        
        if workload == "llm":
            input_summary = payload.get("prompt", "")[:500] if payload.get("prompt") else None
            output_summary = str(response.get("output", {}).get("text", ""))[:500] if response.get("output") else None
        elif workload == "vton":
            input_summary = f"Person: {payload.get('person_image_path', '')}, Garment: {payload.get('garment_image_path', '')}"
            out_img = response.get("report", {}).get("output", {}).get("path")
            if out_img:
                output_summary = out_img
            else:
                out_img = payload.get("output_image_path", "")
                output_summary = out_img
                
        metrics = response.get("report", {}).get("metrics", {}) if workload == "vton" else response.get("metrics", {})
        vram_gb = metrics.get("peak_vram_gb")
        energy_wh = metrics.get("energy_wh")
        cost_usd = metrics.get("estimated_cost_usd")
        quality = metrics.get("native_quality_score")
        if quality is None and workload == "vton":
            quality = response.get("native_vton", {}).get("quality_score")
        
        status = str(response.get("status", "failed" if "error" in response else "completed"))
        if "error" in response:
            status = "failed"
            
        import uuid
        db.insert_request(conn, {
            "id": str(uuid.uuid4()),
            "kind": workload,
            "model_alias": model_alias,
            "adapter": response.get("routing", {}).get("primary_adapter", ""),
            "input_summary": input_summary,
            "output_summary": output_summary,
            "latency_ms": latency_ms,
            "vram_gb": vram_gb,
            "energy_wh": energy_wh,
            "cost_usd": cost_usd,
            "quality": quality,
            "status": status,
            "user_hash": payload.get("user_id"),
            "request_id": request_id,
            "trace_id": event.get("trace", {}).get("trace_id")
        })
    except Exception as e:
        print(f"Failed to persist request to db: {e}")
    finally:
        if 'conn' in locals():
            conn.close()


def _store_vton_upload(payload: dict[str, Any]) -> dict[str, Any]:
    data_url = payload.get("data_url")
    if not isinstance(data_url, str) or not data_url.strip():
        raise ValueError("data_url is required")

    prefix = "data:image/png;base64,"
    if not data_url.startswith(prefix):
        raise ValueError("VTON upload must be a PNG data URL")

    try:
        uploaded_bytes = base64.b64decode(data_url[len(prefix) :], validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError("VTON upload is not valid base64") from exc
    if len(uploaded_bytes) > MAX_IMAGE_BYTES:
        raise ValueError(f"image exceeds {MAX_IMAGE_BYTES} byte limit")
    if not uploaded_bytes.startswith(PNG_SIGNATURE):
        raise ValueError("VTON upload is not a PNG image")

    role = str(payload.get("role", "asset")).strip().lower()
    if role not in {"person", "garment", "asset"}:
        role = "asset"
    filename = Path(str(payload.get("filename", "upload.png"))).name[:180] or "upload.png"
    upload_id = uuid4().hex
    upload_dir = Path("artifacts/runtime/vton/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    raw_path = upload_dir / f".{role}-{upload_id}.raw.png"
    output_path = upload_dir / f"{role}-{upload_id}.png"

    try:
        raw_path.write_bytes(uploaded_bytes)
        image = read_png_rgb(raw_path)
        write_png_rgb(output_path, image)
    except (OSError, ValueError) as exc:
        output_path.unlink(missing_ok=True)
        raise ValueError(f"uploaded image is not supported: {exc}") from exc
    finally:
        raw_path.unlink(missing_ok=True)

    output = str(output_path)
    return {
        "path": output,
        "url": artifact_url(output),
        "role": role,
        "filename": filename,
        "content_type": "image/png",
        "source_size_bytes": len(uploaded_bytes),
        "size_bytes": output_path.stat().st_size,
        "width": image.width,
        "height": image.height,
    }


def _run_vton_adapter(*, adapter: str, clean: dict[str, Any]) -> dict[str, Any]:
    if adapter == "naive-overlay-vton":
        return run_naive_overlay_baseline(
            person_image_path=clean["person_image_path"],
            garment_image_path=clean["garment_image_path"],
            output_image_path=clean["output_image_path"],
            cache_dir=clean.get("cache_dir", "artifacts/cache/vton_preflight"),
        )
    if adapter == "fashn-vton-http":
        return run_remote_fashn_vton(
            person_image_path=clean["person_image_path"],
            garment_image_path=clean["garment_image_path"],
            output_image_path=clean["output_image_path"],
            cache_dir=clean.get("cache_dir", "artifacts/cache/vton_preflight"),
            timeout_ms=clean["timeout_ms"],
            category=clean["category"],
            garment_photo_type=clean["garment_photo_type"],
            num_timesteps=clean["num_timesteps"],
            guidance_scale=clean["guidance_scale"],
            seed=clean["seed"],
            segmentation_free=clean["segmentation_free"],
        )
    raise ValueError(f"unsupported VTON adapter '{adapter}'")


def _optional_json_artifact(path: str) -> dict[str, Any]:
    try:
        return load_json_artifact(path)
    except (OSError, ValueError) as exc:
        return {
            "schema_version": "tryops.optional_artifact_missing.v1",
            "path": path,
            "passed": False,
            "status": "missing",
            "reason": str(exc),
        }


def _write_vton_report_sidecar(report: dict[str, Any]) -> None:
    output_path = report.get("output", {}).get("path")
    if not output_path:
        return
    sidecar_path = Path(str(output_path)).with_suffix(Path(str(output_path)).suffix + ".json")
    sidecar_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")


def _admin_auth_error(request_id: str, auth: dict[str, Any], workload: str) -> dict[str, Any]:
    response = structured_error(
        request_id=request_id,
        code="unauthorized_admin_action",
        message="admin API key is missing or lacks the required scope",
        details=[
            {
                "field": "api_key",
                "message": str(auth["reason"]),
                "required_scope": str(auth["required_scope"]),
            }
        ],
        workload=workload,
    )
    response["auth"] = auth
    return response
