#!/usr/bin/env python3
"""Email drip skill — Stream A (lifecycle) scaffolder.

Usage:
    python3 ~/.claude/skills/email-drip/run.py init <slug>
    python3 ~/.claude/skills/email-drip/run.py scaffold <slug> [--force]
    python3 ~/.claude/skills/email-drip/run.py audit <slug>
    python3 ~/.claude/skills/email-drip/run.py list
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

import yaml

DEFAULT_VAULT = "/Users/mattheweisner/Obsidian/Zerg/MattZerg"
VAULT = Path(os.environ.get("ZERG_VAULT", DEFAULT_VAULT))
GROWTH_DIR = VAULT / "Projects" / "Zerg-Production" / "Growth"
LIFECYCLE_DIR = GROWTH_DIR / "lifecycle"
TEMPLATE_YAML = LIFECYCLE_DIR / "_drip-template.yaml"
BACKLOG_DIR = GROWTH_DIR / "launch-backlog"
MEASUREMENT_DIR = GROWTH_DIR / "measurement"

EXPECTED_EMAILS = ["welcome", "aha_nudge", "trial_day_3", "trial_day_7", "post_pro_onboarding"]

BODIES = {
    "welcome": """Hi {{first_name}},

Welcome to {{PRODUCT_NAME}}. You signed up because you wanted a faster path to the work that actually matters — this email is the orientation, and there's one thing to try in the next five minutes.

## The 5-minute thing

Open {{PRODUCT_NAME}} and complete the first core action. That single step is what separates accounts that stick from accounts that drift. We measure it, and we'll know when you hit it.

## What's next

- Tomorrow: a nudge with a concrete example if you haven't hit the aha moment yet.
- Day 3: one usage tip from how other operators use it.
- Day 7: a check-in — reply directly with what's working and what isn't.

— Matt
""",
    "aha_nudge": """Hi {{first_name}},

You signed up for {{PRODUCT_NAME}} yesterday and haven't hit the core action yet. No judgement — most products bury the value behind ten clicks. {{PRODUCT_NAME}} doesn't, but it's still on you to take the first swing.

## Try this

Pick a real task you'd normally handle manually. Open {{PRODUCT_NAME}}. Run it through the primary flow. You should hit the aha moment in under three minutes.

If you don't, reply to this email and tell me where you got stuck. I read every reply.

— Matt
""",
    "trial_day_3": """Hi {{first_name}},

Three days into {{PRODUCT_NAME}}. Quick check-in plus one tip.

## The tip

Most operators miss this: {{PRODUCT_NAME}} works best when you wire it into the surface you already live in — your dashboard, your inbox, your IDE. Open one, anchor {{PRODUCT_NAME}} next to it, and let muscle memory do the rest.

## How's it going?

If something's clunky or confusing, reply and tell me. We ship fixes fast when real users surface them.

— Matt
""",
    "trial_day_7": """Hi {{first_name}},

One week in with {{PRODUCT_NAME}}. Worth a pause to ask: is it earning a spot in your workflow, or is it sitting on the shelf?

## Reply with feedback

I'd genuinely like to know:

1. What's the one thing that worked best?
2. What's the one thing that frustrated you?
3. Would you miss {{PRODUCT_NAME}} if it disappeared tomorrow?

Hit reply. Short answers are fine. The honest ones help most.

— Matt
""",
    "post_pro_onboarding": """Hi {{first_name}},

Welcome to {{PRODUCT_NAME}} Pro. Your payment went through and the upgraded features are live on your account.

## What unlocks now

Pro flips on the gated capabilities you saw locked in the free tier. The biggest one is the workflow you were already using — now without the rate limit. Re-run it and you'll feel the difference immediately.

## Receipt + billing

Your payment confirmation is in a separate email from our billing provider. If anything looks off, reply here and I'll sort it directly.

