#!/usr/bin/env python3
"""Email drip skill — sequence-based drip + broadcast newsletter sender for Zerg's email program.

Usage:
    python3 ~/.claude/skills/email-drip/run.py lifecycle send \\
        --to <email> --sequence <slug> [--step N] [--dry-run]
    python3 ~/.claude/skills/email-drip/run.py broadcast send \\
        --campaign <slug> --content <issue-NNN> [--segment all|zstack-users|solutions-prospects] [--dry-run]
    python3 ~/.claude/skills/email-drip/run.py validate <campaign-or-sequence-yaml>
    python3 ~/.claude/skills/email-drip/run.py list

Phase 2 build. ESP dispatch via Resend (RESEND_API_KEY env var); falls back to dry-run if key missing.
Hard-fails on raw zergai.com links — every link must pass through utm-attribution.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

VAULT = Path("/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg")
EMAIL_DIR = VAULT / "Marketing" / "Email"
SEQ_DIR = EMAIL_DIR / "Sequences"
NEWS_DIR = EMAIL_DIR / "Newsletters"
SENT_LOG = EMAIL_DIR / "sent-log.md"
LIST_FILE = EMAIL_DIR / "list.md"

ZERG_DOMAINS = {"zergai.com", "www.zergai.com", "zergboard.ai", "www.zergboard.ai"}

RESEND_API_URL = "https://api.resend.com/emails"
DEFAULT_FROM = "Zerg <hello@zergai.com>"
DEFAULT_REPLY_TO = "matt@zergai.com"


class DripError(Exception):
    pass


def parse_simple_yaml(text: str) -> dict:
    """Naive YAML parser — handles flat key:value, '|' literal blocks, and simple '- ' lists."""
    out: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        i += 1
        if not line or line.lstrip().startswith("#"):
            continue
        if line.startswith(" "):
            continue  # already-consumed continuation
        if ":" not in line:
            continue
        k, _, v = line.partition(":")
        k = k.strip()
        v = v.strip()
        if v == "|" or v == ">":
            # literal block — gobble subsequent indented lines
            block_lines: list[str] = []
            while i < len(lines):
                nxt = lines[i]
                if not nxt:
                    block_lines.append("")
                    i += 1
                    continue
                if nxt.startswith("  "):
                    block_lines.append(nxt[2:])
                    i += 1
                    continue
                break
            # strip trailing empty lines
            while block_lines and block_lines[-1] == "":
                block_lines.pop()
            sep = "\n" if v == "|" else " "
            out[k] = sep.join(block_lines)
        elif not v:
            # list start
            items: list = []
            while i < len(lines) and lines[i].lstrip().startswith("- "):
                items.append(lines[i].lstrip()[2:].strip().strip('"'))
                i += 1
            out[k] = items
        else:
            if v.startswith('"') and v.endswith('"'):
                v = v[1:-1]
            out[k] = v
    return out


def find_raw_zerg_links(body: str) -> list[str]:
    """Find zergai.com links missing utm_source param."""
    raw: list[str] = []
    for url in re.findall(r"https?://[^\s)\"']+", body):
        host = urlparse(url).netloc.lower()
        if host in ZERG_DOMAINS or any(host.endswith(s) for s in [".zergai.com"]):
            if "utm_source=" not in url:
                raw.append(url)
    return raw


def render_template(text: str, ctx: dict[str, str]) -> str:
    """Replace {{key}} with ctx[key]."""
    def replace(m: re.Match) -> str:
        key = m.group(1).strip()
        return ctx.get(key, m.group(0))
    return re.sub(r"\{\{\s*([^}]+?)\s*\}\}", replace, text)


def append_sent_log(date_str: str, recipient: str, kind: str, sequence: str,
                    subject: str, dry_run: bool) -> None:
    EMAIL_DIR.mkdir(parents=True, exist_ok=True)
    if not SENT_LOG.exists():
        SENT_LOG.write_text(
            "# Email Send Log\n\nAuto-appended by email-drip skill.\n\n"
            "| Date | Recipient | Kind | Sequence | Subject | Mode |\n"
            "|---|---|---|---|---|---|\n"
        )
    mode = "dry-run" if dry_run else "sent"
    row = f"| {date_str} | {recipient} | {kind} | {sequence} | {subject} | {mode} |\n"
    with SENT_LOG.open("a") as f:
        f.write(row)


def resend_send(to: str, subject: str, body: str, from_addr: str, reply_to: str) -> bool:
    """Dispatch via Resend API. Returns True on success. False on missing key OR API failure."""
    key = os.environ.get("RESEND_API_KEY")
    if not key:
        print("WARN: RESEND_API_KEY not set; falling back to dry-run.", file=sys.stderr)
        return False
    payload = {
        "from": from_addr,
        "to": [to],
        "subject": subject,
        "html": body if "<html" in body.lower() or "<p>" in body else None,
        "text": body if not ("<html" in body.lower() or "<p>" in body) else None,
        "reply_to": reply_to,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    req = urllib.request.Request(
        RESEND_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            r.read()
        return True
    except urllib.error.HTTPError as e:
        print(f"ERROR: Resend API HTTP {e.code}: {e.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return False
    except (urllib.error.URLError, OSError) as e:
        print(f"ERROR: Resend API call failed: {e}", file=sys.stderr)
        return False


def load_sequence(slug: str) -> tuple[Path, dict]:
    f = SEQ_DIR / f"{slug}.yaml"
    if not f.exists():
        raise DripError(f"sequence not found: {f}")
    return f, parse_simple_yaml(f.read_text())


def load_newsletter(content: str) -> tuple[Path, dict, str]:
    f = NEWS_DIR / f"{content}.md"
    if not f.exists():
        raise DripError(f"newsletter not found: {f}")
    text = f.read_text()
    if text.startswith("---\n"):
        end = text.find("\n---\n", 4)
        if end > 0:
            meta = parse_simple_yaml(text[4:end])
            body = text[end + 5 :]
            return f, meta, body
    return f, {}, text


def cmd_lifecycle_send(args: argparse.Namespace) -> int:
    f, seq = load_sequence(args.sequence)
    steps = seq.get("steps") if isinstance(seq.get("steps"), list) else None
    # Steps as a list of slugs pointing to per-step Markdown files
    if not steps:
        # Single-step inline shape
        subject = seq.get("subject", "(no subject)")
        body_template = seq.get("body", "")
    else:
        idx = (args.step or 1) - 1
        if idx < 0 or idx >= len(steps):
            raise DripError(f"step {args.step} out of range; sequence has {len(steps)} steps")
        step_file = SEQ_DIR / args.sequence / f"{steps[idx]}.md"
        if not step_file.exists():
            raise DripError(f"step file not found: {step_file}")
        step_text = step_file.read_text()
        if step_text.startswith("---\n"):
            end = step_text.find("\n---\n", 4)
            meta = parse_simple_yaml(step_text[4:end])
            body_template = step_text[end + 5 :]
            subject = meta.get("subject", "(no subject)")
        else:
            subject = "(no subject)"
            body_template = step_text

    ctx = {"recipient_email": args.to, "today": dt.date.today().isoformat()}
    body = render_template(body_template, ctx)
    subject = render_template(subject, ctx)

    raw = find_raw_zerg_links(body)
    if raw:
        print("ERROR: raw zergai.com links found (UTM-instrument them via utm-attribution):", file=sys.stderr)
        for u in raw:
            print(f"  {u}", file=sys.stderr)
        return 1

    sent = False
    if not args.dry_run:
        sent = resend_send(args.to, subject, body, DEFAULT_FROM, DEFAULT_REPLY_TO)
    today = dt.date.today().isoformat()
    append_sent_log(today, args.to, "lifecycle", f"{args.sequence}#{args.step or 1}", subject, dry_run=args.dry_run or not sent)

    if args.dry_run or not sent:
        print(f"--- DRY RUN ---")
        print(f"To: {args.to}")
        print(f"Subject: {subject}")
        print(f"Body:\n{body}")
        return 0
    print(f"Sent to {args.to}: {subject}")
    return 0


def cmd_broadcast_send(args: argparse.Namespace) -> int:
    f, meta, body_template = load_newsletter(args.content)
    subject = meta.get("subject") or args.subject or "(no subject)"

    if not LIST_FILE.exists():
        raise DripError(
            f"list not found at {LIST_FILE}. Create it with header `# Newsletter list`\n"
            "and one email per row in a Markdown table with columns: email, segment, status."
        )

    # Parse list
    rows = []
    for ln in LIST_FILE.read_text().splitlines():
        if not ln.startswith("|") or ln.startswith("|---") or "email" in ln.lower() and "segment" in ln.lower():
            continue
        cells = [c.strip() for c in ln.split("|")[1:-1]]
        if len(cells) >= 3 and "@" in cells[0]:
            email, segment, status = cells[0], cells[1], cells[2]
            if status.lower() in {"unsubscribed", "bounced"}:
                continue
            if args.segment != "all" and segment != args.segment:
                continue
            rows.append(email)

    if not rows:
        print(f"No recipients matched segment={args.segment}.")
        return 0

    raw = find_raw_zerg_links(body_template)
    if raw:
        print("ERROR: raw zergai.com links found (UTM-instrument via utm-attribution):", file=sys.stderr)
        for u in raw:
            print(f"  {u}", file=sys.stderr)
        return 1

    today = dt.date.today().isoformat()
    sent_count = 0
    for email in rows:
        ctx = {"recipient_email": email, "today": today}
        body = render_template(body_template, ctx)
        subj = render_template(subject, ctx)
        if args.dry_run:
            ok = False
        else:
            ok = resend_send(email, subj, body, DEFAULT_FROM, DEFAULT_REPLY_TO)
        if ok:
            sent_count += 1
        append_sent_log(today, email, "broadcast", f"{args.campaign}/{args.content}", subj, dry_run=args.dry_run or not ok)

    if args.dry_run:
        print(f"DRY RUN: would have sent to {len(rows)} recipients (segment={args.segment}). Subject: {subject}")
    else:
        print(f"Sent: {sent_count}/{len(rows)}. Failures logged in {SENT_LOG}.")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    p = Path(args.target)
    if not p.exists():
        print(f"ERROR: not found: {p}", file=sys.stderr)
        return 1
    text = p.read_text()
    raw = find_raw_zerg_links(text)
    if raw:
        print(f"FAIL: raw zergai.com links:")
        for u in raw:
            print(f"  {u}")
        return 2
    print("OK")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    print("Sequences:")
    if SEQ_DIR.exists():
        for f in sorted(SEQ_DIR.glob("*.yaml")):
            print(f"  - {f.stem}")
    else:
        print("  (no sequences directory)")
    print("Newsletter issues:")
    if NEWS_DIR.exists():
        for f in sorted(NEWS_DIR.glob("*.md")):
            print(f"  - {f.stem}")
    else:
        print("  (no newsletters directory)")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="email-drip", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("lifecycle", help="lifecycle (transactional) operations")
    plsub = pl.add_subparsers(dest="lifecycle_cmd", required=True)
    pls = plsub.add_parser("send")
    pls.add_argument("--to", required=True)
    pls.add_argument("--sequence", required=True)
    pls.add_argument("--step", type=int, default=1)
    pls.add_argument("--dry-run", action="store_true")
    pls.set_defaults(func=cmd_lifecycle_send)

    pb = sub.add_parser("broadcast", help="broadcast newsletter operations")
    pbsub = pb.add_subparsers(dest="broadcast_cmd", required=True)
    pbs = pbsub.add_parser("send")
    pbs.add_argument("--campaign", required=True)
    pbs.add_argument("--content", required=True, help="newsletter slug, e.g. issue-001")
    pbs.add_argument("--segment", default="all")
    pbs.add_argument("--subject", help="override subject (default: from frontmatter)")
    pbs.add_argument("--dry-run", action="store_true")
    pbs.set_defaults(func=cmd_broadcast_send)

    pv = sub.add_parser("validate", help="validate a campaign or sequence file (raw-link scan)")
    pv.add_argument("target")
    pv.set_defaults(func=cmd_validate)

    pls2 = sub.add_parser("list", help="list available sequences and newsletter issues")
    pls2.set_defaults(func=cmd_list)

    args = p.parse_args()
    try:
        return args.func(args)
    except DripError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
