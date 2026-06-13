"""TryOps Console data layer (Production App, Phase P1).

A real persistence layer for the end-user product: every LLM/VTON request,
feedback rating, async job, registered model, and admin action is stored in a
relational database. SQLite is the zero-config runnable default (dev/demo); the
same SQL is Postgres-compatible for the enterprise compose profile. The rest of
the app talks to this repository API, never to raw SQL.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from hashlib import md5, sha256
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import quote

DEFAULT_DB_PATH = Path("artifacts/app/tryops.db")
POSTGRES_DSN_ENV = "TRYOPS_APP_POSTGRES_DSN"
POSTGRES_DSN_FILE_ENV = "TRYOPS_APP_POSTGRES_DSN_FILE"
DEMO_ACCOUNT_ID = "acct_demo"
DEMO_SUBJECT = "demo-local-user"
_SCHEMA_LOCK = threading.Lock()

SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id                 TEXT PRIMARY KEY,
    name               TEXT NOT NULL,
    slug               TEXT UNIQUE NOT NULL,
    description        TEXT,
    avatar_url         TEXT,
    plan               TEXT NOT NULL DEFAULT 'free',
    status             TEXT NOT NULL DEFAULT 'active',
    created_at         TEXT NOT NULL,
    created_by_subject TEXT
);
CREATE TABLE IF NOT EXISTS user_profiles (
    subject      TEXT PRIMARY KEY,
    email        TEXT UNIQUE,
    username     TEXT,
    display_name TEXT,
    avatar_url   TEXT,
    status       TEXT NOT NULL DEFAULT 'active',
    created_at   TEXT NOT NULL,
    updated_at   TEXT NOT NULL,
    last_seen_at TEXT
);
CREATE TABLE IF NOT EXISTS account_members (
    id           TEXT PRIMARY KEY,
    account_id   TEXT NOT NULL,
    subject      TEXT NOT NULL,
    email        TEXT,
    display_name TEXT,
    role         TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'active',
    created_at   TEXT NOT NULL,
    last_seen_at TEXT,
    UNIQUE(account_id, subject)
);
CREATE TABLE IF NOT EXISTS account_audit_log (
    id            TEXT PRIMARY KEY,
    account_id    TEXT NOT NULL,
    created_at    TEXT NOT NULL,
    actor_subject TEXT,
    action        TEXT NOT NULL,
    target        TEXT,
    detail        TEXT
);
CREATE TABLE IF NOT EXISTS account_invitations (
    id              TEXT PRIMARY KEY,
    account_id      TEXT NOT NULL,
    email           TEXT NOT NULL,
    invited_subject TEXT,
    role            TEXT NOT NULL,
    status          TEXT NOT NULL DEFAULT 'pending',
    invited_by      TEXT,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL,
    accepted_at     TEXT,
    revoked_at      TEXT
);
CREATE TABLE IF NOT EXISTS requests (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
    account_id    TEXT,
    principal_subject TEXT,
    kind          TEXT NOT NULL,          -- 'llm' | 'vton'
    model_alias   TEXT,
    adapter       TEXT,
    input_summary TEXT,
    output_summary TEXT,
    latency_ms    REAL,
    vram_gb       REAL,
    energy_wh     REAL,
    cost_usd      REAL,
    quality       REAL,
    status        TEXT NOT NULL DEFAULT 'completed',
    user_hash     TEXT,
    request_id    TEXT,
    trace_id      TEXT
);
CREATE TABLE IF NOT EXISTS feedback (
    id          TEXT PRIMARY KEY,
    account_id  TEXT,
    request_id  TEXT NOT NULL,
    rating      INTEGER,
    label       TEXT,
    comment     TEXT,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    account_id  TEXT,
    kind        TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    payload     TEXT,
    result_path TEXT
);
CREATE TABLE IF NOT EXISTS models (
    id          TEXT PRIMARY KEY,
    account_id  TEXT,
    name        TEXT NOT NULL,
    workload    TEXT NOT NULL,
    stage       TEXT NOT NULL,           -- candidate|challenger|champion|archived|rejected
    version     TEXT,
    signed      INTEGER NOT NULL DEFAULT 0,
    approved    INTEGER NOT NULL DEFAULT 0,
    metrics     TEXT,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS audit_log (
    id          TEXT PRIMARY KEY,
    account_id  TEXT,
    created_at  TEXT NOT NULL,
    actor       TEXT,
    action      TEXT NOT NULL,
    target      TEXT,
    detail      TEXT
);
CREATE TABLE IF NOT EXISTS tryops_quota_usage (
    period     TEXT NOT NULL,
    user_hash  TEXT NOT NULL,
    dimension  TEXT NOT NULL,
    plan       TEXT NOT NULL,
    workload   TEXT NOT NULL,
    used       INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (period, user_hash, dimension)
);
CREATE INDEX IF NOT EXISTS idx_accounts_slug ON accounts(slug);
CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email);
CREATE INDEX IF NOT EXISTS idx_user_profiles_name ON user_profiles(display_name);
CREATE INDEX IF NOT EXISTS idx_account_members_subject ON account_members(subject);
CREATE INDEX IF NOT EXISTS idx_account_members_account ON account_members(account_id);
CREATE INDEX IF NOT EXISTS idx_account_audit_account ON account_audit_log(account_id, created_at);
CREATE INDEX IF NOT EXISTS idx_account_invitations_account ON account_invitations(account_id, status);
CREATE INDEX IF NOT EXISTS idx_account_invitations_email ON account_invitations(email, status);
CREATE INDEX IF NOT EXISTS idx_requests_created ON requests(created_at);
CREATE INDEX IF NOT EXISTS idx_requests_kind ON requests(kind);
CREATE INDEX IF NOT EXISTS idx_feedback_request ON feedback(request_id);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


class DbConnection(Protocol):
    def close(self) -> None: ...
    def commit(self) -> None: ...


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> DbConnection:
    postgres_dsn = _postgres_dsn_from_env()
    if postgres_dsn:
        try:
            import psycopg2
        except ImportError as exc:
            raise RuntimeError(
                "TRYOPS_APP_POSTGRES_DSN is configured but psycopg2 is not installed"
            ) from exc
        conn = psycopg2.connect(postgres_dsn)
        with _SCHEMA_LOCK:
            _ensure_schema(conn)
        return conn

    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    with _SCHEMA_LOCK:
        _ensure_schema(conn)
    return conn


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create the schema if absent (idempotent)."""

    conn = connect(db_path)
    try:
        _ensure_schema(conn)
    finally:
        conn.close()


