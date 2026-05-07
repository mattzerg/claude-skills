#!/usr/bin/env python3
"""Fake Matt personal email skill — draft/revise PERSONAL emails in Matt's voice.

Forked from fakematt-email. Difference: anchors on personal_voice.md + corpus,
3 tones (affection/neutral/terse) instead of 3 registers, no professional closers.

Usage:
    python3 ~/.claude/skills/fakematt-personal/run.py [flags]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".claude" / "feedback-corpus"))
from lib.claude import call_claude  # type: ignore

# Reuse fakematt-email helpers for vault context lookup + first-name extraction.
sys.path.insert(0, str(Path.home() / ".claude" / "skills" / "fakematt-email"))
from run import find_vault_context, extract_first_name  # type: ignore

DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_OUT = Path("/tmp/fakematt-personal")

VAULT_ROOT = Path(
    "/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg"
)
VOICE_UNIVERSALS = VAULT_ROOT / "_style" / "voice_universals.md"
LEARNED_PATTERNS = VAULT_ROOT / "_style" / "learned_patterns.md"
VOICE_DOC = VAULT_ROOT / "_style" / "personal_voice.md"
VOICE_CORPUS = VAULT_ROOT / "_style" / "personal_voice_corpus.md"
PRO_VOICE_DOC = VAULT_ROOT / "_style" / "professional_voice.md"  # for Register-C fallback texture
CORRECTIONS = Path(__file__).parent / "corrections.md"
SENT_LOG = Path(__file__).parent / "sent-log.jsonl"
GMAIL_SKILL = Path.home() / ".claude" / "skills" / "gmail-skill" / "gmail_skill.py"


def log_sent_attempt(record: dict) -> None:
    try:
        with open(SENT_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"[sent-log] failed: {e}", file=sys.stderr)


def load_anchors() -> str:
    parts = []
    if VOICE_UNIVERSALS.exists():
        parts.append(f"# VOICE UNIVERSALS (cross-surface — applies always)\n\n{VOICE_UNIVERSALS.read_text()}")
    if LEARNED_PATTERNS.exists() and LEARNED_PATTERNS.stat().st_size > 200:
        parts.append(f"# LEARNED PATTERNS (auto-promoted from Matt's edits)\n\n{LEARNED_PATTERNS.read_text()}")
    if VOICE_DOC.exists():
        parts.append(f"# PERSONAL VOICE GUIDE (canonical)\n\n{VOICE_DOC.read_text()}")
    if CORRECTIONS.exists() and CORRECTIONS.stat().st_size > 0:
        parts.append(
            "# RECENT CORRECTIONS (Matt's edits to prior personal drafts — refine accordingly)\n\n"
            + CORRECTIONS.read_text()
        )
    else:
        parts.append("# PERSONAL VOICE GUIDE — MISSING")
    if VOICE_CORPUS.exists():
        parts.append(f"# RAW PERSONAL CORPUS\n\n{VOICE_CORPUS.read_text()}")
    if PRO_VOICE_DOC.exists():
        # Pull Register C texture as a floor — personal voice borrows from it
        text = PRO_VOICE_DOC.read_text()
        m = re.search(r"### Register C[^#]*", text)
        if m:
            parts.append(f"# PROFESSIONAL CASUAL-PRO REFERENCE (Register C — voice floor)\n\n{m.group(0)}")
    return "\n\n---\n\n".join(parts)


def load_thread_context(msgid: str, account: str) -> str:
    try:
        out = subprocess.run(
            ["python3", str(GMAIL_SKILL), "read", msgid, "--account", account],
            capture_output=True, text=True, timeout=30,
        )
        d = json.loads(out.stdout)
        return f"From: {d.get('from','')}\nSubject: {d.get('subject','')}\nDate: {d.get('date','')}\n\n{d.get('body') or d.get('snippet','')}"
    except Exception as e:
        return f"(could not load thread {msgid}: {e})"


SYSTEM_PROMPT = """You are Fake Matt's personal email-drafting assistant. The recipient is family or a close friend. Use the PERSONAL voice guide below.

