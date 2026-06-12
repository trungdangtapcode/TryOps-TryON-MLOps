use axum::{
    http::{header, StatusCode},
    response::{IntoResponse, Response},
    Json,
};
use serde::Serialize;

#[derive(Debug, Serialize)]
struct GatewayErrorResponse {
    schema_version: &'static str,
    engine: &'static str,
    error: &'static str,
    reason: String,
}

pub(crate) fn gateway_error(status: StatusCode, error: &'static str, reason: String) -> Response {
    (
        status,
        [(header::CONTENT_TYPE, "application/json")],
        Json(GatewayErrorResponse {
            schema_version: "tryops.gateway_error.v1",
            engine: "native_rust_gateway",
            error,
            reason,
        }),
    )
        .into_response()
}
