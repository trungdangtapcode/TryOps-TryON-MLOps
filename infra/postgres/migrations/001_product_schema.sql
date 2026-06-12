CREATE TABLE IF NOT EXISTS requests (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    kind TEXT NOT NULL CHECK (kind IN ('llm', 'vton')),
    model_alias TEXT,
    adapter TEXT,
    input_summary TEXT,
    output_summary TEXT,
    latency_ms DOUBLE PRECISION,
    vram_gb DOUBLE PRECISION,
    energy_wh DOUBLE PRECISION,
    cost_usd DOUBLE PRECISION,
    quality DOUBLE PRECISION,
    status TEXT NOT NULL DEFAULT 'completed',
    user_hash TEXT,
    request_id TEXT,
    trace_id TEXT
);

CREATE TABLE IF NOT EXISTS feedback (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES requests(id) ON DELETE CASCADE,
    rating INTEGER,
    label TEXT,
    comment TEXT,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    payload JSONB,
    result_path TEXT
);

CREATE TABLE IF NOT EXISTS models (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    workload TEXT NOT NULL,
    stage TEXT NOT NULL CHECK (stage IN ('candidate', 'challenger', 'champion', 'archived', 'rejected')),
    version TEXT,
    signed BOOLEAN NOT NULL DEFAULT false,
    approved BOOLEAN NOT NULL DEFAULT false,
    metrics JSONB,
    created_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL,
    actor TEXT,
    action TEXT NOT NULL,
    target TEXT,
    detail JSONB
);

CREATE INDEX IF NOT EXISTS idx_requests_created ON requests(created_at);
CREATE INDEX IF NOT EXISTS idx_requests_kind ON requests(kind);
CREATE INDEX IF NOT EXISTS idx_requests_trace_id ON requests(trace_id);
CREATE INDEX IF NOT EXISTS idx_feedback_request ON feedback(request_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
CREATE INDEX IF NOT EXISTS idx_models_stage ON models(stage);
CREATE INDEX IF NOT EXISTS idx_audit_log_created ON audit_log(created_at);
