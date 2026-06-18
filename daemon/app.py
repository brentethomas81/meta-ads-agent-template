"""Meta Ads Agent — Slack Socket-Mode bot. Always-on. Two-way.

- @mention or DM -> the Performance Agent answers in-voice (Sonnet), behind a
  cheap Haiku triage gate so noise never costs a reasoning call.
- When the agent recommends a money action it emits an ```action``` block; the
  bot renders Approve / Pass buttons. It NEVER spends without your click.
- Once a day it posts a briefing — but only if a campaign is ACTIVE. Idle = $0.
"""
from __future__ import annotations

import json
import logging
import re

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import actions
import brain
import briefing
import config
import store
from brands import BRANDS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("meta-ads-bot")

app = App(token=config.SLACK_BOT_TOKEN, signing_secret=config.SLACK_SIGNING_SECRET)

DEFAULT_BRAND = next((b for b in BRANDS if b.get("active")), BRANDS[0])

ACTION_RE = re.compile(r"```action\s*(\{.*?\})\s*```", re.DOTALL)


def _extract_action(text: str):
    """Pull an ```action {json}``` block out of the agent's reply, if present."""
    m = ACTION_RE.search(text)
    if not m:
        return text, None
    try:
        action = json.loads(m.group(1))
    except json.JSONDecodeError:
        return text, None
    clean = ACTION_RE.sub("", text).strip()
    return clean, action


def _approval_blocks(aid: int, action: str, args: dict):
    return [
        {"type": "section", "text": {"type": "mrkdwn",
            "text": f"*Approval needed* — `{action}`\n```{json.dumps(args, indent=2)}```"}},
        {"type": "actions", "elements": [
            {"type": "button", "style": "primary", "action_id": "approve",
             "text": {"type": "plain_text", "text": "Approve"}, "value": str(aid)},
            {"type": "button", "style": "danger", "action_id": "pass_action",
             "text": {"type": "plain_text", "text": "Pass"}, "value": str(aid)},
        ]},
    ]


def _respond(text: str, user: str, say):
    """Reason -> reply; render an approval card if the agent proposed a money
    action. No triage gate — every DM/@mention is meant for the bot, so always
    answer (a swallowed message is worse than a cheap call)."""
    text = (text or "").strip()
    log.info("incoming from %s: %r", user, text[:120])
    if user:
        store.set_kv("operator_id", user)  # remember who to DM briefings to
    if len(text) < 2:
        return
    brand_dir = config.BRAND_DIRS.get(DEFAULT_BRAND["id"], config.REPO)
    answer = brain.ask(text, brand_name=DEFAULT_BRAND["name"], brand_dir=brand_dir)
    clean, action = _extract_action(answer)
    say(clean or "(no response)")
    if action and action.get("action") in actions.MONEY_ACTIONS:
        aid = store.create_approval(action["action"], action.get("args", {}), user)
        say(blocks=_approval_blocks(aid, action["action"], action.get("args", {})),
            text="Approval needed")


@app.event("app_mention")
def on_mention(event, say):
    text = re.sub(r"<@[^>]+>", "", event.get("text", "")).strip()
    _respond(text, event.get("user"), say)


@app.event("message")
def on_message(event, say):
    # Only handle direct messages here; channel messages come via app_mention.
    if event.get("channel_type") != "im" or event.get("bot_id"):
        return
    _respond(event.get("text", "").strip(), event.get("user"), say)


@app.event("reaction_added")
def on_reaction(event):
    # 👍/👎 captured as a learning signal only — never auto-tunes a guardrail.
    log.info("reaction %s by %s", event.get("reaction"), event.get("user"))


@app.action("approve")
def on_approve(ack, body, say):
    ack()
    aid = int(body["actions"][0]["value"])
    ap = store.get_approval(aid)
    if not ap or ap["status"] != "pending":
        say("That action is no longer pending.")
        return
    args = json.loads(ap["args_json"])
    result = actions.execute_money_action(ap["action"], args)
    err = isinstance(result, dict) and result.get("error")
    store.update_approval(aid, "error" if err else "executed", result)
    say(f"{'⚠️ Error' if err else '✅ Done'}: `{ap['action']}`\n```{json.dumps(result, indent=2)}```")


@app.action("pass_action")
def on_pass(ack, body, say):
    ack()
    aid = int(body["actions"][0]["value"])
    store.update_approval(aid, "passed")
    say("Passed — no action taken.")


def _post_to_briefing_channel(text: str):
    # Prefer an explicit channel; else DM the operator (their ID is captured
    # from the first message they send the bot). Posting to a user ID DMs them.
    target = config.BRIEFING_CHANNEL or store.get_kv("operator_id")
    if not target:
        log.warning("No briefing target yet — DM the bot once so it learns your ID. Not posted:\n%s", text)
        return
    app.client.chat_postMessage(channel=target, text=text)


def _scheduled_briefing():
    log.info("Daily briefing: %s", briefing.run_daily_briefing(_post_to_briefing_channel))


def main():
    missing = config.missing_secrets()
    if missing:
        raise SystemExit(f"Missing secrets {missing} — set them in daemon/.env or via `fly secrets set`.")
    store.init()
    sched = BackgroundScheduler(timezone=config.BRIEFING_TZ)
    sched.add_job(_scheduled_briefing, CronTrigger(hour=config.BRIEFING_HOUR, minute=config.BRIEFING_MINUTE))
    sched.start()
    log.info("Meta Ads Agent bot up (Socket Mode). Daily briefing %02d:%02d %s.",
             config.BRIEFING_HOUR, config.BRIEFING_MINUTE, config.BRIEFING_TZ)
    SocketModeHandler(app, config.SLACK_APP_TOKEN).start()


if __name__ == "__main__":
    main()
