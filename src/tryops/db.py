"""TryOps Console data layer (Production App, Phase P1).

A real persistence layer for the end-user product: every LLM/VTON request,
feedback rating, async job, registered model, and admin action is stored in a
relational database. SQLite is the zero-config runnable default (dev/demo); the
same SQL is Postgres-compatible for the enterprise compose profile. The rest of
the app talks to this repository API, never to raw SQL.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_DB_PATH = Path("artifacts/app/tryops.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS requests (
    id            TEXT PRIMARY KEY,
    created_at    TEXT NOT NULL,
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
    request_id  TEXT NOT NULL,
    rating      INTEGER,
    label       TEXT,
    comment     TEXT,
    created_at  TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    kind        TEXT NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    payload     TEXT,
    result_path TEXT
);
CREATE TABLE IF NOT EXISTS models (
    id          TEXT PRIMARY KEY,
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
    created_at  TEXT NOT NULL,
    actor       TEXT,
    action      TEXT NOT NULL,
    target      TEXT,
    detail      TEXT
);
CREATE INDEX IF NOT EXISTS idx_requests_created ON requests(created_at);
CREATE INDEX IF NOT EXISTS idx_requests_kind ON requests(kind);
CREATE INDEX IF NOT EXISTS idx_feedback_request ON feedback(request_id);
"""


def _now() -> str:
    return datetime.now(UTC).isoformat()


def connect(db_path: str | Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    return conn


def init_db(db_path: str | Path = DEFAULT_DB_PATH) -> None:
    """Create the schema if absent (idempotent)."""

    conn = connect(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


# ---- requests -------------------------------------------------------------

def insert_request(conn: sqlite3.Connection, record: dict[str, Any]) -> str:
    rid = record.get("id") or str(uuid.uuid4())
    conn.execute(
        """INSERT INTO requests (id, created_at, kind, model_alias, adapter,
            input_summary, output_summary, latency_ms, vram_gb, energy_wh, cost_usd,
            quality, status, user_hash, request_id, trace_id)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            rid, record.get("created_at") or _now(), record["kind"],
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


def get_request(conn: sqlite3.Connection, rid: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM requests WHERE id=?", (rid,)).fetchone()
    return dict(row) if row else None


def list_requests(conn: sqlite3.Connection, *, kind: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    if kind:
        rows = conn.execute(
            "SELECT * FROM requests WHERE kind=? ORDER BY created_at DESC LIMIT ?", (kind, limit)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM requests ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


# ---- feedback -------------------------------------------------------------

def insert_feedback(conn: sqlite3.Connection, record: dict[str, Any]) -> str:
    fid = record.get("id") or str(uuid.uuid4())
    conn.execute(
        "INSERT INTO feedback (id, request_id, rating, label, comment, created_at) VALUES (?,?,?,?,?,?)",
        (fid, record["request_id"], record.get("rating"), record.get("label"),
         record.get("comment"), _now()),
    )
    conn.commit()
    return fid


# ---- models ---------------------------------------------------------------

def upsert_model(conn: sqlite3.Connection, record: dict[str, Any]) -> str:
    mid = record.get("id") or str(uuid.uuid4())
    conn.execute(
        """INSERT INTO models (id, name, workload, stage, version, signed, approved, metrics, created_at)
           VALUES (?,?,?,?,?,?,?,?,?)
           ON CONFLICT(id) DO UPDATE SET stage=excluded.stage, signed=excluded.signed,
             approved=excluded.approved, metrics=excluded.metrics""",
        (mid, record["name"], record["workload"], record.get("stage", "candidate"),
         record.get("version"), int(record.get("signed", 0)), int(record.get("approved", 0)),
         json.dumps(record.get("metrics", {})), record.get("created_at") or _now()),
    )
    conn.commit()
    return mid


def list_models(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM models ORDER BY created_at DESC").fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["metrics"] = json.loads(d.get("metrics") or "{}")
        out.append(d)
    return out


# ---- audit ----------------------------------------------------------------

def insert_audit(conn: sqlite3.Connection, *, actor: str, action: str,
                 target: str | None = None, detail: dict[str, Any] | None = None) -> str:
    aid = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO audit_log (id, created_at, actor, action, target, detail) VALUES (?,?,?,?,?,?)",
        (aid, _now(), actor, action, target, json.dumps(detail or {})),
    )
    conn.commit()
    return aid


def list_audit(conn: sqlite3.Connection, *, limit: int = 50) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM audit_log ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
    return [dict(r) for r in rows]


# ---- dashboard rollup -----------------------------------------------------

def dashboard_summary(conn: sqlite3.Connection) -> dict[str, Any]:
    """Aggregate the live operational picture for the in-app dashboard."""

    def agg(kind: str) -> dict[str, Any]:
        row = conn.execute(
            """SELECT COUNT(*) n, AVG(latency_ms) lat, AVG(energy_wh) e,
                      AVG(cost_usd) c, AVG(quality) q
               FROM requests WHERE kind=?""", (kind,)
        ).fetchone()
        return {
            "requests": row["n"] or 0,
            "avg_latency_ms": round(row["lat"], 3) if row["lat"] is not None else None,
            "avg_energy_wh": round(row["e"], 9) if row["e"] is not None else None,
            "avg_cost_usd": round(row["c"], 9) if row["c"] is not None else None,
            "avg_quality": round(row["q"], 4) if row["q"] is not None else None,
        }

    total = conn.execute("SELECT COUNT(*) n FROM requests").fetchone()["n"]
    fb = conn.execute("SELECT COUNT(*) n, AVG(rating) r FROM feedback").fetchone()
    models = conn.execute(
        "SELECT stage, COUNT(*) n FROM models GROUP BY stage"
    ).fetchall()
    return {
        "schema_version": "tryops.dashboard.v1",
        "generated_at": _now(),
        "total_requests": total or 0,
        "llm": agg("llm"),
        "vton": agg("vton"),
        "feedback": {"count": fb["n"] or 0, "avg_rating": round(fb["r"], 3) if fb["r"] is not None else None},
        "models_by_stage": {r["stage"]: r["n"] for r in models},
    }
