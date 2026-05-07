#!/usr/bin/env python3
"""Fake Matt email skill — draft / revise professional emails in Matt's voice.

Usage:
    python3 ~/.claude/skills/fakematt-email/run.py [flags]

Flags:
    --to EMAIL              recipient email (used for register lookup)
    --task "..."            description of what the email should accomplish
    --revise PATH           path to a draft markdown file to polish
    --reply-to-id MSGID     Gmail message ID to reply to (auto-loads thread)
    --reply-account EMAIL   Gmail account for --reply-to-id (default matteisn@gmail.com)
    --register A|B|C        force register (overrides tier_map)
    --out-dir DIR           output dir (default: /tmp/fakematt-email/)
    --create-draft          create Gmail draft after generating (still needs your send)
    --model MODEL           Claude model id (default: claude-opus-4-7)
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import subprocess
import sys
from pathlib import Path

# Reuse the Claude API wrapper from feedback-corpus.
sys.path.insert(0, str(Path.home() / ".claude" / "feedback-corpus"))
from lib.claude import call_claude  # type: ignore

DEFAULT_MODEL = "claude-opus-4-7"
DEFAULT_OUT = Path("/tmp/fakematt-email")

VAULT_ROOT = Path(
    "/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg"
)
MHE_ROOT = Path(
    "/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/MHE"
)
VOICE_UNIVERSALS = VAULT_ROOT / "_style" / "voice_universals.md"
LEARNED_PATTERNS = VAULT_ROOT / "_style" / "learned_patterns.md"
VOICE_DOC = VAULT_ROOT / "_style" / "professional_voice.md"
VOICE_CORPUS = VAULT_ROOT / "_style" / "professional_voice_corpus.md"
SUBJECT_PATTERNS = VAULT_ROOT / "_style" / "subject_patterns.md"
CORRECTIONS = Path(__file__).parent / "corrections.md"
TIER_MAP = Path(__file__).parent / "tier_map.json"
SENT_LOG = Path(__file__).parent / "sent-log.jsonl"
GMAIL_SKILL = Path.home() / ".claude" / "skills" / "gmail-skill" / "gmail_skill.py"

# Vault dirs to scan for People/Companies/Firms context (in order of preference).
VAULT_CONTEXT_DIRS = [
    MHE_ROOT / "People",
    VAULT_ROOT / "People",
    VAULT_ROOT / "Companies",
    VAULT_ROOT / "Firms",
]


def lookup_register(email: str | None) -> str | None:
    """Match recipient email to A/B/C/excluded via tier_map. None if not found."""
    if not email:
        return None
    addr = email.lower().strip()
    with open(TIER_MAP) as f:
        m = json.load(f)
    for reg in ("A", "B", "C"):
        if addr in [x.lower() for x in m[reg]["members"]]:
            return reg
    if addr in [x.lower() for x in m["_excluded"]["members"]]:
        return "EXCLUDED"
    return None


def extract_first_name(email: str | None, vault_path: Path | None) -> str | None:
    """Pre-extract recipient first name from vault filename if present, else
    email local-part if it parses as a name. Returns None if uncertain.
    """
    if vault_path:
        stem = vault_path.stem.strip()
        first = stem.split()[0] if stem else ""
        if first and first[0].isupper() and len(first) >= 2 and first.isalpha():
            return first
    if not email:
        return None
    local = email.split("@", 1)[0]
    for sep in (".", "_", "-", "+"):
        if sep in local:
            first_chunk = local.split(sep, 1)[0]
            if first_chunk.isalpha() and len(first_chunk) >= 2:
                return first_chunk.capitalize()
    if local.isalpha() and 2 <= len(local) <= 20:
        return local.capitalize()
    return None


def find_vault_context(email: str | None) -> tuple[Path | None, str]:
    """Search vault People/Companies/Firms folders for a file whose frontmatter
    `email:` matches the recipient. Returns (path, content) or (None, '').

    Match priority: explicit `email:` frontmatter > filename containing the
    local part of the email > none.
    """
    if not email:
        return None, ""
    addr = email.lower().strip()
    local = addr.split("@", 1)[0]

    by_email: Path | None = None
    by_name: Path | None = None

    for dir_ in VAULT_CONTEXT_DIRS:
        if not dir_.exists():
            continue
        for fp in dir_.rglob("*.md"):
            try:
                head = fp.read_text(errors="ignore")[:1500]
            except Exception:
                continue
            # Look for email in frontmatter (handles comma-separated lists too)
            m = re.search(r"^\s*email\s*:\s*(.+)$", head, re.M)
            if m and addr in m.group(1).lower():
                by_email = fp
                break
            # Filename fallback: check if local part matches filename stub
            if local and local in fp.stem.lower().replace(" ", ""):
                if by_name is None:
                    by_name = fp
        if by_email:
            break

    chosen = by_email or by_name
    if chosen:
        try:
            content = chosen.read_text()[:4000]
            return chosen, content
        except Exception:
            return None, ""
    return None, ""


def append_tier_map(addr: str, register: str, reason: str = "") -> None:
    """Append a recipient to tier_map.json under the chosen register."""
    if register not in ("A", "B", "C", "EXCLUDED"):
        return
    if not addr:
        return
    addr = addr.lower().strip()
    with open(TIER_MAP) as f:
        m = json.load(f)
    key = "_excluded" if register == "EXCLUDED" else register
    members = [x.lower() for x in m[key]["members"]]
    if addr in members:
        return  # already there
    m[key]["members"].append(addr)
    if reason:
        # store rationale next to _comment-like field
        notes = m[key].setdefault("_autoclassified", {})
        notes[addr] = reason
    with open(TIER_MAP, "w") as f:
        json.dump(m, f, indent=2)


def log_sent_attempt(record: dict) -> None:
    """Append-only JSONL log of every draft we created via --create-draft.
    Used by learn.py to diff our drafts against what Matt actually sent.
    """
    try:
        with open(SENT_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"[sent-log] failed: {e}", file=sys.stderr)


def load_anchors() -> str:
    """Load voice universals + voice doc + corpus + tier map + corrections."""
    parts = []
    if VOICE_UNIVERSALS.exists():
        parts.append(f"# VOICE UNIVERSALS (cross-surface — applies always)\n\n{VOICE_UNIVERSALS.read_text()}")
    if LEARNED_PATTERNS.exists() and LEARNED_PATTERNS.stat().st_size > 200:
        parts.append(f"# LEARNED PATTERNS (auto-promoted from Matt's edits)\n\n{LEARNED_PATTERNS.read_text()}")
    if VOICE_DOC.exists():
        parts.append(f"# PROFESSIONAL VOICE GUIDE (canonical)\n\n{VOICE_DOC.read_text()}")
    else:
        parts.append("# PROFESSIONAL VOICE GUIDE — MISSING")
    if VOICE_CORPUS.exists():
        parts.append(f"# RAW CORPUS (outgoing samples)\n\n{VOICE_CORPUS.read_text()}")
    if SUBJECT_PATTERNS.exists():
        parts.append(f"# SUBJECT LINE PATTERNS\n\n{SUBJECT_PATTERNS.read_text()}")
    if TIER_MAP.exists():
        parts.append(f"# TIER MAP (recipient → register)\n\n```json\n{TIER_MAP.read_text()}\n```")
    if CORRECTIONS.exists() and CORRECTIONS.stat().st_size > 0:
        parts.append(
            "# RECENT CORRECTIONS (Matt's edits to prior drafts — use these to refine voice)\n\n"
            + CORRECTIONS.read_text()
        )
    return "\n\n---\n\n".join(parts)


def load_thread_context(msgid: str, account: str) -> str:
    """Pull thread context for a reply via gmail-skill."""
    try:
        out = subprocess.run(
            ["python3", str(GMAIL_SKILL), "read", msgid, "--account", account],
            capture_output=True, text=True, timeout=30,
        )
        d = json.loads(out.stdout)
        return f"From: {d.get('from','')}\nSubject: {d.get('subject','')}\nDate: {d.get('date','')}\n\n{d.get('body') or d.get('snippet','')}"
    except Exception as e:
        return f"(could not load thread {msgid}: {e})"


SYSTEM_PROMPT = """You are Fake Matt's email-drafting assistant. Your job is to produce email text that sounds like Matt — using the voice doc + raw corpus + tier map below as ground truth.

