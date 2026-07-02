# cross-model-check

Second-opinion gate that asks the OTHER LLM in Matt's stack to review an artifact. Closes the missing Codex→Claude direction (Claude→Codex was already covered by the `codex` skill).

## Layout

```
~/.claude/skills/cross-model-check/
├── SKILL.md                          # frontmatter + WHEN/HOW/anti-patterns
├── README.md                         # this file
├── run.py                            # dispatcher
└── scripts/
    ├── detect_active_model.py        # env-var sniff
    ├── invoke_codex.py               # Claude→Codex shell-out (codex exec --json)
    ├── invoke_claude.py              # Codex→Claude shell-out (claude -p --output-format json)
    ├── check_rate_limit.py           # pre-flight: skip if other model is over cap
    └── prompts/
        ├── code.md
        ├── prose.md
        ├── launch.md
        ├── email.md
        └── generic.md
```

## Codex-side install

Symlinked at `~/.codex/skills/cross-model-check → ~/.claude/skills/cross-model-check`. Same SKILL.md, same run.py, same prompts — Codex discovers it via its own skill loader.

## Always-on integration

- `~/.claude/skills/pr-gate/run.py` runs `cross-model-check` as a 4th section after fakeidan / fakematt-copyedit / launch-announcement. HIGH findings feed the existing `total_high` block logic.
- `~/.claude/skills/qa-gate/scripts/run_fakeidan.py` runs `cross-model-check` alongside fakeidan. HIGH findings append `[XMODEL]` entries to the manifest.

Both gates support `--no-cross-model` for rate-limit conservation; off by default.

## Direct CLI

```bash
python3 ~/.claude/skills/cross-model-check/run.py path/to/artifact.md \
    --mode prose \
    --from claude \
    --primary-review path/to/copyedit-output.md \
    --out-dir /tmp/xmodel/
```

Exit codes: `0` clean / `2` HIGH findings / `3` skipped / `1` usage error.

## Latency note

v1 runs sequentially after the existing reviewers in both gates. If wall-clock pain emerges, refactor to `concurrent.futures.ThreadPoolExecutor` and run all fan-out skills in parallel — the section accumulator (`sections.append(...)`) already tolerates out-of-order completion.