def _postgres_dsn_from_env() -> str | None:
    dsn = os.getenv(POSTGRES_DSN_ENV, "").strip()
    if dsn:
        return dsn
    dsn_file = os.getenv(POSTGRES_DSN_FILE_ENV, "").strip()
    if not dsn_file:
        return None
    try:
        return Path(dsn_file).read_text(encoding="utf-8").strip() or None
    except OSError as exc:
        raise RuntimeError(f"cannot read {POSTGRES_DSN_FILE_ENV}: {dsn_file}") from exc


def _is_postgres(conn: DbConnection) -> bool:
    return conn.__class__.__module__.startswith("psycopg2")


def _ensure_schema(conn: DbConnection) -> None:
    if _is_postgres(conn):
        with conn.cursor() as cur:
            cur.execute(SCHEMA)
        conn.commit()
        _ensure_account_columns(conn)
        _ensure_demo_account(conn)
        _backfill_demo_account(conn)
        _backfill_avatar_images(conn)
        return
    conn.executescript(SCHEMA)  # type: ignore[attr-defined]
    conn.commit()
    _ensure_account_columns(conn)
    _ensure_demo_account(conn)
    _backfill_demo_account(conn)
    _backfill_avatar_images(conn)


def _sql(conn: DbConnection, statement: str) -> str:
    if _is_postgres(conn):
        return statement.replace("?", "%s")
    return statement


def _execute(conn: DbConnection, statement: str, params: tuple[Any, ...] = ()) -> Any:
    if _is_postgres(conn):
        from psycopg2.extras import RealDictCursor
        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(_sql(conn, statement), params)
        return cur
    return conn.execute(statement, params)  # type: ignore[attr-defined]


def _fetchone(conn: DbConnection, statement: str, params: tuple[Any, ...] = ()) -> Any:
    cur = _execute(conn, statement, params)
    try:
        return cur.fetchone()
    finally:
        if _is_postgres(conn):
            cur.close()


def _fetchall(conn: DbConnection, statement: str, params: tuple[Any, ...] = ()) -> list[Any]:
    cur = _execute(conn, statement, params)
    try:
        return cur.fetchall()
    finally:
        if _is_postgres(conn):
            cur.close()


def _row_dict(row: Any) -> dict[str, Any]:
    if row is None:
        return {}
    return dict(row)


def _ensure_account_columns(conn: DbConnection) -> None:
    columns = {
        "accounts": {
            "description": "TEXT",
            "avatar_url": "TEXT",
        },
        "user_profiles": {
            "avatar_url": "TEXT",
        },
        "requests": {
            "account_id": "TEXT",
            "principal_subject": "TEXT",
        },
        "feedback": {"account_id": "TEXT"},
        "jobs": {"account_id": "TEXT"},
        "models": {"account_id": "TEXT"},
        "audit_log": {"account_id": "TEXT"},
    }
    if _is_postgres(conn):
        with conn.cursor() as cur:
            for table, table_columns in columns.items():
                for column, column_type in table_columns.items():
                    cur.execute(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {column} {column_type}")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_user_profiles_name ON user_profiles(display_name)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_account_invitations_account ON account_invitations(account_id, status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_account_invitations_email ON account_invitations(email, status)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_requests_account ON requests(account_id, created_at)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_feedback_account ON feedback(account_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_jobs_account ON jobs(account_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_models_account ON models(account_id)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_account ON audit_log(account_id, created_at)")
        conn.commit()
        return

    for table, table_columns in columns.items():
        existing = {
            str(row["name"])
            for row in conn.execute(f"PRAGMA table_info({table})").fetchall()  # type: ignore[attr-defined]
        }
        for column, column_type in table_columns.items():
            if column not in existing:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_type}")  # type: ignore[attr-defined]
    conn.execute("CREATE INDEX IF NOT EXISTS idx_requests_account ON requests(account_id, created_at)")  # type: ignore[attr-defined]
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_profiles_email ON user_profiles(email)")  # type: ignore[attr-defined]
    conn.execute("CREATE INDEX IF NOT EXISTS idx_user_profiles_name ON user_profiles(display_name)")  # type: ignore[attr-defined]
    conn.execute("CREATE INDEX IF NOT EXISTS idx_account_invitations_account ON account_invitations(account_id, status)")  # type: ignore[attr-defined]
    conn.execute("CREATE INDEX IF NOT EXISTS idx_account_invitations_email ON account_invitations(email, status)")  # type: ignore[attr-defined]
    conn.execute("CREATE INDEX IF NOT EXISTS idx_feedback_account ON feedback(account_id)")  # type: ignore[attr-defined]
    conn.execute("CREATE INDEX IF NOT EXISTS idx_jobs_account ON jobs(account_id)")  # type: ignore[attr-defined]
    conn.execute("CREATE INDEX IF NOT EXISTS idx_models_account ON models(account_id)")  # type: ignore[attr-defined]
    conn.execute("CREATE INDEX IF NOT EXISTS idx_audit_log_account ON audit_log(account_id, created_at)")  # type: ignore[attr-defined]
    conn.commit()


