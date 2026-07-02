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
from lib.claude import DEFAULT_MODEL as CLAUDE_DEFAULT_MODEL  # type: ignore
from lib.claude import call_claude  # type: ignore

# Reuse fakematt-email helpers for vault context lookup + first-name extraction.
sys.path.insert(0, str(Path.home() / ".claude" / "skills" / "fakematt-email"))
from run import find_vault_context, extract_first_name  # type: ignore

# Shared voice machinery (2026-06-02 exemplar-first overhaul): measured
# structural priors, task-similarity exemplar retrieval, resemblance check.
from voice_priors import (  # type: ignore
    compute_structural_priors,
    render_priors_block,
    load_task_exemplars,
    structural_check,
)

# aitr-backed model defaulting (explicit --model still wins).
sys.path.insert(0, str(Path.home() / ".claude" / "skills" / "aitr" / "scripts"))
try:
    from skill_default import aitr_model_or  # type: ignore
except ImportError:
    def aitr_model_or(fallback, **kwargs):  # type: ignore
        return fallback

# Voice drafting never runs below Opus-class (feedback_voice_exemplar_first.md).
VOICE_DRAFT_FALLBACK_MODEL = "claude-opus-4-8"
DEFAULT_MODEL = VOICE_DRAFT_FALLBACK_MODEL
DEFAULT_OUT = Path("/tmp/fakematt-personal")

# Family priors: family corpus is small (~284 real messages), so compute over
# 2018-2026 rather than the 3-year window the professional skill uses.
PERSONAL_PRIORS_CACHE = Path(__file__).parent / "structural_priors.json"
FAMILY_YEARS = tuple(str(y) for y in range(2018, dt.datetime.now().year + 1))

def _pick_vault_root() -> Path:
    """Prefer the live Obsidian vault (canonical); fall back to legacy iCloud or
    the TCC mirror only when canonical is unavailable.

    NOTE 2026-06-30: canonical moved to ~/Obsidian/Zerg. The old 'prefer iCloud'
    logic returned the now near-empty iCloud shell whenever it was merely readable,
    so this skill was reading MISSING voice docs (voice_universals, personal_voice,
    corpus) from there — silently degrading drafts. See
    Growth/publishing/_audit-2026-06-30-nobody-reads-code.md §4.
    """
    canonical = Path.home() / "Obsidian" / "Zerg" / "MattZerg"
    icloud = Path("/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg")
    mirror = Path.home() / ".zerg-vault-mirror" / "MattZerg"
    for cand in (canonical, icloud, mirror):
        try:
            if cand.exists() and any(cand.iterdir()):
                return cand
        except (PermissionError, OSError):
            continue
    return canonical


VAULT_ROOT = _pick_vault_root()
VOICE_UNIVERSALS = VAULT_ROOT / "_style" / "voice_universals.md"
LEARNED_PATTERNS = VAULT_ROOT / "_style" / "learned_patterns.md"
VOICE_DOC = VAULT_ROOT / "_style" / "personal_voice.md"
VOICE_CORPUS = VAULT_ROOT / "_style" / "personal_voice_corpus.md"
PRO_VOICE_DOC = VAULT_ROOT / "_style" / "professional_voice.md"  # for Register-C fallback texture
# Canonical work-lane memory (post 2026-06-30 iCloud->Obsidian migration). The old
# ~/.claude/projects/<iCloud-slug>/memory is now just a symlink to this dir — depend on
# the canonical location directly so a stale-project-dir/symlink cleanup can't break memory.
_CANON_MEMORY = Path.home() / "Obsidian/Zerg/MattZerg/claude-memory"
_LEGACY_MEMORY = Path.home() / ".claude/projects/-Users-mattheweisner-Library-Mobile-Documents-iCloud-md-obsidian-Documents-Zerg/memory"
MEMORY_DIR = _CANON_MEMORY if _CANON_MEMORY.exists() else _LEGACY_MEMORY
EMAIL_REPLY_VOICE = MEMORY_DIR / "feedback_email_reply_voice.md"
CORRECTIONS = Path(__file__).parent / "corrections.md"
SENT_LOG = Path(__file__).parent / "sent-log.jsonl"
GMAIL_SKILL = Path.home() / ".claude" / "skills" / "gmail-skill" / "gmail_skill.py"