— Matt
""",
}

PURPOSES = {
    "welcome": "orientation + one specific action",
    "aha_nudge": "nudge toward the aha action with a concrete example",
    "trial_day_3": "one usage tip + check-in",
    "trial_day_7": "one-week-in reflection + ask for reply with feedback",
    "post_pro_onboarding": "congrats + Pro feature pointer + payment confirmation reference",
}

PREHEADERS = {
    "welcome": "Quick orientation — and one thing to try in the next 5 minutes.",
    "aha_nudge": "You signed up yesterday. Here's the concrete thing to try.",
    "trial_day_3": "Day 3 check-in plus one operator tip.",
    "trial_day_7": "One week in. Reply with the honest answer.",
    "post_pro_onboarding": "Pro is live on your account. Here's what unlocks.",
}


class DripError(Exception):
    pass


def load_yaml(path: Path) -> dict:
    with path.open() as f:
        return yaml.safe_load(f) or {}


def read_backlog_product_name(slug: str) -> str:
    candidates = list(BACKLOG_DIR.glob("*.md"))
    for f in candidates:
        text = f.read_text()
        if not text.startswith("---\n"):
            continue
        end = text.find("\n---\n", 4)
        if end < 0:
            continue
        try:
            fm = yaml.safe_load(text[4:end]) or {}
        except yaml.YAMLError:
            continue
        if fm.get("slug") == slug:
            name = fm.get("product_name")
            if name:
                return str(name)
    return slug.replace("-", " ").title()


def cmd_init(args: argparse.Namespace) -> int:
    slug = args.slug
    target = LIFECYCLE_DIR / f"{slug}.yaml"
    if target.exists():
        print(f"SKIP: {target} already exists")
        return 0
    if not TEMPLATE_YAML.exists():
        print(f"ERROR: template not found at {TEMPLATE_YAML}", file=sys.stderr)
        return 1
    raw = TEMPLATE_YAML.read_text()
    rendered = raw.replace("PLACEHOLDER_SLUG", slug)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(rendered)
    product_name = read_backlog_product_name(slug)
    print(f"INIT: wrote {target}")
    print(f"      product_name resolved from launch-backlog: {product_name}")
    print(f"      next: edit {target.name} to confirm subjects/triggers, then run `scaffold {slug}`")
    return 0


def render_template(email_id: str, product_name: str, slug: str, success_event: str,
                    subject_template: str, trigger: str, delay: int) -> str:
    body = BODIES[email_id].replace("{{PRODUCT_NAME}}", product_name)
    subject = subject_template.replace("{{PRODUCT_NAME}}", product_name)
    preheader = PREHEADERS[email_id]
    purpose = PURPOSES[email_id]
    campaign = f"{slug}-stream-a-{email_id.replace('_', '-')}"
    fm_lines = [
        "---",
        f"email_id: {email_id}",
        f"trigger: {trigger}",
        f"delay_minutes: {delay}",
        f'subject: "{subject}"',
        f'preheader: "{preheader}"',
        f"success_event: {success_event}",
        "utm_source: email",
        "utm_medium: lifecycle",
        f"utm_campaign: {campaign}",
        f"purpose: {purpose}",
        "---",
    ]
    header = f"# {subject}"
    return "\n".join(fm_lines) + "\n\n" + header + "\n\n" + body


def cmd_scaffold(args: argparse.Namespace) -> int:
    slug = args.slug
    config_path = LIFECYCLE_DIR / f"{slug}.yaml"
    if not config_path.exists():
        print(f"ERROR: drip config not found at {config_path}. Run `init {slug}` first.", file=sys.stderr)
        return 1
    try:
        config = load_yaml(config_path)
    except yaml.YAMLError as e:
        print(f"ERROR: failed to parse {config_path}: {e}", file=sys.stderr)
        return 2
    product_name = read_backlog_product_name(slug)
    out_dir = LIFECYCLE_DIR / slug / "templates"
    out_dir.mkdir(parents=True, exist_ok=True)
    emails = config.get("emails", [])
    written = 0
    skipped = 0
    for entry in emails:
        email_id = entry.get("id")
        if email_id not in BODIES:
            print(f"WARN: unknown email id {email_id!r} in {config_path}; skipping")
            continue
        filename = email_id.replace("_", "-") + ".md"
        target = out_dir / filename
        if target.exists() and not args.force:
            print(f"SKIP: {target} (use --force to overwrite)")
            skipped += 1
            continue
        rendered = render_template(
            email_id=email_id,
            product_name=product_name,
            slug=slug,
            success_event=str(entry.get("success_event", "email_open")),
            subject_template=str(entry.get("subject_template", f"Update from {product_name}")),
            trigger=str(entry.get("trigger", f"{slug}_signup")),
            delay=int(entry.get("delay", 0)),
        )
        target.write_text(rendered)
        print(f"WROTE: {target}")
        written += 1
    print(f"\nScaffold complete: {written} written, {skipped} skipped (out of {len(emails)} configured).")
    return 0


def parse_frontmatter(text: str) -> dict:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---\n", 4)
    if end < 0:
        return {}
    try:
        return yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return {}


def collect_measurement_events(slug: str) -> set:
    path = MEASUREMENT_DIR / f"{slug}.yaml"
    events: set = set()
    if not path.exists():
        return events
    try:
        data = load_yaml(path)
    except yaml.YAMLError:
        return events
    for entry in data.get("required_events", []) or []:
        if isinstance(entry, dict) and "name" in entry:
            events.add(str(entry["name"]))
        elif isinstance(entry, str):
            events.add(entry)
    for entry in data.get("optional_events", []) or []:
        if isinstance(entry, str):
            events.add(entry)
        elif isinstance(entry, dict) and "name" in entry:
            events.add(str(entry["name"]))
    events.update({"email_open", "email_click", "email_reply", "pro_feature_used"})
    return events


def cmd_audit(args: argparse.Namespace) -> int:
    slug = args.slug
    out_dir = LIFECYCLE_DIR / slug / "templates"
    findings: list[tuple[str, str, str]] = []

    if not out_dir.exists():
        findings.append(("HIGH", "A1", f"templates directory missing: {out_dir}"))

    canonical_events = collect_measurement_events(slug)
    measurement_present = (MEASUREMENT_DIR / f"{slug}.yaml").exists()

    for email_id in EXPECTED_EMAILS:
        filename = email_id.replace("_", "-") + ".md"
        path = out_dir / filename
        if not path.exists():
            findings.append(("HIGH", "A1", f"missing template: {filename}"))
            continue
        text = path.read_text()
        fm = parse_frontmatter(text)
        subject = str(fm.get("subject", ""))
        if not subject or re.search(r"TODO|\{\{|<.+?>", subject):
            findings.append(("HIGH", "A2", f"{filename}: subject is placeholder or empty: {subject!r}"))
        success_event = str(fm.get("success_event", ""))
        if measurement_present and success_event and success_event not in canonical_events:
            findings.append(("HIGH", "A3",
                             f"{filename}: success_event {success_event!r} not in measurement/{slug}.yaml"))
        elif not measurement_present and success_event:
            findings.append(("MED", "A3",
                             f"{filename}: measurement/{slug}.yaml missing — cannot verify success_event {success_event!r}"))
        campaign = str(fm.get("utm_campaign", ""))
        if not campaign.startswith(f"{slug}-stream-a-"):
            findings.append(("MED", "A4",
                             f"{filename}: utm_campaign {campaign!r} missing slug-stream-a- prefix"))
        body = text.split("\n---\n", 1)[1] if "\n---\n" in text else text
        if re.search(r"\bTODO\b|\bFIXME\b", body):
            findings.append(("MED", "A5", f"{filename}: body contains TODO/FIXME"))

    if not findings:
        print(f"AUDIT OK: {slug} — all 5 templates present, subjects rendered, events bound.")
        return 0

    print(f"AUDIT findings for {slug}:")
    for severity, rule, msg in sorted(findings, key=lambda f: ("HIGH MED LOW".split().index(f[0]), f[1])):
        print(f"  [{severity}] {rule}: {msg}")
    high = sum(1 for f in findings if f[0] == "HIGH")
    return 1 if high else 0


def cmd_list(args: argparse.Namespace) -> int:
    if not LIFECYCLE_DIR.exists():
        print("(no lifecycle directory)")
        return 0
    configs = sorted(p for p in LIFECYCLE_DIR.glob("*.yaml") if not p.name.startswith("_"))
    if not configs:
        print("(no per-product drip configs found)")
        return 0
    print("| Slug | Stream | Emails | Templates dir |")
    print("|---|---|---|---|")
    for f in configs:
        try:
            data = load_yaml(f)
        except yaml.YAMLError:
            print(f"| {f.stem} | (parse error) | — | — |")
            continue
        slug = data.get("product", f.stem)
        stream = data.get("stream", "?")
        n_emails = len(data.get("emails", []) or [])
        tdir = LIFECYCLE_DIR / slug / "templates"
        tdir_status = "yes" if tdir.exists() else "missing"
        print(f"| {slug} | {stream} | {n_emails} | {tdir_status} |")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(prog="email-drip", description=__doc__)
    sub = p.add_subparsers(dest="cmd", required=True)

    pi = sub.add_parser("init", help="copy template to per-product drip YAML")
    pi.add_argument("slug")
    pi.set_defaults(func=cmd_init)

    ps = sub.add_parser("scaffold", help="render 5 Stream A email markdown templates")
    ps.add_argument("slug")
    ps.add_argument("--force", action="store_true")
    ps.set_defaults(func=cmd_scaffold)

    pa = sub.add_parser("audit", help="verify templates + canonical event bindings")
    pa.add_argument("slug")
    pa.set_defaults(func=cmd_audit)

    pl = sub.add_parser("list", help="list per-product Stream A configs")
    pl.set_defaults(func=cmd_list)

    args = p.parse_args()
    try:
        return args.func(args)
    except DripError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
