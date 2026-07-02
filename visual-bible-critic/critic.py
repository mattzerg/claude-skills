#!/usr/bin/env python3
"""
visual-bible-critic — score a generated frame (or i2v clip's keyframe) against the
Omphalos visual bible and PASS/FAIL it before it may enter a reel. The guardrail
that stops a soft / non-cyberpunk / off-style frame from shipping.

Two backends:
  * AUTO  — if ANTHROPIC_API_KEY is set, calls Claude vision directly (headless/cron).
  * AGENT — if no key (e.g. inside Claude Code), prints the assembled scoring prompt
            + the frame path so the harness can dispatch a vision subagent that
            returns the same JSON schema. (See SKILL.md.)

9 axes (1-10): futurism, palette_fit, scale_grammar, density_detail, motion_smoothness,
text_absence, materiality, composition, relevance.
PASS = every axis >= --floor (default 7) AND no hard_fail.
Hard fails: garbled_generated_text, present_day, sparse_empty, soft_lowres, morph_wobble,
fantasy_painterly.

CLI:
  critic.py score FRAME.png --bible omphalos-visual-bible-v1.md \
     --title "The Census" --location "Crown/Ministry" --vo-beat "the spire counts the city" \
     --model flux-pro [--floor 7] [--json-out report.json]
  critic.py prompt FRAME.png --bible ... --title ... --location ... --vo-beat ...   # just print the agent prompt
"""
from __future__ import annotations

import argparse, base64, json, os, sys
from pathlib import Path

AXES = ["photorealism", "megastructure_scale", "futurism", "palette_fit", "scale_grammar",
        "density_detail", "motion_smoothness", "text_absence", "materiality", "composition", "relevance"]
HARD_FAILS = ["stylized_illustration_gameart", "scale_too_small", "garbled_generated_text",
              "present_day", "sparse_empty", "soft_lowres", "morph_wobble", "fantasy_painterly"]

SCHEMA_HINT = {
    "scores": {a: 0 for a in AXES},
    "hard_fails": [],
    "reasoning": {a: "" for a in AXES},
    "fixes": [],
    "reroll_params": {"seed": None, "extra_negative": "", "notes": ""},
}


def build_prompt(bible_md: str, ctx: dict, floor: int) -> str:
    return f"""You are the OMPHALOS visual-standards critic. Score the attached generated frame
STRICTLY against the visual bible below. Be harsh — this gate exists because the agent kept SELF-APPROVING
sub-standard frames (soft / muted / stylized / small-scale) that regressed below the bar and shipped twice.
Default to FAIL when unsure. THE BAR IS: PHOTOREALISTIC (a real photograph / live-action cinema still à la
Blade Runner 2049 — NOT stylized, illustration, concept-art, digital-painting, anime, or video-game render)
+ planet-city MEGASTRUCTURE scale (immense, vertical, kilometers-deep; humans are ants) + dense fine detail.
If reference EXEMPLAR images are also attached, compare DIRECTLY — the frame must MATCH OR BEAT them or it FAILs.

=== VISUAL BIBLE (the law) ===
{bible_md}
=== END BIBLE ===

Reel context: title={ctx.get('title')!r}; location={ctx.get('location')!r} (use its tonal dial);
VO beat={ctx.get('vo_beat')!r}; source_model={ctx.get('model')!r}.

Score each of these 9 axes 1-10 (10=matches the exemplars/bar, 1=violates):
{", ".join(AXES)}.
Flag any of these HARD FAILS that apply (any one => FAIL regardless of scores):
- stylized_illustration_gameart: reads as illustration / concept-art / digital-painting / anime /
  video-game render / over-saturated neon-poster instead of a real photograph or live-action film still.
- scale_too_small: reads as a normal/present-day metropolis, not an immense vertical kilometers-deep planet-city.
- garbled_generated_text: any FLUX-generated readable Latin words or gibberish lettering/signage
  (in-world text must be composited Concord glyphs in post, never generated).
- present_day: the frame could pass as present-day Earth (fails the far-future test).
- sparse_empty: minimal/empty/clean — >40% dead space, lacks density.
- soft_lowres: soft focus, low detail, washed-out, not sharp.
- morph_wobble: (i2v only) morphing/wobbling/warping motion.
- fantasy_painterly: fantasy/baroque/gold-filigree/painterly/illustration/serif.

PASS only if EVERY axis >= {floor} AND no hard_fails. Output STRICT JSON only, this shape:
{json.dumps(SCHEMA_HINT)}
For fixes/reroll_params, give concrete advice (stronger negatives, re-seed, composite text in post, etc.)."""


