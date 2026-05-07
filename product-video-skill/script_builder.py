#!/usr/bin/env python3
"""Build a storyboard JSON from a product video brief.

Reads a brief (a small JSON or interactive prompt) describing the product,
capability, audience, tone, length, and end-card copy, and emits a
storyboard JSON conforming to lib/storyboard_schema.json.

Beat templates and copy patterns come from best-practices.md §7–§8 (the
15s / 30s / 60s structures and the concrete-copy patterns: capability-named,
before/after, X-without-Y, outcome-led).

Usage:
    # Interactive
    python3 script_builder.py --interactive --out /tmp/storyboard.json

    # From brief JSON
    python3 script_builder.py --brief brief.json --out /tmp/storyboard.json

    # Print example brief
    python3 script_builder.py --example-brief

    # Render brief immediately to a Markdown approval doc too
    python3 script_builder.py --brief brief.json --out /tmp/sb.json --md /tmp/brief.md

The output storyboard is the input to the rest of the pipeline (recording,
assembly, checklist). Voice / register defaults: informational, clean, clear,
business/professional. Light dry humor is permitted on the agent reveal beat.
"""
import argparse
import json
import sys
from pathlib import Path


EXAMPLE_BRIEF = {
    "product_name": "Zergboard",
    "capability": "The board your AI agents can use.",
    "audience": "Anyone using AI + a PM tool.",
    "tone": "informational, clean, clear, business/professional; light dry humor permitted on the agent reveal",
    "length_s": 30,
    "channels": ["site-hero", "twitter", "linkedin", "youtube", "blog-embed"],
    "aspects": ["16:9", "1:1"],
    "actions": [
        {"verb": "Create", "object": "a card", "ui_anchor": "Backlog"},
        {"verb": "Move", "object": "a card", "ui_anchor": "Doing → Review"},
        {"verb": "Let your AI agent move it", "object": "", "ui_anchor": "no cursor"}
    ],
    "outcome": "Same board. Same source of truth.",
    "end_card": {
        "brand_mark": "zergboard",
        "headline": "Zergboard.",
        "subtitle": "AI-native PM, across the ZergStack.",
        "cta": "Try it",
        "url": "zergboard.com"
    },
    "title_card": {
        "enabled": True,
        "duration_s": 1.5,
        "headline": "Zergboard.",
        "tagline": "The board your AI agents can use."
    },
    "audio_mode": "silent",
    "music_prompt": "modern indie tech instrumental, soft synth pads, light percussion, 110 BPM, sparse first 3 seconds, builds to gentle peak around the agent reveal, resolves under end card, no piano, no vocals, productivity software demo soundtrack"
}


# Per-length beat budgets (from best-practices.md §2 and §8).
# Each entry: list of (label, fraction_of_body) — body excludes title & end card.
BEAT_TEMPLATES = {
    15: [  # single-mechanic teaser
        ("Hook", 0.20),
        ("Action", 0.55),
        ("Payoff", 0.25),
    ],
    30: [  # dominant length: hook → setup → 3 actions → payoff
        ("Hook", 0.10),
        ("Setup", 0.10),
        ("Action 1", 0.20),
        ("Action 2", 0.20),
        ("Agent Action", 0.25),
        ("Payoff", 0.15),
    ],
    60: [  # feature walkthrough
        ("Hook", 0.05),
        ("Setup", 0.15),
        ("Action 1", 0.18),
        ("Action 2", 0.18),
        ("Action 3", 0.18),
        ("Agent Action", 0.16),
        ("Payoff", 0.10),
    ],
}


def _round_seconds(x):
    return round(x * 10) / 10


