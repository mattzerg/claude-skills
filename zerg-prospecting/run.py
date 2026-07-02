#!/usr/bin/env python3
"""Zerg prospecting CLI for Durable-like Solutions accounts.

Stdlib-only. File-based. No outbound sends.
"""
from __future__ import annotations

import argparse
import datetime as dt
import re
import sys
from pathlib import Path

VAULT = Path("/Users/mattheweisner/Obsidian/Zerg/MattZerg")
GROWTH = VAULT / "Projects" / "Zerg-Production" / "Growth"
TARGETS_DIR = GROWTH / "target-accounts"
ACCOUNT_FILE = TARGETS_DIR / "durable-like.yaml"

# Segment → target-account file. `durable-like` is the original software track.
# `hardware-bcd` is the Series B/C/D hardware track (CesiumAstro reference pattern).
SEGMENT_FILES = {
    "durable-like": TARGETS_DIR / "durable-like.yaml",
    "hardware-bcd": TARGETS_DIR / "hardware-bcd.yaml",
}


def segment_file(segment: str) -> Path:
    """Resolve a --segment value to its target-account file path."""
    return SEGMENT_FILES.get(segment, ACCOUNT_FILE)


RUNS_DIR = GROWTH / "prospecting-runs"
PROSPECTS_FILE = GROWTH / "prospects.md"  # legacy bulk ledger (read-only after Phase 2)
PROSPECTS_DIR = GROWTH / "prospects"  # gtm-hub source of truth

WEIGHTS = {
    "durable_similarity": 35,
    "public_signal": 30,
    "urgency": 20,
    "offer_fit": 15,
}
SENDABILITY_WEIGHTS = {
    "route_quality": 30,
    "buyer_specificity": 25,
    "trigger_recency": 20,
    "message_relevance": 15,
    "company_size_fit": 10,
}
VALID_STAGES = {"inbound", "qualified", "scoped", "proposal-out", "won", "lost"}

