#!/usr/bin/env python3
"""Fake Matt email skill — draft / revise professional emails in Matt's voice.

Usage:
    python3 ~/.claude/skills/fakematt-email/run.py [flags]

Flags:
    --to EMAIL              recipient email (used for register lookup)
    --task "..."            description of what the email should accomplish
    --revise PATH           path to a draft markdown file to polish
    --reply-to-id MSGID     Gmail message ID to reply to (auto-loads thread)
    --reply-account EMAIL   Gmail account for --reply-to-id (default matthew@zergai.com — fakematt is Zerg/work voice; personal goes through fakematt-personal or future fakematthew)
    --register A|B|C        force register (overrides tier_map)
    --out-dir DIR           output dir (default: /tmp/fakematt-email/)
    --create-draft          create Gmail draft after generating (still needs your send)
    --model MODEL           Claude model id (default: shared Claude wrapper default)
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
from lib.claude import DEFAULT_MODEL as CLAUDE_DEFAULT_MODEL  # type: ignore
from lib.claude import call_claude  # type: ignore

# aitr-backed model defaulting (explicit --model still wins).
sys.path.insert(0, str(Path.home() / ".claude" / "skills" / "aitr" / "scripts"))
try:
    from skill_default import aitr_pick_or, record_outcome  # type: ignore
except ImportError:
    def aitr_pick_or(fallback, **kwargs):  # type: ignore
        return fallback, None

    def record_outcome(*args, **kwargs):  # type: ignore
        pass

# Decision id of this run's aitr pick (None when --model was explicit or aitr
# fell back) — the __main__ wrapper records the realized outcome against it.
_AITR_DECISION_ID = None

# Structural priors + exemplar retrieval + resemblance check (2026-06-02
# voice overhaul — exemplar-first generation).
sys.path.insert(0, str(Path(__file__).parent))
from voice_priors import (  # type: ignore
    compute_structural_priors,
    render_priors_block,
    load_task_exemplars,
    structural_check,
    is_first_contact_rfq,
)

# Voice drafting is high-stakes: cheap models produce the "too dumb /
# too clearly AI" failures Matt flagged 2026-06-02. Never draft below
# Opus-class regardless of what the shared default is.
VOICE_DRAFT_FALLBACK_MODEL = "claude-opus-4-8"
DEFAULT_MODEL = VOICE_DRAFT_FALLBACK_MODEL
DEFAULT_OUT = Path("/tmp/fakematt-email")

def _pick_vault_root() -> Path:
    """Prefer the live Obsidian vault (canonical); fall back to legacy iCloud or
    the TCC mirror only when canonical is unavailable.

    NOTE 2026-06-30: canonical moved to ~/Obsidian/Zerg. The old 'prefer iCloud'
    logic returned the now near-empty iCloud shell whenever it was merely readable,
    so this skill was reading MISSING voice docs (voice_universals, professional_voice,
    corpus, contexts) from there — silently degrading drafts. See
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
MHE_ROOT = Path(
    "/Users/mattheweisner/Obsidian/MHE"
)
VOICE_UNIVERSALS = VAULT_ROOT / "_style" / "voice_universals.md"
LEARNED_PATTERNS = VAULT_ROOT / "_style" / "learned_patterns.md"
CONTEXT_GUIDE = VAULT_ROOT / "_style" / "fakematt_contexts.md"
VOICE_DOC = VAULT_ROOT / "_style" / "professional_voice.md"
VOICE_CORPUS = VAULT_ROOT / "_style" / "professional_voice_corpus.md"
SUBJECT_PATTERNS = VAULT_ROOT / "_style" / "subject_patterns.md"
VOICE_DRIFT_REPORT = VAULT_ROOT / "_style" / "voice_drift_report.md"
# Canonical work-lane memory (post 2026-06-30 iCloud->Obsidian migration). The old
# ~/.claude/projects/<iCloud-slug>/memory is now just a symlink to this dir — depend on
# the canonical location directly so a stale-project-dir/symlink cleanup can't break memory.
_CANON_MEMORY = Path.home() / "Obsidian/Zerg/MattZerg/claude-memory"
_LEGACY_MEMORY = Path.home() / ".claude/projects/-Users-mattheweisner-Library-Mobile-Documents-iCloud-md-obsidian-Documents-Zerg/memory"
MEMORY_DIR = _CANON_MEMORY if _CANON_MEMORY.exists() else _LEGACY_MEMORY
EMAIL_REPLY_VOICE = MEMORY_DIR / "feedback_email_reply_voice.md"
CORRECTIONS = Path(__file__).parent / "corrections.md"
TIER_MAP = Path(__file__).parent / "tier_map.json"
SENT_LOG = Path(__file__).parent / "sent-log.jsonl"
GMAIL_SKILL = Path.home() / ".claude" / "skills" / "gmail-skill" / "gmail_skill.py"
CONVO_CLAUDE_DIR = VAULT_ROOT / "Conversations" / "Claude"
CONVO_SLACK_DIR = VAULT_ROOT / "Conversations" / "Slack"
RAW_OUTGOING_ROOT = Path(__file__).parent / "raw_outgoing"
RECIPIENT_PATTERNS_ROOT = Path(__file__).parent / "recipient_patterns"

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
    # Generic vendor/role inboxes — filename fallback would match unrelated
    # vault files (e.g. "Mixpanel Support.md" for support@stickermule.com).
    GENERIC_LOCALS = {"support", "info", "hello", "sales", "hi", "contact",
                      "team", "admin", "billing", "help", "office", "mail",
                      "noreply", "no-reply", "service", "orders"}
    if local in GENERIC_LOCALS:
        local = ""

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


REGISTER_DEFINITIONS = """\
- A: Formal-warm. Opens "Hi <Name>,", closes "Best, Matthew". Used for: investors,
  hiring managers, fund partners, accountants, first-touch external contacts,
  formal organizational outreach, anyone Matt hasn't met or has only met briefly.
- B: Mid-casual. Opens "Hi <Name>," or "Hey <Name>,", closes "Best, Matt" or
  just "Matt". Used for: known business contacts with prior threads, ongoing
  partners, ecosystem peers, journalists, podcast hosts, BD contacts.
- C: Casual-pro. Opens "Hey <Name>," or dive-in (no greeting), closes "Matt"
  or no closer. Used for: internal Zerg team (Idan, André, Michael), close
  long-time ecosystem peers, friends in industry on first-name terms.
- EXCLUDED: Family or close personal friends — should route to fakematt-personal,
  not professional voice. Signals: family-naming patterns, personal-life topics,
  Gmail thread shape that mirrors casual-friend dynamics.
"""


