#!/usr/bin/env python3
"""Pipeline observability for zpub — blog posts only (Phase 1).

Reads real signals at each stage of a blog post's pipeline:

  1. drafted        — vault `.md` exists (surfaces field points to it)
  2. gates          — fakematt_copyedit / fakeidan / signoff per gates.json
  3. on_dev_branch  — `web/src/public/content/blog/<slug>.md` on origin/development
  4. live_on_dev    — dev.zergai.com/blog/<slug> returns 200, or becomes
                      non-blocking after prod is confirmed live
  5. on_main_branch — `web/src/public/content/blog/<slug>.md` on origin/main
                      (i.e., Idan ran the manual main←dev sync)
  6. live_on_prod   — zergai.com/blog/<slug> returns 200, appears in blog API,
                      or zpub marks the post published + prod_deployed passed

Per `feedback_dev_merge_is_not_publish.md`: prod deploy is Idan's MANUAL periodic
main←dev sync. Branch stages are verified from source. Live-route stages also
account for the current Nuxt SPA false-negative: some human-live blog routes
return server-side 404 until prerender/unfurl work lands.

Cache: `_meta/pipeline.json` in the publishing dir. `zpub refresh` rebuilds it.
"""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

ZERG_REPO = Path.home() / "zerg"
DEV_BASE = "https://dev.zergai.com"
PROD_BASE = "https://zergai.com"
BLOG_PATH_RE = re.compile(r"web/src/public/content/blog/([a-z0-9][a-z0-9-]+)\.md")
TS_PATH_RE = re.compile(r"web/src/constants/blog/posts/([a-z0-9][a-z0-9-]+)\.ts")
TS_SLUG_RE = re.compile(r"""\bslug\s*:\s*['"]([^'"]+)['"]""")
TS_STATUS_RE = re.compile(r"""\bstatus\s*:\s*['"](draft|queued|published)['"]""")
TS_CATEGORY_RE = re.compile(r"""\bcategory\s*:\s*['"]([^'"]+)['"]""")
TS_CANONICAL_RE = re.compile(r"""\bcanonicalUrl\s*:\s*['"]([^'"]+)['"]""")
HTTP_TIMEOUT = 8.0


def validate_gate_consistency(entry) -> list[str]:
    """Return a list of gate-state contradictions.

    An entry's stored gate state can claim a downstream gate has cleared
    while an upstream prerequisite still hasn't. That contradiction must
    not be representable — it produces false-confidence "imminent publish"
    signals in render, morning brief, and AI session reasoning.

    Invariants (per ~/.claude/plans/synchronous-yawning-storm.md Part A1):
      - signoff=passed requires fakeidan=passed AND ledger_clean=passed
        AND imagery_quality in {passed, n_a}.
      - prod_deployed=passed requires signoff=passed.
      - status=scheduled requires date_confirmed=true AND every required
        gate in {passed, n_a}.
      - status=published requires prod_deployed=passed.

    `entry` is duck-typed: `.gates` (dict), `.status` (str),
    `.date_confirmed` (bool), `.type` (str). Caller computes
    `required_gates(entry.type)` and passes it in or we look it up via a
    callback; to avoid a circular import we accept either an `Entry`-like
    object or a plain dict shaped the same way.
    """
    gates = getattr(entry, "gates", None) or (entry.get("gates") if isinstance(entry, dict) else {}) or {}
    status = getattr(entry, "status", None) or (entry.get("status") if isinstance(entry, dict) else "") or ""
    date_confirmed = getattr(entry, "date_confirmed", None)
    if date_confirmed is None and isinstance(entry, dict):
        date_confirmed = entry.get("date_confirmed", False)
    entry_type = getattr(entry, "type", None) or (entry.get("type") if isinstance(entry, dict) else "") or ""

    violations: list[str] = []

    def gv(name: str) -> str:
        return gates.get(name, "pending")

    if gv("signoff") == "passed":
        if gv("fakeidan") != "passed":
            violations.append(f"signoff=passed but fakeidan={gv('fakeidan')} (required: passed)")
        if gv("ledger_clean") not in ("passed", "n_a"):
            violations.append(f"signoff=passed but ledger_clean={gv('ledger_clean')} (required: passed or n_a)")
        if gv("imagery_quality") not in ("passed", "n_a"):
            violations.append(f"signoff=passed but imagery_quality={gv('imagery_quality')} (required: passed or n_a)")

    if gv("prod_deployed") == "passed" and gv("signoff") != "passed":
        violations.append(f"prod_deployed=passed but signoff={gv('signoff')} (required: passed)")

    if status == "scheduled":
        if not date_confirmed:
            violations.append("status=scheduled but date_confirmed=false")
        # Required-gates check requires the caller to know the type's required
        # set; we encode the conservative subset here. The CLI guard in zpub.py
        # already performs the full required-gates sweep at the status-flip
        # site, so this duplicate check is intentionally narrow.
        for g in ("fakeidan", "signoff"):
            if g in gates and gv(g) not in ("passed", "n_a"):
                violations.append(f"status=scheduled but {g}={gv(g)} (required: passed or n_a)")

    if status == "published" and gv("prod_deployed") != "passed":
        violations.append(f"status=published but prod_deployed={gv('prod_deployed')} (required: passed)")

    # entry_type is unused today but kept in scope for future type-aware
    # invariants (e.g., case-study has a different required chain).
    _ = entry_type
    return violations


