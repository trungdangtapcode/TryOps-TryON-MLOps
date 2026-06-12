use std::{
    process,
    sync::atomic::{AtomicU64, Ordering},
    time::{SystemTime, UNIX_EPOCH},
};

use axum::http::HeaderMap;
use sha2::{Digest, Sha256};

static TRACE_COUNTER: AtomicU64 = AtomicU64::new(1);

#[derive(Debug, Clone, PartialEq, Eq)]
pub(crate) struct TraceContext {
    trace_id: String,
    span_id: String,
    parent_span_id: Option<String>,
    trace_flags: String,
    remote_parent: bool,
    traceparent: String,
}

#[derive(Debug, Clone, PartialEq, Eq)]
struct ParsedTraceparent {
    trace_id: String,
    span_id: String,
    trace_flags: String,
}

impl TraceContext {
    pub(crate) fn trace_id(&self) -> &str {
        &self.trace_id
    }

    pub(crate) fn span_id(&self) -> &str {
        &self.span_id
    }

    pub(crate) fn trace_flags(&self) -> &str {
        &self.trace_flags
    }

    pub(crate) fn traceparent(&self) -> &str {
        &self.traceparent
    }
}

pub(crate) fn trace_context_from_headers(headers: &HeaderMap) -> TraceContext {
    let parent = headers
        .get("traceparent")
        .and_then(|value| value.to_str().ok())
        .and_then(parse_traceparent);
    match parent {
        Some(parent) => continue_trace(parent),
        None => new_root_trace(),
    }
}

fn continue_trace(parent: ParsedTraceparent) -> TraceContext {
    let span_id = new_span_id();
    let traceparent = format!("00-{}-{}-{}", parent.trace_id, span_id, parent.trace_flags);
    TraceContext {
        trace_id: parent.trace_id,
        span_id,
        parent_span_id: Some(parent.span_id),
        trace_flags: parent.trace_flags,
        remote_parent: true,
        traceparent,
    }
}

fn new_root_trace() -> TraceContext {
    let trace_id = new_trace_id();
    let span_id = new_span_id();
    let trace_flags = "01".to_string();
    let traceparent = format!("00-{trace_id}-{span_id}-{trace_flags}");
    TraceContext {
        trace_id,
        span_id,
        parent_span_id: None,
        trace_flags,
        remote_parent: false,
        traceparent,
    }
}

fn parse_traceparent(value: &str) -> Option<ParsedTraceparent> {
    let normalized = value.trim().to_ascii_lowercase();
    let mut parts = normalized.split('-');
    let version = parts.next()?;
    let trace_id = parts.next()?;
    let span_id = parts.next()?;
    let trace_flags = parts.next()?;
    if version.len() != 2 || version == "ff" || !is_lower_hex(version) {
        return None;
    }
    if trace_id.len() != 32 || !is_lower_hex(trace_id) || is_all_zero(trace_id) {
        return None;
    }
    if span_id.len() != 16 || !is_lower_hex(span_id) || is_all_zero(span_id) {
        return None;
    }
    if trace_flags.len() != 2 || !is_lower_hex(trace_flags) {
        return None;
    }
    Some(ParsedTraceparent {
        trace_id: trace_id.to_string(),
        span_id: span_id.to_string(),
        trace_flags: trace_flags.to_string(),
    })
}

fn new_trace_id() -> String {
    nonzero_hex(32, "trace")
}

fn new_span_id() -> String {
    nonzero_hex(16, "span")
}

fn nonzero_hex(length: usize, label: &str) -> String {
    loop {
        let count = TRACE_COUNTER.fetch_add(1, Ordering::Relaxed);
        let nanos = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap_or_default()
            .as_nanos();
        let mut hasher = Sha256::new();
        hasher.update(label.as_bytes());
        hasher.update(process::id().to_le_bytes());
        hasher.update(count.to_le_bytes());
        hasher.update(nanos.to_le_bytes());
        let digest = format!("{:x}", hasher.finalize());
        let value = digest.chars().take(length).collect::<String>();
        if !is_all_zero(&value) {
            return value;
        }
    }
}

fn is_lower_hex(value: &str) -> bool {
    value
        .bytes()
        .all(|byte| byte.is_ascii_digit() || (b'a'..=b'f').contains(&byte))
}

fn is_all_zero(value: &str) -> bool {
    value.bytes().all(|byte| byte == b'0')
}

#[cfg(test)]
mod tests {
    use axum::http::{HeaderMap, HeaderValue};

    use super::*;

    #[test]
    fn continues_valid_traceparent_with_new_gateway_span() {
        let mut headers = HeaderMap::new();
        headers.insert(
            "traceparent",
            HeaderValue::from_static("00-11111111111111111111111111111111-2222222222222222-01"),
        );

        let context = trace_context_from_headers(&headers);

        assert_eq!(context.trace_id, "11111111111111111111111111111111");
        assert_eq!(context.parent_span_id.as_deref(), Some("2222222222222222"));
        assert_eq!(context.trace_flags, "01");
        assert!(context.remote_parent);
        assert_ne!(context.span_id, "2222222222222222");
        assert_eq!(context.traceparent.len(), 55);
        assert!(context
            .traceparent
            .starts_with("00-11111111111111111111111111111111-"));
        assert!(parse_traceparent(&context.traceparent).is_some());
    }

    #[test]
    fn starts_new_trace_when_traceparent_is_missing_or_invalid() {
        let headers = HeaderMap::new();
        let missing = trace_context_from_headers(&headers);

        assert_eq!(missing.traceparent.len(), 55);
        assert!(!missing.remote_parent);
        assert!(parse_traceparent(&missing.traceparent).is_some());

        let mut invalid_headers = HeaderMap::new();
        invalid_headers.insert(
            "traceparent",
            HeaderValue::from_static("00-00000000000000000000000000000000-2222222222222222-01"),
        );
        let invalid = trace_context_from_headers(&invalid_headers);

        assert_ne!(invalid.trace_id, "00000000000000000000000000000000");
        assert!(!invalid.remote_parent);
        assert!(parse_traceparent(&invalid.traceparent).is_some());
    }

    #[test]
    fn rejects_non_w3c_traceparent_values() {
        assert!(parse_traceparent("not-a-trace").is_none());
        assert!(
            parse_traceparent("ff-11111111111111111111111111111111-2222222222222222-01").is_none()
        );
        assert!(
            parse_traceparent("00-11111111111111111111111111111111-0000000000000000-01").is_none()
        );
        assert!(
            parse_traceparent("00-11111111111111111111111111111111-2222222222222222-zz").is_none()
        );
    }
}
