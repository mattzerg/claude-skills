#!/usr/bin/env python3
"""Structural priors + exemplar retrieval for voice skills.

The 2026-06-02 voice overhaul: generation must be grounded in what Matt's
real emails LOOK like (length, structure, openers) and in verbatim nearest
exemplars — not in abstracted "voice tells" deployed as a checklist.

Three jobs:
1. compute_structural_priors() — measured stats from raw_outgoing/ corpus,
   segmented fresh-send vs reply. Cached to structural_priors.json (7-day TTL).
2. load_task_exemplars() — task-similarity retrieval over the corpus so EVERY
   draft gets verbatim exemplars, even for new recipients + unknown surfaces
   (the gap that produced the 2026-06-02 swag RFQ caricatures).
3. structural_check() — deterministic post-generation resemblance check.
   Violations → one auto-revision pass before the draft reaches Matt.

Self-contained (own corpus parser) so fakematt-personal / fakematt-slack can
import it without pulling in fakematt-email's run.py.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import statistics
from pathlib import Path

# Default corpus root — fakematt-email's raw_outgoing sweep (19k+ real emails).
DEFAULT_CORPUS_ROOT = Path(__file__).parent / "raw_outgoing"
PRIORS_CACHE = Path(__file__).parent / "structural_priors.json"
PRIORS_TTL_DAYS = 7

# Years considered "current voice" per voice_drift_report.md era weighting.
RECENT_YEARS = ("2024", "2025", "2026")

# Quoted-thread markers — everything from the first match onward is not Matt.
QUOTE_RE = re.compile(
    r"(?m)^On .{10,90}wrote:\s*$"
    r"|^On \w{3}, \w{3} \d{1,2}, \d{4}.*$"
    r"|^>{1,}\s"
    r"|^-{5,}\s*Forwarded message\s*-{5,}"
)

# Automated/script-generated emails that Matt's account sent but Matt did not
# write — Apps Script error notifications, cron failure reports, etc. These
# contaminated 55% of the 2024-2026 corpus (922/1664 messages, all error
# notifications to jens.arne.hartwig@gmail.com) and made the measured priors
# wildly overtight (median 27 words vs real 38). Discovered 2026-06-02.
AUTOMATED_RE = re.compile(
    r"^Error:"
    r"|GoogleJsonResponseException"
    r"|^Summary of failures"
    r"|Apps Script"
    r"|^This is an automated"
    r"|^Your script,"
    r"|TypeError: Cannot read propert",
    re.I,
)

# Stop-words excluded from task-similarity scoring.
_STOP = frozenset(
    "the a an and or of to in for on with at from by is are was were be been "
    "it this that these those i you he she we they my your our their as if so "
    "not no do does did done can could would should will just about into over "
    "email draft send write reply please let know need want get make".split()
)


# ---------------------------------------------------------------------------
# Corpus parsing
# ---------------------------------------------------------------------------

def parse_year_corpus(path: Path) -> list[dict]:
    """Parse a raw_outgoing/<account>/<year>.md file into message dicts:
    {date, to, subject, msg_id, body}. Same format sweep_outgoing.py writes."""
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
        # Bare recipient email for filtering (family vs professional).
        em = re.search(r"[\w\.\+\-]+@[\w\.\-]+", meta.get("to", ""))
        if em:
            meta["recipient_email"] = em.group(0).lower()
        meta["body"] = body
        msgs.append(meta)
    return msgs


def clean_body(body: str) -> str:
    """Strip quoted thread + forwarded blocks so only Matt's own words remain."""
    m = QUOTE_RE.search(body)
    if m:
        body = body[: m.start()]
    return body.strip()


def iter_recent_messages(corpus_root: Path = DEFAULT_CORPUS_ROOT,
                         years: tuple[str, ...] = RECENT_YEARS,
                         recipient_filter: set[str] | None = None,
                         exclude_recipients: set[str] | None = None) -> list[dict]:
    """All messages from recent years across all accounts, bodies cleaned.
    Adds: clean_body, is_reply, word_count.

    recipient_filter: keep ONLY messages to these emails (e.g. family for
    fakematt-personal). exclude_recipients: drop messages to these emails
    (e.g. family, for professional-only stats)."""
    out: list[dict] = []
    if not corpus_root.exists():
        return out
    for account_dir in corpus_root.iterdir():
        if not account_dir.is_dir():
            continue
        for year in years:
            for msg in parse_year_corpus(account_dir / f"{year}.md"):
                rec = msg.get("recipient_email", "")
                if recipient_filter is not None and rec not in recipient_filter:
                    continue
                if exclude_recipients is not None and rec in exclude_recipients:
                    continue
                cb = clean_body(msg["body"])
                if len(cb) < 20:
                    continue
                # Drop script-generated mail — Matt's account sent it, Matt
                # didn't write it.
                if AUTOMATED_RE.search(cb) or AUTOMATED_RE.search(msg.get("subject") or ""):
                    continue
                msg["clean_body"] = cb
                msg["is_reply"] = (msg.get("subject") or "").lower().startswith("re:")
                msg["word_count"] = len(cb.split())
                out.append(msg)
    return out


