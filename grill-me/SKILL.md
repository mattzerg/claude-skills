---
name: grill-me
description: Relentless self-adversarial interrogation of a plan, design, or decision until every branch of the decision tree is resolved or explicitly deferred with a reason. Maps the full decision tree, attacks each open branch (assumptions, failure modes, reversibility, "what would make this wrong"), and refuses to conclude while any branch is unresolved. Different from brainstorming (divergent idea generation, runs BEFORE), careful (caution posture on a single risky action), and fakeidan/cross-model-check (an EXTERNAL second model's pass) — grill-me is the INTERNAL closure pass that pressure-tests Matt's own plan before it ships. Adapted from mattpocock/skills `/grill-me` (2026-06-07 setup-ideas evaluation). USE PROACTIVELY when Matt says "grill me", "poke holes", "interrogate this plan", "what am I missing", "stress-test this", "am I sure about X", or before committing to any non-trivial, hard-to-reverse plan.
---

# grill-me

**Purpose.** A plan can look complete and still hide unresolved branches: an assumption never checked, a failure mode never named, a fork silently decided by default. `grill-me` is the disciplined closure pass — it interrogates a plan until every branch is either **resolved** (with the reasoning) or **deferred** (with an explicit reason and trigger to revisit). It is self-adversarial: the goal is to find the weakness *now*, not after shipping.

This is the Matt-native adaptation of `mattpocock/skills` `/grill-me` (surfaced via a self-sent reel, evaluated 2026-06-07 — see `MattZerg/Skills/setup-ideas-evaluation-2026-06.md`).

## When to use vs. siblings

| Skill | Role | Timing |
|---|---|---|
| `brainstorming` | Generate options, explore the space | BEFORE a plan exists |
| **`grill-me`** | **Close every branch of a chosen plan** | AFTER a plan, BEFORE commit |
| `careful` | Caution posture on one risky action | At the action |
| `fakeidan` / `cross-model-check` | External second-opinion pass | At review/gate |

Run `grill-me` after `brainstorming` and `writing-plans`, before `pr-gate` / execution. It is not a substitute for the external passes — it's the internal one that should make them boring.

## The loop

1. **State the plan in one sentence + list its decisions.** Force the plan into an explicit decision tree. Every "we'll do X" is a node. Every node with an unstated alternative is an **open branch**.
2. **For each open branch, attack it** with the question battery below. Do not move on until the branch is resolved or deferred-with-reason.
3. **Surface hidden branches** — the decisions made silently by default ("we just assumed the API is idempotent"). These are the dangerous ones.
4. **Refuse to conclude while any branch is open.** End with a branch ledger: every branch marked `RESOLVED <why>` or `DEFERRED <reason + revisit trigger>`. No branch may be left `OPEN`.

## Question battery (per branch)

- **Assumption:** What must be true for this to work? Have we *checked* it, or *assumed* it? How would we know if it's false?
- **Failure mode:** What's the worst realistic outcome if this branch is wrong? Who/what breaks?
- **Reversibility:** If this is wrong, how expensive is the undo? (One-way doors get more grilling.)
- **Falsifier:** What single fact, if we learned it, would make this the wrong call? Can we cheaply go learn it now?
- **Alternative:** What did we *not* choose here, and why is the chosen path strictly better — or just defaulted?
- **Evidence:** Is this grounded in something read/measured, or in a vibe? Cite it.
- **Scope creep / blast radius:** Does this branch quietly expand what we're touching?

## Output

A **branch ledger**, e.g.:

```
PLAN: <one sentence>
├─ Branch: store tokens in config.json
│   RESOLVED — moved to env; falsifier (works offline) checked.
├─ Branch: assume MCP server is idempotent on retry
│   DEFERRED — low blast radius; revisit if retries observed in logs.
└─ Branch: skip migration backfill
│   OPEN ← cannot conclude. Need: row count + cost of backfill.
```

If any branch is `OPEN`, the verdict is **NOT READY** — name exactly what's needed to close it.

## Anti-patterns

- Don't accept "it'll probably be fine" — that's an unresolved branch wearing a confident hat.
- Don't grill cosmetics; grill the **load-bearing** decisions and the **one-way doors**.
- Don't turn it into infinite bikeshedding — a branch resolved with a cited reason is *closed*, move on.
- Don't use it to relitigate something already decided and recorded — check `decision-queue` / prior plans first.
