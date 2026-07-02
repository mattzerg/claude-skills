---
name: qa-gate
description: Gate engineering-loop correctness for significant code changes before opening a PR or invoking ship-gate. Use when Codex is making or preparing to ship non-trivial code edits, migrations, release/deploy changes, dependency upgrades, CI changes, auth/payment/data-handling changes, UI behavior changes, or any production-facing change. Discovers repo-appropriate checks, assigns a sticky risk tier, runs tests, runs fakeidan code review feedback, fixes findings, reruns tests, and reports evidence before final handoff.
---

# QA Gate

## Overview

Use this skill as the pre-ship loop for meaningful code work. It makes `fakeidan` feedback a required part of the engineering cycle, paired with concrete test evidence before and after fixes.

## Dependencies

- Requires the external Claude skill runner at `~/.claude/skills/fakeidan/run.py`.
- Assumes the fakeidan runner accepts positional artifact paths plus `--mode`, `--out-dir`, `--quick`, and `--model`.
- Assumes `fakeidan --quick` still emits the mandatory review shape, including `**Verdict:**` and `## Concerns ranked`; `scripts/run_fakeidan.py` treats missing mandatory shape as `UNABLE_TO_RUN`.
- If this contract drifts, inspect `~/.claude/skills/fakeidan/SKILL.md`, update `scripts/run_fakeidan.py`, and rerun the qa-gate self-tests.
- Fakeidan reviews and manifests are persisted under `~/.codex/artifacts/qa-gate/` by default. Set `QA_GATE_ARTIFACT_ROOT` only for tests or temporary isolated runs.
- `scripts/run_fakeidan.py` keeps the newest 50 passed artifact directories plus the newest 50 blocked artifact directories by default; override with `--retain-artifacts` and `--retain-failures` when a task needs a shorter or longer local audit trail. Values below 1 disable that retention class rather than clearing artifacts.
- When `CLAUDE_BIN` is unset, `scripts/run_fakeidan.py` prefers `~/.config/zerg/zclaude` if executable so reviews use the local Claude account router.
- Codex runtime note: `zclaude` uses Claude Code OAuth in the macOS Keychain. Codex's normal sandbox cannot read that credential, and Claude reports the failure as `Not logged in · Please run /login`. When running `scripts/run_fakeidan.py` from Codex, run the top-level command with escalated permissions rather than retrying inside the sandbox.

## Trigger Threshold

Run this gate when any trigger predicate matches. Trigger Threshold answers whether `qa-gate` runs at all; Risk Tier answers how heavy the loop is once the gate is running.

- Multiple files or shared modules.
- User-facing behavior, UI flow, API contract, persistence, auth, payments, permissions, secrets, deployments, migrations, CI, dependencies, or generated assets used in production.
- Bug fixes where regression risk matters.
- Any request that mentions shipping, deploying, publishing, merging, release readiness, or production.

If no trigger predicate matches, the full gate is not required unless the user asks for it. Still run normal lightweight verification appropriate to the edit.

## Workflow

1. Inspect the repo state.
   - Run `git status --short`.
   - Identify files changed by this task versus unrelated pre-existing changes.
   - Do not revert unrelated user changes.
   - If the workspace is not a git checkout, state that and use the user request, file timestamps, or direct file inspection to scope the change.

