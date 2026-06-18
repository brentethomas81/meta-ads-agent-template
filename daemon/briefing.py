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


def run_learning_review(post=None) -> str:
    """Close the learning loop: grade past decisions whose outcome is now known,
    record the outcome, and promote durable patterns into lessons. Cheap and
    bounded — only touches graded decisions ≥3 days old with no outcome yet."""
    pend = store.pending_decisions(min_age_days=3, limit=12)
    if not pend:
        return "Learning review: nothing ready to grade."
    graded = 0
    new_lessons = 0
    for d in pend:
        brand = next((b for b in BRANDS if b.get("name") == d.get("brand")), None)
        live = {}
        if brand and brand.get("ad_account_id"):
            for c in actions.active_campaigns(brand["ad_account_id"]):
                live[c.get("name", c.get("id"))] = actions.campaign_insights(
                    campaign_id=c["id"], date_preset="maximum"
                )
        verdict = brain.assess_outcome(d, json.dumps(live, indent=2)[:6000])
        if not verdict:
            continue
        store.record_outcome(d["id"], str(verdict.get("outcome", ""))[:500])
        graded += 1
        lesson = verdict.get("lesson")
        if lesson and str(lesson).strip().lower() not in ("null", "none", ""):
            store.add_lesson(d.get("brand"), str(lesson)[:300], evidence=f"decision #{d['id']}")
            new_lessons += 1
    summary = f"Learning review: graded {graded}, promoted {new_lessons} lesson(s)."
    if post and new_lessons:
        post("🧠 *Learning update* — " + summary)
    return summary