def _ensure_demo_account(conn: DbConnection) -> None:
    created_at = _now()
    _execute(
        conn,
        """INSERT INTO user_profiles (subject, email, username, display_name, avatar_url, status, created_at, updated_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(subject) DO UPDATE SET
             email=excluded.email,
             username=excluded.username,
             display_name=excluded.display_name,
             avatar_url=excluded.avatar_url,
             updated_at=excluded.updated_at,
             last_seen_at=excluded.last_seen_at""",
        (
            DEMO_SUBJECT,
            "demo@tryops.local",
            "demo",
            "Demo Owner",
            _avatar_url("demo@tryops.local", "Demo Owner"),
            "active",
            created_at,
            created_at,
            created_at,
        ),
    )
    _execute(
        conn,
        """INSERT INTO accounts (id, name, slug, avatar_url, plan, status, created_at, created_by_subject)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO NOTHING""",
        (DEMO_ACCOUNT_ID, "Demo Workspace", "demo", _avatar_url("demo@tryops.local", "Demo Workspace"), "free", "active", created_at, DEMO_SUBJECT),
    )
    _execute(
        conn,
        """INSERT INTO account_members
             (id, account_id, subject, email, display_name, role, status, created_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(account_id, subject) DO NOTHING""",
        (
            "member_demo_owner",
            DEMO_ACCOUNT_ID,
            DEMO_SUBJECT,
            "demo@tryops.local",
            "Demo Owner",
            "account_owner",
            "active",
            created_at,
            created_at,
        ),
    )
    conn.commit()


def _backfill_demo_account(conn: DbConnection) -> None:
    for table in ("requests", "feedback", "jobs", "models", "audit_log"):
        _execute(conn, f"UPDATE {table} SET account_id=? WHERE account_id IS NULL", (DEMO_ACCOUNT_ID,))
    conn.commit()


def _backfill_avatar_images(conn: DbConnection) -> None:
    profile_rows = _fetchall(
        conn,
        """SELECT subject, email, display_name
           FROM user_profiles
           WHERE avatar_url IS NULL OR avatar_url=''""",
    )
    for row in profile_rows:
        profile = _row_dict(row)
        _execute(
            conn,
            "UPDATE user_profiles SET avatar_url=? WHERE subject=?",
            (_avatar_url(profile.get("email"), profile.get("display_name") or profile.get("subject")), profile["subject"]),
        )

    account_rows = _fetchall(
        conn,
        """SELECT a.id, a.name, p.email, p.display_name
           FROM accounts a
           LEFT JOIN user_profiles p ON p.subject = a.created_by_subject
           WHERE a.avatar_url IS NULL OR a.avatar_url=''""",
    )
    for row in account_rows:
        account = _row_dict(row)
        _execute(
            conn,
            "UPDATE accounts SET avatar_url=? WHERE id=?",
            (_avatar_url(account.get("email"), account.get("name") or account.get("display_name")), account["id"]),
        )
    conn.commit()


def _stable_id(prefix: str, value: str) -> str:
    return f"{prefix}_{sha256(value.encode('utf-8')).hexdigest()[:16]}"


def _slug(value: str) -> str:
    cleaned = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return cleaned[:48] or "workspace"


def _email(value: object) -> str:
    return str(value or "").strip().lower()


def _role(value: object, *, default: str = "account_member") -> str:
    role = str(value or default).strip()
    if role not in {"account_owner", "account_member", "account_viewer", "platform_admin"}:
        raise ValueError("role must be account_owner, account_member, or account_viewer")
    return "account_owner" if role == "platform_admin" else role


def _avatar_url(email: object = None, label: object = None) -> str:
    normalized_email = _email(email)
    if normalized_email:
        try:
            digest = md5(normalized_email.encode("utf-8"), usedforsecurity=False).hexdigest()
        except TypeError:  # pragma: no cover - older Python compatibility
            digest = md5(normalized_email.encode("utf-8")).hexdigest()
        return f"https://www.gravatar.com/avatar/{digest}?d=mp&s=160"
    seed = str(label or "TryOps").strip() or "TryOps"
    digest = sha256(seed.encode("utf-8")).hexdigest()
    bg = f"#{digest[:6]}"
    fg = "#fffaf2"
    initial_match = re.search(r"[A-Za-z0-9]", seed)
    initial = (initial_match.group(0) if initial_match else "T").upper()
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160">'
        f'<rect width="160" height="160" fill="{bg}"/>'
        f'<text x="80" y="93" text-anchor="middle" font-family="Arial, sans-serif" '
        f'font-size="68" font-weight="700" fill="{fg}">{initial}</text>'
        f"</svg>"
    )
    return f"data:image/svg+xml;utf8,{quote(svg)}"


