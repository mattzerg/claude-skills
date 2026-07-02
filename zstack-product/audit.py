#!/usr/bin/env python3
"""Audit a Zstack microproduct against canonical patterns.

Emits severity-tagged findings (HIGH/MED/LOW) with cited rule + fix recipe.
Never auto-fixes.

Usage:
    python3 audit.py <slug>
    python3 audit.py zergboard
    python3 audit.py zsend
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

ZERG_ROOT = Path.home() / "zerg"
VAULT_ROOT = (
    Path.home()
    / "Obsidian/Zerg/MattZerg"
)


@dataclass
class Finding:
    severity: str  # HIGH | MED | LOW
    code: str  # A1, B2, etc. — maps to anti-patterns.md
    title: str
    rule: str  # citation
    fix: str  # concrete recipe
    where: str = ""  # file path that triggered

    def render(self) -> str:
        loc = f" — `{self.where}`" if self.where else ""
        return (
            f"[{self.severity}] {self.code}: {self.title}{loc}\n"
            f"  Rule: {self.rule}\n"
            f"  Fix:  {self.fix}\n"
        )


def detect_tier(repo: Path) -> str:
    """Auto-detect the product tier so we can skip Nuxt-specific checks for FastAPI/Tauri products.

    Returns one of: 'nuxt', 'fastapi', 'tauri', 'unknown'.
    """
    pkg = repo / "package.json"
    if pkg.is_file():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
            if "nuxt" in deps:
                return "nuxt"
            if "@tauri-apps/api" in deps or (repo / "src-tauri").is_dir() or (repo / "tauri.conf.json").is_file():
                return "tauri"
        except json.JSONDecodeError:
            pass
    if (repo / "main.py").is_file() or (repo / "requirements.txt").is_file() or (repo / "pyproject.toml").is_file():
        return "fastapi"
    if (repo / "src-tauri").is_dir() or (repo / "tauri.conf.json").is_file():
        return "tauri"
    return "unknown"


def open_prs_touching(slug: str) -> list[dict]:
    """Return list of open PRs in Epoch-ML/zerg whose diff touches <slug>/.

    Each entry: {number: int, title: str, files: set[str]}. Empty list on any failure
    (gh not installed, no auth, network down, etc.) — reconciliation is a soft enhancement.
    """
    out: list[dict] = []
    try:
        listing = subprocess.run(
            [
                "gh", "pr", "list",
                "--repo", "Epoch-ML/zerg",
                "--state", "open",
                "--json", "number,title,headRefName",
                "--limit", "30",
            ],
            capture_output=True, text=True, timeout=20,
        )
        if listing.returncode != 0:
            return []
        prs = json.loads(listing.stdout or "[]")
    except (subprocess.SubprocessError, FileNotFoundError, json.JSONDecodeError):
        return []

    for pr in prs:
        num = pr.get("number")
        if not num:
            continue
        try:
            diff = subprocess.run(
                ["gh", "pr", "diff", str(num), "--repo", "Epoch-ML/zerg", "--name-only"],
                capture_output=True, text=True, timeout=30,
            )
            if diff.returncode != 0:
                continue
            files = {ln.strip() for ln in diff.stdout.splitlines() if ln.strip()}
        except subprocess.SubprocessError:
            continue
        # Only track PRs that actually touch this product
        if any(f.startswith(f"{slug}/") for f in files):
            out.append({"number": num, "title": pr.get("title", ""), "files": files})
    return out


def reconcile_with_open_prs(slug: str, findings: list[Finding]) -> list[Finding]:
    """Downgrade findings whose target file is already touched by an open PR.

    HIGH → MED, MED → LOW, LOW unchanged. Annotates finding title with `(addressed in PR #N)`.
    """
    prs = open_prs_touching(slug)
    if not prs:
        return findings
    downgrade = {"HIGH": "MED", "MED": "LOW", "LOW": "LOW"}
    out: list[Finding] = []
    for f in findings:
        if not f.where:
            out.append(f)
            continue
        # Convert absolute path to repo-relative if applicable
        rel = f.where
        for prefix in (str(ZERG_ROOT) + "/",):
            if rel.startswith(prefix):
                rel = rel[len(prefix):]
                break
        match = next((pr for pr in prs if rel in pr["files"]), None)
        if match:
            out.append(Finding(
                severity=downgrade[f.severity],
                code=f.code,
                title=f"{f.title} (addressed in PR #{match['number']})",
                rule=f.rule,
                fix=f"Reconciled: PR #{match['number']} ({match['title'][:60]}) already touches this file. Verify after merge.",
                where=f.where,
            ))
        else:
            out.append(f)
    return out


def read_file(p: Path) -> Optional[str]:
    try:
        return p.read_text(encoding="utf-8")
    except Exception:
        return None


def audit_tech_stack(slug: str, repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    pkg = repo / "package.json"
    pkg_text = read_file(pkg)
    if pkg_text is None:
        findings.append(
            Finding(
                "HIGH",
                "T1",
                "package.json missing — not a Nuxt product or not bootstrapped",
                "canonical-patterns.md §1",
                f"Add package.json with Nuxt ^3.17.2 + TS strict pinned deps",
                where=str(pkg),
            )
        )
        return findings

    try:
        pkg_json = json.loads(pkg_text)
    except json.JSONDecodeError:
        findings.append(
            Finding(
                "HIGH",
                "T2",
                "package.json invalid JSON",
                "canonical-patterns.md §1",
                f"Repair package.json",
                where=str(pkg),
            )
        )
        return findings

    deps = {**pkg_json.get("dependencies", {}), **pkg_json.get("devDependencies", {})}

    expected = {
        "nuxt": "3.17",
        "@nuxtjs/tailwindcss": "6.13",
        "postgres": "3.",
        "bcryptjs": "2.4",
        "zod": "3.",
        "typescript": "5.",
    }
    for name, prefix in expected.items():
        version = deps.get(name)
        if not version:
            findings.append(
                Finding(
                    "MED",
                    "T3",
                    f"missing dep: {name}",
                    "canonical-patterns.md §1",
                    f"Add `{name}` (expected ~{prefix}.x) to package.json",
                    where=str(pkg),
                )
            )
            continue
        # crude version sniff: check the prefix appears
        cleaned = version.lstrip("^~>=< ")
        if not cleaned.startswith(prefix):
            findings.append(
                Finding(
                    "LOW",
                    "T4",
                    f"dep {name} version drift: {version} (expected ~{prefix}.x)",
                    "canonical-patterns.md §1",
                    f"Bump or downgrade {name} to match canonical pin",
                    where=str(pkg),
                )
            )
    return findings


def audit_layout(slug: str, repo: Path) -> list[Finding]:
    findings: list[Finding] = []

    required_dirs = ["server/api", "components", "pages", "db"]
    for d in required_dirs:
        if not (repo / d).is_dir():
            findings.append(
                Finding(
                    "HIGH",
                    "L1",
                    f"missing dir: {d}/",
                    "canonical-patterns.md §2",
                    f"Create `{repo}/{d}/` (see zergboard for shape)",
                    where=str(repo / d),
                )
            )

    # server/lib check — if signup imports from ../../lib but dir missing, flag
    lib_dir = repo / "server/lib"
    signup = repo / "server/api/auth/signup.post.ts"
    if signup.is_file():
        signup_text = read_file(signup) or ""
        if "../../lib/" in signup_text and not lib_dir.is_dir():
            findings.append(
                Finding(
                    "HIGH",
                    "A3",
                    "signup imports from server/lib/ but directory missing",
                    "anti-patterns.md A3",
                    "Materialize server/lib/ from zsend (auth.ts, db.ts, crypto.ts, validation.ts)",
                    where=str(lib_dir),
                )
            )
        elif not lib_dir.is_dir() and (repo / "server/api").is_dir():
            findings.append(
                Finding(
                    "MED",
                    "L2",
                    "server/lib/ missing",
                    "canonical-patterns.md §2",
                    "Add server/lib/{auth,db,crypto,validation}.ts (copy from zsend)",
                    where=str(lib_dir),
                )
            )

    # health endpoint
    health = repo / "server/api/health.get.ts"
    if not health.is_file():
        findings.append(
            Finding(
                "HIGH",
                "L3",
                "missing /api/health endpoint",
                "canonical-patterns.md §2",
                "Add server/api/health.get.ts returning 200 (Fly healthcheck depends on it)",
                where=str(health),
            )
        )

    # db migration
    if not (repo / "db/schema.sql").is_file():
        findings.append(
            Finding(
                "HIGH",
                "D1",
                "missing db/schema.sql",
                "canonical-patterns.md §4",
                "Add db/schema.sql with idempotent CREATE TABLE IF NOT EXISTS + ALTER TABLE",
                where=str(repo / "db/schema.sql"),
            )
        )
    if not (repo / "db/migrate.mjs").is_file():
        findings.append(
            Finding(
                "MED",
                "D2",
                "missing db/migrate.mjs",
                "canonical-patterns.md §4",
                "Add db/migrate.mjs runner (sql.unsafe(schema)). See zergboard.",
                where=str(repo / "db/migrate.mjs"),
            )
        )

    return findings


def audit_dockerfile(slug: str, repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    df = repo / "Dockerfile"
    text = read_file(df)
    if text is None:
        findings.append(
            Finding(
                "HIGH",
                "B1",
                "Dockerfile missing",
                "canonical-patterns.md §5",
                "Add multi-stage Dockerfile (node:22-alpine, npm install, prod-deps stage)",
                where=str(df),
            )
        )
        return findings

    if "node:22-alpine" not in text:
        findings.append(
            Finding(
                "MED",
                "B2",
                "Dockerfile not on node:22-alpine",
                "canonical-patterns.md §5",
                "Use FROM node:22-alpine AS base (canonical for Nuxt products)",
                where=str(df),
            )
        )
    if re.search(r"\bnpm ci\b", text):
        findings.append(
            Finding(
                "HIGH",
                "A5",
                "Dockerfile uses `npm ci`",
                "anti-patterns.md A5 (zerg-ztc 0.1.72 workspace bug)",
                "Replace with `npm install` until ztc fix lands",
                where=str(df),
            )
        )
    if "/api/health" not in text and "EXPOSE" not in text:
        # weak check, but flag if neither port nor health appear at all
        pass

    return findings


def audit_fly(slug: str, repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    ft = repo / "fly.toml"
    text = read_file(ft)
    if text is None:
        findings.append(
            Finding(
                "HIGH",
                "F1",
                "fly.toml missing",
                "canonical-patterns.md §6",
                "Add fly.toml with primary_region, NITRO_HOST/PORT, /api/health check",
                where=str(ft),
            )
        )
        return findings

    if 'primary_region' not in text:
        findings.append(
            Finding(
                "HIGH",
                "F2",
                "fly.toml missing primary_region",
                "canonical-patterns.md §6",
                'Add primary_region = "lax" (Nitro) or "sjc" (FastAPI)',
                where=str(ft),
            )
        )
    if "/api/health" not in text:
        findings.append(
            Finding(
                "HIGH",
                "F3",
                "fly.toml missing /api/health check",
                "canonical-patterns.md §6",
                "Add [[http_service.checks]] with path = \"/api/health\"",
                where=str(ft),
            )
        )
    if "auto_stop_machines" not in text:
        findings.append(
            Finding(
                "MED",
                "F4",
                'fly.toml missing auto_stop_machines = "stop"',
                "canonical-patterns.md §6",
                'Add auto_stop_machines = "stop" + min_machines_running = 0',
                where=str(ft),
            )
        )
    return findings


def audit_tracker(slug: str, repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    nc = repo / "nuxt.config.ts"
    if not nc.is_file():
        return findings  # caught elsewhere
    text = read_file(nc) or ""
    has_tracker = "useAnalytics" in text or "zerglytics" in text.lower() or "zergalytics" in text.lower()
    if not has_tracker:
        # also scan composables/ for the tracker
        comp_dir = repo / "composables"
        tracker_file = (
            comp_dir.is_dir()
            and any(p.name.startswith("useAnalytics") for p in comp_dir.iterdir())
        )
        if not tracker_file:
            findings.append(
                Finding(
                    "HIGH",
                    "A1",
                    "ZergAlytics tracker not embedded",
                    "anti-patterns.md A1, feedback_zb_tracker_cross_origin.md",
                    "Copy ~/zerg/web/src/composables/useAnalytics.ts → composables/; wire in app.vue",
                    where=str(nc),
                )
            )
    return findings


def audit_signup_upsert(slug: str, repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    signup = repo / "server/api/auth/signup.post.ts"
    if not signup.is_file():
        return findings  # not all products have signup yet
    text = read_file(signup) or ""
    # heuristic: look for upsertContact, ZSEND_INGEST_TOKEN, /api/v1/contacts, account_creation
    indicators = ["upsertContact", "ZSEND_INGEST_TOKEN", "/api/v1/contacts", "account_creation"]
    if not any(s in text for s in indicators):
        findings.append(
            Finding(
                "HIGH",
                "A2",
                "signup endpoint does not call ZergSend upsert_contact",
                "anti-patterns.md A2",
                "After createSession, POST account_creation event to ${ZSEND_BASE_URL}/api/v1/contacts (see ~/zerg/zsend/server/lib/upsert_contact.ts UpsertContactInput)",
                where=str(signup),
            )
        )
    return findings


def audit_readme(slug: str, repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    rm = repo / "README.md"
    text = read_file(rm)
    if not text:
        findings.append(
            Finding(
                "MED",
                "R1",
                "README.md missing or empty",
                "canonical-patterns.md §14",
                "Add README with 7-section shape (Intro/Features/Local Setup/Tech Stack/API Surface/Deployment/Notes)",
                where=str(rm),
            )
        )
        return findings

    sections = ["features", "setup", "tech stack", "api", "deploy", "notes"]
    text_lower = text.lower()
    missing = [s for s in sections if s not in text_lower]
    if missing:
        findings.append(
            Finding(
                "MED",
                "B3",
                f"README missing sections: {', '.join(missing)}",
                "anti-patterns.md B3",
                "Add the missing H2 sections (see zergboard README)",
                where=str(rm),
            )
        )
    return findings


def audit_vault_positioning(slug: str) -> list[Finding]:
    findings: list[Finding] = []
    proj_root = VAULT_ROOT / "Projects"
    proj_dir = proj_root / "Zerg-Production" / "Zstack"
    if not proj_root.is_dir():
        return findings  # vault not on this machine

    # Search layered Projects/ tree: Zerg-Production/<P>/<P>.md, Zerg-Development/<P>/<P>.md, legacy Zstack/<P>.md
    _search = []
    for d in (proj_root / "Zerg-Production", proj_root / "Zerg-Development", proj_dir):
        if d.is_dir():
            _search += list(d.glob("*.md")) + list(d.glob("*/*.md"))
    # Match by case-insensitive stem; positioning doc is e.g. Zergboard.md, ZergSend.md
    candidates = [p for p in _search if p.stem.lower() == slug.lower()]
    if not candidates:
        # try capitalized variants
        candidates = [
            p
            for p in _search
            if p.stem.lower().replace("zerg", "") == slug.lower().replace("zerg", "").replace("z", "")
        ]
    if not candidates:
        findings.append(
            Finding(
                "HIGH",
                "A6",
                f"positioning doc missing for {slug}",
                "anti-patterns.md A6",
                f"Create {proj_dir}/{slug.capitalize()}.md with positioning template (run bootstrap.py)",
                where=str(proj_dir / f"{slug}.md"),
            )
        )
        return findings

    pos = candidates[0]
    text = read_file(pos) or ""
    text_lower = text.lower()

    pillars = [
        ("AI-native", ["ai-native", "ai native", "agents are first-class"]),
        ("Zstack-interconnected", ["zstack-interconnected", "zergstack-interconnected", "interconnected"]),
        ("Much cheaper", ["much cheaper", "cheaper", "undercut"]),
        ("Easy to automate", ["easy to automate", "automate", "agent context"]),
    ]
    for label, keys in pillars:
        if not any(k in text_lower for k in keys):
            findings.append(
                Finding(
                    "MED",
                    "B4",
                    f"positioning missing pillar: {label}",
                    "anti-patterns.md B4",
                    f"Add the {label} pillar paragraph to {pos.name}",
                    where=str(pos),
                )
            )

    # Pricing tier check
    has_free = "free" in text_lower
    has_basic = "$1" in text or "basic" in text_lower
    has_pro = "$9" in text or "pro" in text_lower
    if not (has_free and has_basic and has_pro):
        findings.append(
            Finding(
                "MED",
                "B8",
                "positioning missing Free/$1/$9/Enterprise tier prices",
                "anti-patterns.md B8",
                "State Free/$1 Basic/$9 Pro/Enterprise verbatim per Pricing-Snapshot.md",
                where=str(pos),
            )
        )

    return findings


def audit_competitive(slug: str, category: Optional[str]) -> list[Finding]:
    findings: list[Finding] = []
    if not category:
        return findings
    comp_dir = VAULT_ROOT / "Competitive" / category
    if not comp_dir.is_dir():
        findings.append(
            Finding(
                "HIGH",
                "B5",
                f"competitive folder missing: {category}/",
                "anti-patterns.md B5",
                f"Create {comp_dir} with 8-file shape (run competitive-review-skill or bootstrap.py --category {category})",
                where=str(comp_dir),
            )
        )
        return findings

    expected = [
        "index.md",
        "matrix.md",
        "gaps.md",
        "positioning.md",
        "positioning-deep.md",
        "pricing.md",
        "differentiation-opportunities.md",
        "drift.md",
    ]
    for f in expected:
        if not (comp_dir / f).is_file():
            findings.append(
                Finding(
                    "MED",
                    "B5",
                    f"competitive folder missing: {category}/{f}",
                    "canonical-patterns.md §11",
                    f"Add {comp_dir / f} (template available in MattZerg/Competitive/pm-software/)",
                    where=str(comp_dir / f),
                )
            )
    return findings


def audit_measurement_spec(slug: str) -> list[Finding]:
    """Check per-product Zerglytics measurement spec — canonical-patterns.md §16.

    HIGH-fails if YAML or checklist missing, YAML doesn't parse, or required canonical
    events are absent. MED-fails if optional_events empty or funnels.expansion missing.
    """
    findings: list[Finding] = []
    measurement_dir = VAULT_ROOT / "Projects/Zerg-Production/Growth/measurement"
    spec_yaml = measurement_dir / f"{slug}.yaml"
    checklist = measurement_dir / f"{slug}.checklist.md"

    if not measurement_dir.is_dir():
        # Vault not on this machine — skip silently (same convention as audit_vault_positioning)
        return findings

    if not spec_yaml.is_file():
        findings.append(
            Finding(
                "HIGH",
                "M1",
                f"measurement spec missing: {slug}.yaml",
                "canonical-patterns.md §16",
                f"Create {spec_yaml} from Growth/measurement/_template.yaml (declare required events, funnels, dashboard bindings)",
                where=str(spec_yaml),
            )
        )

    if not checklist.is_file():
        findings.append(
            Finding(
                "HIGH",
                "M2",
                f"measurement checklist missing: {slug}.checklist.md",
                "canonical-patterns.md §16",
                f"Create {checklist} from Growth/measurement/_checklist-template.md (parsed by launch-ops ship-readiness gate)",
                where=str(checklist),
            )
        )

    if not spec_yaml.is_file():
        return findings

    text = read_file(spec_yaml) or ""
    try:
        import yaml  # local import — keeps module loadable even if PyYAML missing
        spec = yaml.safe_load(text)
    except ImportError:
        findings.append(
            Finding(
                "LOW",
                "M3",
                "PyYAML not installed — could not parse measurement spec",
                "canonical-patterns.md §16",
                "pip install pyyaml (audit can validate spec contents)",
                where=str(spec_yaml),
            )
        )
        return findings
    except Exception as e:
        findings.append(
            Finding(
                "HIGH",
                "M4",
                f"measurement spec does not parse: {e.__class__.__name__}",
                "canonical-patterns.md §16",
                f"Repair YAML in {spec_yaml} (yaml.safe_load raised)",
                where=str(spec_yaml),
            )
        )
        return findings

    if not isinstance(spec, dict):
        findings.append(
            Finding(
                "HIGH",
                "M5",
                "measurement spec is not a YAML mapping",
                "canonical-patterns.md §16",
                "Top-level must be a mapping (required_events, optional_events, funnels, ...)",
                where=str(spec_yaml),
            )
        )
        return findings

    canonical_events = [
        f"{slug}_signup",
        f"{slug}_aha",
        f"{slug}_pro_upgrade",
        f"{slug}_bundle_upgrade",
        f"{slug}_last_active_at",
        f"{slug}_churn_risk",
    ]
    required_events = spec.get("required_events") or []
    if not isinstance(required_events, list):
        required_events = []
    missing_canon = [e for e in canonical_events if e not in required_events]
    if missing_canon:
        findings.append(
            Finding(
                "HIGH",
                "M6",
                f"measurement spec missing canonical required_events: {', '.join(missing_canon)}",
                "canonical-patterns.md §16",
                f"Add to required_events list in {spec_yaml.name}: {missing_canon}",
                where=str(spec_yaml),
            )
        )

    optional_events = spec.get("optional_events")
    if not optional_events:
        findings.append(
            Finding(
                "MED",
                "M7",
                "measurement spec has no optional_events",
                "canonical-patterns.md §16",
                f"Declare optional_events in {spec_yaml.name} (product-specific signals beyond the canonical 6)",
                where=str(spec_yaml),
            )
        )

    funnels = spec.get("funnels") or {}
    if not isinstance(funnels, dict) or "expansion" not in funnels:
        findings.append(
            Finding(
                "MED",
                "M8",
                "measurement spec missing funnels.expansion",
                "canonical-patterns.md §16",
                f"Add funnels.expansion (pro_upgrade → bundle_upgrade) in {spec_yaml.name}",
                where=str(spec_yaml),
            )
        )

    return findings


def audit_docs_surface(slug: str, repo: Path) -> list[Finding]:
    """Check per-product docs surface — canonical-patterns.md §17.

    HIGH-fails on missing docs/, missing canonical H2 sections in README, or missing
    sibling files. MED-fails on empty changelog.md.
    """
    findings: list[Finding] = []
    docs_dir = repo / "docs"

    if not docs_dir.is_dir():
        findings.append(
            Finding(
                "HIGH",
                "DC1",
                f"docs/ directory missing for {slug}",
                "canonical-patterns.md §17",
                f"Scaffold from ~/zerg/_templates/zerg-product/product-docs/ (use zerg-new-product.sh or product-docs-skill scaffold)",
                where=str(docs_dir),
            )
        )
        return findings

    canonical_sections = [
        "What it is",
        "Quick start",
        "Concepts",
        "API",
        "Frontend",
        "Status",
    ]
    readme = docs_dir / "README.md"
    readme_text = read_file(readme)
    if readme_text is None:
        findings.append(
            Finding(
                "HIGH",
                "DC2",
                "docs/README.md missing",
                "canonical-patterns.md §17",
                "Create docs/README.md with the 6 canonical H2 sections (What it is / Quick start / Concepts / API / Frontend / Status)",
                where=str(readme),
            )
        )
    else:
        present_sections = set(re.findall(r"^## (.+)$", readme_text, re.MULTILINE))
        # Normalize whitespace from captured headings
        present_sections = {s.strip() for s in present_sections}
        missing_sections = [s for s in canonical_sections if s not in present_sections]
        if missing_sections:
            findings.append(
                Finding(
                    "HIGH",
                    "DC3",
                    f"docs/README.md missing canonical H2 sections: {', '.join(missing_sections)}",
                    "canonical-patterns.md §17",
                    f"Add the missing ## sections to {readme} (order matters: What it is → Quick start → Concepts → API → Frontend → Status)",
                    where=str(readme),
                )
            )

    sibling_files = [
        "getting-started.md",
        "architecture.md",
        "what-can-i-build.md",
        "api-backend.md",
        "web-frontend.md",
        "faq.md",
        "changelog.md",
    ]
    for name in sibling_files:
        if not (docs_dir / name).is_file():
            findings.append(
                Finding(
                    "HIGH",
                    "DC4",
                    f"docs/{name} missing",
                    "canonical-patterns.md §17",
                    f"Scaffold docs/{name} from ~/zerg/_templates/zerg-product/product-docs/{name}",
                    where=str(docs_dir / name),
                )
            )

    changelog = docs_dir / "changelog.md"
    if changelog.is_file():
        cl_text = (read_file(changelog) or "").strip()
        # Treat as empty if very short or matches placeholder hints
        is_placeholder = (
            len(cl_text) < 80
            or re.search(r"\b(TODO|placeholder|no entries yet|fill me in)\b", cl_text, re.IGNORECASE) is not None
        )
        if is_placeholder:
            findings.append(
                Finding(
                    "MED",
                    "DC5",
                    "docs/changelog.md has no entries (placeholder only)",
                    "canonical-patterns.md §17",
                    f"Log at least one shipped entry in {changelog} (product-docs-skill flags 90-day staleness vs git log)",
                    where=str(changelog),
                )
            )

    return findings


def audit_brand_palette(slug: str, repo: Path) -> list[Finding]:
    findings: list[Finding] = []
    # Brand palette is conventionally in assets/css/main.css OR nuxt.config.ts.
    # Marketing pages should contain brand hex codes; in-app theming may use --skin-*.
    candidates = [repo / "nuxt.config.ts", repo / "assets/css/main.css"]
    combined = ""
    for c in candidates:
        combined += read_file(c) or ""
    brand_hex = ["#f4f0e7", "#111514", "#b3662f", "#8a4a1f", "#6FBE31", "#6fbe31"]
    has_brand = any(c in combined for c in brand_hex)
    has_inapp_skin = "--skin-bg" in combined or "--skin-accent" in combined
    nc = repo / "nuxt.config.ts"
    if not has_brand and not has_inapp_skin:
        findings.append(
            Finding(
                "MED",
                "B1",
                "no brand palette and no in-app skin tokens detected",
                "anti-patterns.md B1",
                "If marketing-facing, embed brand palette from ~/zerg/web/src/pages/index.vue. If in-app, set up --skin-* presets.",
                where=str(nc),
            )
        )
    return findings


NUXT_ONLY_CHECKS = {
    "audit_tech_stack",
    "audit_layout",
    "audit_dockerfile",  # canonical Dockerfile shape is Nuxt-specific (node:22-alpine + prod-deps stage)
    "audit_tracker",
    "audit_signup_upsert",
    "audit_brand_palette",
}


def audit_product(slug: str, category: Optional[str] = None, tier: Optional[str] = None) -> list[Finding]:
    repo = ZERG_ROOT / slug
    findings: list[Finding] = []
    if not repo.is_dir():
        return [
            Finding(
                "HIGH",
                "X1",
                f"product directory missing: ~/zerg/{slug}/",
                "canonical-patterns.md §2",
                f"Bootstrap with: python3 audit.py — wait, run bootstrap.py {slug}",
                where=str(repo),
            )
        ]

    detected = tier or detect_tier(repo)

    # Tier-aware gating: only run the canonical (Nuxt) rule set on Nuxt products.
    # FastAPI / Tauri products get a single LOW info note instead of 7-10 false-positive HIGHs.
    if detected != "nuxt":
        findings.append(
            Finding(
                "LOW",
                "X2",
                f"tier={detected} — Nuxt-specific rule set skipped",
                "canonical-patterns.md §1",
                f"This product is detected as {detected}; canonical-patterns.md §1-§14 are Nuxt-tier rules. Vault + competitive + Fly checks still ran. Override with --tier nuxt to force-audit.",
                where=str(repo),
            )
        )
        # Cross-tier checks that DO apply
        findings += audit_fly(slug, repo)
        findings += audit_readme(slug, repo)
        findings += audit_vault_positioning(slug)
        findings += audit_competitive(slug, category)
        findings += audit_measurement_spec(slug)
        findings += audit_docs_surface(slug, repo)
        return findings

    findings += audit_tech_stack(slug, repo)
    findings += audit_layout(slug, repo)
    findings += audit_dockerfile(slug, repo)
    findings += audit_fly(slug, repo)
    findings += audit_tracker(slug, repo)
    findings += audit_signup_upsert(slug, repo)
    findings += audit_readme(slug, repo)
    findings += audit_brand_palette(slug, repo)
    findings += audit_vault_positioning(slug)
    findings += audit_competitive(slug, category)
    findings += audit_measurement_spec(slug)
    findings += audit_docs_surface(slug, repo)
    return findings


def render_findings(slug: str, findings: list[Finding]) -> str:
    out: list[str] = []
    out.append(f"# Audit: {slug}")
    out.append("")
    counts = {"HIGH": 0, "MED": 0, "LOW": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    out.append(f"**Summary**: {counts.get('HIGH', 0)} HIGH · {counts.get('MED', 0)} MED · {counts.get('LOW', 0)} LOW")
    out.append("")
    if not findings:
        out.append("No findings — product is canonical.")
        return "\n".join(out)

    for sev in ["HIGH", "MED", "LOW"]:
        sev_findings = [f for f in findings if f.severity == sev]
        if not sev_findings:
            continue
        out.append(f"## {sev}")
        out.append("")
        for f in sev_findings:
            out.append(f.render())
    return "\n".join(out)


def main() -> int:
    p = argparse.ArgumentParser(description="Audit a Zstack microproduct against canonical patterns")
    p.add_argument("slug", help="Product slug (e.g. zergboard, zsend, zergwallet)")
    p.add_argument(
        "--category",
        help="Competitive category folder name (e.g. pm-software, crm). If set, audits competitive folder.",
        default=None,
    )
    p.add_argument(
        "--tier",
        choices=["nuxt", "fastapi", "tauri", "auto"],
        default="auto",
        help="Override tier detection. 'auto' (default) detects from package.json/main.py. Non-Nuxt tiers skip Nuxt-specific rules.",
    )
    p.add_argument(
        "--reconcile-prs",
        action="store_true",
        help="Cross-reference open PRs in Epoch-ML/zerg via gh CLI; downgrade findings whose target file is already touched by an open PR. Closes the gap documented in feedback_audit_misses_in_flight_prs.md.",
    )
    p.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable")
    args = p.parse_args()

    tier_arg = None if args.tier == "auto" else args.tier
    findings = audit_product(args.slug, args.category, tier=tier_arg)
    if args.reconcile_prs:
        findings = reconcile_with_open_prs(args.slug, findings)
    if args.json:
        print(json.dumps([asdict(f) for f in findings], indent=2))
    else:
        print(render_findings(args.slug, findings))

    # Exit non-zero if any HIGH findings — useful for pre-deploy gates
    high = [f for f in findings if f.severity == "HIGH"]
    return 1 if high else 0


if __name__ == "__main__":
    sys.exit(main())
