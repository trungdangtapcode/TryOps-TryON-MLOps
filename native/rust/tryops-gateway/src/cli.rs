use std::{env, time::Duration};

pub(crate) async fn run_health_check_cli() -> Result<(), String> {
    let address =
        env::var("TRYOPS_GATEWAY_HEALTH_ADDR").unwrap_or_else(|_| "127.0.0.1:8081".to_string());
    let scheme = env::var("TRYOPS_GATEWAY_HEALTH_SCHEME").unwrap_or_else(|_| "http".to_string());
    let insecure_tls = env_bool("TRYOPS_GATEWAY_HEALTH_INSECURE", false);
    let url = format!("{scheme}://{address}/health");
    let client = reqwest::Client::builder()
        .timeout(Duration::from_secs(2))
        .danger_accept_invalid_certs(insecure_tls)
        .build()
        .map_err(|error| format!("build health client: {error}"))?;
    let response = client
        .get(&url)
        .send()
        .await
        .map_err(|error| format!("request gateway health endpoint at {url}: {error}"))?;
    if response.status().is_success() {
        println!("ok");
        Ok(())
    } else {
        Err(format!(
            "gateway health returned non-200 response: {}",
            response.status()
        ))
    }
}

fn env_bool(name: &str, default_value: bool) -> bool {
    match env::var(name)
        .unwrap_or_default()
        .trim()
        .to_ascii_lowercase()
        .as_str()
    {
        "1" | "true" | "yes" | "y" => true,
        "0" | "false" | "no" | "n" => false,
        _ => default_value,
    }
}
