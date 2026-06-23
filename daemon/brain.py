"""The agent's brain: assembles the Performance Agent's full knowledge into a
cached system prompt and calls Claude to reason in-voice.

Knowledge loaded on every analysis:
  L1 curated  -> AGENT_INSTRUCTIONS + CAC ladder + Decision framework + knowledge/*
  per-brand   -> that brand's Playbook / Decision_Log / Audience_Map
  L4 learning -> learning/lessons_learned.md + recent decisions from the SQLite store

The big, slow-changing L1 block is sent with Anthropic prompt caching, so a
back-and-forth thread re-reads it at ~1/10th the input cost.
"""
from __future__ import annotations

import json
from functools import lru_cache

from anthropic import Anthropic

import config
import store

_client = Anthropic(api_key=config.ANTHROPIC_API_KEY) if config.ANTHROPIC_API_KEY else None

# Optional cross-vendor auditor (Gemini). When a key is set, spend actions get an
# INDEPENDENT (different-vendor) review; otherwise we fall back to a 2nd Claude model.
_gemini = None
if config.GEMINI_API_KEY:
    try:
        import google.generativeai as _genai
        _genai.configure(api_key=config.GEMINI_API_KEY)
        _gemini = _genai.GenerativeModel(config.GEMINI_MODEL)
    except Exception:
        _gemini = None

# Protocol that lets the agent PROPOSE a money action. app.py turns any emitted
# block into an Approve/Pass button. The agent never executes — operator clicks.
ACTION_PROTOCOL = (
    "ACTION PROTOCOL: You may RECOMMEND and PROPOSE account changes, but you NEVER execute "
    "them — the operator taps Approve. If (and only if) a change should be made, append at the "
    "very END of your message exactly ONE fenced block:\n"
    "```action\n{\"action\": \"<name>\", \"args\": { ... }}\n```\n"
    "The system renders it as an Approve / Pass button; nothing runs until the operator taps Approve.\n"
    "AVAILABLE ACTIONS (campaigns & ad sets are always created PAUSED; server guardrails always apply):\n"
    "SPEND (moves live budget):\n"
    "- activate_campaign {campaign_id}\n"
    "- pause_ad_set {ad_set_id, force?}   (refuses <$50 spent or <3 days unless force=true)\n"
    "- scale_ad_set_budget {ad_set_id, percent_change}   (hard-capped at +/-25% per call)\n"
    "BUILD / STRUCTURE:\n"
    "- create_campaign {name, objective?}   (objective default OUTCOME_SALES)\n"
    "- create_ad_set {name, campaign_id, daily_budget_cents, custom_audience_ids:[], pixel_id?, "
    "optimization_goal?, custom_event_type?, countries?, placements?}\n"
    "- create_ad {name, ad_set_id, creative_id}\n"
    "- create_ad_creative {name, page_id, video_id, primary_text, headline, destination_url, cta_type?, instagram_actor_id?}\n"
    "- upload_video_creative {file_path, name}\n"
    "- upload_custom_audience {name, csv_path, description?}\n"
    "- create_lookalike_audience {seed_audience_id, name, country?, ratio_pct?}\n"
    "Pull IDs from the LIVE snapshot and the brand Playbook. If you're missing a required arg "
    "(a page_id, creative_id, video file, etc.), ASK the operator for it — never invent IDs. "
    "Emit at most one action block; if no change is warranted, emit none."
)

