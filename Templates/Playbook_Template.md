# [BRAND NAME] Meta Ads — Playbook
**Last updated:** YYYY-MM-DD

> This file inherits role, frameworks, and behavior from `../Meta Ads Agent/AGENT_INSTRUCTIONS.md`.
> It captures ONLY brand-specific data: budget, account IDs, CAC thresholds, audiences, funnel.

## Account Identity

- **Brand:** [Brand Name]
- **Domain:** [example.com]
- **Operator:** [Your name]
- **Objective:** [Monthly subscribers / Leads / Purchases / etc.]
- **Primary conversion event:** [Subscribe / Purchase / Lead / CompleteRegistration]
- **Subscription / unit price:** [$X.XX]
- **Strategy frame:** [Volume play / Margin play / Mixed]

## Budget Reality

- **Weekly spend:** $[X]
- **Monthly spend:** ~$[X] (4.3 weeks)
- **Target blended CAC:** $[X]
- **Realistic monthly conversions at target CAC:** [N]

### Budget context

At $[X]/week the account is in [LEARN / GROW / SCALE] mode. That means:
- Maximum [N] active ad sets at a time
- Each ad set needs ~$[X] cumulative spend AND ≥5 conversions before signal is conclusive
- Default confidence tag is [🟡 MEDIUM / 🟢 HIGH] until proven otherwise

## CAC Ladder (brand-specific values)

LTV: $[X]
Payback target: [N] days

| Tier | Threshold | Action |
|---|---|---|
| 🟢 SCALE | CAC < $[X] | Bump daily budget +20-25%, wait 48-72h |
| 🟡 HOLD | CAC $[X] - $[Y] | Watch. No action. |
| 🔴 PAUSE | CAC > $[Z] | Pause ad set, log it, brief Creative Agent if creative-driven |

### Learning phase ladder (days 1-14)

| Tier | Threshold |
|---|---|
| 🟢 SCALE | CAC < $[X] |
| 🟡 HOLD | CAC $[X] - $[Y] |
| 🔴 PAUSE | CAC > $[Z] |

## Funnel

- **Landing page / ad CTA destination:** [URL]
- **Checkout type:** [Stripe Payment Link / Custom checkout / Lead form]
- **Funnel steps:** Ad → [URL] → [Step 2] → [Conversion]
- **Tracking:**
  - Browser Pixel: [Pixel ID]
  - CAPI: [implementation method — Stripe-Meta marketplace app / custom webhook / GTM server-side]
  - Domain verification: [verified Y/N]

## Audiences in Play

1. **[Audience name]** — [hypothesis]
2. **[Audience name]** — [hypothesis]
3. **[Audience name]** — [hypothesis]

At low budget, test ONE audience at launch. Expand only after first winner emerges.

**Custom audience seed:** [name and source]
**1% LAL:** [audience name]

## Angle Library

- **Angle 1: [name]** — [one-line description]
- **Angle 2: [name]** — [one-line description]
- **Angle 3: [name]** — [one-line description]

At launch, run ONE angle per audience.

## Account Setup Status

- [ ] Meta Business Portfolio: [name + ID]
- [ ] Ad Account: [name + ID]
- [ ] Meta Pixel created: [name + ID]
- [ ] CAPI configured
- [ ] Domain added to portfolio
- [ ] Domain verified (meta tag deployed + Verify button clicked)
- [ ] Aggregated Event Measurement priorities set (primary event = #1)
- [ ] Data connector wired (Coupler.io / Pipeboard / native)
- [ ] First test purchase end-to-end verified
- [ ] First campaign launched

## Channels

- **Active:** [Reels 9:16, Feed 1:1, ...]
- **Tested but not active:** [...]
- **Never run:** [TikTok — shut down across operator portfolio]

## Notes from operator

[Empty — agent appends manual overrides and observations here]

## Hard Guardrails Specific to This Brand

[Any brand-specific rules layered on top of the universal guardrails in `AGENT_INSTRUCTIONS.md`. Examples: "Never reference [competitor]", "Never run ads in [region]", "Always include disclaimer X".]
