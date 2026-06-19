"""
Meta Ads MCP — local stdio server wrapping the Marketing API as agent tools.

Run locally; Cowork connects via stdio. See README.md for setup.

Tier 1 tools (this file):
- list_audiences, upload_custom_audience, create_lookalike_audience
- list_campaigns, create_campaign, create_ad_set, create_ad
- upload_video_creative, create_ad_creative
- activate_campaign, pause_ad_set, scale_ad_set_budget
- get_campaign_insights, get_ad_set_insights

Guardrails enforced in code (not just docs):
- Campaigns/ad sets default to PAUSED. activate_campaign() is the only path to ACTIVE.
- scale_ad_set_budget caps changes at +/- 25%.
- pause_ad_set without force=True refuses ads with <$50 spend or <3 days runtime.
- All ops logged to local SQLite audit.db.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from dotenv import load_dotenv
from mcp.server.fastmcp import FastMCP

# Load .env from the same directory as this script
HERE = Path(__file__).parent
load_dotenv(HERE / ".env")

# ---------------------------------------------------------------------------
# Meta SDK init
# ---------------------------------------------------------------------------
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad
from facebook_business.adobjects.adcreative import AdCreative
from facebook_business.adobjects.advideo import AdVideo
from facebook_business.adobjects.customaudience import CustomAudience
from facebook_business.exceptions import FacebookRequestError

ACCESS_TOKEN = os.getenv("META_ACCESS_TOKEN")
DEFAULT_AD_ACCOUNT = os.getenv("META_DEFAULT_AD_ACCOUNT_ID")
BUSINESS_ID = os.getenv("META_BUSINESS_ID")
DEFAULT_PIXEL_ID = os.getenv("META_DEFAULT_PIXEL_ID")
APP_ID = os.getenv("META_APP_ID") or None
APP_SECRET = os.getenv("META_APP_SECRET") or None
_audit_env = os.getenv("AUDIT_DB_PATH")
# Resolve any relative AUDIT_DB_PATH against this script's folder, not the
# launch cwd — the Claude app starts the server from a different directory.
AUDIT_DB_PATH = str((HERE / _audit_env).resolve()) if _audit_env else str(HERE / "audit.db")

if not ACCESS_TOKEN:
    print("[meta-ads-mcp] FATAL: META_ACCESS_TOKEN not set in .env", file=sys.stderr)
    sys.exit(1)

FacebookAdsApi.init(
    app_id=APP_ID,
    app_secret=APP_SECRET,
    access_token=ACCESS_TOKEN,
    api_version="v21.0",
)

# ---------------------------------------------------------------------------
# Audit log (SQLite)
# ---------------------------------------------------------------------------

def _audit_init() -> None:
    conn = sqlite3.connect(AUDIT_DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT NOT NULL,
            tool TEXT NOT NULL,
            params TEXT,
            result TEXT,
            error TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def _audit(tool: str, params: dict, result: Optional[Any] = None, error: Optional[str] = None) -> None:
    conn = sqlite3.connect(AUDIT_DB_PATH)
    conn.execute(
        "INSERT INTO calls (ts, tool, params, result, error) VALUES (?, ?, ?, ?, ?)",
        (
            datetime.utcnow().isoformat() + "Z",
            tool,
            json.dumps(params, default=str)[:5000],
            json.dumps(result, default=str)[:5000] if result is not None else None,
            error,
        ),
    )
    conn.commit()
    conn.close()


_audit_init()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _ad_account(ad_account_id: Optional[str]) -> AdAccount:
    aid = ad_account_id or DEFAULT_AD_ACCOUNT
    if not aid:
        raise ValueError("ad_account_id not provided and META_DEFAULT_AD_ACCOUNT_ID not set in .env")
    if not aid.startswith("act_"):
        aid = f"act_{aid}"
    return AdAccount(aid)


def _sha256_norm(value: Optional[str]) -> str:
    """SHA-256 hash of a normalized identifier (lowercased, stripped). Empty -> ''."""
    if not value:
        return ""
    return hashlib.sha256(str(value).strip().lower().encode("utf-8")).hexdigest()


def _jsonable(obj):
    """Recursively coerce facebook-business SDK objects (and any other non-JSON
    types) into plain dict / list / str / number / bool / None so FastMCP can
    serialize them. Without this, fields like delivery_status or insights
    `actions` come back as SDK objects and crash the whole tool response.
    """
    # Primitives pass straight through.
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    # Plain mappings: recurse into values.
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    # SDK objects expose export_all_data() -> plain dict.
    export = getattr(obj, "export_all_data", None)
    if callable(export):
        try:
            return _jsonable(export())
        except Exception:
            pass
    # Sequences (lists, tuples, sets, SDK Cursors) — but never strings/bytes.
    if isinstance(obj, (list, tuple, set)):
        return [_jsonable(v) for v in obj]
    # AbstractCrudObject and similar are dict()-convertible.
    try:
        return {str(k): _jsonable(v) for k, v in dict(obj).items()}
    except Exception:
        pass
    # Last resort: stringify so the response never crashes.
    return str(obj)


def _safely_call(tool_name: str, params: dict, fn):
    """Execute fn, audit-log the result or error, and return a clean response."""
    try:
        result = _jsonable(fn())
        _audit(tool_name, params, result=result)
        return result
    except FacebookRequestError as e:
        def _safe(fn):
            try:
                return fn()
            except Exception:
                return None
        err = {
            "error": "FacebookRequestError",
            "message": _safe(e.api_error_message),
            "type": _safe(e.api_error_type),
            "code": _safe(e.api_error_code),
            "subcode": _safe(e.api_error_subcode),
            "fbtrace_id": _safe(getattr(e, "api_error_fbtrace_id", lambda: None)),
            "body": _safe(e.body),
        }
        _audit(tool_name, params, error=json.dumps(err, default=str))
        return err
    except Exception as e:
        err = {"error": type(e).__name__, "message": str(e)}
        _audit(tool_name, params, error=json.dumps(err))
        return err


# ---------------------------------------------------------------------------
# MCP server
# ---------------------------------------------------------------------------
mcp = FastMCP("meta-ads")


# === AUDIENCES =============================================================

@mcp.tool()
def list_audiences(ad_account_id: Optional[str] = None, limit: int = 50) -> list[dict]:
    """List custom and lookalike audiences in the ad account.

    Args:
        ad_account_id: Override default ad account (prefix with "act_"). Defaults to META_DEFAULT_AD_ACCOUNT_ID.
        limit: Max number of audiences to return. Default 50.

    Returns: list of {id, name, subtype, approximate_count, delivery_status}
    """
    params_log = {"ad_account_id": ad_account_id, "limit": limit}

    def _do():
        fields = [
            CustomAudience.Field.id,
            CustomAudience.Field.name,
            CustomAudience.Field.subtype,
            CustomAudience.Field.approximate_count_lower_bound,
            CustomAudience.Field.approximate_count_upper_bound,
            CustomAudience.Field.delivery_status,
            CustomAudience.Field.time_created,
        ]
        items = _ad_account(ad_account_id).get_custom_audiences(fields=fields, params={"limit": limit})

        def _clean(a):
            raw = dict(a)
            ds = raw.get("delivery_status")
            # delivery_status comes back as a CustomAudienceStatus SDK object; coerce to plain dict/str
            if ds is not None and not isinstance(ds, (dict, str)):
                try:
                    ds = dict(ds)
                except Exception:
                    ds = str(ds)
            lo = raw.get("approximate_count_lower_bound")
            hi = raw.get("approximate_count_upper_bound")
            return {
                "id": raw.get("id"),
                "name": raw.get("name"),
                "subtype": raw.get("subtype"),
                "approximate_count_lower_bound": lo,
                "approximate_count_upper_bound": hi,
                "delivery_status": ds,
                "time_created": raw.get("time_created"),
            }

        return [_clean(a) for a in items]

    return _safely_call("list_audiences", params_log, _do)


@mcp.tool()
def upload_custom_audience(
    name: str,
    csv_path: str,
    description: str = "",
    ad_account_id: Optional[str] = None,
) -> dict:
    """Upload a CSV of customer identifiers as a Custom Audience. Hashes server-side.

    CSV must have a header row. Recognized column names (case-insensitive):
      email, fn (first name), ln (last name), phone, ct (city), st (state), country, zip, madid, dob, gen

    Args:
        name: Audience name (e.g. "MyBrand_Active_Subs_Seed_v1")
        csv_path: Absolute path to the CSV file on this machine.
        description: Optional description.
        ad_account_id: Override default ad account.

    Returns: {audience_id, name, rows_uploaded, sessions_used}
    """
    import csv as _csv

    params_log = {"name": name, "csv_path": csv_path, "description": description}

    def _do():
        if not Path(csv_path).exists():
            raise FileNotFoundError(f"CSV not found at {csv_path}")

        # Read + normalize CSV
        with open(csv_path, "r", newline="") as f:
            reader = _csv.DictReader(f)
            headers = [h.lower().strip() for h in (reader.fieldnames or [])]
            rows = [dict((k.lower().strip(), v) for k, v in row.items()) for row in reader]

        if not rows:
            raise ValueError("CSV is empty")

        # Build schema (Meta's expected field codes)
        schema_map = {
            "email": "EMAIL",
            "phone": "PHONE",
            "fn": "FN",
            "ln": "LN",
            "ct": "CT",
            "st": "ST",
            "country": "COUNTRY",
            "zip": "ZIP",
            "madid": "MADID",
            "dob": "DOBY",  # year of birth alias
            "gen": "GEN",
        }
        schema = [schema_map[h] for h in headers if h in schema_map]
        if not schema:
            raise ValueError(f"CSV headers {headers} don't include any recognized identifiers")

        # Hash each row
        hashed_rows = []
        for row in rows:
            hashed_rows.append([_sha256_norm(row.get(h)) for h in headers if h in schema_map])

        # Create the audience (empty shell first)
        audience = _ad_account(ad_account_id).create_custom_audience(
            fields=[],
            params={
                "name": name,
                "subtype": "CUSTOM",
                "description": description,
                "customer_file_source": "USER_PROVIDED_ONLY",
            },
        )

        # Add the hashed users
        # Meta accepts up to ~10,000 per call; chunk for safety.
        CHUNK = 5000
        total_uploaded = 0
        sessions = 0
        for i in range(0, len(hashed_rows), CHUNK):
            chunk = hashed_rows[i : i + CHUNK]
            audience.create_user(
                params={
                    "payload": {
                        "schema": schema,
                        "data": chunk,
                    }
                }
            )
            total_uploaded += len(chunk)
            sessions += 1

        return {
            "audience_id": audience["id"],
            "name": name,
            "rows_uploaded": total_uploaded,
            "sessions_used": sessions,
            "note": "Matching takes 15-60 min. Use list_audiences to check delivery_status.",
        }

    return _safely_call("upload_custom_audience", params_log, _do)


@mcp.tool()
def create_lookalike_audience(
    seed_audience_id: str,
    name: str,
    country: str = "US",
    ratio_pct: float = 1.0,
    ad_account_id: Optional[str] = None,
) -> dict:
    """Create a Lookalike Audience from an existing seed Custom Audience.

    Args:
        seed_audience_id: ID of the source Custom Audience.
        name: Lookalike name (e.g. "MyBrand_Subs_LAL_US_1pct_v1")
        country: ISO 3166-1 alpha-2 (default "US"). Single country only.
        ratio_pct: 1.0 to 10.0 (interpreted as 1%, 2%, ... 10%). Default 1.0.
        ad_account_id: Override default ad account.

    Returns: {audience_id, name, ratio_pct, country}
    """
    params_log = {
        "seed_audience_id": seed_audience_id,
        "name": name,
        "country": country,
        "ratio_pct": ratio_pct,
    }

    def _do():
        if not (0.1 <= ratio_pct <= 10.0):
            raise ValueError("ratio_pct must be 0.1-10.0")
        lookalike_spec = {
            "type": "similarity",
            "country": country.upper(),
            "ratio": ratio_pct / 100.0,
        }
        lal = _ad_account(ad_account_id).create_custom_audience(
            fields=[],
            params={
                "name": name,
                "subtype": "LOOKALIKE",
                "origin_audience_id": seed_audience_id,
                "lookalike_spec": json.dumps(lookalike_spec),
            },
        )
        return {
            "audience_id": lal["id"],
            "name": name,
            "ratio_pct": ratio_pct,
            "country": country.upper(),
            "note": "Meta builds the LAL in 6-24h. Use list_audiences to check delivery_status.",
        }

    return _safely_call("create_lookalike_audience", params_log, _do)


# === CAMPAIGNS / AD SETS / ADS ============================================

@mcp.tool()
def list_campaigns(ad_account_id: Optional[str] = None, status_filter: Optional[str] = None, limit: int = 25) -> list[dict]:
    """List campaigns in the ad account.

    Args:
        ad_account_id: Override default ad account.
        status_filter: One of ACTIVE, PAUSED, ARCHIVED, DELETED, or None for all.
        limit: Max campaigns to return.

    Returns: list of {id, name, objective, status, daily_budget, created_time}
    """
    params_log = {"ad_account_id": ad_account_id, "status_filter": status_filter, "limit": limit}

    def _do():
        fields = [
            Campaign.Field.id,
            Campaign.Field.name,
            Campaign.Field.objective,
            Campaign.Field.status,
            Campaign.Field.effective_status,
            Campaign.Field.daily_budget,
            Campaign.Field.created_time,
        ]
        params: dict = {"limit": limit}
        if status_filter:
            params["effective_status"] = [status_filter.upper()]
        items = _ad_account(ad_account_id).get_campaigns(fields=fields, params=params)
        return [dict(c) for c in items]

    return _safely_call("list_campaigns", params_log, _do)


@mcp.tool()
def create_campaign(
    name: str,
    objective: str = "OUTCOME_SALES",
    ad_account_id: Optional[str] = None,
    special_ad_categories: Optional[list[str]] = None,
) -> dict:
    """Create a campaign in PAUSED status. Use activate_campaign() to start delivery.

    Args:
        name: Campaign name.
        objective: One of OUTCOME_SALES (default, for Subscribe/Purchase), OUTCOME_LEADS, OUTCOME_TRAFFIC, OUTCOME_AWARENESS, OUTCOME_ENGAGEMENT, OUTCOME_APP_PROMOTION.
        ad_account_id: Override default ad account.
        special_ad_categories: List like ["HOUSING"], ["CREDIT"], ["EMPLOYMENT"], or empty.

    Returns: {campaign_id, name, status, objective}
    """
    params_log = {"name": name, "objective": objective, "special_ad_categories": special_ad_categories}

    def _do():
        campaign = _ad_account(ad_account_id).create_campaign(
            fields=[],
            params={
                "name": name,
                "objective": objective,
                "status": "PAUSED",  # GUARDRAIL: never auto-activate
                "special_ad_categories": special_ad_categories or [],
                # Meta now requires this when not using campaign-level budget (CBO).
                # False = each ad set keeps its own budget (no cross-ad-set sharing).
                "is_adset_budget_sharing_enabled": False,
            },
        )
        return {
            "campaign_id": campaign["id"],
            "name": name,
            "status": "PAUSED",
            "objective": objective,
            "note": "Campaign is PAUSED. Call activate_campaign() after Ad Set + Ad are built.",
        }

    return _safely_call("create_campaign", params_log, _do)


@mcp.tool()
def create_ad_set(
    name: str,
    campaign_id: str,
    daily_budget_cents: int,
    custom_audience_ids: list[str],
    pixel_id: Optional[str] = None,
    optimization_goal: str = "OFFSITE_CONVERSIONS",
    custom_event_type: str = "SUBSCRIBE",
    countries: list[str] = ["US"],
    placements: Optional[list[str]] = None,
    ad_account_id: Optional[str] = None,
) -> dict:
    """Create an Ad Set inside an existing campaign. Defaults to PAUSED.

    Args:
        name: Ad set name.
        campaign_id: Parent campaign ID.
        daily_budget_cents: Daily budget in cents (1400 = $14.00/day).
        custom_audience_ids: List of audience IDs (your 1% LAL goes here).
        pixel_id: Pixel for conversion optimization. Defaults to META_DEFAULT_PIXEL_ID.
        optimization_goal: OFFSITE_CONVERSIONS (default for Subscribe), LINK_CLICKS, LANDING_PAGE_VIEWS, etc.
        custom_event_type: SUBSCRIBE, PURCHASE, COMPLETE_REGISTRATION, LEAD, etc.
        countries: List of ISO 3166-1 alpha-2 codes.
        placements: Optional. If None, uses Advantage+ Placements (recommended).
        ad_account_id: Override default ad account.

    Returns: {ad_set_id, name, status, daily_budget_cents}
    """
    params_log = {
        "name": name,
        "campaign_id": campaign_id,
        "daily_budget_cents": daily_budget_cents,
        "custom_audience_ids": custom_audience_ids,
        "optimization_goal": optimization_goal,
        "custom_event_type": custom_event_type,
        "countries": countries,
    }

    def _do():
        pid = pixel_id or DEFAULT_PIXEL_ID
        if not pid:
            raise ValueError("pixel_id not provided and META_DEFAULT_PIXEL_ID not set")

        targeting = {
            "geo_locations": {"countries": [c.upper() for c in countries]},
            "custom_audiences": [{"id": a} for a in custom_audience_ids],
        }
        if placements:
            # Advantage+ Placements is the default if we don't specify
            targeting["publisher_platforms"] = placements

        params = {
            "name": name,
            "campaign_id": campaign_id,
            "daily_budget": daily_budget_cents,
            "billing_event": "IMPRESSIONS",
            "optimization_goal": optimization_goal,
            "promoted_object": {
                "pixel_id": pid,
                "custom_event_type": custom_event_type,
            },
            "bid_strategy": "LOWEST_COST_WITHOUT_CAP",
            "targeting": targeting,
            "attribution_spec": [
                {"event_type": "CLICK_THROUGH", "window_days": 7},
                {"event_type": "VIEW_THROUGH", "window_days": 1},
            ],
            "status": "PAUSED",  # GUARDRAIL: ad set starts paused
        }

        ad_set = _ad_account(ad_account_id).create_ad_set(fields=[], params=params)
        return {
            "ad_set_id": ad_set["id"],
            "name": name,
            "status": "PAUSED",
            "daily_budget_cents": daily_budget_cents,
        }

    return _safely_call("create_ad_set", params_log, _do)


@mcp.tool()
def upload_video_creative(
    file_path: str,
    name: str,
    ad_account_id: Optional[str] = None,
) -> dict:
    """Upload an MP4 video to the ad account for use in ads.

    Args:
        file_path: Absolute path to the video file.
        name: Display name in Ads Manager.
        ad_account_id: Override default ad account.

    Returns: {video_id, name}
    """
    params_log = {"file_path": file_path, "name": name}

    def _do():
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Video not found at {file_path}")

        aid = _ad_account(ad_account_id).get_id_assured()
        video = AdVideo(parent_id=aid)
        video[AdVideo.Field.filepath] = file_path
        video[AdVideo.Field.name] = name
        video.remote_create()
        return {"video_id": video["id"], "name": name}

    return _safely_call("upload_video_creative", params_log, _do)


@mcp.tool()
def create_ad_creative(
    name: str,
    page_id: str,
    video_id: str,
    primary_text: str,
    headline: str,
    destination_url: str,
    cta_type: str = "LEARN_MORE",
    description: str = "",
    instagram_actor_id: Optional[str] = None,
    ad_account_id: Optional[str] = None,
) -> dict:
    """Create an Ad Creative from an uploaded video + ad copy.

    Args:
        name: Creative display name.
        page_id: Facebook Page ID that the ad runs under.
        video_id: ID returned by upload_video_creative.
        primary_text: Body copy (~125 char limit).
        headline: Headline above CTA (~40 char limit).
        destination_url: Where the CTA sends the user (e.g. the Stripe Payment Link).
        cta_type: LEARN_MORE, GET_OFFER, SHOP_NOW, SUBSCRIBE, SIGN_UP, etc.
        description: Optional description (~30 char limit).
        ad_account_id: Override default ad account.

    Returns: {creative_id, name}
    """
    params_log = {
        "name": name,
        "page_id": page_id,
        "video_id": video_id,
        "primary_text_len": len(primary_text),
        "headline": headline,
        "destination_url": destination_url,
        "cta_type": cta_type,
    }

    def _do():
        object_story_spec = {
            "page_id": page_id,
            "video_data": {
                "video_id": video_id,
                "title": headline,
                "message": primary_text,
                "call_to_action": {
                    "type": cta_type,
                    "value": {"link": destination_url},
                },
            },
        }
        # Meta now requires a thumbnail for video creatives. Pull the video's
        # auto-generated preferred frame and attach it as the thumbnail.
        try:
            _thumbs = AdVideo(video_id).get_thumbnails(fields=["uri", "is_preferred"])
            if _thumbs:
                _pref = next((t for t in _thumbs if t.get("is_preferred")), _thumbs[0])
                if _pref.get("uri"):
                    object_story_spec["video_data"]["image_url"] = _pref["uri"]
        except Exception:
            pass
        if description:
            object_story_spec["video_data"]["link_description"] = description
        # Run the ad under an Instagram account (e.g. the brand's IG with its
        # follower social proof) in addition to the Facebook Page.
        if instagram_actor_id:
            object_story_spec["instagram_actor_id"] = instagram_actor_id

        creative = _ad_account(ad_account_id).create_ad_creative(
            fields=[],
            params={
                "name": name,
                "object_story_spec": object_story_spec,
            },
        )
        return {"creative_id": creative["id"], "name": name}

    return _safely_call("create_ad_creative", params_log, _do)


@mcp.tool()
def create_ad(
    name: str,
    ad_set_id: str,
    creative_id: str,
    ad_account_id: Optional[str] = None,
) -> dict:
    """Create an Ad linking an Ad Creative to an Ad Set. Defaults to PAUSED.

    Args:
        name: Ad name.
        ad_set_id: Parent ad set ID.
        creative_id: Creative ID from create_ad_creative.
        ad_account_id: Override default ad account.

    Returns: {ad_id, name, status}
    """
    params_log = {"name": name, "ad_set_id": ad_set_id, "creative_id": creative_id}

    def _do():
        ad = _ad_account(ad_account_id).create_ad(
            fields=[],
            params={
                "name": name,
                "adset_id": ad_set_id,
                "creative": {"creative_id": creative_id},
                "status": "PAUSED",  # GUARDRAIL
            },
        )
        return {
            "ad_id": ad["id"],
            "name": name,
            "status": "PAUSED",
            "note": "Ad created but paused. activate_campaign() activates the entire chain.",
        }

    return _safely_call("create_ad", params_log, _do)


@mcp.tool()
def activate_campaign(campaign_id: str) -> dict:
    """Flip a campaign from PAUSED to ACTIVE. Requires explicit operator approval upstream.

    This is the ONLY tool that turns ad spend on. Use sparingly.
    """
    params_log = {"campaign_id": campaign_id}

    def _do():
        campaign = Campaign(campaign_id)
        campaign.api_update(params={"status": "ACTIVE"})
        # A campaign alone won't deliver while its ad sets / ads stay PAUSED.
        # Flip the whole chain ACTIVE so activation actually turns on spend.
        ad_sets, ads = [], []
        for aset in campaign.get_ad_sets(fields=["id"]):
            try:
                AdSet(aset["id"]).api_update(params={"status": "ACTIVE"})
                ad_sets.append(aset["id"])
            except Exception:
                pass
        for ad in campaign.get_ads(fields=["id"]):
            try:
                Ad(ad["id"]).api_update(params={"status": "ACTIVE"})
                ads.append(ad["id"])
            except Exception:
                pass
        return {
            "campaign_id": campaign_id,
            "status": "ACTIVE",
            "ad_sets_activated": ad_sets,
            "ads_activated": ads,
            "note": "Campaign + ad sets + ads set ACTIVE. Ads still under Meta review will deliver once approved.",
        }

    return _safely_call("activate_campaign", params_log, _do)


@mcp.tool()
def pause_ad_set(ad_set_id: str, force: bool = False) -> dict:
    """Pause an ad set. Without force=True, refuses to pause ad sets with <$50 spend or <3 days runtime.

    Args:
        ad_set_id: Ad set ID.
        force: Override safety guardrail. Use only when sure.
    """
    params_log = {"ad_set_id": ad_set_id, "force": force}

    def _do():
        ad_set = AdSet(ad_set_id)
        fields = [
            AdSet.Field.created_time,
            AdSet.Field.insights,
        ]
        ad_set.api_get(fields=fields)
        if not force:
            # Pull spend insights
            insights = ad_set.get_insights(fields=["spend"], params={"date_preset": "maximum"})
            spend = sum(float(i.get("spend", 0)) for i in insights)
            created = ad_set.get(AdSet.Field.created_time)
            runtime_days = None
            if created:
                created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                runtime_days = (datetime.now(created_dt.tzinfo) - created_dt).days
            if spend < 50 or (runtime_days is not None and runtime_days < 3):
                return {
                    "error": "PauseGuardrail",
                    "message": (
                        f"Refused: spend=${spend:.2f}, runtime={runtime_days}d. "
                        "Min $50 + 3d. Re-call with force=True if you really want to pause."
                    ),
                }
        ad_set.api_update(params={"status": "PAUSED"})
        return {"ad_set_id": ad_set_id, "status": "PAUSED"}

    return _safely_call("pause_ad_set", params_log, _do)


@mcp.tool()
def scale_ad_set_budget(ad_set_id: str, percent_change: float) -> dict:
    """Bump or cut an ad set's daily budget. Hard-capped at +/- 25% per call.

    Args:
        ad_set_id: Ad set ID.
        percent_change: e.g. 20 for +20%, -10 for -10%. Outside +/-25 is rejected.

    Returns: {ad_set_id, old_budget, new_budget, percent_change}
    """
    params_log = {"ad_set_id": ad_set_id, "percent_change": percent_change}

    def _do():
        if abs(percent_change) > 25:
            return {
                "error": "ScaleGuardrail",
                "message": f"Refused: |{percent_change}%| > 25%. Larger jumps trigger Meta's learning phase reset.",
            }
        ad_set = AdSet(ad_set_id)
        ad_set.api_get(fields=[AdSet.Field.daily_budget])
        old_budget = int(ad_set.get(AdSet.Field.daily_budget) or 0)
        if old_budget == 0:
            return {"error": "NoCurrentBudget", "message": "Ad set has no daily budget set."}
        new_budget = int(round(old_budget * (1 + percent_change / 100)))
        ad_set.api_update(params={"daily_budget": new_budget})
        return {
            "ad_set_id": ad_set_id,
            "old_budget_cents": old_budget,
            "new_budget_cents": new_budget,
            "percent_change": percent_change,
        }

    return _safely_call("scale_ad_set_budget", params_log, _do)


# === INSIGHTS ==============================================================

@mcp.tool()
def get_campaign_insights(
    campaign_id: str,
    date_preset: str = "last_7d",
) -> dict:
    """Pull performance metrics for a campaign.

    Args:
        campaign_id: Campaign ID.
        date_preset: today, yesterday, last_3d, last_7d, last_14d, last_28d, last_30d, this_month, last_month, maximum.

    Returns: dict of {spend, impressions, clicks, ctr, cpc, cpm, reach, frequency, actions (events)}
    """
    params_log = {"campaign_id": campaign_id, "date_preset": date_preset}

    def _do():
        insights = Campaign(campaign_id).get_insights(
            fields=[
                "spend",
                "impressions",
                "clicks",
                "ctr",
                "cpc",
                "cpm",
                "reach",
                "frequency",
                "actions",
                "cost_per_action_type",
                "video_thruplay_watched_actions",
                "video_p25_watched_actions",
            ],
            params={"date_preset": date_preset},
        )
        return [dict(i) for i in insights]

    return _safely_call("get_campaign_insights", params_log, _do)


@mcp.tool()
def get_ad_set_insights(
    ad_set_id: str,
    date_preset: str = "last_7d",
) -> dict:
    """Pull performance metrics for an ad set. Same date_preset options as get_campaign_insights."""
    params_log = {"ad_set_id": ad_set_id, "date_preset": date_preset}

    def _do():
        insights = AdSet(ad_set_id).get_insights(
            fields=[
                "spend",
                "impressions",
                "clicks",
                "ctr",
                "cpc",
                "cpm",
                "reach",
                "frequency",
                "actions",
                "cost_per_action_type",
            ],
            params={"date_preset": date_preset},
        )
        return [dict(i) for i in insights]

    return _safely_call("get_ad_set_insights", params_log, _do)


# === MAIN ==================================================================

if __name__ == "__main__":
    mcp.run()