def classify_register_via_llm(recipient: str, thread_ctx: str, vault_content: str,
                              model: str | None = None) -> dict | None:
    """First-encounter classifier: short LLM call that picks A/B/C/EXCLUDED
    based on reply-thread tone + vault context. Returns
    {register, confidence, rationale} or None on failure. Persists nothing
    itself — caller handles tier_map write.
    """
    if not recipient:
        return None
    # Cap context — classifier doesn't need the full thread, just tone signal
    thread_excerpt = (thread_ctx or "").strip()
    if len(thread_excerpt) > 2000:
        thread_excerpt = thread_excerpt[:2000] + "\n…(truncated)"
    vault_excerpt = (vault_content or "").strip()
    if len(vault_excerpt) > 2000:
        vault_excerpt = vault_excerpt[:2000] + "\n…(truncated)"

    prompt = (
        "Classify the email register Matt should use for this recipient.\n\n"
        f"Recipient email: {recipient}\n\n"
        f"REGISTER DEFINITIONS:\n{REGISTER_DEFINITIONS}\n\n"
        "REPLY-THREAD TONE (most recent inbound from this recipient, if any):\n"
        f"{thread_excerpt or '(none — first-touch outbound)'}\n\n"
        "VAULT CONTEXT (Matt's notes about this contact, if any):\n"
        f"{vault_excerpt or '(no vault entry)'}\n\n"
        "Output ONLY a JSON object — no prose, no markdown fences:\n"
        '{"register": "A" | "B" | "C" | "EXCLUDED", '
        '"confidence": "high" | "medium" | "low", '
        '"rationale": "one sentence citing the strongest signal"}'
    )
    try:
        out = subprocess.run(
            [str(Path.home() / ".local" / "bin" / "claude"),
             "--print", "--model", model or "claude-sonnet-4-6", "--tools", ""],
            input=prompt, capture_output=True, text=True, timeout=60,
        )
        if out.returncode != 0:
            return None
        raw = out.stdout.strip()
        # Strip fences if model added any
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
        first = raw.find("{")
        last = raw.rfind("}")
        if first == -1 or last <= first:
            return None
        result = json.loads(raw[first:last + 1])
        if result.get("register") not in ("A", "B", "C", "EXCLUDED"):
            return None
        return result
    except Exception as e:
        print(f"[fakematt-email] classifier failed (non-fatal): {e}", file=sys.stderr)
        return None


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
    """Append-only JSONL log of every draft fakematt-email produced (stdout
    or Gmail draft). Used by learn.py to diff drafts against what Matt sent.
    """
    try:
        with open(SENT_LOG, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"[sent-log] failed: {e}", file=sys.stderr)


def update_last_record_draft_id(draft_id: str) -> None:
    """When --create-draft succeeds AFTER we already logged the record,
    rewrite the last line with the now-known Gmail draft_id."""
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


def _summarize_convo_file(path: Path, max_chars: int = 220) -> str | None:
    """Return ONE line per file: date, title, key extras. Reads only frontmatter
    + first H1 — never session bodies. Skips files that look private."""
    try:
        text = path.read_text(errors="ignore")
    except Exception:
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    fm_raw, body = parts[1], parts[2]
    fm: dict[str, str] = {}
    for line in fm_raw.splitlines():
        m = re.match(r"^(\w+):\s*(.+)$", line.strip())
        if m:
            fm[m.group(1)] = m.group(2).strip()
    h1 = ""
    for line in body.lstrip().splitlines():
        if line.startswith("# "):
            h1 = line[2:].strip()
            break
        if line.strip():
            break
    if not h1:
        return None
    # Skip anything that looks like a private/personal channel
    chan = fm.get("channel", "")
    if chan and any(tok in chan.lower() for tok in ("personal", "private", "dm-")):
        return None
    date = fm.get("date") or fm.get("started", "")[:10]
    extras = []
    if fm.get("prs"):
        extras.append(f"PRs {fm['prs']}")
    if fm.get("duration_min"):
        extras.append(f"{fm['duration_min']}min")
    if chan:
        extras.append(f"#{chan}")
    extra_str = f" [{', '.join(extras)}]" if extras else ""
    out = f"- {date}: {h1}{extra_str}"
    return out[:max_chars]


def load_recent_context(register: str | None, days: int = 3, max_lines: int = 20) -> str:
    """Inject 'what Matt has been working on' into the prompt. Register-aware:
    skip Register A (formal-warm, first-touch external) so confidential project
    context never bleeds into a cold-outreach email. Reads only conversation
    frontmatter + H1 — never session bodies — to minimize content leakage.
    """
    if register == "A":
        return ""
    cutoff = dt.datetime.now() - dt.timedelta(days=days)

    items: list[tuple[float, str]] = []
    for d in (CONVO_CLAUDE_DIR, CONVO_SLACK_DIR):
        if not d.exists():
            continue
        for path in d.rglob("*.md"):
            try:
                mtime = path.stat().st_mtime
            except Exception:
                continue
            if dt.datetime.fromtimestamp(mtime) < cutoff:
                continue
            line = _summarize_convo_file(path)
            if line:
                items.append((mtime, line))

    if not items:
        return ""
    items.sort(key=lambda x: -x[0])
    items = items[:max_lines]

    lines = items  # already sorted newest-first
    body = "\n".join(line for _, line in lines)
    return (
        f"# MATT'S RECENT FOCUS (last {days} days, from conversation-ingest)\n\n"
        "Use this for situational awareness only — don't quote, don't drop "
        "client/PR/branch names into a draft unless the recipient is already "
        "in that context, and never invent a connection. If the request "
        "doesn't relate to any of these threads, ignore this block.\n\n"
        f"{body}\n"
    )


def _parse_year_corpus(path: Path) -> list[dict]:
    """Parse a raw_outgoing/<account>/<year>.md file into a list of message
    dicts: {date, to, subject, msg_id, body}."""
    if not path.exists():
        return []
    text = path.read_text()
    # Each message starts with `---\n` frontmatter terminated by `---\n` then body
    # until the next `\n---\ndate:` marker (or EOF)
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
        meta["body"] = body
        msgs.append(meta)
    return msgs


# Era-based weights derived from voice_drift_report.md recommendation
# (2026-05-09): "Weight recent eras aggressively — 2025-2026 and 2023-2024
# should together account for at least 65-70% of sampler weight. The 2015-2017
# samples are actively misleading for voice mimicry."
ERA_WEIGHTS = {
    # year -> weight share of total (must roughly sum to 1.0)
    # 2025-2026 = 40% / 2023-2024 = 30% / 2020-2022 = 18% / 2018-2019 = 8% / 2015-2017 = 4%
    2026: 0.20, 2025: 0.20,
    2024: 0.15, 2023: 0.15,
    2022: 0.06, 2021: 0.06, 2020: 0.06,
    2019: 0.04, 2018: 0.04,
    2017: 0.015, 2016: 0.015, 2015: 0.01,
}


