"""Load voice + principles corpora into critique-ready prompt blocks."""

from __future__ import annotations

import json
from pathlib import Path

CORPUS_ROOT = Path.home() / ".claude" / "feedback-corpus"
VOICE_FINGERPRINT = CORPUS_ROOT / "voice" / "fingerprint.md"
VOICE_QUOTES = CORPUS_ROOT / "voice" / "quotes.json"
VOICE_CATEGORIES = CORPUS_ROOT / "voice" / "categories.json"
PRINCIPLES_LIBRARY = CORPUS_ROOT / "principles" / "library.md"
PRINCIPLES_CITATIONS = CORPUS_ROOT / "principles" / "citations.json"

# Auto-mined feedback voice patterns (from mine_feedback_patterns.py — pulled
# from Matt's actual outgoing email history). Higher signal than the
# fingerprint because it's grounded in real feedback he gave, not curated.
import sys
sys.path.insert(0, str(Path.home() / ".config" / "zerg" / "lib"))
from vault_path import style_dir  # canonical vault resolver (was hardcoded iCloud — now a near-empty shell)
FEEDBACK_PATTERNS = style_dir() / "feedback_voice_patterns.md"


def _load_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_voice_block(top_n: int = 25) -> str:
    """System-prompt block: Matt's voice fingerprint + top-N quotes + auto-
    mined feedback patterns from his real outgoing email."""
    fingerprint = _load_text(VOICE_FINGERPRINT)
    if not fingerprint:
        return "_(no voice corpus — run feedback-corpus/build_corpus.py --voice-only)_\n"
    quotes_block = ""
    if VOICE_QUOTES.exists():
        try:
            quotes = json.loads(VOICE_QUOTES.read_text(encoding="utf-8"))
            top = quotes[:top_n]
            quotes_block = "\n## Quote bank (cite with voice_provenance)\n\n"
            for q in top:
                quotes_block += f"- `{q['id']}` (w={q['weight']}, tags={','.join(q.get('tags', []))}): {q['text'][:280]}\n"
        except Exception:
            pass
    patterns_block = ""
    fp = _load_text(FEEDBACK_PATTERNS)
    if fp.strip():
        # Drop YAML frontmatter so the block is clean
        import re as _re
        fp_body = _re.sub(r"^---\n.*?\n---\n", "", fp, count=1, flags=_re.S)
        patterns_block = (
            "\n## Auto-mined feedback voice patterns (use these structural moves + voice tells)\n\n"
            + fp_body.strip() + "\n"
        )
    return fingerprint + "\n" + quotes_block + patterns_block


def load_principles_block(per_domain: int = 8) -> str:
    """System-prompt block: principles library, capped per domain to keep cache hot."""
    if not PRINCIPLES_CITATIONS.exists():
        return "_(no principles corpus — run feedback-corpus/build_corpus.py --principles-only)_\n"
    try:
        principles = json.loads(PRINCIPLES_CITATIONS.read_text(encoding="utf-8"))
    except Exception:
        return _load_text(PRINCIPLES_LIBRARY) or "_(principles parse failure)_\n"

    by_domain: dict[str, list[dict]] = {}
    for p in principles:
        by_domain.setdefault(p["domain"], []).append(p)

    out = ["# Principles Library", "", "Cite at least one of these in `principle_provenance`. Each principle has an ID like `p-NNNN`.", ""]
    for domain in sorted(by_domain.keys()):
        out.append(f"## {domain}")
        # take top by weight to keep within cache budget
        items = sorted(by_domain[domain], key=lambda p: p.get("weight", 1.0), reverse=True)[:per_domain]
        for p in items:
            tags = ",".join(p.get("tags", []))
            out.append(f"- `{p['principle_id']}` **{p['rule']}** — {p['rationale']} _({p['citation']}, tags={tags})_")
        out.append("")
    return "\n".join(out)
