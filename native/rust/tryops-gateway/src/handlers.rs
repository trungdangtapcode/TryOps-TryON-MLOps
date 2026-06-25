use std::{
    fs::{create_dir_all, OpenOptions},
    io::Write,
    path::Path,
    sync::Arc,
    time::Instant,
};

use axum::{
    body::Bytes,
    extract::State,
    http::{header, HeaderMap, HeaderValue, Method, StatusCode, Uri},
    response::{IntoResponse, Response},
    routing::{any, get, post},
    Json, Router,
};
use serde::{Deserialize, Serialize};

use crate::{
    auth::{auth_status, required_scope},
    errors::gateway_error,
    guardrail::{edge_guardrail_blocked, edge_guardrail_should_evaluate, evaluate_edge_guardrail},
    metrics::gateway_route_label,
    proxy::{
        api_proxy_path, artifact_path_preflight_error, is_admin_proxy_path, method_to_reqwest,
        new_gateway_request_id, proxy_target_url, request_id_from_headers, response_from_upstream,
        should_forward_header, signed_artifact_header_passes,
    },
    quota::{QuotaCheckRequest, QuotaErrorResponse, QuotaSnapshot},
    rate_limit::{current_minute_window, edge_rate_key},
    semantic_cache::{
        edge_cache_should_evaluate, evaluate_edge_cache_admission, evaluate_native_cache_lookup,
        EdgeCacheAdmission, NativeCacheLookup,
    },
    state::AppState,
    static_assets::serve_static_asset,
    trace_context::trace_context_from_headers,
    trace_envelope::NativeTraceLogEnvelope,
};

#[derive(Debug, Deserialize)]
struct PromotionRequest {
    candidate_id: String,
    workload: String,
    target_stage: String,
    signed: bool,
}

#[derive(Debug, Serialize)]
struct PromotionResponse {
    approved: bool,
    reasons: Vec<String>,
}

#[derive(Debug, Serialize)]
struct HealthResponse {
    status: &'static str,
    service: &'static str,
}

pub(crate) fn router(state: Arc<AppState>) -> Router {
    Router::new()
        .route("/health", get(health))
        .route("/v1/health", get(health))
        .route("/metrics", get(gateway_metrics))
        .route("/v1/metrics", get(gateway_metrics))
        .route("/promotion/evaluate", post(evaluate_promotion))
        .route("/v1/promotion/evaluate", post(evaluate_promotion))
        .route("/quota/check", post(check_quota))
        .route("/v1/quota/check", post(check_quota))
        .route("/quota/snapshot", get(quota_snapshot))
        .route("/v1/quota/snapshot", get(quota_snapshot))
        .route("/api", any(proxy_api))
        .route("/api/{*path}", any(proxy_api))
        .fallback(serve_static_asset)
        .with_state(state)
}

async fn health(State(state): State<Arc<AppState>>) -> Response {
    let started = Instant::now();
    let response = Json(HealthResponse {
        status: "ok",
        service: state.service_name,
    })
    .into_response();
    record_gateway_request(&state, "/health", "GET", response.status(), started);
    response
}

