use axum::http::Method;
use serde_json::Value;
use sha2::{Digest, Sha256};
use std::{
    io::Write,
    process::{Command, Stdio},
};

#[derive(Debug, Clone, PartialEq)]
pub(crate) struct EdgeCacheAdmission {
    pub(crate) admitted: bool,
    pub(crate) reason: &'static str,
    pub(crate) key_hash: Option<String>,
    pub(crate) model_alias: String,
    pub(crate) threshold: f64,
    pub(crate) lookup_query: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub(crate) struct NativeCacheEntry {
    pub(crate) id: String,
    pub(crate) prompt: String,
    pub(crate) input_tokens: f64,
    pub(crate) output_tokens: f64,
    pub(crate) cost_usd: f64,
    pub(crate) energy_wh: f64,
}

#[derive(Debug, Clone, PartialEq)]
pub(crate) struct NativeCacheLookup {
    pub(crate) available: bool,
    pub(crate) hit: bool,
    pub(crate) result: &'static str,
    pub(crate) source: String,
    pub(crate) matched_entry_id: String,
    pub(crate) score: f64,
    pub(crate) entry_count: usize,
    pub(crate) error: Option<String>,
}

pub(crate) fn edge_cache_should_evaluate(method: &Method, proxy_path: &str) -> bool {
    method == Method::POST && proxy_path == "/v1/llm/generate"
}

pub(crate) fn evaluate_edge_cache_admission(body: &[u8]) -> EdgeCacheAdmission {
    let Ok(payload) = serde_json::from_slice::<Value>(body) else {
        return skipped("invalid_json", "unknown", 0.72);
    };
    let enabled = payload
        .get("semantic_cache_enabled")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    let threshold = payload
        .get("semantic_cache_threshold")
        .and_then(Value::as_f64)
        .unwrap_or(0.72);
    let model_alias = payload
        .get("model_alias")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
        .unwrap_or("champion")
        .to_string();
    if !enabled {
        return skipped("disabled_by_request", &model_alias, threshold);
    }
    if !(0.0..=1.0).contains(&threshold) {
        return skipped("invalid_threshold", &model_alias, threshold);
    }
    let Some(prompt) = payload
        .get("prompt")
        .and_then(Value::as_str)
        .map(str::trim)
        .filter(|value| !value.is_empty())
    else {
        return skipped("missing_prompt", &model_alias, threshold);
    };
    if contains_sensitive_prompt_signal(prompt) {
        return skipped("sensitive_prompt", &model_alias, threshold);
    }
    let structured = payload
        .get("structured")
        .and_then(Value::as_bool)
        .unwrap_or(true);
    let query = format!("model={model_alias} structured={structured} prompt={prompt}");
    EdgeCacheAdmission {
        admitted: true,
        reason: "admitted",
        key_hash: Some(short_hash(query.as_bytes())),
        model_alias,
        threshold,
        lookup_query: Some(prompt.to_string()),
    }
}

fn skipped(reason: &'static str, model_alias: &str, threshold: f64) -> EdgeCacheAdmission {
    EdgeCacheAdmission {
        admitted: false,
        reason,
        key_hash: None,
        model_alias: model_alias.to_string(),
        threshold,
        lookup_query: None,
    }
}

pub(crate) fn parse_native_cache_entries(raw: &str) -> Vec<NativeCacheEntry> {
    raw.split(";;")
        .filter_map(|row| {
            let parts = row.split('|').map(str::trim).collect::<Vec<_>>();
            if parts.len() < 2 || parts[0].is_empty() || parts[1].is_empty() {
                return None;
            }
            Some(NativeCacheEntry {
                id: parts[0].to_string(),
                prompt: parts[1].to_string(),
                input_tokens: parse_float(parts.get(2).copied(), 0.0),
                output_tokens: parse_float(parts.get(3).copied(), 0.0),
                cost_usd: parse_float(parts.get(4).copied(), 0.0),
                energy_wh: parse_float(parts.get(5).copied(), 0.0),
            })
        })
        .collect()
}

pub(crate) fn evaluate_native_cache_lookup(
    cli_path: Option<&str>,
    entries: &[NativeCacheEntry],
    admission: &EdgeCacheAdmission,
) -> Option<NativeCacheLookup> {
    if !admission.admitted {
        return None;
    }
    let cli_path = cli_path?;
    if cli_path.trim().is_empty() || entries.is_empty() {
        return None;
    }
    let payload = native_cache_wire_payload(
        admission.lookup_query.as_deref().unwrap_or_default(),
        admission.threshold,
        entries,
    );
    let mut child = match Command::new(cli_path)
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
    {
        Ok(child) => child,
        Err(error) => {
            return Some(NativeCacheLookup {
                available: false,
                hit: false,
                result: "error",
                source: "native_cpp_cli".to_string(),
                matched_entry_id: String::new(),
                score: 0.0,
                entry_count: entries.len(),
                error: Some(format!("spawn failed: {error}")),
            });
        }
    };
    if let Some(stdin) = child.stdin.as_mut() {
        if let Err(error) = stdin.write_all(payload.as_bytes()) {
            return Some(NativeCacheLookup {
                available: false,
                hit: false,
                result: "error",
                source: "native_cpp_cli".to_string(),
                matched_entry_id: String::new(),
                score: 0.0,
                entry_count: entries.len(),
                error: Some(format!("stdin failed: {error}")),
            });
        }
    }
    let output = match child.wait_with_output() {
        Ok(output) => output,
        Err(error) => {
            return Some(NativeCacheLookup {
                available: false,
                hit: false,
                result: "error",
                source: "native_cpp_cli".to_string(),
                matched_entry_id: String::new(),
                score: 0.0,
                entry_count: entries.len(),
                error: Some(format!("wait failed: {error}")),
            });
        }
    };
    if !output.status.success() {
        return Some(NativeCacheLookup {
            available: true,
            hit: false,
            result: "error",
            source: "native_cpp_cli".to_string(),
            matched_entry_id: String::new(),
            score: 0.0,
            entry_count: entries.len(),
            error: Some(String::from_utf8_lossy(&output.stderr).trim().to_string()),
        });
    }
    native_cache_lookup_from_json(&String::from_utf8_lossy(&output.stdout), entries.len())
}

fn native_cache_lookup_from_json(
    raw: &str,
    fallback_entry_count: usize,
) -> Option<NativeCacheLookup> {
    let payload = serde_json::from_str::<Value>(raw).ok()?;
    let lookup = payload.get("lookup").and_then(Value::as_object)?;
    let hit = lookup.get("hit").and_then(Value::as_bool).unwrap_or(false);
    let source = lookup
        .get("source")
        .and_then(Value::as_str)
        .unwrap_or("native_cpp_cli")
        .to_string();
    let matched_entry_id = lookup
        .get("matched_entry_id")
        .and_then(Value::as_str)
        .unwrap_or("")
        .to_string();
    let score = lookup.get("score").and_then(Value::as_f64).unwrap_or(0.0);
    let entry_count = lookup
        .get("entry_count")
        .and_then(Value::as_u64)
        .map(|value| value as usize)
        .unwrap_or(fallback_entry_count);
    Some(NativeCacheLookup {
        available: payload.get("schema_version").and_then(Value::as_str)
            == Some("tryops.native_semantic_cache.v1"),
        hit,
        result: if hit { "hit" } else { "miss" },
        source,
        matched_entry_id,
        score,
        entry_count,
        error: None,
    })
}

fn native_cache_wire_payload(query: &str, threshold: f64, entries: &[NativeCacheEntry]) -> String {
    let mut lines = vec![
        format!("threshold={threshold}"),
        format!("query={}", wire_value(query)),
        format!("entry_count={}", entries.len()),
    ];
    for (index, entry) in entries.iter().enumerate() {
        let prefix = format!("entry.{index}.");
        lines.extend([
            format!("{prefix}id={}", wire_value(&entry.id)),
            format!("{prefix}prompt={}", wire_value(&entry.prompt)),
            format!("{prefix}input_tokens={}", entry.input_tokens),
            format!("{prefix}output_tokens={}", entry.output_tokens),
            format!("{prefix}cost_usd={}", entry.cost_usd),
            format!("{prefix}energy_wh={}", entry.energy_wh),
        ]);
    }
    lines.push(String::new());
    lines.join("\n")
}

fn wire_value(value: &str) -> String {
    value.replace(['\r', '\n'], " ").trim().to_string()
}

fn parse_float(value: Option<&str>, default_value: f64) -> f64 {
    value
        .and_then(|value| value.parse::<f64>().ok())
        .unwrap_or(default_value)
}

fn short_hash(value: &[u8]) -> String {
    let digest = Sha256::digest(value);
    digest
        .iter()
        .take(12)
        .map(|byte| format!("{byte:02x}"))
        .collect()
}

fn contains_sensitive_prompt_signal(prompt: &str) -> bool {
    let lower = prompt.to_ascii_lowercase();
    if [
        "password",
        "secret",
        "api_key",
        "apikey",
        "access token",
        "bearer ",
        "private key",
        "ssn",
        "social security",
        "credit card",
    ]
    .iter()
    .any(|signal| lower.contains(signal))
    {
        return true;
    }
    looks_like_email(&lower) || has_long_digit_run(&lower, 12)
}

fn looks_like_email(value: &str) -> bool {
    value.split_whitespace().any(|token| {
        let token = token.trim_matches(|ch: char| {
            !ch.is_ascii_alphanumeric() && ch != '@' && ch != '.' && ch != '_' && ch != '-'
        });
        let Some((local, domain)) = token.split_once('@') else {
            return false;
        };
        !local.is_empty() && domain.contains('.') && domain.len() >= 3
    })
}

fn has_long_digit_run(value: &str, minimum: usize) -> bool {
    let mut run = 0;
    for ch in value.chars() {
        if ch.is_ascii_digit() {
            run += 1;
            if run >= minimum {
                return true;
            }
        } else if ch != '-' && ch != ' ' {
            run = 0;
        }
    }
    false
}

#[cfg(test)]
mod tests {
    use axum::http::Method;

