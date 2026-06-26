#!/usr/bin/env python3
"""memory-maintenance — read-only hygiene scan of the 3 memory lanes + CLAUDE.md files.

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
LANES = [
    {"name": "env  (dotfiles)", "dir": f"{HOME}/dotfiles/claude-memory"},
    {"name": "mhe  (personal)", "dir": f"{HOME}/Obsidian/MHE/claude-memory",
     "vault_root": f"{HOME}/Obsidian/MHE"},
    {"name": "zerg (work)", "dir": f"{HOME}/Obsidian/Zerg/claude-memory",
     "vault_root": f"{HOME}/Obsidian/Zerg",
     "projection_src": f"{HOME}/Obsidian/Zerg/MattZerg/_agent_memory"},
]
CLAUDE_MDS = {
    "global CLAUDE.md": f"{HOME}/dotfiles/claude/CLAUDE.md",
    "MHE CLAUDE.md":    f"{HOME}/Obsidian/MHE/CLAUDE.md",
}
MEMORY_MD_MAX_LINES = 90      # index getting long → consider pruning/splitting
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
    md_targets = {os.path.basename(t) for t in MDLINK.findall(idx)}
    wiki_targets = {t.strip() for t in WIKILINK.findall(idx)}
    indexed = {t[:-3] if t.endswith(".md") else t for t in md_targets} | wiki_targets
    # valid targets for "is this a real note": local files + (projection source) + (vault-wide for obsidian)
    valid = set(basenames)
    if L.get("projection_src") and os.path.isdir(L["projection_src"]):
        valid |= basenames_under(L["projection_src"])
    if L.get("vault_root") and os.path.isdir(L["vault_root"]):
        valid |= basenames_under(L["vault_root"])
    orphans = sorted(b for b in basenames if b not in indexed)        # file exists, not in index
    dangling = sorted(t[:-3] for t in md_targets if t[:-3] not in valid and t not in files)
    dangling += sorted(t for t in wiki_targets if t not in valid)
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
        for tgt in WIKILINK.findall(txt):
            tgt = tgt.strip()
            if tgt and tgt not in valid:
                broken.append([b, tgt])
    r.update({"file_count": len(files), "idx_lines": lines(idx_path),
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
        if res["idx_lines"] > MEMORY_MD_MAX_LINES:
            report["flags"].append(f"{res['lane']}: MEMORY.md {res['idx_lines']} lines (>{MEMORY_MD_MAX_LINES}) — prune/split")
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