# How replies should LOOK in Slack — short, scannable, phone-friendly, PLAIN.
SLACK_STYLE = (
    "REPLY STYLE (Slack, read on a phone — keep it tight, scannable, and PLAIN):\n"
    "- First line = the headline answer/number in *bold*. No preamble, no restating the question.\n"
    "- Then 2-5 short bullet lines, one metric or point each; *bold* the numbers.\n"
    "- End with ONE line: the call — 🟢 Scale / 🟡 Hold / 🟠 Watch / 🔴 Pause + a <=1-sentence why.\n"
    "- Under ~120 words unless asked to go deep. No long paragraphs. Money in USD.\n"
    "- PLAIN ENGLISH. Write for a sharp non-marketer. No hype words ('burning', 'crushing', 'flying blind').\n"
    "- TEACH THE LINGO — required: the FIRST time ANY industry term or acronym appears in a message, add a short "
    "plain-English gloss in parentheses right after it. The operator is learning the industry, so do this EVERY message, "
    "even for terms used before. Examples: CAPI (server-side tracking that reports sales straight to Meta), "
    "CAC (cost to get one paying customer), CPC (cost per click), CPM (cost per 1,000 views), CTR (click-through rate — "
    "% who click), CVR (% who finish checkout), ROAS (revenue per $1 of ad spend), frequency (avg times one person saw the "
    "ad), attribution (how Meta credits a sale to an ad), learning phase (Meta's early test period before it optimizes).\n"
    "- TIME WINDOW — respect exactly what's asked: if the operator names a window (today, yesterday, last 7 days), report "
    "ONLY that window's numbers and say which window it is. Do NOT pad with lifetime totals. Use lifetime only when no window "
    "is named. If a needed number isn't available for that window, say so plainly rather than substituting another period."
)