STAGE_LABELS = [
    ("drafted",        "draft"),
    ("gates",          "gates"),
    ("on_dev_branch",  "on dev"),
    ("live_on_dev",    "dev URL"),
    ("on_main_branch", "on main"),
    ("live_on_prod",   "prod URL"),
]


@dataclass
class StageResult:
    name: str
    state: str         # "passed" | "failed" | "n_a" | "unknown"
    detail: str = ""
    next_action: str = ""


@dataclass
class PipelineState:
    entry_id: str
    slug: Optional[str]
    stages: list[StageResult] = field(default_factory=list)
    highest_completed: int = -1  # 0-based index into STAGE_LABELS
    next_blocker: Optional[str] = None
    checked_at: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "slug": self.slug,
            "stages": [asdict(s) for s in self.stages],
            "highest_completed": self.highest_completed,
            "next_blocker": self.next_blocker,
            "checked_at": self.checked_at,
        }


# ---------- Signal helpers ----------

def derive_content_filename(entry) -> Optional[str]:
    """Parse the .md filename basename from surfaces.

    The filename is what `git ls-tree` checks. It's NOT the route slug — the
    route slug is in the .ts file's `slug:` field.

    When no cms surface exists yet (entry only carries a blog-source surface),
    fall back to slug_util's shared candidates (SLUG_HINTS + normalized title)
    so prod_deployed can still be evaluated — previously this returned None and
    the gate hung pending forever (e.g. pub-2026-thesis-nobody-reads-code).
    """
    for s in entry.surfaces or []:
        path = (s.get("path") or "")
        m = BLOG_PATH_RE.search(path)
        if m:
            return m.group(1)
        m = TS_PATH_RE.search(path)
        if m:
            return m.group(1)
    try:
        from slug_util import slug_candidates  # shared with tools/check_gates.py
        candidates = slug_candidates(getattr(entry, "id", ""), entry.surfaces)
        if candidates:
            return candidates[0]
    except ImportError:
        pass
    return None


# Backwards-compat alias.
derive_slug = derive_content_filename


@dataclass
class TsMeta:
    """Per-branch metadata extracted from the .ts file's source."""
    branch: str
    present: bool
    slug: Optional[str] = None        # route slug (`slug:` field)
    category: Optional[str] = None
    canonical_url: Optional[str] = None
    status: Optional[str] = None      # 'draft' | 'queued' | 'published'
    last_commit: Optional[str] = None # `<sha> <date> <msg>` of last commit touching .ts on branch


def _read_ts_meta(filename: str, branch: str) -> TsMeta:
    path = f"web/src/constants/blog/posts/{filename}.ts"
    listing = _git(["ls-tree", f"origin/{branch}", path])
    if not listing:
        return TsMeta(branch=branch, present=False)
    src = _git(["show", f"origin/{branch}:{path}"]) or ""
    slug_m = TS_SLUG_RE.search(src)
    status_m = TS_STATUS_RE.search(src)
    category_m = TS_CATEGORY_RE.search(src)
    canonical_m = TS_CANONICAL_RE.search(src)
    last_commit = _git([
        "log", f"origin/{branch}", "--first-parent",
        "--format=%h %cs %s", "-n", "1", "--", path,
    ])
    return TsMeta(
        branch=branch,
        present=True,
        slug=slug_m.group(1) if slug_m else None,
        category=category_m.group(1) if category_m else None,
        canonical_url=canonical_m.group(1) if canonical_m else None,
        status=status_m.group(1) if status_m else None,
        last_commit=last_commit,
    )


