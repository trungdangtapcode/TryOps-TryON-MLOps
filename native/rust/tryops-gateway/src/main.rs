mod auth;
mod cli;
mod config;
mod errors;
mod guardrail;
mod handlers;
mod metrics;
mod proxy;
mod quota;
mod quota_durable;
mod quota_snapshot;
mod quota_store;
mod rate_limit;
mod semantic_cache;
mod state;
mod static_assets;
mod tls;
mod trace_context;
mod trace_envelope;

use std::{env, net::SocketAddr, process};

use tower_http::{limit::RequestBodyLimitLayer, trace::TraceLayer};

#[tokio::main]
async fn main() {
    let args = env::args().collect::<Vec<_>>();
    if args.get(1).is_some_and(|arg| arg == "quota-check") {
        if let Err(error) = quota::run_quota_cli() {
            eprintln!("{error}");
            process::exit(2);
        }
        return;
    }
    if args.get(1).is_some_and(|arg| arg == "health-check") {
        if let Err(error) = cli::run_health_check_cli().await {
            eprintln!("{error}");
            process::exit(2);
        }
        return;
    }

    tracing_subscriber::fmt()
        .with_env_filter("tryops_gateway=info,tower_http=info")
        .init();

    let state = state::AppState::from_env().await;
    let max_body_bytes = state.max_body_bytes;
    let app = handlers::router(state)
        .layer(RequestBodyLimitLayer::new(max_body_bytes))
        .layer(TraceLayer::new_for_http());

    let address = env::var("TRYOPS_GATEWAY_ADDR")
        .unwrap_or_else(|_| "0.0.0.0:8081".to_string())
        .parse::<SocketAddr>()
        .expect("parse TRYOPS_GATEWAY_ADDR");
    if let Some(tls_config) = tls::GatewayTlsConfig::from_env() {
        tracing::info!(
            address = %address,
            cert_path = %tls_config.cert_path,
            "listening with native rustls TLS"
        );
        axum_server::bind_rustls(address, tls_config.load().await)
            .serve(app.into_make_service())
            .await
            .expect("serve gateway with TLS");
    } else {
        tracing::info!("listening on {address}");
        let listener = tokio::net::TcpListener::bind(address)
            .await
            .expect("bind gateway socket");
        axum::serve(listener, app).await.expect("serve gateway");
    }
}
