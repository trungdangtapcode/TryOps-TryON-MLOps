use std::{
    collections::HashMap,
    io::{self, Read},
    time::{SystemTime, UNIX_EPOCH},
};

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};

use crate::quota_snapshot::{build_tenant_snapshots, QuotaTenantSnapshot};

#[derive(Debug, Clone, Deserialize)]
pub(crate) struct QuotaCheckRequest {
    user_id: String,
    plan: String,
    workload: String,
    #[serde(default = "default_request_units")]
    request_units: u64,
    #[serde(default)]
    estimated_tokens: u64,
    #[serde(default)]
    period: Option<String>,
}

#[derive(Debug, Clone, Serialize)]
pub(crate) struct QuotaDimensionCheck {
    pub(crate) dimension: String,
    pub(crate) limit: u64,
    pub(crate) used: u64,
    pub(crate) increment: u64,
    pub(crate) remaining_before: u64,
    pub(crate) allowed: bool,
    pub(crate) used_after: u64,
    pub(crate) remaining_after: u64,
}

#[derive(Debug, Clone, Serialize)]
pub(crate) struct QuotaDecision {
    schema_version: &'static str,
    engine: &'static str,
    pub(crate) allowed: bool,
    pub(crate) period: String,
    pub(crate) user_hash: String,
    pub(crate) plan: String,
    pub(crate) workload: String,
    pub(crate) checks: Vec<QuotaDimensionCheck>,
    reason: &'static str,
}

#[derive(Debug, Clone, Serialize)]
pub(crate) struct QuotaSnapshot {
    schema_version: &'static str,
    engine: &'static str,
    pub(crate) usage: Vec<QuotaUsageRow>,
    pub(crate) tenants: Vec<QuotaTenantSnapshot>,
}

#[derive(Debug, Clone, Deserialize, PartialEq, Serialize)]
pub(crate) struct QuotaUsageRow {
    pub(crate) period: String,
    pub(crate) user_hash: String,
    pub(crate) dimension: String,
    pub(crate) used: u64,
}

#[derive(Debug, Serialize)]
pub(crate) struct QuotaErrorResponse {
    pub(crate) schema_version: &'static str,
    pub(crate) engine: &'static str,
    pub(crate) allowed: bool,
    pub(crate) reason: &'static str,
    pub(crate) error: String,
}

#[derive(Debug, Serialize)]
struct QuotaBatchOutput {
    schema_version: &'static str,
    engine: &'static str,
    available: bool,
    decisions: Vec<QuotaDecision>,
    snapshot: QuotaSnapshot,
}

#[derive(Debug, Deserialize)]
struct QuotaBatchInput {
    requests: Vec<QuotaCheckRequest>,
}

#[derive(Debug, Deserialize)]
#[serde(untagged)]
enum QuotaCliInput {
    Batch(QuotaBatchInput),
    Single(QuotaCheckRequest),
}

type UsageKey = (String, String, String);

#[derive(Debug, Default)]
pub(crate) struct QuotaLedger {
    usage: HashMap<UsageKey, u64>,
}

impl QuotaLedger {
    pub(crate) fn from_usage_rows(rows: Vec<QuotaUsageRow>) -> Result<Self, String> {
        let mut usage = HashMap::new();
        for row in rows {
            if row.period.trim().is_empty() {
                return Err("quota usage row has empty period".to_string());
            }
            if row.user_hash.trim().is_empty() {
                return Err("quota usage row has empty user_hash".to_string());
            }
            if row.dimension.trim().is_empty() {
                return Err("quota usage row has empty dimension".to_string());
            }
            usage.insert((row.period, row.user_hash, row.dimension), row.used);
        }
        Ok(Self { usage })
    }