# Surface-keyword fingerprints for at-draft-time exemplar selection. Mirrors
# (a subset of) mine_surface_patterns.py keywords — enough for retrieval
# scoring, not full classification.
SURFACE_KEYWORD_FINGERPRINTS = {
    "cold-outreach": re.compile(
        r"\bI'?m (writing|reaching out|the )\b|\bI lead\b|\bI run\b|"
        r"\bI head\b|\bWe'?re (building|launching)\b|"
        r"\bwould love to (chat|connect|grab|jump on)\b|"
        r"\bI'?m a (founder|partner|investor|operator)\b|"
        r"\bI saw\b|\bcame across\b",
        re.I,
    ),
    "warm-intro": re.compile(
        r"\bintroducing\b|\bintroduce\b|\bI think you (two|guys|both)\b|"
        r"\b(you|both) should (meet|connect|chat)\b|\bI'll let .* take it from here\b|"
        r"\bover to you\b",
        re.I,
    ),
    "investor-update": re.compile(
        r"\b(quarterly|monthly|annual) (update|letter)\b|\b(MRR|ARR|runway)\b|"
        r"\b(LP|fund|portfolio) update\b|\bahead of (plan|target)\b|"
        r"\b(asks|how you can help)\b",
        re.I,
    ),
    "post-meeting-followup": re.compile(
        r"\b(great|good|nice) (to (chat|meet|see)|(chat|call|meeting))\b|"
        r"\b(thanks|thank you) for (the|your time|jumping|taking)\b|"
        r"\bfollowing up\b|\bnext steps\b|\bto recap\b|\bI'll (send|share|circle back)\b|"
        r"\bthanks again\b",
        re.I,
    ),
    "catchup-reconnect": re.compile(
        r"\bbeen (a )?(while|long time|forever|ages)\b|\b(it'?s been|long time)\b|"
        r"\b(catch up|catching up|catchup|reconnect)\b|"
        r"\bsorry for (my |the )?(MIA|silence|delay|delayed reply)\b|"
        r"\bgrab a (drink|coffee|beer|bite)\b|\bbeen meaning to\b",
        re.I,
    ),
    "deep-feedback": re.compile(
        r"\bmy (main |biggest |first |only )?(concern|reaction|take|sense|push.?back|critique)\b|"
        r"\bI'd (push|focus|prioritize|cut|keep|drop|kill|reframe)\b|"
        r"\bhave you (considered|thought about|tried)\b|"
        r"\b(few|couple|some) (thoughts|notes|reactions|flags|concerns)\b|"
        r"\bthoughts:\b|\breactions:\b|\bfeedback:\b",
        re.I,
    ),
}


def _score_surface_match(body: str, surface_re: re.Pattern) -> int:
    return len(surface_re.findall(body))


def load_surface_exemplars(surface: str | None, n: int = 3, recent_only: bool = True) -> str:
    """Pull N verbatim past Matt emails that score high on this surface's
    keyword fingerprint. Recent (last 2 years) by default. Returns markdown
    block; empty string if surface unknown or no matches.

    Round 18 hypothesis: LLMs mirror verbatim exemplars more reliably than
    abstract pattern descriptions. Hopes especially for cold-outreach (R17 = 50)
    where structural compliance is genuinely needed.
    """
    if not surface or surface not in SURFACE_KEYWORD_FINGERPRINTS:
        return ""
    if not RAW_OUTGOING_ROOT.exists():
        return ""
    pat = SURFACE_KEYWORD_FINGERPRINTS[surface]
    cutoff_year = dt.datetime.now().year - 2 if recent_only else 2015
    candidates: list[tuple[int, str, dict]] = []
    for account_dir in RAW_OUTGOING_ROOT.iterdir():
        if not account_dir.is_dir():
            continue
        for year_file in account_dir.glob("*.md"):
            try:
                year = int(year_file.stem)
            except ValueError:
                continue
            if year < cutoff_year:
                continue
            for msg in _parse_year_corpus(year_file):
                body = msg.get("body", "")
                if len(body) < 80 or len(body) > 1500:
                    continue
                score = _score_surface_match(body, pat)
                if score >= 2:
                    candidates.append((score, msg.get("date", ""), msg))
    if not candidates:
        return ""
    # Prefer high-score AND recent — sort by (score desc, date desc)
    candidates.sort(key=lambda x: (-x[0], x[1]), reverse=False)
    candidates.sort(key=lambda x: (x[0], x[1]), reverse=True)
    chosen = candidates[:n]
    if not chosen:
        return ""

    lines = [
        f"# VERBATIM EXEMPLARS — {surface}",
        "",
        f"Below are **{len(chosen)} actual past Matt emails** of the `{surface}` "
        "surface, picked from his outgoing corpus by keyword match + recency. "
        "**Mirror these.** They are stronger signal than the abstract patterns "
        "in the SURFACE PATTERNS section. Voice, structure, opener, length, "
        "closer — model your draft after these specific shapes.",
        "",
    ]
    for _score, _date, m in chosen:
        date = m.get("date", "?")
        to = (m.get("to") or "?")[:80]
        subject = (m.get("subject") or "")[:100]
        body = m["body"][:1000]
        lines.append(f"## {date} — to {to}")
        if subject:
            lines.append(f"_subject: {subject}_")
        lines.append("")
        lines.append("```")
        lines.append(body)
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def load_recipient_exemplars(recipient: str | None, n: int = 3) -> str:
    """Pull N most-recent verbatim past Matt-to-this-recipient emails. Mirrors
    actual dyad voice; pairs with recipient_patterns/<email>.md (rules) by
    showing concrete shapes the rules describe.
    """
    if not recipient or not RAW_OUTGOING_ROOT.exists():
        return ""
    matches: list[dict] = []
    rec_lower = recipient.lower()
    for account_dir in RAW_OUTGOING_ROOT.iterdir():
        if not account_dir.is_dir():
            continue
        for year_file in account_dir.glob("*.md"):
            for msg in _parse_year_corpus(year_file):
                to_raw = (msg.get("to") or "")
                em = re.search(r"[\w\.\+\-]+@[\w\.\-]+", to_raw)
                if not em or em.group(0).lower() != rec_lower:
                    continue
                body = msg.get("body", "")
                if 60 <= len(body) <= 1500:
                    matches.append(msg)
    if not matches:
        return ""
    matches.sort(key=lambda m: m.get("date", ""), reverse=True)
    chosen = matches[:n]
    lines = [
        f"# VERBATIM EXEMPLARS — to {recipient}",
        "",
        f"**{len(chosen)} most-recent past Matt-to-{recipient} emails.** "
        "**Mirror their exact opener, length, register, and closer** — these "
        "are the dyad's actual shape. Stronger signal than the abstract rules "
        "in the RECIPIENT-SPECIFIC PATTERNS section.",
        "",
    ]
    for m in chosen:
        date = m.get("date", "?")
        subject = (m.get("subject") or "")[:100]
        body = m["body"][:1000]
        lines.append(f"## {date}")
        if subject:
            lines.append(f"_subject: {subject}_")
        lines.append("")
        lines.append("```")
        lines.append(body)
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