    use super::*;

    #[test]
    fn edge_cache_only_evaluates_llm_generation_posts() {
        assert!(edge_cache_should_evaluate(
            &Method::POST,
            "/v1/llm/generate"
        ));
        assert!(!edge_cache_should_evaluate(
            &Method::GET,
            "/v1/llm/generate"
        ));
        assert!(!edge_cache_should_evaluate(&Method::POST, "/v1/vton/infer"));
    }

    #[test]
    fn admits_cacheable_llm_prompt() {
        let decision = evaluate_edge_cache_admission(
            br#"{"prompt":"Explain governed VTON.","model_alias":"champion","structured":true}"#,
        );

        assert!(decision.admitted);
        assert_eq!(decision.reason, "admitted");
        assert_eq!(decision.model_alias, "champion");
        assert!(decision.key_hash.is_some());
        assert_eq!(
            decision.lookup_query.as_deref(),
            Some("Explain governed VTON.")
        );
    }

    #[test]
    fn skips_disabled_or_sensitive_prompts() {
        let disabled = evaluate_edge_cache_admission(
            br#"{"prompt":"Explain governed VTON.","semantic_cache_enabled":false}"#,
        );
        assert!(!disabled.admitted);
        assert_eq!(disabled.reason, "disabled_by_request");

        let sensitive = evaluate_edge_cache_admission(
            br#"{"prompt":"send email to user@example.com with my secret token"}"#,
        );
        assert!(!sensitive.admitted);
        assert_eq!(sensitive.reason, "sensitive_prompt");
    }

