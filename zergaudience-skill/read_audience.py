#!/usr/bin/env python3
"""Read-only Postgres queries against ZergAudience contacts."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys

DEFAULT_DSN = "postgres://localhost/zergaudience?sslmode=disable"


def dsn() -> str:
    return os.environ.get("ZERGAUDIENCE_DATABASE_URL", DEFAULT_DSN)


def psql(sql: str) -> str:
    try:
        result = subprocess.run(
            ["psql", dsn(), "-At", "-F", "\t", "-c", sql],
            capture_output=True,
            text=True,
            timeout=20,
        )
    except FileNotFoundError:
        print("psql not installed. brew install postgresql", file=sys.stderr)
        sys.exit(1)
    except subprocess.TimeoutExpired:
        print("(psql timed out)", file=sys.stderr)
        return ""
    if result.returncode != 0:
        print(f"(psql error: {result.stderr.strip()})", file=sys.stderr)
        print(
            "If running outside ZergAudience local dev, set "
            "ZERGAUDIENCE_DATABASE_URL to a read-only DSN.",
            file=sys.stderr,
        )
        return ""
    return result.stdout


def fmt_contact_row(row: list[str]) -> str:
    first_seen, email, first, last, src, product, utm, status = (
        (row + [""] * 8)[:8]
    )
    name = f"{first or ''} {last or ''}".strip() or "—"
    return (
        f"[{first_seen[:16]:16}] {email:40}  {name:25}  "
        f"src={src:18} product={product or '—':12} utm={utm or '—':14} status={status}"
    )


def cmd_summary() -> int:
    print("=== Workspace totals ===")
    out = psql("SELECT name, slug FROM workspaces ORDER BY created_at")
    if not out.strip():
        print("(no workspaces — is the DB reachable?)")
        return 1
    for line in out.strip().split("\n"):
        name, slug = line.split("\t")
        print(f"  workspace: {name} ({slug})")
        counts = psql(
            "SELECT primary_source, status, COUNT(*) FROM contacts c "
            f"WHERE c.workspace_id = (SELECT id FROM workspaces WHERE slug='{slug}') "
            "GROUP BY primary_source, status ORDER BY 3 DESC"
        )
        if counts.strip():
            print(f"    {'source':<20} {'status':<14} count")
            for r in counts.strip().split("\n"):
                ps, st, ct = r.split("\t")
                print(f"    {ps:<20} {st:<14} {ct}")

        recents = psql(
            "SELECT COUNT(*) FILTER (WHERE first_seen_at > NOW() - INTERVAL '7 days'), "
            "COUNT(*) FILTER (WHERE first_seen_at > NOW() - INTERVAL '30 days'), "
            "COUNT(*) FROM contacts "
            f"WHERE workspace_id = (SELECT id FROM workspaces WHERE slug='{slug}')"
        )
        if recents.strip():
            d7, d30, total = recents.strip().split("\t")
            print(f"    last 7d: {d7}  |  last 30d: {d30}  |  all-time: {total}")
    return 0


def cmd_recent(days: int, limit: int) -> int:
    out = psql(
        "SELECT first_seen_at, email, first_name, last_name, primary_source, "
        "primary_source_product, utm_first_source, status FROM contacts "
        f"WHERE first_seen_at > NOW() - INTERVAL '{days} days' "
        f"ORDER BY first_seen_at DESC LIMIT {limit}"
    )
    if not out.strip():
        print(f"(no contacts in last {days}d)")
        return 0
    for line in out.strip().split("\n"):
        print(fmt_contact_row(line.split("\t")))
    return 0


def cmd_for_product(product: str, limit: int) -> int:
    out = psql(
        "SELECT first_seen_at, email, first_name, last_name, primary_source, "
        "primary_source_product, utm_first_source, status FROM contacts "
        f"WHERE primary_source_product = '{product}' "
        f"ORDER BY first_seen_at DESC LIMIT {limit}"
    )
    if not out.strip():
        print(f"(no contacts with primary_source_product='{product}')")
        return 0
    for line in out.strip().split("\n"):
        print(fmt_contact_row(line.split("\t")))
    return 0


def cmd_for_source(source: str, limit: int) -> int:
    out = psql(
        "SELECT first_seen_at, email, first_name, last_name, primary_source, "
        "primary_source_product, utm_first_source, status FROM contacts "
        f"WHERE primary_source = '{source}' "
        f"ORDER BY first_seen_at DESC LIMIT {limit}"
    )
    if not out.strip():
        print(f"(no contacts with primary_source='{source}')")
        return 0
    for line in out.strip().split("\n"):
        print(fmt_contact_row(line.split("\t")))
    return 0


def cmd_lookup(query: str, limit: int) -> int:
    q = query.replace("'", "''")
    out = psql(
        "SELECT first_seen_at, email, first_name, last_name, primary_source, "
        "primary_source_product, utm_first_source, status FROM contacts "
        f"WHERE email ILIKE '%{q}%' OR first_name ILIKE '%{q}%' OR last_name ILIKE '%{q}%' "
        f"ORDER BY first_seen_at DESC LIMIT {limit}"
    )
    if not out.strip():
        print(f"(no contacts matching '{query}')")
        return 0
    for line in out.strip().split("\n"):
        print(fmt_contact_row(line.split("\t")))
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="read_audience")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("summary")

    p_recent = sub.add_parser("recent")
    p_recent.add_argument("--days", type=int, default=7)
    p_recent.add_argument("--limit", type=int, default=50)

    p_prod = sub.add_parser("for-product")
    p_prod.add_argument("product")
    p_prod.add_argument("--limit", type=int, default=50)

    p_src = sub.add_parser("for-source")
    p_src.add_argument("source")
    p_src.add_argument("--limit", type=int, default=50)

    p_look = sub.add_parser("lookup")
    p_look.add_argument("query")
    p_look.add_argument("--limit", type=int, default=20)

    args = ap.parse_args(argv)
    if args.cmd == "summary":
        return cmd_summary()
    if args.cmd == "recent":
        return cmd_recent(args.days, args.limit)
    if args.cmd == "for-product":
        return cmd_for_product(args.product, args.limit)
    if args.cmd == "for-source":
        return cmd_for_source(args.source, args.limit)
    if args.cmd == "lookup":
        return cmd_lookup(args.query, args.limit)
    return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
