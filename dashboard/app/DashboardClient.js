"use client";
import { useState, useMemo } from "react";

function money(n) { return "$" + (Number(n) || 0).toLocaleString(undefined, { maximumFractionDigits: 2 }); }
function cacText(c) { return c == null ? "—" : "$" + c.toFixed(2); }
const STATUS_COLOR = { GREEN: "#16a34a", YELLOW: "#ca8a04", RED: "#dc2626" };
const STATUS_DOT = { GREEN: "🟢", YELLOW: "🟡", RED: "🔴" };

export default function DashboardClient({ brands, vaults, health, loadedAt }) {
  const [open, setOpen] = useState(false);
  const items = useMemo(() => {
    const out = [];
    for (const b of brands) for (const c of b.campaigns) out.push({ key: `${b.id}:${c.id}`, brand: b, campaign: c });
    return out;
  }, [brands]);

  // view = {type:'campaign',key} | {type:'vault',id} | {type:'health'}
  const [view, setView] = useState(items.length ? { type: "campaign", key: items[0].key } : { type: "vault", id: "knowledge" });
  function pick(v) { setView(v); setOpen(false); }
  const current = view.type === "campaign" ? items.find((i) => i.key === view.key) : null;
  const hColor = health ? STATUS_COLOR[health.overall] : "#6b7280";

  return (
    <div className="shell">
      <header className="topbar">
        <button className="ham" aria-label="Menu" onClick={() => setOpen((o) => !o)}><span /><span /><span /></button>
        <div className="title">Meta Ads Agent</div>
        <button className="health-chip" onClick={() => pick({ type: "health" })} title="Agent Health">
          <span className="hdot" style={{ background: hColor }} /> health
        </button>
        <div className="loaded">live · {loadedAt} PT</div>
      </header>

      {open && <div className="scrim" onClick={() => setOpen(false)} />}
      <nav className={"drawer" + (open ? " show" : "")}>
        <div className="drawer-head">Campaigns</div>
        {brands.map((b) => (
          <div className="nav-brand" key={b.id}>
            <div className="nav-brand-name">{b.name}{!b.active && <span className="tag">stub</span>}</div>
            {b.active && b.campaigns.length === 0 && <div className="nav-empty">no campaigns</div>}
            {b.active && b.reason && <div className="nav-empty err-text">{b.reason}</div>}
            {b.campaigns.map((c) => {
              const key = `${b.id}:${c.id}`;
              const active = view.type === "campaign" && view.key === key;
              return (
                <button key={key} className={"nav-item" + (active ? " active" : "")} onClick={() => pick({ type: "campaign", key })}>
                  <span className="dot" style={{ background: c.verdict.color }} />
                  <span className="nav-item-name">{c.name}</span>
                </button>
              );
            })}
          </div>
        ))}
        <div className="drawer-head" style={{ marginTop: 18 }}>Vaults</div>
        <button className={"nav-item" + (view.type === "vault" && view.id === "knowledge" ? " active" : "")} onClick={() => pick({ type: "vault", id: "knowledge" })}>
          <span className="vdot">📚</span><span className="nav-item-name">Knowledge Vault</span>
        </button>
        <button className={"nav-item" + (view.type === "vault" && view.id === "learning" ? " active" : "")} onClick={() => pick({ type: "vault", id: "learning" })}>
          <span className="vdot">🧠</span><span className="nav-item-name">Recursive Learning</span>
        </button>
        <div className="drawer-head" style={{ marginTop: 18 }}>System</div>
        <button className={"nav-item" + (view.type === "health" ? " active" : "")} onClick={() => pick({ type: "health" })}>
          <span className="hdot" style={{ background: hColor }} /><span className="nav-item-name">Agent Health</span>
        </button>
      </nav>

      <main className="main">
        {view.type === "campaign" && current && <CampaignDetail brand={current.brand} c={current.campaign} />}
        {view.type === "campaign" && !current && <div className="empty-main">No campaigns yet. Launch one and it&apos;ll appear here.</div>}
        {view.type === "vault" && <VaultView title={view.id === "knowledge" ? "Knowledge Vault" : "Recursive Learning Vault"} subtitle={view.id === "knowledge" ? "The agent's media-buying brain — best practices it applies and teaches from." : "What actually worked for our brands — the agent gets smarter from real outcomes."} sections={vaults[view.id] || []} />}
        {view.type === "health" && <HealthView health={health} />}
      </main>
    </div>
  );
}

