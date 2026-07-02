#!/usr/bin/env python3
"""
prompt_grammar — expand an ambient future-cities brief into N concrete,
visually-coherent text-to-video prompts.

The coherence levers (per research): ONE locked style suffix on every clip,
ONE shared negative prompt, one subject + one camera move + one time-of-day
per clip, and a single time-of-day arc across the reel. The unified color
grade is applied later in assembly — this module only governs generation.

CLI:
    prompt_grammar.py expand --brief briefs/future-cities.yaml
    prompt_grammar.py shots            # list shot template keys
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# ── Locked style suffix: appended verbatim to EVERY shot prompt ──
STYLE_SUFFIX = (
    "Cinematic establishing shot, photorealistic, grounded near-future science "
    "fiction, anamorphic lens, shallow depth of field, volumetric haze, soft "
    "bloom on lights, gentle film grain, ARRI Alexa look, teal-and-amber color "
    "grade, one slow continuous camera move, no text, no logos, no people in "
    "foreground."
)

# ── Shared negative prompt ──
NEGATIVE_PROMPT = (
    "text, watermark, logo, captions, subtitles, distorted faces, warped "
    "architecture, flickering, morphing geometry, jump cut, fast zoom, dutch "
    "tilt, cartoon, illustration, lowres, oversaturated, glitching vehicles, "
    "extra limbs, deformed wheels"
)

# ── Shot templates: one subject + one camera move each ──
SHOT_TEMPLATES = {
    "aerial_cityscape": (
        "Slow aerial drift over a vast vertical megacity, layered glass towers, "
        "sky-bridges spanning between buildings, ribbons of traffic light far "
        "below, low clouds drifting between spires"
    ),
    "drone_street": (
        "Low smooth drone glide down a clean future avenue, autonomous pods "
        "passing, holographic storefront glow reflecting on wet pavement, trees "
        "and planters lining the median"
    ),
    "maglev_pass": (
        "Sleek white maglev train sweeping along an elevated curved guideway "
        "above the city, soft sun flare, camera tracking parallel at matched "
        "speed"
    ),
    "bullet_train": (
        "Bullet train threading between arcology towers, camera slowly pulls "
        "back from the nose cone to reveal the skyline, reflections rippling "
        "across the hull"
    ),
    "evtol_approach": (
        "Electric tilt-rotor air-taxi descending toward a rooftop skyport, "
        "landing pads lit in soft amber, distant skyline behind, slow approach, "
        "rotor haze"
    ),
    "autonomous_intersection": (
        "Overhead slow push-in on a driverless intersection, self-driving cars "
        "flowing in silent choreographed lanes, lit crosswalks, no traffic "
        "lights, light rain on the road"
    ),
    "drone_swarm": (
        "Formation of delivery drones rising past a green vertical-farm tower, "
        "mist in the lower city, sun breaking over the skyline, slow upward tilt"
    ),
    "promenade": (
        "Slow dolly along a tree-lined elevated promenade, transparent transit "
        "tubes overhead, soft pedestrian ambience at a distance, warm low sun "
        "between towers, lens flare"
    ),
}

# Time-of-day modifiers keep ONE arc across the reel for coherence.
TIME_OF_DAY = {
    "blue_hour": "at blue hour, deep blue sky, city lights just coming on",
    "golden_hour": "at golden hour, warm low sun, long soft shadows",
    "night_neon": "at night, neon glow, wet reflective streets, deep shadows",
    "dawn_mist": "at dawn, pale gold light, low mist in the streets",
    "dusk": "at dusk, magenta-to-indigo sky, glowing windows",
}


def build_prompt(shot_key: str, tod_key: str) -> str:
    base = SHOT_TEMPLATES[shot_key]
    tod = TIME_OF_DAY.get(tod_key, "")
    core = f"{base} {tod}.".strip()
    return f"{core} {STYLE_SUFFIX}"


def expand(brief: dict) -> list[dict]:
    """Turn a brief dict into a list of clip-generation specs.

    brief keys used:
      shots: ordered list of shot template keys (rotate for variety)
      time_of_day: one key from TIME_OF_DAY (held constant for coherence)
      n_clips: total clips to generate (rotates through `shots`)
      duration_s: per-clip generation duration (default 5)
      aspect_ratio: e.g. "9:16"
      model_default / model_hero: model tiers
      hero_indices: clip indices (0-based) to upgrade to model_hero
    """
    shots = brief.get("shots") or list(SHOT_TEMPLATES.keys())
    tod = brief.get("time_of_day", "blue_hour")
    n = int(brief.get("n_clips", len(shots)))
    dur = int(brief.get("duration_s", 5))
    aspect = brief.get("aspect_ratio", "9:16")
    model_default = brief.get("model_default", "luma")
    model_hero = brief.get("model_hero", "kling")
    hero_idx = set(brief.get("hero_indices", [0]))

    specs = []
    for i in range(n):
        shot_key = shots[i % len(shots)]
        model = model_hero if i in hero_idx else model_default
        specs.append({
            "index": i,
            "label": f"{i:02d}-{shot_key}",
            "shot": shot_key,
            "prompt": build_prompt(shot_key, tod),
            "negative_prompt": NEGATIVE_PROMPT,
            "model": model,
            "duration_s": dur,
            "aspect_ratio": aspect,
        })
    return specs


def _load_brief(path: Path) -> dict:
    text = path.read_text()
    try:
        import yaml  # type: ignore
        return yaml.safe_load(text)
    except Exception:
        # Minimal fallback parser for flat "key: value" + simple lists so the
        # skill runs without PyYAML installed.
        return _mini_yaml(text)


def _mini_yaml(text: str) -> dict:
    data: dict = {}
    cur_list_key = None
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if line.lstrip().startswith("- ") and cur_list_key:
            data.setdefault(cur_list_key, []).append(_coerce(line.lstrip()[2:].strip()))
            continue
        if ":" in line and not line.startswith(" "):
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            if val == "":
                cur_list_key = key
                data.setdefault(key, [])
            else:
                cur_list_key = None
                data[key] = _coerce(val)
    return data


def _coerce(v: str):
    v = v.strip().strip('"').strip("'")
    if v.lower() in ("true", "false"):
        return v.lower() == "true"
    try:
        if "." in v:
            return float(v)
        return int(v)
    except ValueError:
        # bracketed inline list e.g. [0, 4]
        if v.startswith("[") and v.endswith("]"):
            inner = v[1:-1].strip()
            if not inner:
                return []
            return [_coerce(x) for x in inner.split(",")]
        return v


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    pe = sub.add_parser("expand", help="expand a brief into prompts")
    pe.add_argument("--brief", required=True)
    sub.add_parser("shots", help="list shot template keys")
    args = ap.parse_args()

    if args.cmd == "shots":
        for k in SHOT_TEMPLATES:
            print(k)
        return 0
    if args.cmd == "expand":
        brief = _load_brief(Path(args.brief).expanduser())
        specs = expand(brief)
        print(json.dumps(specs, indent=2))
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