# Shared with fakematt-email — single source of truth for outgoing-mail corpus.
EMAIL_RAW_OUTGOING = Path.home() / ".claude" / "skills" / "fakematt-email" / "raw_outgoing"
EMAIL_TIER_MAP = Path.home() / ".claude" / "skills" / "fakematt-email" / "tier_map.json"
RECIPIENT_PATTERNS_ROOT = Path(__file__).parent / "recipient_patterns"


def log_sent_attempt(record: dict) -> None:
    try:
        with open(SENT_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"[sent-log] failed: {e}", file=sys.stderr)


def update_last_record_draft_id(draft_id: str) -> None:
    """Patch draft_id onto the last logged record once Gmail draft creation
    succeeds. Called only on the --create-draft path."""
    try:
        if not SENT_LOG.exists():
            return
        with open(SENT_LOG) as f:
            lines = f.readlines()
        if not lines:
            return
        last = json.loads(lines[-1])
        last["draft_id"] = draft_id
        lines[-1] = json.dumps(last) + "\n"
        with open(SENT_LOG, "w") as f:
            f.writelines(lines)
    except Exception as e:
        print(f"[sent-log] update failed: {e}", file=sys.stderr)


def _excluded_emails() -> set[str]:
    if not EMAIL_TIER_MAP.exists():
        return set()
    try:
        data = json.loads(EMAIL_TIER_MAP.read_text())
        return {e.lower() for e in data.get("_excluded", {}).get("members", [])}
    except Exception:
        return set()


def _parse_outgoing_year_file(path: Path) -> list[dict]:
    """Same parser fakematt-email uses on its own raw_outgoing files."""
    if not path.exists():
        return []
    text = path.read_text()
    msgs: list[dict] = []
    parts = re.split(r"(?m)^---\n(?=date: )", text)
    for chunk in parts:
        chunk = chunk.strip()
        if not chunk.startswith("date: "):
            continue
        try:
            fm_end = chunk.index("\n---\n")
        except ValueError:
            continue
        fm_raw, body = chunk[:fm_end], chunk[fm_end + 5:].strip()
        meta: dict = {}
        for line in fm_raw.splitlines():
            m = re.match(r"^(\w+):\s*(.+)$", line)
            if m:
                meta[m.group(1)] = m.group(2).strip()
        if not meta.get("date") or not body:
            continue
        # Extract bare email
        to_raw = meta.get("to", "")
        em = re.search(r"[\w\.\+\-]+@[\w\.\-]+", to_raw)
        if em:
            meta["recipient_email"] = em.group(0).lower()
        meta["body"] = body
        msgs.append(meta)
    return msgs


