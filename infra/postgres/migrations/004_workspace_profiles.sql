CREATE TABLE IF NOT EXISTS user_profiles (
    subject TEXT PRIMARY KEY,
    email TEXT UNIQUE,
    username TEXT,
    display_name TEXT,
    avatar_url TEXT,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS account_invitations (
    id TEXT PRIMARY KEY,
    account_id TEXT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    invited_subject TEXT,
    role TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    invited_by TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    accepted_at TIMESTAMPTZ,
    revoked_at TIMESTAMPTZ
);

ALTER TABLE accounts ADD COLUMN IF NOT EXISTS description TEXT;
ALTER TABLE accounts ADD COLUMN IF NOT EXISTS avatar_url TEXT;
ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS avatar_url TEXT;

INSERT INTO user_profiles
    (subject, email, username, display_name, avatar_url, status, created_at, updated_at, last_seen_at)
VALUES
    (
        'demo-local-user',
        'demo@tryops.local',
        'demo',
        'Demo Owner',
        'https://www.gravatar.com/avatar/' || md5(lower('demo@tryops.local')) || '?d=mp&s=160',
        'active',
        NOW(),
        NOW(),
        NOW()
    )
ON CONFLICT (subject) DO UPDATE SET
    email = EXCLUDED.email,
    username = EXCLUDED.username,
    display_name = EXCLUDED.display_name,
    avatar_url = EXCLUDED.avatar_url,
    updated_at = EXCLUDED.updated_at,
    last_seen_at = EXCLUDED.last_seen_at;

UPDATE accounts
SET avatar_url = COALESCE(avatar_url, 'https://www.gravatar.com/avatar/' || md5(lower('demo@tryops.local')) || '?d=mp&s=160')
WHERE id = 'acct_demo';

CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email);
CREATE INDEX IF NOT EXISTS idx_user_profiles_name ON user_profiles(display_name);
CREATE INDEX IF NOT EXISTS idx_account_invitations_account ON account_invitations(account_id, status);
CREATE INDEX IF NOT EXISTS idx_account_invitations_email ON account_invitations(email, status);