def _git(args: list[str]) -> Optional[str]:
    try:
        r = subprocess.run(
            ["git", "-C", str(ZERG_REPO)] + args,
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode != 0:
            return None
        return r.stdout.strip()
    except (subprocess.SubprocessError, OSError):
        return None


def _check_branch_has(branch: str, slug: str) -> tuple[bool, str]:
    """Return (present, detail). Detail is `<sha> <date>` of last commit touching the file."""
    path = f"web/src/public/content/blog/{slug}.md"
    listing = _git(["ls-tree", f"origin/{branch}", path])
    if not listing:
        return False, ""
    log = _git([
        "log", f"origin/{branch}", "--first-parent",
        "--format=%h %cs %s", "-n", "1", "--", path,
    ])
    return True, (log or "present")


def _http_status(url: str) -> Optional[int]:
    # GET with a Range header so we don't pull a full HTML body for every check.
    # The Nuxt/Cloudflare front-end rejects HEAD on these routes, so we use GET.
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "zpub-pipeline/1",
                "Range": "bytes=0-127",
            },
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            r.read(128)
            return r.status
    except urllib.error.HTTPError as e:
        return e.code
    except (urllib.error.URLError, TimeoutError, OSError):
        return None


# Cache for the API list (one call per host per refresh).
_API_CACHE: dict[str, set[str]] = {}


def _api_slugs(base: str) -> Optional[set[str]]:
    if base in _API_CACHE:
        return _API_CACHE[base]
    try:
        req = urllib.request.Request(f"{base}/api/blog/posts/",
                                     headers={"User-Agent": "zpub-pipeline/1"})
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r:
            data = json.loads(r.read().decode())
        slugs = {p.get("slug") for p in data.get("posts", []) if p.get("slug")}
        _API_CACHE[base] = slugs
        return slugs
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        return None


DRAFT_KIND_HINTS = ("draft", "source", "cms-canonical-md", "markdown", "blog")
DRAFT_PATH_SKIP = (".plist", ".py", ".png", ".jpg", ".jpeg", ".gif", ".pdf", ".svg")


def _surface_paths(entry) -> list[Path]:
    """Vault `.md` paths from surfaces that plausibly point at a draft.

    Filters out plists / images / cron scripts / PDFs. Prefers surfaces whose
    `kind` mentions draft/source/markdown.
    """
    vault_root = Path.home() / "Obsidian/Zerg"  # post-migration live vault root (contains MattZerg/)
    preferred: list[Path] = []
    fallback: list[Path] = []
    for s in entry.surfaces or []:
        path_str = (s.get("path") or "").strip()
        kind = (s.get("kind") or "").lower()
        if not path_str:
            continue
        if any(path_str.lower().endswith(ext) for ext in DRAFT_PATH_SKIP):
            continue
        if not path_str.lower().endswith(".md"):
            continue
        if path_str.startswith("MattZerg/"):
            p = vault_root / path_str
        elif path_str.startswith("/"):
            p = Path(path_str)
        else:
            continue
        if any(h in kind for h in DRAFT_KIND_HINTS):
            preferred.append(p)
        else:
            fallback.append(p)
    return preferred + fallback


# ---------- Stage checks ----------

def _stage_drafted(entry, slug: Optional[str]) -> StageResult:
    paths = _surface_paths(entry)
    existing = [p for p in paths if p.exists()]
    if existing:
        rel = str(existing[0]).split("/Documents/Zerg/")[-1]
        return StageResult("drafted", "passed", detail=rel)
    # Fallback: if the canonical `.md` is already on a branch in the repo,
    # the post was clearly drafted (just in repo, not vault).
    if slug:
        present_dev, _ = _check_branch_has("development", slug)
        if present_dev:
            return StageResult("drafted", "passed",
                               detail=f"web/src/public/content/blog/{slug}.md on origin/development")
    if not paths:
        return StageResult("drafted", "unknown",
                           detail="no `.md` surface on entry",
                           next_action="add a `MattZerg/Writing/<title>.md` surface to the entry")
    return StageResult("drafted", "failed",
                       detail=f"expected at {paths[0]}",
                       next_action=f"write the draft at {paths[0]}")