# ---------------------------------------------------------------------------
# Structural priors
# ---------------------------------------------------------------------------

_SELF_INTRO_RE = re.compile(
    # "I'm head of X" / "I'm the founder" / "I run X"
    r"\bI'?m (the )?(head of|founder|running|leading|a |an )"
    r"|\bI (run|lead|head)\b"
    # "I'm Matt, head of growth" / "I'm Matt Eisner — founder of" (name between)
    r"|\bI'?m [A-Z]\w+([ ,]+\w+)?[,—-]+\s*(the )?(head of|founder|cofounder|co-founder|ceo|cto)",
    re.I,
)
_HOPE_RE = re.compile(r"hope (all is well|you.re (doing )?well)", re.I)
_BULLET_RE = re.compile(r"^\s*[-*•]\s", re.M)

# ---------------------------------------------------------------------------
# First-contact vendor RFQ task type (calibrated 2026-06-02)
#
# Matt confirmed THREE TIMES on 2026-06-02 that first-contact multi-ask vendor
# RFQs follow the Threadbird template he sent himself (message 19e88531749c0919:
# ~195 words, bulleted quantities / design / asks, self-intro, em-dashes) — NOT
# the global short-prose envelope. The global priors' reference class is
# dominated by short replies, which is the wrong reference class for this task
# type. Canonical rule:
#   ~/.claude/projects/.../memory/feedback_first_contact_rfq_minimalism.md
# ---------------------------------------------------------------------------

FIRST_CONTACT_RFQ_RE = re.compile(
    r"\bRFQ\b"
    r"|request for (a )?quote"
    r"|first[- ]contact .{0,40}(vendor|supplier|manufacturer|factory)"
    r"|(vendor|supplier|manufacturer|factory) .{0,40}first[- ]contact"
    r"|quote .{0,30}(from|for) .{0,30}(vendor|supplier|manufacturer|factory)",
    re.I,
)

# A follow-up to an RFQ already sent is NOT first-contact: the recipient has the
# specs, so the 8-beat self-introducing template (150-220 words, bullets) is the
# wrong reference class — it should use the short follow-up envelope. The RFQ
# keyword still matches above ("follow up on our swag RFQ"), so guard on
# follow-up language and negate. (2026-06-04: caught by the FM voice test —
# run.py forced the template on a threadbird follow-up and the deterministic
# structural check false-failed a correct draft.)
RFQ_FOLLOWUP_RE = re.compile(
    r"\bfollow[- ]?up\b|\bfollowing up\b|\bcircl(e|ing) back\b|\bcheck(ing)? in\b"
    r"|\bany (update|news)\b|\bhaven'?t heard\b|\bnudge\b|\bre-?ping\b|\bbump(ing)?\b"
    r"|\breminder\b|\bstill (waiting|interested)\b|\bgentle (nudge|reminder)\b",
    re.I,
)


def is_first_contact_rfq(task: str | None) -> bool:
    """True when the drafting task is a first-contact vendor RFQ — the one
    task type where Matt's own sent exemplars are long, bulleted, and
    self-introducing (Threadbird template).

    A follow-up to an already-sent RFQ is explicitly NOT first-contact, even
    though it mentions "RFQ" — it routes to the normal short-prose envelope.
    """
    if not task:
        return False
    if RFQ_FOLLOWUP_RE.search(task):
        return False
    return bool(FIRST_CONTACT_RFQ_RE.search(task))


