#!/usr/bin/env python3
"""
scifi-predicted-this bridge — parse the OMPHALOS technology bestiary into structured records so the
producer can auto-wire each bulletin's real-futurology grounding (the "sci-fi predicted this" hook).

Source of truth: scifi-reels/encyclopedia/technology.md (each entry = in-world tech + antecedent +
real analogue + similarity_kind + confidence + grounding + "the crack").

CLI:
  bridge.py list                 -> one tech name per line
  bridge.py get "<name>"         -> JSON record for one tech (fuzzy match on name)
  bridge.py all                  -> JSON array of every record
  bridge.py hook "<name>"        -> the ready-to-paste video-description hook string
"""
from __future__ import annotations
import json, re, sys, difflib
from pathlib import Path

TECH_MD = Path("/Users/mattheweisner/Obsidian/Zerg/MattZerg/Projects/Zerg-Production/scifi-reels/encyclopedia/technology.md")


def parse() -> list[dict]:
    text = TECH_MD.read_text()
    # only the bestiary clusters, not the trailing "New canonical terms coined" glossary
    text = text.split("### New canonical terms")[0]
    recs = []
    # split into ### entries (skip ## cluster headers)
    for block in re.split(r"\n### ", text)[1:]:
        lines = block.split("\n")
        name = lines[0].strip()
        body = "\n".join(lines[1:])
        # description = text up to the **Antecedent:** line
        desc = body.split("**Antecedent:")[0].strip().replace("\n", " ")
        ant = re.search(r"\*\*Antecedent:\*\*\s*(.+?)\.\s*\*\*Real analogue", body, re.S)
        ana = re.search(r"\*\*Real analogue:\*\*\s*(.+?)\.\s*(?:\*\*|`|analogue)", body, re.S)
        sim = re.search(r"\*\*`([^`]+)`\*\*", body)
        conf = re.search(r"conf\s*~?(\d\.\d+)", body)
        grounding = "frontier" if "Frontier-labeled" in body else ("grounded" if "Grounded core" in body else "mixed")
        crack_m = re.search(r"\*\*The crack\s*[—-]+\s*(.+?)\.\*\*\s*(.+)", body, re.S)
        recs.append({
            "name": name,
            "summary": desc,
            "antecedent": (ant.group(1).strip() if ant else ""),
            "analogue": (ana.group(1).strip() if ana else ""),
            "similarity_kind": (sim.group(1) if sim else ""),
            "confidence": (float(conf.group(1)) if conf else None),
            "grounding": grounding,
            "crack_title": (crack_m.group(1).strip() if crack_m else ""),
            "crack": (crack_m.group(2).strip().replace("\n", " ") if crack_m else ""),
        })
    return recs


def find(name: str, recs: list[dict]) -> dict | None:
    names = [r["name"] for r in recs]
    # exact / substring / fuzzy
    for r in recs:
        if r["name"].lower() == name.lower():
            return r
    for r in recs:
        if name.lower() in r["name"].lower():
            return r
    m = difflib.get_close_matches(name, names, n=1, cutoff=0.4)
    return next((r for r in recs if r["name"] == m[0]), None) if m else None


def hook(r: dict) -> str:
    """Ready-to-paste 'sci-fi predicted this' video-description line."""
    return (f"// {r['name']} is grounded in real futurology: {r['antecedent']} → {r['analogue']} "
            f"({r['grounding']}). The crack: {r['crack_title'].lower()}.")


def main() -> int:
    recs = parse()
    if len(sys.argv) < 2:
        print(__doc__); return 0
    cmd = sys.argv[1]
    if cmd == "list":
        for r in recs: print(r["name"])
    elif cmd == "all":
        print(json.dumps(recs, indent=2))
    elif cmd in ("get", "hook") and len(sys.argv) > 2:
        r = find(sys.argv[2], recs)
        if not r:
            print(f"no match for {sys.argv[2]!r}; try: bridge.py list", file=sys.stderr); return 1
        print(hook(r) if cmd == "hook" else json.dumps(r, indent=2))
    else:
        print(__doc__); return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
