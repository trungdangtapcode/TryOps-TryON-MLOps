use std::{
    path::{Component, Path, PathBuf},
    sync::Arc,
    time::Instant,
};

use axum::{
    body::Bytes,
    extract::State,
    http::{header, Method, StatusCode, Uri},
    response::{IntoResponse, Response},
};

use crate::{config::optional_env, errors::gateway_error, state::AppState};

#[derive(Clone, Debug)]
pub(crate) struct StaticAssets {
    root: Option<PathBuf>,
}

impl StaticAssets {
    pub(crate) fn from_env() -> Self {
        Self {
            root: optional_env("TRYOPS_GATEWAY_STATIC_DIR").map(PathBuf::from),
        }
    }

    #[cfg(test)]
    pub(crate) fn disabled() -> Self {
        Self { root: None }
    }

    async fn serve(&self, method: Method, path: &str) -> Response {
        if method != Method::GET && method != Method::HEAD {
            return gateway_error(
                StatusCode::METHOD_NOT_ALLOWED,
                "static_method_not_allowed",
                "static assets only support GET and HEAD".to_string(),
            );
        }
        let Some(root) = &self.root else {
            return gateway_error(
                StatusCode::NOT_FOUND,
                "static_assets_disabled",
                "TRYOPS_GATEWAY_STATIC_DIR is not configured".to_string(),
            );
        };

        let Some(candidate) = resolve_static_path(root, path) else {
            return gateway_error(
                StatusCode::NOT_FOUND,
                "static_path_not_found",
                format!("static path is outside the configured asset root: {path}"),
            );
        };

        let file_path = match tokio::fs::metadata(&candidate).await {
            Ok(metadata) if metadata.is_file() => candidate,
            _ if should_spa_fallback(path) => root.join("index.html"),
            _ => {
                return gateway_error(
                    StatusCode::NOT_FOUND,
                    "static_path_not_found",
                    format!("static asset was not found: {path}"),
                );
            }
        };

        match tokio::fs::read(&file_path).await {
            Ok(bytes) => static_response(path, &file_path, method, bytes),
            Err(error) => gateway_error(
                StatusCode::NOT_FOUND,
                "static_path_not_found",
                format!("failed to read static asset {path}: {error}"),
            ),
        }
    }
}

pub(crate) async fn serve_static_asset(
    State(state): State<Arc<AppState>>,
    method: Method,
    uri: Uri,
) -> Response {
    let started = Instant::now();
    let route_label = static_route_label(uri.path());
    let response = state.static_assets.serve(method.clone(), uri.path()).await;
    let elapsed_ms = started.elapsed().as_secs_f64() * 1000.0;
    {
        let mut metrics = state.metrics.lock().expect("metrics ledger mutex poisoned");
        metrics.record_request(
            &route_label,
            method.as_str(),
            response.status().as_u16(),
            elapsed_ms,
        );
    }
    response
}

fn static_response(
    request_path: &str,
    file_path: &Path,
    method: Method,
    bytes: Vec<u8>,
) -> Response {
    let body = if method == Method::HEAD {
        Bytes::new()
    } else {
        Bytes::from(bytes)
    };
    let mut response = (StatusCode::OK, body).into_response();
    response.headers_mut().insert(
        header::CONTENT_TYPE,
        header::HeaderValue::from_static(content_type(file_path)),
    );
    response.headers_mut().insert(
        header::CACHE_CONTROL,
        header::HeaderValue::from_static(cache_control(request_path)),
    );
    response
}

fn resolve_static_path(root: &Path, request_path: &str) -> Option<PathBuf> {
    let asset_path = request_path.trim_start_matches('/');
    let relative = if asset_path.is_empty() {
        Path::new("index.html")
    } else {
        Path::new(asset_path)
    };

    let mut resolved = root.to_path_buf();
    for component in relative.components() {
        match component {
            Component::Normal(part) => resolved.push(part),
            Component::CurDir => {}
            Component::ParentDir | Component::RootDir | Component::Prefix(_) => return None,
        }
    }
    Some(resolved)
}

fn should_spa_fallback(request_path: &str) -> bool {
    if request_path.starts_with("/assets/") {
        return false;
    }
    let last = request_path.rsplit('/').next().unwrap_or_default();
    request_path == "/" || !last.contains('.')
}

fn content_type(path: &Path) -> &'static str {
    match path
        .extension()
        .and_then(|extension| extension.to_str())
        .unwrap_or_default()
    {
        "css" => "text/css; charset=utf-8",
        "gif" => "image/gif",
        "html" => "text/html; charset=utf-8",
        "ico" => "image/x-icon",
        "jpg" | "jpeg" => "image/jpeg",
        "js" => "text/javascript; charset=utf-8",
        "json" => "application/json; charset=utf-8",
        "png" => "image/png",
        "svg" => "image/svg+xml",
        "txt" => "text/plain; charset=utf-8",
        "wasm" => "application/wasm",
        "webp" => "image/webp",
        _ => "application/octet-stream",
    }
}

fn cache_control(request_path: &str) -> &'static str {
    if request_path.starts_with("/assets/") {
        "public, max-age=31536000, immutable"
    } else {
        "no-store"
    }
}

fn static_route_label(path: &str) -> String {
    if path == "/" {
        "/".to_string()
    } else if path.starts_with("/assets/") {
        "/assets/*".to_string()
    } else {
        "/*".to_string()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn resolves_index_for_root() {
        let root = Path::new("/tmp/tryops-web");
        assert_eq!(
            resolve_static_path(root, "/").unwrap(),
            root.join("index.html")
        );
    }

    #[test]
    fn blocks_parent_directory_escape() {
        let root = Path::new("/tmp/tryops-web");
        assert!(resolve_static_path(root, "/../secret").is_none());
        assert!(resolve_static_path(root, "/assets/../../secret").is_none());
    }

    #[test]
    fn detects_spa_fallback_paths() {
        assert!(should_spa_fallback("/console/history"));
        assert!(should_spa_fallback("/"));
        assert!(!should_spa_fallback("/assets/index.js"));
        assert!(!should_spa_fallback("/favicon.ico"));
    }

    #[test]
    fn maps_content_types() {
        assert_eq!(
            content_type(Path::new("index.html")),
            "text/html; charset=utf-8"
        );
        assert_eq!(
            content_type(Path::new("main.css")),
            "text/css; charset=utf-8"
        );
        assert_eq!(
            content_type(Path::new("app.js")),
            "text/javascript; charset=utf-8"
        );
    }
}
