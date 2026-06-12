use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};

use crate::trace_context::TraceContext;

pub(crate) const NATIVE_TRACE_LOG_SCHEMA: &str = "tryops.native_trace_log_envelope.v1";

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub(crate) struct NativeTraceLogEnvelope {
    pub(crate) schema_version: String,
    pub(crate) timestamp: String,
    pub(crate) observed_timestamp: String,
    pub(crate) language: String,
    pub(crate) runtime: String,
    pub(crate) component: String,
    pub(crate) event_name: String,
    pub(crate) severity_text: String,
    pub(crate) severity_number: u8,
    pub(crate) trace_id: String,
    pub(crate) span_id: String,
    pub(crate) trace_flags: String,
    pub(crate) traceparent: String,
    pub(crate) request_id: String,
    pub(crate) workload: String,
    pub(crate) resource: BTreeMap<String, String>,
    pub(crate) attributes: BTreeMap<String, String>,
}

impl NativeTraceLogEnvelope {
    pub(crate) fn gateway_proxy_request(
        trace_context: &TraceContext,
        request_id: &str,
        endpoint: &str,
        method: &str,
        service_version: &str,
    ) -> Self {
        let timestamp = unix_timestamp_millis();
        let mut resource = BTreeMap::new();
        resource.insert("service.name".to_string(), "tryops-gateway".to_string());
        resource.insert("service.version".to_string(), service_version.to_string());
        resource.insert("telemetry.sdk.language".to_string(), "rust".to_string());

        let mut attributes = BTreeMap::new();
        attributes.insert("endpoint".to_string(), endpoint.to_string());
        attributes.insert("method".to_string(), method.to_string());
        attributes.insert("status".to_string(), "forwarded".to_string());

        Self {
            schema_version: NATIVE_TRACE_LOG_SCHEMA.to_string(),
            timestamp: timestamp.clone(),
            observed_timestamp: timestamp,
            language: "rust".to_string(),
            runtime: "tokio-axum".to_string(),
            component: "edge-gateway".to_string(),
            event_name: "tryops.gateway.proxy.request".to_string(),
            severity_text: "INFO".to_string(),
            severity_number: 9,
            trace_id: trace_context.trace_id().to_string(),
            span_id: trace_context.span_id().to_string(),
            trace_flags: trace_context.trace_flags().to_string(),
            traceparent: trace_context.traceparent().to_string(),
            request_id: request_id.to_string(),
            workload: workload_from_endpoint(endpoint).to_string(),
            resource,
            attributes,
        }
    }

    #[cfg(test)]
    pub(crate) fn validate(&self) -> Vec<String> {
        let mut errors = Vec::new();
        if self.schema_version != NATIVE_TRACE_LOG_SCHEMA {
            errors.push("schema_version mismatch".to_string());
        }
        if !is_hex_len(&self.trace_id, 32) || is_all_zero(&self.trace_id) {
            errors.push("invalid trace_id".to_string());
        }
        if !is_hex_len(&self.span_id, 16) || is_all_zero(&self.span_id) {
            errors.push("invalid span_id".to_string());
        }
        if !is_hex_len(&self.trace_flags, 2) {
            errors.push("invalid trace_flags".to_string());
        }
        if self.traceparent != format!("00-{}-{}-{}", self.trace_id, self.span_id, self.trace_flags)
        {
            errors.push("traceparent does not match trace fields".to_string());
        }
        if self
            .resource
            .get("service.name")
            .map_or(true, |value| value.is_empty())
        {
            errors.push("resource.service.name is required".to_string());
        }
        if self
            .resource
            .get("service.version")
            .map_or(true, |value| value.is_empty())
        {
            errors.push("resource.service.version is required".to_string());
        }
        if self.event_name.is_empty() {
            errors.push("event_name is required".to_string());
        }
        if self.severity_number == 0 {
            errors.push("severity_number must be positive".to_string());
        }
        errors
    }

    pub(crate) fn with_outcome(mut self, status_code: u16, latency_ms: f64) -> Self {
        self.attributes
            .insert("status".to_string(), status_code.to_string());
        self.attributes
            .insert("latency_ms".to_string(), format!("{latency_ms:.3}"));
        if status_code >= 500 {
            self.severity_text = "ERROR".to_string();
            self.severity_number = 17;
        } else if status_code >= 400 {
            self.severity_text = "WARN".to_string();
            self.severity_number = 13;
        }
        self
    }
}

fn workload_from_endpoint(endpoint: &str) -> &'static str {
    if endpoint.contains("/llm/") {
        "llm"
    } else if endpoint.contains("/vton/") {
        "vton"
    } else if endpoint.contains("/quota/") {
        "quota"
    } else {
        "platform"
    }
}

fn unix_timestamp_millis() -> String {
    let millis = std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap_or_default()
        .as_millis();
    format!("{millis}")
}

#[cfg(test)]
fn is_hex_len(value: &str, length: usize) -> bool {
    value.len() == length
        && value
            .bytes()
            .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

#[cfg(test)]
fn is_all_zero(value: &str) -> bool {
    value.bytes().all(|byte| byte == b'0')
}

#[cfg(test)]
mod tests {
    use axum::http::{HeaderMap, HeaderValue};

    use crate::trace_context::trace_context_from_headers;

    use super::*;

    #[test]
    fn gateway_envelope_matches_shared_trace_contract() {
        let mut headers = HeaderMap::new();
        headers.insert(
            "traceparent",
            HeaderValue::from_static("00-11111111111111111111111111111111-2222222222222222-01"),
        );
        let context = trace_context_from_headers(&headers);

        let envelope = NativeTraceLogEnvelope::gateway_proxy_request(
            &context,
            "req-rust",
            "/v1/llm/generate",
            "POST",
            "0.1.0",
        );

        assert_eq!(envelope.schema_version, NATIVE_TRACE_LOG_SCHEMA);
        assert_eq!(envelope.trace_id, "11111111111111111111111111111111");
        assert_eq!(envelope.workload, "llm");
        assert!(envelope.traceparent.ends_with("-01"));
        assert_eq!(envelope.validate(), Vec::<String>::new());
    }

    #[test]
    fn gateway_envelope_records_outcome_without_breaking_contract() {
        let mut headers = HeaderMap::new();
        headers.insert(
            "traceparent",
            HeaderValue::from_static("00-11111111111111111111111111111111-2222222222222222-01"),
        );
        let context = trace_context_from_headers(&headers);
        let envelope = NativeTraceLogEnvelope::gateway_proxy_request(
            &context,
            "req-rust",
            "/v1/llm/generate",
            "POST",
            "0.1.0",
        )
        .with_outcome(429, 12.3456);

        assert_eq!(envelope.attributes["status"], "429");
        assert_eq!(envelope.attributes["latency_ms"], "12.346");
        assert_eq!(envelope.severity_text, "WARN");
        assert_eq!(envelope.validate(), Vec::<String>::new());
    }

    #[test]
    fn validation_rejects_invalid_trace_ids() {
        let mut headers = HeaderMap::new();
        headers.insert(
            "traceparent",
            HeaderValue::from_static("00-11111111111111111111111111111111-2222222222222222-01"),
        );
        let context = trace_context_from_headers(&headers);
        let mut envelope = NativeTraceLogEnvelope::gateway_proxy_request(
            &context,
            "req-rust",
            "/v1/vton/infer",
            "POST",
            "0.1.0",
        );
        envelope.trace_id = "00000000000000000000000000000000".to_string();

        assert!(envelope
            .validate()
            .contains(&"invalid trace_id".to_string()));
    }
}
