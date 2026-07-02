#!/usr/bin/env python3
"""Deterministic structure/anti-pattern checks for Fake Matt fixtures.

This is not a voice-quality benchmark. It catches format regressions and
obvious cross-surface mistakes without pinning exact prose.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

FIXTURES = Path(__file__).with_name("regression_fixtures.json")
BANNED_EMAIL_PHRASES = [
    "i hope this email finds you well",
    "please don't hesitate to reach out",
    "kind regards",
    "sincerely",
]


def fail(name: str, reason: str, failures: list[str]) -> None:
    failures.append(f"{name}: {reason}")


def check_professional(name: str, text: str, failures: list[str]) -> None:
    lower = text.lower()
    if "# draft" not in lower or "# brief" not in lower:
        fail(name, "missing Draft/Brief sections", failures)
    # NOTE (2026-06-02 voice overhaul): greeting is NOT required — 88% of real
    # Matt emails open with no greeting. We only require a plausible closer OR
    # a no-closer short body (both real patterns).
    if not re.search(r"^(best|thanks|matthew|matt)\b", text, re.I | re.M):
        fail(name, "missing plausible closer", failures)
    for phrase in BANNED_EMAIL_PHRASES:
        if phrase in lower:
            fail(name, f"banned phrase: {phrase}", failures)
    # Structural caricature checks (mirror voice_priors.structural_check):
    draft_body = text.split("---", 1)[0]
    body_words = len(draft_body.split())
    if body_words > 250:
        fail(name, f"draft body is {body_words} words — outside Matt's distribution", failures)
    if re.search(r"(?m)^\s*[-*•]\s", draft_body):
        fail(name, "professional draft body contains bullet list (2.5% real usage)", failures)
    if re.search(r"\bI'?m (the )?(head of|founder)\b", draft_body, re.I):
        fail(name, "draft self-introduces with role/title (1.1% real usage)", failures)


def check_personal(name: str, text: str, failures: list[str]) -> None:
    lower = text.lower()
    if "# draft" not in lower or "# brief" not in lower:
        fail(name, "missing Draft/Brief sections", failures)
    if re.search(r"^best,\s*$\n^matthew\s*$", text, re.I | re.M):
        fail(name, "used professional Best/Matthew closer", failures)
    if re.search(r"(?m)^[-*]\s+", text.split("---", 1)[0]):
        fail(name, "personal draft body contains bullet list", failures)
    for phrase in BANNED_EMAIL_PHRASES:
        if phrase in lower:
            fail(name, f"banned phrase: {phrase}", failures)


def check_slack(name: str, text: str, failures: list[str]) -> None:
    for section in ("=== Draft ===", "=== Register ===", "=== Voice tells used ===", "=== Anti-pattern check ==="):
        if section not in text:
            fail(name, f"missing section: {section}", failures)
    draft = text.split("=== Register ===", 1)[0].replace("=== Draft ===", "").strip()
    if len([line for line in draft.splitlines() if line.strip()]) > 15:
        fail(name, "draft exceeds 15 nonblank lines", failures)
    if re.search(r"^(hi|hey)\s+\w+,", draft, re.I | re.M):
        fail(name, "Slack draft has email-style greeting", failures)
    if re.search(r"^(best|thanks),?\s*$", draft, re.I | re.M):
        fail(name, "Slack draft has email-style closer", failures)


def check_copyedit(name: str, text: str, failures: list[str]) -> None:
    lower = text.lower()
    if "## findings" not in lower:
        fail(name, "missing Findings section", failures)
    if "interview queue" not in lower:
        fail(name, "missing Interview queue section", failures)
    if not re.search(r"\b(high|medium|low)\b", text, re.I):
        fail(name, "missing confidence label", failures)
    if "rule cited:" not in lower and "writing_style.md" not in lower:
        fail(name, "missing style citation", failures)


CHECKS = {
    "email": check_professional,
    "personal": check_personal,
    "slack": check_slack,
    "copyedit": check_copyedit,
}


def main() -> int:
    data = json.loads(FIXTURES.read_text())
    failures: list[str] = []
    for name, item in data.items():
        surface = item["surface"]
        text = item["text"]
        CHECKS[surface](name, text, failures)
    if failures:
        print("Fake Matt regression fixtures FAILED")
        print("\n".join(f"- {f}" for f in failures))
        return 1
    print(f"Fake Matt regression fixtures OK ({len(data)} fixtures)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
