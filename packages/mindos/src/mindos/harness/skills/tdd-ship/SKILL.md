---
name: tdd-ship
description: Ship a small feature test-first, red-green-refactor, push once green.
version: 1
author: mindos-harness
created_at: "2026-04-19"
trigger_keywords: [tdd, test first, red green, ship endpoint, ship feature]
---

# tdd-ship

## When to use
The user asks to add a small, well-scoped feature (an endpoint, a helper, a
CLI flag) and wants it to land behind tests. Avoid for large refactors, for
migrations that touch state, or for anything where you don't already know
the shape of the answer.

## Steps
1. Read the surrounding code — understand the existing patterns before touching them.
2. Write the failing test first. One test, the smallest one that proves the
   feature doesn't exist yet. Run it, see it fail, note the error.
3. Implement the minimum to make it green. Don't widen scope. Don't refactor.
4. Run the full test suite — not just the new test. If regressions appear,
   fix them before moving on.
5. Refactor the new code for clarity if it earned it. Leave surrounding code
   alone.
6. Commit with a message that explains *why*, not what. Push when green.

## Notes
- Never commit with failing tests, even with `-f` or `--no-verify`.
- Coverage means nothing; one good test beats five that only exercise happy paths.
- If the test is hard to write, the API is probably wrong — stop and rethink.
- This skill advertises behavior; the harness does not auto-run the steps.
  A human or a `run_skill()` runner executes them.