    pub(crate) fn check_and_record(
        &mut self,
        request: QuotaCheckRequest,
    ) -> Result<QuotaDecision, String> {
        if plan_limits(&request.plan).is_none() {
            return Err(format!("unsupported quota plan '{}'", request.plan));
        }
        let dimensions = usage_dimensions(&request)?;
        let period = request.period.unwrap_or_else(current_period_key);
        let user_hash = user_hash(&request.user_id);

        let mut checks = Vec::with_capacity(dimensions.len());
        for (dimension, increment) in dimensions {
            let limit = dimension_limit(&request.plan, dimension)
                .ok_or_else(|| format!("unsupported quota dimension '{dimension}'"))?;
            let key = (period.clone(), user_hash.clone(), dimension.to_string());
            let used = *self.usage.get(&key).unwrap_or(&0);
            let remaining_before = limit.saturating_sub(used);
            let allowed = used.saturating_add(increment) <= limit;
            checks.push((
                key,
                QuotaDimensionCheck {
                    dimension: dimension.to_string(),
                    limit,
                    used,
                    increment,
                    remaining_before,
                    allowed,
                    used_after: used,
                    remaining_after: remaining_before,
                },
            ));
        }

        let allowed = checks.iter().all(|(_, check)| check.allowed);
        if allowed {
            for (key, check) in &mut checks {
                let used_after = check.used.saturating_add(check.increment);
                self.usage.insert(key.clone(), used_after);
                check.used_after = used_after;
                check.remaining_after = check.limit.saturating_sub(used_after);
            }
        }

        Ok(QuotaDecision {
            schema_version: "tryops.quota_decision.v1",
            engine: "native_rust_gateway",
            allowed,
            period,
            user_hash,
            plan: request.plan,
            workload: request.workload,
            checks: checks.into_iter().map(|(_, check)| check).collect(),
            reason: if allowed {
                "within_quota"
            } else {
                "quota_exceeded"
            },
        })
    }

    pub(crate) fn snapshot(&self) -> QuotaSnapshot {
        let usage = self.usage_rows();
        let tenants = build_tenant_snapshots(&usage);
        QuotaSnapshot {
            schema_version: "tryops.quota_snapshot.v1",
            engine: "native_rust_gateway",
            usage,
            tenants,
        }
    }

    pub(crate) fn usage_rows(&self) -> Vec<QuotaUsageRow> {
        let mut rows = self
            .usage
            .iter()
            .map(|((period, user_hash, dimension), used)| QuotaUsageRow {
                period: period.clone(),
                user_hash: user_hash.clone(),
                dimension: dimension.clone(),
                used: *used,
            })
            .collect::<Vec<_>>();
        rows.sort_by(|left, right| {
            (&left.period, &left.user_hash, &left.dimension).cmp(&(
                &right.period,
                &right.user_hash,
                &right.dimension,
            ))
        });
        rows
    }
}

pub(crate) fn run_quota_cli() -> Result<(), String> {
    let mut stdin = String::new();
    io::stdin()
        .read_to_string(&mut stdin)
        .map_err(|error| format!("read stdin: {error}"))?;
    let input = serde_json::from_str::<QuotaCliInput>(&stdin)
        .map_err(|error| format!("parse quota JSON: {error}"))?;

    let store = crate::quota_store::QuotaLedgerStore::from_env();
    let mut ledger = match &store {
        Some(store) => store.load()?,
        None => QuotaLedger::default(),
    };
    let requests = match input {
        QuotaCliInput::Batch(batch) => batch.requests,
        QuotaCliInput::Single(request) => vec![request],
    };
    let mut decisions = Vec::with_capacity(requests.len());
    for request in requests {
        decisions.push(ledger.check_and_record(request)?);
    }
    if let Some(store) = &store {
        if decisions.iter().any(|decision| decision.allowed) {
            store.save(&ledger)?;
        }
    }
    let output = QuotaBatchOutput {
        schema_version: "tryops.native_quota_batch.v1",
        engine: "native_rust_gateway",
        available: true,
        decisions,
        snapshot: ledger.snapshot(),
    };
    let body = serde_json::to_string_pretty(&output)
        .map_err(|error| format!("serialize quota output: {error}"))?;
    println!("{body}");
    Ok(())
}

pub(crate) fn user_hash(user_id: &str) -> String {
    let normalized = match user_id.trim() {
        "" => "anonymous",
        value => value,
    };
    let digest = Sha256::digest(normalized.as_bytes());
    format!("{digest:x}").chars().take(16).collect()
}

fn default_request_units() -> u64 {
    1
}

fn usage_dimensions(request: &QuotaCheckRequest) -> Result<Vec<(&'static str, u64)>, String> {
    match request.workload.as_str() {
        "llm" => Ok(vec![
            ("llm_requests_per_day", request.request_units),
            ("llm_tokens_per_day", request.estimated_tokens),
        ]),
        "vton" => Ok(vec![("vton_requests_per_day", request.request_units)]),
        workload => Err(format!("unsupported quota workload '{workload}'")),
    }
}