# Hard rules

1. **Match the register** specified by the caller. A=Formal-Warm ("Hi Name,"+"Best, Matthew"), B=Mid-Casual, C=Casual-Pro ("Hey Name,"+drops or "Matt"). Don't cross registers.
2. **Anti-patterns are forbidden:**
   - "I hope this email finds you well" — Matt uses "Hope all is well!" with the exclamation.
   - "Please don't hesitate to reach out" — Matt says "Let me know if you have any questions."
   - "Sincerely," / "Regards," / "Kind regards," — Matt uses "Best,"
   - Capitalize-for-emphasis — Matt uses *italics*.
   - Long preambles before the ask. Matt gets to it in para 1-2.
3. **Voice tells to use** (when natural, don't force):
   - "let me know if [...]" — workhorse ask
   - "looking forward to it" — closing affirmation
   - "just wanted to [give you a heads up / touch base / follow up]" — soft prefix
   - "or send a calendly if that's easier" — scheduling fallback (catch-up emails only)
   - "hope all is well!" — opener for cold-ish reach-outs
4. **Hedges** ("hopefully," "I imagine," "I assume," "or down to...") are Matt's. Use sparingly, not in every sentence.
5. **Sentence length:** median ~14 words. Don't go terse or verbose.
6. **Bullets** for structured asks (especially in Register A). Prose for everything else.
7. **Sign-off:** Register A → "Best, Matthew". Register B → "Best, Matthew" or just "Matthew". Register C → drop closer or "Matt".
8. **Never invent recipient context.** If you need background, ask in your output instead of fabricating.

# Output format

Produce TWO sections, separated by a markdown horizontal rule:

```
# Draft

<the email body, ready to copy-paste — no subject line unless the caller asks>

---

# Brief

**Register chosen:** A / B / C — one-sentence reason (matches tier_map / explicit override / inferred from context).

**Voice tells used:** bullet list of phrases/patterns from the voice doc that this draft uses.

**Anti-patterns avoided:** any AI-template phrasing the draft consciously avoided.

**Open questions for Matt:** anything you couldn't infer from the context (use bullet list, or "none" if straightforward).

**RECOMMEND_TIER:** A / B / C / EXCLUDED — only emit this line if the recipient was NOT already classified in tier_map.json (i.e., the request told you the register was a FALLBACK). Pick the register that best fits this recipient based on prior thread tone, vault context, and voice doc rules. The skill will persist this recommendation back to tier_map for future runs.
```

The Brief is for Matt's review. It should be short and honest.
"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", help="recipient email")
    ap.add_argument("--task", help="what the email should accomplish")
    ap.add_argument("--revise", type=Path, help="markdown draft to polish")
    ap.add_argument("--reply-to-id", help="Gmail message ID to reply to")
    ap.add_argument("--reply-account", default="matteisn@gmail.com")
    ap.add_argument("--register", choices=["A","B","C"], help="force register")
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--create-draft", action="store_true")
    ap.add_argument("--subject", help="explicit subject (otherwise inferred from --reply-to-id or generated)")
    ap.add_argument("--subject-task", action="store_true",
                    help="ask the LLM to generate a Matt-style subject (uses subject_patterns.md)")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    args = ap.parse_args()

    if not (args.task or args.revise or args.reply_to_id):
        print("error: need --task or --revise or --reply-to-id", file=sys.stderr)
        return 2

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Determine register
    register = args.register or lookup_register(args.to)
    if register == "EXCLUDED":
        # Auto-forward to fakematt-personal — the recipient is family/close-friend.
        personal_skill = Path.home() / ".claude" / "skills" / "fakematt-personal" / "run.py"
        if personal_skill.exists():
            print(f"[fakematt-email] {args.to} is in EXCLUDED list — forwarding to fakematt-personal", file=sys.stderr)
            forward_args = ["python3", str(personal_skill)]
            for k in ("to","task","reply_to_id","reply_account","out_dir","subject","model"):
                v = getattr(args, k, None)
                if v is not None:
                    forward_args += [f"--{k.replace('_','-')}", str(v)]
            if args.revise:
                forward_args += ["--revise", str(args.revise)]
            if args.create_draft:
                forward_args += ["--create-draft"]
            return subprocess.call(forward_args)
        print(f"error: {args.to} is EXCLUDED and fakematt-personal not found.", file=sys.stderr)
        return 2
    if not register:
        register = "B"  # safe default
        register_note = f"FALLBACK to B (mid-casual) — {args.to} not in tier_map; revise via --register if needed."
    else:
        register_note = f"From tier_map: {register}"

    # Build user message
    fallback_used = register == "B" and not args.register and not lookup_register(args.to)
    user_parts = [
        f"Recipient: {args.to or '(unspecified)'}",
        f"Register: {register} — {register_note}",
    ]
    if fallback_used:
        user_parts.append(
            "(Note: this is a FALLBACK classification because the recipient is "
            "not yet in tier_map.json. Emit a RECOMMEND_TIER line in the Brief "
            "so the skill can persist your judgment.)"
        )
    if args.task:
        user_parts.append(f"\n# Task\n{args.task}")
    if args.revise and args.revise.exists():
        user_parts.append(f"\n# Existing draft to polish\n{args.revise.read_text()}")
    if args.reply_to_id:
        ctx = load_thread_context(args.reply_to_id, args.reply_account)
        user_parts.append(f"\n# Thread you're replying to\n{ctx}")

    # #3: Vault context injection — pull the recipient's People/Companies file if it exists
    vault_path, vault_content = find_vault_context(args.to)
    if vault_content:
        user_parts.append(
            f"\n# Vault context for this recipient\nSource: `{vault_path}`\n\n{vault_content}"
        )
        print(f"[fakematt-email] vault context: {vault_path.name}", file=sys.stderr)

    # #4: First-name pre-extraction — give the LLM an explicit salutation hint
    first_name = extract_first_name(args.to, vault_path)
    if first_name:
        user_parts.append(
            f"\n# Salutation hint\nRecipient first name appears to be: **{first_name}**. "
            f"Use this in the greeting unless the thread context indicates otherwise "
            f"(e.g., a nickname or different preferred form)."
        )

    # #3: Subject-line generation request
    if args.subject_task and not args.reply_to_id:
        user_parts.append(
            "\n# Subject line\nGenerate a Matt-style subject line for this email "
            "(see SUBJECT LINE PATTERNS above). Emit it in the Brief as a "
            "**SUBJECT_LINE:** line. Pick a pattern that fits the situation."
        )

    anchors = load_anchors()

    # Single-prompt CLI wrapper (call_claude takes one prompt blob)
    print(f"[fakematt-email] register={register}, model={args.model}", file=sys.stderr)
    full_prompt = (
        SYSTEM_PROMPT
        + "\n\n---\n\n"
        + anchors
        + "\n\n---\n\n# REQUEST\n\n"
        + "\n".join(user_parts)
    )
    response = call_claude(full_prompt, model=args.model)

    # Write outputs
    ts = dt.datetime.now().strftime("%Y%m%dT%H%M%S")
    recip = (args.to or "unspecified").replace("@","_at_").replace(".","_")
    base = args.out_dir / f"{ts}-to-{recip}"

    # Split draft + brief
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

    # #2: Tier-map autocomplete — if we used a fallback and the LLM emitted a
    # RECOMMEND_TIER line, persist it back to tier_map.json.
    if fallback_used and args.to and brief:
        rec = re.search(r"^\s*\*\*?RECOMMEND_TIER:?\*\*?\s*([ABC]|EXCLUDED)\b", brief, re.M)
        if rec:
            new_tier = rec.group(1)
            append_tier_map(args.to, new_tier, reason=f"auto from {ts}")
            print(f"[fakematt-email] tier_map updated: {args.to} → {new_tier}", file=sys.stderr)

    # Optional: create Gmail draft
    if args.create_draft and args.to:
        # Extract clean body — content between "# Draft" and trailing "---" or EOF
        m = re.search(r"^#\s*Draft\s*\n+(.*?)(?:\n---\s*$|\Z)", draft, re.S | re.M)
        body = m.group(1).strip() if m else draft.strip()

        # Determine subject
        if args.subject:
            subject = args.subject
        elif args.subject_task and brief:
            # Look for SUBJECT_LINE: in the brief
            sm = re.search(r"^\s*\*\*?SUBJECT_LINE:?\*\*?\s*(.+)$", brief, re.M)
            if sm:
                subject = sm.group(1).strip().strip("\"'`")
            else:
                subject = "(set subject before sending)"
        elif args.reply_to_id:
            # Fetch the original message's subject and prefix "Re: " if needed
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
            # #1: Log this draft so learn.py can compare it against the eventually-sent version
            try:
                draft_data = json.loads(r.stdout)
                log_sent_attempt({
                    "ts": ts,
                    "draft_id": draft_data.get("draft_id"),
                    "to": args.to,
                    "subject": subject,
                    "register": register,
                    "reply_to_id": args.reply_to_id,
                    "account": args.reply_account,
                    "generated_body": body,
                    "draft_file": str(draft_path),
                    "checked": False,  # learn.py flips this once it has compared
                })
            except Exception as e:
                print(f"[sent-log] could not log: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[gmail draft] failed: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