def load_negative_space_corpus(max_samples: int = 24) -> str:
    """Load era-weighted samples from raw_outgoing/. Recent years sampled
    aggressively per voice_drift_report.md recommendation — pre-2018 voice is
    actively misleading for current register. Returns a markdown anchor block,
    or empty string if corpus doesn't exist yet.
    """
    if not RAW_OUTGOING_ROOT.exists():
        return ""
    import random
    by_year: dict[int, list[dict]] = {}
    for account_dir in RAW_OUTGOING_ROOT.iterdir():
        if not account_dir.is_dir():
            continue
        for year_file in account_dir.glob("*.md"):
            try:
                year = int(year_file.stem)
            except ValueError:
                continue
            for msg in _parse_year_corpus(year_file):
                msg["account"] = account_dir.name
                by_year.setdefault(year, []).append(msg)
    if not by_year:
        return ""

    weights = {y: ERA_WEIGHTS.get(y, 1.0 / max(1, dt.datetime.now().year - y + 1) ** 2)
               for y in by_year}
    total_weight = sum(weights.values())
    quotas = {y: max(1, int(round(max_samples * w / total_weight))) for y, w in weights.items()}

    # Cap at max_samples while respecting quotas (favor newer years if over)
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
        f"# RAW OUTGOING (NEGATIVE SPACE) — {len(chosen)} samples across "
        f"{len(set(m.get('date','')[:4] for m in chosen))} year(s)",
        "",
        "Real outgoing emails from Matt's Gmail history that FM did NOT draft. "
        "Use these as voice ground truth — what Matt actually sounds like when "
        "left to himself. Recent years sampled more heavily than older. Don't "
        "quote these directly; treat as voice fingerprint.",
        "",
    ]
    for m in chosen:
        date = m.get("date", "?")
        to_addr = m.get("to", "?")[:80]
        subject = m.get("subject", "")[:80]
        body = m["body"][:1200]  # cap each sample to 1200 chars
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
    """Load recipient-specific patterns from `recipient_patterns/<email>.md`
    (auto-mined per top-N recipients). Returns the file body as an anchor block,
    or empty string if this recipient hasn't been mined yet. Strips frontmatter
    + the auto-generated lead so injection is clean.
    """
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
        "These are patterns mined exclusively from past Matt-to-this-recipient "
        "messages. **They override universal/surface patterns when they conflict.** "
        "If 'Recipient closer' says `Matthew` and surface says `Best, Matt`, use "
        "`Matthew`.\n\n"
        + text.strip() + "\n"
    )


def load_recipient_history(recipient: str | None, max_drafts: int = 3) -> str:
    """Pull last N drafts to this recipient from sent-log.jsonl with their
    reconciliation outcome. Closes the 'FM has amnesia between sessions' gap —
    when Matt edits a draft, the next draft to the same recipient should not
    repeat the same mistake.
    """
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
    matches = matches[-max_drafts:]  # most recent N
    out_parts = [
        f"# PRIOR DRAFTS TO {recipient} (last {len(matches)}, oldest first)\n\n"
        "These are previous drafts FM produced for this recipient and how Matt "
        "responded. **Use them to avoid repeating the same edits.** If a prior "
        "draft was reshaped, do not regenerate the original shape."
    ]
    for r in matches:
        ts = r.get("ts", "?")
        ed = r.get("edit_distance")
        if r.get("checked"):
            outcome = (
                f"kept verbatim" if ed == 0 or ed is None
                else f"edited ({ed} changed lines)"
            )
        else:
            outcome = "pending reconciliation (still draft or not yet sent)"
        body = (r.get("generated_body") or "").strip()
        out_parts.append(
            f"\n## Draft {ts}  —  outcome: {outcome}\n\n```\n{body}\n```"
        )
    return "\n".join(out_parts)


SURFACE_PATTERN_FILES = {
    "cold-outreach":         VAULT_ROOT / "_style" / "cold_outreach_voice_patterns.md",
    "warm-intro":            VAULT_ROOT / "_style" / "warm_intro_voice_patterns.md",
    "investor-update":       VAULT_ROOT / "_style" / "investor_update_voice_patterns.md",
    "post-meeting-followup": VAULT_ROOT / "_style" / "post_meeting_followup_voice_patterns.md",
    "catchup-reconnect":     VAULT_ROOT / "_style" / "catchup_reconnect_voice_patterns.md",
}


def detect_surface(task: str | None, register: str | None,
                   has_thread: bool, recipient: str | None) -> str | None:
    """Pick the most relevant email surface from signals available at draft time.
    Returns one of SURFACE_PATTERN_FILES keys, or None for the universal default.
    Stacked priority: explicit task verbs first, then thread+register heuristics.
    """
    t = (task or "").lower()
    if not task:
        # Inferred only from thread + register
        if not has_thread and register == "A":
            return "cold-outreach"
        return None
    # Explicit task-verb signals
    if re.search(r"\bintro(duc(e|ing|tion))?\b", t):
        return "warm-intro"
    if re.search(r"\b(follow.?up|after (our|the|today's|yesterday's|the call)|recap|next steps|thanks for (the call|your time|jumping|taking))\b", t):
        return "post-meeting-followup"
    if re.search(r"\b(quarterly|monthly|annual|investor|LP|fund) update\b", t) or \
       re.search(r"\b(MRR|ARR|runway|portfolio update)\b", t):
        return "investor-update"
    if re.search(r"\b(catch up|catching up|catchup|reconnect|been (a |so )?long)\b", t):
        return "catchup-reconnect"
    # Cold outreach heuristic — first-touch + Register A typically
    if not has_thread and register == "A" and \
       re.search(r"\b(reach out|introducing myself|pitch|cold|outreach|fundraising|raising|investor outreach)\b", t):
        return "cold-outreach"
    return None


def detect_identity_context(
    explicit: str,
    task: str | None,
    reply_account: str | None,
    recipient: str | None,
    vault_content: str,
) -> str:
    if explicit != "auto":
        return explicit
    t = " ".join([
        task or "",
        reply_account or "",
        recipient or "",
        vault_content[:2000] if vault_content else "",
    ]).lower()
    if "zergai.com" in t or "zerg" in t or "head of growth" in t:
        return "matt_zerg_professional"
    return "matt_personal_professional"


def identity_context_block(identity_context: str) -> str:
    return f"""# ACTIVE IDENTITY CONTEXT

Identity context: `{identity_context}`

Use `fakematt_contexts.md` as the routing contract:
- `matt_personal_professional`: write as Matt personally, using `professional_voice.md` and recipient history. Do not apply Zerg public-prose bans mechanically.
- `matt_zerg_professional`: write as Matt at Zerg. Preserve Matt's professional voice and A/B/C register, but inherit Zerg claim discipline: avoid grandiosity, source or soften load-bearing claims, and label roadmapped capabilities if this could be forwarded externally.

Important conflict rule: "Let me know if..." is valid Matt email voice. Do not remove it merely because it would be weak in public blog prose."""


