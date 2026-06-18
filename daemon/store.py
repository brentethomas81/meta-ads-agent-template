"""Persistent learning store (SQLite) — the spine of the recursive-learning loop.

Lives on the Fly /data volume so it survives restarts and redeploys. This is
what the bot writes to automatically (every call + every approval) and reads
back for context. The markdown in ../learning stays the human-curated mirror;
this DB is the machine record.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from config import DATA_DIR, DB_PATH


def _conn() -> sqlite3.Connection:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    c = _conn()
    c.executescript(
        """
        CREATE TABLE IF NOT EXISTS decisions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            brand TEXT,
            scope TEXT,            -- campaign / ad set name
            call TEXT,             -- SCALE / HOLD / WATCH / PAUSE / SETUP / BRIEFING / NO-DATA
            confidence TEXT,       -- HIGH / MEDIUM / JUDGMENT
            metrics_json TEXT,     -- snapshot of metrics behind the call
            diagnosis TEXT,
            action_taken TEXT,
            predicted TEXT,
            outcome TEXT,          -- filled later when the result is known
            source TEXT            -- 'briefing' or 'chat'
        );
        CREATE TABLE IF NOT EXISTS approvals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            action TEXT,           -- e.g. scale_ad_set_budget
            args_json TEXT,
            status TEXT,           -- pending / approved / passed / executed / error
            slack_user TEXT,
            result_json TEXT
        );
        CREATE TABLE IF NOT EXISTS kv (
            key TEXT PRIMARY KEY,
            value TEXT
        );
        """
    )
    c.commit()
    c.close()


def set_kv(key: str, value: str) -> None:
    c = _conn()
    c.execute("INSERT INTO kv (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
              (key, value))
    c.commit()
    c.close()


def get_kv(key: str, default=None):
    c = _conn()
    row = c.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    c.close()
    return row["value"] if row else default


def log_decision(**kw) -> int:
    c = _conn()
    cur = c.execute(
        "INSERT INTO decisions "
        "(ts,brand,scope,call,confidence,metrics_json,diagnosis,action_taken,predicted,outcome,source) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            datetime.now(timezone.utc).isoformat(),
            kw.get("brand"), kw.get("scope"), kw.get("call"), kw.get("confidence"),
            json.dumps(kw.get("metrics", {})), kw.get("diagnosis"), kw.get("action_taken"),
            kw.get("predicted"), kw.get("outcome"), kw.get("source", "chat"),
        ),
    )
    c.commit()
    rid = cur.lastrowid
    c.close()
    return rid


def recent_decisions(brand: str | None = None, limit: int = 12) -> list[dict]:
    c = _conn()
    if brand:
        rows = c.execute(
            "SELECT * FROM decisions WHERE brand=? ORDER BY id DESC LIMIT ?", (brand, limit)
        ).fetchall()
    else:
        rows = c.execute("SELECT * FROM decisions ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
    c.close()
    return [dict(r) for r in rows]


def create_approval(action: str, args: dict, slack_user: str | None) -> int:
    c = _conn()
    cur = c.execute(
        "INSERT INTO approvals (ts,action,args_json,status,slack_user) VALUES (?,?,?,?,?)",
        (datetime.now(timezone.utc).isoformat(), action, json.dumps(args), "pending", slack_user),
    )
    c.commit()
    rid = cur.lastrowid
    c.close()
    return rid


def get_approval(aid: int) -> dict | None:
    c = _conn()
    row = c.execute("SELECT * FROM approvals WHERE id=?", (aid,)).fetchone()
    c.close()
    return dict(row) if row else None


def update_approval(aid: int, status: str, result=None) -> None:
    c = _conn()
    c.execute(
        "UPDATE approvals SET status=?, result_json=? WHERE id=?",
        (status, json.dumps(result) if result is not None else None, aid),
    )
    c.commit()
    c.close()