def _read(path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


@lru_cache(maxsize=1)
def static_knowledge() -> str:
    """Curated, slow-changing knowledge (L1). Cached in-process and prompt-cached."""
    parts = [
        ("AGENT_INSTRUCTIONS", _read(config.AGENT_INSTRUCTIONS)),
        ("CAC_LADDER_FRAMEWORK", _read(config.CAC_LADDER)),
        ("DECISION_FRAMEWORK", _read(config.DECISION_FRAMEWORK)),
    ]
    for f in sorted(config.KNOWLEDGE_DIR.glob("*.md")):
        parts.append((f"KNOWLEDGE/{f.name}", _read(f)))
    return "\n\n".join(f"# === {name} ===\n{body}" for name, body in parts if body)


def _brand_context(brand_dir, brand_name) -> str:
    parts = []
    for fn in ("Playbook.md", "Performance_Playbook.md", "Decision_Log.md", "Audience_Map.md"):
        body = _read(brand_dir / fn)
        if body:
            parts.append(f"# === {brand_name}/{fn} ===\n{body}")
    return "\n\n".join(parts) or f"(no brand files found for {brand_name})"


def _learning_context(brand_name) -> str:
    lessons_md = _read(config.LEARNING_DIR / "lessons_learned.md")
    proven = store.recent_lessons(brand=brand_name, limit=12)
    recent = store.recent_decisions(brand=brand_name, limit=10)
    lines = ["# === PROVEN LESSONS (learned from real outcomes — these override general benchmarks) ==="]
    if not proven:
        lines.append("(none proven yet)")
    for l in proven:
        lines.append(f"- [{l.get('brand')}] {l.get('lesson')}")
    lines.append("\n# === RECENT DECISIONS (machine learning store) ===")
    if not recent:
        lines.append("(none logged yet)")
    for d in recent:
        lines.append(
            f"- {d['ts'][:10]} {d.get('scope')}: {d.get('call')} ({d.get('confidence')}) "
            f"— {d.get('diagnosis')} -> outcome: {d.get('outcome') or 'pending'}"
        )
    return f"# === LESSONS LEARNED (curated) ===\n{lessons_md}\n\n" + "\n".join(lines)


def _json_in(text):
    """Pull the first JSON object out of a model reply."""
    import re as _re
    m = _re.search(r"\{.*\}", text or "", _re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def assess_outcome(decision: dict, live_data: str):
    """Given a past decision + current data, judge what actually happened and
    whether it's a durable lesson. Returns {"outcome": str, "lesson": str|None} or None."""
    if not _client:
        return None
    prompt = (
        "A prior media-buying decision was logged. Using the CURRENT live data, assess what actually happened. "
        "Be concrete and cite the key number.\n\n"
        f"DECISION ({(decision.get('ts') or '')[:10]}): {decision.get('call')} on {decision.get('scope')} — "
        f"diagnosis: {decision.get('diagnosis')}; predicted: {decision.get('predicted')}.\n\n"
        f"CURRENT DATA:\n{live_data}\n\n"
        'Return ONLY JSON: {"outcome": "one sentence — did it play out as predicted, with the key number", '
        '"lesson": "a durable, transferable one-line lesson IF clearly generalizable for this brand, else null"}'
    )
    resp = _client.messages.create(
        model=config.MODEL_REASONING, max_tokens=400,
        messages=[{"role": "user", "content": prompt}],
    )
    return _json_in("".join(b.text for b in resp.content if b.type == "text"))


def audit(recommendation_text: str, action: str, args: dict):
    """Independent second-model sanity check on a proposed spend action.
    Returns (ok: bool, note: str). Does NOT redo the analysis — only flags clear
    guardrail violations / red flags."""
    prompt = (
        "You are an independent risk auditor for a Meta Ads agent. A spend action is proposed. "
        "Check ONLY for clear problems against these hard guardrails: scale changes must be within ±25%; "
        "never pause an ad set with <$50 spend or <3 days runtime unless explicitly forced; activate only "
        "with a clear rationale; args must be well-formed. Do not re-do the analysis.\n\n"
        f"PROPOSED: {action} args={json.dumps(args)}\n\nAGENT RATIONALE:\n{(recommendation_text or '')[:1500]}\n\n"
        'Return ONLY JSON: {"ok": true or false, "note": "one short line"}'
    )
    # Prefer the independent cross-vendor auditor (Gemini) when configured.
    if _gemini is not None:
        try:
            v = _json_in(_gemini.generate_content(prompt).text)
            if v is not None:
                return (bool(v.get("ok", True)), "Gemini: " + str(v.get("note", "")))
        except Exception:
            pass  # fall through to the Claude auditor
    if not _client:
        return (True, "auditor offline")
    resp = _client.messages.create(
        model=config.MODEL_AUDITOR, max_tokens=150,
        messages=[{"role": "user", "content": prompt}],
    )
    v = _json_in("".join(b.text for b in resp.content if b.type == "text"))
    if not v:
        return (True, "auditor returned no verdict")
    return (bool(v.get("ok", True)), "Claude-2nd: " + str(v.get("note", "")))


def ask(question, *, brand_name, brand_dir, live_data=None, model=None, max_tokens=1500) -> str:
    """One reasoning call. Returns the agent's in-voice answer (may include an
    ```action``` block per ACTION_PROTOCOL)."""
    if not _client:
        return "ANTHROPIC_API_KEY not set — the brain is offline."
    system = [
        {"type": "text", "text": static_knowledge(), "cache_control": {"type": "ephemeral"}},
        {"type": "text", "text": _brand_context(brand_dir, brand_name)},
        {"type": "text", "text": _learning_context(brand_name)},
        {"type": "text", "text": ACTION_PROTOCOL},
        {"type": "text", "text": SLACK_STYLE},
    ]
    user = question
    if live_data:
        user = f"LIVE META DATA (read-only snapshot):\n{live_data}\n\n---\n{question}"
    resp = _client.messages.create(
        model=model or config.MODEL_REASONING,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    return "".join(b.text for b in resp.content if b.type == "text").strip()


def triage(text) -> bool:
    """Cheap Haiku gate: is this message actually a request the agent should
    answer? Stops 'thanks'/emoji/chatter from costing a Sonnet call."""
    if not _client:
        return True
    if not text or len(text.strip()) < 2:
        return False
    resp = _client.messages.create(
        model=config.MODEL_TRIAGE,
        max_tokens=5,
        messages=[{"role": "user", "content": (
            "Reply only YES or NO. Is this a question or request a Meta Ads "
            f"media-buying agent should answer?\n\nMessage: {text}"
        )}],
    )
    return "YES" in "".join(b.text for b in resp.content if b.type == "text").upper()
