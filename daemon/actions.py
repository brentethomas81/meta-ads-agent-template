"""Action layer. The bot DOES things (pull data, scale, pause, activate) by
importing the Meta MCP tool functions directly from ../mcp/server.py — the same
functions, with the same guardrails baked in (paused-by-default, +/-25% scale
cap, $50 / 3-day minimum before a pause). Importing server.py initialises the
Meta API from environment variables (Fly secrets in production).

No money action runs without an explicit Slack button approval (see app.py).
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make ../mcp importable, then import the server module (initialises Meta API).
sys.path.insert(0, str(Path(__file__).parent.parent / "mcp"))
import server as meta  # noqa: E402


# --- Read-only tools: safe to call directly, no approval needed -------------
def list_campaigns(**kw):
    return meta.list_campaigns(**kw)


def list_audiences(**kw):
    return meta.list_audiences(**kw)


def campaign_insights(**kw):
    return meta.get_campaign_insights(**kw)


def ad_set_insights(**kw):
    return meta.get_ad_set_insights(**kw)


# --- Money / spend tools: gated behind Slack approval -----------------------
MONEY_ACTIONS = {
    "activate_campaign": meta.activate_campaign,
    "pause_ad_set": meta.pause_ad_set,
    "scale_ad_set_budget": meta.scale_ad_set_budget,
}


def _as_list(res):
    if isinstance(res, dict):
        if res.get("error"):
            return []
        return res.get("result", [])
    return res if isinstance(res, list) else []


def active_campaigns(ad_account_id=None) -> list[dict]:
    """Campaigns currently spending. Used to gate the daily briefing."""
    res = meta.list_campaigns(ad_account_id=ad_account_id, status_filter="ACTIVE", limit=50)
    return _as_list(res)


def execute_money_action(action: str, args: dict):
    fn = MONEY_ACTIONS.get(action)
    if not fn:
        return {"error": "UnknownAction", "message": action}
    return fn(**args)