def _stage_gates(entry) -> StageResult:
    from zpub import required_gates
    req = [g for g in required_gates(entry.type) if g != "prod_deployed"]
    if not req:
        return StageResult("gates", "n_a")
    states = [(g, entry.gates.get(g, "pending")) for g in req]
    passed = [g for g, v in states if v in ("passed", "n_a")]
    failed = [g for g, v in states if v == "failed"]
    pending = [g for g, v in states if v == "pending"]
    if failed:
        return StageResult("gates", "failed",
                           detail=f"failed: {', '.join(failed)}",
                           next_action=f"redo gate `{failed[0]}`")
    if pending:
        return StageResult("gates", "failed",
                           detail=f"{len(passed)}/{len(req)} passed · pending: {', '.join(pending)}",
                           next_action=f"clear gate `{pending[0]}`")
    return StageResult("gates", "passed",
                       detail=f"{len(passed)}/{len(req)}: {', '.join(passed)}")


def _stage_on_branch(filename: Optional[str], ts: TsMeta, branch: str) -> StageResult:
    name = "on_dev_branch" if branch == "development" else "on_main_branch"
    if not filename:
        return StageResult(name, "n_a", detail="no blog filename derivable from surfaces")
    md_present, md_detail = _check_branch_has(branch, filename)
    ts_present = ts.present
    if md_present and ts_present:
        status_note = f" · ts.status={ts.status}" if ts.status else ""
        return StageResult(name, "passed",
                           detail=f"{md_detail}{status_note}")
    missing = []
    if not md_present: missing.append(f"{filename}.md")
    if not ts_present: missing.append(f"{filename}.ts")
    if branch == "main":
        action = (f"ping Idan in #growzth: 'Ready to sync to main: {filename}'")
    else:
        action = (f"PR adding web/src/public/content/blog/{filename}.md + "
                  f"web/src/constants/blog/posts/{filename}.ts to development")
    return StageResult(name, "failed",
                       detail=f"missing on origin/{branch}: {', '.join(missing)}",
                       next_action=action)


def _stage_live(filename: Optional[str], ts: TsMeta, base: str, label: str) -> StageResult:
    name = "live_on_dev" if "dev" in base else "live_on_prod"
    if not filename:
        return StageResult(name, "n_a", detail="no filename")
    if not ts.present:
        return StageResult(name, "failed",
                           detail=f"{filename}.ts missing on origin/{ts.branch}",
                           next_action=f"add the .ts entry on origin/{ts.branch}")
    if ts.status == "draft":
        return StageResult(name, "failed",
                           detail=f"{filename}.ts has status:'draft' on {ts.branch}",
                           next_action=(f"flip status:'draft' → 'queued' (or 'published') in "
                                        f"web/src/constants/blog/posts/{filename}.ts and PR"))
    route_slug = ts.slug or filename
    if ts.canonical_url and base in ts.canonical_url:
        url = ts.canonical_url
    elif ts.category:
        url = f"{base}/blog/{ts.category.lower()}/{route_slug}"
    else:
        url = f"{base}/blog/{route_slug}"
    code = _http_status(url)
    api_slugs = _api_slugs(base)
    in_api = (api_slugs is not None) and (route_slug in api_slugs)
    status_note = f"ts.status={ts.status}"
    if code == 200:
        api_note = " · in API" if in_api else (" · not in API" if api_slugs is not None else "")
        return StageResult(name, "passed",
                           detail=f"{url} → 200 · {status_note}{api_note}")
    if ts.status == "published" and in_api:
        code_str = "?" if code is None else str(code)
        return StageResult(name, "passed",
                           detail=(f"{url} → {code_str} server-side · {status_note} · in API "
                                   "(SPA live; prerender/unfurl is separate)"))
    code_str = "?" if code is None else str(code)
    if ts.status == "queued":
        # publishedAt should auto-flip status:queued → status:published on the SSG.
        # When that doesn't fire, the post is stranded.
        return StageResult(name, "failed",
                           detail=f"{url} → {code_str} · {status_note} (SSG didn't auto-publish)",
                           next_action=(f"ping Idan: '{label}: {route_slug} is status:queued in .ts "
                                        f"but route 404 — auto-publish from publishedAt didn't fire'"))
    if ts.status == "published":
        return StageResult(name, "failed",
                           detail=f"{url} → {code_str} · {status_note} but route 404 (build cache lag?)",
                           next_action=f"ping Idan: '{label} build needs to pick up `{route_slug}` — status:published, route 404'")
    # Unknown / unparseable
    return StageResult(name, "failed",
                       detail=f"{url} → {code_str} · ts.status={ts.status or 'unparseable'}",
                       next_action=f"inspect web/src/constants/blog/posts/{filename}.ts on origin/{ts.branch}")