def load_surface_patterns(surface: str | None) -> str:
    """Load the matching <surface>_voice_patterns.md as a PRESCRIPTIVE anchor
    block — patterns are requirements, not suggestions. The drafter must
    apply each numbered move and self-report in the brief which ones it
    applied. Round 16 fix: round-15 calibration scored cold-outreach at 58
    because surface patterns were treated as advisory; this rewrite makes
    them mandatory.

    Returns empty string if the file doesn't exist yet or if surface is None.
    """
    if not surface:
        return ""
    path = SURFACE_PATTERN_FILES.get(surface)
    if not path or not path.exists() or path.stat().st_size < 200:
        return ""
    text = path.read_text()
    text = re.sub(r"^---\n.*?\n---\n", "", text, count=1, flags=re.S)
    surface_label = surface.replace('-', ' ').title()
    return (
        f"# SURFACE PATTERNS — {surface_label} (PRESCRIPTIVE, NOT ADVISORY)\n\n"
        f"This draft is a **{surface}** email. The patterns below are "
        f"REQUIREMENTS, not suggestions. They were mined directly from Matt's "
        f"actual {surface} emails — generic professional alternatives are "
        f"DRIFT.\n\n"
        f"## RULES FOR EVERY {surface_label.upper()} DRAFT\n\n"
        f"1. **Adopt the highest-frequency opening pattern** below. Do not "
        f"open with a generic 'Hi <Name>, I'm Matt' template.\n"
        f"2. **Apply at least 2 structural moves** from the structural moves "
        f"section. The `{surface}` shape is defined by these moves.\n"
        f"3. **Use ≥1 specificity technique** (named comparator, exact format, "
        f"quantified target). Generic claims are anti-pattern for this surface.\n"
        f"4. **Close with the highest-frequency closing pattern.** Do not "
        f"invent a new closer.\n"
        f"5. **Avoid every anti-pattern** listed below. The judge in round-15 "
        f"calibration explicitly flags these as score-killers.\n"
        f"6. **In the brief, emit `SURFACE_CHECKLIST_APPLIED:`** listing the "
        f"specific patterns you applied (by short title from the sections "
        f"below). This is mandatory — empty list = failed surface application.\n\n"
        + text.strip() + "\n"
    )


def load_anchors(recipient: str | None = None, register: str | None = None,
                 inject_context: bool = True, task: str | None = None,
                 has_thread: bool = False, identity_context: str = "matt_zerg_professional",
                 include_subject_patterns: bool = False) -> str:
    """Exemplar-first anchor assembly (2026-06-02 voice overhaul).

    Order matters: measured structural priors + verbatim exemplars carry the
    voice; everything after is supporting context. The old kitchen-sink
    assembly (full voice docs + 24K corpus dump + drift report + tier-map
    JSON + prescriptive pattern checklists) buried the signal in rules and
    produced checklist caricature — see the 2026-06-02 swag RFQ drafts.
    """
    parts = []

    # 1. Measured structural priors — the hard envelope every draft must fit.
    #    Exception: first-contact vendor RFQs get the Threadbird template block
    #    (Matt-confirmed 3x on 2026-06-02) instead of the short-prose envelope.
    #    "First-contact" means NOT a reply — replies within an RFQ thread use
    #    the normal reply envelope.
    is_rfq = is_first_contact_rfq(task) and not has_thread
    priors = compute_structural_priors()
    priors_block = render_priors_block(priors, is_reply=has_thread, is_rfq=is_rfq)
    if priors_block:
        parts.append(priors_block)

    # 2. Verbatim exemplars — recipient dyad first (strongest), then surface,
    #    then task-similarity retrieval. Task retrieval backfills so EVERY
    #    draft sees at least 5 real Matt emails, even for brand-new
    #    recipients on unrecognized surfaces (the gap that produced the
    #    caricature drafts).
    n_exemplars = 0
    rec_exemplars = load_recipient_exemplars(recipient)
    if rec_exemplars:
        parts.append(rec_exemplars)
        n_exemplars += 3
    surface = detect_surface(task, register, has_thread, recipient)
    surf_exemplars = load_surface_exemplars(surface)
    if surf_exemplars:
        parts.append(surf_exemplars)
        n_exemplars += 3
    if n_exemplars < 5:
        task_exemplars = load_task_exemplars(
            task or "", n=5 - n_exemplars if n_exemplars else 5,
            is_reply=True if has_thread else None,
        )
        if task_exemplars:
            parts.append(task_exemplars)

    # 3. Identity context (short routing contract).
    parts.append(identity_context_block(identity_context))

    # 4. The learning loop: Matt's actual edits to prior drafts.
    if CORRECTIONS.exists() and CORRECTIONS.stat().st_size > 0:
        parts.append(
            "# MATT'S EDITS TO PRIOR DRAFTS (don't repeat these mistakes)\n\n"
            + CORRECTIONS.read_text()
        )
    if LEARNED_PATTERNS.exists() and LEARNED_PATTERNS.stat().st_size > 200:
        parts.append(
            "# LEARNED PATTERNS (auto-promoted from Matt's edits)\n\n"
            "Context for judgment — NOT a checklist to deploy. The exemplars "
            "above define the voice.\n\n"
            + LEARNED_PATTERNS.read_text()
        )

    # 5. Recipient-specific memory (dyad history + mined patterns).
    history = load_recipient_history(recipient)
    if history:
        parts.append(history)
    rec_patterns = load_recipient_patterns(recipient)
    if rec_patterns:
        parts.append(rec_patterns)

    # 6. Situational context (register-gated; never for Register A).
    if inject_context:
        ctx = load_recent_context(register)
        if ctx:
            parts.append(ctx)

    # 7. Subject patterns — only when the caller asked for subject generation.
    if include_subject_patterns and SUBJECT_PATTERNS.exists():
        parts.append(f"# SUBJECT LINE PATTERNS\n\n{SUBJECT_PATTERNS.read_text()}")

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


