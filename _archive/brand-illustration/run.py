#!/usr/bin/env python3
"""brand-illustration — brand-aware illustration prompt builder + generator.

Wraps the existing chatgpt-image-skill / nano-banana-pro / fal-image-skill with brand-context
injection. Loads brand presets from brands.json, assembles a prompt that includes palette,
typography, voice-tells, and anti-patterns, then dispatches to the chosen image-gen backend.

Usage:
  # Just print the assembled prompt (no API call) — for review before spending tokens:
  python3 run.py prompt --brand matteisn --intent "hero illustration of a sailboat vang rope" --aspect 16:9

  # Generate via chatgpt-image-skill (default backend):
  python3 run.py generate --brand matteisn --intent "hero illustration of a sailboat vang rope" \\
                          --output ~/matteisn-site/assets/illustrations/hero.png --aspect 16:9

  # List available brands:
  python3 run.py list

Brand presets live in ./brands.json. Edit there to refine voice / palette / anti-patterns.
"""
from __future__ import annotations
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent
BRANDS_PATH = SKILL_DIR / "brands.json"

ASPECT_TO_SIZE = {
    "1:1": "1024x1024",
    "square": "1024x1024",
    "portrait": "1024x1536",
    "9:16": "1024x1536",
    "16:9": "1536x1024",
    "landscape": "1536x1024",
    "hero": "1536x1024",
    "og": "1536x1024",
}


def load_brands():
    return json.loads(BRANDS_PATH.read_text())


def build_prompt(brand_key: str, intent: str, brands: dict | None = None) -> str:
    if brands is None:
        brands = load_brands()
    if brand_key not in brands:
        raise SystemExit(f"unknown brand '{brand_key}'. Available: {', '.join(brands.keys())}")
    b = brands[brand_key]
    pal = b["palette"]
    typo = b["typography"]
    voice = b.get("voice_tells", [])
    anti = b.get("anti_patterns", [])
    style = b.get("style_guidance", "")

    palette_line = (
        f"primary {pal.get('primary')} ({pal.get('primary_name','')}), "
        f"accent {pal.get('accent')} ({pal.get('accent_name','')})"
    )
    if pal.get("secondary"):
        palette_line += f", secondary {pal.get('secondary')} ({pal.get('secondary_name','')})"
    if pal.get("paper"):
        palette_line += f", on {pal.get('paper_name','paper')} {pal.get('paper')}"

    typo_line = f"headline type evokes {typo.get('headline')}; body {typo.get('body')}"

    parts = [
        f"Brand: {b['site']} ({b['register']}).",
        f"Subject / intent: {intent}.",
        f"Palette: {palette_line}.",
        f"Typography reference: {typo_line}.",
    ]
    if voice:
        parts.append("Voice / context: " + "; ".join(voice) + ".")
    if style:
        parts.append("Style guidance: " + style)
    if anti:
        parts.append("AVOID: " + "; ".join(anti) + ".")
    parts.append(
        "Render as a clean, brand-coherent illustration. No text/captions in the image unless specifically requested. "
        "Composition should leave room at top-left or bottom-right for overlay text if used as a hero. "
        "Vector-clean lines, restrained palette, no over-rendering."
    )
    return " ".join(parts)


def cmd_list(args):
    brands = load_brands()
    print(f"# brand-illustration: {len(brands)} brand presets\n")
    for k, v in brands.items():
        print(f"  {k:18s}  {v['site']}  ·  {v['register']}")


def cmd_prompt(args):
    p = build_prompt(args.brand, args.intent)
    print(p)


