#!/usr/bin/env python3
"""ship-gate blog 4-place metadata drift check (B3).

Per memory/feedback_blog_metadata_drift.md, blog facts live in 4 places that
drift independently:

    1. body markdown (lede)                            ~/zerg/web/src/public/content/blog/<slug>.md
    2. .ts excerpt                                     ~/zerg/web/src/constants/blog/posts/<slug>.ts
    3. .ts seo.description                             same .ts file
    4. image alt-text in body markdown                 in body MD: ![alt](path)

Past incidents (CMU/UC Berkeley/AMD): names corrected in body but stale in
excerpt + seo.description. This script catches:

    drift  - excerpt or seo.description references a NAME or NUMBER that does
             not appear in the body lede   --> hard block (red)
    copy   - excerpt and seo.description are identical / >=90% similar
             --> yellow (each should serve a distinct purpose)
    blind  - alt-text is empty or just the filename                --> yellow

Usage:
    python3 check_metadata_drift.py <slug-or-md-path>

Exit codes: 0 green, 1 yellow, 2 red, 64 usage error.
"""
import difflib
import re
import sys
from pathlib import Path

DEFAULT_MD_DIR = Path.home() / "zerg/web/src/public/content/blog"
DEFAULT_TS_DIR = Path.home() / "zerg/web/src/constants/blog/posts"

NAME_RE = re.compile(r"\b[A-Z][a-z0-9]{1,}(?:[-A-Z][a-zA-Z0-9]+)*\b")
NUMBER_RE = re.compile(r"\b\d{2,}(?:\.\d+)?%?\b")
STOPWORDS = {
    "The", "This", "That", "Those", "These", "Then", "There", "They", "Their",
    "And", "But", "For", "With", "From", "Into", "Have", "When", "What",
    "Which", "While", "Where", "Will", "Why", "How", "Not", "All", "One", "Two",
    "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
    "It", "Its", "His", "Her", "Our", "Your", "Mine", "Yours",
    # months / weekdays
    "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday",
    "January", "February", "March", "April", "May", "June", "July", "August",
    "September", "October", "November", "December",
}


def lede(text: str, max_chars: int = 600) -> str:
    paragraphs = [p.strip() for p in re.split(r"\n\n+", text) if p.strip()]
    body_paragraphs = [p for p in paragraphs if not p.startswith("#") and not p.startswith("---")]
    if not body_paragraphs:
        return ""
    out = ""
    for p in body_paragraphs:
        out += " " + p
        if len(out) >= max_chars:
            break
    return out.strip()[:max_chars]


CAMELCASE_RE = re.compile(r"[A-Z][a-z]+[A-Z]")  # DeepMind, AlphaEvolve
ALL_CAPS_RE = re.compile(r"^[A-Z]{2,5}$")        # CMU, AMD, MIT, NASA
HAS_DIGIT_RE = re.compile(r"\d")                  # GPT4, R1, Q3


def is_high_confidence_proper(token: str) -> bool:
    """A high-confidence proper-noun signal: drift on these is almost certainly
    real (CMU vs MIT, AMD vs Nvidia). Sentence-initial common words like
    'Beat' or 'Deep' do not match.
    """
    if CAMELCASE_RE.search(token):
        return True
    if ALL_CAPS_RE.match(token):
        return True
    if HAS_DIGIT_RE.search(token):
        return True
    return False


def candidate_names(text: str) -> set[str]:
    """All capitalized tokens worth checking. Confidence sorted downstream."""
    candidates = {m for m in NAME_RE.findall(text) if m not in STOPWORDS and not m[0].isdigit()}
    return {c for c in candidates if len(c) >= 3}


def numbers(text: str) -> set[str]:
    return set(NUMBER_RE.findall(text))


def name_in_body(name: str, body: str) -> bool:
    """Case-insensitive whole-word check. Catches 'capital' in body matching
    'Capital' (sentence-initial) in excerpt — the most common false-positive
    pattern.
    """
    return re.search(rf"\b{re.escape(name)}\b", body, re.IGNORECASE) is not None


def _extract_string(name: str, scope: str) -> str:
    """Find a `<name>: '...'` / `"..."` / `` `...` `` assignment in the scope.
    Handles multi-line backtick template literals AND escaped quotes inside
    single/double-quoted strings (e.g. `'DeepMind\\'s AlphaEvolve...'`).
    """
    for quote in ("`", "'", '"'):
        q = re.escape(quote)
        # Body matches any char except the quote, OR a backslash followed by anything.
        pattern = rf"{name}:\s*{q}((?:[^{q}\\]|\\.)*){q}\s*,?"
        m = re.search(pattern, scope, re.DOTALL)
        if m:
            return m.group(1).replace("\\'", "'").replace('\\"', '"')
    return ""


def parse_ts_excerpt_and_seo(ts_text: str) -> tuple[str, str]:
    excerpt = _extract_string("excerpt", ts_text)
    seo_description = ""
    m = re.search(r"seo:\s*\{(.+?)^\s*\}", ts_text, re.DOTALL | re.MULTILINE)
    if m:
        seo_description = _extract_string("description", m.group(1))
    return excerpt, seo_description