async fn check_quota(
    State(state): State<Arc<AppState>>,
    Json(request): Json<QuotaCheckRequest>,
) -> Response {
    let started = Instant::now();
    if state.quota_postgres_admission {
        if let Some(durable) = &state.quota_durable {
            match durable.check_and_record_postgres(request.clone()).await {
                Ok(Some(decision)) => {
                    if let Err(response) = sync_local_quota_snapshot(&state, &decision, started) {
                        return response;
                    }
                    if decision.allowed {
                        if let Err(error) = durable.record_valkey_allowed_decision(&decision).await
                        {
                            let response = gateway_error(
                                StatusCode::INTERNAL_SERVER_ERROR,
                                "quota_valkey_mirror_failed",
                                error,
                            );
                            record_gateway_request(
                                &state,
                                "/v1/quota/check",
                                "POST",
                                response.status(),
                                started,
                            );
                            return response;
                        }
                    }
                    return quota_decision_response(&state, decision, started);
                }
                Ok(None) => {
                    let response = gateway_error(
                        StatusCode::SERVICE_UNAVAILABLE,
                        "quota_postgres_admission_unavailable",
                        "Postgres admission was requested but no Postgres quota adapter is active"
                            .to_string(),
                    );
                    record_gateway_request(
                        &state,
                        "/v1/quota/check",
                        "POST",
                        response.status(),
                        started,
                    );
                    return response;
                }
                Err(error) => {
                    let response = gateway_error(
                        StatusCode::INTERNAL_SERVER_ERROR,
                        "quota_postgres_admission_failed",
                        error,
                    );
                    record_gateway_request(
                        &state,
                        "/v1/quota/check",
                        "POST",
                        response.status(),
                        started,
                    );
                    return response;
                }
            }
        } else {
            let response = gateway_error(
                StatusCode::SERVICE_UNAVAILABLE,
                "quota_postgres_admission_unavailable",
                "Postgres admission was requested but durable quota adapters are unavailable"
                    .to_string(),
            );
            record_gateway_request(
                &state,
                "/v1/quota/check",
                "POST",
                response.status(),
                started,
            );
            return response;
        }
    }

    let decision = {
        let mut ledger = state.quota.lock().expect("quota ledger mutex poisoned");
        match ledger.check_and_record(request) {
            Ok(decision) => {
                if decision.allowed {
                    if let Some(store) = &state.quota_store {
                        if let Err(error) = store.save(&ledger) {
                            let response = gateway_error(
                                StatusCode::INTERNAL_SERVER_ERROR,
                                "quota_ledger_persist_failed",
                                error,
                            );
                            record_gateway_request(
                                &state,
                                "/v1/quota/check",
                                "POST",
                                response.status(),
                                started,
                            );
                            return response;
                        }
                    }
                }
                Ok(decision)
            }
            Err(error) => Err(error),
        }
    };

    let response = match decision {
        Ok(decision) => {
            if decision.allowed {
                if let Some(durable) = &state.quota_durable {
                    if let Err(error) = durable.record_allowed_decision(&decision).await {
                        let response = gateway_error(
                            StatusCode::INTERNAL_SERVER_ERROR,
                            "quota_durable_ledger_failed",
                            error,
                        );
                        record_gateway_request(
                            &state,
                            "/v1/quota/check",
                            "POST",
                            response.status(),
                            started,
                        );
                        return response;
                    }
                }
            }
            return quota_decision_response(&state, decision, started);
        }
        Err(error) => (
            StatusCode::UNPROCESSABLE_ENTITY,
            Json(QuotaErrorResponse {
                schema_version: "tryops.quota_error.v1",
                engine: "native_rust_gateway",
                allowed: false,
                reason: "invalid_quota_request",
                error,
            }),
        )
            .into_response(),
    };
    record_gateway_request(
        &state,
        "/v1/quota/check",
        "POST",
        response.status(),
        started,
    );
    response
}

fn sync_local_quota_snapshot(
    state: &Arc<AppState>,
    decision: &crate::quota::QuotaDecision,
    started: Instant,
) -> Result<(), Response> {
    let mut ledger = state.quota.lock().expect("quota ledger mutex poisoned");
    ledger.apply_decision_snapshot(decision);
    if let Some(store) = &state.quota_store {
        if let Err(error) = store.save(&ledger) {
            let response = gateway_error(
                StatusCode::INTERNAL_SERVER_ERROR,
                "quota_ledger_persist_failed",
                error,
            );
            record_gateway_request(state, "/v1/quota/check", "POST", response.status(), started);
            return Err(response);
        }
    }
    Ok(())
}

fn quota_decision_response(
    state: &Arc<AppState>,
    decision: crate::quota::QuotaDecision,
    started: Instant,
) -> Response {
    {
        let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
        metrics.record_quota_decision(decision.allowed, &decision.workload, &decision.plan);
    }
    let response = (StatusCode::OK, Json(decision)).into_response();
    record_gateway_request(state, "/v1/quota/check", "POST", response.status(), started);
    response
}

