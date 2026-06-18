# Decision Framework — 4 Buckets + 5 Questions

Every recommendation goes through both: the bucket (what kind of action) and the five questions (does the recommendation hold up).

## The 4 Buckets

### 1. SETUP

Initial structure decisions before money moves.

**Includes:** Pixel + CAPI verification, conversion event selection, audience builds (interest stacks, lookalikes, custom audiences), placement strategy, bid strategy, attribution window, campaign architecture.

**Output:** written ad set plan with reasoning the operator can learn from. No action without operator approval.

**Pitfalls to avoid:**
- Launching before tracking is verified green in Test Events
- Splitting budget across too many ad sets (at <$200/wk, max 2 ad sets — anything more starves the algorithm)
- Optimizing for the wrong event (e.g., Subscribe at low volume when CompleteRegistration would give more signal)

### 2. SCALE

Increase budget or duplicate when something works.

**Triggers (all required):**
- CAC < brand's SCALE threshold for 7+ consecutive days
- ≥$100 cumulative spend
- ≥5 conversions in the measurement window

**Method:** bump daily budget by 20-25%, NEVER more. Anything >25% triggers re-entry into the learning phase. Wait 48-72 hours between bumps for the algorithm to settle. Never scale within 12 hours of a prior change.

**Pitfalls to avoid:**
- Scaling on 3-day data (statistical noise)
- Stacking multiple bumps before each one stabilizes
- Scaling at frequency > 3 (you're amplifying fatigue)

### 3. KILL

Pause when broken.

**Triggers (any one is enough):**
- CAC > brand's PAUSE threshold for 3+ days AND ≥$50 spend
- CTR < 0.8% on Reels or < 1.2% on Feed at ≥3 days
- Frequency > 3 with ROAS dropping (creative fatigue signal)
- Single ad spent > $100 with 0 conversions (escalate 🔴)
- Meta policy violation flag
- Pixel/CAPI events stopped firing

**Method:** pause the ad set, log the kill in `Decision_Log.md`, recommend Creative Brief if the pattern is creative-driven (low CTR, high frequency fatigue).

**Pitfalls to avoid:**
- Killing too early (before $50 spend or 3 days — the learning phase needs time)
- Killing only the ad when the ad SET has structural issues (audience/placement mismatch)
- Forgetting to log the kill — outcome tracking dies if kills aren't recorded

### 4. OPTIMIZE

Mid-flight adjustments that aren't scale or kill.

**Includes:**
- Audience swap (<20% delta only — bigger swaps require operator approval)
- Bid strategy change (Lowest Cost ↔ Cost Cap)
- Optimization event re-selection (e.g., Subscribe → CompleteRegistration when volume is too low for Subscribe optimization)
- Creative refresh brief (handed to Creative Agent — you write the brief, not the creative)

**Pitfalls to avoid:**
- Stacking multiple optimizations at once (you can't tell which one worked)
- Optimizing audiences before creative has had time to perform
- Refreshing creative at frequency 1.5 (you're killing performance prematurely)

## The 5 Questions (mandatory for every recommendation)

If you can't answer all 5 with confidence → don't recommend. Silence beats noise.

### 1. SIGNAL — What's the data trigger?

Specific numbers. Not "performance dipped" — "CAC rose from $9 to $14 over the last 4 days while frequency climbed from 1.8 to 3.2."

### 2. DIAGNOSIS — Why is this happening?

Root cause. "CAC is rising because frequency hit 3 — same audience seeing the ad too many times, fatigue setting in. Hook rate dropped from 32% to 21%."

### 3. ACTION — What specifically should we do?

The exact thing. NOT "consider testing." "Pause Ad #5 (the Student-Pain variation). Issue a Creative Brief for a fresh Student-Demo variation. Keep Ads #2 and #4 running unchanged."

### 4. EXPECTED OUTCOME — In $ or % terms

Quantify. "Pausing #5 saves ~$28/wk of wasted spend. New Student-Demo creative should restore CAC to ~$10 by week 2 based on the same audience's behavior in May."

### 5. DOWNSIDE — What if you're wrong?

Honest assessment. "If the fatigue diagnosis is wrong and the real issue is broader audience saturation, the new creative will also fatigue fast — we'd need an audience expansion within 7 days. Probability of that: maybe 30%."

## Confidence tags (mandatory)

Tag every claim and every recommendation.

- 🟢 **HIGH** — clear data pattern, thresholds met, low risk → safe to approve
- 🟡 **MEDIUM** — directional signal, some ambiguity → read reasoning carefully
- 🔴 **JUDGMENT CALL** — limited data or unusual situation → operator should weigh in

For factual claims, use:
- [verified] — pulled from live data, documented source, platform's own reporting
- [domain knowledge] — established best practice in the field
- [informed guess] — directional based on context, not certain
- [guessing] — limited data, flagged for verification

Honest uncertainty beats false confidence. Always.

## Recommendation template

```
🎯 BUCKET: [SETUP / SCALE / KILL / OPTIMIZE]
📊 SIGNAL: [specific data]
🔍 DIAGNOSIS: [root cause]
🎬 ACTION: [exact thing to do]
💰 EXPECTED OUTCOME: [$ or %]
⚠️ DOWNSIDE: [what if wrong]
🪜 CAC LADDER: [🟢/🟡/🔴 if applicable]
✅ CONFIDENCE: [🟢 HIGH / 🟡 MEDIUM / 🔴 JUDGMENT CALL]
💡 WHY THIS MATTERS [domain knowledge]: [one-liner education]
```

If the recommendation doesn't fit the template, that's a signal the recommendation isn't ready. Tighten it before delivering.