# ---- requests -------------------------------------------------------------

def insert_request(conn: DbConnection, record: dict[str, Any]) -> str:
    rid = record.get("id") or str(uuid.uuid4())
    _execute(
        conn,
        """INSERT INTO requests (id, created_at, account_id, principal_subject, kind, model_alias, adapter,
            input_summary, output_summary, latency_ms, vram_gb, energy_wh, cost_usd,
            quality, status, user_hash, request_id, trace_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            rid, record.get("created_at") or _now(),
            record.get("account_id") or DEMO_ACCOUNT_ID,
            record.get("principal_subject"),
            record["kind"],
            record.get("model_alias"), record.get("adapter"),
            record.get("input_summary"), record.get("output_summary"),
            record.get("latency_ms"), record.get("vram_gb"), record.get("energy_wh"),
            record.get("cost_usd"), record.get("quality"),
            record.get("status", "completed"), record.get("user_hash"),
            record.get("request_id"), record.get("trace_id"),
        ),
    )
    conn.commit()
    return rid


def get_request(conn: DbConnection, rid: str) -> dict[str, Any] | None:
    row = _fetchone(conn, "SELECT * FROM requests WHERE id=?", (rid,))
    return _row_dict(row) if row else None


def list_requests(
    conn: DbConnection,
    *,
    kind: str | None = None,
    account_id: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if kind:
        clauses.append("kind=?")
        params.append(kind)
    if account_id:
        clauses.append("account_id=?")
        params.append(account_id)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.append(limit)
    rows = _fetchall(conn, f"SELECT * FROM requests {where} ORDER BY created_at DESC LIMIT ?", tuple(params))
    return [_row_dict(r) for r in rows]


# ---- accounts -------------------------------------------------------------

def bootstrap_account(conn: DbConnection, principal: dict[str, Any]) -> dict[str, Any]:
    """Create a user profile and default workspace if the user has no memberships."""

    subject = str(principal.get("subject") or principal.get("key_id") or "").strip()
    if not subject:
        raise ValueError("authenticated principal subject is required")
    now = _now()
    profile = upsert_user_profile(conn, principal, now=now)
    _accept_pending_invitations(conn, profile, now=now)
    accounts = list_accounts_for_subject(conn, subject)
    if accounts:
        _execute(conn, "UPDATE account_members SET last_seen_at=? WHERE subject=?", (now, subject))
        conn.commit()
        return accounts[0]

    return create_account(
        conn,
        principal,
        name=f"{profile['display_name']}'s Workspace" if profile.get("display_name") else "TryOps Workspace",
        description="Personal fitting workspace",
        now=now,
    )


def upsert_user_profile(conn: DbConnection, principal: dict[str, Any], *, now: str | None = None) -> dict[str, Any]:
    subject = str(principal.get("subject") or principal.get("key_id") or "").strip()
    if not subject:
        raise ValueError("authenticated principal subject is required")
    timestamp = now or _now()
    email = _email(principal.get("email")) or None
    username = str(principal.get("username") or "").strip() or (email.split("@", 1)[0] if email else None)
    display_name = str(principal.get("display_name") or username or email or "TryOps User").strip()
    avatar_url = str(principal.get("avatar_url") or "").strip() or _avatar_url(email, display_name)
    _execute(
        conn,
        """INSERT INTO user_profiles (subject, email, username, display_name, avatar_url, status, created_at, updated_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(subject) DO UPDATE SET
             email=excluded.email,
             username=excluded.username,
             display_name=excluded.display_name,
             avatar_url=excluded.avatar_url,
             status='active',
             updated_at=excluded.updated_at,
             last_seen_at=excluded.last_seen_at""",
        (subject, email, username, display_name, avatar_url, "active", timestamp, timestamp, timestamp),
    )
    conn.commit()
    return {
        "subject": subject,
        "email": email,
        "username": username,
        "display_name": display_name,
        "avatar_url": avatar_url,
        "status": "active",
        "created_at": timestamp,
        "updated_at": timestamp,
        "last_seen_at": timestamp,
    }


def create_account(
    conn: DbConnection,
    principal: dict[str, Any],
    *,
    name: str,
    description: str | None = None,
    plan: str = "free",
    now: str | None = None,
) -> dict[str, Any]:
    subject = str(principal.get("subject") or principal.get("key_id") or "").strip()
    if not subject:
        raise ValueError("authenticated principal subject is required")
    timestamp = now or _now()
    profile = upsert_user_profile(conn, principal, now=timestamp)
    account_id = _stable_id("acct", f"{subject}:{name}:{uuid.uuid4()}")
    slug_base = _slug(name or profile.get("display_name") or "workspace")
    slug = f"{slug_base}-{account_id.rsplit('_', 1)[-1][:6]}"
    member_id = _stable_id("member", f"{account_id}:{subject}")

    _execute(
        conn,
        """INSERT INTO accounts (id, name, slug, description, avatar_url, plan, status, created_at, created_by_subject)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO NOTHING""",
        (
            account_id,
            name.strip() or "TryOps Workspace",
            slug,
            description,
            profile.get("avatar_url") or _avatar_url(profile.get("email"), name),
            plan,
            "active",
            timestamp,
            subject,
        ),
    )
    _execute(
        conn,
        """INSERT INTO account_members
             (id, account_id, subject, email, display_name, role, status, created_at, last_seen_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(account_id, subject) DO UPDATE SET
             email=excluded.email,
             display_name=excluded.display_name,
             last_seen_at=excluded.last_seen_at""",
        (
            member_id,
            account_id,
            subject,
            profile.get("email"),
            profile.get("display_name"),
            "account_owner",
            "active",
            timestamp,
            timestamp,
        ),
    )
    _execute(
        conn,
        """INSERT INTO account_audit_log (id, account_id, created_at, actor_subject, action, target, detail)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()),
            account_id,
            timestamp,
            subject,
            "account.bootstrap",
            account_id,
            json.dumps({"role": "account_owner", "provider": principal.get("provider", "oidc")}),
        ),
    )
    conn.commit()
    created = resolve_account_for_subject(conn, subject, account_id)
    if created is None:
        raise RuntimeError("account bootstrap failed")
    return created


