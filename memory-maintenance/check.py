#!/usr/bin/env python3
"""memory-maintenance — read-only hygiene scan of the 2 memory scopes (core + work) + CLAUDE.md files.

Reports (never modifies): index integrity (orphans/dangling), bloat (oversized files),
staleness (old dates / long-untouched), broken [[wikilinks]]. Advisory only — pruning/merging
is proposed for the session to confirm, not auto-applied.

Lane-aware to avoid false positives:
  - Obsidian lanes resolve [[wikilinks]] vault-wide (a link can target any note in the vault).
  - The Zerg lane's MEMORY.md is a PROJECTION of MattZerg/_agent_memory — index entries whose
    target lives there are expected, not dangling.
"""
import os, re, json, time, datetime

HOME = os.path.expanduser("~")
# dir = the claude-memory lane; vault_root = resolve wikilinks vault-wide (Obsidian);
# projection_src = an external dir the index legitimately references (not local files).
# 2 scopes (post-2026-06-30 collapse): core (env+personal+unclassified) + work (Zerg).
# Personal/MHE was folded into core; MHE is no longer a memory lane.
LANES = [
    {"name": "core (dotfiles)", "dir": f"{HOME}/dotfiles/claude-memory"},
    {"name": "zerg (work)", "dir": f"{HOME}/Obsidian/Zerg/MattZerg/claude-memory",
     "vault_root": f"{HOME}/Obsidian/Zerg/MattZerg",
     "projection_src": f"{HOME}/Obsidian/Zerg/MattZerg/_agent_memory"},
]
CLAUDE_MDS = {
    "global CLAUDE.md": f"{HOME}/dotfiles/claude/CLAUDE.md",
    "MHE CLAUDE.md":    f"{HOME}/Obsidian/MHE/CLAUDE.md",
}
MEMORY_MD_MAX_LINES = 90      # advisory only; the real cap is the byte limit below
MEMORY_MD_MAX_BYTES = 24976   # hard load limit enforced by agent-memory-sync.py
CLAUDE_MD_MAX_LINES = 120     # global instructions getting heavy
MEMORY_FILE_MAX_BYTES = 6000  # a single fact-memory should not be an essay
PROJECT_FILE_MAX_BYTES = 12000  # active `type: project` trackers legitimately run longer
STALE_DAYS = 180             # untouched this long → review for relevance

def mem_type(path):
    try:
        head = open(path, encoding="utf-8", errors="ignore").read(800)
        m = re.search(r'^\s*type:\s*([a-z]+)', head, re.M)
        return m.group(1) if m else ""
    except: return ""

MDLINK = re.compile(r'\[[^\]]+\]\(([^)]+\.md)\)')
WIKILINK = re.compile(r'\[\[([^\]|#]+)')
BACKTICK_MD = re.compile(r'`([^`]+\.md)`')   # catalog tables list files as `composite_x.md`

def _is_example_link(t: str) -> bool:
    """True for documentation/template placeholders, not real note links: angle-bracket
    or ellipsis markers (<slug>, ...), or path-style targets (real flat-vault note
    wikilinks are bare basenames). Keeps guidance-doc examples from false-flagging."""
    return any(m in t for m in ("<", ">", "...", "/"))

def lines(p):
    try: return open(p, encoding="utf-8", errors="ignore").read().count("\n") + 1
    except: return 0

def basenames_under(root):
    out = set()
    for dp, _, fns in os.walk(root):
        if "/.git" in dp: continue
        for f in fns:
            if f.endswith(".md"):
                out.add(os.path.splitext(f)[0])
    return out

