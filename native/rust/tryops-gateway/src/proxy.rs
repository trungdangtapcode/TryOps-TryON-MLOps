use axum::{
    body::Bytes,
    http::{HeaderMap, HeaderName, Method, StatusCode, Uri},
    response::{IntoResponse, Response},
};
use std::time::{SystemTime, UNIX_EPOCH};

const ARTIFACT_FILE_PROXY_PATH: &str = "/v1/artifacts/file";
const ARTIFACT_REF_PREFIX: &str = "artifact:";
const ALLOWED_ARTIFACT_PREFIXES: [&str; 5] = [
    "artifacts/eval/",
    "artifacts/demo/",
    "artifacts/deployments/",
    "artifacts/runtime/",
    "reports/generated/",
];
const ALLOWED_ARTIFACT_EXTENSIONS: [&str; 4] = [".json", ".png", ".jpg", ".jpeg"];

pub(crate) fn api_proxy_path(uri: &Uri) -> Option<String> {
    let path = uri.path();
    if path == "/api" {
        return Some("/v1".to_string());
    }
    path.strip_prefix("/api/")
        .map(|suffix| format!("/v1/{suffix}"))
}

pub(crate) fn proxy_target_url(
    upstream_base: &str,
    proxy_path: &str,
    query: Option<&str>,
) -> String {
    let mut target = format!("{}{}", upstream_base.trim_end_matches('/'), proxy_path);
    if let Some(query) = query {
        if !query.is_empty() {
            target.push('?');
            target.push_str(query);
        }
    }
    target
}

pub(crate) fn is_admin_proxy_path(proxy_path: &str) -> bool {
    proxy_path == "/v1/promotion/evaluate"
        || proxy_path.starts_with("/v1/admin/")
        || (proxy_path.starts_with("/v1/models/") && proxy_path.ends_with("/promote"))
}

pub(crate) fn artifact_path_preflight_error(
    proxy_path: &str,
    query: Option<&str>,
) -> Option<String> {
    if proxy_path != ARTIFACT_FILE_PROXY_PATH {
        return None;
    }
    let raw_path = match query.and_then(|value| query_param(value, "path")) {
        Some(value) if !value.trim().is_empty() => value,
        _ => return Some("artifact path query parameter is required".to_string()),
    };
    let path = percent_decode_component(&raw_path);
    if let Some(artifact_id) = path.strip_prefix(ARTIFACT_REF_PREFIX) {
        if artifact_id.is_empty()
            || artifact_id.len() > 128
            || !artifact_id
                .bytes()
                .all(|byte| byte.is_ascii_alphanumeric() || byte == b'_' || byte == b'-')
        {
            return Some("invalid artifact reference".to_string());
        }
        return None;
    }
    if path.starts_with('/') || path.starts_with('\\') {
        return Some("absolute artifact paths are not allowed".to_string());
    }
    if path.split(['/', '\\']).any(|part| part == "..") {
        return Some("artifact path traversal is not allowed".to_string());
    }
    if !ALLOWED_ARTIFACT_PREFIXES
        .iter()
        .any(|prefix| path.starts_with(prefix))
    {
        return Some("artifact path is outside allowed roots".to_string());
    }
    if !ALLOWED_ARTIFACT_EXTENSIONS
        .iter()
        .any(|suffix| path.to_ascii_lowercase().ends_with(suffix))
    {
        return Some("unsupported artifact type".to_string());
    }
    None
}

fn query_param(query: &str, name: &str) -> Option<String> {
    query.split('&').find_map(|pair| {
        let (key, value) = pair.split_once('=').unwrap_or((pair, ""));
        if percent_decode_component(key) == name {
            Some(value.to_string())
        } else {
            None
        }
    })
}

fn percent_decode_component(value: &str) -> String {
    let bytes = value.as_bytes();
    let mut decoded = Vec::with_capacity(bytes.len());
    let mut index = 0;
    while index < bytes.len() {
        if bytes[index] == b'%' && index + 2 < bytes.len() {
            if let (Some(high), Some(low)) =
                (hex_value(bytes[index + 1]), hex_value(bytes[index + 2]))
            {
                decoded.push((high << 4) | low);
                index += 3;
                continue;
            }
        }
        decoded.push(if bytes[index] == b'+' {
            b' '
        } else {
            bytes[index]
        });
        index += 1;
    }
    String::from_utf8_lossy(&decoded).to_string()
}

fn hex_value(byte: u8) -> Option<u8> {
    match byte {
        b'0'..=b'9' => Some(byte - b'0'),
        b'a'..=b'f' => Some(byte - b'a' + 10),
        b'A'..=b'F' => Some(byte - b'A' + 10),
        _ => None,
    }
}

pub(crate) fn signed_artifact_header_passes(headers: &HeaderMap) -> bool {
    headers
        .get("x-tryops-artifact-signed")
        .and_then(|value| value.to_str().ok())
        .map(|value| {
            matches!(
                value.trim().to_ascii_lowercase().as_str(),
                "true" | "1" | "yes" | "signed"
            )
        })
        .unwrap_or(false)
}

