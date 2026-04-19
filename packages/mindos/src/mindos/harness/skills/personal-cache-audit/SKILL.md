---
name: personal-cache-audit
description: Audit prompt-cache TTL usage in the last N harness runs and flag 5m TTL regressions.
version: 1
author: mindos-harness
created_at: "2026-04-19"
trigger_keywords: [cache audit, prompt cache, ttl, cache_ttl, cache regression]
---

# personal-cache-audit

## When to use
Before the monthly Anthropic bill lands. Claude silently flipped the default
prompt-cache TTL from `1h` back to `5m` on 2026-03-06 — if your backend is
not asking for `ttl="1h"` explicitly, your long-lived agent is paying
20-32% more tokens than necessary. Run this to verify every harness call in
your recent history explicitly requested `1h`.

## Steps
1. Query the most recent 100 EvoLog rows with `event_type="harness_run"`.
2. For each row, read `details.cache_ttl_used` (the value the backend
   actually requested).
3. Count the rows grouped by TTL. Expected shape for production Claude:
   100% `"1h"`. Stub/offline runs report `"none"` and are exempt.
4. If any row shows `"5m"` or an empty string on a Claude backend, the
   backend config drifted — open the offending module and check it passes
   `cache_ttl="1h"` on construction.
5. Report the summary (date range, totals per TTL, suspects) to the user.

## Notes
- The fix is always in the backend constructor, not in the harness loop.
- Kimi/OpenAI backends don't support prompt caching; expect `"none"` there.
- This skill advertises behavior; `run_skill()` may implement the query if
  you wire one. Without a runner, the harness surfaces the steps as advice.