SYSTEM_PROMPT = """You are drafting an email AS Matt Eisner. Not "in Matt's style" — AS him. The reader must not be able to tell this wasn't typed by Matt on his phone between meetings.

# How voice works here (read this before anything else)

The VERBATIM EXEMPLARS below are real emails Matt sent. They are the ONLY source of voice. The MEASURED STRUCTURE block is the statistical envelope of his real emails. Everything else in this prompt (register notes, recipient context, corrections) is supporting information — when anything conflicts with the exemplars or the measured structure, the exemplars and structure win.

What this means concretely:
- Matt's real emails are SHORT. Most are 2–4 sentences. If your draft is longer than the exemplars, you have failed, regardless of how much information the task contains.
- Matt does not write structured documents in email. No bullet specs, no section headers, no "Here's what we're looking at:" blocks. If the task has 6 sub-questions, Matt asks the 1–2 that matter and trusts the conversation to surface the rest.
- Matt does not introduce himself with role/title. The from-address does that.
- Matt's voice tics (em-dashes, "happy to", "let me know") are NOT a checklist. They appear in his writing at natural frequency — which you absorb from the exemplars, not from deploying them deliberately. A draft with every tic reads as a parody.
- Matt is smart and busy. His emails compress: the single ask, the essential context in half a sentence, done. Padding is the loudest AI tell.

# Two-step process (do both, in order)

**STEP 1 — CONTENT PLAN (think before you write).** Before drafting, decide:
- What does this recipient actually need to know to act? (one line)
- What is the single ask? (one line — if the task lists many asks, pick the one that unlocks the others; the rest can ride in a clause or wait for the reply)
- What would Matt cut? (everything not load-bearing)

**STEP 2 — DRAFT.** Write the email following the content plan, shaped like the exemplars. Then check it against MEASURED STRUCTURE. If it's outside the envelope (too long, bullets, self-intro, headers), rewrite it before emitting.

# Hard rules

1. **Match the register**: A=Formal-Warm ("Hi Name," + "Best, Matthew"), B=Mid-Casual, C=Casual-Pro ("Hey Name," + no closer). Don't cross registers.
2. **Match the identity context**: `matt_personal_professional` = Matt personally. `matt_zerg_professional` = Matt at Zerg — same voice, but claims about Zerg stay sourced/soft.
3. **Never invent recipient context.** If you need background, ask in the Brief instead of fabricating.
4. **Banned phrases** (pure AI-template, Matt never writes these): "I hope this email finds you well", "Please don't hesitate to reach out", "Sincerely,", "Kind regards,", "I'm excited to", "I wanted to reach out".
5. **Punctuation (corpus-verified 2026-06-02):** Matt types plain ' - ' for asides — never em-dash '—' or en-dash '–' (those appear in 2% of his real emails and are a loud AI tell). Number ranges use plain hyphens too: "500-1000", not "500–1000".
6. **Sign-off name (corpus-verified):** when signing, it's "Matthew" — never bare "Matt" (0 of 742 real emails sign "Matt"). Many emails have no sign-off at all; that's fine too.
7. **Greeting (corpus-verified):** the recipient's first name, "Hi team," for a group inbox, or no greeting at all. Never "Hi there," (0 of 742 real emails).
8. **One ask at a time.** Real Matt asks the one question that unlocks the rest and lets the reply surface the details. Bundling 4+ sub-questions into one email is an AI tell — pick the load-bearing ask, fold at most 1-2 others into a single trailing clause, drop the rest.

# Output format

Produce TWO sections, separated by a markdown horizontal rule:

```
# Draft

<the email body, ready to copy-paste — no subject line unless the caller asks>

---

# Brief

**Content plan:** the 3 lines from STEP 1 (recipient needs / single ask / what got cut).

**Register chosen:** A / B / C — one-sentence reason.

**Identity context:** matt_personal_professional / matt_zerg_professional — one-sentence reason.

**RESEMBLANCE_CHECK:** compare your draft against the exemplars and measured structure:
- word count: <draft words> vs exemplar median <N> — PASS/FAIL
- structure: prose/bullets/headers vs exemplars — PASS/FAIL
- ceremony: self-intro/sign-off weight vs exemplars — PASS/FAIL
If any line is FAIL, you should have rewritten before emitting. A FAIL here means the draft is not done.

**Open questions for Matt:** anything you couldn't infer from the context ("none" if straightforward).

**RECOMMEND_TIER:** A / B / C / EXCLUDED — only emit if the recipient was NOT already in tier_map.json (the request said the register was a FALLBACK).

**SELF_CONFIDENCE:** HIGH | MEDIUM | LOW — HIGH only if the draft passes all RESEMBLANCE_CHECK lines AND the content plan addresses the task. Pattern coverage does not count toward confidence; resemblance does.
```

The Brief is for Matt's review. Keep it short and honest."""


def compute_decision_trace(
    recipient: str | None,
    register: str | None,
    identity_context: str,
    register_note: str,
    fallback_used: bool,
    context_injected: bool,
    brief: str,
    structural_violations: list | None = None,
) -> dict:
    """Build the structured decision-trace record. Combines deterministic facts
    we control (register source, recipient memory stats, structural check) with
    the LLM's self-report (RESEMBLANCE_CHECK, SELF_CONFIDENCE) parsed from the
    brief.
    """
    # Deterministic: prior drafts to this recipient
    prior_total = 0
    prior_kept = 0
    prior_edited = 0
    prior_pending = 0
    if recipient and SENT_LOG.exists():
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
                    if (rec.get("to") or "").lower() != recipient.lower():
                        continue
                    prior_total += 1
                    if not rec.get("checked"):
                        prior_pending += 1
                        continue
                    ed = rec.get("edit_distance") or 0
                    if ed >= 2:
                        prior_edited += 1
                    else:
                        prior_kept += 1
        except Exception:
            pass

    # LLM self-report from the brief
    resemblance = "not reported"
    confidence = "—"
    if brief:
        m = re.search(r"^\s*\*\*?RESEMBLANCE_CHECK:?\*\*?\s*(.+?)(?:\n\*\*|\Z)", brief, re.S | re.M)
        if m:
            # collapse the check lines into one summary string
            check_lines = [l.strip().lstrip("- ") for l in m.group(1).strip().splitlines() if l.strip()]
            resemblance = "; ".join(check_lines)[:400]
        m = re.search(r"^\s*\*\*?SELF_CONFIDENCE:?\*\*?\s*(HIGH|MEDIUM|LOW)\b\s*[-—]?\s*(.*?)(?:\n\n|\Z)",
                      brief, re.S | re.M | re.I)
        if m:
            level = m.group(1).upper()
            reason_lines = m.group(2).strip().splitlines()
            reason = reason_lines[0].strip()[:200] if reason_lines else ""
            confidence = f"{level} — {reason}" if reason else level

    if fallback_used:
        register_source = "fallback"
    elif register_note.startswith("AUTO-CLASSIFIED"):
        register_source = "auto_classified"
    elif register_note.startswith("(forced"):
        register_source = "forced"
    else:
        register_source = "tier_map"
    return {
        "register": register,
        "identity_context": identity_context,
        "register_source": register_source,
        "register_note": register_note,
        "context_injected": context_injected,
        "prior_drafts_total": prior_total,
        "prior_drafts_kept": prior_kept,
        "prior_drafts_edited": prior_edited,
        "prior_drafts_pending": prior_pending,
        "resemblance_check": resemblance,
        "self_confidence": confidence,
        "structural_violations": structural_violations or [],
    }