SEED = """# Durable-like Zerg Solutions target accounts
#
# Scores are 1-5. The CLI normalizes weighted total to 100.
# Keep Durable itself as the reference pattern, not an outbound target.

- company: Durable
  slug: durable
  segment: ai-business-builder
  status: reference-pattern
  durable_similarity: 5
  public_signal: 5
  urgency: 4
  offer_fit: 5
  recommended_offer: zcloud-harness
  trigger_signals:
    - AI business builder with website, CRM, invoicing, and marketing surfaces
    - Distributed v2 platform and internal subservice orchestration pattern in local case-study notes
  likely_pain: Distributed platform/runtime visibility, migration, and agent-facing internal ops.
  offer_angle: Use only as internal proof pattern until Durable publication clearance is explicit.
  source_urls:
    - https://durable.com/
  outreach_paths:
    - Reference only. Do not send outbound to Durable without explicit publication/customer clearance.
  notes: Internal reference account. Do not draft outbound.

- company: Lovable
  slug: lovable
  segment: ai-app-builder
  status: research
  durable_similarity: 4
  public_signal: 5
  urgency: 4
  offer_fit: 4
  recommended_offer: custom-solutions
  trigger_signals:
    - AI app builder with generated full-stack app workflows
    - Likely complex project, deployment, and agent/runtime coordination surfaces
  likely_pain: Scaling generated-app workflows, agent task state, customer project operations, and internal orchestration.
  offer_angle: Agent-native product/platform workstream around generated-app lifecycle and internal ops.
  source_urls:
    - https://lovable.dev/
  outreach_paths:
    - Direct account-based outreach to platform, enterprise, security, partnerships, or operations leadership.
    - Use public product/security/enterprise pages for relevance before asking for any intro.
  notes: Strong category fit; no warm path required for priority.

- company: Bolt
  slug: bolt
  segment: ai-app-builder
  status: research
  durable_similarity: 4
  public_signal: 5
  urgency: 4
  offer_fit: 5
  recommended_offer: custom-solutions
  trigger_signals:
    - AI builder for apps, websites, and prototypes with Figma/GitHub import
    - Public positioning emphasizes design systems, enterprise backend infrastructure, hosting, databases, and integrations
  likely_pain: Scaling generated-app workflows into production infrastructure, enterprise controls, internal runtime coordination, and customer implementation ops.
  offer_angle: Agent-native product/platform workstream around productionizing generated apps and operationalizing complex customer projects.
  source_urls:
    - https://bolt.new/
  outreach_paths:
    - Direct account-based outreach to enterprise, product, platform, or partnerships leadership.
  notes: Highest non-network priority alongside Lovable because the public site already names enterprise and production infrastructure surfaces.

- company: Replit
  slug: replit
  segment: ai-dev-platform
  status: research
  durable_similarity: 4
  public_signal: 5
  urgency: 4
  offer_fit: 4
  recommended_offer: custom-solutions
  trigger_signals:
    - AI agent builds apps and websites from natural-language prompts
    - Public site emphasizes database, publish, integrations, enterprise security, and operations roles
  likely_pain: Agent workflow coordination, project state, deployment handoff, and internal customer-facing ops.
  offer_angle: Agent-native workflow infrastructure or Zergboard-backed project/runtime coordination.
  source_urls:
    - https://replit.com/ai
  outreach_paths:
    - Direct account-based outreach to operations, enterprise, product, or partnerships leadership.
  notes: Also appears in Product BD co-marketing list; keep Solutions motion separate.

- company: Glide
  slug: glide
  segment: ai-app-builder
  status: research
  durable_similarity: 3
  public_signal: 3
  urgency: 3
  offer_fit: 3
  recommended_offer: zergboard-rollout
  trigger_signals:
    - No-code app platform with AI/workflow use cases
    - Customer/project operations likely span many internal tools
  likely_pain: Internal workflow tracking, customer implementation ops, and AI-assisted delivery surfaces.
  offer_angle: Zergboard Rollout Sprint for agent-aware delivery and implementation operations.
  source_urls:
    - https://www.glideapps.com/
  outreach_paths:
    - Direct account-based outreach only after finding a current AI/agent implementation trigger.
  notes: Needs stronger trigger before outreach.

- company: Framer
  slug: framer
  segment: ai-website-builder
  status: research
  durable_similarity: 3
  public_signal: 4
  urgency: 3
  offer_fit: 3
  recommended_offer: custom-solutions
  trigger_signals:
    - AI website generation and web publishing workflows
    - Multi-surface customer/project lifecycle
  likely_pain: AI generation workflow ops, customer implementation tooling, and internal platform visibility.
  offer_angle: Custom agent-native product/platform workstream if a concrete platform trigger appears.
  source_urls:
    - https://www.framer.com/ai/
  outreach_paths:
    - Direct account-based outreach to AI, enterprise, or product leadership after trigger verification.
  notes: Good category adjacency; qualify for urgency before drafting.
"""


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")


def normalize(value: str) -> str:
    return slugify(value).replace("-", "")


def parse_scalar(raw: str):
    raw = raw.strip()
    if raw == "":
        return ""
    if raw.lower() in {"true", "false"}:
        return raw.lower() == "true"
    if re.fullmatch(r"-?\d+", raw):
        return int(raw)
    return raw.strip('"').strip("'")


def load_accounts(path: Path = ACCOUNT_FILE) -> list[dict]:
    if not path.exists():
        return []
    accounts: list[dict] = []
    current: dict | None = None
    current_list_key: str | None = None
    for raw in path.read_text().splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and not raw.startswith("    - "):
            if current:
                accounts.append(current)
            current = {}
            current_list_key = None
            item = stripped[2:]
            if ":" in item:
                key, value = item.split(":", 1)
                current[key.strip()] = parse_scalar(value)
            continue
        if current is None:
            continue
        if raw.startswith("  ") and not raw.startswith("    - ") and ":" in stripped:
            key, value = stripped.split(":", 1)
            key = key.strip()
            value = value.strip()
            if value == "":
                current[key] = []
                current_list_key = key
            else:
                current[key] = parse_scalar(value)
                current_list_key = None
            continue
        if raw.startswith("    - ") and current_list_key:
            current.setdefault(current_list_key, []).append(stripped[2:].strip())
    if current:
        accounts.append(current)
    return accounts


