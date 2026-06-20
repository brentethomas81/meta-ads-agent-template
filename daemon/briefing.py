"""Daily briefing — the ONE scheduled call/day, and only when a campaign is
ACTIVE. No active campaign anywhere => return early, make ZERO LLM calls => $0.
"""
from __future__ import annotations

import json

import actions
import brain
import config
import store
import stripe_data
from brands import BRANDS

# Clean, no-jargon morning report for a non-technical operator on a phone.
BRIEF_PROMPT = (
    "Write this brand's MORNING REPORT for a NON-TECHNICAL operator reading on a phone. "
    "Plain English, ZERO jargon: say 'cost per subscriber' (not CAC), 'ad clicks' (not CTR / link clicks), "
    "'started checkout but didn't buy' (not abandonment rate). Under ~90 words. "
    "Pull every number from the LIVE DATA; if one isn't there, write '—'. "
    "Output EXACTLY this structure, nothing before or after:\n"
    "☀️ *<Brand> — Morning Report*\n"
    "💸 Spent: $<total so far>\n"
    "✅ New subscribers from ads: <n>\n"
    "🎯 Cost per subscriber: $<x, or '—' if no sales yet>\n"
    "👆 Ad clicks: <n>\n"
    "🛒 Checkout: <started> started → <bought> bought\n"
    "📌 The call: <ONE plain sentence — keep running / watch / a specific next step>"
)


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
        live = actions.live_snapshot(b["ad_account_id"])
        try:
            sf = stripe_data.funnel_snapshot(days=14)
            if sf:
                live = live + "\n" + sf
        except Exception:  # noqa: BLE001
            pass
        brand_dir = config.BRAND_DIRS.get(b["id"], config.REPO)
        answer = brain.ask(
            BRIEF_PROMPT,
            brand_name=b["name"],
            brand_dir=brand_dir,
            live_data=live,
            max_tokens=500,
        )
        sections.append(answer)
        store.log_decision(
            brand=b["name"], scope="daily_briefing", call="BRIEFING", confidence="-",
            metrics={}, diagnosis="auto daily briefing", action_taken="posted to Slack",
            predicted="", source="briefing",
        )

    post("\n\n".join(sections))
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