def build_storyboard(brief, slug=None, title=None):
    """Construct a storyboard dict from a brief dict.

    Beat copy is generated using concrete patterns. The author should
    review and tighten — this is a *starter*, not the final word.
    """
    length_s = brief["length_s"]
    if length_s not in BEAT_TEMPLATES:
        # Pick the closest template
        length_s_template = min(BEAT_TEMPLATES.keys(), key=lambda k: abs(k - length_s))
    else:
        length_s_template = length_s

    title_card = brief.get("title_card", {})
    title_dur = title_card.get("duration_s", 0) if title_card.get("enabled") else 0
    end_hold = brief.get("end_card", {}).get("hold_s", 6.0)

    body_s = max(8, length_s - title_dur - end_hold)

    # Generate beat objects
    beats = []
    cursor = 0.0

    # Optional title card beat
    if title_dur > 0:
        beats.append({
            "label": "Title card",
            "start_s": _round_seconds(cursor),
            "duration_s": _round_seconds(title_dur),
            "visual": "Branded title card: dark navy backdrop, brand mark + product name + tagline. Subtle accent underline. No app UI yet.",
            "caption": "",
            "action": f"Hold {title_dur}s, hard cut to body.",
            "audio_note": "Music starts sparse — pad-only opening.",
        })
        cursor += title_dur

    # Body beats
    template = BEAT_TEMPLATES[length_s_template]
    capability = brief["capability"]
    actions = brief.get("actions", [])
    outcome = brief.get("outcome", "")
    product_name = brief.get("product_name", "")

    body_beats_meta = []
    for label, frac in template:
        body_beats_meta.append((label, _round_seconds(body_s * frac)))

    # Re-distribute rounding leftover to last body beat so total == body_s
    total_assigned = sum(d for _, d in body_beats_meta)
    if abs(total_assigned - body_s) > 0.05 and body_beats_meta:
        last_label, last_dur = body_beats_meta[-1]
        body_beats_meta[-1] = (last_label, _round_seconds(last_dur + (body_s - total_assigned)))

    action_idx = 0
    for label, dur in body_beats_meta:
        caption, visual, audio_note = _beat_copy(
            label, capability, actions, action_idx, outcome, product_name
        )
        # Track action consumption
        if label.startswith("Action") or label == "Agent Action":
            action_idx += 1

        beats.append({
            "label": label,
            "start_s": _round_seconds(cursor),
            "duration_s": _round_seconds(dur),
            "visual": visual,
            "caption": caption,
            "action": _beat_action(label, actions, action_idx - 1 if (label.startswith("Action") or label == "Agent Action") else None),
            "audio_note": audio_note,
        })
        cursor += dur

    # End card
    ec = brief.get("end_card", {})
    beats.append({
        "label": "End card",
        "start_s": _round_seconds(cursor),
        "duration_s": _round_seconds(end_hold),
        "visual": (
            f"Hard cut to end-card frame: brand mark, headline '{ec.get('headline', '')}', "
            f"subtitle '{ec.get('subtitle', '')}', CTA pill '{ec.get('cta', '')}', URL. "
            f"Held for {end_hold}s."
        ),
        "caption": "",
        "action": f"End card hold {end_hold}s, music tails out.",
        "audio_note": "Music tail fades over last 0.8s.",
    })

    storyboard = {
        "slug": slug or _slugify(brief.get("product_name", "video") + "-launch"),
        "title": title or f"{brief.get('product_name', '')} — Launch Demo",
        "core_message": capability,
        "audience": brief["audience"],
        "channels": brief.get("channels", ["site-hero", "twitter", "linkedin"]),
        "length_s": length_s,
        "tone": brief.get("tone", "informational, clean, clear, business/professional"),
        "aspects": brief.get("aspects", ["16:9", "1:1"]),
        "audio": {
            "mode": brief.get("audio_mode", "silent"),
            "music_prompt": brief.get("music_prompt", ""),
        },
        "beats": beats,
        "end_card": {**ec, "hold_s": end_hold},
    }
    if title_dur > 0:
        storyboard["title_card"] = title_card

    return storyboard


def _beat_copy(label, capability, actions, action_idx, outcome, product_name):
    """Return (caption, visual, audio_note) for a beat. Concrete patterns;
    author should review."""

    if label == "Hook":
        # Pattern: name the capability outright. Use the capability sentence.
        return (
            capability,
            "Cold open on the product UI in its end-state — populated and alive. "
            "Caption fades in within 0.3s. Subtle 1.05x slow zoom for life.",
            "Music starts sparse — pad only, no percussion."
        )

    if label == "Setup":
        return (
            "Real product. Real workflow.",
            "Hold the wide UI shot, slight pan to bring the first action target toward frame center.",
            "Music begins to introduce light percussion."
        )

    if label.startswith("Action") or label == "Agent Action":
        if action_idx < len(actions):
            a = actions[action_idx]
            verb = a.get("verb", "Do something")
            obj = a.get("object", "")
            anchor = a.get("ui_anchor", "")
            # Capability copy pattern: imperative verb, ≤4 words.
            caption = f"{verb} {obj}".strip().rstrip(".") + "."
            visual = (
                f"Action: {verb.lower()} {obj} ({anchor}). "
                "Auto-zoom 1.3x on the moment of interaction, hold ~1.0–1.5s, "
                "ease back to wide."
            )
            audio = "Music continues steady through this beat."
            if label == "Agent Action":
                audio = "Music swells slightly through this beat — payoff moment."
            return (caption, visual, audio)
        # Fallback if not enough actions provided
        return (
            "Do the thing.",
            "Action beat — one mechanic shown.",
            "Music continues steady."
        )

    if label == "Payoff":
        return (
            outcome or "Same workflow. Less friction.",
            "Wide shot back to the full UI, the result of the actions visible. Brief decel.",
            "Music begins to resolve."
        )

    return ("", "", "")


