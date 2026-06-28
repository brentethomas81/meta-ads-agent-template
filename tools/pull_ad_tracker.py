import os, json, sys, time, stripe
sys.path.insert(0,'/app/daemon'); import stripe_data as sd
sys.path.insert(0,'/app/mcp'); import server
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adaccount import AdAccount
stripe.api_key=os.environ["STRIPE_API_KEY"]
CAMP="YOUR_CAMPAIGN_ID"; ACCT="act_REPLACE_ME"
# --- Meta campaign delivery (lifetime) ---
meta={}
try:
    ins=Campaign(CAMP).get_insights(params={"date_preset":"maximum"},
        fields=["spend","impressions","reach","frequency","clicks","inline_link_clicks","ctr","cpc","cpm","actions","date_start"])
    if ins:
        r=ins[0]; acts={a["action_type"]:a["value"] for a in (r.get("actions") or [])}
        meta={"spend":round(float(r.get("spend",0)),2),"impressions":int(r.get("impressions",0) or 0),
            "reach":int(r.get("reach",0) or 0),"frequency":round(float(r.get("frequency",0) or 0),2),
            "clicks":int(r.get("clicks",0) or 0),"link_clicks":int(r.get("inline_link_clicks",0) or 0),
            "ctr":round(float(r.get("ctr",0) or 0),2),"cpc":round(float(r.get("cpc",0) or 0),2),
            "cpm":round(float(r.get("cpm",0) or 0),2),"lpv":int(acts.get("landing_page_view",0) or 0),
            "start":r.get("date_start","")}
except Exception as e:
    meta={"error":str(e)[:120]}
acct_spend=int(AdAccount(ACCT).api_get(fields=["amount_spent"]).get("amount_spent",0))/100
# --- ad-driven subscribers (confirmed + signal) lifecycle from Stripe ---
tier={}
for s in sd._recent_sessions(120):
    e=sd._email(s)
    if not e or e in sd._TEST_EMAILS: continue
    t=sd.classify_session(s)
    if t=="confirmed": tier[e]="confirmed"
    elif t=="likely": tier.setdefault(e,"likely")
for e in sd._CONFIRMED_AD_EMAILS: tier.setdefault(e,"confirmed")
rows=[]
for e in sorted(tier):
    try:
        custs=json.loads(str(stripe.Customer.list(email=e, limit=1)))["data"]
        if not custs: 
            rows.append({"email":e,"plan":"(no Stripe customer)","status":"—","start":"","canceled":"","collected":0,"amount":0,"interval":""}); continue
        cid=custs[0]["id"]
        subs=json.loads(str(stripe.Subscription.list(customer=cid, status="all", limit=10)))["data"]
        invs=json.loads(str(stripe.Invoice.list(customer=cid, status="paid", limit=100)))["data"]
        paid=round(sum((i.get("amount_paid") or 0) for i in invs)/100.0,2)
        if subs:
            s=subs[0]; p=((s.get("items") or {}).get("data") or [{}])[0].get("price") or {}
            amt=(p.get("unit_amount") or 0)/100.0; iv=(p.get("recurring") or {}).get("interval")
            rows.append({"email":e,"plan":f"${amt:.2f}/{iv}","amount":amt,"interval":iv,"status":s.get("status"),
                "start":time.strftime("%Y-%m-%d",time.localtime(s.get("start_date") or s.get("created"))),
                "canceled":(time.strftime("%Y-%m-%d",time.localtime(s["canceled_at"])) if s.get("canceled_at") else ""),
                "collected":paid})
        else:
            rows.append({"email":e,"plan":"one-time","amount":0,"interval":"","status":"paid (no sub)","start":"","canceled":"","collected":paid})
    except Exception as ex:
        rows.append({"email":e,"plan":"err","status":str(ex)[:60],"start":"","canceled":"","collected":0,"amount":0,"interval":""})
for r in rows: r["tier"]=tier.get(r["email"],"confirmed")
json.dump({"meta":meta,"ad_spend":round(acct_spend,2),"ad_subs":rows,"generated":time.strftime("%Y-%m-%d %H:%M")}, open("/tmp/adtracker.json","w"))
print("DONE meta_spend",meta.get("spend"),"ad_subs",len(rows),
      "confirmed",sum(1 for r in rows if r.get("tier")=="confirmed"),
      "likely",sum(1 for r in rows if r.get("tier")=="likely"))