def decide(result: dict, floor: int) -> dict:
    scores = result.get("scores", {})
    hard = result.get("hard_fails", []) or []
    low = [a for a in AXES if int(scores.get(a, 0) or 0) < floor]
    passed = not hard and not low
    return {
        "verdict": "PASS" if passed else "FAIL",
        "below_floor": low,
        "hard_fails": hard,
        "min_axis": min((int(scores.get(a, 0) or 0) for a in AXES), default=0),
        "scores": scores,
        "reasoning": result.get("reasoning", {}),
        "fixes": result.get("fixes", []),
        "reroll_params": result.get("reroll_params", {}),
    }


def _b64(p: Path) -> tuple[str, str]:
    suf = p.suffix.lower()
    media = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}.get(suf, "image/png")
    return media, base64.standard_b64encode(p.read_bytes()).decode()


def score_via_api(frame: Path, prompt: str, model: str) -> dict:
    import anthropic
    client = anthropic.Anthropic()
    media, data = _b64(frame)
    msg = client.messages.create(
        model=model, max_tokens=1500,
        messages=[{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media, "data": data}},
            {"type": "text", "text": prompt},
        ]}],
    )
    txt = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    txt = txt[txt.find("{"): txt.rfind("}") + 1]
    return json.loads(txt)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("score", "prompt"):
        p = sub.add_parser(name)
        p.add_argument("frame")
        p.add_argument("--bible", default="/Users/mattheweisner/Obsidian/Zerg/MattZerg/Projects/Zerg-Production/scifi-reels/omphalos-visual-bible-v1.md")
        p.add_argument("--title", default="")
        p.add_argument("--location", default="")
        p.add_argument("--vo-beat", default="")
        p.add_argument("--model", default="flux-pro")
        p.add_argument("--floor", type=int, default=7)
        p.add_argument("--vision-model", default="claude-sonnet-5")
        p.add_argument("--json-out")
    args = ap.parse_args()

    frame = Path(args.frame).expanduser()
    if not frame.exists():
        print(f"ERROR: frame not found: {frame}", file=sys.stderr); return 2
    bible = Path(args.bible).expanduser().read_text()
    ctx = {"title": args.title, "location": args.location, "vo_beat": args.vo_beat, "model": args.model}
    prompt = build_prompt(bible, ctx, args.floor)

    if args.cmd == "prompt":
        print(prompt); return 0

    if not (os.environ.get("ANTHROPIC_API_KEY")):
        # AGENT mode: no key. Emit instructions for the harness to score via a vision subagent.
        print(json.dumps({
            "backend": "agent",
            "note": "No ANTHROPIC_API_KEY. Dispatch a vision subagent with this frame + prompt; have it return the JSON schema; then re-run `critic.py` logic on that JSON (or just apply PASS/FAIL: every axis>=floor and no hard_fails).",
            "frame": str(frame), "floor": args.floor, "schema": SCHEMA_HINT,
            "prompt_preview": prompt[:400] + "…",
        }, indent=2))
        return 3

    result = score_via_api(frame, prompt, args.vision_model)
    verdict = decide(result, args.floor)
    out = {"frame": str(frame), "context": ctx, **verdict}
    print(json.dumps(out, indent=2))
    if args.json_out:
        Path(args.json_out).expanduser().write_text(json.dumps(out, indent=2))
    return 0 if verdict["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
