"""Daily briefing — the ONE scheduled call/day, and only when a campaign is
ACTIVE. No active campaign anywhere => return early, make ZERO LLM calls => $0.
"""
from __future__ import annotations

import json

import actions
import brain
import config
import store
from brands import BRANDS


def _active_brands():
    """[(brand, [active campaigns]), ...] for brands that are live AND spending."""
    out = []
    for b in BRANDS:
        if not b.get("active") or not b.get("ad_account_id"):
            continue
        camps = actions.active_campaigns(b["ad_account_id"])
        if camps:
            out.append((b, camps))
    return out


def run_daily_briefing(post) -> str:
    """post: callable(text) -> sends to Slack. Returns a short status string."""
    active = _active_brands()
    if not active:
        # Nothing running -> skip entirely. This is the $0 path.
        return "No active campaigns — briefing skipped (0 LLM calls, $0)."

    sections = []
    for b, camps in active:
        data = {}
        for c in camps:
            data[c.get("name", c.get("id"))] = actions.campaign_insights(
                campaign_id=c["id"], date_preset="last_7d"
            )
        brand_dir = config.BRAND_DIRS.get(b["id"], config.REPO)
        answer = brain.ask(
            "Produce today's morning briefing for this brand. Follow AGENT_INSTRUCTIONS exactly: "
            "apply the 4-bucket framework and the 5 Questions, give the top recommendations with "
            "confidence tags and a one-line 'why this matters' each. Be concise. If nothing needs "
            "action, say so in one line.",
            brand_name=b["name"],
            brand_dir=brand_dir,
            live_data=json.dumps(data, indent=2)[:12000],
            max_tokens=1800,
        )
        sections.append(f"*{b['name']}*\n{answer}")
        store.log_decision(
            brand=b["name"], scope="daily_briefing", call="BRIEFING", confidence="-",
            metrics={}, diagnosis="auto daily briefing", action_taken="posted to Slack",
            predicted="", source="briefing",
        )

    post("🗞️ *Daily Meta Ads Briefing*\n\n" + "\n\n".join(sections))
    return f"Briefing posted for {len(active)} active brand(s)."
