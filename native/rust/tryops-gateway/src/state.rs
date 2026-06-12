use std::{
    env,
    sync::{Arc, Mutex},
};

use crate::{
    auth::AuthPreflight,
    config::{env_bool, env_u64, optional_env},
    metrics::MetricsLedger,
    quota::QuotaLedger,
    quota_durable::QuotaDurableStore,
    quota_store::QuotaLedgerStore,
    rate_limit::EdgeRateLedger,
    semantic_cache::{parse_native_cache_entries, NativeCacheEntry},
    static_assets::StaticAssets,
};

#[derive(Clone)]
pub(crate) struct AppState {
    pub(crate) service_name: &'static str,
    pub(crate) quota: Arc<Mutex<QuotaLedger>>,
    pub(crate) edge_rate: Arc<Mutex<EdgeRateLedger>>,
    pub(crate) metrics: Arc<Mutex<MetricsLedger>>,
    pub(crate) auth: AuthPreflight,
    pub(crate) quota_store: Option<QuotaLedgerStore>,
    pub(crate) quota_durable: Option<QuotaDurableStore>,
    pub(crate) quota_postgres_admission: bool,
    pub(crate) proxy_client: reqwest::Client,
    pub(crate) upstream_base: String,
    pub(crate) guardrail_url: Option<String>,
    pub(crate) semantic_cache_cli: Option<String>,
    pub(crate) semantic_cache_entries: Vec<NativeCacheEntry>,
    pub(crate) static_assets: StaticAssets,
    pub(crate) max_body_bytes: usize,
    pub(crate) rate_limit_per_minute: u64,
    pub(crate) structured_log_path: Option<String>,
}

impl AppState {
    pub(crate) async fn from_env() -> Arc<Self> {
        let quota_store = QuotaLedgerStore::from_env();
        let quota = match &quota_store {
            Some(store) => store
                .load()
                .expect("load TRYOPS_GATEWAY_QUOTA_LEDGER_PATH quota ledger"),
            None => QuotaLedger::default(),
        };
        let quota_durable = match QuotaDurableStore::from_env().await {
            Ok(store) => store,
            Err(error) => {
                tracing::error!(
                    error = %error,
                    "durable quota mirror disabled; falling back to local quota ledger"
                );
                None
            }
        };
        if let Some(store) = &quota_durable {
            tracing::info!(
                adapters = ?store.adapter_names(),
                "durable quota mirror enabled"
            );
        }
        Arc::new(Self {
            service_name: "tryops-gateway",
            quota: Arc::new(Mutex::new(quota)),
            edge_rate: Arc::new(Mutex::new(EdgeRateLedger::default())),
            metrics: Arc::new(Mutex::new(MetricsLedger::default())),
            auth: AuthPreflight::from_env(),
            quota_store,
            quota_durable,
            quota_postgres_admission: env_bool("TRYOPS_GATEWAY_QUOTA_POSTGRES_ADMISSION", false),
            proxy_client: reqwest::Client::new(),
            upstream_base: env::var("TRYOPS_GATEWAY_UPSTREAM")
                .unwrap_or_else(|_| "http://127.0.0.1:8080".to_string()),
            guardrail_url: optional_env("TRYOPS_GATEWAY_GUARDRAIL_URL"),
            semantic_cache_cli: optional_env("TRYOPS_GATEWAY_SEMANTIC_CACHE_CLI"),
            semantic_cache_entries: optional_env("TRYOPS_GATEWAY_SEMANTIC_CACHE_ENTRIES")
                .map(|entries| parse_native_cache_entries(&entries))
                .unwrap_or_default(),
            static_assets: StaticAssets::from_env(),
            max_body_bytes: env_u64("TRYOPS_GATEWAY_MAX_BODY_BYTES", 4 * 1024 * 1024) as usize,
            rate_limit_per_minute: env_u64("TRYOPS_GATEWAY_RATE_LIMIT_PER_MINUTE", 600),
            structured_log_path: optional_env("TRYOPS_GATEWAY_STRUCTURED_LOG_PATH"),
        })
    }
}

#[cfg(test)]
pub(crate) fn test_state(guardrail_url: Option<String>) -> Arc<AppState> {
    Arc::new(AppState {
        service_name: "tryops-gateway",
        quota: Arc::new(Mutex::new(QuotaLedger::default())),
        edge_rate: Arc::new(Mutex::new(EdgeRateLedger::default())),
        metrics: Arc::new(Mutex::new(MetricsLedger::default())),
        auth: AuthPreflight::default(),
        quota_store: None,
        quota_durable: None,
        quota_postgres_admission: false,
        proxy_client: reqwest::Client::new(),
        upstream_base: "http://127.0.0.1:8080".to_string(),
        guardrail_url,
        semantic_cache_cli: None,
        semantic_cache_entries: Vec::new(),
        static_assets: StaticAssets::disabled(),
        max_body_bytes: 1024 * 1024,
        rate_limit_per_minute: 600,
        structured_log_path: None,
    })
}
