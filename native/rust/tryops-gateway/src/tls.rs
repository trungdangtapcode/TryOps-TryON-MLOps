use crate::config::optional_env;

pub(crate) struct GatewayTlsConfig {
    pub(crate) cert_path: String,
    pub(crate) key_path: String,
}

impl GatewayTlsConfig {
    pub(crate) fn from_env() -> Option<Self> {
        let cert_path = optional_env("TRYOPS_GATEWAY_TLS_CERT_PATH");
        let key_path = optional_env("TRYOPS_GATEWAY_TLS_KEY_PATH");
        match (cert_path, key_path) {
            (Some(cert_path), Some(key_path)) => Some(Self {
                cert_path,
                key_path,
            }),
            (None, None) => None,
            _ => panic!(
                "TRYOPS_GATEWAY_TLS_CERT_PATH and TRYOPS_GATEWAY_TLS_KEY_PATH must be set together"
            ),
        }
    }

    pub(crate) async fn load(&self) -> axum_server::tls_rustls::RustlsConfig {
        let _ = rustls::crypto::aws_lc_rs::default_provider().install_default();
        axum_server::tls_rustls::RustlsConfig::from_pem_file(&self.cert_path, &self.key_path)
            .await
            .expect("load TRYOPS_GATEWAY_TLS_CERT_PATH/TRYOPS_GATEWAY_TLS_KEY_PATH")
    }
}
