CREATE TABLE IF NOT EXISTS tryops_quota_usage (
    period TEXT NOT NULL,
    user_hash TEXT NOT NULL,
    dimension TEXT NOT NULL,
    plan TEXT NOT NULL,
    workload TEXT NOT NULL,
    used BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (period, user_hash, dimension)
);

CREATE INDEX IF NOT EXISTS idx_tryops_quota_usage_period ON tryops_quota_usage(period);
CREATE INDEX IF NOT EXISTS idx_tryops_quota_usage_workload ON tryops_quota_usage(workload);
