"""SQLite persistence layer. Zero-dependency (stdlib sqlite3).
Swap for Supabase/Postgres in v0.2 — the API surface here is intentionally tiny.
"""
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path

DB_PATH = Path(os.environ.get("CLAUSE_DB", Path(__file__).parent.parent / "clause.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
  id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS prds (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, content TEXT NOT NULL,
  version INTEGER NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS clauses (
  id TEXT PRIMARY KEY, prd_id TEXT NOT NULL, position INTEGER NOT NULL,
  text TEXT NOT NULL, category TEXT NOT NULL,
  testability TEXT, lint_reason TEXT, rewrite TEXT
);
CREATE TABLE IF NOT EXISTS eval_cases (
  id TEXT PRIMARY KEY, clause_id TEXT NOT NULL, input TEXT NOT NULL,
  kind TEXT NOT NULL, checker_type TEXT NOT NULL, checker_config TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL, prd_id TEXT NOT NULL,
  target_kind TEXT NOT NULL, status TEXT NOT NULL, created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS results (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL, eval_case_id TEXT NOT NULL,
  clause_id TEXT NOT NULL, output TEXT, verdict TEXT, reason TEXT, latency_ms INTEGER
);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def new_id() -> str:
    return uuid.uuid4().hex[:12]


def now() -> float:
    return time.time()


def rows_to_dicts(rows) -> list[dict]:
    return [dict(r) for r in rows]


# ---- convenience queries used by main.py ----

def insert(conn, table: str, data: dict):
    keys = ",".join(data)
    marks = ",".join("?" * len(data))
    conn.execute(f"INSERT INTO {table} ({keys}) VALUES ({marks})", list(data.values()))
    conn.commit()


def latest_prd(conn, project_id: str):
    r = conn.execute(
        "SELECT * FROM prds WHERE project_id=? ORDER BY version DESC LIMIT 1", (project_id,)
    ).fetchone()
    return dict(r) if r else None


def clauses_for_prd(conn, prd_id: str) -> list[dict]:
    return rows_to_dicts(
        conn.execute("SELECT * FROM clauses WHERE prd_id=? ORDER BY position", (prd_id,))
    )


def cases_for_clause(conn, clause_id: str) -> list[dict]:
    out = rows_to_dicts(
        conn.execute("SELECT * FROM eval_cases WHERE clause_id=?", (clause_id,))
    )
    for c in out:
        c["checker_config"] = json.loads(c["checker_config"])
    return out
