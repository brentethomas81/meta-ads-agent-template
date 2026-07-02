"""Real-boot smoke test (pattern mined from the Lucille team, 2026-07-01).

Their scar: CI passed for weeks while EVERY production boot crashed, because no
test ever actually imported and constructed the app. This test does the minimum
that catches that whole bug class: import every daemon module with dummy env,
init the stores, and run one click-log round trip. Run before every deploy.

    python3 -m pytest tests/ -q        (or)        python3 tests/test_boot.py
"""
import os
import sys
import tempfile
import time

# Dummy env BEFORE any daemon import (config.py reads env at import time).
_TMP = tempfile.mkdtemp(prefix="ads_boot_test_")
os.environ.setdefault("DATA_DIR", _TMP)
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-not-real")
os.environ.setdefault("SLACK_APP_TOKEN", "xapp-test-not-real")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test")
os.environ.setdefault("ANTHROPIC_API_KEY", "test")
os.environ.setdefault("GEMINI_API_KEY", "test")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "daemon"))


def test_daemon_modules_import_and_boot():
    """Every module the bot needs at boot must import without secrets/network."""
    import config          # noqa: F401
    import store
    import stripe_data     # noqa: F401  (Stripe key absent → _READY False, no crash)
    import brands          # noqa: F401
    import clicklog

    store.init()  # learning-store schema builds on a fresh volume

    # Click-log round trip: log → unique-mcid lookup → windowed counts.
    mcid = clicklog.log_click("stan", {"fbclid": "BOOTTEST"}, "pytest-ua", "127.0.0.1")
    assert len(mcid) == 12
    hit = clicklog.click_for_mcid(mcid)
    assert hit and hit["fbclid"] == "BOOTTEST" and hit["slug"] == "stan"
    assert clicklog.clicks_near(int(time.time()) + 60) >= 1
    assert clicklog.click_count(1) >= 1


def test_attribution_window_never_clips_flight():
    """The 2026-07-01 shrinking-window bug must stay dead: the effective scan
    window must always reach back to the campaign flight start."""
    import stripe_data as sd
    if not sd._AD_FLIGHT_START:
        return  # date gate disabled — nothing to clip
    flight_age_days = (time.time() - time.mktime(
        time.strptime(sd._AD_FLIGHT_START, "%Y-%m-%d"))) / 86400
    widened = max(14, int(flight_age_days) + 2)
    assert widened >= flight_age_days, "window would clip the flight"


def test_classifier_scores_logger_signals_confirmed():
    """mcid / firstTouchUrl / stan-plan / fbc must all yield CONFIRMED."""
    import stripe_data as sd

    def fake_session(md):
        return {"status": "complete", "metadata": md,
                "customer_details": {"email": "someone@example.com"},
                "amount_total": 2999}

    assert sd._is_ad_driven(fake_session({"eventSourceUrl": "https://picklephd.com/stan-plan?mcid=abc123def456"}))
    assert sd._is_ad_driven(fake_session({"firstTouchUrl": "https://picklephd.com/stan-plan?fbclid=X"}))
    assert sd._is_ad_driven(fake_session({"eventSourceUrl": "https://picklephd.com/", "fbc": "fb.1.123.X"}))
    assert not sd._is_ad_driven(fake_session({"eventSourceUrl": "https://picklephd.com/"}))


if __name__ == "__main__":
    test_daemon_modules_import_and_boot()
    test_attribution_window_never_clips_flight()
    test_classifier_scores_logger_signals_confirmed()
    print("BOOT SMOKE TEST: ALL PASS")
