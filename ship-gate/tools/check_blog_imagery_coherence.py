#!/usr/bin/env python3
"""ship-gate blog imagery SVG-coherence check (B2).

Implements memory/feedback_blog_imagery_coherence.md:

    Hero + LinkedIn + X share images must speak the same visual language as
    the body diagrams. If the body has coded SVG diagrams (technical post,
    Tier 1 register), then hero/LI/X must also be SVG-coded - not AI-PNG
    decorative imagery. Mixing produces "two different brands stapled
    together" (Idan, 2026-05-04, agents-that-remember post).

Decision rule:
    1. Scan blog markdown body for inline <svg> tags OR ![]( ... .svg) image
       references. If none, post is Tier 2 (narrative) - check is N/A.
    2. If body has SVG content, check that the corresponding hero / linkedin /
       twitter assets exist as .svg files (or .png that was rendered FROM an
       .svg of the same name living next to the .png).
    3. Block (red) if any of (hero, linkedin, twitter) is a Tier-2 AI-PNG.

Usage:
    python3 check_blog_imagery_coherence.py <blog-md-path>

Exit codes: 0 green, 1 yellow, 2 red, 64 usage error.
"""
import re
import sys
from pathlib import Path

# Default Zerg image directory (per memory/project_blog_imagery_skill.md)
DEFAULT_IMG_DIR = Path.home() / "zerg/web/src/public/images/blog"


def find_body_svg(md_text: str) -> list[str]:
    """Return a list of SVG signals found in the body."""
    signals: list[str] = []
    if re.search(r"<svg\b", md_text, re.IGNORECASE):
        signals.append("inline <svg>")
    for match in re.finditer(r"!\[[^\]]*\]\(([^)]+\.svg)\)", md_text, re.IGNORECASE):
        signals.append(f"image ref {match.group(1)}")
    for match in re.finditer(r"!\[[^\]]*\]\(([^)]+/blog/[^)]+\.png)\)", md_text, re.IGNORECASE):
        path = match.group(1)
        if "body-" in path or "diagram" in path:
            sibling = Path(path).with_suffix(".svg").name
            sibling_path = DEFAULT_IMG_DIR / sibling
            if sibling_path.exists():
                signals.append(f"PNG with .svg sibling: {sibling}")
    return signals


def asset_is_svg_coded(slug: str, suffix: str, img_dir: Path) -> tuple[bool, str]:
    """Check if `<slug>-<suffix>` exists as svg, or as png with svg sibling.
    Returns (is_svg_coded, evidence-string).
    """
    svg_path = img_dir / f"{slug}-{suffix}.svg"
    if svg_path.exists():
        return True, f"{svg_path.name} (svg)"
    png_path = img_dir / f"{slug}-{suffix}.png"
    if not png_path.exists():
        return False, f"{slug}-{suffix} not found in {img_dir}"
    sibling_svg = png_path.with_suffix(".svg")
    if sibling_svg.exists():
        return True, f"{png_path.name} (rendered from sibling {sibling_svg.name})"
    return False, f"{png_path.name} (AI-PNG, no svg sibling)"


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: check_blog_imagery_coherence.py <blog-md-path>", file=sys.stderr)
        return 64
    md_path = Path(sys.argv[1]).expanduser().resolve()
    if not md_path.exists():
        print(f"file not found: {md_path}", file=sys.stderr)
        return 64
    slug = md_path.stem
    md_text = md_path.read_text()

    body_signals = find_body_svg(md_text)
    if not body_signals:
        print("# blog-imagery coherence — N/A")
        print()
        print(f"**Post**: `{slug}`")
        print("No body SVG content detected — this is a Tier 2 (narrative) post.")
        print("AI imagery hero/LI/X is fine here. No coherence rule fires.")
        return 0

    img_dir = DEFAULT_IMG_DIR
    if not img_dir.exists():
        print("# blog-imagery coherence — ERROR")
        print()
        print(f"image dir missing: {img_dir}")
        return 2

    targets = [("hero", "hero"), ("LinkedIn", "linkedin"), ("X / Twitter", "twitter")]
    findings: list[tuple[str, bool, str]] = []
    for label, suffix in targets:
        ok, evidence = asset_is_svg_coded(slug, suffix, img_dir)
        findings.append((label, ok, evidence))

    all_ok = all(f[1] for f in findings)
    status = "GREEN" if all_ok else "RED"
    exit_code = 0 if all_ok else 2

    print(f"# blog-imagery coherence — {status}")
    print()
    print(f"**Post**: `{slug}`")
    print(f"**Body SVG signals**: {', '.join(body_signals[:4])}")
    print()
    print("| Channel | Coherent | Evidence |")
    print("|---|---|---|")
    for label, ok, evidence in findings:
        mark = "✓" if ok else "✗"
        print(f"| {label} | {mark} | {evidence} |")
    if not all_ok:
        print()
        print("**Block reason**: body uses coded SVGs but at least one of (hero/LI/X) is an AI-PNG.")
        print("Per memory/feedback_blog_imagery_coherence.md the post must pick ONE register per campaign.")
        print("Either render the missing channels as SVG (see blog-imagery skill Tier 1 templates),")
        print("or convert the body diagrams to PNG so the post is consistently Tier 2.")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