# Hard rules

1. **No "Best, Matthew" with family.** Closer options:
   - **affection** tone → "Lots of love <3" + Matthew
   - **neutral** tone → drop closer entirely
   - **terse** tone → no closer, just end
   - Casual friends → "Matt" or first-name only
2. **Greeting flexibility:**
   - Start of new thread / after silence → "Hi [Name]," or "Hey [Name],"
   - Continuing an active thread → dive in directly (~70% of corpus does this)
3. **No bullet lists.** Family logistics get prose, even short prose.
4. **No anti-template phrases** (same as professional voice):
   - "I hope this email finds you well" — never
   - "Please don't hesitate to reach out" — never
   - "Sincerely," / "Regards," — never
5. **Voice texture:**
   - Self-deprecation goes hard with family ("Sorry for my MIA-ness", "I'm very not good at keeping in contact long distance")
   - Parenthetical confessional asides are welcome
   - Lowercase "i" sneaks in occasionally in casual moments
   - Hearts <3 for family with affection
   - Keep paragraphs short (2-3 sentences)

# When to fall back to professional voice

If the email has a third party CC'd (e.g., Mom forwards Matt to a UMich contact), use **professional Register A or B** instead — even though family is in the thread. This skill is for direct family-to-family / friend-to-friend exchanges only.

# Output format

