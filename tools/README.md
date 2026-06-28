# tools/ — data pulls + spreadsheet builders for the trackers

These power the Desktop subscription / ad-campaign trackers and their daily 6 AM refresh
(scheduled task "pickle-subscriptions-tracker-daily").

Pipeline: a `pull_*.py` runs ON the Fly bot (it has the Stripe + Meta credentials) and writes a
JSON to `/tmp`; that JSON is downloaded; a `build_*_xlsx.py` turns it into the Excel file on the Desktop.

- **pull_subs.py** — runs on the Fly bot (kept at `/data/pull_subs.py`). Paginates ALL Stripe
  subscriptions + paid invoices, tags ad-driven sales (via `daemon/stripe_data.py`), writes `/tmp/subs.json`.
- **pull_ad_tracker.py** — runs on the Fly bot (`/data/pull_ad_tracker.py`). Pulls the Meta campaign
  delivery metrics + the ad-driven customers' lifecycle from Stripe, writes `/tmp/adtracker.json`.
- **build_tracker_xlsx.py** — runs locally (needs `openpyxl`). `subs.json` -> whole-business
  "Subscriptions & Ad ROI" workbook.
- **build_ad_tracker_xlsx.py** — runs locally (needs `openpyxl`). `adtracker.json` -> focused
  "Ad Campaign Tracker" workbook (the current one).

Note: the `pull_*` scripts live on the bot's persistent `/data` volume so they survive redeploys.
Build the file as a pure openpyxl workbook (no LibreOffice recalc) so it opens cleanly in Microsoft Excel.
