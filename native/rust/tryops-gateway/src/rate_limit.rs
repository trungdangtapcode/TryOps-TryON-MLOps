use std::time::{SystemTime, UNIX_EPOCH};

use axum::http::HeaderMap;
use serde::Serialize;

use crate::quota::user_hash;

#[derive(Debug, Clone, Serialize)]
pub(crate) struct EdgeRateDecision {
    pub(crate) allowed: bool,
    pub(crate) key_hash: String,
    pub(crate) limit: u64,
    used_before: u64,
    pub(crate) used_after: u64,
    window: u64,
}

#[derive(Debug, Default)]
pub(crate) struct EdgeRateLedger {
    usage: std::collections::HashMap<(u64, String), u64>,
}

impl EdgeRateLedger {
    pub(crate) fn check_and_record(
        &mut self,
        key: String,
        limit: u64,
        window: u64,
    ) -> EdgeRateDecision {
        let key_hash = user_hash(&key);
        let usage_key = (window, key_hash.clone());
        let used_before = *self.usage.get(&usage_key).unwrap_or(&0);
        let allowed = used_before < limit;
        let used_after = if allowed {
            used_before.saturating_add(1)
        } else {
            used_before
        };
        if allowed {
            self.usage.insert(usage_key, used_after);
        }
        EdgeRateDecision {
            allowed,
            key_hash,
            limit,
            used_before,
            used_after,
            window,
        }
    }
}

pub(crate) fn edge_rate_key(headers: &HeaderMap) -> String {
    for name in ["x-tryops-tenant", "x-api-key", "x-forwarded-for"] {
        if let Some(value) = headers.get(name).and_then(|header| header.to_str().ok()) {
            let trimmed = value.trim();
            if !trimmed.is_empty() {
                return trimmed.to_string();
            }
        }
    }
    "anonymous".to_string()
}

pub(crate) fn current_minute_window() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs()
        / 60
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn edge_rate_ledger_rejects_after_limit_without_incrementing() {
        let mut ledger = EdgeRateLedger::default();
        let first = ledger.check_and_record("tenant-a".to_string(), 2, 10);
        let second = ledger.check_and_record("tenant-a".to_string(), 2, 10);
        let third = ledger.check_and_record("tenant-a".to_string(), 2, 10);

        assert!(first.allowed);
        assert!(second.allowed);
        assert!(!third.allowed);
        assert_eq!(third.used_before, 2);
        assert_eq!(third.used_after, 2);
    }
}
