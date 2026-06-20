"""Stripe funnel / checkout-abandonment data for the agent. READ-ONLY.

Needs STRIPE_API_KEY — a RESTRICTED, read-only Stripe key with at least
'Checkout Sessions: read' and 'Payment Intents: read'. Without it (or without the
stripe lib), funnel_snapshot() returns "" and the bot just omits Stripe data;
Meta reporting is unaffected.

Optional STRIPE_PAYMENT_LINK isolates the funnel to the ad's payment link.
"""
from __future__ import annotations

import time

import config

try:
    import stripe as _stripe
except Exception:  # noqa: BLE001 — lib not installed locally; bot installs it
    _stripe = None

_READY = bool(config.STRIPE_API_KEY) and _stripe is not None
if _READY:
    _stripe.api_key = config.STRIPE_API_KEY


def _recent_sessions(days: int):
    """Recent Checkout Sessions (capped) within the window."""
    since = int(time.time()) - days * 86400
    out = []
    for s in _stripe.checkout.Session.list(limit=100, created={"gte": since}).auto_paging_iter():
        out.append(s)
        if len(out) >= 500:
            break
    return out


def funnel_snapshot(days: int = 14) -> str:
    """One line: checkout sessions started vs completed vs abandoned + rates.
    Abandonment = sessions that never reached 'complete' (open/expired)."""
    if not _READY:
        return ""
    try:
        sessions = _recent_sessions(days)
    except Exception as e:  # noqa: BLE001
        return f"STRIPE: data unavailable ({str(e)[:110]})"
    link = config.STRIPE_PAYMENT_LINK
    if link:
        sessions = [s for s in sessions if s.get("payment_link") == link]
    started = len(sessions)
    if not started:
        scope = "ad payment link" if link else "all links"
        return f"STRIPE FUNNEL (last {days}d, {scope}): 0 checkout sessions started yet."
    complete = sum(1 for s in sessions if s.get("status") == "complete")
    paid = sum((s.get("amount_total") or 0) for s in sessions if s.get("status") == "complete") / 100.0
    abandoned = started - complete
    rate = complete / started * 100
    scope = "ad payment link" if link else "all links"
    return (
        f"STRIPE FUNNEL (last {days}d, {scope}): {started} checkout sessions started · "
        f"{complete} completed (${paid:.2f}) · {abandoned} abandoned → "
        f"{rate:.0f}% completion / {100 - rate:.0f}% abandonment."
    )
