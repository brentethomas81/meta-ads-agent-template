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

# Protocol that lets the agent PROPOSE a money action. app.py turns any emitted
# block into an Approve/Pass button. The agent never executes — operator clicks.
ACTION_PROTOCOL = (
    "ACTION PROTOCOL: You may RECOMMEND but never execute money actions. If—and only if—"
    "you conclude the operator should run a spend action (activate_campaign, pause_ad_set, "
    "or scale_ad_set_budget), append at the very END of your message a single fenced block:\n"
    "```action\n{\"action\": \"scale_ad_set_budget\", \"args\": {\"ad_set_id\": \"<id>\", \"percent_change\": 20}}\n```\n"
    "The system renders it as an Approve/Pass button for the operator. Emit at most one. "
    "If no spend action is warranted, emit no block."
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
    lessons = _read(config.LEARNING_DIR / "lessons_learned.md")
    recent = store.recent_decisions(brand=brand_name, limit=10)
    lines = ["# === RECENT DECISIONS (machine learning store) ==="]
    if not recent:
        lines.append("(none logged yet)")
    for d in recent:
        lines.append(
            f"- {d['ts'][:10]} {d.get('scope')}: {d.get('call')} ({d.get('confidence')}) "
            f"— {d.get('diagnosis')} -> outcome: {d.get('outcome') or 'pending'}"
        )
    return f"# === LESSONS LEARNED (curated) ===\n{lessons}\n\n" + "\n".join(lines)


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