function HealthView({ health }) {
  if (!health) return <div className="empty-main">Health unavailable.</div>;
  return (
    <div className="detail">
      <div className="detail-head">
        <div>
          <div className="d-name">Agent Health</div>
          <div className="d-sub">Live breakage-point checks — re-run on every page load.</div>
        </div>
        <span className="pill" style={{ background: STATUS_COLOR[health.overall] }}>{STATUS_DOT[health.overall]} {health.overall}</span>
      </div>
      <div className="health-list">
        {health.checks.map((c, i) => (
          <div className="health-row" key={i}>
            <span className="hdot" style={{ background: STATUS_COLOR[c.status] }} />
            <div className="health-text"><div className="health-name">{c.name}</div><div className="health-detail">{c.detail}</div></div>
          </div>
        ))}
      </div>
      <div className="legend">🟢 healthy · 🟡 needs attention / not built yet · 🔴 broken — fix now. The most common 🔴 is the Meta token; regenerate it and update the .env + Fly secret.</div>
    </div>
  );
}

function VaultView({ title, subtitle, sections }) {
  return (
    <div className="vault">
      <div className="vault-head"><div className="d-name">{title}</div><div className="d-sub">{subtitle}</div></div>
      {sections.length === 0 && <div className="empty-main">Vault is empty.</div>}
      {sections.map((s) => (<div className="md" key={s.file} dangerouslySetInnerHTML={{ __html: s.html }} />))}
    </div>
  );
}

function CampaignDetail({ brand, c }) {
  const v = c.verdict;
  return (
    <div className="detail">
      <div className="detail-head">
        <div>
          <div className="d-brand">{brand.name} · target CAC {money(brand.targetCac)}</div>
          <div className="d-name">{c.name}</div>
          <div className="d-sub">{c.objective} · {c.ageDays != null ? `day ${c.ageDays}` : "age n/a"}{c.ageDays != null && c.ageDays < 15 ? " (learning phase)" : ""} · {brand.adAccountId}</div>
        </div>
        <div className="d-badges">
          <span className="status">{c.status}</span>
          <span className="pill" style={{ background: v.color }}>{v.label}</span>
        </div>
      </div>
      <div className="big-cac" style={{ borderColor: v.color }}>
        <div className="k">Cost per acquisition (CAC)</div>
        <div className="v" style={{ color: v.color }}>{cacText(c.cac)}</div>
        <div className="hint">{c.conversions} conversion{c.conversions === 1 ? "" : "s"} · {money(c.spend)} spent</div>
      </div>
      <div className="metrics">
        <div className="metric"><div className="k">Spend</div><div className="v">{money(c.spend)}</div></div>
        <div className="metric"><div className="k">Conversions</div><div className="v">{c.conversions}</div></div>
        <div className="metric"><div className="k">Clicks</div><div className="v">{c.clicks}</div></div>
        <div className="metric"><div className="k">CTR</div><div className="v">{(c.ctr || 0).toFixed(2)}%</div></div>
        <div className="metric"><div className="k">CPC</div><div className="v">{money(c.cpc)}</div></div>
        <div className="metric"><div className="k">Impressions</div><div className="v">{(c.impressions || 0).toLocaleString()}</div></div>
      </div>
      <div className="legend">🟢 SCALE · 🟡 HOLD · 🟠 WATCH · 🔴 PAUSE — vs. {brand.name}&apos;s ladder (softer thresholds during the first 14 days).</div>
    </div>
  );
}