async fn quota_snapshot(State(state): State<Arc<AppState>>) -> Json<QuotaSnapshot> {
    let ledger = state.quota.lock().expect("quota ledger mutex poisoned");
    Json(ledger.snapshot())
}

async fn gateway_metrics(State(state): State<Arc<AppState>>) -> Response {
    let started = Instant::now();
    let body = {
        let metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
        metrics.render()
    };
    let response = (
        StatusCode::OK,
        [(header::CONTENT_TYPE, "text/plain; version=0.0.4")],
        body,
    )
        .into_response();
    record_gateway_request(&state, "/metrics", "GET", response.status(), started);
    response
}

async fn evaluate_promotion(
    State(state): State<Arc<AppState>>,
    Json(request): Json<PromotionRequest>,
) -> Response {
    let started = Instant::now();
    let mut reasons = Vec::new();
    if request.candidate_id.is_empty() {
        reasons.push("candidate_id is required".to_string());
    }
    if request.workload != "vton" && request.workload != "llm" {
        reasons.push(format!("unsupported workload '{}'", request.workload));
    }
    if request.target_stage != "staging" && request.target_stage != "champion" {
        reasons.push(format!(
            "unsupported target_stage '{}'",
            request.target_stage
        ));
    }
    if !request.signed {
        reasons.push("candidate artifact is not signed".to_string());
    }
    if reasons.is_empty() {
        reasons.push("gateway preflight passed".to_string());
    }

    let approved = reasons.len() == 1 && reasons[0] == "gateway preflight passed";
    let status = if approved {
        StatusCode::OK
    } else {
        StatusCode::UNPROCESSABLE_ENTITY
    };

    let response = (status, Json(PromotionResponse { approved, reasons })).into_response();
    record_gateway_request(
        &state,
        "/v1/promotion/evaluate",
        "POST",
        response.status(),
        started,
    );
    response
}

