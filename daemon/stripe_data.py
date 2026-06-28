"""Stripe funnel / checkout-abandonment data for the agent. READ-ONLY.

Needs STRIPE_API_KEY — a RESTRICTED, read-only Stripe key with at least
'Checkout Sessions: read' and 'Payment Intents: read'. Without it (or without the
stripe lib), funnel_snapshot() returns "" and the bot just omits Stripe data;
Meta reporting is unaffected.

Optional STRIPE_PAYMENT_LINK isolates the funnel to the ad's payment link.
"""
from __future__ import annotations

import json
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
_AD_PAGE = "REPLACE_ME"  # the slug of your ad's dedicated landing page, e.g. "get" for /get

# Your own internal test-purchase emails to exclude from real-revenue counts.
_TEST_EMAILS = set()  # e.g. {"you@example.com"}

# Emails of sales you've hand-verified as ad-driven that Meta missed (its cookie /
# click-id attribution is wiped by the Instagram in-app browser, iOS, etc.). Add to
# this set as you confirm them, so ad_attribution counts them.
_CONFIRMED_AD_EMAILS = set()


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
    cookie attribution. Tagged by the the ad landing page + Meta click id; test
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
        if _is_ad_driven(s) or _email(s) in _CONFIRMED_AD_EMAILS:
            subs += 1
            rev += _field(s, "amount_total", 0) / 100.0
    if not subs:
        return f"AD-ATTRIBUTED (Stripe, last {days}d): 0 real ad-driven subscriptions tagged yet (test purchases excluded)."
    return (f"AD-ATTRIBUTED (Stripe, last {days}d): {subs} real ad-driven subscription(s) · ${rev:.2f} "
            f"— tagged by the the ad landing page + Meta click id + hand-confirmed sales, NOT Meta's cookie attribution (which under-counts); test emails excluded.")


def _fbp_first_ms(md: dict):
    """The Meta pixel cookie fbp = 'fb.1.<ms_first_set>.<rand>'. The <ms> is when
    the visitor's browser FIRST loaded the pixel = first site visit. Returns that
    epoch-ms, or None."""
    fbp = str((md or {}).get("fbp", "") or "")
    try:
        return int(fbp.split(".")[2])
    except Exception:  # noqa: BLE001
        return None


def _latest_session(cid: str):
    try:
        sl = _stripe.checkout.Session.list(customer=cid, limit=3).data
        return sl[0] if sl else None
    except Exception:  # noqa: BLE001
        return None


def _sub_line(cid: str) -> str:
    """Plan + status for a customer's most recent subscription, robust to SDK shape."""
    try:
        subs = _stripe.Subscription.list(customer=cid, limit=1).data
        if not subs:
            return "no subscription on file"
        sd = json.loads(str(subs[0]))
        item = sd["items"]["data"][0]
        amt = (item["price"].get("unit_amount") or 0) / 100.0
        interval = (item["price"].get("recurring") or {}).get("interval", "")
        return f"${amt:.2f}/{interval} · {sd.get('status', '')}"
    except Exception:  # noqa: BLE001
        return "subscription unreadable"


def customer_attribution(query: str, scan: int = 200) -> str:
    """Look up ONE named/emailed customer and judge — honestly — whether their
    purchase can be tied to the Meta ad. HARD proof = the checkout carried the
    Meta click id (fbc/fbclid) or arrived via the ad's dedicated landing page.
    The pixel cookie (fbp) alone is NOT proof (every visitor gets one). Returns a
    plain-text block for the brain, or '' if Stripe isn't configured."""
    if not _READY:
        return ""
    q = (query or "").strip().lower()
    if not q:
        return ""
    found = []
    try:
        if "@" in q:
            found = list(_stripe.Customer.list(email=q, limit=5).data)
        if not found:
            n = 0
            for c in _stripe.Customer.list(limit=100).auto_paging_iter():
                nm = str(_field(c, "name", "") or "").lower()
                em = str(_field(c, "email", "") or "").lower()
                if q in nm or q in em:
                    found.append(c)
                n += 1
                if n >= scan or len(found) >= 5:
                    break
    except Exception as e:  # noqa: BLE001
        return f"CUSTOMER LOOKUP ({query}): Stripe error — {str(e)[:120]}"
    if not found:
        return (f"CUSTOMER LOOKUP ({query}): no Stripe customer matches that name/email. "
                f"They may have paid under a different address, or started checkout without finishing.")

    blocks = []
    for c in found[:3]:
        cid = _field(c, "id", "")
        name = _field(c, "name", "") or "(no name)"
        email = _field(c, "email", "") or "(no email)"
        created = int(_field(c, "created", 0) or 0)
        sess = _latest_session(cid)
        # Parse the session to a plain dict so .get() is safe (Stripe objects aren't dicts).
        _sd = json.loads(str(sess)) if sess else {}
        md = _sd.get("metadata") or {}
        src = str(md.get("eventSourceUrl") or md.get("event_source_url") or "").lower()
        has_click = bool(md.get("fbc") or md.get("fbclid")) or "fbclid=" in src
        via_landing = bool(_AD_PAGE) and _AD_PAGE != "REPLACE_ME" and _AD_PAGE in src
        fbp_ms = _fbp_first_ms(md)
        mins = None
        if fbp_ms and created:
            mins = round((created * 1000 - fbp_ms) / 60000)
        if email.lower() in _TEST_EMAILS:
            verdict = "INTERNAL TEST purchase (excluded from ad numbers)."
        elif via_landing or has_click:
            why = "the ad's dedicated landing page" if via_landing else "a Meta click id (fbc/fbclid)"
            verdict = f"AD-DRIVEN ✅ (confirmed) — the checkout carried {why}."
        elif email.lower() in _CONFIRMED_AD_EMAILS:
            verdict = ("AD-DRIVEN ✅ (hand-confirmed) — the operator verified this one as coming from the ad (from timing/context); "
                       "the automatic signals were wiped by the in-app browser.")
        elif fbp_ms is not None and mins is not None and 0 <= mins <= 60:
            verdict = (f"UNCONFIRMED, leans paid/referral — first-time visitor (Meta pixel first fired ~{mins} min before "
                       f"they bought) who purchased the ad's plan, BUT there's no Meta click id and the checkout source is "
                       f"'{src or 'unknown'}' (not the ad landing page). Can't be PROVEN ad-driven — could be an ad "
                       f"view-through, an influencer/link share, or direct.")
        elif fbp_ms is not None:
            verdict = ("LIKELY ORGANIC / RETURNING — a Meta pixel cookie exists but predates this purchase and there's no ad-click "
                       "id; no evidence of an ad click.")
        else:
            verdict = "NO META SIGNAL — no pixel cookie, no click id; organic/direct as far as Stripe can see."
        blocks.append(
            f"  • {name} <{email}> — {_sub_line(cid)}\n"
            f"    signals: via_landing={via_landing} · meta_click_id={has_click} · "
            f"pixel_cookie={'yes' if fbp_ms else 'no'}{f' (first fired ~{mins}m before buying)' if mins is not None else ''}\n"
            f"    VERDICT: {verdict}"
        )
    note = ("NOTE on limits: if the landing page doesn't pass the Meta click id into the payment record, and the in-app browser "
            "wipes cookies, only purchases arriving with a click id or via the ad landing-page URL can be HARD-confirmed; "
            "everything else is inferred from soft signals (be explicit about that).")
    return "CUSTOMER LOOKUP (" + query + "):\n" + "\n".join(blocks) + "\n" + note


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
    # the ad landing page (Checkout Sessions, no payment_link), so we track ALL sessions
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
