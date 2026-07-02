#!/usr/bin/env python3
"""Fake Matt personal email skill — daily smoke test.

Runs the skill against a synthetic input + verifies the output is sane.
Failure → posts an alert to Fake Matt's Slack self-DM.

Designed to run as a daily cron (suggested 7:15am, after fakematt-email's smoke).
"""
from __future__ import annotations

import datetime as dt
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).parent
SLACK_SKILL = Path.home() / ".claude" / "skills" / "slack-skill" / "slack_skill.py"
FM_DM = "D0B0T0ETDR8"


def diagnostics_section(title: str, body: str) -> str:
    return f"\n## {title}\n{body.strip() or '(empty)'}"


def build_failure(
    today: str,
    reason: str,
    *,
    result: subprocess.CompletedProcess[str] | None = None,
    out_dir: Path | None = None,
    validation: str = "",
) -> str:
    sections = [
        f":warning: *fakematt-personal smoke FAILED* ({today})\n{reason}",
        diagnostics_section("model", "run.py uses the shared Claude wrapper default unless --model is passed."),
        diagnostics_section(
            "auth",
            "See generation stderr/stdout below for Claude/zclaude authentication errors.",
        ),
        diagnostics_section(
            "anchor files",
            "\n".join(
                f"- {path}: {'OK' if path.exists() else 'MISSING'}"
                for path in [
                    SKILL_DIR / "run.py",
                    Path.home() / ".claude" / "feedback-corpus" / "lib" / "claude.py",
                    Path("/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/personal_voice.md"),
                    Path("/Users/mattheweisner/Obsidian/Zerg/MattZerg/_style/personal_voice_corpus.md"),
                    Path.home() / ".claude" / "skills" / "fakematt-email" / "tier_map.json",
                ]
            ),
        ),
        diagnostics_section(
            "vault context",
            "Smoke recipient: leutholdcat@hotmail.com. Vault lookup happens inside run.py; failures appear in generation stderr.",
        ),
    ]
    if result is not None:
        sections.append(
            diagnostics_section(
                "generation",
                "\n".join(
                    [
                        f"returncode={result.returncode}",
                        "stderr:",
                        result.stderr or "<empty>",
                        "stdout:",
                        result.stdout or "<empty>",
                    ]
                ),
            )
        )
    if out_dir is not None:
        sections.append(diagnostics_section("output validation", validation or f"out_dir={out_dir}"))
    return "\n".join(sections)


def post_alert(msg: str) -> None:
    if not SLACK_SKILL.exists():
        print(f"[smoke-test alert] {msg}", file=sys.stderr)
        return
    try:
        subprocess.run(
            ["python3", str(SLACK_SKILL), "send", FM_DM, "-m", msg],
            capture_output=True, text=True, timeout=20,
        )
    except Exception as e:
        print(f"[smoke-test alert] post failed: {e}", file=sys.stderr)


def main() -> int:
    today = dt.date.today().isoformat()
    with tempfile.TemporaryDirectory() as tmp:
        out_dir = Path(tmp)
        # Synthetic input: Catherine Leuthold (vault file exists, low-stakes affection tone)
        result = subprocess.run(
            [
                "python3", str(SKILL_DIR / "run.py"),
                "--to", "leutholdcat@hotmail.com",
                "--task", "(smoke test) Quick check-in — wishing well, mentioning summer plans. Affection tone.",
                "--out-dir", str(out_dir),
            ],
            capture_output=True, text=True, timeout=120,
            env={**os.environ, "FAKEMATT_SYNTHETIC": "1"},
        )
        if result.returncode != 0:
            msg = build_failure(
                today,
                f"`run.py` exited {result.returncode}",
                result=result,
                out_dir=out_dir,
            )
            print(msg)
            post_alert(msg)
            return 1
        drafts = list(out_dir.glob("*.draft.md"))
        briefs = list(out_dir.glob("*.brief.md"))
        if not drafts or not briefs:
            msg = build_failure(
                today,
                "Missing artifacts.",
                result=result,
                out_dir=out_dir,
                validation=f"drafts={len(drafts)} briefs={len(briefs)}",
            )
            print(msg); post_alert(msg)
            return 1
        draft_text = drafts[0].read_text().strip()
        brief_text = briefs[0].read_text().strip()
        if len(draft_text) < 50 or "(no brief produced)" in brief_text:
            msg = build_failure(
                today,
                "Draft too short or brief missing.",
                result=result,
                out_dir=out_dir,
                validation=f"draft={len(draft_text)} brief={len(brief_text)}",
            )
            print(msg); post_alert(msg)
            return 1
        # Personal-specific check: should NOT contain "Best, Matthew" (formal-pro closer)
        body = re.sub(r"^#\s*Draft\s*\n+", "", draft_text, flags=re.M)
        if re.search(r"^Best,\s*$", body, re.M) and re.search(r"^Matthew\s*$", body, re.M):
            msg = build_failure(
                today,
                "Personal draft used 'Best, Matthew' formal closer (anti-pattern for family).",
                result=result,
                out_dir=out_dir,
                validation=f"draft preview:\n{body[:1200]}",
            )
            print(msg); post_alert(msg)
            return 1
        print(f"[smoke-test {today}] PASS — draft={len(draft_text)} chars, brief={len(brief_text)} chars")
        return 0


if __name__ == "__main__":
    sys.exit(main())
