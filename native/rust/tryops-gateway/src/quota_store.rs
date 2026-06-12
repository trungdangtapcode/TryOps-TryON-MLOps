use std::{
    env, fs,
    path::{Path, PathBuf},
};

use serde::{Deserialize, Serialize};

use crate::quota::{QuotaLedger, QuotaUsageRow};

const QUOTA_LEDGER_ENV: &str = "TRYOPS_GATEWAY_QUOTA_LEDGER_PATH";

#[derive(Clone, Debug)]
pub(crate) struct QuotaLedgerStore {
    path: PathBuf,
}

#[derive(Debug, Deserialize, Serialize)]
struct StoredQuotaLedger {
    schema_version: String,
    engine: String,
    usage: Vec<QuotaUsageRow>,
}

impl QuotaLedgerStore {
    pub(crate) fn from_env() -> Option<Self> {
        env::var(QUOTA_LEDGER_ENV)
            .ok()
            .map(|value| value.trim().to_string())
            .filter(|value| !value.is_empty())
            .map(PathBuf::from)
            .map(|path| Self { path })
    }

    pub(crate) fn load(&self) -> Result<QuotaLedger, String> {
        if !self.path.exists() {
            return Ok(QuotaLedger::default());
        }
        let body = fs::read_to_string(&self.path)
            .map_err(|error| format!("read quota ledger {}: {error}", self.path.display()))?;
        let stored = serde_json::from_str::<StoredQuotaLedger>(&body)
            .map_err(|error| format!("parse quota ledger {}: {error}", self.path.display()))?;
        QuotaLedger::from_usage_rows(stored.usage)
    }

    pub(crate) fn save(&self, ledger: &QuotaLedger) -> Result<(), String> {
        if let Some(parent) = self.path.parent() {
            if !parent.as_os_str().is_empty() {
                fs::create_dir_all(parent).map_err(|error| {
                    format!(
                        "create quota ledger directory {}: {error}",
                        parent.display()
                    )
                })?;
            }
        }
        let stored = StoredQuotaLedger {
            schema_version: "tryops.quota_ledger_file.v1".to_string(),
            engine: "native_rust_gateway".to_string(),
            usage: ledger.usage_rows(),
        };
        let body = serde_json::to_vec_pretty(&stored)
            .map_err(|error| format!("serialize quota ledger {}: {error}", self.path.display()))?;
        let temp_path = temp_path_for(&self.path);
        fs::write(&temp_path, body)
            .map_err(|error| format!("write quota ledger {}: {error}", temp_path.display()))?;
        fs::rename(&temp_path, &self.path).map_err(|error| {
            format!(
                "commit quota ledger {} -> {}: {error}",
                temp_path.display(),
                self.path.display()
            )
        })?;
        Ok(())
    }
}

fn temp_path_for(path: &Path) -> PathBuf {
    let mut name = path
        .file_name()
        .map(|value| value.to_os_string())
        .unwrap_or_else(|| "quota-ledger.json".into());
    name.push(".tmp");
    path.with_file_name(name)
}

#[cfg(test)]
mod tests {
    use std::{
        fs,
        time::{SystemTime, UNIX_EPOCH},
    };

    use crate::quota::{QuotaCheckRequest, QuotaLedger};

    use super::*;

    #[test]
    fn quota_store_roundtrips_usage_rows() {
        let path = env::temp_dir().join(format!(
            "tryops-quota-ledger-{}.json",
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap_or_default()
                .as_nanos()
        ));
        let store = QuotaLedgerStore { path: path.clone() };
        let mut ledger = QuotaLedger::default();
        let request = serde_json::from_str::<QuotaCheckRequest>(
            r#"{
                "user_id": "enterprise-user",
                "plan": "free",
                "workload": "llm",
                "request_units": 1,
                "estimated_tokens": 300,
                "period": "2026-06-11"
            }"#,
        )
        .unwrap();
        let decision = ledger.check_and_record(request).unwrap();

        assert!(decision.allowed);
        store.save(&ledger).unwrap();
        let loaded = store.load().unwrap();

        assert_eq!(loaded.snapshot().usage, ledger.snapshot().usage);
        let _ = fs::remove_file(path);
    }
}