def _downgrade_spa_live_false_negative(entry, stage: StageResult) -> StageResult:
    """Treat SPA-rendered published posts as live when zpub deploy gate is passed.

    zergai.com currently serves some client-rendered blog routes with a
    server-side 404. That is an unfurl/prerender bug, not proof the post is not
    live to humans. Keep that work visible elsewhere; do not block the content
    pipeline on the false negative.
    """
    if stage.state == "passed":
        return stage
    if entry.status == "published" and entry.gates.get("prod_deployed") == "passed":
        if stage.name == "live_on_dev":
            return StageResult(
                stage.name,
                "n_a",
                detail=f"prod is published/deployed; dev route check is non-blocking. Last check: {stage.detail}",
            )
        return StageResult(
            stage.name,
            "passed",
            detail=f"{stage.detail} (SPA live per zpub prod_deployed; prerender/unfurl tracked separately)",
        )
    return stage


# ---------- Top-level ----------

def check_pipeline(entry) -> PipelineState:
    filename = derive_content_filename(entry)
    ts_dev = _read_ts_meta(filename, "development") if filename else TsMeta(branch="development", present=False)
    ts_main = _read_ts_meta(filename, "main") if filename else TsMeta(branch="main", present=False)
    # Use route slug from main (or dev if not on main) for cache key / display.
    slug = ts_main.slug or ts_dev.slug or filename
    stages: list[StageResult] = []
    stages.append(_stage_drafted(entry, filename))
    stages.append(_stage_gates(entry))
    stages.append(_stage_on_branch(filename, ts_dev, "development"))
    stages.append(_downgrade_spa_live_false_negative(entry, _stage_live(filename, ts_dev, DEV_BASE, "dev")))
    stages.append(_stage_on_branch(filename, ts_main, "main"))
    stages.append(_downgrade_spa_live_false_negative(entry, _stage_live(filename, ts_main, PROD_BASE, "prod")))

    highest = -1
    next_blocker = None
    for i, s in enumerate(stages):
        if s.state in ("passed", "n_a"):
            highest = i
        else:
            next_blocker = s.next_action or f"{STAGE_LABELS[i][1]}: {s.detail}"
            break
    return PipelineState(
        entry_id=entry.id,
        slug=slug,
        stages=stages,
        highest_completed=highest,
        next_blocker=next_blocker,
        checked_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    )


def render_status(state: PipelineState, title: str = "") -> str:
    """Single-entry detailed render."""
    out = [f"{state.entry_id}  {title}".rstrip()]
    out.append(f"slug: {state.slug or '(none)'}")
    out.append("")
    for i, (name, _label) in enumerate(STAGE_LABELS):
        s = state.stages[i]
        mark = {"passed": "✓", "failed": "✗", "n_a": "·", "unknown": "?"}[s.state]
        line = f"  {mark} {name:<16} {s.detail}"
        out.append(line)
        if s.next_action and s.state != "passed":
            out.append(f"      → {s.next_action}")
    out.append("")
    if state.highest_completed == len(STAGE_LABELS) - 1:
        out.append("→ LIVE ON PROD")
    elif state.next_blocker:
        out.append(f"→ next: {state.next_blocker}")
    out.append(f"  (checked {state.checked_at})")
    return "\n".join(out)


# ---------- Cache I/O ----------

def cache_path(pub_dir: Path) -> Path:
    return pub_dir / "_meta" / "pipeline.json"


def load_cache(pub_dir: Path) -> dict[str, dict[str, Any]]:
    p = cache_path(pub_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return {}


def save_cache(pub_dir: Path, states: dict[str, PipelineState]) -> Path:
    p = cache_path(pub_dir)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "_generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "_schema": 1,
        "entries": {k: v.as_dict() for k, v in states.items()},
    }
    p.write_text(json.dumps(payload, indent=2, sort_keys=True))
    return p