2. Discover the repo's quality commands.
   - Inspect likely sources before choosing commands: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Makefile`, CI config, README/developer docs, and nearby existing test files.
   - When useful, run `python3 ~/.claude/skills/qa-gate/scripts/discover_quality_commands.py <repo-root>` to list POSIX-shell candidate commands. Treat its output as discovery, not an instruction to run everything.
   - Prefer commands already used by the repo over inventing new ones.
   - If several commands exist, choose the smallest set that covers the changed behavior and the final shipping risk.
   - If dependencies must be installed or network access is required, request escalation through the normal tool approval flow.

3. Assign a risk tier and choose the test surface.
   - Low risk: isolated helper, copy-only behavior, local style fix, or tightly scoped code path with no production state. Run targeted tests or the smallest relevant check.
   - Medium risk: multiple files, shared components, user-facing behavior, API changes, dependency bumps, or bug fixes with plausible regressions. Run targeted tests plus the repo's relevant lint/typecheck/build checks.
   - High risk: auth, payments, permissions, secrets, data migrations, persistence, production deploys, CI/release workflow, broad refactors, or security-sensitive code. Run focused checks, broad tests, build/typecheck/lint where available, and a named smoke/manual verification path.
   - High-risk smoke examples: auth should cover login, logout, and session expiry or refresh; payments should cover a staging or sandbox round trip; migrations should cover up/down or rollback on a copy of the relevant schema; deploys should cover health endpoint, core user path, and rollback command or note.
   - High-risk smoke checks are author-driven unless a repo command is discovered. The gate enforces that the check is named, run, waived, or blocked; it does not automatically discover every payment, migration, auth, or deploy smoke command.
   - The test surface is sticky to the initial risk tier. The final label may de-escalate only with documented evidence in `De-escalation evidence:`; do not silently shrink the post-review test surface.

4. Run the initial verification.
   - Execute the chosen tests/checks before final review when practical.
   - If tests fail, determine whether failures are caused by the current changes, pre-existing state, missing environment, or sandbox limits.
   - Fix current-change failures before proceeding.

5. Run `fakeidan` in code mode through the qa-gate wrapper.
   - Use the wrapper so preflight, review persistence, verdict parsing, and `UNABLE_TO_RUN` normalization stay consistent:

```bash
python3 ~/.claude/skills/qa-gate/scripts/run_fakeidan.py <artifact_path> --mode code --quick
```

   - The wrapper emits JSON with `verdict`, `status`, `review_files`, per-review `verdicts`, `manifest_path`, and `error`. Its exit code reports whether fakeidan ran and parsed; parse `verdict` for gate status.
   - Manifest JSON uses `schema_version: 2` and includes `claude_bin` so the review runner source is auditable. Validate persisted manifests with `python3 ~/.claude/skills/qa-gate/scripts/validate_manifest.py <manifest.json>` before consuming them in another gate or audit tool.
   - On malformed review output, `review_files` contains all markdown reviews copied from fakeidan before parsing; the manifest is complete-but-blocked rather than partial.
   - Review the changed file set or the smallest directory that covers the change coherently.
   - For broad changes, pass multiple paths or the relevant module directory rather than the entire repo. When multiple paths are passed, the wrapper bundles them into one temporary markdown artifact so fakeidan performs one review call instead of one Claude call per file.
   - If the wrapper reports `UNABLE_TO_RUN`, the gate is not cleared unless the user explicitly waives the blocker. A manual Idan-style review is useful context, not a substitute for a passed gate.

6. Fix the findings.
   - Treat `Pre-merge blocker`, `Changes requested`, and concrete correctness concerns as required fixes unless the finding is demonstrably inapplicable.
   - For each inapplicable finding, record the reason briefly.
   - Avoid broad refactors unless they are necessary to satisfy the finding safely.

7. Test again.
   - Rerun the focused tests that cover the fixes.
   - Rerun the broader build/lint/typecheck/test gate used before review when the change is medium or high risk.
   - If any check cannot run, state why and what residual risk remains.

8. Rerun review when the fix changed the design.
   - Run `fakeidan` again if the first review produced blockers, the fix touched additional modules, or the final patch materially differs from what was reviewed.
   - Do not rerun `fakeidan` for small mechanical fixes unless the user asks or the risk tier is high.

## Cross-Model Verification

This skill runs `cross-model-check` (always-on) alongside `fakeidan` — Claude gives a second opinion on the same artifact. Findings flow into the manifest via two new keys:

- `xmodel_review` — path to the cross-model review markdown (null if skill not installed)
- `xmodel_status` — one of `null` (didn't run), `"ok"` (no HIGH), `"high"` (HIGH findings present), `"skipped"` (other model unavailable / rate-limited / timeout)

When `xmodel_status == "high"` the manifest goes to `status: BLOCKED` even if fakeidan returned `verdict: Approve`. Callers (pr-gate, Codex agents) must respect both signals.

Opt-out: `--no-cross-model` flag, or env var `QA_GATE_SKIP_XMODEL=1` (set automatically by pr-gate to avoid double-firing since pr-gate runs its own xmodel pass). Don't use the opt-out casually — always-on is the point.

Auto-skips during unit/test runs (detected via `sys.argv[0]` + `sys.modules`) so test fixtures don't burn real API tokens.

Manifest schema bumped to **v3** for this — see `scripts/validate_manifest.py`.

## Adjacent Skill Routing

- Use `fakeidan` for the review pass; this skill orchestrates when and how it gates code work.
- `cross-model-check` runs in parallel — Claude second-opinion. See its SKILL.md.
- Use `playwright-skill` for meaningful browser UI changes, screenshots, logged-in flows, or visual interaction checks. Run those checks as part of step 4 when UI behavior changed, and rerun them in step 7 if fixes touched UI.
- Use `github-pr-identity` before pushing, publishing a branch, creating a PR, or requesting reviews.
- Use `pr-gate` before opening a pull request.
- Use `ship-gate` when the user asks whether a broader page, launch, workflow, or production release is ready to ship.
- `pr-gate` consumes qa-gate manifests automatically when opening PRs; `ship-gate` does not yet, so copy the verdict and manifest path into broader ship handoffs manually.
- Use domain-specific review skills when the changed artifact is not primarily code: `brand-check`, `graphic-layout`, `video-review`, `launch-announcement`, or `fakematt-*` as appropriate.

## Waiver Policy

Do not silently waive failed checks or review findings.

- Waivable with explanation: missing optional tooling, sandbox-only failures, unrelated pre-existing failures, flaky tests with clear prior evidence, or findings that do not apply to the changed code.
- Not waivable without explicit user direction: known correctness bugs, data-loss risk, security/auth/payment/permission defects, broken production build, failing migration, or failed deploy smoke check.
- Not waivable by the agent alone: inability to run `fakeidan` for a medium/high-risk change.
- If a check cannot run, name the command, the blocker, and the risk left uncovered.
- If a `fakeidan` finding is not fixed, state whether it is inapplicable, deferred, or needs user decision.

## Final Handoff

Use this shape for significant code work:

- Change: `<one sentence>`
- Risk tier (initial): `Low | Medium | High`, with the reason.
- Risk tier (final): `Low | Medium | High`
- De-escalation evidence: required if final tier is lower than initial tier; otherwise `none`.
- `fakeidan verdict`: `Approve | Recommend changes | Changes requested | UNABLE_TO_RUN`
- `fakeidan output paths`: paths if available.
- `fakeidan findings addressed`: numbered list or `none`.
- `fakeidan findings deferred / inapplicable`: numbered list with reason per item, or `none`.
- Tests before fixes: commands and outcomes, if run.
- Tests after fixes: commands and outcomes.
- Not run / not cleared: commands/checks skipped, with reason, residual risk, and whether the user explicitly waived the blocker.
- `qa-gate status`: `PASSED | BLOCKED | WAIVED_BY_USER`

Gate passes only if `fakeidan` ran, post-fix tests ran, and there are no unaddressed `fakeidan` blockers. If `fakeidan` could not run, the change is not cleared by this gate; report the blocker and wait for an explicit user waiver before claiming readiness.

Validate a completed handoff with:

```bash
python3 ~/.claude/skills/qa-gate/scripts/validate_final_handoff.py <handoff.md>
```

## Practical Defaults

- Node: check `package.json` scripts; typical order is targeted test, `npm run typecheck`, `npm run lint`, `npm run build`, then full tests if available.
- Python: check project config; typical order is targeted `pytest`, lint/typecheck if configured, then broader `pytest`.
- Rust: run targeted tests when possible, then `cargo test`; include `cargo clippy` or `cargo fmt --check` when configured.
- Go: run targeted package tests, then `go test ./...`; include format/vet checks when configured.
- Frontend apps: for visual or interaction changes, use the app's browser/screenshot workflow when available in addition to unit/build checks.
- Deployments: include the build artifact check, migration validation when relevant, deploy dry run when available, rollback note, and post-deploy smoke command.

## Skill Self-Tests

Before editing this skill's helper scripts, run:

```bash
cd ~/.claude/skills/qa-gate/scripts
python3 test_discover_quality_commands.py
python3 test_parse_fakeidan_verdict.py
python3 test_run_fakeidan.py
python3 test_validate_final_handoff.py
python3 test_validate_manifest.py
```

These self-tests are stdlib-only and do not require the real fakeidan runner or Claude binary. On Python versions before 3.11, `pyproject.toml` discovery degrades gracefully because stdlib `tomllib` is unavailable.

## Anchors

This gate inherits voice and pattern from the skills it orchestrates (fakeidan, cross-model-check, plus downstream pr-gate / ship-gate handoff). References:

- Voice index: `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_voice_patterns.md`
- Pattern catalog: `/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/feedback_patterns_catalog.md`
- Upstream skills' own anchors apply transitively.
- **Catalog patterns to cite by slug** (Section A Universal / process): honest-scoping, bundling-rule
- **Catalog patterns to cite by slug** (Section D Idan-bar (code / security)): right-shape, verify-then-parse, dedup-before-side-effects, schema-enforced-invariants, boot-time-fail-fast, ssrf-defense, two-dot-three-dot-diff
- **Catalog patterns to cite by slug** (Section H Consultant / process): product-type-detection, harness-fidelity

Findings surfaced by this gate should cite pattern slugs from the catalog.