    #[test]
    fn parses_native_cache_seed_entries() {
        let entries = parse_native_cache_entries(
            "hit-1|Explain TryOps native cache admission.|8|24|0.006|0.02;;bad-row",
        );

        assert_eq!(entries.len(), 1);
        assert_eq!(entries[0].id, "hit-1");
        assert_eq!(entries[0].output_tokens, 24.0);
        assert_eq!(entries[0].energy_wh, 0.02);
    }

    #[test]
    fn parses_native_cache_lookup_output() {
        let lookup = native_cache_lookup_from_json(
            r#"{"schema_version":"tryops.native_semantic_cache.v1","lookup":{"hit":true,"matched_entry_id":"hit-1","score":1.0,"entry_count":1,"source":"native_cpp_cli"}}"#,
            0,
        )
        .unwrap();

        assert!(lookup.available);
        assert!(lookup.hit);
        assert_eq!(lookup.result, "hit");
        assert_eq!(lookup.source, "native_cpp_cli");
        assert_eq!(lookup.matched_entry_id, "hit-1");
        assert_eq!(lookup.entry_count, 1);
    }

    #[test]
    fn renders_native_cache_wire_payload() {
        let entries = parse_native_cache_entries("hit-1|hello world|1|2|0.003|0.1");
        let payload = native_cache_wire_payload("hello\nworld", 0.72, &entries);

        assert!(payload.contains("query=hello world\n"));
        assert!(payload.contains("entry_count=1\n"));
        assert!(payload.contains("entry.0.id=hit-1\n"));
    }
}
