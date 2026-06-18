# CAC Ladder Framework — Universal Decision Compass

The CAC Ladder is the single most important decision tool a Meta Ads buyer uses. It compresses complex P&L logic into three clear actions: **Scale, Hold, or Pause.**

This file defines the STRUCTURE. Each brand's Playbook supplies the actual dollar VALUES.

## Universal structure

| Tier | Action | Method |
|---|---|---|
| 🟢 SCALE | CAC below brand's SCALE threshold for 7+ days AND ≥$100 spend AND ≥5 conversions | Bump daily budget +20-25%, wait 48-72h, reassess |
| 🟡 HOLD | CAC inside brand's HOLD range | Watch. No action. Algorithm still finding pockets. |
| 🔴 PAUSE | CAC above brand's PAUSE threshold for 3+ days OR conditional triggers | Pause the ad set. Log it. Recommend Creative Brief if pattern is creative-driven. |

## How brands set their thresholds (in their Playbook)

Each brand fills in three numbers based on LTV math:

- **SCALE threshold:** CAC at which the campaign is instantly profitable (typically ≤ 50% of LTV)
- **HOLD range:** CAC where the campaign is marginally profitable (50-100% of LTV with positive payback inside 30 days)
- **PAUSE threshold:** CAC where the campaign destroys value (> 100% of LTV with no retention upside)

Example formula:
```
LTV = $20
SCALE = LTV × 0.40 = $8        (2.5x payback at acquisition)
HOLD  = LTV × 0.40 to LTV × 0.80 = $8-$16
PAUSE = LTV × 1.00 = $20        (any worse and we're losing money per acquisition)
```

## Why this matters [domain knowledge]

CAC ceilings are set by LTV, not by what you can afford to spend. A SCALE call without LTV underwriting it is just a guess. A PAUSE call without LTV math is leaving money on the table.

## Adjustments for budget level

At small spend (<$500/wk):
- Default to 🟡 HOLD until thresholds are clearly met
- 🟢 SCALE should be RARE — small samples lie
- Require BOTH the $100 cumulative spend AND 5 conversions before any SCALE call
- The agent's confidence tag should usually be 🟡 MEDIUM even when CAC looks great

At medium spend ($500-$2K/wk):
- Standard thresholds apply
- Statistical significance is reachable in 5-7 days
- 🟢 HIGH confidence becomes possible

At scale spend (>$2K/wk):
- Multi-ad-set portfolio decisions, not single-ad calls
- ROAS curves matter more than instantaneous CAC

## Learning phase vs post-learning

**Days 1-14 of an ad set (learning phase):** tolerate higher CAC because Meta is still figuring out delivery. Use a softer SCALE threshold (typically 1.5x normal) and a wider HOLD range.

**Days 15+ (post-learning):** hold the ad set to the brand's normal thresholds. The algorithm has enough data.

## When the ladder doesn't apply

- **Pre-launch / waiting for tracking** → no CAC ladder, no spend, no recommendations
- **Test ads under $50 spend** → directional only, no action
- **Policy-paused ads** → fix the policy issue first, ladder is irrelevant
- **Account-level pacing issue** → escalate 🔴, ladder doesn't address structural problems

## How to communicate a ladder call

Use this format in every recommendation:

```
🎯 BUCKET: [SCALE / KILL / OPTIMIZE]
📊 CAC: $[X] over [Y] days, [Z] conversions, $[W] spend
🪜 LADDER: 🟢 SCALE / 🟡 HOLD / 🔴 PAUSE
ACTION: [exact thing to do]
WHY THIS MATTERS [domain knowledge]: [one-liner education]
DOWNSIDE: [what happens if I'm wrong]
```

If the call doesn't fit cleanly into the ladder, flag it 🔴 and ask for operator input rather than forcing a tier.
