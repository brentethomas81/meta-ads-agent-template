"""Central config for the Meta Ads Agent Slack bot.

Secrets come from the environment. Locally they're loaded from daemon/.env
(via python-dotenv); on Fly they're injected by `fly secrets set`. Either way
it's just os.getenv — no code change between laptop and production.
"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

HERE = Path(__file__).parent
REPO = HERE.parent  # .../Meta Ads Agent
load_dotenv(HERE / ".env")  # no-op on Fly (file absent); Fly injects real env vars

# --- Slack ---
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "").strip()
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "").strip()
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET", "").strip()

# --- Anthropic (the brain) ---
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "").strip()
MODEL_REASONING = os.getenv("MODEL_REASONING", "claude-sonnet-4-6")          # the expert
MODEL_TRIAGE = os.getenv("MODEL_TRIAGE", "claude-haiku-4-5-20251001")        # cheap gate

# --- Behavior ---
# ONE briefing per day, fired at this local time, and ONLY if a campaign is
# ACTIVE (gated in briefing.py). Zero active campaigns => zero LLM calls => $0.
BRIEFING_HOUR = int(os.getenv("BRIEFING_HOUR", "6"))
BRIEFING_MINUTE = int(os.getenv("BRIEFING_MINUTE", "0"))
BRIEFING_TZ = os.getenv("BRIEFING_TZ", "America/Los_Angeles")
BRIEFING_CHANNEL = os.getenv("BRIEFING_CHANNEL", "").strip()  # Slack channel ID/name

# --- Storage (persistent on Fly /data volume) ---
DATA_DIR = Path(os.getenv("DATA_DIR", str(HERE / "data")))
DB_PATH = DATA_DIR / "learning.db"

# --- Knowledge / learning vault paths (read on every analysis) ---
AGENT_INSTRUCTIONS = REPO / "AGENT_INSTRUCTIONS.md"
CAC_LADDER = REPO / "CAC_Ladder_Framework.md"
DECISION_FRAMEWORK = REPO / "Decision_Framework.md"
KNOWLEDGE_DIR = REPO / "knowledge"
LEARNING_DIR = REPO / "learning"

# Map brand id -> repo folder that holds its Playbook/Decision_Log/Audience_Map
BRAND_DIRS = {
    "example-brand": REPO / "Example Brand",
    # Add one entry per brand, matching the ids in brands.py / dashboard brands.js,
    # pointing at that brand's folder (which holds its Playbook.md, etc.).
}


def missing_secrets() -> list[str]:
    """Which required secrets are still unset. Used to fail fast at startup."""
    required = ("SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_SIGNING_SECRET", "ANTHROPIC_API_KEY")
    return [name for name in required if not globals().get(name)]