def cmd_generate(args):
    brands = load_brands()
    if args.brand not in brands:
        raise SystemExit(f"unknown brand '{args.brand}'. Available: {', '.join(brands.keys())}")
    b = brands[args.brand]
    prompt = build_prompt(args.brand, args.intent, brands)

    # Resolve output path — use brand asset_path as default
    if args.output:
        output = os.path.expanduser(args.output)
    else:
        asset_dir = os.path.expanduser(b["asset_path"])
        os.makedirs(asset_dir, exist_ok=True)
        slug = "".join(c if c.isalnum() else "-" for c in args.intent.lower())[:60].strip("-")
        output = os.path.join(asset_dir, f"{slug or 'illustration'}.png")

    size = ASPECT_TO_SIZE.get(args.aspect, args.aspect if "x" in args.aspect else "1536x1024")

    print(f"# brand-illustration: brand={args.brand} backend={args.backend} size={size}")
    print(f"# output: {output}")
    print(f"# prompt: {prompt[:200]}...")
    print()

    if args.dry_run:
        print(f"[dry-run] would invoke {args.backend} — full prompt:\n\n{prompt}\n")
        return

    if args.backend == "chatgpt":
        cmd = [
            "python3", os.path.expanduser("~/.claude/skills/chatgpt-image-skill/generate_image.py"),
            prompt,
            "--size", size,
            "--quality", args.quality,
            "--output", output,
            "--no-brand-prefix",   # we've built our own brand-aware prompt
        ]
    elif args.backend == "nano-banana":
        # nano-banana takes a DIRECTORY for --output (not a file). Pass the parent dir,
        # then let nano-banana write into it; we'll move the result to our intended path.
        out_dir = os.path.dirname(output) or "."
        cmd = [
            "python3", os.path.expanduser("~/.claude/skills/nano-banana-pro/generate_image.py"),
            prompt,
            "--aspect", args.aspect if ":" in args.aspect else "16:9",
            "--output", out_dir,
            "--resolution", "2K",
        ]
    elif args.backend == "fal":
        cmd = [
            "python3", os.path.expanduser("~/.claude/skills/fal-image-skill/fal_image_skill.py"),
            "gen", prompt,
            "--output", output,
        ]
    else:
        raise SystemExit(f"unknown backend: {args.backend}")

    print(f"# invoking: {' '.join(cmd[:3])} ...")
    result = subprocess.run(cmd, capture_output=True, text=True)
    sys.stdout.write(result.stdout)
    sys.stderr.write(result.stderr)
    if result.returncode != 0:
        raise SystemExit(f"image-gen backend failed (exit {result.returncode})")
    if os.path.exists(output):
        print(f"\n✅ wrote {output} ({os.path.getsize(output)} bytes)")
    else:
        print(f"\n⚠️  backend reported success but {output} not found")
        return

    # Auto-run graphic-layout review unless --skip-review
    if getattr(args, "skip_review", False):
        return
    target_kind = getattr(args, "target_kind", None) or _aspect_to_target_kind(size)
    review_cmd = [
        "python3", os.path.expanduser("~/.claude/skills/graphic-layout/run.py"),
        "review", output,
        "--target-kind", target_kind,
    ]
    print(f"\n# graphic-layout review ({target_kind})...")
    rresult = subprocess.run(review_cmd, capture_output=True, text=True)
    if rresult.returncode == 0:
        review_path = rresult.stdout.strip().splitlines()[-1] if rresult.stdout.strip() else "(no path)"
        print(f"✅ review → {review_path}")
    else:
        print(f"⚠️  graphic-layout review failed: {rresult.stderr[:200]}")


def _aspect_to_target_kind(size: str) -> str:
    """Map size string to graphic-layout's expected target_kind."""
    if size in ("1536x1024",) or size.startswith("16"):
        return "hero"
    if size in ("1024x1024",):
        return "hero"  # graphic-layout has limited target kinds; default
    if size in ("1024x1536",) or size.startswith("9:"):
        return "hero"
    return "hero"


def main():
    p = argparse.ArgumentParser(description="brand-aware illustration prompt builder + generator")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="List available brand presets")

    pp = sub.add_parser("prompt", help="Print the assembled brand-aware prompt without generating")
    pp.add_argument("--brand", required=True)
    pp.add_argument("--intent", required=True, help="What the illustration depicts")

    pg = sub.add_parser("generate", help="Generate an illustration via chosen backend")
    pg.add_argument("--brand", required=True)
    pg.add_argument("--intent", required=True)
    pg.add_argument("--output", help="Output path (default: brand asset_path + slugified intent)")
    pg.add_argument("--aspect", default="16:9",
                    choices=list(ASPECT_TO_SIZE.keys()) + ["custom"],
                    help="Aspect ratio (16:9 default for hero, 1:1 for square, 9:16 for portrait)")
    pg.add_argument("--backend", default="chatgpt", choices=["chatgpt", "nano-banana", "fal"])
    pg.add_argument("--quality", default="high", choices=["low", "medium", "high", "auto"])
    pg.add_argument("--dry-run", action="store_true", help="Print full prompt + cmd, don't invoke backend")
    pg.add_argument("--skip-review", action="store_true", help="Skip auto graphic-layout review post-gen")
    pg.add_argument("--target-kind", help="graphic-layout target_kind (default: hero); see graphic-layout for full list")

    args = p.parse_args()
    if args.cmd == "list":
        cmd_list(args)
    elif args.cmd == "prompt":
        cmd_prompt(args)
    elif args.cmd == "generate":
        cmd_generate(args)


if __name__ == "__main__":
    main()
