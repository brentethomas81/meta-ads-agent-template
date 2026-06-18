# SETUP — stand up your own Meta Ads Agent

Follow these in order. Budget ~30–45 minutes. You provide your own accounts; nothing here
shares state with anyone else's setup.

## 0. What you'll need
- A **Meta Business** with an ad account + a conversions pixel/dataset
- A **Slack workspace** you can add an app to
- An **Anthropic API key** (platform.claude.com)
- A **Fly.io** account (hosting) with `flyctl` installed and `fly auth login` done
- A **GitHub** account (to hold your copy of this repo)
- Python 3.12+ and Node 18+ locally

---

## 1. Meta System User token
1. Go to **business.facebook.com → Business Settings → System Users**.
2. Create a System User (e.g. "Meta Ads Agent"), **Generate token**, and grant scopes:
   `ads_management`, `ads_read`, `business_management`, `pages_read_engagement`.
3. Add assets to the token: your **ad account** and **pixel**.
4. Note these four values — you'll need them:
   - Access token (long string)
   - Ad account ID (looks like `act_1234…`)
   - Business/Portfolio ID
   - Pixel/dataset ID

Put them in **`mcp/.env`** (copy from `mcp/.env.example`).

---

## 2. Slack app (two-way bot)
1. Go to **api.slack.com/apps → Create New App → From a manifest**, pick your workspace.
2. Paste the contents of **`daemon/slack_app_manifest.yaml`** (it pre-sets all scopes,
   events, Socket Mode, and interactivity). Create the app.
3. **Install App → Install to Workspace → Allow.** Copy the **Bot User OAuth Token** (`xoxb-…`).
4. **Basic Information → App-Level Tokens → Generate Token and Scopes**, name it `socket`,
   add scope **`connections:write`**, Generate. Copy it (`xapp-…`).
5. **Basic Information → App Credentials → Signing Secret → Show.** Copy it.
6. **App Home →** enable the **Messages Tab** and check **"Allow users to send … messages
   from the messages tab"**, then **reinstall** the app (Install App → Reinstall) so DMs work.

Put `xoxb…`, `xapp…`, and the signing secret in **`daemon/.env`** (copy from `daemon/.env.example`).

---

## 3. Anthropic API key
1. **platform.claude.com → API keys → Create key.** Copy it (`sk-ant-…`) into `daemon/.env`
   as `ANTHROPIC_API_KEY`.
2. Recommended: **Billing → Email notifications** — add an alert at a monthly $ amount so spend
   never surprises you. (Realistic cost is small: ~$5 hosting + a few cents per briefing/question.)

---

## 4. Configure your brand(s)
Edit **both** registries (keep them in sync):
- `dashboard/lib/brands.js`
- `daemon/brands.py`

Set `id`, `name`, your `adAccountId` (`act_…`), `targetCac`, and the CAC ladder thresholds.
Then in **`daemon/config.py`**, make sure `BRAND_DIRS` maps each brand `id` to its folder.

Rename **`Example Brand/`** to your brand and fill in its `Playbook.md` (the blank
`Templates/` files show the format). Repeat the block to add more brands later.

---

## 5. Deploy
Push your copy to **your** GitHub, then deploy two Fly apps from the repo root.

```bash
# pick unique app names and set them in fly.bot.toml and dashboard/fly.toml
# (they currently say CHANGEME-…)

# --- Dashboard ---
cd dashboard && fly apps create <your-dashboard-name> && fly deploy --remote-only && cd ..

# --- Bot daemon ---
fly apps create <your-bot-name>
fly volumes create meta_ads_data -a <your-bot-name> -r <region> -n 1 -s 1 --yes
# load ALL secrets from your local .env files straight into Fly (values never printed):
{ grep -E '^(SLACK_|ANTHROPIC_)' daemon/.env; grep -E '^META_' mcp/.env; } | fly secrets import -a <your-bot-name>
fly deploy -c fly.bot.toml -a <your-bot-name> --remote-only
```

Check the bot booted: `fly logs -a <your-bot-name>` should show
`⚡️ Bolt app is running!` and `bot up (Socket Mode)`.

---

## 6. Test
In Slack, open the **app's DM** (under *Apps* in the sidebar) and message it, e.g.
*"what's our CAC ladder and when would you pause an ad set?"* It should answer in the
Performance Agent's voice. Ask it to do something that spends money and it replies with
**Approve / Pass** buttons instead of acting.

The daily briefing posts once per day **only when a brand has an ACTIVE campaign** — so it
stays quiet (and free) until you launch.

---

## 7. How it fits together
```
   Slack  ←──websocket──►  Bot daemon (Fly)  ──imports──►  mcp/server.py  ──►  Meta API
                                  │  reads
                                  ▼
                    AGENT_INSTRUCTIONS + knowledge/ + learning/ + brand Playbook
                                  │
                          Anthropic API (the brain)

   Dashboard (Fly)  ──►  Meta API (live campaign metrics + CAC ladder)
```

Secrets live only in your `.env` files (local) and as Fly secrets (production) — never in git.
