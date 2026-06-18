# Authoritative Sources & Update Tracking

> Where the agent pulls fresh, official knowledge — and how often each source changes. The agent web-searches/reads these on demand; a scheduled "knowledge refresh" (future) will check the changelogs automatically and flag changes. Today: refresh the dated files in this vault quarterly, or whenever a changelog below ships a major version.

## Meta / Facebook Ads — official

| Resource | What it is | Update cadence | Link |
|---|---|---|---|
| Graph + Marketing API **Changelog** | Deprecated endpoints, new fields, version notes (our API runs on this) | New version every ~few months (v24, v25…); each version deprecates after ~2 years | https://developers.facebook.com/docs/graph-api/changelog |
| API **Versions / deprecation schedule** | Exact sunset dates per version | Updated each release | https://developers.facebook.com/docs/graph-api/changelog/versions/ |
| Marketing API docs | The endpoints we call | Continuous | https://developers.facebook.com/docs/marketing-api/ |
| Meta for Business **News** | Product/ad-policy/feature announcements | Ongoing (multiple/month) | https://www.facebook.com/business/news |
| Meta Business **Help Center** | How features/policies work | Ongoing | https://www.facebook.com/business/help |
| Meta **Blueprint** (training) | Official courses/best practices | Periodic | https://www.facebook.com/business/learn |

**Why it matters for us:** our MCP is pinned to a Graph API version (currently v21.0). When the changelog announces that version's sunset, we bump it — the Agent Health tab and a future knowledge-refresh job should surface it before it breaks.

## Google Ads — official (secondary / future brands)

| Resource | What it is | Update cadence | Link |
|---|---|---|---|
| Google Ads API **Release Notes** | Version changes, deprecations | **Monthly** from v23 (2026) — was quarterly | https://developers.google.com/google-ads/api/docs/release-notes |
| API **Versioning** | Support windows per version | Per release | https://developers.google.com/google-ads/api/docs/concepts/versioning |
| "Stay updated" | Subscribe to release notifications | — | https://developers.google.com/google-ads/api/docs/productionize/stay-updated |
| Google Ads **Developer Blog** | Release announcements | Per release | https://ads-developers.googleblog.com/ |
| Google Ads **Help** | Feature/policy docs | Ongoing | https://support.google.com/google-ads |
| **Think with Google** | Research, benchmarks, best practice | Ongoing | https://www.thinkwithgoogle.com/ |

## Industry benchmark sources (for metric_benchmarks.md refresh)
WordStream, LocaliQ, Triple Whale, WebFX, Madgicx — published annually/quarterly. Re-pull the benchmark numbers each quarter and update `metric_benchmarks.md` (date it).

## Refresh protocol
1. **Quarterly** (or on a major changelog release): re-read the changelogs above; update `meta_platform_2026.md`, `metric_benchmarks.md`, and bump the API version if a sunset is announced.
2. **On demand**: the agent can web-search any of these live during a session to answer "what changed recently?"
3. **Future automation**: a scheduled task checks the Meta + Google changelogs weekly and posts a "platform changed" alert to Slack + flags it on the Agent Health tab. (Not built yet — noted in ARCHITECTURE §9 oversight.)

## Sources for this file
- Meta Graph API Changelog: https://developers.facebook.com/docs/graph-api/changelog
- Google Ads API Release Notes: https://developers.google.com/google-ads/api/docs/release-notes
- Social Media Today — Meta Marketing API updates: https://www.socialmediatoday.com/news/meta-updates-marketing-api-to-align-with-latest-ad-shifts/812648/
- Google Ads Developer Blog (v23 monthly cadence): https://ads-developers.googleblog.com/2026/01/announcing-v23-of-google-ads-api.html
