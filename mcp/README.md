# Meta Ads MCP server

A local **stdio MCP server** that wraps the Meta Marketing API as agent-callable tools
(list/create campaigns, ad sets, ads, audiences, insights, scale/pause — with guardrails
baked in). The Slack daemon imports these same functions directly; you can also register
the server with a desktop MCP client (e.g. Claude Desktop) for interactive use.

## Configure
1. Copy `.env.example` → `.env` and fill in your Meta values (see the top-level **SETUP.md**, step 1, for how to generate a System User token).
2. Create the virtualenv and install deps:
   ```bash
   python3 -m venv .venv && ./.venv/bin/pip install -r requirements.txt
   ```

## Run locally (smoke test)
```bash
./.venv/bin/python smoke_test.py     # verifies the token + lists campaigns/audiences
```

## Register with a desktop MCP client (optional)
Point the client at `./.venv/bin/python` running `server.py` (absolute paths), with the
working directory set to this `mcp/` folder. Anything the server touches at startup
(the audit DB) resolves relative to the script folder, so it works regardless of the
client's launch directory.

## Guardrails (enforced in code, not just docs)
- Campaigns/ad sets default to **PAUSED**; `activate_campaign()` is the only path to ACTIVE.
- `scale_ad_set_budget` caps changes at **±25%**.
- `pause_ad_set` without `force=True` refuses ads with <$50 spend or <3 days runtime.
- Every call is logged to a local SQLite `audit.db`.

See the top-level **SETUP.md** for the full deployment walkthrough.