def _beat_action(label, actions, action_idx):
    """Action description for the Markdown brief — what's happening on screen."""
    if action_idx is not None and action_idx < len(actions):
        a = actions[action_idx]
        return f"Caption fades in 200ms before action; clears as action completes. Anchor: {a.get('ui_anchor', '')}."
    if label in ("Hook", "Setup", "Payoff"):
        return "Caption transitions at the start of beat over 0.25s."
    return ""


def _slugify(text):
    return "".join(c if c.isalnum() else "-" for c in text.lower()).strip("-").replace("--", "-")


def render_md_brief(storyboard, brief):
    """Render a Markdown approval brief for the storyboard."""
    sys.path.insert(0, str(Path(__file__).parent))
    from storyboard import render_md
    return render_md(storyboard)


def interactive_brief():
    """Prompt the user for the minimum brief fields."""
    print("=== Product Video Brief ===\n")
    brief = {}
    brief["product_name"] = input("Product name: ").strip() or "Product"
    brief["capability"] = input("Capability sentence (use as hook caption): ").strip()
    brief["audience"] = input("Audience: ").strip()
    brief["tone"] = input("Tone (default: informational, clean, clear, business/professional): ").strip() or \
        "informational, clean, clear, business/professional"
    length = input("Length seconds (15/30/60, default 30): ").strip() or "30"
    brief["length_s"] = int(length)
    channels = input("Channels (comma-sep, default site-hero,twitter,linkedin): ").strip() or \
        "site-hero,twitter,linkedin"
    brief["channels"] = [c.strip() for c in channels.split(",")]

    n_actions = int(input("Number of action beats (1–3, default 3): ").strip() or "3")
    actions = []
    for i in range(n_actions):
        verb = input(f"  Action {i+1} verb (e.g. 'Move'): ").strip()
        obj = input(f"  Action {i+1} object (e.g. 'a card'): ").strip()
        ui = input(f"  Action {i+1} UI anchor (e.g. 'Doing → Review'): ").strip()
        actions.append({"verb": verb, "object": obj, "ui_anchor": ui})
    brief["actions"] = actions

    brief["outcome"] = input("Outcome / payoff line: ").strip()
    print("\n--- End card ---")
    brief["end_card"] = {
        "brand_mark": input("Brand mark slug: ").strip(),
        "headline": input("End card headline: ").strip(),
        "subtitle": input("End card subtitle: ").strip(),
        "cta": input("End card CTA: ").strip() or "Try it",
        "url": input("URL: ").strip(),
    }
    title_yes = (input("\nInclude title card (1.5s)? [Y/n]: ").strip() or "y").lower().startswith("y")
    if title_yes:
        brief["title_card"] = {
            "enabled": True,
            "duration_s": 1.5,
            "headline": brief["end_card"]["headline"],
            "tagline": brief["capability"],
        }

    return brief


def main():
    ap = argparse.ArgumentParser(description="Build a product video storyboard from a brief.")
    ap.add_argument("--brief", help="Path to a brief JSON file")
    ap.add_argument("--interactive", action="store_true", help="Prompt for brief fields")
    ap.add_argument("--example-brief", action="store_true", help="Print the example brief and exit")
    ap.add_argument("--out", help="Output storyboard JSON path")
    ap.add_argument("--md", help="Also write a Markdown approval brief to this path")
    ap.add_argument("--slug", help="Override storyboard slug")
    ap.add_argument("--title", help="Override storyboard title")
    args = ap.parse_args()

    if args.example_brief:
        print(json.dumps(EXAMPLE_BRIEF, indent=2))
        return

    if args.interactive:
        brief = interactive_brief()
    elif args.brief:
        brief = json.loads(Path(args.brief).read_text())
    else:
        ap.error("Either --brief or --interactive is required (or --example-brief)")

    storyboard = build_storyboard(brief, slug=args.slug, title=args.title)

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(storyboard, indent=2))
        print(f"Wrote storyboard: {out}")
    else:
        print(json.dumps(storyboard, indent=2))

    if args.md:
        md = render_md_brief(storyboard, brief)
        Path(args.md).parent.mkdir(parents=True, exist_ok=True)
        Path(args.md).write_text(md)
        print(f"Wrote brief: {args.md}")


if __name__ == "__main__":
    main()
