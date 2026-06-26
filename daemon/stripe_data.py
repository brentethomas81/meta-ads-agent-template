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


def _field(obj, key, default=None):
    """Read a field from a Stripe object OR a plain dict, safely.

    Stripe's response objects don't reliably expose dict's ``.get`` across
    library versions, so we try subscript access first and fall back to
    attribute access — never raising on a missing key.
    """
    try:
        val = obj[key]
    except Exception:  # noqa: BLE001
        val = getattr(obj, key, default)
    return default if val is None else val


def _recent_sessions(days: int):
    """Recent Checkout Sessions (capped) within the window."""
    since = int(time.time()) - days * 86400
    out = []
    for s in _stripe.checkout.Session.list(limit=100, created={"gte": since}).auto_paging_iter():
        out.append(s)
        if len(out) >= 500:
            break
    return out


# --- Ad attribution (deterministic, cookie-free) ----------------------------
# The ad's dedicated landing page: organic users never see it, so any checkout
# that STARTS there is ad-driven by definition. Combined with the Meta click id
# (fbc / fbclid carried in the stored landing URL) this tags real ad sales
# WITHOUT relying on Meta's cookie attribution (which the IG in-app browser and
# iOS routinely wipe). Excludes known internal test emails.
_AD_PAGE = "stan-plan"
_TEST_EMAILS = {"redacted@example.com", "redacted@example.com", "redacted@example.com"}


def _meta(s) -> dict:
    md = _field(s, "metadata", {}) or {}
    out = {}
    for k in ("eventSourceUrl", "event_source_url", "fbc", "fbclid"):
        v = _field(md, k, None)
        if v not in (None, ""):
            out[k] = str(v)
    return out


def _email(s) -> str:
    cd = _field(s, "customer_details", {}) or {}
    return str(_field(cd, "email", "") or "").lower()


def _is_ad_driven(s) -> bool:
    m = _meta(s)
    src = (m.get("eventSourceUrl") or m.get("event_source_url") or "").lower()
    if _AD_PAGE in src:
        return True
    if m.get("fbc") or m.get("fbclid") or "fbclid=" in src:
        return True
    return False


def ad_attribution(days: int = 14) -> str:
    """Real ad-driven subscriptions from Stripe, independent of Meta's (under-counted)
    cookie attribution. Tagged by the /stan-plan landing page + Meta click id; test
    emails excluded. Returns '' if Stripe isn't configured."""
    if not _READY:
        return ""
    try:
        sessions = _recent_sessions(days)
    except Exception:  # noqa: BLE001
        return ""
    subs, rev = 0, 0.0
    for s in sessions:
        if _field(s, "status") != "complete" or _email(s) in _TEST_EMAILS:
            continue
        if _is_ad_driven(s):
            subs += 1
            rev += _field(s, "amount_total", 0) / 100.0
    if not subs:
        return f"AD-ATTRIBUTED (Stripe, last {days}d): 0 real ad-driven subscriptions tagged yet (test purchases excluded)."
    return (f"AD-ATTRIBUTED (Stripe, last {days}d): {subs} real ad-driven subscription(s) · ${rev:.2f} "
            f"— tagged by the /stan-plan page + Meta click id, NOT Meta's cookie attribution (which under-counts); test emails excluded.")


def funnel_snapshot(days: int = 14) -> str:
    """One line: checkout sessions started vs completed vs abandoned + rates.
    Abandonment = sessions that never reached 'complete' (open/expired)."""
    if not _READY:
        return ""
    try:
        sessions = _recent_sessions(days)
    except Exception as e:  # noqa: BLE001
        return f"STRIPE: data unavailable ({str(e)[:110]})"
    # NOTE: the old bare Stripe Payment Link is retired — the ad now drives to the
    # /stan-plan page (Checkout Sessions, no payment_link), so we track ALL sessions
    # for overall checkout health and tag the ad-driven subset separately below.
    started = len(sessions)
    ad = ad_attribution(days)
    if not started:
        base = f"STRIPE FUNNEL (last {days}d): 0 checkout sessions started yet."
        return base + ("\n" + ad if ad else "")
    complete = sum(1 for s in sessions if _field(s, "status") == "complete")
    paid = sum(_field(s, "amount_total", 0) for s in sessions if _field(s, "status") == "complete") / 100.0
    abandoned = started - complete
    rate = complete / started * 100
    funnel = (
        f"STRIPE FUNNEL (last {days}d, all checkout sessions): {started} started · "
        f"{complete} completed (${paid:.2f}) · {abandoned} abandoned → "
        f"{rate:.0f}% completion / {100 - rate:.0f}% abandonment."
    )
    return funnel + ("\n" + ad if ad else "")
