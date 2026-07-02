#!/usr/bin/env python3
"""inbox-manager — Phase 0 read-only inbox scan (+ Phase-1 prep: --fetch-bodies).

Smallest useful first version of the long-term inbox management system
(plan: ~/.claude/plans/i-want-to-design-hidden-axolotl.md).

Design: REUSE, don't rebuild. This imports the canonical logic as libraries
so there is zero drift from the daily systems:
  - gmail-triage  (TierMap / KillList / DealWatch / Classifier / Thread)  → classification
  - zergguard-scam-check check.py (Verdict / check_sender / check_text / check_url) → scam scoring

It scans BOTH mailboxes (personal IMAP + work OAuth), account-aware, and writes
per-item classification records + a human digest. It is strictly READ-ONLY:
it never calls mark_done / archive / label / send. The only writes are local
state files and a Downloads digest. This is Phase 0 — we prove classification
accuracy before any staged action is enabled.

--fetch-bodies (Phase-1 PREP, off by default): fetch full message bodies via
gmail-skill `read` for HUMAN_IN / PROJECT / already-flagged items and re-score
scam on the fuller text. The daily 07:15 job runs WITHOUT this flag (light +
read-only); extractors use it later.

Outputs (all local — NO Gmail mutations):
  ~/.claude/state/inbox/items-<date>.jsonl     per-item records (fresh each run)
  ~/.claude/state/inbox/scam_verdicts.jsonl    append-only: non-SAFE verdicts only
  ~/.claude/state/inbox/scan.jsonl             append-only: per-run audit
  ~/.claude/state/inbox/spotcheck-<date>.jsonl 5-item accuracy sample
  ~/Downloads/email_triage_<date>/email_review.md   human digest

recommended_action / risk_tier / autonomy_verdict on each record are ADVISORY
previews of what Phase 1+ would do — Phase 0 takes none of them.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

HOME = Path.home()
SKILLS = HOME / ".claude/skills"
STATE = HOME / ".claude/state/inbox"

# --- import canonical logic as libraries (no subprocess, no drift) ----------
sys.path.insert(0, str(SKILLS / "gmail-triage"))
sys.path.insert(0, str(SKILLS / "zergguard-scam-check"))
sys.path.insert(0, str(HOME / ".config/zerg-guard/lib"))  # check.py needs ioc
import gmail_triage as gt          # noqa: E402
import check as scam               # noqa: E402

# Both addresses are "me" — the daily gmail_triage hardcodes matteisn only, so
# for the work lane we override last_from_matt against this union.
SELF_ADDRESSES = {"matteisn@gmail.com", "matthew@zergai.com"}
DEFAULT_ACCOUNTS = ["matteisn@gmail.com", "matthew@zergai.com"]


def list_account(account: str, max_results: int) -> list[dict]:
    """Read-only INBOX list for one account via gmail-skill CLI → thread-shaped dicts."""
    cmd = ["python3", str(gt.GMAIL_SKILL), "list", "--account", account,
           "--label", "INBOX", "--max-results", str(max_results)]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    if r.returncode != 0:
        raise RuntimeError(
            f"gmail-skill list failed for {account} (exit {r.returncode}): "
            f"{r.stderr.strip()[:300]}"
        )
    raw = json.loads(r.stdout)
    if isinstance(raw, dict):
        items = raw.get("results") or raw.get("threads") or []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    # gmail-skill 'list' returns message-level items, so a multi-message thread
    # yields N rows. Collapse to one row per thread (list is reverse-chron, so
    # the first occurrence is the latest message — what classification wants).
    seen, deduped = set(), []
    for it in items:
        tid = it.get("threadId") or it.get("id")
        if tid in seen:
            continue
        seen.add(tid)
        deduped.append(it)
    # results items are flat message summaries; adapt via the canonical helper
    return [gt.GmailTransport._cli_item_to_thread(it) for it in deduped]


def read_body(account: str, msg_id: str) -> str:
    """Read-only full-body fetch via gmail-skill `read`. Returns '' on any failure."""
    try:
        r = subprocess.run(
            ["python3", str(gt.GMAIL_SKILL), "read", msg_id, "--account", account],
            capture_output=True, text=True, timeout=60)
        if r.returncode != 0:
            return ""
        d = json.loads(r.stdout)
        return d.get("body", "") if isinstance(d, dict) else ""
    except Exception:
        return ""


def derive(bucket: str, scam_label: str, tier: str | None) -> tuple[str, str, str]:
    """(bucket, scam_label, tier) → (recommended_action, risk_tier, autonomy_verdict).

    ADVISORY preview of Phase 1+ behavior. 'auto' for draft_reply means
    create an UNSENT Gmail draft only — never auto-send (send-gate always guards).
    """
    if scam_label == "PHISH":
        return "review_scam", "high", "needs_matt"
    if scam_label == "SUSPICIOUS":
        return "review_scam", "medium", "needs_matt"
    if bucket == "EXCLUDED":
        return "none", "low", "never"            # family/personal — never touch
    if bucket == "HUMAN_IN":
        return "draft_reply", "medium", "auto"   # unsent draft only; send is needs_matt
    if bucket == "MINE_OUT":
        return "follow_up", "low", "auto"         # surface a nudge only
    if bucket == "DEAL":
        return "surface_deal", "low", "auto"
    if bucket == "PROJECT":
        return "surface_action", "medium", "needs_matt"
    if bucket in ("KILL", "RECEIPT"):
        # Ungraduated in Phase 0 → staged batch archive. Senders earn 'auto'
        # only after ~8 consistent approvals (graduation, Phase 2). Humans never.
        return "archive", "medium", "needs_matt"
    return "keep", "low", "auto"                  # KEEP_INBOX


def scan_account(account: str, classifier, tier_map, max_results: int,
                 fetch_bodies: bool = False) -> list[dict]:
    records = []
    now = dt.datetime.now().isoformat()
    for th in list_account(account, max_results):
        t = gt.Thread.from_mcp(th)
        # account-aware "sent by me last" (fixes single-account hardcode)
        t.last_from_matt = t.sender_email in SELF_ADDRESSES
        bucket, rationale = classifier.classify(t)
        tier = tier_map.register(t.sender_email)

        verdict = {"label": "SAFE", "score": 0, "reasons": []}
        # Only scam-scan non-family, non-known-human senders (avoids false
        # brand hits on real contacts; known humans are not phish vectors).
        if bucket != "EXCLUDED" and tier is None:
            v = scam.Verdict()
            scam.check_sender(t.sender, v)
            scam.check_text(f"{t.subject} {t.snippet}", v)
            for url in scam.URL_RE.findall(t.snippet or ""):
                scam.check_url(url, v)
            verdict = {
                "label": v.label, "score": v.score,
                "reasons": [r.text for r in sorted(v.reasons, key=lambda x: -x.weight)],
            }

        # Phase-1 prep: fetch full body for items that need it, re-score scam.
        body = ""
        if fetch_bodies and (bucket in ("HUMAN_IN", "PROJECT") or verdict["label"] != "SAFE"):
            body = read_body(account, t.id)
            if body and bucket != "EXCLUDED" and tier is None:
                v = scam.Verdict()
                scam.check_sender(t.sender, v)
                scam.check_text(body[:4000], v)
                for url in scam.URL_RE.findall(body):
                    scam.check_url(url, v)
                if v.score > verdict["score"]:
                    verdict = {"label": v.label, "score": v.score,
                               "reasons": [r.text for r in sorted(v.reasons, key=lambda x: -x.weight)]}

        action, risk, autonomy = derive(bucket, verdict["label"], tier)
        domain = t.sender_email.split("@", 1)[-1] if "@" in t.sender_email else ""
        records.append({
            "id": t.id,
            "account": account,
            "sender": t.sender,
            "sender_email": t.sender_email,
            "sender_domain": domain,
            "subject": t.subject,
            "snippet": (t.snippet or "")[:200],
            "body": body[:1000],
            "days_since_last_message": t.days_since_last_message,
            "last_from_matt": t.last_from_matt,
            "bucket": bucket,
            "tier": tier,
            "scam": verdict,
            "recommended_action": action,
            "risk_tier": risk,
            "autonomy_verdict": autonomy,
            "rationale": rationale,
            "status": "observed",   # Phase 0 takes no action
            "ts": now,
        })
    return records


# ─── digest ────────────────────────────────────────────────────────────────

def spot_check_sample(records: list[dict], n: int = 5) -> list[dict]:
    """Diverse sample across buckets for an accuracy check — deterministic."""
    by_bucket: dict[str, list[dict]] = {}
    for r in records:
        by_bucket.setdefault(r["bucket"], []).append(r)
    sample, buckets = [], sorted(by_bucket)
    i = 0
    while len(sample) < n and any(by_bucket.values()):
        b = buckets[i % len(buckets)]
        if by_bucket[b]:
            sample.append(by_bucket[b].pop(0))
        i += 1
        if i > 1000:
            break
    return sample


def write_digest(records: list[dict], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    counts: dict[str, int] = {}
    for r in records:
        counts[r["bucket"]] = counts.get(r["bucket"], 0) + 1

    scam_hits = [r for r in records if r["scam"]["label"] != "SAFE"]
    humans = sorted((r for r in records if r["bucket"] == "HUMAN_IN"),
                    key=lambda r: (r["tier"] or "Z", -r["days_since_last_message"]))
    archives = [r for r in records if r["bucket"] in ("KILL", "RECEIPT")]
    deals = [r for r in records if r["bucket"] == "DEAL"]

    L = [f"# Email Review — {today}", ""]
    L.append(f"_Phase 0 · READ-ONLY · {len(records)} items across "
             f"{len(set(r['account'] for r in records))} accounts · zero mailbox changes._")
    L.append("")
    L.append("**Counts:** " + " · ".join(f"{k} {v}" for k, v in sorted(counts.items())))
    L.append("")

    L.append("## 🔴 Scam / suspicious")
    if not scam_hits:
        L.append("_None flagged._")
    for r in sorted(scam_hits, key=lambda r: -r["scam"]["score"]):
        L.append(f"- **{r['scam']['label']} ({r['scam']['score']})** · `{r['sender_email']}` "
                 f"· {r['subject'][:70]} · _{r['account']}_")
        for reason in r["scam"]["reasons"][:2]:
            L.append(f"    - {reason}")
    L.append("")

    L.append("## 🟠 Humans awaiting your reply")
    if not humans:
        L.append("_None._")
    for r in humans:
        L.append(f"- Tier {r['tier'] or '?'} · `{r['sender_email']}` · "
                 f"{r['days_since_last_message']}d · {r['subject'][:70]} · _{r['account']}_")
    L.append("")

    L.append(f"## 🟢 Proposed archives — batch, NOT executed ({len(archives)})")
    if not archives:
        L.append("_None._")
    for r in archives[:15]:
        L.append(f"- `{r['sender_email']}` · {r['subject'][:70]} · ({r['bucket']}) · _{r['account']}_")
    if len(archives) > 15:
        L.append(f"- …and {len(archives) - 15} more (see items-{today}.jsonl)")
    L.append("")

    L.append("## 💸 Deals")
    if not deals:
        L.append("_None._")
    for r in deals:
        L.append(f"- `{r['sender_email']}` · {r['subject'][:70]} · _{r['account']}_")
    L.append("")

    sample = spot_check_sample(records)
    L.append("## ✅ Spot-check — did I classify these right?")
    L.append("_Reply with any misses; corrections seed the learning corpus._")
    for r in sample:
        L.append(f"- [{r['bucket']}] `{r['sender_email']}` · {r['subject'][:70]} "
                 f"→ _{r['rationale']}_")
    L.append("")
    L.append("---")
    L.append("_Recommended-action / risk / autonomy fields in the records are advisory "
             "previews of Phase 1+; nothing was drafted, archived, labeled, or sent._")

    path = out_dir / "email_review.md"
    path.write_text("\n".join(L))
    (STATE / f"spotcheck-{today}.jsonl").write_text(
        "\n".join(json.dumps(r) for r in sample) + ("\n" if sample else ""))
    return path


# ─── main ────────────────────────────────────────────────────────────────

def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(description="inbox-manager Phase 0 read-only scan")
    ap.add_argument("--accounts", nargs="*", default=DEFAULT_ACCOUNTS)
    ap.add_argument("--max-results", type=int, default=200)
    ap.add_argument("--fetch-bodies", action="store_true",
                    help="fetch full bodies for HUMAN_IN/PROJECT/flagged (Phase-1 prep; slower)")
    args = ap.parse_args(argv)

    STATE.mkdir(parents=True, exist_ok=True)
    tier_map = gt.TierMap()
    classifier = gt.Classifier(tier_map, gt.KillList(), gt.DealWatch())

    all_records: list[dict] = []
    per_account_counts: dict[str, dict] = {}
    for account in args.accounts:
        try:
            recs = scan_account(account, classifier, tier_map, args.max_results, args.fetch_bodies)
        except Exception as e:
            print(f"WARN: scan failed for {account}: {e}", file=sys.stderr)
            per_account_counts[account] = {"error": str(e)[:200]}
            continue
        all_records.extend(recs)
        c: dict[str, int] = {}
        for r in recs:
            c[r["bucket"]] = c.get(r["bucket"], 0) + 1
        per_account_counts[account] = {"total": len(recs), "buckets": c,
                                       "scam": sum(1 for r in recs if r["scam"]["label"] != "SAFE")}
        print(f"{account}: {len(recs)} items · {c}")

    today = dt.date.today().isoformat()
    # items snapshot (fresh each run)
    (STATE / f"items-{today}.jsonl").write_text(
        "\n".join(json.dumps(r) for r in all_records) + ("\n" if all_records else ""))
    # scam log (append-only, non-SAFE only)
    with (STATE / "scam_verdicts.jsonl").open("a") as f:
        for r in all_records:
            if r["scam"]["label"] != "SAFE":
                f.write(json.dumps({"ts": r["ts"], "account": r["account"],
                                    "sender": r["sender_email"], "subject": r["subject"],
                                    "verdict": r["scam"]}) + "\n")
    # run audit (append-only)
    with (STATE / "scan.jsonl").open("a") as f:
        f.write(json.dumps({"action": "scan", "ts": dt.datetime.now().isoformat(),
                            "accounts": per_account_counts, "fetch_bodies": args.fetch_bodies,
                            "total": len(all_records)}) + "\n")

    out_dir = HOME / f"Downloads/email_triage_{today}"
    digest = write_digest(all_records, out_dir)
    print(f"\nRecords → {STATE / f'items-{today}.jsonl'}")
    print(f"Digest  → {digest}")
    print("READ-ONLY: no mailbox changes made.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