RFQ_TEMPLATE_BLOCK = """# FIRST-CONTACT VENDOR RFQ — TEMPLATE OVERRIDE (hard constraints for THIS task type)

This task is a first-contact vendor RFQ. For this task type ONLY, the global
short-prose envelope does NOT apply. The reference class is the RFQs Matt
actually sent on 2026-06-02 (canonical: the Threadbird message, 195 words,
bulleted). Matt has confirmed this template three times; do not compress it away.

Structure (all 8 beats, in order):

1. Greeting: "Hi [Name]," (named contact) or "Hi [Vendor] team," (group inbox)
2. Intro paragraph, 3 sentences glued: "I'm Matt, head of growth at Zerg
   (zergai.com) — an early-stage AI company. I'm putting together a first run
   of [PRODUCT] for our team and shortlisted [Vendor] based on [WHY-THEM ANGLE]."
   For international vendors add: "The order will ship to the US."
3. Quantities bullets with "Here's what I'm looking at:" lead-in
4. Flex line: "Quantities are somewhat flexible — happy to bump if there's a
   meaningful price break at a higher tier."
5. Design bullets with "On design:" lead-in (2-3 bullets)
6. Punchline (own paragraph): "Premium feel matters more than lowest price for us."
7. Asks bullets with "Could you send over:" lead-in (4 bullets: vendor-specific
   rec / pricing + tiers / turnaround (+ US shipping, DDP for international) /
   sample policy; international vendors also get a Trade Assurance bullet)
8. "Happy to send art files once we confirm fit." then "Best," / "Matthew"

Envelope for this task type: 150-220 words. Bullets REQUIRED. Self-intro
REQUIRED (first contact — the recipient has never heard of Matt or Zerg).
Em-dashes are fine here (the canonical sent message uses them)."""