pub(crate) fn request_id_from_headers(headers: &HeaderMap) -> Option<String> {
    headers
        .get("x-request-id")
        .and_then(|header| header.to_str().ok())
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .map(ToOwned::to_owned)
}

pub(crate) fn new_gateway_request_id() -> String {
    let nanos = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_nanos();
    format!("gw-{nanos}")
}

pub(crate) fn method_to_reqwest(method: &Method) -> reqwest::Method {
    reqwest::Method::from_bytes(method.as_str().as_bytes()).unwrap_or(reqwest::Method::GET)
}

pub(crate) fn should_forward_header(name: &str) -> bool {
    !matches!(
        name.to_ascii_lowercase().as_str(),
        "connection"
            | "content-length"
            | "host"
            | "traceparent"
            | "transfer-encoding"
            | "x-request-id"
    )
}

pub(crate) async fn response_from_upstream(upstream: reqwest::Response) -> Response {
    let status =
        StatusCode::from_u16(upstream.status().as_u16()).unwrap_or(StatusCode::BAD_GATEWAY);
    let headers = upstream.headers().clone();
    let body = upstream.bytes().await.unwrap_or_else(|_| Bytes::new());
    let mut response = (status, body).into_response();
    for (name, value) in headers.iter() {
        if should_forward_response_header(name.as_str()) {
            if let Ok(header_name) = HeaderName::from_bytes(name.as_str().as_bytes()) {
                response.headers_mut().insert(header_name, value.clone());
            }
        }
    }
    response
}

fn should_forward_response_header(name: &str) -> bool {
    !matches!(
        name.to_ascii_lowercase().as_str(),
        "connection" | "content-length" | "transfer-encoding"
    )
}

#[cfg(test)]
mod tests {
    use axum::http::HeaderValue;

    use super::*;

    #[test]
    fn maps_public_api_prefix_to_backend_v1_prefix() {
        let uri = "/api/llm/generate?shadow=true".parse::<Uri>().unwrap();
        assert_eq!(api_proxy_path(&uri).unwrap(), "/v1/llm/generate");
        assert_eq!(
            proxy_target_url(
                "http://api:8080/",
                &api_proxy_path(&uri).unwrap(),
                uri.query()
            ),
            "http://api:8080/v1/llm/generate?shadow=true"
        );
    }

    #[test]
    fn detects_admin_proxy_routes_and_signed_artifact_header() {
        assert!(is_admin_proxy_path("/v1/promotion/evaluate"));
        assert!(is_admin_proxy_path("/v1/models/candidate-1/promote"));
        assert!(!is_admin_proxy_path("/v1/llm/generate"));

        let mut headers = HeaderMap::new();
        assert!(!signed_artifact_header_passes(&headers));
        headers.insert("x-tryops-artifact-signed", HeaderValue::from_static("true"));
        assert!(signed_artifact_header_passes(&headers));
    }

    #[test]
    fn preflights_artifact_file_paths() {
        assert_eq!(
            artifact_path_preflight_error(
                "/v1/artifacts/file",
                Some("path=artifacts%2Feval%2Fvton_comparison%2Fnaive_standard.png")
            ),
            None
        );
        assert_eq!(
            artifact_path_preflight_error(
                "/v1/artifacts/file",
                Some("path=artifacts/demo/vton/person.png")
            ),
            None
        );
        assert_eq!(
            artifact_path_preflight_error(
                "/v1/artifacts/file",
                Some("path=artifacts/runtime/vton/console-output.png")
            ),
            None
        );
        assert_eq!(
            artifact_path_preflight_error(
                "/v1/artifacts/file",
                Some("path=artifacts/deployments/rollback_state.json")
            ),
            None
        );
        assert_eq!(
            artifact_path_preflight_error(
                "/v1/artifacts/file",
                Some("path=artifact%3Aartifact_abc123")
            ),
            None
        );
        assert!(artifact_path_preflight_error(
            "/v1/artifacts/file",
            Some("path=artifact%3A..%2Fconfigs%2Fapi_keys")
        )
        .is_some());
        assert!(artifact_path_preflight_error(
            "/v1/artifacts/file",
            Some("path=..%2F..%2Fconfigs%2Fapi_keys.json")
        )
        .is_some());
        assert!(
            artifact_path_preflight_error("/v1/artifacts/file", Some("path=/etc/passwd")).is_some()
        );
        assert!(artifact_path_preflight_error(
            "/v1/artifacts/file",
            Some("path=artifacts/eval/vton_comparison/raw.exe")
        )
        .is_some());
        assert_eq!(
            artifact_path_preflight_error("/v1/llm/generate", Some("path=/etc/passwd")),
            None
        );
    }

    #[test]
    fn proxy_uses_existing_or_generated_request_id() {
        let mut headers = HeaderMap::new();
        assert!(request_id_from_headers(&headers).is_none());

        headers.insert("x-request-id", HeaderValue::from_static("req-123"));
        assert_eq!(request_id_from_headers(&headers).unwrap(), "req-123");
        assert!(new_gateway_request_id().starts_with("gw-"));
    }
}
