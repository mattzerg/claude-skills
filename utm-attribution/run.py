#!/usr/bin/env python3
"""UTM attribution skill — build + validate UTM-instrumented links for Zerg properties.

Usage:
    python3 ~/.claude/skills/utm-attribution/run.py build \\
        --destination URL --source S --medium M --campaign C [--content X] [--term T]
    python3 ~/.claude/skills/utm-attribution/run.py validate URL
    python3 ~/.claude/skills/utm-attribution/run.py ledger  (prints recent rows)

Hard-fails when destination is not on a Zerg domain or when required fields are missing.
Appends every built link to MattZerg/Projects/Zerg-Production/Growth/links.md (canonical ledger).

Convention source: MattZerg/Projects/Zerg-Production/Growth/utm-convention.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path
from urllib.parse import quote, urlencode, urlparse, parse_qs

VAULT = Path("/Users/mattheweisner/Obsidian/Zerg/MattZerg")
GROWTH_DIR = VAULT / "Projects" / "Zerg-Production" / "Growth"
CONVENTION_FILE = GROWTH_DIR / "utm-convention.md"
LEDGER_FILE = GROWTH_DIR / "links.md"

ZERG_DOMAINS = {
    "zergai.com", "www.zergai.com",
    "zergboard.ai", "www.zergboard.ai",
    "zerglytics.fly.dev",
    "zergboard-preview.pages.dev",
}
ZERG_DOMAIN_SUFFIXES = (".zergai.com",)

ALLOWED_MEDIUMS = {
    "social", "email", "community", "pr", "paid-social", "paid-search",
    "partner", "referral", "organic-search", "direct", "webinar",
}

KEBAB_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
PII_PATTERN = re.compile(r"[@\s]")


class UTMError(Exception):
    pass


def is_zerg_domain(url: str) -> bool:
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    if host in ZERG_DOMAINS:
        return True
    return any(host.endswith(s) for s in ZERG_DOMAIN_SUFFIXES)


def kebab_check(value: str, field: str) -> None:
    if not KEBAB_PATTERN.match(value):
        raise UTMError(f"{field}={value!r}: must be lowercase kebab-case ([a-z0-9-])")
    if PII_PATTERN.search(value):
        raise UTMError(f"{field}={value!r}: contains @ or whitespace (possible PII)")


def parse_campaign_catalog() -> set[str]:
    """Parse campaign catalog from utm-convention.md. Returns set of known campaign slugs."""
    if not CONVENTION_FILE.exists():
        return set()
    txt = CONVENTION_FILE.read_text()
    campaigns: set[str] = set()
    in_catalog = False
    for line in txt.splitlines():
        if "Campaign catalog" in line:
            in_catalog = True
            continue
        if in_catalog and line.startswith("##") and "catalog" not in line.lower():
            break
        # Match ` - `slug` — desc` style lines
        m = re.match(r"^\s*-\s*`([a-z0-9-]+)`", line)
        if m:
            campaigns.add(m.group(1))
    return campaigns


def build_url(destination: str, source: str, medium: str, campaign: str,
              content: str | None, term: str | None,
              register_campaign: bool, register_source: bool) -> str:
    if not is_zerg_domain(destination):
        raise UTMError(
            f"destination {destination!r} is not a Zerg domain. "
            f"Zerg domains: {sorted(ZERG_DOMAINS)} or *{ZERG_DOMAIN_SUFFIXES}. "
            f"External destinations should NOT be UTM-instrumented (we don't track outbound)."
        )

    for field, value in [("source", source), ("medium", medium), ("campaign", campaign)]:
        if not value:
            raise UTMError(f"--{field} is required")
        kebab_check(value, field)

    if medium not in ALLOWED_MEDIUMS:
        raise UTMError(f"medium={medium!r} not in allowed set {sorted(ALLOWED_MEDIUMS)}")

    catalog = parse_campaign_catalog()
    if catalog and campaign not in catalog and not register_campaign:
        raise UTMError(
            f"campaign={campaign!r} not in catalog. "
            f"Add it to utm-convention.md OR pass --register-campaign to add it on the fly."
        )

    if content:
        kebab_check(content, "content")
    if term:
        kebab_check(term, "term")

    params: dict[str, str] = {
        "utm_source": source,
        "utm_medium": medium,
        "utm_campaign": campaign,
    }
    if content:
        params["utm_content"] = content
    if term:
        params["utm_term"] = term

    sep = "&" if "?" in destination else "?"
    return f"{destination}{sep}{urlencode(params, quote_via=quote)}"


def append_ledger(date_str: str, campaign: str, source: str, medium: str,
                  content: str | None, destination: str, full_url: str) -> None:
    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not LEDGER_FILE.exists():
        # write header
        LEDGER_FILE.write_text(
            "# UTM Links Ledger\n\nAuto-appended by utm-attribution skill.\n\n"
            "| Date | Campaign | Source | Medium | Content | Destination | Full URL |\n"
            "|---|---|---|---|---|---|---|\n"
        )
    row = f"| {date_str} | {campaign} | {source} | {medium} | {content or ''} | {destination} | {full_url} |\n"
    with LEDGER_FILE.open("a") as f:
        f.write(row)


def validate_url(url: str) -> dict[str, list[str]]:
    """Returns {'errors': [...], 'warnings': [...], 'parsed': {...}}."""
    errors: list[str] = []
    warnings: list[str] = []
    if not is_zerg_domain(url):
        errors.append(f"not a Zerg domain: {urlparse(url).netloc}")
    qs = parse_qs(urlparse(url).query)
    parsed = {k: v[0] if v else "" for k, v in qs.items()}
    for required in ("utm_source", "utm_medium", "utm_campaign"):
        if not parsed.get(required):
            errors.append(f"missing required param: {required}")
    if parsed.get("utm_medium") and parsed["utm_medium"] not in ALLOWED_MEDIUMS:
        errors.append(f"utm_medium={parsed['utm_medium']!r} not in allowed set")
    catalog = parse_campaign_catalog()
    if catalog and parsed.get("utm_campaign") and parsed["utm_campaign"] not in catalog:
        warnings.append(f"utm_campaign={parsed['utm_campaign']!r} not in catalog")
    return {"errors": errors, "warnings": warnings, "parsed": parsed}


def cmd_build(args: argparse.Namespace) -> int:
    try:
        url = build_url(
            destination=args.destination,
            source=args.source,
            medium=args.medium,
            campaign=args.campaign,
            content=args.content,
            term=args.term,
            register_campaign=args.register_campaign,
            register_source=args.register_source,
        )
    except UTMError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    if not args.no_log:
        append_ledger(
            date_str=dt.date.today().isoformat(),
            campaign=args.campaign,
            source=args.source,
            medium=args.medium,
            content=args.content,
            destination=args.destination,
            full_url=url,
        )
    print(url)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    result = validate_url(args.url)
    if result["errors"]:
        for e in result["errors"]:
            print(f"ERROR: {e}", file=sys.stderr)
        return 2
    if result["warnings"]:
        for w in result["warnings"]:
            print(f"WARN: {w}", file=sys.stderr)
    print("OK")
    return 0


def cmd_ledger(args: argparse.Namespace) -> int:
    if not LEDGER_FILE.exists():
        print("(ledger empty — no links generated yet)")
        return 0
    txt = LEDGER_FILE.read_text()
    lines = txt.splitlines()
    rows = [ln for ln in lines if ln.startswith("|") and not ln.startswith("|---")]
    last = rows[-args.tail :] if args.tail else rows
    print("\n".join(last))
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="utm-attribution", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pb = sub.add_parser("build", help="build a UTM-instrumented URL")
    pb.add_argument("--destination", required=True, help="full URL on a Zerg domain")
    pb.add_argument("--source", required=True, help="utm_source (kebab-case)")
    pb.add_argument("--medium", required=True, help=f"utm_medium ({'/'.join(sorted(ALLOWED_MEDIUMS))})")
    pb.add_argument("--campaign", required=True, help="utm_campaign (must match catalog or use --register-campaign)")
    pb.add_argument("--content", help="utm_content (variant tag)")
    pb.add_argument("--term", help="utm_term (paid search keyword)")
    pb.add_argument("--register-campaign", action="store_true", help="bypass campaign catalog check")
    pb.add_argument("--register-source", action="store_true", help="bypass source catalog check (Phase 1: no-op)")
    pb.add_argument("--no-log", action="store_true", help="don't append to links.md ledger")
    pb.set_defaults(func=cmd_build)

    pv = sub.add_parser("validate", help="validate an existing URL")
    pv.add_argument("url", help="URL to validate")
    pv.set_defaults(func=cmd_validate)

    pl = sub.add_parser("ledger", help="show recent ledger rows")
    pl.add_argument("--tail", type=int, default=20, help="number of rows from the end (default: 20, 0 = all)")
    pl.set_defaults(func=cmd_ledger)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
