#!/usr/bin/env python3
"""self-email-miner — harvest + commit helper for mining self-emails to matthew@zergai.com.

The *intelligence* (deciding what each item is, writing the log) lives in the Claude session
that runs this skill; this script does the mechanical, idempotent parts:

  harvest   search for self-emails NOT yet in the cursor, read bodies, extract URLs,
            download attachments, and emit fresh_items.json for the session to process.
  commit    given a list of email ids, archive them (gmail mark-done) and add them to the
            cursor so they are never reprocessed.

State lives in ~/.claude/state/self-email-miner/ : cursor.json (processed ids), work/ (scratch).
"""
import json, os, re, subprocess, sys, argparse, datetime

HOME = os.path.expanduser("~")
GS = os.path.join(HOME, ".claude/skills/gmail-skill")
# gmail-skill needs a Python with google-auth deps. The old value pointed at
# gmail-skill's own .venv (which doesn't exist) — and a prior local variant used
# sys.executable (this miner's .venv, which also lacks the deps). Either way every
# `harvest` failed with an empty-stdout JSON error, so the cursor was never created.
# Resolve a system python3 (which carries the deps) for the gmail-skill subprocess.
import shutil as _shutil
GS_PY = _shutil.which("python3") or "/opt/homebrew/bin/python3"
ACCOUNT = "matthew@zergai.com"
STATE = os.path.join(HOME, ".claude/state/self-email-miner")
CURSOR = os.path.join(STATE, "cursor.json")
WORK = os.path.join(STATE, "work")
QUERY = "to:matthew@zergai.com (from:matteisn@gmail.com OR from:matthew@zergai.com)"
URL_RE = re.compile(r'https?://[^\s<>"\)\]]+')

def gs(*args):
    r = subprocess.run([GS_PY, "gmail_skill.py", *args, "-a", ACCOUNT],
                       cwd=GS, capture_output=True, text=True, timeout=120)
    return r.stdout

def load_cursor():
    if os.path.exists(CURSOR):
        return json.load(open(CURSOR))
    return {"processed_ids": [], "last_run": None}

def save_cursor(c):
    os.makedirs(STATE, exist_ok=True)
    json.dump(c, open(CURSOR, "w"), indent=1)

def harvest(max_results=200):
    cur = load_cursor()
    seen = set(cur["processed_ids"])
    try:
        search = json.loads(gs("search", QUERY, "--max-results", str(max_results)))
    except Exception as e:
        print(json.dumps({"error": f"search failed: {e}"})); return
    fresh = []
    for m in search.get("results", []):
        if m["id"] in seen:
            continue
        try:
            full = json.loads(gs("read", m["id"]))
        except Exception:
            full = {"body": "", "attachments": []}
        body = full.get("body", "") or ""
        urls = []
        for u in URL_RE.findall(body):
            u = u.rstrip('.,);')
            if u not in urls:
                urls.append(u)
        atts = [{"filename": a.get("filename"), "mimeType": a.get("mimeType")}
                for a in full.get("attachments", [])]
        if atts:  # pull attachments to scratch so the session can read them
            outdir = os.path.join(WORK, m["id"])
            os.makedirs(outdir, exist_ok=True)
            gs("attachment", m["id"], "--out-dir", outdir)
        fresh.append({
            "id": m["id"], "date": m.get("date", ""), "from": m.get("from", ""),
            "subject": m.get("subject", ""), "snippet": m.get("snippet", ""),
            "in_inbox": "INBOX" in m.get("labels", []),
            "urls": urls, "attachments": atts,
            "body_preview": body.strip()[:300],
        })
    out = os.path.join(STATE, "fresh_items.json")
    json.dump(fresh, open(out, "w"), indent=1)
    print(json.dumps({"fresh_count": len(fresh), "already_processed": len(seen),
                      "fresh_items_file": out}))

def commit(ids, archive=True):
    cur = load_cursor()
    seen = set(cur["processed_ids"])
    archived = []
    for i in ids:
        if archive:
            gs("mark-done", i)
            archived.append(i)
        seen.add(i)
    cur["processed_ids"] = sorted(seen)
    cur["last_run"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    save_cursor(cur)
    print(json.dumps({"committed": len(ids), "archived": len(archived),
                      "total_processed": len(seen)}))

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    h = sub.add_parser("harvest"); h.add_argument("--max-results", type=int, default=200)
    c = sub.add_parser("commit")
    c.add_argument("ids", nargs="+")
    c.add_argument("--no-archive", action="store_true")
    a = ap.parse_args()
    if a.cmd == "harvest":
        harvest(a.max_results)
    elif a.cmd == "commit":
        commit(a.ids, archive=not a.no_archive)