def _segment_stats(msgs: list[dict]) -> dict:
    if not msgs:
        return {}
    wcs = sorted(m["word_count"] for m in msgs)
    sents = sorted(len(re.findall(r"[.!?]+(?:\s|$)", m["clean_body"])) for m in msgs)
    n = len(msgs)
    bullets = sum(1 for m in msgs if _BULLET_RE.search(m["clean_body"]))
    intro = sum(1 for m in msgs if _SELF_INTRO_RE.search(m["clean_body"]))
    hope = sum(1 for m in msgs if _HOPE_RE.search(m["clean_body"]))
    openers: dict[str, int] = {}
    closers: dict[str, int] = {}
    for m in msgs:
        lines = [l for l in m["clean_body"].splitlines() if l.strip()]
        first = lines[0] if lines else ""
        if re.match(r"^Hi \w", first):
            op = "Hi <Name>,"
        elif re.match(r"^Hey\b", first):
            op = "Hey <Name>," if re.match(r"^Hey \w", first) else "Hey,"
        elif re.match(r"^Hello", first):
            op = "Hello,"
        else:
            op = "(no greeting — straight into it)"
        openers[op] = openers.get(op, 0) + 1
        low = m["clean_body"].lower()
        if re.search(r"\bbest,?\s*\n+\s*matt", low):
            cl = "Best, / Matthew"
        elif re.search(r"thanks!?\s*\n+\s*matt", low):
            cl = "Thanks! / Matthew"
        elif re.search(r"\n\s*matt(hew)?\s*$", low):
            cl = "(bare name)"
        else:
            cl = "(no closer)"
        closers[cl] = closers.get(cl, 0) + 1
    return {
        "n": n,
        "word_count": {"median": wcs[n // 2], "p25": wcs[n // 4],
                       "p75": wcs[3 * n // 4], "p90": wcs[int(n * 0.9)]},
        "sentences": {"median": sents[n // 2], "p75": sents[3 * n // 4]},
        "pct_bullets": round(100 * bullets / n, 1),
        "pct_self_intro": round(100 * intro / n, 1),
        "pct_hope_opener": round(100 * hope / n, 1),
        "openers": dict(sorted(openers.items(), key=lambda x: -x[1])),
        "closers": dict(sorted(closers.items(), key=lambda x: -x[1])),
    }


def compute_structural_priors(corpus_root: Path = DEFAULT_CORPUS_ROOT,
                              force: bool = False,
                              recipient_filter: set[str] | None = None,
                              cache_path: Path | None = None,
                              years: tuple[str, ...] = RECENT_YEARS) -> dict:
    """Measured structural stats from the recent corpus, segmented fresh vs
    reply. Cached (7-day TTL). Pass recipient_filter + a dedicated cache_path
    for sub-population priors (e.g. family-only for fakematt-personal, which
    also passes a wider `years` window since the family corpus is small)."""
    cache = cache_path or PRIORS_CACHE
    if not force and cache.exists():
        try:
            cached = json.loads(cache.read_text())
            age = dt.datetime.now() - dt.datetime.fromisoformat(cached["computed_at"])
            if age.days < PRIORS_TTL_DAYS:
                return cached
        except Exception:
            pass

    msgs = iter_recent_messages(corpus_root, years=years,
                                recipient_filter=recipient_filter)
    fresh = [m for m in msgs if not m["is_reply"]]
    replies = [m for m in msgs if m["is_reply"]]
    priors = {
        "computed_at": dt.datetime.now().isoformat(),
        "corpus_years": list(years),
        "filtered": recipient_filter is not None,
        "fresh": _segment_stats(fresh),
        "reply": _segment_stats(replies),
        "all": _segment_stats(msgs),
    }
    try:
        cache.write_text(json.dumps(priors, indent=2))
    except Exception:
        pass
    return priors


def render_priors_block(priors: dict, is_reply: bool = False, is_rfq: bool = False) -> str:
    """Render priors as a HARD CONSTRAINTS prompt block.

    is_rfq: first-contact vendor RFQs get the Threadbird template block instead
    of the global short-prose envelope (see RFQ_TEMPLATE_BLOCK)."""
    if is_rfq:
        return RFQ_TEMPLATE_BLOCK
    seg_key = "reply" if is_reply else "fresh"
    seg = priors.get(seg_key) or priors.get("all") or {}
    if not seg:
        return ""
    kind = "replies" if is_reply else "fresh (non-reply) emails"
    wc = seg["word_count"]
    top_openers = list(seg["openers"].items())[:3]
    top_closers = list(seg["closers"].items())[:3]
    opener_str = "; ".join(f"{k} ({round(100 * v / seg['n'])}%)" for k, v in top_openers)
    closer_str = "; ".join(f"{k} ({round(100 * v / seg['n'])}%)" for k, v in top_closers)
    return f"""# MEASURED STRUCTURE OF MATT'S REAL EMAILS (hard constraints, not suggestions)

Measured over {seg['n']} real {kind} Matt sent 2024–2026. Your draft MUST sit
inside this distribution — a draft outside it does not sound like Matt no
matter how many "voice patterns" it uses.

- **Length:** median {wc['median']} words, p75 {wc['p75']}, p90 {wc['p90']}.
  Your draft should be UNDER {wc['p75']} words unless the task truly demands
  more — and must never exceed {max(wc['p90'], 100)} words.
- **Sentences:** median {seg['sentences']['median']}, p75 {seg['sentences']['p75']}.
- **Bullet lists:** {seg['pct_bullets']}% of real emails use them. Default: NO bullets — write prose.
- **Self-introduction** ("I'm X, head of Y"): {seg['pct_self_intro']}% of real emails. Default: NO self-intro; the signature/from-address does that job.
- **"Hope all is well" opener:** {seg['pct_hope_opener']}% of real emails. Default: don't use it.
- **Openers:** {opener_str}
- **Closers:** {closer_str}

If you find yourself writing section headers, spec blocks, or multi-bullet
asks: STOP. Matt would put that in a linked doc or just ask the one question
that matters. Compression is the voice."""


# ---------------------------------------------------------------------------
# Task-similarity exemplar retrieval
# ---------------------------------------------------------------------------

def _tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z']{3,}", text.lower()) if w not in _STOP}


def load_task_exemplars(task: str, n: int = 5,
                        corpus_root: Path = DEFAULT_CORPUS_ROOT,
                        is_reply: bool | None = None,
                        min_words: int = 15, max_words: int = 250,
                        recipient_filter: set[str] | None = None,
                        years: tuple[str, ...] = RECENT_YEARS) -> str:
    """Top-N real corpus emails by token overlap with the task description.
    Guarantees exemplars exist for EVERY draft (new recipients, unknown
    surfaces included). Returns a markdown block; empty string if corpus
    missing. recipient_filter limits the pool (e.g. family-only)."""
    if not task:
        return ""
    msgs = iter_recent_messages(corpus_root, years=years,
                                recipient_filter=recipient_filter)
    if not msgs:
        return ""
    task_toks = _tokens(task)
    scored: list[tuple[float, dict]] = []
    for m in msgs:
        if not (min_words <= m["word_count"] <= max_words):
            continue
        if is_reply is not None and m["is_reply"] != is_reply:
            continue
        body_toks = _tokens(m["clean_body"]) | _tokens(m.get("subject") or "")
        if not body_toks:
            continue
        overlap = len(task_toks & body_toks)
        if overlap == 0:
            continue
        score = overlap / (len(task_toks) ** 0.5)
        # mild recency boost
        if (m.get("date") or "").startswith(("2025", "2026")):
            score *= 1.3
        # demote structural outliers — exemplars should model Matt's TYPICAL
        # shape (the priors handle the distribution; outliers mislead)
        if _BULLET_RE.search(m["clean_body"]):
            score *= 0.4
        if m["word_count"] > 150:
            score *= 0.6
        scored.append((score, m))
    scored.sort(key=lambda x: -x[0])
    chosen = [m for _, m in scored[:n]]

    # Backfill with recent fresh sends if similarity matches are thin —
    # exemplars must ALWAYS be present.
    if len(chosen) < n:
        pool = sorted(
            (m for m in msgs
             if min_words <= m["word_count"] <= max_words
             and (is_reply is None or m["is_reply"] == is_reply)
             and m not in chosen),
            key=lambda m: m.get("date") or "", reverse=True,
        )
        chosen.extend(pool[: n - len(chosen)])
    if not chosen:
        return ""

    lines = [
        f"# VERBATIM EXEMPLARS — {len(chosen)} real Matt emails nearest to this task",
        "",
        "These are real emails Matt sent. **Your draft must be indistinguishable "
        "from these in length, structure, rhythm, and ceremony level.** They are "
        "the ONLY source of voice — if a 'pattern' or 'rule' conflicts with what "
        "you see here, the exemplars win.",
        "",
    ]
    for m in chosen:
        date = m.get("date", "?")
        to = (m.get("to") or "?")[:70]
        subject = (m.get("subject") or "")[:90]
        lines.append(f"## {date} — to {to}")
        if subject:
            lines.append(f"_subject: {subject}_")
        lines.append("")
        lines.append("```")
        lines.append(m["clean_body"][:1500])
        lines.append("```")
        lines.append("")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Post-generation structural check
# ---------------------------------------------------------------------------

def _rfq_structural_check(draft: str) -> list[str]:
    """Threadbird-template envelope check for first-contact vendor RFQs.
    Calibrated against the canonical sent message (19e88531749c0919, 195 words)
    and feedback_first_contact_rfq_minimalism.md. Matt confirmed this template
    3x on 2026-06-02 — violations here mean the draft DEVIATES from the
    template, not that it's too long or too structured."""
    violations: list[str] = []
    body = re.sub(r"^#\s*Draft\s*\n", "", draft.strip()).strip()
    wc = len(body.split())
    if wc > 250:
        violations.append(
            f"RFQ LENGTH: draft is {wc} words; the Threadbird template runs "
            "150-220. Trim the design/asks bullets — don't cut whole beats."
        )
    if wc < 110:
        violations.append(
            f"RFQ LENGTH: draft is {wc} words; the Threadbird template runs "
            "150-220. This is the over-compressed failure mode Matt rejected — "
            "restore the missing beats (quantities bullets, design bullets, "
            "asks bullets, flex line, punchline, art-files line)."
        )
    if not _BULLET_RE.search(body):
        violations.append(
            "RFQ BULLETS MISSING: first-contact vendor RFQs use bulleted "
            "quantities / design / asks sections (Threadbird template). "
            "Prose-only RFQs are the failure mode Matt rejected on 2026-06-02."
        )
    beats = {
        "quantities lead-in (\"Here's what I'm looking at:\")":
            re.search(r"looking at:", body, re.I),
        "flex line (\"Quantities are somewhat flexible\")":
            re.search(r"flexible", body, re.I),
        "punchline (\"Premium feel matters more than\")":
            re.search(r"premium feel matters", body, re.I),
        "asks lead-in (\"Could you send over:\")":
            re.search(r"(could|can) you send", body, re.I),
        "art-files line (\"Happy to send art files\")":
            re.search(r"art files", body, re.I),
    }
    missing = [name for name, hit in beats.items() if not hit]
    if missing:
        violations.append(
            "RFQ BEATS MISSING: " + "; ".join(missing) + ". All template beats "
            "must be present (feedback_first_contact_rfq_minimalism.md)."
        )
    return violations


def structural_check(draft: str, priors: dict, is_reply: bool = False,
                     is_rfq: bool = False) -> list[str]:
    """Deterministic resemblance check. Returns a list of violations (empty =
    pass). Used for one auto-revision pass before the draft reaches Matt.

    is_rfq: first-contact vendor RFQs are checked against the Threadbird
    template envelope instead of the global short-prose envelope."""
    if is_rfq:
        return _rfq_structural_check(draft)
    seg = priors.get("reply" if is_reply else "fresh") or priors.get("all") or {}
    if not seg:
        return []
    violations: list[str] = []
    body = draft.strip()
    # strip the "# Draft" header if present
    body = re.sub(r"^#\s*Draft\s*\n", "", body).strip()
    wc = len(body.split())
    p90 = seg["word_count"]["p90"]
    p75 = seg["word_count"]["p75"]
    # Violation = longer than 90% of real Matt emails (with a floor so tiny
    # corpora don't produce absurdly tight caps).
    hard_cap = max(p90, 120)
    if wc > hard_cap:
        violations.append(
            f"LENGTH: draft is {wc} words; longer than 90% of real Matt emails "
            f"(p90 = {p90}). Aim near the median ({seg['word_count']['median']}); "
            f"cut to under {p75}."
        )
    if _BULLET_RE.search(body) and seg["pct_bullets"] < 15:
        violations.append(
            f"BULLETS: draft uses bullet lists; only {seg['pct_bullets']}% of real "
            "Matt emails do. Convert to 1–2 plain sentences, or ask the single "
            "question that matters."
        )
    if _SELF_INTRO_RE.search(body) and seg["pct_self_intro"] < 10:
        violations.append(
            f"SELF-INTRO: draft introduces Matt with role/title; only "
            f"{seg['pct_self_intro']}% of real emails do. Cut it — the from-address "
            "and signature carry identity."
        )
    if _HOPE_RE.search(body) and seg["pct_hope_opener"] < 10:
        violations.append(
            f"TEMPLATE OPENER: 'Hope all is well' appears in only "
            f"{seg['pct_hope_opener']}% of real Matt emails. Cut it; open with the "
            "actual content."
        )
    n_headers = len(re.findall(r"(?m)^#{1,4}\s|^\*\*[^*]+:\*\*\s*$", body))
    if n_headers >= 2:
        violations.append(
            "SECTION HEADERS: draft uses section headers / labeled blocks; real "
            "Matt emails are plain prose paragraphs."
        )
    # RFQ-template shape: 2+ colon-introduced lists ("Here's what I'm looking
    # at:" ... "Could you send over:" ...). Real Matt never structures an email
    # as a spec document — this is the 2026-06-02 caricature signature.
    colon_lists = len(re.findall(r"(?m)^.{0,60}:\s*$\n+\s*[-*•\d]", body))
    if colon_lists >= 2:
        violations.append(
            "RFQ-TEMPLATE SHAPE: draft has multiple colon-introduced list blocks "
            "('Here's what...:' / 'Could you send...:'). Real Matt emails are "
            "prose — compress to the one ask that matters and fold the rest into "
            "a trailing clause."
        )
    # --- Tells confirmed by LLM-judge + corpus verification 2026-06-02 ---
    if "—" in body or "–" in body:
        violations.append(
            "TYPOGRAPHIC DASH: draft uses em/en-dashes (— –); real Matt types "
            "plain ' - ' for asides (43% of emails) and uses — in only 2.2%. "
            "This is a loud AI tell — replace every — / – with ' - '."
        )
    if re.search(r"(?m)^\s*Matt\s*$", body):
        violations.append(
            "SIGN-OFF 'Matt': real Matt signs 'Matthew' (320/742 emails) or "
            "nothing — never bare 'Matt' (0/742)."
        )
    if re.search(r"^Hi there\b", body, re.I | re.M):
        violations.append(
            "GENERIC GREETING 'Hi there': appears in 0/742 real emails. Use the "
            "recipient's name, 'Hi team,' for a group inbox, or no greeting."
        )
    return violations


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Voice structural priors")
    ap.add_argument("--recompute", action="store_true", help="force recompute priors cache")
    ap.add_argument("--show", action="store_true", help="print priors block")
    ap.add_argument("--exemplars", help="show task exemplars for this task string")
    ap.add_argument("--check", type=Path, help="run structural_check on a draft file")
    ap.add_argument("--rfq", action="store_true",
                    help="check against the first-contact vendor RFQ (Threadbird template) envelope")
    args = ap.parse_args()
    priors = compute_structural_priors(force=args.recompute)
    if args.show or args.recompute:
        print(json.dumps({k: v for k, v in priors.items() if k != "computed_at"}, indent=2))
    if args.exemplars:
        print(load_task_exemplars(args.exemplars))
    if args.check:
        v = structural_check(args.check.read_text(), priors, is_rfq=args.rfq)
        print("\n".join(v) if v else "PASS — draft inside structural distribution")