```
# Draft

<the email body, ready to copy-paste>

---

# Brief

**Tone chosen:** affection / neutral / terse — one-sentence reason.

**Voice tells used:** bullet list of phrases/patterns from personal_voice.md.

**Anti-patterns avoided:** any AI-template phrasing avoided.

**Open questions for Matt:** anything that needs author input (or "none").
```
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", help="recipient email")
    ap.add_argument("--task", help="what the email should accomplish")
    ap.add_argument("--revise", type=Path, help="markdown draft to polish")
    ap.add_argument("--reply-to-id", help="Gmail message ID to reply to")
    ap.add_argument("--reply-account", default="matteisn@gmail.com")
    ap.add_argument("--tone", choices=["affection", "neutral", "terse"],
                    help="override auto-picked tone")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--create-draft", action="store_true")
    ap.add_argument("--subject", help="explicit subject")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    if not (args.task or args.revise or args.reply_to_id):
        print("error: need --task or --revise or --reply-to-id", file=sys.stderr)
        return 2

    # Validate recipient is in EXCLUDED list (or related personal/family domain).
    # If it's a known-pro contact, forward to fakematt-email instead.
    if args.to:
        tier_map = Path.home() / ".claude" / "skills" / "fakematt-email" / "tier_map.json"
        if tier_map.exists():
            with open(tier_map) as f:
                m = json.load(f)
            addr = args.to.lower().strip()
            for reg in ("A", "B", "C"):
                if addr in [x.lower() for x in m[reg]["members"]]:
                    pro_skill = Path.home() / ".claude" / "skills" / "fakematt-email" / "run.py"
                    print(f"[fakematt-personal] {args.to} is in tier_map register {reg} — forwarding to fakematt-email", file=sys.stderr)
                    fwd = ["python3", str(pro_skill)]
                    for k in ("to","task","reply_to_id","reply_account","out_dir","subject","model"):
                        v = getattr(args, k, None)
                        if v is not None:
                            fwd += [f"--{k.replace('_','-')}", str(v)]
                    if args.revise:
                        fwd += ["--revise", str(args.revise)]
                    if args.create_draft:
                        fwd += ["--create-draft"]
                    return subprocess.call(fwd)

    args.out_dir.mkdir(parents=True, exist_ok=True)

    user_parts = [f"Recipient: {args.to or '(unspecified)'}"]
    if args.tone:
        user_parts.append(f"Tone (override): {args.tone}")
    if args.task:
        user_parts.append(f"\n# Task\n{args.task}")
    if args.revise and args.revise.exists():
        user_parts.append(f"\n# Existing draft to polish\n{args.revise.read_text()}")
    if args.reply_to_id:
        ctx = load_thread_context(args.reply_to_id, args.reply_account)
        user_parts.append(f"\n# Thread you're replying to\n{ctx}")

    vault_path, vault_content = find_vault_context(args.to)
    if vault_content:
        user_parts.append(f"\n# Vault context for this recipient\nSource: `{vault_path}`\n\n{vault_content}")
        print(f"[fakematt-personal] vault context: {vault_path.name}", file=sys.stderr)

    first_name = extract_first_name(args.to, vault_path)
    if first_name:
        user_parts.append(
            f"\n# Salutation hint\nRecipient first name: **{first_name}**. "
            f"Use only if a greeting is appropriate; many personal-thread continuations dive in directly."
        )

    anchors = load_anchors()
    print(f"[fakematt-personal] tone={args.tone or 'auto'}, model={args.model}", file=sys.stderr)
    full_prompt = (
        SYSTEM_PROMPT + "\n\n---\n\n" + anchors
        + "\n\n---\n\n# REQUEST\n\n" + "\n".join(user_parts)
    )
    response = call_claude(full_prompt, model=args.model)

    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    recip = (args.to or "unspecified").replace("@","_at_").replace(".","_")
    base = args.out_dir / f"{ts}-to-{recip}"
    text = response.strip()
    if "\n---\n" in text:
        draft, _, brief = text.partition("\n---\n")
    else:
        draft, brief = text, ""

    draft_path = base.with_suffix(".draft.md")
    brief_path = base.with_suffix(".brief.md")
    draft_path.write_text(draft.strip() + "\n")
    brief_path.write_text(brief.strip() + "\n" if brief else "(no brief produced)\n")
    print(f"\n=== DRAFT ({draft_path}) ===\n{draft.strip()}\n")
    if brief.strip():
        print(f"\n=== BRIEF ({brief_path}) ===\n{brief.strip()}\n")

    # Optional Gmail draft creation
    if args.create_draft and args.to:
        m = re.search(r"^#\s*Draft\s*\n+(.*?)(?:\n---\s*$|\Z)", draft, re.S | re.M)
        body = m.group(1).strip() if m else draft.strip()
        if args.subject:
            subject = args.subject
        elif args.reply_to_id:
            try:
                r0 = subprocess.run(
                    ["python3", str(GMAIL_SKILL), "read", args.reply_to_id, "--account", args.reply_account],
                    capture_output=True, text=True, timeout=20,
                )
                d0 = json.loads(r0.stdout)
                orig = d0.get("subject", "").strip()
                subject = orig if orig.lower().startswith("re:") else f"Re: {orig}"
            except Exception:
                subject = "(set subject before sending)"
        else:
            subject = "(set subject before sending)"
        cmd = [
            "python3", str(GMAIL_SKILL), "draft",
            "--to", args.to, "--subject", subject, "--body", body,
            "--account", args.reply_account,
        ]
        if args.reply_to_id:
            cmd += ["--reply-to-id", args.reply_to_id]
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            print(f"\n[gmail draft] {r.stdout.strip()[:300]}")
            try:
                draft_data = json.loads(r.stdout)
                log_sent_attempt({
                    "ts": ts,
                    "draft_id": draft_data.get("draft_id"),
                    "to": args.to,
                    "subject": subject,
                    "tone": args.tone or "auto",
                    "reply_to_id": args.reply_to_id,
                    "account": args.reply_account,
                    "generated_body": body,
                    "draft_file": str(draft_path),
                    "checked": False,
                })
            except Exception as e:
                print(f"[sent-log] {e}", file=sys.stderr)
        except Exception as e:
            print(f"[gmail draft] failed: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
