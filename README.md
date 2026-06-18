# Meta Ads Agent — Template

A **standalone, multi-brand Meta Ads management system** you can stand up for your own
brand(s). It replaces UI-driven Meta Ads work with API-driven automation through three pieces:

- **`mcp/`** — a Meta Marketing API server exposing campaigns/ad sets/ads/audiences/insights
  as guardrailed tools.
- **`daemon/`** — an always-on **two-way Slack agent** (Socket Mode). DM it or @mention it and
  it answers as a senior media buyer, reading the knowledge + learning vaults each time. Posts
  one daily briefing per brand that's actively spending, and asks for approval before any money
  action (Scale / Pause buttons).
- **`dashboard/`** — a Next.js dashboard showing each brand's live campaigns, CAC traffic-lights
  vs. its ladder, plus the knowledge & learning vaults and an agent-health view.

It also ships the **agent's brain**:
- **`AGENT_INSTRUCTIONS.md`**, **`CAC_Ladder_Framework.md`**, **`Decision_Framework.md`** — the
  universal Performance Agent role, decision buckets, and CAC ladder.
- **`knowledge/`** — curated media-buying best practice + 2025–26 benchmarks (the reusable brain).
- **`learning/`** — the recursive-learning vault (decisions → outcomes → lessons); starts empty.
- **`Templates/`** — blank per-brand templates (Playbook, Audience Map, Decision Log, Creative Brief).
- **`Example Brand/`** — a starter brand folder you rename/duplicate.

## Quick start
**Read [`SETUP.md`](SETUP.md)** — it walks you through, in order:
1. Generate your Meta System User token
2. Create your Slack app (from `daemon/slack_app_manifest.yaml`)
3. Get an Anthropic API key
4. Configure your brand(s) in `dashboard/lib/brands.js` + `daemon/brands.py`
5. Deploy the dashboard and the bot to Fly

## Project structure
```
Meta Ads Agent Template/
├── AGENT_INSTRUCTIONS.md, CAC_Ladder_Framework.md, Decision_Framework.md
├── knowledge/            ← curated media-buying brain (reusable as-is)
├── learning/             ← recursive-learning vault (starts empty)
├── Templates/            ← blank per-brand templates
├── Example Brand/        ← starter brand — rename/duplicate per brand
├── mcp/                  ← Meta Marketing API MCP server (+ .env.example)
├── daemon/               ← Slack Socket-Mode agent (+ .env.example, manifest)
├── dashboard/            ← Next.js dashboard (Fly)
├── Dockerfile.bot, fly.bot.toml   ← deploy the bot to Fly
└── SETUP.md              ← START HERE
```

## What you provide (your own accounts)
Your Meta Business + ad account, a Slack workspace, an Anthropic API key, and a Fly.io account.
No secrets are committed to this repo — you supply all credentials via `.env` (local) or Fly
secrets (production).
