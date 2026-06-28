import os, json, sys, time, stripe
sys.path.insert(0,'/app/daemon'); import stripe_data as sd
sys.path.insert(0,'/app/mcp'); import server
from facebook_business.adobjects.adaccount import AdAccount
stripe.api_key=os.environ["STRIPE_API_KEY"]
def pages(fn, **kw):
    out=[]; sa=None
    while True:
        pg=json.loads(str(fn(limit=100, starting_after=sa, **kw) if sa else fn(limit=100, **kw)))
        out+=pg["data"]
        if not pg.get("has_more") or not pg["data"]: break
        sa=pg["data"][-1]["id"]
    return out
subs=pages(stripe.Subscription.list, status="all", expand=["data.customer"])
invs=pages(stripe.Invoice.list, status="paid")
TEST=sd._TEST_EMAILS
ad_emails=set(sd._CONFIRMED_AD_EMAILS)
for s in sd._recent_sessions(120):
    if sd._is_ad_driven(s):
        e=sd._email(s)
        if e and e not in TEST: ad_emails.add(e)
collected={}
for inv in invs:
    e=(inv.get("customer_email") or "").lower(); collected[e]=collected.get(e,0)+(inv.get("amount_paid") or 0)/100.0
def cemail(s):
    c=s.get("customer"); return (c.get("email") or "").lower() if isinstance(c,dict) else ""
rows=[]
for s in subs:
    e=cemail(s)
    if e in TEST: continue
    p=((s.get("items") or {}).get("data") or [{}])[0].get("price") or {}
    amt=(p.get("unit_amount") or 0)/100.0; iv=(p.get("recurring") or {}).get("interval")
    rows.append({"email":e,"plan":f"${amt:.2f}/{iv}","amount":amt,"interval":iv,"status":s.get("status"),
        "start":time.strftime("%Y-%m-%d",time.localtime(s.get("start_date") or s.get("created"))),
        "canceled":(time.strftime("%Y-%m-%d",time.localtime(s["canceled_at"])) if s.get("canceled_at") else ""),
        "collected":round(collected.get(e,0),2),"is_ad": e in ad_emails})
spend=int(AdAccount("act_REPLACE_ME").api_get(fields=["amount_spent"]).get("amount_spent",0))/100
json.dump({"rows":rows,"ad_spend":round(spend,2),"generated":time.strftime("%Y-%m-%d %H:%M")}, open("/tmp/subs.json","w"))
print("DONE rows=",len(rows))