def _account_context_from_row(row: Any) -> dict[str, Any]:
    data = _row_dict(row)
    return {
        "account": {
            "id": data["account_id"],
            "name": data["account_name"],
            "slug": data["account_slug"],
            "description": data.get("account_description"),
            "avatar_url": data.get("account_avatar_url"),
            "plan": data["account_plan"],
            "status": data["account_status"],
            "created_at": data["account_created_at"],
        },
        "membership": {
            "id": data["member_id"],
            "account_id": data["account_id"],
            "subject": data["subject"],
            "email": data.get("email"),
            "display_name": data.get("display_name"),
            "avatar_url": data.get("profile_avatar_url"),
            "role": data["role"],
            "status": data["member_status"],
            "created_at": data["member_created_at"],
            "last_seen_at": data.get("last_seen_at"),
        },
    }


def _account_membership_select(where: str) -> str:
    return f"""SELECT
             a.id AS account_id,
             a.name AS account_name,
             a.slug AS account_slug,
             a.description AS account_description,
             a.avatar_url AS account_avatar_url,
             a.plan AS account_plan,
             a.status AS account_status,
             a.created_at AS account_created_at,
             m.id AS member_id,
             m.subject,
             m.email,
             COALESCE(p.display_name, m.display_name) AS display_name,
             p.avatar_url AS profile_avatar_url,
             m.role,
             m.status AS member_status,
             m.created_at AS member_created_at,
             m.last_seen_at
           FROM account_members m
           JOIN accounts a ON a.id = m.account_id
           LEFT JOIN user_profiles p ON p.subject = m.subject
           {where}"""


def get_account_for_subject(conn: DbConnection, subject: str) -> dict[str, Any] | None:
    return resolve_account_for_subject(conn, subject, None)


def resolve_account_for_subject(
    conn: DbConnection,
    subject: str,
    account_id: str | None = None,
) -> dict[str, Any] | None:
    params: tuple[Any, ...]
    if account_id:
        where = """WHERE m.subject=? AND m.account_id=? AND m.status='active' AND a.status='active'
           ORDER BY m.created_at ASC
           LIMIT 1"""
        params = (subject, account_id)
    else:
        where = """WHERE m.subject=? AND m.status='active' AND a.status='active'
           ORDER BY m.created_at ASC
           LIMIT 1"""
        params = (subject,)
    row = _fetchone(
        conn,
        _account_membership_select(where),
        params,
    )
    if not row:
        return None
    return _account_context_from_row(row)


def list_accounts_for_subject(conn: DbConnection, subject: str) -> list[dict[str, Any]]:
    rows = _fetchall(
        conn,
        _account_membership_select(
            """WHERE m.subject=? AND m.status='active' AND a.status='active'
           ORDER BY m.created_at ASC"""
        ),
        (subject,),
    )
    return [_account_context_from_row(row) for row in rows]


def update_account(
    conn: DbConnection,
    account_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
) -> dict[str, Any]:
    current = _fetchone(conn, "SELECT * FROM accounts WHERE id=?", (account_id,))
    if not current:
        raise ValueError("account not found")
    data = _row_dict(current)
    next_name = (name if name is not None else data.get("name") or "").strip() or "TryOps Workspace"
    _execute(
        conn,
        "UPDATE accounts SET name=?, description=? WHERE id=?",
        (next_name, description if description is not None else data.get("description"), account_id),
    )
    conn.commit()
    row = _fetchone(conn, "SELECT * FROM accounts WHERE id=?", (account_id,))
    return _row_dict(row)


