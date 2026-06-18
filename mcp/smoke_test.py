"""Smoke test: verify the System User token + SDK against the live ad account.
Reads only. Never prints the token."""
import os
from dotenv import load_dotenv
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

load_dotenv()
TOKEN = os.environ["META_ACCESS_TOKEN"]
ACCT = os.environ["META_DEFAULT_AD_ACCOUNT_ID"]
APP_ID = os.environ.get("META_APP_ID") or None
APP_SECRET = os.environ.get("META_APP_SECRET") or None

print("=== Token + SDK smoke test ===")
print(f"Account: {ACCT}")
print(f"App ID present: {bool(APP_ID)} | App secret present: {bool(APP_SECRET)}")

try:
    if APP_ID and APP_SECRET:
        FacebookAdsApi.init(APP_ID, APP_SECRET, TOKEN)
    else:
        FacebookAdsApi.init(access_token=TOKEN)
    print("SDK init: OK")
except Exception as e:
    print(f"SDK init: FAILED -> {type(e).__name__}: {e}")
    raise SystemExit(1)

acct = AdAccount(ACCT)

# 1) Account read
try:
    info = acct.api_get(fields=["name", "account_status", "currency", "amount_spent", "balance"])
    print("\n[1] Ad account read: OK")
    print(f"    name={info.get('name')}  status={info.get('account_status')}  currency={info.get('currency')}")
except Exception as e:
    print(f"\n[1] Ad account read: FAILED -> {type(e).__name__}: {e}")

# 2) Campaigns
try:
    camps = list(acct.get_campaigns(fields=["name", "status", "objective"], params={"limit": 25}))
    print(f"\n[2] Campaigns read: OK -> {len(camps)} campaign(s)")
    for c in camps[:10]:
        print(f"    - {c.get('name')} [{c.get('status')}] {c.get('objective','')}")
except Exception as e:
    print(f"\n[2] Campaigns read: FAILED -> {type(e).__name__}: {e}")

# 3) Custom audiences
try:
    auds = list(acct.get_custom_audiences(fields=["name", "subtype", "approximate_count_lower_bound", "delivery_status"], params={"limit": 25}))
    print(f"\n[3] Custom audiences read: OK -> {len(auds)} audience(s)")
    for a in auds[:10]:
        print(f"    - {a.get('name')} [{a.get('subtype','')}] ~{a.get('approximate_count_lower_bound','?')}")
except Exception as e:
    print(f"\n[3] Custom audiences read: FAILED -> {type(e).__name__}: {e}")

print("\n=== smoke test complete ===")
