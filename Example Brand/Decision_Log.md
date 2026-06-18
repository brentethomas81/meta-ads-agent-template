# [BRAND NAME] Meta Ads — Decision Log

Every recommendation the Performance Agent makes gets logged here. Outcomes filled in within 7 days to measure accuracy.

## Status Key
- **PENDING APPROVAL** — recommendation made, awaiting operator's call
- **APPROVED** — operator said yes, action executed
- **DENIED** — operator said no
- **EXECUTED** — completed, awaiting outcome data
- **LOGGED** — observation or context, no action

## Log

| Date | Time | Ad/Set | Recommendation | Confidence | Status | Outcome (7-day) | Agent Right? |
|------|------|--------|----------------|------------|--------|------------------|--------------|
| YYYY-MM-DD | HH:MM | [Ad Set Name or —] | [Plain-English description of the recommendation, with specific data + bucket + action] | 🟢/🟡/🔴 | PENDING | [Filled later] | Y/N |

## Accuracy Tracking (recompute monthly)

- Total recommendations: 0
- Approved: 0
- Denied: 0
- Agent right when approved: 0%
- Agent right when denied (counterfactual): N/A
- Confidence calibration: 🟢 correct __%, 🟡 correct __%, 🔴 correct __%

## Notes

- First entry = first scheduled briefing
- Agent reads this file before every session to learn from history
- Patterns of wrong recommendations trigger system prompt refinement
- Outcomes are tracked on a 7-day window from execution date
