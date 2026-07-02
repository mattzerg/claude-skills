#!/usr/bin/env python3
import argparse
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml

HOME = Path.home()
TEMPLATE_DIR = HOME / "zerg" / "_templates" / "zerg-product" / "product-docs"
VAULT = HOME / "Obsidian" / "Zerg"
DEFAULT_BACKLOG_DIR = VAULT / "MattZerg" / "Projects" / "Zerg-Production" / "Growth" / "launch-backlog"

CANONICAL_H2 = [
    "What it is",
    "Quick start",
    "Concepts",
    "API",
    "Frontend",
    "Status",
]

CANONICAL_SIBLINGS = [
    "getting-started.md",
    "architecture.md",
    "what-can-i-build.md",
    "api-backend.md",
    "web-frontend.md",
    "faq.md",
    "changelog.md",
]

TOKEN_FIELDS = [
    ("{{PRODUCT_SLUG}}", "slug"),
    ("{{PRODUCT_NAME}}", "name"),
    ("{{PRODUCT_DOMAIN}}", "domain"),
    ("{{PRODUCT_TAGLINE}}", "tagline"),
    ("{{PRODUCT_DESCRIPTION}}", "description"),
]


def load_backlog_frontmatter(path: Path) -> dict:
    if not path.exists():
        return {}
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if not match:
        return {}
    try:
        return yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError:
        return {}


def substitute_tokens(text: str, tokens: dict) -> str:
    for token, key in TOKEN_FIELDS:
        text = text.replace(token, str(tokens.get(key, "")))
    return text


def cmd_scaffold(args) -> int:
    slug = args.slug
    backlog_path = Path(args.from_backlog) if args.from_backlog else DEFAULT_BACKLOG_DIR / f"{slug}.md"
    target = HOME / "zerg" / slug / "docs"

    if not TEMPLATE_DIR.exists():
        print(f"ERROR: template dir not found: {TEMPLATE_DIR}", file=sys.stderr)
        return 2

    frontmatter = load_backlog_frontmatter(backlog_path)
    tokens = {
        "slug": slug,
        "name": frontmatter.get("name", slug),
        "domain": frontmatter.get("domain", f"{slug}.zerg.com"),
        "tagline": frontmatter.get("tagline", ""),
        "description": frontmatter.get("description", ""),
    }

    target.mkdir(parents=True, exist_ok=True)
    created = []
    skipped = []

    for src in TEMPLATE_DIR.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(TEMPLATE_DIR)
        dest = target / rel
        if dest.exists():
            skipped.append(str(dest))
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        if src.suffix in {".md", ".txt", ".json", ".yaml", ".yml"}:
            content = src.read_text(encoding="utf-8")
            dest.write_text(substitute_tokens(content, tokens), encoding="utf-8")
        else:
            shutil.copy2(src, dest)
        created.append(str(dest))

    print(f"scaffold: slug={slug} target={target}")
    print(f"backlog={backlog_path} {'(found)' if backlog_path.exists() else '(missing — defaults used)'}")
    print(f"created ({len(created)}):")
    for p in created:
        print(f"  + {p}")
    if skipped:
        print(f"skipped ({len(skipped)} — already exist):")
        for p in skipped:
            print(f"  = {p}")
    return 0


def check_d1(docs_dir: Path) -> dict | None:
    readme = docs_dir / "README.md"
    if not readme.exists():
        return {"code": "D1", "severity": "HIGH", "message": "docs/README.md missing", "file_path": str(readme)}
    return None


def check_d2(docs_dir: Path) -> list[dict]:
    findings = []
    readme = docs_dir / "README.md"
    if not readme.exists():
        return findings
    text = readme.read_text(encoding="utf-8")
    headings = re.findall(r"^##\s+(.+?)\s*$", text, re.MULTILINE)
    headings_norm = [h.strip().lower() for h in headings]
    for canonical in CANONICAL_H2:
        if not any(canonical.lower() in h for h in headings_norm):
            findings.append({
                "code": "D2",
                "severity": "HIGH",
                "message": f"README missing canonical H2 section: '{canonical}'",
                "file_path": str(readme),
            })
    return findings


def check_d3(docs_dir: Path) -> list[dict]:
    findings = []
    for fname in CANONICAL_SIBLINGS:
        p = docs_dir / fname
        if not p.exists():
            findings.append({
                "code": "D3",
                "severity": "HIGH",
                "message": f"canonical sibling file missing: {fname}",
                "file_path": str(p),
            })
    return findings