fn dimension_limit(plan: &str, dimension: &str) -> Option<u64> {
    plan_limits(plan).and_then(|limits| {
        limits
            .iter()
            .find(|(candidate, _)| *candidate == dimension)
            .map(|(_, limit)| *limit)
    })
}

fn plan_limits(plan: &str) -> Option<&'static [(&'static str, u64)]> {
    match plan {
        "free" => Some(&[
            ("llm_requests_per_day", 20),
            ("llm_tokens_per_day", 5_000),
            ("vton_requests_per_day", 5),
        ]),
        "team" => Some(&[
            ("llm_requests_per_day", 500),
            ("llm_tokens_per_day", 250_000),
            ("vton_requests_per_day", 100),
        ]),
        "enterprise" => Some(&[
            ("llm_requests_per_day", 50_000),
            ("llm_tokens_per_day", 25_000_000),
            ("vton_requests_per_day", 10_000),
        ]),
        _ => None,
    }
}

fn current_period_key() -> String {
    let seconds = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs() as i64;
    let days_since_epoch = seconds / 86_400;
    let (year, month, day) = civil_from_days(days_since_epoch);
    format!("{year:04}-{month:02}-{day:02}")
}

fn civil_from_days(days_since_epoch: i64) -> (i32, u32, u32) {
    let z = days_since_epoch + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = z - era * 146_097;
    let yoe = (doe - doe / 1_460 + doe / 36_524 - doe / 146_096) / 365;
    let y = yoe + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = doy - (153 * mp + 2) / 5 + 1;
    let month = mp + if mp < 10 { 3 } else { -9 };
    let year = y + if month <= 2 { 1 } else { 0 };
    (year as i32, month as u32, day as u32)
}

#[cfg(test)]
mod tests {
    use std::collections::HashMap;

    use super::*;

    fn llm_request(tokens: u64) -> QuotaCheckRequest {
        QuotaCheckRequest {
            user_id: "enterprise-user".to_string(),
            plan: "free".to_string(),
            workload: "llm".to_string(),
            request_units: 1,
            estimated_tokens: tokens,
            period: Some("2026-06-11".to_string()),
        }
    }

    #[test]
    fn records_usage_and_matches_python_hash_contract() {
        let mut ledger = QuotaLedger::default();

        let decision = ledger.check_and_record(llm_request(300)).unwrap();

        assert!(decision.allowed);
        assert_eq!(decision.user_hash, "9cd0ffa8da8b17c4");
        let dimensions = decision
            .checks
            .iter()
            .map(|check| (check.dimension.as_str(), check.used_after))
            .collect::<HashMap<_, _>>();
        assert_eq!(dimensions["llm_requests_per_day"], 1);
        assert_eq!(dimensions["llm_tokens_per_day"], 300);
    }

    #[test]
    fn rejects_over_limit_without_incrementing() {
        let mut ledger = QuotaLedger::default();

        let decision = ledger.check_and_record(llm_request(5_001)).unwrap();

        assert!(!decision.allowed);
        assert_eq!(decision.reason, "quota_exceeded");
        let token_check = decision
            .checks
            .iter()
            .find(|check| check.dimension == "llm_tokens_per_day")
            .unwrap();
        assert_eq!(token_check.used_after, 0);
        assert_eq!(ledger.snapshot().usage.len(), 0);
    }

    #[test]
    fn separates_daily_periods() {
        let mut ledger = QuotaLedger::default();
        let mut first = llm_request(100);
        first.period = Some("2026-06-11".to_string());
        let mut second = llm_request(100);
        second.period = Some("2026-06-12".to_string());

        assert!(ledger.check_and_record(first).unwrap().allowed);
        assert!(ledger.check_and_record(second).unwrap().allowed);

        assert_eq!(ledger.snapshot().usage.len(), 4);
    }

    #[test]
    fn civil_date_conversion_matches_unix_epoch() {
        assert_eq!(civil_from_days(0), (1970, 1, 1));
        assert_eq!(civil_from_days(20_615), (2026, 6, 11));
    }
}
