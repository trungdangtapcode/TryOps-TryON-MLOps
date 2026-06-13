CREATE TABLE IF NOT EXISTS accounts (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free',
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    created_by_subject TEXT
);

CREATE TABLE IF NOT EXISTS account_members (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    subject TEXT NOT NULL,
    email TEXT,
    display_name TEXT,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ,
    UNIQUE(account_id, subject)
);

CREATE TABLE IF NOT EXISTS account_audit_log (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    actor_subject TEXT,
    action TEXT NOT NULL,
    target TEXT,
    detail JSONB
);

ALTER TABLE requests ADD COLUMN IF NOT EXISTS account_id TEXT;
ALTER TABLE requests ADD COLUMN IF NOT EXISTS principal_subject TEXT;
ALTER TABLE feedback ADD COLUMN IF NOT EXISTS account_id TEXT;
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS account_id TEXT;
ALTER TABLE models ADD COLUMN IF NOT EXISTS account_id TEXT;
ALTER TABLE audit_log ADD COLUMN IF NOT EXISTS account_id TEXT;

INSERT INTO accounts (id, name, slug, plan, status, created_at, created_by_subject)
VALUES ('acct_demo', 'Demo Workspace', 'demo', 'free', 'active', NOW(), 'demo-local-user')
ON CONFLICT (id) DO NOTHING;

INSERT INTO account_members
    (id, account_id, subject, email, display_name, role, status, created_at, last_seen_at)
VALUES
    ('member_demo_owner', 'acct_demo', 'demo-local-user', 'demo@tryops.local', 'Demo Owner', 'account_owner', 'active', NOW(), NOW())
ON CONFLICT (account_id, subject) DO NOTHING;

UPDATE requests SET account_id = 'acct_demo' WHERE account_id IS NULL;
UPDATE feedback SET account_id = 'acct_demo' WHERE account_id IS NULL;
UPDATE jobs SET account_id = 'acct_demo' WHERE account_id IS NULL;
UPDATE models SET account_id = 'acct_demo' WHERE account_id IS NULL;
UPDATE audit_log SET account_id = 'acct_demo' WHERE account_id IS NULL;

CREATE INDEX IF NOT EXISTS idx_accounts_slug ON accounts(slug);
CREATE INDEX IF NOT EXISTS idx_account_members_subject ON account_members(subject);
CREATE INDEX IF NOT EXISTS idx_account_members_account ON account_members(account_id);
CREATE INDEX IF NOT EXISTS idx_account_audit_account ON account_audit_log(account_id, created_at);
CREATE INDEX IF NOT EXISTS idx_requests_account ON requests(account_id, created_at);
CREATE INDEX IF NOT EXISTS idx_feedback_account ON feedback(account_id);
CREATE INDEX IF NOT EXISTS idx_jobs_account ON jobs(account_id);
CREATE INDEX IF NOT EXISTS idx_models_account ON models(account_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_account ON audit_log(account_id, created_at);
