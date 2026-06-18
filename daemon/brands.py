"""Brand registry + CAC ladder logic (Python mirror of the dashboard's brands.js).
Keep this in sync with dashboard/lib/brands.js. The "id" must also appear in
daemon/config.py BRAND_DIRS, pointing at that brand's folder."""

BRANDS = [
    {
        "id": "example-brand",
        "name": "Example Brand",
        "ad_account_id": "act_REPLACE_ME",   # your Meta ad account (prefix with act_)
        "currency": "USD",
        "target_cac": 15,
        "ladder": {"scale_below": 10, "hold_max": 20, "pause_above": 25},
        "learning_ladder": {"scale_below": 12, "hold_max": 25, "pause_above": 35},
        "active": True,
    },
    # Add more brands here, mirroring dashboard/lib/brands.js.
]


def ladder_verdict(cac, age_days, brand):
    """Return (tier, emoji, label) for a CAC given ad-set age and brand thresholds."""
    if cac is None:
        return ("NODATA", "⚪", "No data")
    learning = age_days is not None and age_days < 15 and brand.get("learning_ladder")
    l = brand["learning_ladder"] if learning else brand["ladder"]
    if cac < l["scale_below"]:
        return ("SCALE", "🟢", "SCALE")
    if cac <= l["hold_max"]:
        return ("HOLD", "🟡", "HOLD")
    if cac > l["pause_above"]:
        return ("PAUSE", "🔴", "PAUSE")
    return ("WATCH", "🟠", "WATCH")