async fn proxy_api(
    State(state): State<Arc<AppState>>,
    method: Method,
    headers: HeaderMap,
    uri: Uri,
    body: Bytes,
) -> Response {
    let started = Instant::now();
    let route_label = gateway_route_label(&uri);
    let method_label = method.as_str().to_string();
    if body.len() > state.max_body_bytes {
        let response = gateway_error(
            StatusCode::PAYLOAD_TOO_LARGE,
            "payload_too_large",
            format!(
                "request body has {} bytes; limit is {} bytes",
                body.len(),
                state.max_body_bytes
            ),
        );
        record_gateway_request(
            &state,
            &route_label,
            &method_label,
            response.status(),
            started,
        );
        return response;
    }

    let proxy_path = match api_proxy_path(&uri) {
        Some(path) => path,
        None => {
            let response = gateway_error(
                StatusCode::NOT_FOUND,
                "proxy_route_not_found",
                format!("no proxy route for {}", uri.path()),
            );
            record_gateway_request(
                &state,
                &route_label,
                &method_label,
                response.status(),
                started,
            );
            return response;
        }
    };
    if is_admin_proxy_path(&proxy_path) && !signed_artifact_header_passes(&headers) {
        let response = gateway_error(
            StatusCode::PRECONDITION_REQUIRED,
            "signed_artifact_preflight_required",
            "admin routes require x-tryops-artifact-signed: true".to_string(),
        );
        record_gateway_request(
            &state,
            &route_label,
            &method_label,
            response.status(),
            started,
        );
        return response;
    }
    if let Some(reason) = artifact_path_preflight_error(&proxy_path, uri.query()) {
        let response = gateway_error(
            StatusCode::BAD_REQUEST,
            "artifact_path_preflight_failed",
            reason,
        );
        record_gateway_request(
            &state,
            &route_label,
            &method_label,
            response.status(),
            started,
        );
        return response;
    }
    let mut auth_principal = None;
    if let Some(required_scope) = required_scope(&method, &proxy_path) {
        let auth = state
            .auth
            .evaluate(&headers, uri.query(), &body, required_scope);
        {
            let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
            metrics.record_auth_decision(auth.allowed, auth.reason, auth.required_scope);
        }
        if !auth.allowed {
            let response = gateway_error(
                auth_status(auth.reason),
                "auth_preflight_failed",
                format!(
                    "native gateway auth preflight denied scope {}: {}",
                    auth.required_scope, auth.reason
                ),
            );
            record_gateway_request(
                &state,
                &route_label,
                &method_label,
                response.status(),
                started,
            );
            return response;
        }
        auth_principal = auth.principal;
    }

    let rate_key = edge_rate_key(&headers);
    let decision = {
        let mut ledger = state
            .edge_rate
            .lock()
            .expect("edge rate ledger mutex poisoned");
        ledger.check_and_record(
            rate_key,
            state.rate_limit_per_minute,
            current_minute_window(),
        )
    };
    if !decision.allowed {
        let mut response = gateway_error(
            StatusCode::TOO_MANY_REQUESTS,
            "edge_rate_limit_exceeded",
            format!(
                "rate limit exceeded for key {}; limit is {} requests per minute",
                decision.key_hash, decision.limit
            ),
        );
        if let Ok(value) = HeaderValue::from_str(&decision.limit.to_string()) {
            response.headers_mut().insert("x-ratelimit-limit", value);
        }
        if let Ok(value) = HeaderValue::from_str(&decision.used_after.to_string()) {
            response.headers_mut().insert("x-ratelimit-used", value);
        }
        {
            let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
            metrics.record_rate_limited();
        }
        record_gateway_request(
            &state,
            &route_label,
            &method_label,
            response.status(),
            started,
        );
        return response;
    }

    if edge_guardrail_should_evaluate(&state, &method, &proxy_path) {
        match evaluate_edge_guardrail(&state, &body).await {
            Ok(guardrails) if guardrails.blocked => {
                {
                    let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
                    metrics.record_guardrail_decision("blocked");
                }
                let response = edge_guardrail_blocked(guardrails);
                record_gateway_request(
                    &state,
                    &route_label,
                    &method_label,
                    response.status(),
                    started,
                );
                return response;
            }
            Ok(_) => {
                let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
                metrics.record_guardrail_decision("passed");
            }
            Err(response) => {
                {
                    let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
                    metrics.record_guardrail_decision("error");
                }
                record_gateway_request(
                    &state,
                    &route_label,
                    &method_label,
                    response.status(),
                    started,
                );
                return response;
            }
        }
    }

    let cache_admission = if edge_cache_should_evaluate(&method, &proxy_path) {
        let decision = evaluate_edge_cache_admission(&body);
        {
            let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
            metrics.record_semantic_cache_admission(decision.admitted, decision.reason);
        }
        Some(decision)
    } else {
        None
    };
    let cache_lookup = cache_admission.as_ref().and_then(|decision| {
        evaluate_native_cache_lookup(
            state.semantic_cache_cli.as_deref(),
            &state.semantic_cache_entries,
            decision,
        )
    });
    if let Some(lookup) = &cache_lookup {
        let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
        metrics.record_semantic_cache_lookup(&lookup.source, lookup.result);
    }

    let target = proxy_target_url(&state.upstream_base, &proxy_path, uri.query());
    let request_id = request_id_from_headers(&headers).unwrap_or_else(new_gateway_request_id);
    let trace_context = trace_context_from_headers(&headers);
    let trace_envelope = NativeTraceLogEnvelope::gateway_proxy_request(
        &trace_context,
        &request_id,
        &proxy_path,
        method.as_str(),
        env!("CARGO_PKG_VERSION"),
    );
    let mut request = state
        .proxy_client
        .request(method_to_reqwest(&method), target)
        .body(body);
    for (name, value) in headers.iter() {
        if should_forward_header(name.as_str()) {
            request = request.header(name.as_str(), value.as_bytes());
        }
    }
    request = request
        .header("x-tryops-gateway", state.service_name)
        .header("x-request-id", request_id.as_str())
        .header("traceparent", trace_context.traceparent())
        .header("x-tryops-trace-id", trace_context.trace_id())
        .header(
            "x-tryops-native-envelope-schema",
            trace_envelope.schema_version.as_str(),
        )
        .header("x-tryops-edge-rate-key", decision.key_hash);
    if let Some(principal) = auth_principal {
        request = add_identity_header(request, "x-tryops-auth-key-id", &principal.key_id);
        request = add_identity_header(request, "x-tryops-auth-subject", &principal.subject);
        request = request
            .header("x-tryops-auth-provider", principal.provider)
            .header("x-tryops-auth-role", header_ascii_value(&principal.role))
            .header("x-tryops-auth-scopes", principal.scopes.join(" "));
        if let Some(email) = principal.email {
            request = add_identity_header(request, "x-tryops-auth-email", &email);
        }
        if let Some(username) = principal.username {
            request = add_identity_header(request, "x-tryops-auth-username", &username);
        }
        if let Some(display_name) = principal.display_name {
            request = add_identity_header(request, "x-tryops-auth-display-name", &display_name);
        }
    }
    request = add_edge_cache_headers(request, cache_admission.as_ref());

    {
        let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
        metrics.record_proxy_inflight_delta(1);
    }
    let upstream = match request.send().await {
        Ok(response) => response,
        Err(error) => {
            let response = gateway_error(
                StatusCode::BAD_GATEWAY,
                "upstream_unavailable",
                format!("failed to reach upstream: {error}"),
            );
            {
                let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
                metrics.record_proxy_inflight_delta(-1);
                metrics.record_upstream_error(&route_label, &method_label);
            }
            record_gateway_request(
                &state,
                &route_label,
                &method_label,
                response.status(),
                started,
            );
            return response;
        }
    };
    {
        let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
        metrics.record_proxy_inflight_delta(-1);
    }
    let mut response = response_from_upstream(upstream).await;
    if let Ok(value) = HeaderValue::from_str(&request_id) {
        response.headers_mut().insert("x-request-id", value);
    }
    if let Ok(value) = HeaderValue::from_str(trace_context.traceparent()) {
        response.headers_mut().insert("traceparent", value);
    }
    if let Ok(value) = HeaderValue::from_str(trace_context.trace_id()) {
        response.headers_mut().insert("x-tryops-trace-id", value);
    }
    add_edge_cache_response_headers(
        &mut response,
        cache_admission.as_ref(),
        cache_lookup.as_ref(),
    );
    record_gateway_proxy_request(
        &state,
        &route_label,
        &method_label,
        response.status(),
        started,
        &trace_envelope,
    );
    response
}