def dump_accounts(accounts: list[dict], path: Path = ACCOUNT_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Durable-like Zerg Solutions target accounts",
        "#",
        "# Scores are 1-5. The CLI normalizes weighted total to 100.",
        "# Keep Durable itself as the reference pattern, not an outbound target.",
        "",
    ]
    list_keys = {"trigger_signals", "source_urls", "outreach_paths", "network_paths"}
    preferred = [
        "company", "slug", "segment", "trigger_type", "status",
        "durable_similarity", "public_signal", "urgency", "offer_fit",
        "route_quality", "buyer_specificity", "trigger_recency", "message_relevance", "company_size_fit",
        "recommended_offer", "trigger_signals", "likely_pain",
        "offer_angle", "source_urls", "outreach_paths", "network_paths", "notes",
    ]
    for account in accounts:
        first = True
        for key in preferred:
            if key not in account:
                continue
            prefix = "- " if first else "  "
            first = False
            value = account[key]
            if key in list_keys:
                lines.append(f"{prefix}{key}:")
                for item in value or []:
                    lines.append(f"    - {item}")
            else:
                lines.append(f"{prefix}{key}: {value}")
        lines.append("")
    path.write_text("\n".join(lines).rstrip() + "\n")


def score_account(account: dict) -> int:
    total = 0
    for key, weight in WEIGHTS.items():
        value = int(account.get(key, 0) or 0)
        value = max(0, min(5, value))
        total += value * weight
    return round(total / 5)


def score_sendability(account: dict) -> int:
    total = 0
    for key, weight in SENDABILITY_WEIGHTS.items():
        value = int(account.get(key, 0) or 0)
        value = max(0, min(5, value))
        total += value * weight
    return round(total / 5)


def find_account(name: str, accounts: list[dict]) -> dict | None:
    needle = normalize(name)
    for account in accounts:
        candidates = [account.get("company", ""), account.get("slug", "")]
        if any(normalize(str(c)) == needle for c in candidates):
            return account
    return None