def scan_lane(L):
    name, d = L["name"], L["dir"]
    r = {"lane": name, "dir": d, "exists": os.path.isdir(d)}
    if not r["exists"]:
        return r
    files = [f for f in os.listdir(d) if f.endswith(".md") and f != "MEMORY.md"]
    basenames = {os.path.splitext(f)[0] for f in files}
    idx_path = os.path.join(d, "MEMORY.md")
    idx = open(idx_path, encoding="utf-8", errors="ignore").read() if os.path.exists(idx_path) else ""
    # Catalog-aware: MEMORY.md links to ARCHIVE.md + the catalog files, which in
    # turn list the projected/feedback notes. A file reachable via those is
    # indexed transitively (not an orphan) — fold their link targets in too.
    link_text = idx
    for catalog in ("ARCHIVE.md", "MEMORY-composites.md", "MEMORY-projections.md"):
        cp = os.path.join(d, catalog)
        if os.path.exists(cp):
            link_text += "\n" + open(cp, encoding="utf-8", errors="ignore").read()
    md_targets_full = MDLINK.findall(link_text)
    md_targets = {os.path.basename(t) for t in md_targets_full}
    wiki_targets = {t.strip() for t in WIKILINK.findall(link_text)}
    # Catalog tables (MEMORY-composites/projections.md) reference files as backtick
    # filenames `composite_x.md`, not markdown links — credit those as indexed too,
    # else every catalog-listed projection false-orphans.
    backtick_targets = {os.path.basename(t)[:-3] for t in BACKTICK_MD.findall(link_text)}
    indexed = {t[:-3] if t.endswith(".md") else t for t in md_targets} | wiki_targets | backtick_targets
    # valid targets for "is this a real note": local files + (projection source) + (vault-wide for obsidian)
    valid = set(basenames)
    if L.get("projection_src") and os.path.isdir(L["projection_src"]):
        valid |= basenames_under(L["projection_src"])
    if L.get("vault_root") and os.path.isdir(L["vault_root"]):
        valid |= basenames_under(L["vault_root"])
    orphans = sorted(b for b in basenames if b not in indexed)        # file exists, not in index
    # MD-link dangling: a BARE in-lane link (foo.md) whose file is missing. Cross-dir /
    # explicit-path links (~/.claude/agents/x.md, ../plans/y.md) are resolved at the path
    # and exempted when the file exists — intentional pointers, not lane dangling.
    dangling = []
    for full in md_targets_full:
        base = os.path.basename(full); name = base[:-3] if base.endswith(".md") else base
        if "/" in full:  # cross-dir / explicit path
            if not (os.path.exists(os.path.expanduser(full)) or os.path.exists(os.path.join(d, full))):
                dangling.append(name)
        elif name not in valid and base not in files:
            dangling.append(name)
    dangling = sorted(set(dangling))
    # Wikilink dangling: skip example/template placeholders (guidance-doc examples).
    dangling += sorted(t for t in wiki_targets if t not in valid and not _is_example_link(t))
    now = time.time()
    big, stale = [], []
    for f in files:
        p = os.path.join(d, f); sz = os.path.getsize(p)
        limit = PROJECT_FILE_MAX_BYTES if mem_type(p) == "project" else MEMORY_FILE_MAX_BYTES
        if sz > limit: big.append([f, sz])
        if (now - os.path.getmtime(p)) / 86400 > STALE_DAYS:
            stale.append([f, int((now - os.path.getmtime(p)) / 86400)])
    # broken wikilinks inside memory bodies (target not resolvable anywhere valid)
    broken = []
    for b in basenames:
        txt = open(os.path.join(d, b + ".md"), encoding="utf-8", errors="ignore").read()
        txt = re.sub(r'`[^`]*`', '', txt)  # drop inline-code spans: `[[Foo]]` examples aren't real links
        for tgt in WIKILINK.findall(txt):
            tgt = tgt.strip()
            if tgt and tgt not in valid and not _is_example_link(tgt):
                broken.append([b, tgt])
    idx_bytes = os.path.getsize(idx_path) if os.path.exists(idx_path) else 0
    r.update({"file_count": len(files), "idx_lines": lines(idx_path), "idx_bytes": idx_bytes,
              "orphans": orphans, "dangling": sorted(set(dangling)),
              "oversized": big, "stale": stale, "broken_wikilinks": broken})
    return r

def main():
    report = {"generated": datetime.date.today().isoformat(), "lanes": [], "claude_mds": [], "flags": []}
    for L in LANES:
        res = scan_lane(L)
        report["lanes"].append(res)
        if not res.get("exists"):
            report["flags"].append(f"{L['name']}: lane dir missing ({L['dir']})"); continue
        if res.get("idx_bytes", 0) > MEMORY_MD_MAX_BYTES:
            report["flags"].append(f"{res['lane']}: MEMORY.md {res['idx_bytes']}B (>{MEMORY_MD_MAX_BYTES} load limit) — prune/split")
        if res["orphans"]:
            report["flags"].append(f"{res['lane']}: {len(res['orphans'])} file(s) missing from index → {res['orphans']}")
        if res["dangling"]:
            report["flags"].append(f"{res['lane']}: index → {len(res['dangling'])} missing target(s) → {res['dangling']}")
        if res["oversized"]:
            report["flags"].append(f"{res['lane']}: oversized → {[f for f,_ in res['oversized']]}")
        if res["stale"]:
            report["flags"].append(f"{res['lane']}: {len(res['stale'])} stale (>{STALE_DAYS}d) → {[f for f,_ in res['stale']]}")
        if res["broken_wikilinks"]:
            report["flags"].append(f"{res['lane']}: broken [[link]] → {res['broken_wikilinks']}")
    for name, p in CLAUDE_MDS.items():
        if os.path.exists(p):
            ln = lines(p); report["claude_mds"].append({"file": name, "lines": ln, "path": p})
            mx = CLAUDE_MD_MAX_LINES if "global" in name else 80
            if ln > mx:
                report["flags"].append(f"{name}: {ln} lines (>{mx}) — getting heavy, consider trimming")
    if not report["flags"]:
        report["flags"].append("clean — no hygiene issues found")
    print(json.dumps(report, indent=1))

if __name__ == "__main__":
    main()