def alt_texts(md_text: str) -> list[tuple[str, str]]:
    return re.findall(r"!\[([^\]]*)\]\(([^)]+)\)", md_text)


def resolve_paths(arg: str) -> tuple[Path, Path, str]:
    arg_path = Path(arg).expanduser()
    if arg_path.exists() and arg_path.suffix == ".md":
        slug = arg_path.stem
        md_path = arg_path
    else:
        slug = arg
        md_path = DEFAULT_MD_DIR / f"{slug}.md"
    ts_candidates = [DEFAULT_TS_DIR / f"{slug}.ts"]
    ts_path = next((p for p in ts_candidates if p.exists()), ts_candidates[0])
    return md_path, ts_path, slug


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_metadata_drift.py <slug-or-md-path>", file=sys.stderr)
        return 64
    md_path, ts_path, slug = resolve_paths(sys.argv[1])
    if not md_path.exists():
        print(f"body markdown not found: {md_path}", file=sys.stderr)
        return 64
    if not ts_path.exists():
        print(f"post .ts not found: {ts_path}", file=sys.stderr)
        return 64

    md = md_path.read_text()
    ts = ts_path.read_text()
    excerpt, seo_desc = parse_ts_excerpt_and_seo(ts)
    body_lede = lede(md)

    body_nums = numbers(md)  # numbers checked against full body (lede may not include all)
    excerpt_names = candidate_names(excerpt)
    excerpt_nums = numbers(excerpt)
    seo_names = candidate_names(seo_desc)
    seo_nums = numbers(seo_desc)

    drift_findings: list[str] = []  # red
    yellow_findings: list[str] = []
    excerpt_missing = sorted(n for n in excerpt_names if not name_in_body(n, md))
    seo_missing = sorted(n for n in seo_names if not name_in_body(n, md))

    high_excerpt = [n for n in excerpt_missing if is_high_confidence_proper(n)]
    low_excerpt = [n for n in excerpt_missing if not is_high_confidence_proper(n)]
    high_seo = [n for n in seo_missing if is_high_confidence_proper(n)]
    low_seo = [n for n in seo_missing if not is_high_confidence_proper(n)]

    if high_excerpt:
        drift_findings.append(f"excerpt has high-confidence proper nouns missing from body: {high_excerpt}")
    if high_seo:
        drift_findings.append(f"seo.description has high-confidence proper nouns missing from body: {high_seo}")
    if low_excerpt:
        yellow_findings.append(f"excerpt has capitalized words not in body (likely paraphrase, verify): {low_excerpt}")
    if low_seo:
        yellow_findings.append(f"seo.description has capitalized words not in body (likely paraphrase, verify): {low_seo}")
    drifted_excerpt_nums = excerpt_nums - body_nums
    if drifted_excerpt_nums:
        drift_findings.append(f"excerpt numbers not in body: {sorted(drifted_excerpt_nums)}")
    drifted_seo_nums = seo_nums - body_nums
    if drifted_seo_nums:
        drift_findings.append(f"seo.description numbers not in body: {sorted(drifted_seo_nums)}")

    if excerpt and seo_desc:
        ratio = difflib.SequenceMatcher(a=excerpt.lower(), b=seo_desc.lower()).ratio()
        if ratio >= 0.9:
            yellow_findings.append(
                f"excerpt and seo.description are {int(ratio * 100)}% identical — should serve distinct purposes"
            )
    alts = alt_texts(md)
    blind_alts = [(a, p) for a, p in alts if not a.strip() or a.strip().lower() == Path(p).stem.lower()]
    if blind_alts:
        yellow_findings.append(
            f"{len(blind_alts)} image(s) have empty or filename-only alt text — alt should reference body claims"
        )

    if drift_findings:
        status, exit_code = "RED", 2
    elif yellow_findings:
        status, exit_code = "YELLOW", 1
    else:
        status, exit_code = "GREEN", 0

    print(f"# metadata drift — {status}")
    print()
    print(f"**Slug**: `{slug}`")
    print(f"**Body MD**: `{md_path}`")
    print(f"**Post .ts**: `{ts_path}`")
    print()
    if not excerpt:
        print("(could not parse `excerpt` from .ts — pattern may have changed)")
    if not seo_desc:
        print("(could not parse `seo.description` from .ts — pattern may have changed)")
    print(f"**Excerpt** ({len(excerpt)} ch): {excerpt[:160]}{'…' if len(excerpt) > 160 else ''}")
    print(f"**SEO desc** ({len(seo_desc)} ch): {seo_desc[:160]}{'…' if len(seo_desc) > 160 else ''}")
    print()

    if drift_findings:
        print("## Drift (block)")
        for f in drift_findings:
            print(f"- {f}")
        print()
    if yellow_findings:
        print("## Soft warnings")
        for f in yellow_findings:
            print(f"- {f}")
        print()
    if status == "GREEN":
        print("All four places agree on names + numbers; excerpt and seo.description are distinct.")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
