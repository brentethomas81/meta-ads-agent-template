import { BRANDS, ladderVerdict } from "../lib/brands";
import { getBrandCampaigns } from "../lib/meta";
import { getVaults } from "../lib/vaults";
import { getHealth } from "../lib/health";
import DashboardClient from "./DashboardClient";

export const dynamic = "force-dynamic"; // always pull live data

export default async function Page() {
  const brands = [];
  for (const b of BRANDS) {
    if (!b.active) {
      brands.push({ id: b.id, name: b.name, active: false, campaigns: [] });
      continue;
    }
    const { ok, reason, campaigns } = await getBrandCampaigns(b);
    let list = campaigns || [];
    // No live campaign yet -> show a zeroed "awaiting launch" scaffold instead of a
    // blank screen, so the dashboard reads "ready and waiting", not broken/empty.
    if (ok && list.length === 0) {
      list = [{
        id: "__none__", name: "No active campaign", status: "—", objective: "Awaiting launch",
        ageDays: null, spend: 0, conversions: 0, cac: null, clicks: 0, ctr: 0, cpc: 0, impressions: 0,
        placeholder: true,
      }];
    }
    brands.push({
      id: b.id,
      name: b.name,
      active: true,
      adAccountId: b.adAccountId,
      targetCac: b.targetCac,
      ok,
      reason: reason || null,
      campaigns: list.map((c) => ({ ...c, verdict: ladderVerdict(c.cac, c.ageDays, b) })),
    });
  }
  const vaults = getVaults();
  const health = await getHealth();
  const loadedAt = new Date().toLocaleString("en-US", { timeZone: "America/Los_Angeles" });
  return <DashboardClient brands={brands} vaults={vaults} health={health} loadedAt={loadedAt} />;
}
