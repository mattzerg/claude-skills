# Ship Gate Patterns

Use these patterns when deciding whether something is ready to ship.

## Pattern 1: Readiness is evidence, not vibe

A ship call should rely on explicit artifacts:

- review output
- launch runbook
- metric spec
- experiment doc
- screenshot or asset review

If the evidence is missing, the gate is not green.

## Pattern 2: Five common blocker classes

- message / claim blocker
- CTA / flow blocker
- proof / trust blocker
- measurement blocker
- ownership / operations blocker

Name the class, not just the symptom.

## Pattern 3: External ship requires proof discipline

When broad claims are in play, ask:

- is the cost-saving claim evidenced or framed as directional?
- is the custom-systems claim backed by examples or clients?
- is the shared-data / AI-underpinning claim visible anywhere concrete?
- are we promising implementation capacity we can actually support?

Broad positioning is allowed. Unproven broad positioning is a blocker.

## Pattern 4: Yellow is useful

Use `yellow` when:

- the artifact is good enough for internal review, advisors, or design iteration
- the main issue is external-proof or operational readiness
- the launch can proceed in a narrower way than originally planned

`yellow` is not failure. It is controlled scope.

## Pattern 5: Path to green should be finite

Every blocker should convert into:

- one owner
- one artifact or fix
- one verification step

If the path to green is vague, the gate is not doing its job.