def check_d4(docs_dir: Path) -> list[dict]:
    findings = []
    link_pattern = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
    for md in docs_dir.rglob("*.md"):
        text = md.read_text(encoding="utf-8", errors="ignore")
        for link in link_pattern.findall(text):
            target = link.split("#", 1)[0].strip()
            if not target:
                continue
            if target.startswith(("http://", "https://", "mailto:", "tel:", "/")):
                continue
            resolved = (md.parent / target).resolve()
            try:
                docs_resolved = docs_dir.resolve()
                resolved.relative_to(docs_resolved)
            except ValueError:
                continue
            if not resolved.exists():
                findings.append({
                    "code": "D4",
                    "severity": "HIGH",
                    "message": f"dead internal link: {target}",
                    "file_path": str(md),
                })
    return findings


def check_d5(docs_dir: Path, slug: str, strict: bool) -> dict | None:
    sev = "HIGH" if strict else "MED"
    changelog = docs_dir / "changelog.md"
    if not changelog.exists():
        return None
    text = changelog.read_text(encoding="utf-8")
    dates = re.findall(r"\b(20\d{2}-\d{2}-\d{2})\b", text)
    if not dates:
        return {"code": "D5", "severity": sev, "message": "changelog.md has no dated entries", "file_path": str(changelog)}
    last = max(datetime.strptime(d, "%Y-%m-%d") for d in dates)
    age = (datetime.utcnow() - last).days
    if age <= 90:
        return None
    repo = HOME / "zerg" / slug
    if not (repo / ".git").exists():
        return {"code": "D5", "severity": sev, "message": f"changelog last entry {last.date()} is {age}d old; no git repo at {repo}", "file_path": str(changelog)}
    try:
        result = subprocess.run(
            ["git", "-C", str(repo), "log", f"--since={last.strftime('%Y-%m-%d')}", "--oneline"],
            capture_output=True, text=True, timeout=10,
        )
        commits = [line for line in result.stdout.splitlines() if line.strip()]
    except (subprocess.SubprocessError, OSError):
        commits = []
    if commits:
        return {"code": "D5", "severity": sev, "message": f"changelog last entry {last.date()} but {len(commits)} commits to {repo} since", "file_path": str(changelog)}
    return None


def render_findings(findings: list[dict], slug: str, docs_dir: Path, exit_code: int) -> str:
    today = datetime.now().strftime("%Y-%m-%d")
    lines = [
        f"# product-docs audit — {slug} — {today}",
        "",
        f"docs_dir: `{docs_dir}`",
        f"total findings: {len(findings)}",
        f"HIGH: {sum(1 for f in findings if f['severity'] == 'HIGH')}",
        f"MED: {sum(1 for f in findings if f['severity'] == 'MED')}",
        f"exit_code: {exit_code}",
        "",
        "| code | severity | message | file |",
        "|------|----------|---------|------|",
    ]
    if not findings:
        lines.append("| — | — | clean | — |")
    for f in findings:
        msg = f["message"].replace("|", "\\|")
        lines.append(f"| {f['code']} | {f['severity']} | {msg} | `{f['file_path']}` |")
    lines.append("")
    if exit_code:
        lines.append(f"## next action")
        lines.append(f"resolve the {exit_code} HIGH findings, then re-run `audit {slug}`.")
    return "\n".join(lines) + "\n"


def cmd_audit(args) -> int:
    slug = args.slug
    docs_dir = HOME / "zerg" / slug / "docs"

    findings: list[dict] = []
    if not docs_dir.exists():
        findings.append({
            "code": "D1",
            "severity": "HIGH",
            "message": f"docs directory does not exist at {docs_dir}; run `scaffold {slug}` first",
            "file_path": str(docs_dir),
        })
    else:
        d1 = check_d1(docs_dir)
        if d1:
            findings.append(d1)
        findings.extend(check_d2(docs_dir))
        findings.extend(check_d3(docs_dir))
        findings.extend(check_d4(docs_dir))
        d5 = check_d5(docs_dir, slug, args.strict)
        if d5:
            findings.append(d5)

    high_count = sum(1 for f in findings if f["severity"] == "HIGH")
    report = render_findings(findings, slug, docs_dir, high_count)

    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(report, encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(report)

    return high_count


def main():
    parser = argparse.ArgumentParser(prog="product-docs-skill")
    sub = parser.add_subparsers(dest="verb", required=True)

    p_scaffold = sub.add_parser("scaffold", help="copy template into ~/zerg/<slug>/docs/ and token-substitute")
    p_scaffold.add_argument("slug")
    p_scaffold.add_argument("--from-backlog", help="path to launch-backlog markdown with frontmatter")
    p_scaffold.set_defaults(func=cmd_scaffold)

    p_audit = sub.add_parser("audit", help="run the 5 canonical docs checks")
    p_audit.add_argument("slug")
    p_audit.add_argument("--output", help="write markdown report to this path instead of stdout")
    p_audit.add_argument("--strict", action="store_true", help="promote D5 from MED to HIGH")
    p_audit.set_defaults(func=cmd_audit)

    args = parser.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
