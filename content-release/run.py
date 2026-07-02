#!/usr/bin/env python3
"""content-release — post-publish content release orchestrator.

Verbs:
  release <slug>   — full 10-step loop (resolve → scrape → download → crop → assemble → render → version → archive → zpub flip)
  status <slug>    — read-only status
  assets <slug>    — steps 1-4 only (resolve + scrape + download + crop)
  audit <slug>     — re-audit latest pack

See SKILL.md for the full flow + non-goals.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path.home() / ".config" / "zerg" / "lib"))
from vault_path import zerg_root  # canonical vault resolver (was hardcoded iCloud — now a near-empty shell)
VAULT = zerg_root()
WRITING = VAULT / "MattZerg/Writing"
EXPORTS = VAULT / "MattZerg/Writing/exports"
COLLATERAL = VAULT / "MattZerg/Brand/assets/collateral/launch-packs"

CONFIG = Path.home() / ".config" / "zerg"
URL_RESOLVER = CONFIG / "zergai_blog_url.py"
CROP = CONFIG / "crop_image_padding.py"
AUDIT = CONFIG / "audit_pack.py"
RENDER = Path.home() / ".claude" / "skills" / "document-styling-skill" / "render.py"


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kw)


def _lock_preflight(slug: str, allow_unlocked: bool) -> int:
    """Verify the article is locked before assembling derivative artifacts.

    Per `feedback_approved_posts_locked.md` + the agents-that-remember regression:
    content-release should only run AGAINST a locked, approved canonical. If the
    article isn't locked yet, the user is releasing too early — print a clear
    error and bail (unless --allow-unlocked is passed).

    Also verifies all HIGH-severity findings have status `applied` so we don't
    ship a pack that contradicts review work.
    """
    try:
        import sys as _sys
        _sys.path.insert(0, str(Path.home() / ".config" / "zerg" / "lib"))
        import article_lock as _al  # type: ignore
    except Exception as e:  # noqa: BLE001
        print(f"  WARN: lock preflight skipped (library load failed: {e})", file=sys.stderr)
        return 0

    approval = _al.read_approval(slug)
    if not approval or not approval.get("locked"):
        if allow_unlocked:
            print(f"  WARN: {slug} is NOT locked. Continuing anyway because --allow-unlocked was passed.")
            return 0
        print(f"FAIL: {slug} is not locked. Run `zerg_approve.py lock {slug} --by idan|matt "
              f"--source ...` after Idan's signoff, then re-run release.\n"
              f"(Override with --allow-unlocked for emergencies.)", file=sys.stderr)
        return 4

    findings = _al.read_findings(slug)
    high_unapplied = [
        f for f in findings
        if (f.get("severity") in ("high", "HIGH"))
        and f.get("status") not in ("applied", "wontfix", "duplicate")
    ]
    if high_unapplied:
        if allow_unlocked:
            print(f"  WARN: {len(high_unapplied)} HIGH finding(s) without status=applied — "
                  f"--allow-unlocked overrides this gate.")
            return 0
        print(f"FAIL: {len(high_unapplied)} HIGH-severity finding(s) on {slug} are not applied. "
              f"Either apply them or mark them wontfix/duplicate in the ledger:", file=sys.stderr)
        for f in high_unapplied[:5]:
            tag = f.get("tag", "?")
            text = (f.get("finding") or "")[:140]
            print(f"  - [{tag}] {text}", file=sys.stderr)
        print(f"(Override with --allow-unlocked for emergencies.)", file=sys.stderr)
        return 4

    print(f"  [lock-preflight] {slug} locked by {approval.get('locked_by')} "
          f"at {approval.get('locked_at')}; HIGH findings clean.")
    return 0


def resolve_url(slug: str) -> dict:
    out = run(["python3", URL_RESOLVER, slug, "--check-live", "--json"])
    try:
        rec = json.loads(out.stdout)
    except json.JSONDecodeError:
        rec = {"slug": slug, "url": None, "error": "resolver did not return JSON",
               "stderr": out.stderr}
    return rec


def scrape_live(url: str, out_dir: Path) -> dict:
    """Scrape the live page via chrome-devtools-mcp from the parent assistant.

    This skill is a CLI — it can't call MCP tools directly. So when invoked from a
    Claude session, this function emits a clear instruction for the assistant to
    perform the scrape and re-invoke with --scraped-from <path-to-saved-md>.
    """
    out_md = out_dir / "atr-live-body.md"
    if out_md.is_file():
        return {"ok": True, "path": str(out_md), "from_cache": True}
    return {"ok": False, "needs_scrape": True, "url": url,
            "instruction": (f"Live scrape required. Assistant should: (1) navigate Chrome to {url}, "
                            f"(2) extract title/author/publishedTime/body/imagery via evaluate_script, "
                            f"(3) write the canonical markdown to {out_md}, (4) re-invoke this skill.")}


def download_imagery(out_dir: Path, image_urls: list[str], ua: str) -> list[Path]:
    imagery = out_dir / "imagery"
    imagery.mkdir(exist_ok=True, parents=True)
    paths = []
    for u in image_urls:
        if u.startswith("/"):
            u = "https://zergai.com" + u
        name = u.split("/")[-1].split("?")[0]
        dst = imagery / name
        if not dst.is_file():
            run(["/usr/bin/curl", "-sSL", "-A", ua, u, "-o", str(dst)])
        paths.append(dst)
    return paths


def crop_imagery(imagery_dir: Path) -> dict:
    out = {"cropped": [], "untouched": []}
    for p in imagery_dir.glob("*"):
        if p.suffix.lower() not in (".png", ".jpg", ".jpeg"):
            continue
        r = run(["python3", CROP, str(p), "--only-light", "--tolerance", "6"])
        msg = (r.stdout + r.stderr).strip()
        if "cropped" in msg:
            out["cropped"].append({"name": p.name, "msg": msg})
        else:
            out["untouched"].append(p.name)
    return out


def find_social_pack(slug: str) -> Path | None:
    candidates = list(WRITING.glob(f"{slug}-social-*.md"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def existing_pack_versions(slug: str) -> list[tuple[int, Path]]:
    pat = re.compile(rf"^{re.escape(slug)}-pack-v(\d+)-\d{{4}}-\d{{2}}-\d{{2}}\.pdf$")
    out = []
    for d in (EXPORTS, COLLATERAL, Path.home() / "Downloads"):
        if not d.is_dir():
            continue
        for f in d.iterdir():
            m = pat.match(f.name)
            if m:
                out.append((int(m.group(1)), f))
    return sorted(out, key=lambda t: t[0])


def next_pack_version(slug: str) -> int:
    versions = existing_pack_versions(slug)
    return max([v for v, _ in versions], default=0) + 1


def cmd_status(slug: str) -> int:
    print(f"=== content-release status: {slug} ===\n")
    rec = resolve_url(slug)
    if rec.get("url"):
        print(f"  canonical URL: {rec['url']}")
        print(f"  manifest source: {rec.get('source')}")
        print(f"  manifest status: {rec.get('status')}")
        live = rec.get("live") or {}
        print(f"  live HTTP: {live.get('http_status', '?')}")
    else:
        print(f"  ERROR: {rec.get('error', 'no URL resolved')}")
    print()

    social = find_social_pack(slug)
    print(f"  approved social pack: {social.name if social else '(not found)'}")
    print()

    versions = existing_pack_versions(slug)
    if versions:
        print(f"  existing pack versions:")
        for v, f in versions:
            print(f"    v{v}: {f}")
    else:
        print("  existing pack versions: (none)")
    print()

    # zpub status (best-effort)
    zpub = shutil.which("zpub")
    if zpub:
        r = run([zpub, "show", f"pub-{slug}"])
        if r.returncode == 0:
            print("  zpub:")
            for line in r.stdout.strip().splitlines()[:8]:
                print(f"    {line}")
    return 0


def cmd_assets(slug: str, out_dir: Path, force_not_live: bool, ua: str) -> int:
    out_dir.mkdir(exist_ok=True, parents=True)
    rec = resolve_url(slug)
    if not rec.get("url"):
        print(f"FAIL: {rec.get('error')}", file=sys.stderr)
        return 2

    live_status = (rec.get("live") or {}).get("http_status")
    if live_status != 200 and not force_not_live:
        print(f"WARN: live URL returns HTTP {live_status} (use --force-not-live to proceed)", file=sys.stderr)

    print(f"resolved: {rec['url']}")
    print(f"manifest: {rec.get('source')}  status={rec.get('status')}  live HTTP={live_status}\n")

    scrape = scrape_live(rec["url"], out_dir)
    if scrape.get("needs_scrape"):
        print("=== NEXT STEP (manual; assistant continues from here) ===")
        print(scrape["instruction"])
        return 3

    print(f"scrape cached: {scrape['path']}")
    return 0


def cmd_audit(slug: str) -> int:
    versions = existing_pack_versions(slug)
    if not versions:
        print(f"no pack versions found for {slug}", file=sys.stderr)
        return 2
    latest = versions[-1][1]
    print(f"auditing: {latest}\n")
    return subprocess.run(["python3", str(AUDIT), str(latest)]).returncode


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("verb", choices=("release", "status", "assets", "audit"))
    ap.add_argument("slug")
    ap.add_argument("--out-dir", default=None)
    ap.add_argument("--force-not-live", action="store_true")
    ap.add_argument("--theme", default=None)
    ap.add_argument("--no-zpub", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--allow-unlocked", action="store_true",
                    help="Bypass the lock-preflight gate. Only for emergencies.")
    args = ap.parse_args()

    out_dir = Path(args.out_dir).expanduser() if args.out_dir else Path.home() / "Downloads" / f"{args.slug}-release"

    if args.verb == "status":
        return cmd_status(args.slug)
    if args.verb == "assets":
        ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"
        return cmd_assets(args.slug, out_dir, args.force_not_live, ua)
    if args.verb == "audit":
        return cmd_audit(args.slug)
    if args.verb == "release":
        print(f"=== release {args.slug} ===\n")
        # Step 0 — lock preflight. The article MUST be locked before any
        # derivative artifact ships. This is the structural enforcement of
        # `feedback_approved_posts_locked.md`; previously the rule was only
        # documented and got bypassed.
        rc = _lock_preflight(args.slug, allow_unlocked=args.allow_unlocked)
        if rc != 0:
            return rc
        # Step 1
        rec = resolve_url(args.slug)
        if not rec.get("url"):
            print(f"FAIL step 1 (resolve): {rec.get('error')}", file=sys.stderr)
            return 2
        print(f"[1] resolved: {rec['url']}  ({rec.get('status')})\n")
        # Step 2-4 partial — surface scrape requirement
        out_dir.mkdir(exist_ok=True, parents=True)
        scrape = scrape_live(rec["url"], out_dir)
        if scrape.get("needs_scrape"):
            print(f"[2] scrape required — assistant continues:\n    {scrape['instruction']}")
            return 3
        print(f"[2] scrape cached: {scrape['path']}")
        # Step 5
        social = find_social_pack(args.slug)
        if not social:
            print(f"FAIL step 5 (social pack): no {WRITING}/{args.slug}-social-*.md found", file=sys.stderr)
            return 2
        print(f"[5] social pack: {social.name}")
        # Step 6-10 — full assembly + render + archive + zpub flip
        # The assembly step composes the source MD from scrape + social + asset map.
        # That's substantive enough that it deserves the parent assistant's eye —
        # halt here with a clear handoff so the assistant builds the source MD,
        # then re-invokes render via document-styling-skill (which auto-audits).
        print(f"\n[6] assemble pack source MD at {out_dir}/{args.slug}-pack-v{next_pack_version(args.slug)}-{_dt.date.today()}.md")
        print(f"[7] render: python3 {RENDER} <that.md> --theme <theme> --layout multi-page --no-open")
        print(f"           (auto-runs crop + audit per composite_multipage_pdf.md)")
        print(f"[8] version + stage: name as <slug>-pack-v<N>-YYYY-MM-DD.pdf; copy to:")
        print(f"      ~/Downloads/")
        print(f"      {EXPORTS}")
        print(f"      {COLLATERAL}")
        if not args.no_zpub:
            print(f"[9] zpub set pub-{args.slug} status published")
            print(f"    zpub set pub-{args.slug} gates.distribution passed (if URLs already logged)")
        print(f"[10] open Preview ONCE")
        print("\n(skill is a guide-rail orchestrator; substantive assembly happens in-session)")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