fn add_edge_cache_headers(
    mut request: reqwest::RequestBuilder,
    admission: Option<&EdgeCacheAdmission>,
) -> reqwest::RequestBuilder {
    let Some(admission) = admission else {
        return request;
    };
    request = request
        .header(
            "x-tryops-edge-cache-admission",
            if admission.admitted { "admit" } else { "skip" },
        )
        .header("x-tryops-edge-cache-reason", admission.reason)
        .header("x-tryops-edge-cache-model", admission.model_alias.as_str())
        .header(
            "x-tryops-edge-cache-threshold",
            format!("{:.6}", admission.threshold),
        );
    if let Some(key_hash) = &admission.key_hash {
        request = request.header("x-tryops-edge-cache-key", key_hash.as_str());
    }
    request
}

fn add_edge_cache_response_headers(
    response: &mut Response,
    admission: Option<&EdgeCacheAdmission>,
    lookup: Option<&NativeCacheLookup>,
) {
    let Some(admission) = admission else {
        return;
    };
    if let Ok(value) = HeaderValue::from_str(if admission.admitted { "admit" } else { "skip" }) {
        response
            .headers_mut()
            .insert("x-tryops-edge-cache-admission", value);
    }
    if let Ok(value) = HeaderValue::from_str(admission.reason) {
        response
            .headers_mut()
            .insert("x-tryops-edge-cache-reason", value);
    }
    if let Some(key_hash) = &admission.key_hash {
        if let Ok(value) = HeaderValue::from_str(key_hash) {
            response
                .headers_mut()
                .insert("x-tryops-edge-cache-key", value);
        }
    }
    let Some(lookup) = lookup else {
        return;
    };
    if let Ok(value) = HeaderValue::from_str(if lookup.hit { "true" } else { "false" }) {
        response
            .headers_mut()
            .insert("x-tryops-edge-cache-lookup-hit", value);
    }
    if let Ok(value) = HeaderValue::from_str(lookup.source.as_str()) {
        response
            .headers_mut()
            .insert("x-tryops-edge-cache-lookup-source", value);
    }
    if let Ok(value) = HeaderValue::from_str(lookup.result) {
        response
            .headers_mut()
            .insert("x-tryops-edge-cache-lookup-result", value);
    }
    if let Ok(value) = HeaderValue::from_str(&format!("{:.6}", lookup.score)) {
        response
            .headers_mut()
            .insert("x-tryops-edge-cache-lookup-score", value);
    }
    if !lookup.matched_entry_id.is_empty() {
        if let Ok(value) = HeaderValue::from_str(lookup.matched_entry_id.as_str()) {
            response
                .headers_mut()
                .insert("x-tryops-edge-cache-matched-entry", value);
        }
    }
}

