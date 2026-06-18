// Minimal Meta Marketing API client (server-side only — uses the System User token).
const API = "https://graph.facebook.com/v21.0";
const TOKEN = process.env.META_ACCESS_TOKEN;

async function metaGet(path, params = {}) {
  const url = new URL(`${API}/${path}`);
  url.searchParams.set("access_token", TOKEN || "");
  for (const [k, v] of Object.entries(params)) url.searchParams.set(k, v);
  const res = await fetch(url.toString(), { cache: "no-store" });
  const json = await res.json();
  if (json.error) throw new Error(json.error.message || "Meta API error");
  return json;
}

// Count purchase/subscribe conversions out of an insights "actions" array.
export function countConversions(actions) {
  if (!Array.isArray(actions)) return 0;
  let n = 0;
  for (const a of actions) {
    if (/purchase|subscribe/i.test(a.action_type)) n += Number(a.value || 0);
  }
  return n;
}

function daysSince(iso) {
  if (!iso) return null;
  const d = (Date.now() - new Date(iso).getTime()) / 86400000;
  return Math.floor(d);
}

// Returns campaigns for a brand with spend, conversions, CAC, age.
export async function getBrandCampaigns(brand) {
  if (!brand.adAccountId || !TOKEN) return { ok: false, reason: !TOKEN ? "No token configured" : "No ad account set", campaigns: [] };
  try {
    const fields =
      "name,status,objective,start_time,insights.date_preset(maximum){spend,actions,impressions,clicks,cpc,ctr,reach}";
    const data = await metaGet(`${brand.adAccountId}/campaigns`, { fields, limit: "100" });
    const campaigns = (data.data || []).map((c) => {
      const ins = c.insights && c.insights.data && c.insights.data[0];
      const spend = ins ? Number(ins.spend || 0) : 0;
      const conversions = ins ? countConversions(ins.actions) : 0;
      const cac = conversions > 0 ? spend / conversions : null;
      return {
        id: c.id,
        name: c.name,
        status: c.status,
        objective: c.objective,
        ageDays: daysSince(c.start_time),
        spend,
        conversions,
        cac,
        impressions: ins ? Number(ins.impressions || 0) : 0,
        clicks: ins ? Number(ins.clicks || 0) : 0,
        ctr: ins ? Number(ins.ctr || 0) : 0,
        cpc: ins ? Number(ins.cpc || 0) : 0,
      };
    });
    // Hide stale/legacy campaigns (e.g. the old paused Traffic campaign) so the
    // dashboard stays focused on what's active or being set up now: keep ACTIVE
    // campaigns and anything created within the last 45 days; drop long-paused ones.
    const visible = campaigns.filter(
      (c) => c.status === "ACTIVE" || c.ageDays == null || c.ageDays <= 45
    );
    return { ok: true, campaigns: visible };
  } catch (e) {
    return { ok: false, reason: e.message, campaigns: [] };
  }
}
