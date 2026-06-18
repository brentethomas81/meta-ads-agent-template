# Recursive Learning Vault

The agent's **memory of what actually worked** — the loop that makes it smarter every campaign.

## How the loop works
1. **Decision** — every Scale/Hold/Watch/Pause call is logged to `decision_log.md` with the metrics + diagnosis that drove it.
2. **Outcome** — when the result is known (did CAC move the way we predicted?), it's recorded against that decision.
3. **Lesson** — patterns that repeat become entries in `lessons_learned.md` (e.g., "for this brand, the X angle beat Y at 1.4× lower CAC").
4. **Feedback** — brand-specific lessons are injected back into the agent's next analysis and **override the general benchmarks** in the Knowledge Vault once a brand has 20+ closed conversions.

## Hard rule
Learning improves the **advice and teaching only**. It NEVER changes a money guardrail (budget caps, paused-by-default, ±25% scaling) on its own. Threshold/ladder changes require a deliberate, human-approved edit.

## Files
- **decision_log.md** — the running record of every call + its outcome.
- **lessons_learned.md** — the distilled, transferable lessons per brand.
- **outcomes (daemon):** once the daemon is live, closed-campaign outcomes also write to a SQLite store on the daemon's volume; this markdown stays the human-readable mirror.

## Status
Empty by design — the first entries arrive once your campaign launches and starts converting. The structure is ready so the very first decision gets captured.
