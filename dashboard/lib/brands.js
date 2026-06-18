// Brand registry — one entry per Meta ad account you manage.
// Duplicate the example block for each brand. Values come from each brand's Playbook.md.
// IMPORTANT: keep this in sync with daemon/brands.py (and the id must match a folder
// listed in daemon/config.py BRAND_DIRS).

export const BRANDS = [
  {
    id: "example-brand",            // url-safe id; also the key in daemon/config.py BRAND_DIRS
    name: "Example Brand",          // display name shown in the dashboard + briefings
    adAccountId: "act_REPLACE_ME",  // your Meta ad account (prefix with act_)
    currency: "USD",
    targetCac: 15,                  // your target cost per acquisition ($)
    // Post-learning ladder (ad-set age >= 15 days)
    ladder: { scaleBelow: 10, holdMax: 20, pauseAbove: 25 },
    // Learning-phase ladder (days 1-14) — softer thresholds
    learningLadder: { scaleBelow: 12, holdMax: 25, pauseAbove: 35 },
    active: true,                   // set false to keep as a stub (not fetched)
  },
  // Add more brands by copying the block above with new id / name / adAccountId / ladder.
];

// Given a CAC, ad-set age in days, and a brand, return the ladder verdict.
export function ladderVerdict(cac, ageDays, brand) {
  if (cac == null || !isFinite(cac)) return { tier: "NODATA", label: "No data", color: "#6b7280" };
  const l = ageDays != null && ageDays < 15 && brand.learningLadder ? brand.learningLadder : brand.ladder;
  if (!l) return { tier: "NODATA", label: "No ladder", color: "#6b7280" };
  if (cac < l.scaleBelow) return { tier: "SCALE", label: "SCALE", color: "#16a34a" };
  if (cac <= l.holdMax) return { tier: "HOLD", label: "HOLD", color: "#ca8a04" };
  if (cac > l.pauseAbove) return { tier: "PAUSE", label: "PAUSE", color: "#dc2626" };
  return { tier: "WATCH", label: "WATCH", color: "#ea580c" }; // between holdMax and pauseAbove
}
