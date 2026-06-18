// Server-only: live health checks for the agent's breakage points.
import fs from "fs";
import path from "path";
import { BRANDS } from "./brands";

const API = "https://graph.facebook.com/v21.0";
const TOKEN = process.env.META_ACCESS_TOKEN;

function check(name, status, detail) { return { name, status, detail }; }

async function metaProbe(adAccountId) {
  const url = `${API}/${adAccountId}?fields=name,account_status&access_token=${encodeURIComponent(TOKEN || "")}`;
  const res = await fetch(url, { cache: "no-store" });
  const json = await res.json().catch(() => ({}));
  return { ok: !json.error, json };
}

export async function getHealth() {
  const checks = [];

  // 1. Token present
  if (!TOKEN) {
    checks.push(check("Meta access token", "RED", "META_ACCESS_TOKEN is not set on the dashboard. The agent can't reach Meta."));
  } else {
    checks.push(check("Meta access token", "GREEN", `Configured (${TOKEN.length} chars).`));
  }

  // 2. Meta API + token validity, per active brand
  if (TOKEN) {
    for (const b of BRANDS.filter((b) => b.active && b.adAccountId)) {
      try {
        const { ok, json } = await metaProbe(b.adAccountId);
        if (ok) {
          const active = json.account_status === 1;
          checks.push(check(`Meta API · ${b.name}`, active ? "GREEN" : "YELLOW",
            active ? `Reachable. Account "${json.name}" active.` : `Reachable but account_status=${json.account_status} (not active).`));
        } else {
          const msg = (json.error && json.error.message) || "unknown error";
          const isAuth = /token|OAuth|session|permission/i.test(msg);
          checks.push(check(`Meta API · ${b.name}`, isAuth ? "RED" : "YELLOW", `${isAuth ? "AUTH/permission problem" : "API error"}: ${msg}`));
        }
      } catch (e) {
        checks.push(check(`Meta API · ${b.name}`, "RED", `Could not reach Meta: ${e.message}`));
      }
    }
  }

  // 3. Vault files present
  for (const [label, dir] of [["Knowledge Vault", "knowledge"], ["Recursive Learning Vault", "learning"]]) {
    try {
      const files = fs.readdirSync(path.join(process.cwd(), "content", dir)).filter((f) => f.endsWith(".md"));
      checks.push(check(label, files.length ? "GREEN" : "YELLOW", `${files.length} file(s) loaded.`));
    } catch {
      checks.push(check(label, "RED", "Vault folder missing from the deploy."));
    }
  }

  // 4. Graph API version watch (informational)
  checks.push(check("Graph API version", "GREEN", "Pinned to v21.0. Watch the Meta changelog for its sunset date (see Knowledge Vault → sources_and_updates)."));

  // 5. Daemon (not deployed yet)
  checks.push(check("Briefing daemon", "YELLOW", "Not deployed yet — 6 AM/6 PM Slack briefings + two-way bot are on the roadmap (ARCHITECTURE §7)."));

  // 6. Dashboard itself
  checks.push(check("Dashboard", "GREEN", "Serving — you're looking at it."));

  const overall = checks.some((c) => c.status === "RED") ? "RED" : checks.some((c) => c.status === "YELLOW") ? "YELLOW" : "GREEN";
  return { overall, checks };
}