def load_negative_space_corpus(max_samples: int = 24) -> str:
    """Load personal-voice samples from fakematt-email's raw_outgoing corpus,
    filtered to EXCLUDED-tier recipients (family/close-friends). Age-weighted
    sampling — recent years dominate, older years still represented. Massive
    expansion vs the curated 29-sample personal_voice_corpus.md."""
    if not EMAIL_RAW_OUTGOING.exists():
        return ""
    import random
    excluded = _excluded_emails()
    if not excluded:
        return ""
    by_year: dict[int, list[dict]] = {}
    for account_dir in EMAIL_RAW_OUTGOING.iterdir():
        if not account_dir.is_dir():
            continue
        for year_file in account_dir.glob("*.md"):
            try:
                year = int(year_file.stem)
            except ValueError:
                continue
            for msg in _parse_outgoing_year_file(year_file):
                if msg.get("recipient_email") in excluded:
                    by_year.setdefault(year, []).append(msg)
    if not by_year:
        return ""

    current_year = dt.datetime.now().year
    weights = {y: 1.0 / max(1, current_year - y + 1) for y in by_year}
    total_w = sum(weights.values())
    quotas = {y: max(1, int(round(max_samples * w / total_w))) for y, w in weights.items()}

    chosen: list[dict] = []
    for year in sorted(by_year.keys(), reverse=True):
        pool = by_year[year]
        n = min(quotas[year], len(pool))
        chosen.extend(random.sample(pool, n))
        if len(chosen) >= max_samples:
            break
    chosen = chosen[:max_samples]
    if not chosen:
        return ""
    chosen.sort(key=lambda m: m.get("date", ""), reverse=True)

    lines = [
        f"# RAW PERSONAL OUTGOING (NEGATIVE SPACE) — {len(chosen)} samples across "
        f"{len(set(m.get('date','')[:4] for m in chosen))} year(s)",
        "",
        "Real personal/family emails from Matt's history that fakematt-personal "
        "did NOT draft. These are voice ground truth — what Matt actually sounds "
        "like writing to family and close friends, left to himself. Recent years "
        "dominate. Don't quote directly; use as voice fingerprint.",
        "",
    ]
    for m in chosen:
        date = m.get("date", "?")
        to_addr = (m.get("to") or "?")[:80]
        subject = (m.get("subject") or "")[:80]
        body = m["body"][:1200]
        lines.append(f"## {date} — to {to_addr}")
        if subject:
            lines.append(f"_subject: {subject}_")
        lines.append("")
        lines.append("```")
        lines.append(body)
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def load_recipient_patterns(recipient: str | None) -> str:
    """Load recipient-specific patterns mined from past Matt-to-this-person
    personal emails. File at recipient_patterns/<email_safe>.md. Returns empty
    if not yet mined for this recipient."""
    if not recipient or not RECIPIENT_PATTERNS_ROOT.exists():
        return ""
    safe = recipient.lower().replace("@", "_at_").replace(".", "_") + ".md"
    path = RECIPIENT_PATTERNS_ROOT / safe
    if not path.exists() or path.stat().st_size < 200:
        return ""
    text = path.read_text()
    text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)
    return (
        f"# RECIPIENT-SPECIFIC PATTERNS — {recipient}\n\n"
        "Patterns mined from past Matt-to-this-person personal emails. "
        "**These override universal personal-voice patterns when they conflict.** "
        "If recipient closer says `Lots of love <3` and universal says `no closer`, "
        "use `Lots of love <3`.\n\n"
        + text.strip() + "\n"
    )


def load_recipient_history(recipient: str | None, max_drafts: int = 3) -> str:
    if not recipient or not SENT_LOG.exists():
        return ""
    matches: list[dict] = []
    try:
        with open(SENT_LOG) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:
                    continue
                if (rec.get("to") or "").lower() == recipient.lower():
                    matches.append(rec)
    except Exception:
        return ""
    if not matches:
        return ""
    matches = matches[-max_drafts:]
    out_parts = [
        f"# PRIOR DRAFTS TO {recipient} (last {len(matches)}, oldest first)\n\n"
        "These are previous drafts FM produced for this recipient and how Matt "
        "responded. **Use them to avoid repeating the same edits.**"
    ]
    for r in matches:
        ts = r.get("ts", "?")
        ed = r.get("edit_distance")
        if r.get("checked"):
            outcome = "kept verbatim" if ed in (0, None) else f"edited ({ed} changed lines)"
        else:
            outcome = "pending reconciliation"
        body = (r.get("generated_body") or "").strip()
        out_parts.append(f"\n## Draft {ts}  —  outcome: {outcome}\n\n```\n{body}\n```")
    return "\n".join(out_parts)


def _family_emails() -> set[str]:
    """Family/close-friend recipients, minus script-notification targets."""
    fam = _excluded_emails()
    # jens gets Apps Script error mail from Matt's account; his real
    # personal threads are rare and technical — low voice signal either way.
    fam.discard("matteisn@gmail.com")  # self-sends are notes, not voice
    return fam