def ensure_seed(path: Path = ACCOUNT_FILE) -> None:
    if path.exists():
        return
    # Only the original durable-like file has a built-in SEED. Other segment
    # files (e.g. hardware-bcd) are authored directly and must already exist.
    if path != ACCOUNT_FILE:
        print(
            f"ERROR: account file not found: {path}. "
            "Author the segment file before scoring.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(SEED)


def render_account(account: dict) -> str:
    score = score_account(account)
    sendability = score_sendability(account)
    lines = [
        f"# {account.get('company')} Prospect Brief",
        "",
        f"- **Score:** {score}/100",
        f"- **Sendability:** {sendability}/100",
        f"- **Segment:** {account.get('segment', '')}",
        f"- **Trigger type:** {account.get('trigger_type', '')}",
        f"- **Status:** {account.get('status', '')}",
        f"- **Recommended offer:** {account.get('recommended_offer', '')}",
        f"- **Likely pain:** {account.get('likely_pain', '')}",
        f"- **Offer angle:** {account.get('offer_angle', '')}",
        "",
        "## Trigger Signals",
    ]
    for signal in account.get("trigger_signals", []) or []:
        lines.append(f"- {signal}")
    lines.extend(["", "## Sources"])
    for url in account.get("source_urls", []) or []:
        lines.append(f"- {url}")
    lines.extend(["", "## Outreach Paths"])
    for path in account.get("outreach_paths", account.get("network_paths", [])) or []:
        lines.append(f"- {path}")
    lines.extend(["", "## Notes", str(account.get("notes", ""))])
    return "\n".join(lines).rstrip() + "\n"


def write_run_file(account: dict, kind: str, body: str) -> Path:
    RUNS_DIR.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    path = RUNS_DIR / f"{today}-{account.get('slug', slugify(account.get('company', 'account')))}-{kind}.md"
    path.write_text(body)
    return path


def cmd_seed(args: argparse.Namespace) -> int:
    if args.segment not in SEGMENT_FILES:
        print(
            f"ERROR: unknown --segment {args.segment}; "
            f"choose from {sorted(SEGMENT_FILES)}",
            file=sys.stderr,
        )
        return 1
    path = segment_file(args.segment)
    if args.segment != "durable-like":
        # Authored segments are not auto-seeded; just report existence.
        print(("Exists" if path.exists() else "Missing (author it)") + f": {path}")
        return 0
    created = not path.exists()
    ensure_seed(path)
    print(("Created" if created else "Exists") + f": {path}")
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    path = segment_file(args.segment)
    ensure_seed(path)
    accounts = load_accounts(path)
    ranked = sorted(accounts, key=score_account, reverse=True)
    print(f"{'Score':<6} {'Company':<24} {'Offer':<18} {'Trigger':<24} Segment")
    print("-" * 104)
    for account in ranked:
        score = score_account(account)
        if score < args.min_score:
            continue
        print(
            f"{score:<6} {str(account.get('company', '')):<24} "
            f"{str(account.get('recommended_offer', '')):<18} "
            f"{str(account.get('trigger_type', '')):<24} {account.get('segment', '')}"
        )
    return 0


def cmd_sendability(args: argparse.Namespace) -> int:
    path = segment_file(args.segment)
    ensure_seed(path)
    accounts = load_accounts(path)
    ranked = sorted(accounts, key=score_sendability, reverse=True)
    print(f"{'Send':<6} {'Fit':<6} {'Company':<24} {'Route':<6} {'Buyer':<6} {'Trigger':<8} {'Status':<16} Next")
    print("-" * 118)
    for account in ranked:
        sendability = score_sendability(account)
        if sendability < args.min_score:
            continue
        print(
            f"{sendability:<6} {score_account(account):<6} {str(account.get('company', '')):<24} "
            f"{int(account.get('route_quality', 0) or 0):<6} "
            f"{int(account.get('buyer_specificity', 0) or 0):<6} "
            f"{int(account.get('trigger_recency', 0) or 0):<8} "
            f"{str(account.get('status', '')):<16} {account.get('notes', '')}"
        )
    return 0


def cmd_enrich(args: argparse.Namespace) -> int:
    path = segment_file(args.segment)
    ensure_seed(path)
    account = find_account(args.company, load_accounts(path))
    if not account:
        print(f"ERROR: account not found: {args.company}", file=sys.stderr)
        return 1
    body = render_account(account)
    path = write_run_file(account, "brief", body)
    print(path)
    return 0


def draft_body(account: dict, segment: str = "durable-like") -> str:
    company = account.get("company", "")
    first_source = (account.get("source_urls") or [""])[0]
    relevance = (account.get("trigger_signals") or [""])[0]
    angle = account.get("offer_angle", "")
    offer = account.get("recommended_offer", "")
    # Skeleton only — final copy comes from fakematt-email. The hardware
    # variant frames the wedge as software management/migration/efficiency
    # and hardware optimization, not the software "agent ops" framing.
    if segment == "hardware-bcd":
        cohort = "hardware and deep-tech teams"
        wedge = (
            "We help hardware companies with the software side of the business: "
            "modernizing and migrating internal tooling, making the runtime/cloud "
            "they depend on efficient, and building the program, supply-chain, and "
            "ops software that lets the hardware move faster."
        )
        owner_line = "engineering, software, or program-ops"
    else:
        cohort = "AI SaaS/platform teams"
        wedge = "Zerg ships code against scoped platform and ops outcomes, not a deck."
        owner_line = "platform, ops, or product"
    return f"""# Outreach Draft — {company}

**Score:** {score_account(account)}/100
**Segment:** {segment}
**Recommended offer:** {offer}
**Source to verify before send:** {first_source}

## First Touch

Subject: {company} <> Zerg

{{target_first_name}},

I'm building a short list of {cohort} where Zerg's Solutions work may be relevant. One signal on {company}: {relevance}.

The relevant workstream is {offer}: {angle} {wedge}

Worth a 30-minute scoping call next week? If it is not a fit, I will say so quickly.

Matt

## Follow-Up

Subject: Zerg <> {company}

{{target_first_name}},

Quick follow-up on this. The specific reason I had {company} on the list was: {relevance}.

If the right owner is someone else on {owner_line}, happy to route there instead.

Matt
"""


def cmd_draft(args: argparse.Namespace) -> int:
    path = segment_file(args.segment)
    ensure_seed(path)
    account = find_account(args.company, load_accounts(path))
    if not account:
        print(f"ERROR: account not found: {args.company}", file=sys.stderr)
        return 1
    score = score_account(account)
    if score < args.min_score and not args.force:
        print(
            f"ERROR: score {score} is below drafting threshold {args.min_score}. "
            "Use --force if Matt explicitly wants a draft.",
            file=sys.stderr,
        )
        return 1
    if account.get("status") == "reference-pattern" and not args.force:
        print("ERROR: reference-pattern accounts are not outbound targets. Use --force only for internal drafts.", file=sys.stderr)
        return 1
    body = draft_body(account, args.segment)
    path = write_run_file(account, "draft", body)
    print(path)
    return 0


def prospects_has_company(company: str) -> bool:
    """True if a prospect entity already exists in Growth/prospects/."""
    if not PROSPECTS_DIR.exists():
        return False
    target = normalize(company)
    for f in PROSPECTS_DIR.glob("*.md"):
        if f.name.startswith("_"):
            continue
        head = f.read_text(encoding="utf-8")[:2048]
        if f"\ncompany: {company}\n" in head or f"\ntitle: {company}\n" in head:
            return True
        if normalize(f.stem) == target:
            return True
    return False


def _render_prospect_entity(account: dict, stage: str, today: str) -> tuple[str, str]:
    """Return (slug, full_file_text) for a gtm-hub-compliant prospect entity."""
    company = account["company"]
    slug = account.get("slug") or slugify(company)
    source = "zerg-prospecting-public-signal"
    score = score_account(account)
    category = account.get("segment") or account.get("trigger_type") or ""
    next_step = "verify current public trigger + identify direct buyer"
    notes = "; ".join(
        x for x in [
            account.get("segment", ""),
            account.get("trigger_type", ""),
            f"score {score}/100",
            account.get("recommended_offer", ""),
            account.get("likely_pain", ""),
        ] if x
    )
    lines = [
        "---",
        f"id: {slug}",
        "type: prospect",
        f"title: {company}",
        f"status: {stage}",
        "owner: matt",
        f"created: {today}",
        f"last_touch: {today}",
        f"company: {company}",
        f"source: {source}",
        f"score: {score}",
        f"category: {category}" if category else "category:",
        "referrer:",
        f'next_action: "{next_step}"',
        f'notes: "{notes}"',
        "---",
        "",
        f"# {company}",
        "",
        notes or "_(no notes)_",
        "",
    ]
    return slug, "\n".join(lines)


def cmd_export(args: argparse.Namespace) -> int:
    if args.stage not in VALID_STAGES:
        print(f"ERROR: --stage must be one of {sorted(VALID_STAGES)}", file=sys.stderr)
        return 1
    path = segment_file(args.segment)
    ensure_seed(path)
    account = find_account(args.company, load_accounts(path))
    if not account:
        print(f"ERROR: account not found: {args.company}", file=sys.stderr)
        return 1
    if prospects_has_company(account["company"]):
        print(f"Exists in Growth/prospects/: {account['company']}")
        return 0
    today = dt.date.today().isoformat()
    slug, text = _render_prospect_entity(account, args.stage, today)
    PROSPECTS_DIR.mkdir(parents=True, exist_ok=True)
    (PROSPECTS_DIR / f"{slug}.md").write_text(text, encoding="utf-8")
    print(f"Wrote Growth/prospects/{slug}.md ({args.stage})")
    print("Run `gtm-hub regenerate` to refresh the canonical README.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="zerg-prospecting", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    seed = sub.add_parser("seed")
    seed.add_argument("--segment", default="durable-like")
    seed.set_defaults(func=cmd_seed)

    score = sub.add_parser("score")
    score.add_argument("--segment", default="durable-like")
    score.add_argument("--min-score", type=int, default=0)
    score.set_defaults(func=cmd_score)

    sendability = sub.add_parser("sendability")
    sendability.add_argument("--segment", default="durable-like")
    sendability.add_argument("--min-score", type=int, default=0)
    sendability.set_defaults(func=cmd_sendability)

    enrich = sub.add_parser("enrich")
    enrich.add_argument("company")
    enrich.add_argument("--segment", default="durable-like")
    enrich.set_defaults(func=cmd_enrich)

    draft = sub.add_parser("draft")
    draft.add_argument("company")
    draft.add_argument("--segment", default="durable-like")
    draft.add_argument("--min-score", type=int, default=70)
    draft.add_argument("--force", action="store_true")
    draft.set_defaults(func=cmd_draft)

    export = sub.add_parser("export")
    export.add_argument("company")
    export.add_argument("--segment", default="durable-like")
    export.add_argument("--stage", default="inbound")
    export.set_defaults(func=cmd_export)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