def get_account_members(conn: DbConnection, account_id: str) -> list[dict[str, Any]]:
    rows = _fetchall(
        conn,
        """SELECT
             m.id,
             m.account_id,
             m.subject,
             COALESCE(p.email, m.email) AS email,
             COALESCE(p.display_name, m.display_name) AS display_name,
             p.avatar_url AS avatar_url,
             m.role,
             m.status,
             m.created_at,
             m.last_seen_at
           FROM account_members m
           LEFT JOIN user_profiles p ON p.subject = m.subject
           WHERE m.account_id=?
           ORDER BY m.created_at ASC""",
        (account_id,),
    )
    return [_row_dict(row) for row in rows]


def search_user_profiles(conn: DbConnection, query: str, *, limit: int = 12) -> list[dict[str, Any]]:
    q = query.strip().lower()
    if len(q) < 2:
        return []
    like = f"%{q}%"
    rows = _fetchall(
        conn,
        """SELECT subject, email, username, display_name, avatar_url, status, created_at, updated_at, last_seen_at
           FROM user_profiles
           WHERE status='active'
             AND (LOWER(COALESCE(email, '')) LIKE ?
               OR LOWER(COALESCE(username, '')) LIKE ?
               OR LOWER(COALESCE(display_name, '')) LIKE ?)
           ORDER BY last_seen_at DESC
           LIMIT ?""",
        (like, like, like, limit),
    )
    return [_row_dict(row) for row in rows]


def create_account_invitation(
    conn: DbConnection,
    *,
    account_id: str,
    email: str,
    role: str,
    invited_by: str,
) -> dict[str, Any]:
    normalized_email = _email(email)
    if not normalized_email or "@" not in normalized_email:
        raise ValueError("valid email is required")
    invite_role = _role(role)
    now = _now()
    existing = _fetchone(
        conn,
        """SELECT * FROM account_invitations
           WHERE account_id=? AND LOWER(email)=? AND status='pending'
           LIMIT 1""",
        (account_id, normalized_email),
    )
    if existing:
        return _row_dict(existing)
    profile = _fetchone(conn, "SELECT * FROM user_profiles WHERE LOWER(email)=? LIMIT 1", (normalized_email,))
    profile_data = _row_dict(profile) if profile else {}
    invited_subject = profile_data.get("subject")
    if invited_subject:
        active_member = _fetchone(
            conn,
            "SELECT id FROM account_members WHERE account_id=? AND subject=? AND status='active' LIMIT 1",
            (account_id, invited_subject),
        )
        if active_member:
            raise ValueError("user is already an active workspace member")
    invitation_id = _stable_id("invite", f"{account_id}:{normalized_email}:{uuid.uuid4()}")
    _execute(
        conn,
        """INSERT INTO account_invitations
             (id, account_id, email, invited_subject, role, status, invited_by, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (invitation_id, account_id, normalized_email, invited_subject, invite_role, "pending", invited_by, now, now),
    )
    conn.commit()
    if invited_subject:
        _accept_pending_invitations(
            conn,
            {"subject": invited_subject, "email": normalized_email, "display_name": profile_data.get("display_name")},
            now=now,
        )
    row = _fetchone(conn, "SELECT * FROM account_invitations WHERE id=?", (invitation_id,))
    return _row_dict(row)


def list_account_invitations(conn: DbConnection, account_id: str) -> list[dict[str, Any]]:
    rows = _fetchall(
        conn,
        """SELECT * FROM account_invitations
           WHERE account_id=?
           ORDER BY created_at DESC""",
        (account_id,),
    )
    return [_row_dict(row) for row in rows]


def revoke_account_invitation(conn: DbConnection, account_id: str, invitation_id: str, *, actor: str) -> dict[str, Any]:
    now = _now()
    _execute(
        conn,
        """UPDATE account_invitations
           SET status='revoked', revoked_at=?, updated_at=?
           WHERE id=? AND account_id=? AND status='pending'""",
        (now, now, invitation_id, account_id),
    )
    _execute(
        conn,
        """INSERT INTO account_audit_log (id, account_id, created_at, actor_subject, action, target, detail)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (str(uuid.uuid4()), account_id, now, actor, "account.invitation.revoked", invitation_id, json.dumps({})),
    )
    conn.commit()
    row = _fetchone(conn, "SELECT * FROM account_invitations WHERE id=? AND account_id=?", (invitation_id, account_id))
    if not row:
        raise ValueError("invitation not found")
    return _row_dict(row)