def load_recipient_exemplars(recipient: str | None, n: int = 4) -> str:
    """Most-recent real Matt emails to THIS family member — the strongest
    possible voice signal for a personal email (dyad-specific affection level,
    closers, in-jokes)."""
    if not recipient or not EMAIL_RAW_OUTGOING.exists():
        return ""
    matches: list[dict] = []
    rec_lower = recipient.lower()
    for account_dir in EMAIL_RAW_OUTGOING.iterdir():
        if not account_dir.is_dir():
            continue
        for year_file in account_dir.glob("*.md"):
            for msg in _parse_outgoing_year_file(year_file):
                if msg.get("recipient_email") != rec_lower:
                    continue
                body = msg.get("body", "")
                # skip automated/script mail + tiny fragments
                if len(body) < 40 or body.startswith("Error:"):
                    continue
                matches.append(msg)
    if not matches:
        return ""
    matches.sort(key=lambda m: m.get("date", ""), reverse=True)
    chosen = matches[:n]
    lines = [
        f"# VERBATIM EXEMPLARS — Matt's real emails to {recipient}",
        "",
        f"**{len(chosen)} most-recent real emails Matt sent this person.** Your "
        "draft must be indistinguishable from these in length, warmth, closer "
        "choice, and rhythm. These outrank every rule below.",
        "",
    ]
    for m in chosen:
        lines.append(f"## {m.get('date','?')}")
        subj = (m.get("subject") or "")[:90]
        if subj:
            lines.append(f"_subject: {subj}_")
        lines.append("")
        lines.append("```")
        lines.append(m["body"][:1500])
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def load_anchors(recipient: str | None = None, task: str | None = None,
                 has_thread: bool = False) -> str:
    """Exemplar-first anchor assembly (2026-06-02 voice overhaul).

    Order: measured family priors → recipient-dyad exemplars → family
    task-similarity exemplars → personal-voice rules (closers/tones) →
    corrections → recipient memory. The old assembly dumped every voice doc
    + the full 29-sample corpus and let rules dominate."""
    parts = []
    family = _family_emails()

    # 1. Measured structure of Matt's real family emails.
    priors = compute_structural_priors(
        recipient_filter=family,
        cache_path=PERSONAL_PRIORS_CACHE,
        years=FAMILY_YEARS,
    )
    priors_block = render_priors_block(priors, is_reply=has_thread)
    if priors_block:
        parts.append(priors_block.replace(
            "MATT'S REAL EMAILS", "MATT'S REAL FAMILY/PERSONAL EMAILS"))

    # 2. Verbatim exemplars — dyad first (strongest), then family-wide
    #    task-similarity backfill.
    rec_exemplars = load_recipient_exemplars(recipient)
    if rec_exemplars:
        parts.append(rec_exemplars)
    task_exemplars = load_task_exemplars(
        task or "", n=3 if rec_exemplars else 5,
        recipient_filter=family, years=FAMILY_YEARS,
        is_reply=True if has_thread else None,
    )
    if task_exemplars:
        parts.append(task_exemplars.replace(
            "real Matt emails nearest to this task",
            "real Matt FAMILY emails nearest to this task"))

    # 3. Personal voice rules — closer/tone conventions only (the part
    #    exemplars can't fully carry for a new tone situation).
    if VOICE_DOC.exists():
        parts.append(f"# PERSONAL VOICE GUIDE (closer/tone conventions)\n\n{VOICE_DOC.read_text()}")

    # 4. Learning loop: Matt's edits to prior personal drafts.
    if CORRECTIONS.exists() and CORRECTIONS.stat().st_size > 0:
        parts.append(
            "# MATT'S EDITS TO PRIOR PERSONAL DRAFTS (don't repeat these mistakes)\n\n"
            + CORRECTIONS.read_text()
        )

    # 5. Recipient memory (prior FM drafts + mined dyad patterns).
    history = load_recipient_history(recipient)
    if history:
        parts.append(history)
    rec_patterns = load_recipient_patterns(recipient)
    if rec_patterns:
        parts.append(rec_patterns)

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


