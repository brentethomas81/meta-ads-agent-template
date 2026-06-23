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


# --- Write tools: EVERY one is gated behind a Slack Approve/Pass tap ---------
# Spend actions (extra-sensitive — they move live budget).
MONEY_ACTIONS = {
    "activate_campaign": meta.activate_campaign,
    "pause_ad_set": meta.pause_ad_set,
    "scale_ad_set_budget": meta.scale_ad_set_budget,
}
# Build / structural actions (change the account; campaigns & ad sets build PAUSED).
BUILD_ACTIONS = {
    "create_campaign": meta.create_campaign,
    "create_ad_set": meta.create_ad_set,
    "create_ad": meta.create_ad,
    "create_ad_creative": meta.create_ad_creative,
    "upload_video_creative": meta.upload_video_creative,
    "upload_custom_audience": meta.upload_custom_audience,
    "create_lookalike_audience": meta.create_lookalike_audience,
}
# Everything the agent may PROPOSE for one-tap approval.
WRITE_ACTIONS = {**MONEY_ACTIONS, **BUILD_ACTIONS}


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


def all_campaigns(ad_account_id=None) -> list[dict]:
    """Every campaign on the account regardless of status (incl. PAUSED)."""
    res = meta.list_campaigns(ad_account_id=ad_account_id, limit=50)
    return _as_list(res)


def _camp_metrics(cid, preset):
    """Return {spend, clicks, purchases} for a campaign over a date preset, or {}."""
    try:
        ins = campaign_insights(campaign_id=cid, date_preset=preset)
        row = ins[0] if isinstance(ins, list) and ins else (ins if isinstance(ins, dict) else {})
        if not row or row.get("error"):
            return {}
        acts = row.get("actions") or []

        def _find(*subs):
            for a in acts:
                if any(s in str(a.get("action_type", "")) for s in subs):
                    return a.get("value")
            return None

        return {"spend": row.get("spend"), "clicks": row.get("clicks"),
                "purchases": _find("purchase"), "subscribes": _find("subscribe"),
                "checkouts": _find("initiate_checkout")}
    except Exception:  # noqa: BLE001
        return {}


def _camp_segment(c, include_empty=False):
    """One human-readable line of LIFETIME (+today) metrics for a campaign, or
    None if it has no data and we're not forcing it in."""
    cid = str(c.get("id"))
    life = _camp_metrics(cid, "maximum")
    today = _camp_metrics(cid, "today")
    seg = f"- {c.get('name')} [{cid}] — {c.get('effective_status') or c.get('status')}"
    has_data = False

    def _conv(m):
        # the meaningful conversion = subscribes (current optimization) else purchases
        for k in ("subscribes", "purchases"):
            v = m.get(k)
            if v not in (None, ""):
                try:
                    return float(v), k
                except (TypeError, ValueError):
                    pass
        return 0.0, "subscribes"

    if life:
        spend = life.get("spend")
        n, label = _conv(life)
        parts = [f"spend ${spend}"] if spend is not None else []
        parts.append(f"{int(n)} {label}")
        if n > 0 and spend:
            parts.append(f"cost-per-{label[:-1]} ${float(spend) / n:.2f}")
        ck = life.get("checkouts")
        if ck not in (None, ""):
            parts.append(f"checkout {int(float(ck))} started → {int(n)} converted")
        if life.get("clicks") is not None:
            parts.append(f"{life.get('clicks')} clicks")
        seg += " | LIFETIME: " + ", ".join(parts)
        if spend is not None:
            try:
                has_data = float(spend) > 0
            except (TypeError, ValueError):
                has_data = False
    # TODAY (so the agent can answer 'just today' without borrowing lifetime numbers)
    if today and today.get("spend") is not None:
        tn, tlabel = _conv(today)
        tparts = [f"${today.get('spend')} spent"]
        if today.get("clicks") is not None:
            tparts.append(f"{today.get('clicks')} clicks")
        tparts.append(f"{int(tn)} {tlabel}")
        tck = today.get("checkouts")
        if tck not in (None, ""):
            tparts.append(f"{int(float(tck))} checkouts started")
        seg += " | TODAY ONLY: " + ", ".join(tparts)
    if not has_data and not include_empty:
        return None
    return seg


def live_snapshot(ad_account_id=None) -> str:
    """LIVE snapshot for the agent — LIFETIME totals first (so a fresh-day 'today'
    near zero never masks real cumulative spend) plus today-so-far for momentum.

    If nothing is ACTIVE right now, we still surface the LIFETIME history of any
    PAUSED campaign that has spent money, so 'pull the metrics' on a paused
    campaign returns its real numbers instead of 'nothing is running'."""
    try:
        camps = active_campaigns(ad_account_id)
    except Exception as e:  # noqa: BLE001
        return f"LIVE STATUS: unavailable ({str(e)[:120]})"
    if camps:
        lines = ["LIVE STATUS — ACTIVELY SPENDING NOW (figures are campaign LIFETIME unless marked 'today'):"]
        for c in camps:
            lines.append(_camp_segment(c, include_empty=True))
        return "\n".join(lines)
    # Nothing active — fall back to lifetime history of paused campaigns.
    try:
        history = [s for s in (_camp_segment(c) for c in all_campaigns(ad_account_id)) if s]
    except Exception:  # noqa: BLE001
        history = []
    if not history:
        return "LIVE STATUS: No campaign is spending right now, and no lifetime spend on record yet."
    return ("LIVE STATUS: No campaign is ACTIVELY spending right now (all PAUSED). "
            "Lifetime history of paused campaigns below — these numbers are real, just not live:\n"
            + "\n".join(history))


def execute_action(action: str, args: dict):
    """Run any approval-gated write action. Server-side guardrails still apply
    (paused-by-default, +/-25% scale cap, pause minimums)."""
    fn = WRITE_ACTIONS.get(action)
    if not fn:
        return {"error": "UnknownAction", "message": action}
    try:
        return fn(**(args or {}))
    except TypeError as e:
        return {"error": "BadArgs", "message": str(e)}


# Backwards-compatible alias.
def execute_money_action(action: str, args: dict):
    return execute_action(action, args)
