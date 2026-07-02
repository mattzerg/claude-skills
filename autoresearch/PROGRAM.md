# autoresearch loop — instructions for the improving agent

This is the `program.md` of the autoresearch pattern (Karpathy): a frozen eval,
one editable target, keep only validated wins, log everything tried.

**Target (the only thing you may edit):** the SKILL.md of the skill under test.
**Frozen eval (never edit to make a number go up):** the golden cases file.
**Metric:** pass-rate (primary) → mean tokens (tiebreak, lower better) → mean wall.

## Loop

1. **Baseline.** `run.py eval --skill <NAME> --cases <cases> --runner claude`
   Record the pass-rate + cost. If pass-rate is already 1.0 and cost is low, stop —
   there's nothing to chase; don't churn the skill.
2. **Hypothesize one change.** Read the failing cases. Propose a *single* concrete
   edit to the SKILL.md (sharper trigger, clearer rule, a missing anti-pattern,
   a tighter example). Write it to a candidate copy, e.g. `/tmp/<name>.candidate.md`.
   One variable at a time — this is an experiment, not a rewrite.
3. **A/B.** `run.py ab --skill <NAME> --cases <cases> --variant /tmp/<name>.candidate.md --runner claude`
   The harness measures both, restores the original, and prints KEEP / REVERT.
4. **Keep wins only.** If KEEP, re-run with `--apply` to write the variant live.
   If REVERT, discard the candidate and try a different hypothesis.
5. **Log & repeat.** Every run is logged under `experiments/`. Keep a short note of
   what you tried and why it won/lost, so the next loop doesn't repeat dead ends.

## Rules (don't cheat the eval)
- Never edit the golden cases to pass — that's overfitting, not improvement.
- Change one thing per experiment. Compound edits hide which change mattered.
- A KEEP needs *real* signal: a higher pass-rate, or equal pass-rate at lower cost
  beyond `--tol`. Noise is not improvement.
- Add new golden cases when you find a real failure mode in the wild — grow the
  eval, then improve against it.

## Applies beyond skills
Karpathy's autoresearch is metric-agnostic. The same harness shape works for any
"editable artifact + frozen scorer + keep-wins" loop — e.g. cold-email templates
scored by reply-rate, or a landing variant scored by conversion. Swap the cases
file + runner; the keep/revert logic is identical.