SYSTEM_PROMPT = """You are drafting a personal email AS Matt — to family or a close friend. The reader knows Matt's voice intimately; anything stiff, padded, or template-shaped will read as fake immediately.

# How voice works here

The VERBATIM EXEMPLARS below are real emails Matt sent to this person (or to family generally). They are the ONLY source of voice — length, warmth, rhythm, closers all come from them. The MEASURED STRUCTURE block is the statistical envelope of his real family emails. Rules below are conventions the exemplars can't always carry (closer choice by tone); when a rule conflicts with the exemplars, the exemplars win.

Before drafting, plan: what does this person actually need to hear, what's the one thing being said, what would Matt cut. Family emails are short, warm, and concrete — never newsletters.

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

If the email has a third party CC'd (e.g., Mom forwards Matt to a UMich contact), use **professional Register A or B** instead — even though family is in the thread. If Matt is representing Zerg, route to fakematt-email with `matt_zerg_professional`. This skill is for direct family-to-family / friend-to-friend exchanges only.

# Output format

```
# Draft

<the email body, ready to copy-paste>

---

# Brief

**Content plan:** what this person needs to hear / the one thing being said / what got cut.

**Tone chosen:** affection / neutral / terse — one-sentence reason.

**RESEMBLANCE_CHECK:** compare your draft against the exemplars:
- word count: <draft words> vs exemplar median — PASS/FAIL
- warmth/closer: matches the dyad's real closers — PASS/FAIL
- rhythm: prose paragraphs like the exemplars, no lists/structure — PASS/FAIL

**Open questions for Matt:** anything that needs author input (or "none").

**SELF_CONFIDENCE:** HIGH | MEDIUM | LOW — HIGH only if all RESEMBLANCE_CHECK lines pass.
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
    ap.add_argument("--model", default=None,
                    help=f"Claude model id (default: aitr pick, falling back to {DEFAULT_MODEL})")
    args = ap.parse_args()

    # Model resolution: explicit --model > aitr pick > Opus fallback.
    # Voice drafting never runs below Opus-class.
    if args.model is None:
        args.model = aitr_model_or(
            DEFAULT_MODEL,
            task_kind="draft-prose",
            caller="fakematt-personal",
            quality_floor="high-stakes",
        )

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

    anchors = load_anchors(recipient=args.to, task=args.task,
                           has_thread=bool(args.reply_to_id))
    print(f"[fakematt-personal] tone={args.tone or 'auto'}, model={args.model}", file=sys.stderr)
    full_prompt = (
        SYSTEM_PROMPT + "\n\n---\n\n" + anchors
        + "\n\n---\n\n# REQUEST\n\n" + "\n".join(user_parts)
    )
    response = call_claude(full_prompt, model=args.model)

    def _normalize_response(text: str) -> str:
        """Cut any preamble before '# Draft' (hook-injection noise from the
        claude CLI subprocess)."""
        m = re.search(r"(?m)^#\s*Draft\s*$", text)
        return text[m.start():] if m else text

    def _draft_body(text: str) -> str:
        body = text.strip()
        m = re.search(r"^#\s*Draft\s*\n+(.*?)(?:\n---\s*\n|\Z)", body, re.S | re.M)
        return m.group(1).strip() if m else body.partition("\n---\n")[0]

    response = _normalize_response(response)

    # Post-generation structural resemblance check against family priors.
    family_priors = compute_structural_priors(
        recipient_filter=_family_emails(),
        cache_path=PERSONAL_PRIORS_CACHE,
        years=FAMILY_YEARS,
    )
    violations = structural_check(_draft_body(response), family_priors,
                                  is_reply=bool(args.reply_to_id))
    if violations:
        print(f"[fakematt-personal] structural check FAILED ({len(violations)}) — revision pass",
              file=sys.stderr)
        revision_prompt = (
            full_prompt
            + "\n\n---\n\n# YOUR PREVIOUS DRAFT (failed the structural resemblance check)\n\n"
            + response
            + "\n\n# STRUCTURAL VIOLATIONS — fix every one, then re-emit the full Draft + Brief\n\n"
            + "\n".join(f"- {v}" for v in violations)
        )
        revised = _normalize_response(call_claude(revision_prompt, model=args.model))
        re_violations = structural_check(_draft_body(revised), family_priors,
                                         is_reply=bool(args.reply_to_id))
        if len(re_violations) < len(violations):
            response = revised
            violations = re_violations
        if violations:
            print(f"[fakematt-personal] WARNING: {len(violations)} violation(s) remain",
                  file=sys.stderr)

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

    # Extract body + subject up-front so we can log the draft regardless of
    # whether Gmail draft creation was requested. learn.py reconciles by
    # `to:<addr> after:<date>` so the stdout-only path is still useful.
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

    if args.to:
        is_synthetic = bool(__import__("os").environ.get("FAKEMATT_SYNTHETIC"))
        log_sent_attempt({
            "ts": ts,
            "draft_id": None,
            "to": args.to,
            "subject": subject,
            "tone": args.tone or "auto",
            "reply_to_id": args.reply_to_id,
            "account": args.reply_account,
            "generated_body": body,
            "draft_file": str(draft_path),
            "create_draft_path": bool(args.create_draft),
            "synthetic": is_synthetic,
            "checked": is_synthetic,  # synthetic = already-checked → learn.py skip
        })

    if args.create_draft and args.to:
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
                draft_id = draft_data.get("draft_id")
                if draft_id:
                    update_last_record_draft_id(draft_id)
            except Exception as e:
                print(f"[sent-log] {e}", file=sys.stderr)
        except Exception as e:
            print(f"[gmail draft] failed: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