fn record_gateway_request(
    state: &Arc<AppState>,
    route: &str,
    method: &str,
    status: StatusCode,
    started: Instant,
) {
    let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;
    let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
    metrics.record_request(route, method, status.as_u16(), elapsed_ms);
}

fn record_gateway_proxy_request(
    state: &Arc<AppState>,
    route: &str,
    method: &str,
    status: StatusCode,
    started: Instant,
    envelope: &NativeTraceLogEnvelope,
) {
    let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;
    {
        let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
        metrics.record_request(route, method, status.as_u16(), elapsed_ms);
    }
    if let Some(path) = &state.structured_log_path {
        let envelope = envelope.clone().with_outcome(status.as_u16(), elapsed_ms);
        let _guard = state
            .structured_log_lock
            .lock()
            .expect("structured log mutex poisoned");
        if let Err(error) = append_gateway_structured_log(path, &envelope) {
            tracing::warn!(path = path.as_str(), error = %error, "gateway structured log write failed");
        }
    }
}

fn append_gateway_structured_log(
    path: &str,
    envelope: &NativeTraceLogEnvelope,
) -> Result<(), String> {
    let path = Path::new(path);
    if let Some(parent) = path.parent() {
        create_dir_all(parent).map_err(|error| error.to_string())?;
    }
    let mut file = OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
        .map_err(|error| error.to_string())?;
    let mut line = serde_json::to_vec(envelope).map_err(|error| error.to_string())?;
    line.push(b'\n');
    file.write_all(&line).map_err(|error| error.to_string())?;
    Ok(())
}

fn add_identity_header(
    request: reqwest::RequestBuilder,
    name: &'static str,
    value: &str,
) -> reqwest::RequestBuilder {
    let encoded_name = format!("{name}-utf8");
    request
        .header(name, header_ascii_value(value))
        .header(encoded_name, percent_encode_utf8(value))
}

fn header_ascii_value(value: &str) -> String {
    value
        .chars()
        .map(|ch| {
            if ch.is_ascii() && !ch.is_control() {
                ch
            } else {
                '?'
            }
        })
        .collect()
}

fn percent_encode_utf8(value: &str) -> String {
    let mut encoded = String::with_capacity(value.len());
    for byte in value.bytes() {
        if matches!(byte, b'A'..=b'Z' | b'a'..=b'z' | b'0'..=b'9' | b'-' | b'.' | b'_' | b'~') {
            encoded.push(byte as char);
        } else {
            encoded.push('%');
            encoded.push_str(&format!("{byte:02X}"));
        }
    }
    encoded
}
