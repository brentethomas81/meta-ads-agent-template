"""Server-side ad-click logger + redirect.

Why this exists: the Instagram in-app browser wipes Meta's click id before
checkout (buyers detour through login and check out from "/"), so ad sales
arrive in Stripe without proof. This module gives every ad click a paper
trail WE control:

    ad -> https://<this app>/c/stan?fbclid=... -> logged -> 302 to the
    landing page with the original params PLUS &mcid=<unique click id>

Every click is stored in SQLite (on the Fly /data volume) with its timestamp,
click id, and a unique mcid. If the buyer checks out from the landing page,
eventSourceUrl carries the mcid -> perfect per-click match (CONFIRMED).
If they detour through login, we still know exactly WHEN real ad clicks
happened, so a purchase minutes after a logged click is click-matched
evidence, far stronger than pixel-age alone.

Zero external deps (stdlib http.server); runs as a daemon thread inside the
bot process. Read-only GETs, no cookies set, no PII stored (IP is hashed).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qsl, urlencode

from config import DB_PATH

# slug -> landing page. Add entries per campaign; keep slugs short.
TARGETS = {
    "stan": "https://YOUR-LANDING-PAGE.example.com/offer",
}

_FALLBACK = "https://YOUR-SITE.example.com/"


def _conn() -> sqlite3.Connection:
    c = sqlite3.connect(DB_PATH, timeout=10)
    c.execute(
        """CREATE TABLE IF NOT EXISTS ad_clicks (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               ts INTEGER NOT NULL,
               slug TEXT NOT NULL,
               mcid TEXT NOT NULL UNIQUE,
               fbclid TEXT,
               ua TEXT,
               ip_hash TEXT,
               query TEXT
           )"""
    )
    return c


def log_click(slug: str, params: dict, ua: str, ip: str) -> str:
    """Store one click; returns the unique mcid to tag the landing URL with."""
    mcid = uuid.uuid4().hex[:12]
    c = _conn()
    with c:
        c.execute(
            "INSERT INTO ad_clicks (ts, slug, mcid, fbclid, ua, ip_hash, query) VALUES (?,?,?,?,?,?,?)",
            (
                int(time.time()),
                slug,
                mcid,
                (params.get("fbclid") or "")[:256],
                (ua or "")[:256],
                hashlib.sha256((ip or "").encode()).hexdigest()[:16],
                json.dumps(params)[:1000],
            ),
        )
    c.close()
    return mcid


def click_for_mcid(mcid: str) -> dict | None:
    c = _conn()
    row = c.execute(
        "SELECT ts, slug, fbclid FROM ad_clicks WHERE mcid = ?", (mcid,)
    ).fetchone()
    c.close()
    return {"ts": row[0], "slug": row[1], "fbclid": row[2]} if row else None


# Crawlers hammer ad-destination URLs (Meta's own facebookexternalhit re-checks
# the redirect constantly — observed 1,023 crawler hits vs ~57 humans on day 1).
# All stats exclude them; raw rows are kept for audit.
_BOT_UA_SQL = ("(ua IS NULL OR (ua NOT LIKE '%facebookexternalhit%' AND ua NOT LIKE '%bot%' "
               "AND ua NOT LIKE '%crawler%' AND ua NOT LIKE '%spider%' AND ua NOT LIKE '%preview%' "
               "AND ua NOT LIKE '%curl%' AND ua NOT LIKE '%python%'))")


def clicks_near(ts: int, before_min: int = 45) -> int:
    """How many logged HUMAN ad clicks happened in the window before `ts`?
    Used to click-match purchases that lost their id at the login detour."""
    c = _conn()
    n = c.execute(
        f"SELECT COUNT(*) FROM ad_clicks WHERE ts BETWEEN ? AND ? AND {_BOT_UA_SQL}",
        (ts - before_min * 60, ts),
    ).fetchone()[0]
    c.close()
    return int(n)


def click_count(days: int = 7) -> int:
    """Human ad clicks in the window (crawlers excluded)."""
    c = _conn()
    n = c.execute(
        f"SELECT COUNT(*) FROM ad_clicks WHERE ts >= ? AND {_BOT_UA_SQL}",
        (int(time.time()) - days * 86400,),
    ).fetchone()[0]
    c.close()
    return int(n)


class _Handler(BaseHTTPRequestHandler):
    server_version = "AdClickLog/1.0"

    def log_message(self, *a):  # silence default stderr access log
        pass

    def do_GET(self):  # noqa: N802
        parsed = urlparse(self.path)
        parts = [p for p in parsed.path.split("/") if p]
        # Health checks (Lucille/Medic pattern: cheap, no side effects beyond a
        # heartbeat row). Fly probes /health; a failing check restarts the
        # machine and BLOCKS a bad deploy from replacing a healthy one.
        if not parts or parts[0] == "health":
            try:
                c = _conn()
                c.execute("SELECT COUNT(*) FROM ad_clicks").fetchone()
                c.close()
                self._respond(200, "ok")
            except Exception as e:  # noqa: BLE001
                self._respond(500, f"unhealthy: {type(e).__name__}")
            return
        if parts[0] == "c" and len(parts) == 2 and parts[1] in TARGETS:
            slug = parts[1]
            params = dict(parse_qsl(parsed.query))
            ip = self.headers.get("Fly-Client-IP") or self.client_address[0]
            try:
                mcid = log_click(slug, params, self.headers.get("User-Agent", ""), ip)
            except Exception:  # noqa: BLE001 — never break the buyer's journey
                mcid = ""
            out = dict(params)
            if mcid:
                out["mcid"] = mcid
            dest = TARGETS[slug] + ("?" + urlencode(out) if out else "")
            self.send_response(302)
            self.send_header("Location", dest)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            return
        self._respond(404, "not found")

    def _respond(self, code: int, body: str):
        data = body.encode()
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def start_http(port: int = 8080) -> None:
    """Start the redirect server as a daemon thread (called from app.main)."""
    srv = ThreadingHTTPServer(("0.0.0.0", port), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True, name="clicklog-http").start()