def render_decision_trace(trace: dict) -> str:
    lines = ["## Decision trace", ""]
    lines.append(f"- **Register:** {trace['register']} _(source: {trace['register_source']})_")
    lines.append(f"- **Identity context:** {trace.get('identity_context', 'unknown')}")
    pt = trace["prior_drafts_total"]
    if pt:
        lines.append(
            f"- **Recipient memory:** {pt} prior draft(s) — "
            f"{trace['prior_drafts_kept']} kept verbatim, "
            f"{trace['prior_drafts_edited']} edited, "
            f"{trace['prior_drafts_pending']} pending reconciliation"
        )
    else:
        lines.append("- **Recipient memory:** none (first draft to this address)")
    lines.append(f"- **Project context injected:** {'yes' if trace['context_injected'] else 'no'}")
    lines.append(f"- **Resemblance check (FM self-report):** {trace['resemblance_check']}")
    lines.append(f"- **Confidence (FM self-report):** {trace['self_confidence']}")
    sv = trace.get("structural_violations") or []
    if sv:
        lines.append(f"- **⚠ STRUCTURAL VIOLATIONS (deterministic check, post-revision):** "
                     + "; ".join(v.split(":")[0] for v in sv))
    else:
        lines.append("- **Structural check (deterministic):** PASS — inside Matt's measured distribution")
    return "\n".join(lines)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--to", help="recipient email")
    ap.add_argument("--task", help="what the email should accomplish")
    ap.add_argument("--revise", type=Path, help="markdown draft to polish")
    ap.add_argument("--reply-to-id", help="Gmail message ID to reply to")
    ap.add_argument("--reply-account", default="matthew@zergai.com")
    ap.add_argument("--no-context", action="store_true",
                    help="suppress conversation-ingest project context injection "
                         "(default: inject for Register B/C, never for A)")
    ap.add_argument("--register", choices=["A","B","C"], help="force register")
    ap.add_argument(
        "--identity-context",
        choices=["auto", "matt_personal_professional", "matt_zerg_professional"],
        default="auto",
        help="Whether this professional email is Matt personally or Matt speaking for/at Zerg.",
    )
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--create-draft", action="store_true")
    ap.add_argument("--subject", help="explicit subject (otherwise inferred from --reply-to-id or generated)")
    ap.add_argument("--subject-task", action="store_true",
                    help="ask the LLM to generate a Matt-style subject (uses subject_patterns.md)")
    ap.add_argument("--model", default=None,
                    help=f"Claude model id (default: aitr pick, falling back to {DEFAULT_MODEL})")
    args = ap.parse_args()

    if not (args.task or args.revise or args.reply_to_id):
        print("error: need --task or --revise or --reply-to-id", file=sys.stderr)
        return 2

    # Model resolution: explicit --model > aitr pick > DEFAULT_MODEL (loud fallback).
    # quality_floor=high-stakes: voice drafting never runs on cheap models.
    if args.model is None:
        global _AITR_DECISION_ID
        args.model, _AITR_DECISION_ID = aitr_pick_or(
            DEFAULT_MODEL,
            task_kind="draft-prose",
            caller="fakematt-email",
            quality_floor="high-stakes",
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)

    # Load thread + vault context FIRST so the LLM classifier has signal to use
    # if this is a first-encounter recipient.
    thread_ctx_text = ""
    if args.reply_to_id:
        thread_ctx_text = load_thread_context(args.reply_to_id, args.reply_account)
    vault_path, vault_content = find_vault_context(args.to)
    identity_context = detect_identity_context(
        args.identity_context,
        args.task,
        args.reply_account,
        args.to,
        vault_content or "",
    )

    # Determine register
    register = args.register or lookup_register(args.to)
    auto_classified = False
    classifier_rationale = ""
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

    # First-encounter LLM classifier — runs only when there's no explicit
    # --register and no tier_map entry. Persists confident classifications
    # immediately so future drafts skip this path.
    if not register and args.to:
        cls = classify_register_via_llm(args.to, thread_ctx_text, vault_content)
        if cls and cls.get("register") == "EXCLUDED":
            append_tier_map(args.to, "EXCLUDED",
                            reason=f"LLM classifier: {cls.get('rationale','')}")
            print(f"[fakematt-email] classifier: EXCLUDED → forwarding to fakematt-personal", file=sys.stderr)
            personal_skill = Path.home() / ".claude" / "skills" / "fakematt-personal" / "run.py"
            if personal_skill.exists():
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
        elif cls and cls.get("register") in ("A", "B", "C") and \
                cls.get("confidence", "").lower() in ("high", "medium"):
            register = cls["register"]
            classifier_rationale = cls.get("rationale", "")
            auto_classified = True
            append_tier_map(
                args.to, register,
                reason=f"LLM classifier {cls.get('confidence','?')}: {classifier_rationale}",
            )
            print(
                f"[fakematt-email] auto-classified: {register} "
                f"({cls.get('confidence')}) — {classifier_rationale}",
                file=sys.stderr,
            )
        elif cls:
            classifier_rationale = (
                f"classifier said {cls.get('register')} ({cls.get('confidence')}): "
                f"{cls.get('rationale','')}"
            )

    if not register:
        register = "B"  # safe default
        if classifier_rationale:
            register_note = f"FALLBACK to B (low-confidence classifier — {classifier_rationale})"
        else:
            register_note = f"FALLBACK to B (mid-casual) — {args.to} not in tier_map; revise via --register if needed."
    elif auto_classified:
        register_note = f"AUTO-CLASSIFIED via LLM: {register} — {classifier_rationale}"
    else:
        register_note = f"From tier_map: {register}"

    # Build user message
    fallback_used = (
        register == "B"
        and not args.register
        and not lookup_register(args.to)
        and not auto_classified
    )
    user_parts = [
        f"Recipient: {args.to or '(unspecified)'}",
        f"Register: {register} — {register_note}",
        f"Identity context: {identity_context}",
    ]
    if fallback_used:
        user_parts.append(
            "(Note: this is a FALLBACK classification because the recipient is "
            "not yet in tier_map.json. Emit a RECOMMEND_TIER line in the Brief "
            "so the skill can persist your judgment.)"
        )
    if args.task:
        user_parts.append(f"\n# Task\n{args.task}")
        if is_first_contact_rfq(args.task) and not args.reply_to_id:
            user_parts.append(
                "\n# TASK-TYPE OVERRIDE: FIRST-CONTACT VENDOR RFQ\n"
                "This task is a first-contact vendor RFQ. The system prompt's "
                "compression rules (no bullets, one ask, no self-intro, no "
                "\"Here's what we're looking at:\" blocks) DO NOT APPLY here — "
                "follow the FIRST-CONTACT VENDOR RFQ TEMPLATE OVERRIDE block in "
                "the anchors instead. Matt confirmed that template three times "
                "on 2026-06-02; it is what he actually sends to vendors."
            )
    if args.revise and args.revise.exists():
        user_parts.append(f"\n# Existing draft to polish\n{args.revise.read_text()}")
    if thread_ctx_text:
        user_parts.append(f"\n# Thread you're replying to\n{thread_ctx_text}")

    # #3: Vault context injection — pull the recipient's People/Companies file if it exists
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

    anchors = load_anchors(recipient=args.to, register=register,
                           inject_context=not args.no_context,
                           task=args.task, has_thread=bool(args.reply_to_id),
                           identity_context=identity_context,
                           include_subject_patterns=bool(args.subject_task))

    # Single-prompt CLI wrapper (call_claude takes one prompt blob)
    print(f"[fakematt-email] register={register}, identity_context={identity_context}, model={args.model}", file=sys.stderr)
    full_prompt = (
        SYSTEM_PROMPT
        + "\n\n---\n\n"
        + anchors
        + "\n\n---\n\n# REQUEST\n\n"
        + "\n".join(user_parts)
    )
    response = call_claude(full_prompt, model=args.model)

    def _normalize_response(text: str) -> str:
        """Cut any preamble before '# Draft'. The claude CLI subprocess can
        inherit user-level hooks (UserPromptSubmit gates) whose injected
        reminders the model sometimes responds to before emitting the draft —
        that meta-commentary must never reach the draft file or the
        structural check."""
        m = re.search(r"(?m)^#\s*Draft\s*$", text)
        return text[m.start():] if m else text

    response = _normalize_response(response)

    def _draft_body(text: str) -> str:
        """Extract just the email body (between '# Draft' and the brief
        separator) for the structural check."""
        body = text.strip()
        m = re.search(r"^#\s*Draft\s*\n+(.*?)(?:\n---\s*\n|\Z)", body, re.S | re.M)
        return m.group(1).strip() if m else body.partition("\n---\n")[0]

    # Post-generation structural resemblance check (deterministic). If the
    # draft falls outside Matt's measured distribution, run ONE revision pass
    # with the violations spelled out. This is the gate the old system lacked:
    # it measured pattern deployment, not resemblance.
    # First-contact vendor RFQs check against the Threadbird template envelope
    # instead (Matt-confirmed 3x on 2026-06-02). Replies in RFQ threads are
    # NOT first-contact — they use the normal reply envelope.
    is_rfq = is_first_contact_rfq(args.task) and not args.reply_to_id
    draft_only = _draft_body(response)
    priors = compute_structural_priors()
    violations = structural_check(draft_only, priors,
                                  is_reply=bool(args.reply_to_id),
                                  is_rfq=is_rfq)
    if violations:
        print(f"[fakematt-email] structural check FAILED ({len(violations)} violation(s)) — revision pass",
              file=sys.stderr)
        for v in violations:
            print(f"  - {v.splitlines()[0]}", file=sys.stderr)
        if is_rfq:
            revision_coda = (
                "\n\nThe fix is template fidelity: this is a first-contact vendor "
                "RFQ, so restore every missing Threadbird-template beat "
                "(quantities bullets, flex line, design bullets, punchline, asks "
                "bullets, art-files line). Do NOT compress to short prose."
            )
        else:
            revision_coda = (
                "\n\nThe fix is compression: cut content, don't cram it into fewer "
                "lines. Pick the single ask that matters; everything else waits "
                "for the reply or moves to a linked doc."
            )
        revision_prompt = (
            full_prompt
            + "\n\n---\n\n# YOUR PREVIOUS DRAFT (failed the structural resemblance check)\n\n"
            + response
            + "\n\n# STRUCTURAL VIOLATIONS — fix every one, then re-emit the full Draft + Brief\n\n"
            + "\n".join(f"- {v}" for v in violations)
            + revision_coda
        )
        revised = _normalize_response(call_claude(revision_prompt, model=args.model))
        re_violations = structural_check(
            _draft_body(revised), priors,
            is_reply=bool(args.reply_to_id),
            is_rfq=is_rfq)
        if len(re_violations) < len(violations):
            response = revised
            violations = re_violations
        if violations:
            print(f"[fakematt-email] WARNING: {len(violations)} violation(s) remain after revision — "
                  "draft is flagged in the brief", file=sys.stderr)

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

    # Surface any unresolved structural violations at the top of the brief so
    # Matt sees the warning before the self-report.
    if violations:
        warn = (
            "> ⚠ **STRUCTURAL CHECK FAILED (post-revision).** This draft is still "
            "outside Matt's measured email distribution:\n"
            + "\n".join(f"> - {v}" for v in violations)
            + "\n\n"
        )
        brief = warn + brief

    draft_path = base.with_suffix(".draft.md")
    brief_path = base.with_suffix(".brief.md")
    draft_path.write_text(draft.strip() + "\n")
    brief_path.write_text(brief.strip() + "\n" if brief else "(no brief produced)\n")

    print(f"\n=== DRAFT ({draft_path}) ===\n{draft.strip()}\n")
    if brief.strip():
        print(f"\n=== BRIEF ({brief_path}) ===\n{brief.strip()}\n")

    # Decision trace — combines deterministic facts + LLM self-report. Saved
    # to sent-log so the Monday digest can surface aggregate confidence trends.
    trace = compute_decision_trace(
        recipient=args.to,
        register=register,
        identity_context=identity_context,
        register_note=register_note,
        fallback_used=fallback_used,
        context_injected=(not args.no_context) and register != "A",
        brief=brief,
        structural_violations=violations,
    )
    trace_md = render_decision_trace(trace)
    trace_path = base.with_suffix(".trace.md")
    trace_path.write_text(trace_md + "\n")
    print(f"\n=== DECISION TRACE ({trace_path}) ===\n{trace_md}\n")

    # #2: Tier-map autocomplete — if we used a fallback and the LLM emitted a
    # RECOMMEND_TIER line, persist it back to tier_map.json.
    if fallback_used and args.to and brief:
        rec = re.search(r"^\s*\*\*?RECOMMEND_TIER:?\*\*?\s*([ABC]|EXCLUDED)\b", brief, re.M)
        if rec:
            new_tier = rec.group(1)
            append_tier_map(args.to, new_tier, reason=f"auto from {ts}")
            print(f"[fakematt-email] tier_map updated: {args.to} → {new_tier}", file=sys.stderr)

    # Extract clean body — content between "# Draft" and trailing "---" or EOF.
    # Done unconditionally so the learning ledger captures stdout-only invocations
    # (the dominant case) — learn.py reconciles against Gmail sent folder by
    # `to:<addr> after:<date>` and doesn't require a Gmail draft_id.
    m = re.search(r"^#\s*Draft\s*\n+(.*?)(?:\n---\s*$|\Z)", draft, re.S | re.M)
    body = m.group(1).strip() if m else draft.strip()

    # Determine subject (used for logging + the optional Gmail draft below)
    if args.subject:
        subject = args.subject
    elif args.subject_task and brief:
        sm = re.search(r"^\s*\*\*?SUBJECT_LINE:?\*\*?\s*(.+)$", brief, re.M)
        subject = sm.group(1).strip().strip("\"'`") if sm else "(set subject before sending)"
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

    # Always log the draft for the learning loop, even if we didn't create a
    # Gmail draft. draft_id is None on the stdout-only path; learn.py falls back
    # to a thread search by recipient + ts. Gate on args.to because reconciler
    # needs a recipient.
    if args.to:
        # Synthetic records from calibrate_voice.py are tagged so learn.py
        # skips them — otherwise we waste Gmail API quota trying to reconcile
        # drafts to fictional addresses like partner@hypotheticalseedfund.vc.
        is_synthetic = bool(__import__("os").environ.get("FAKEMATT_SYNTHETIC"))
        log_sent_attempt({
            "ts": ts,
            "draft_id": None,
            "to": args.to,
            "subject": subject,
            "register": register,
            "identity_context": identity_context,
            "reply_to_id": args.reply_to_id,
            "account": args.reply_account,
            "generated_body": body,
            "draft_file": str(draft_path),
            "create_draft_path": bool(args.create_draft),
            "context_injected": (not args.no_context) and register != "A",
            "decision_trace": trace,
            "synthetic": is_synthetic,
            "checked": is_synthetic,  # mark synthetic as already-checked so learn.py skips
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
                print(f"[sent-log] could not patch draft_id: {e}", file=sys.stderr)
        except Exception as e:
            print(f"[gmail draft] failed: {e}", file=sys.stderr)

    return 0


def _main_with_outcome() -> int:
    """Run main() and report the realized outcome of the aitr pick (when one
    was applied) so the router's reputation loop learns from drafting runs.
    Usage errors / EXCLUDED forwards (rc != 0) record nothing — they aren't
    the picked model's fault."""
    try:
        rc = main()
    except Exception as exc:
        if _AITR_DECISION_ID:
            record_outcome(_AITR_DECISION_ID, "bad", source="fakematt-email",
                           note=f"draft run failed: {type(exc).__name__}: {str(exc)[:100]}")
        raise
    if rc == 0 and _AITR_DECISION_ID:
        record_outcome(_AITR_DECISION_ID, "good", source="fakematt-email",
                       note="draft delivered")
    return rc


if __name__ == "__main__":
    sys.exit(_main_with_outcome())