def update_account_member(
    conn: DbConnection,
    account_id: str,
    member_id: str,
    *,
    role: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    member = _fetchone(conn, "SELECT * FROM account_members WHERE id=? AND account_id=?", (member_id, account_id))
    if not member:
        raise ValueError("member not found")
    current = _row_dict(member)
    next_role = _role(role or current.get("role"))
    next_status = str(status or current.get("status") or "active").strip()
    if next_status not in {"active", "removed", "disabled"}:
        raise ValueError("status must be active, disabled, or removed")
    if (current.get("role") == "account_owner" and (next_role != "account_owner" or next_status != "active")
            and _active_owner_count(conn, account_id) <= 1):
        raise ValueError("cannot remove or demote the last workspace owner")
    _execute(
        conn,
        "UPDATE account_members SET role=?, status=? WHERE id=? AND account_id=?",
        (next_role, next_status, member_id, account_id),
    )
    conn.commit()
    row = _fetchone(conn, "SELECT * FROM account_members WHERE id=? AND account_id=?", (member_id, account_id))
    return _row_dict(row)


def remove_account_member(conn: DbConnection, account_id: str, member_id: str) -> dict[str, Any]:
    return update_account_member(conn, account_id, member_id, status="removed")


def _active_owner_count(conn: DbConnection, account_id: str) -> int:
    row = _fetchone(
        conn,
        "SELECT COUNT(*) n FROM account_members WHERE account_id=? AND role='account_owner' AND status='active'",
        (account_id,),
    )
    return int(row["n"] or 0)


def _accept_pending_invitations(conn: DbConnection, profile: dict[str, Any], *, now: str | None = None) -> None:
    email = _email(profile.get("email"))
    subject = str(profile.get("subject") or "").strip()
    if not email or not subject:
        return
    timestamp = now or _now()
    rows = _fetchall(
        conn,
        """SELECT * FROM account_invitations
           WHERE LOWER(email)=? AND status='pending'""",
        (email,),
    )
    for row in rows:
        invitation = _row_dict(row)
        account_id = invitation["account_id"]
        role = _role(invitation.get("role"))
        member_id = _stable_id("member", f"{account_id}:{subject}")
        existing_member = _fetchone(
            conn,
            "SELECT * FROM account_members WHERE account_id=? AND subject=? LIMIT 1",
            (account_id, subject),
        )
        existing_member_data = _row_dict(existing_member) if existing_member else {}
        already_active = existing_member_data.get("status") == "active"
        accepted_role = existing_member_data.get("role") if already_active else role
        if existing_member:
            _execute(
                conn,
                """UPDATE account_members
                   SET email=?, display_name=?, role=?, status='active', last_seen_at=?
                   WHERE id=? AND account_id=?""",
                (
                    email,
                    profile.get("display_name"),
                    accepted_role,
                    timestamp,
                    existing_member_data["id"],
                    account_id,
                ),
            )
        else:
            _execute(
                conn,
                """INSERT INTO account_members
                     (id, account_id, subject, email, display_name, role, status, created_at, last_seen_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    member_id,
                    account_id,
                    subject,
                    email,
                    profile.get("display_name"),
                    role,
                    "active",
                    timestamp,
                    timestamp,
                ),
            )
        _execute(
            conn,
            """UPDATE account_invitations
               SET status='accepted', invited_subject=?, accepted_at=?, updated_at=?
               WHERE id=?""",
            (subject, timestamp, timestamp, invitation["id"]),
        )
        _execute(
            conn,
            """INSERT INTO account_audit_log (id, account_id, created_at, actor_subject, action, target, detail)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                account_id,
                timestamp,
                subject,
                "account.invitation.accepted",
                invitation["id"],
                json.dumps({"role": accepted_role, "email": email, "existing_member": already_active}),
            ),
        )
    conn.commit()


def account_dashboard_summary(conn: DbConnection, account_id: str, *, limit: int = 12) -> dict[str, Any]:
    account = _fetchone(conn, "SELECT * FROM accounts WHERE id=?", (account_id,))
    if not account:
        raise ValueError("account not found")
    account_data = _row_dict(account)
    total = _fetchone(conn, "SELECT COUNT(*) n FROM requests WHERE account_id=?", (account_id,))["n"]
    feedback = _fetchone(conn, "SELECT COUNT(*) n, AVG(rating) r FROM feedback WHERE account_id=?", (account_id,))
    recent = list_requests(conn, account_id=account_id, limit=limit)
    models = _fetchall(
        conn,
        "SELECT stage, COUNT(*) n FROM models WHERE account_id=? GROUP BY stage",
        (account_id,),
    )
    return {
        "schema_version": "tryops.account_dashboard.v1",
        "generated_at": _now(),
        "account": account_data,
        "usage": {
            "total_requests": total or 0,
            "llm": _request_aggregate(conn, kind="llm", account_id=account_id),
            "vton": _request_aggregate(conn, kind="vton", account_id=account_id),
            "feedback": {
                "count": feedback["n"] or 0,
                "avg_rating": round(feedback["r"], 3) if feedback["r"] is not None else None,
            },
            "models_by_stage": {row["stage"]: row["n"] for row in models},
        },
        "recent_requests": recent,
        "quota": account_quota_summary(conn, account_id),
        "members_count": len(get_account_members(conn, account_id)),
    }


def account_quota_summary(conn: DbConnection, account_id: str) -> dict[str, Any]:
    from tryops.quota import PLAN_LIMITS, user_hash

    account = _fetchone(conn, "SELECT * FROM accounts WHERE id=?", (account_id,))
    if not account:
        raise ValueError("account not found")
    account_data = _row_dict(account)
    plan = str(account_data.get("plan") or "free")
    account_hash = user_hash(account_id)
    rows = _fetchall(
        conn,
        "SELECT period, dimension, used, workload, updated_at FROM tryops_quota_usage WHERE user_hash=?",
        (account_hash,),
    )
    latest_period = max([row["period"] for row in rows], default=datetime.now(UTC).date().isoformat())
    used_by_dimension = {str(row["dimension"]): int(row["used"] or 0) for row in rows if row["period"] == latest_period}
    dimensions = []
    for dimension, limit in PLAN_LIMITS.get(plan, PLAN_LIMITS["free"]).items():
        used = used_by_dimension.get(dimension, 0)
        dimensions.append(
            {
                "dimension": dimension,
                "used": used,
                "limit": int(limit),
                "remaining": max(0, int(limit) - used),
                "utilization_pct": round((used / int(limit)) * 100, 3) if int(limit) else 0.0,
            }
        )
    total_used = sum(item["used"] for item in dimensions)
    total_limit = sum(item["limit"] for item in dimensions)
    return {
        "schema_version": "tryops.account_quota.v1",
        "generated_at": _now(),
        "account": account_data,
        "period": latest_period,
        "user_hash": account_hash,
        "plan": plan,
        "total_used": total_used,
        "total_limit": total_limit,
        "remaining": max(0, total_limit - total_used),
        "utilization_pct": round((total_used / total_limit) * 100, 3) if total_limit else 0.0,
        "dimensions": dimensions,
    }


