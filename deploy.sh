#!/bin/zsh
# Deploy gate (Lucille pattern: never deploy what didn't boot).
# Usage: ./deploy.sh          — test, then deploy the bot
set -e
cd "$(dirname "$0")"
echo "1/2 boot smoke test..."
python3 tests/test_boot.py
echo "2/2 deploying bot (health-gated on Fly side)..."
~/.fly/bin/flyctl deploy --remote-only -c fly.bot.toml
echo "DONE — Fly only promoted the new machine after /health passed."
