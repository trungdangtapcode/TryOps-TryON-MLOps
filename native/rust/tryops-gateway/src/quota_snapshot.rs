use std::collections::BTreeMap;

use serde::Serialize;

use crate::quota::QuotaUsageRow;

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub(crate) struct QuotaTenantDimension {
    pub(crate) dimension: String,
    pub(crate) used: u64,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub(crate) struct QuotaTenantSnapshot {
    pub(crate) period: String,
    pub(crate) user_hash: String,
    pub(crate) total_used: u64,
    pub(crate) dimensions: Vec<QuotaTenantDimension>,
}

pub(crate) fn build_tenant_snapshots(rows: &[QuotaUsageRow]) -> Vec<QuotaTenantSnapshot> {
    let mut grouped = BTreeMap::<(String, String), Vec<QuotaTenantDimension>>::new();
    for row in rows {
        grouped
            .entry((row.period.clone(), row.user_hash.clone()))
            .or_default()
            .push(QuotaTenantDimension {
                dimension: row.dimension.clone(),
                used: row.used,
            });
    }

    grouped
        .into_iter()
        .map(|((period, user_hash), mut dimensions)| {
            dimensions.sort_by(|left, right| left.dimension.cmp(&right.dimension));
            let total_used = dimensions.iter().fold(0_u64, |total, dimension| {
                total.saturating_add(dimension.used)
            });
            QuotaTenantSnapshot {
                period,
                user_hash,
                total_used,
                dimensions,
            }
        })
        .collect()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn groups_usage_rows_by_period_and_tenant() {
        let rows = vec![
            QuotaUsageRow {
                period: "2026-06-11".to_string(),
                user_hash: "tenant-a".to_string(),
                dimension: "llm_tokens_per_day".to_string(),
                used: 300,
            },
            QuotaUsageRow {
                period: "2026-06-11".to_string(),
                user_hash: "tenant-a".to_string(),
                dimension: "llm_requests_per_day".to_string(),
                used: 2,
            },
            QuotaUsageRow {
                period: "2026-06-12".to_string(),
                user_hash: "tenant-a".to_string(),
                dimension: "vton_requests_per_day".to_string(),
                used: 1,
            },
        ];

        let snapshots = build_tenant_snapshots(&rows);

        assert_eq!(snapshots.len(), 2);
        assert_eq!(snapshots[0].period, "2026-06-11");
        assert_eq!(snapshots[0].user_hash, "tenant-a");
        assert_eq!(snapshots[0].total_used, 302);
        assert_eq!(snapshots[0].dimensions[0].dimension, "llm_requests_per_day");
        assert_eq!(snapshots[0].dimensions[1].dimension, "llm_tokens_per_day");
    }
}