# ---- feedback -------------------------------------------------------------

def insert_feedback(conn: DbConnection, record: dict[str, Any]) -> str:
    fid = record.get("id") or str(uuid.uuid4())
    _execute(
        conn,
        "INSERT INTO feedback (id, account_id, request_id, rating, label, comment, created_at) VALUES (?,?,?,?,?,?,?)",
        (fid, record.get("account_id") or DEMO_ACCOUNT_ID, record["request_id"], record.get("rating"), record.get("label"),
         record.get("comment"), _now()),
    )
    conn.commit()
    return fid


# ---- models ---------------------------------------------------------------

def upsert_model(conn: DbConnection, record: dict[str, Any]) -> str:
    mid = record.get("id") or str(uuid.uuid4())
    _execute(
        conn,
        """INSERT INTO models (id, account_id, name, workload, stage, version, signed, approved, metrics, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET stage=excluded.stage, signed=excluded.signed,
             approved=excluded.approved, metrics=excluded.metrics""",
        (mid, record.get("account_id") or DEMO_ACCOUNT_ID, record["name"], record["workload"], record.get("stage", "candidate"),
         record.get("version"), int(record.get("signed", 0)), int(record.get("approved", 0)),
         json.dumps(record.get("metrics", {})), record.get("created_at") or _now()),
    )
    conn.commit()
    return mid


def list_models(conn: DbConnection) -> list[dict[str, Any]]:
    rows = _fetchall(conn, "SELECT * FROM models ORDER BY created_at DESC")
    out = []
    for r in rows:
        d = _row_dict(r)
        d["metrics"] = json.loads(d.get("metrics") or "{}")
        out.append(d)
    return out


# ---- audit ----------------------------------------------------------------

def insert_audit(
    conn: DbConnection,
    *,
    actor: str,
    action: str,
    target: str | None = None,
    detail: dict[str, Any] | None = None,
    account_id: str | None = None,
) -> str:
    aid = str(uuid.uuid4())
    _execute(
        conn,
        "INSERT INTO audit_log (id, account_id, created_at, actor, action, target, detail) VALUES (?,?,?,?,?,?,?)",
        (aid, account_id or DEMO_ACCOUNT_ID, _now(), actor, action, target, json.dumps(detail or {})),
    )
    conn.commit()
    return aid


def list_audit(conn: DbConnection, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = _fetchall(conn, "SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,))
    return [_row_dict(r) for r in rows]


# ---- dashboard rollup -----------------------------------------------------

def dashboard_summary(conn: DbConnection) -> dict[str, Any]:
    """Aggregate the live operational picture for the in-app dashboard."""

    def agg(kind: str) -> dict[str, Any]:
        return _request_aggregate(conn, kind=kind)

    total = _fetchone(conn, "SELECT COUNT(*) n FROM requests")["n"]
    fb = _fetchone(conn, "SELECT COUNT(*) n, AVG(rating) r FROM feedback")
    models = _fetchall(
        conn,
        "SELECT stage, COUNT(*) n FROM models GROUP BY stage"
    )
    return {
        "schema_version": "tryops.dashboard.v1",
        "generated_at": _now(),
        "total_requests": total or 0,
        "llm": agg("llm"),
        "vton": agg("vton"),
        "feedback": {"count": fb["n"] or 0, "avg_rating": round(fb["r"], 3) if fb["r"] is not None else None},
        "models_by_stage": {r["stage"]: r["n"] for r in models},
    }


def _request_aggregate(conn: DbConnection, *, kind: str, account_id: str | None = None) -> dict[str, Any]:
    if account_id:
        row = _fetchone(
            conn,
            """SELECT COUNT(*) n, AVG(latency_ms) lat, AVG(energy_wh) e,
                      AVG(cost_usd) c, AVG(quality) q
               FROM requests WHERE kind=? AND account_id=?""",
            (kind, account_id),
        )
    else:
        row = _fetchone(
            conn,
            """SELECT COUNT(*) n, AVG(latency_ms) lat, AVG(energy_wh) e,
                      AVG(cost_usd) c, AVG(quality) q
               FROM requests WHERE kind=?""",
            (kind,),
        )
    return {
        "requests": row["n"] or 0,
        "avg_latency_ms": round(row["lat"], 3) if row["lat"] is not None else None,
        "avg_energy_wh": round(row["e"], 9) if row["e"] is not None else None,
        "avg_cost_usd": round(row["c"], 9) if row["c"] is not None else None,
        "avg_quality": round(row["q"], 4) if row["q"] is not None else None,
    }
