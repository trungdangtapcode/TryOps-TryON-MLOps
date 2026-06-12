use std::sync::Arc;

use axum::{
    body::Bytes,
    http::{header, Method, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use serde::{Deserialize, Serialize};

use crate::{errors::gateway_error, state::AppState};

#[derive(Debug, Serialize)]
struct EdgeGuardrailBlockedResponse {
    schema_version: &'static str,
    engine: &'static str,
    error: &'static str,
    reason: String,
    guardrails: NativeGuardrailResponse,
}

#[derive(Debug, Deserialize)]
struct LlmEdgePayload {
    #[serde(default)]
    prompt: String,
    #[serde(default = "default_max_tokens")]
    max_tokens: u64,
    #[serde(default)]
    structured: bool,
}

#[derive(Debug, Serialize)]
struct NativeGuardrailRequest {
    prompt: String,
    output_text: String,
    max_tokens: u64,
    structured: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub(crate) struct NativeGuardrailResponse {
    schema_version: String,
    engine: serde_json::Value,
    status: String,
    pub(crate) blocked: bool,
    #[serde(default)]
    risk_ids: Vec<String>,
    #[serde(default)]
    findings: Vec<NativeGuardrailFinding>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct NativeGuardrailFinding {
    check_id: String,
    owasp_id: String,
    risk: String,
    stage: String,
    action: String,
    severity: String,
    message: String,
}

pub(crate) fn edge_guardrail_should_evaluate(
    state: &AppState,
    method: &Method,
    proxy_path: &str,
) -> bool {
    state.guardrail_url.is_some() && method == Method::POST && proxy_path == "/v1/llm/generate"
}

pub(crate) async fn evaluate_edge_guardrail(
    state: &Arc<AppState>,
    body: &Bytes,
) -> Result<NativeGuardrailResponse, Response> {
    let payload = serde_json::from_slice::<LlmEdgePayload>(body).map_err(|error| {
        gateway_error(
            StatusCode::BAD_REQUEST,
            "edge_guardrail_invalid_json",
            format!("LLM guardrail could not parse request JSON: {error}"),
        )
    })?;
    let guardrail_url = state.guardrail_url.as_ref().ok_or_else(|| {
        gateway_error(
            StatusCode::BAD_GATEWAY,
            "edge_guardrail_not_configured",
            "LLM edge guardrail URL is not configured".to_string(),
        )
    })?;
    let request = NativeGuardrailRequest {
        prompt: payload.prompt,
        output_text: String::new(),
        max_tokens: payload.max_tokens,
        structured: payload.structured,
    };
    let response = state
        .proxy_client
        .post(guardrail_url)
        .json(&request)
        .send()
        .await
        .map_err(|error| {
            gateway_error(
                StatusCode::BAD_GATEWAY,
                "edge_guardrail_unavailable",
                format!("failed to reach native guardrail sidecar: {error}"),
            )
        })?;
    let status = response.status();
    if !status.is_success() {
        return Err(gateway_error(
            StatusCode::BAD_GATEWAY,
            "edge_guardrail_unhealthy",
            format!("native guardrail sidecar returned HTTP {}", status.as_u16()),
        ));
    }
    response
        .json::<NativeGuardrailResponse>()
        .await
        .map_err(|error| {
            gateway_error(
                StatusCode::BAD_GATEWAY,
                "edge_guardrail_invalid_response",
                format!("native guardrail sidecar returned invalid JSON: {error}"),
            )
        })
}

pub(crate) fn edge_guardrail_blocked(guardrails: NativeGuardrailResponse) -> Response {
    let risks = if guardrails.risk_ids.is_empty() {
        "unknown".to_string()
    } else {
        guardrails.risk_ids.join(",")
    };
    (
        StatusCode::FORBIDDEN,
        [(header::CONTENT_TYPE, "application/json")],
        Json(EdgeGuardrailBlockedResponse {
            schema_version: "tryops.gateway_edge_guardrail.v1",
            engine: "native_rust_gateway",
            error: "edge_guardrail_blocked",
            reason: format!("native guardrail sidecar blocked LLM request: {risks}"),
            guardrails,
        }),
    )
        .into_response()
}

fn default_max_tokens() -> u64 {
    256
}

#[cfg(test)]
mod tests {
    use axum::http::Method;

    use super::*;
    use crate::state::test_state;

    #[test]
    fn edge_guardrail_only_runs_for_configured_llm_generation_post() {
        let disabled = test_state(None);
        let enabled = test_state(Some(
            "http://127.0.0.1:18083/v1/guardrails/evaluate".to_string(),
        ));

        assert!(!edge_guardrail_should_evaluate(
            &disabled,
            &Method::POST,
            "/v1/llm/generate"
        ));
        assert!(edge_guardrail_should_evaluate(
            &enabled,
            &Method::POST,
            "/v1/llm/generate"
        ));
        assert!(!edge_guardrail_should_evaluate(
            &enabled,
            &Method::GET,
            "/v1/llm/generate"
        ));
        assert!(!edge_guardrail_should_evaluate(
            &enabled,
            &Method::POST,
            "/v1/vton/infer"
        ));
    }

    #[test]
    fn llm_edge_payload_defaults_guardrail_fields() {
        let payload: LlmEdgePayload =
            serde_json::from_str(r#"{"prompt":"Explain TryOps."}"#).unwrap();

        assert_eq!(payload.prompt, "Explain TryOps.");
        assert_eq!(payload.max_tokens, 256);
        assert!(!payload.structured);
    }
}
