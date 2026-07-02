#!/usr/bin/env python3
"""apple-notes-skill — import Apple Notes into the Obsidian vault and route
idea-shaped notes into the idea-backlog.

Two behaviours, both driven from Apple Notes via osascript:

1. Plain import (legacy `apple_notes_import.py` behaviour): every note → a
   markdown file under `MattZerg/Notes/Apple Notes/<folder>/`.

2. Idea routing (Phase 4.4 wiring): any note whose title starts with
   `idea:` (case-insensitive) OR whose title/body contains `#idea` is
   formatted as an idea-backlog entry and written to
   `MattZerg/Ideas/<category>/<slug>.md` via the launchd-safe vault_path
   helpers. Frontmatter matches `~/.claude/skills/idea-backlog/SKILL.md` /
   the idea schema (id, title, category, status, conviction, effort, ...).

Modes:
  list           List Apple Notes folders + note titles, flag idea-shaped
                 notes. No writes. (Safe default for previewing.)
  ideas [--dry-run] [--category C]
                 Route idea-shaped notes into the idea backlog. --dry-run
                 prints what would be written without touching the vault.
  import [--force] [--folder F]
                 Full plain import of every note (legacy behaviour).

Apple Notes access uses `osascript`, which requires the controlling process
to hold Automation permission for Notes. Under launchd / a sandboxed -p run
this can fail with a TCC permission error; the skill degrades gracefully and
prints a one-line remediation (run once interactively in Terminal.app to grant
the approval) instead of crashing.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import re
import subprocess
import sys
from pathlib import Path

# vault_path helpers (launchd-safe writes via writeback staging).
sys.path.insert(0, str(Path.home() / ".config" / "zerg"))
try:
    from vault_path import vault_write, vault_path  # noqa: F401
except Exception:  # pragma: no cover - vault helpers should exist
    vault_write = None
    vault_path = None

# Direct vault path used only by the legacy plain-import mode (interactive FDA).
VAULT = Path.home() / "Obsidian" / "Zerg" / "MattZerg"
IMPORT_DIR = VAULT / "Notes" / "Apple Notes"
TODAY = _dt.datetime.now().strftime("%Y-%m-%d")

SKIP_FOLDERS = {"Recently Deleted"}

# Idea-backlog categories (must match the idea schema / idea-backlog SKILL.md).
IDEA_CATEGORIES = {
    "zerg-product",
    "zerg-content",
    "zerg-tooling",
    "personal-venture",
    "personal-life",
    "research",
}
DEFAULT_CATEGORY = "personal-venture"

# Idea markers.
IDEA_TITLE_PREFIX = re.compile(r"^\s*idea\s*:", re.I)
IDEA_TAG = re.compile(r"#idea\b", re.I)


class NotesAccessError(RuntimeError):
    """Raised when osascript cannot reach Apple Notes (usually TCC)."""


def slugify(text: str) -> str:
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-").lower()[:80] or "untitled"


def run_applescript(script: str) -> str:
    r = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True
    )
    if r.returncode != 0:
        err = (r.stderr or "").strip()
        low = err.lower()
        if (
            "not allowed" in low
            or "not authori" in low
            or "-1743" in err
            or "execution error" in low
            and "notes" in low
        ):
            raise NotesAccessError(err)
        raise RuntimeError(err or f"osascript exited {r.returncode}")
    return r.stdout.strip()


def get_folders() -> list[str]:
    script = (
        'tell application "Notes"\n'
        "    set output to \"\"\n"
        "    repeat with f in folders\n"
        '        set output to output & name of f & "\\n"\n'
        "    end repeat\n"
        "    return output\n"
        "end tell"
    )
    raw = run_applescript(script)
    return [f.strip() for f in raw.splitlines() if f.strip()]


def get_notes_in_folder(folder_name: str) -> list[dict]:
    safe_folder = folder_name.replace('"', '\\"')
    script = (
        'tell application "Notes"\n'
        "    set output to \"\"\n"
        "    repeat with f in folders\n"
        f'        if name of f is "{safe_folder}" then\n'
        "            repeat with n in notes of f\n"
        '                set output to output & (name of n) & "|||" & (id of n) & "\\n"\n'
        "            end repeat\n"
        "        end if\n"
        "    end repeat\n"
        "    return output\n"
        "end tell"
    )
    raw = run_applescript(script)
    if not raw or raw == "missing value":
        return []
    notes = []
    for item in raw.splitlines():
        item = item.strip()
        if "|||" in item:
            title, nid = item.split("|||", 1)
            notes.append({"title": title.strip(), "id": nid.strip()})
    return notes


def get_note_content(note_id: str) -> tuple[str, str]:
    safe_id = note_id.replace('"', '\\"')
    script = (
        'tell application "Notes"\n'
        f'    set n to note id "{safe_id}"\n'
        "    set noteBody to plaintext of n\n"
        "    set noteDate to modification date of n\n"
        '    return (noteDate as string) & "|||" & noteBody\n'
        "end tell"
    )
    raw = run_applescript(script)
    if "|||" in raw:
        date_str, body = raw.split("|||", 1)
        return date_str.strip(), body.strip()
    return "", raw.strip()


def html_to_text(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- idea routing ----------------------------------------------------------


def is_idea_note(title: str, body: str) -> bool:
    if IDEA_TITLE_PREFIX.search(title or ""):
        return True
    if IDEA_TAG.search(title or "") or IDEA_TAG.search(body or ""):
        return True
    return False


def pick_category(folder: str, title: str, body: str) -> str:
    """Best-effort category inference from folder name + content keywords."""
    blob = f"{folder} {title} {body}".lower()
    if any(k in blob for k in ("blog", "post", "content", "newsletter", "video")):
        return "zerg-content"
    if any(k in blob for k in ("skill", "tool", "automation", "script", "cron", "hook")):
        return "zerg-tooling"
    if any(k in blob for k in ("product", "feature", "app", "zerg", "launch")):
        return "zerg-product"
    if any(k in blob for k in ("research", "paper", "study", "experiment")):
        return "research"
    if any(k in blob for k in ("invest", "venture", "startup", "company", "fund")):
        return "personal-venture"
    return DEFAULT_CATEGORY


def clean_idea_title(title: str) -> str:
    t = IDEA_TITLE_PREFIX.sub("", title or "").strip()
    t = IDEA_TAG.sub("", t).strip()
    return t or "Untitled idea"


def _yaml_list(items: list[str]) -> str:
    if not items:
        return "[]"
    return "[" + ", ".join(items) + "]"


def build_idea_markdown(title: str, body: str, folder: str, mod_date: str,
                        category: str) -> tuple[str, str]:
    """Return (slug, markdown) for an idea-backlog file."""
    clean_title = clean_idea_title(title)
    slug = slugify(clean_title)
    idea_id = f"idea-{TODAY}-{slug}"[:90]
    body = html_to_text(body)
    # First non-empty body line → one-line pitch.
    pitch = ""
    for line in body.splitlines():
        if line.strip():
            pitch = line.strip()
            break
    excerpt = body.strip()[:600]
    fm = (
        "---\n"
        f"id: {idea_id}\n"
        f"title: {clean_title}\n"
        f"category: {category}\n"
        f"subcategory: apple-notes\n"
        f"tags: {_yaml_list(['apple-notes', 'idea'])}\n"
        "status: raw\n"
        "conviction: medium\n"
        "effort: unknown\n"
        "time_estimate: unknown\n"
        "cost_estimate: unknown\n"
        f"created: {TODAY}\n"
        f"last_touched: {TODAY}\n"
        f"sources:\n  - \"[[Notes/Apple Notes/{folder}]]\"\n"
        "related: []\n"
        "task_link: null\n"
        f"source: apple-notes\n"
        f"note_modified: {mod_date}\n"
        "---\n\n"
    )
    md = (
        f"{fm}"
        f"## Idea\n{pitch or clean_title}\n\n"
        f"## Why interesting\n_Captured from Apple Notes — review and expand._\n\n"
        f"## Open questions\n- \n\n"
        f"## Source excerpt\n> {excerpt}\n"
    )
    return slug, md


# --- modes -----------------------------------------------------------------


def mode_list(args) -> int:
    folders = get_folders()
    print(f"Found {len(folders)} Apple Notes folders\n")
    total = 0
    idea_count = 0
    for folder in folders:
        if folder in SKIP_FOLDERS:
            continue
        if args.folder and folder != args.folder:
            continue
        notes = get_notes_in_folder(folder)
        if not notes:
            continue
        print(f"[{folder}] — {len(notes)} notes")
        for n in notes:
            total += 1
            title = n["title"] or "Untitled"
            # Cheap idea check on title only (avoid per-note content fetch here);
            # body-#idea notes are still caught in `ideas` mode.
            flag = ""
            if IDEA_TITLE_PREFIX.search(title) or IDEA_TAG.search(title):
                idea_count += 1
                flag = "  <- idea"
            print(f"  - {title[:70]}{flag}")
    print(f"\n{total} notes total; {idea_count} idea-shaped by title.")
    print("Run `ideas --dry-run` to preview idea-backlog routing (scans bodies too).")
    return 0


def mode_ideas(args) -> int:
    if vault_write is None and not args.dry_run:
        print("[error] vault_path helpers unavailable; cannot write to vault.",
              file=sys.stderr)
        return 1
    folders = get_folders()
    routed = 0
    scanned = 0
    for folder in folders:
        if folder in SKIP_FOLDERS:
            continue
        if args.folder and folder != args.folder:
            continue
        notes = get_notes_in_folder(folder)
        for n in notes:
            title = n["title"] or "Untitled"
            try:
                mod_date, body = get_note_content(n["id"])
            except NotesAccessError:
                raise
            except Exception:
                mod_date, body = "", ""
            scanned += 1
            if not is_idea_note(title, body):
                continue
            category = args.category or pick_category(folder, title, body)
            if category not in IDEA_CATEGORIES:
                category = DEFAULT_CATEGORY
            slug, md = build_idea_markdown(title, body, folder, mod_date, category)
            rel = f"Ideas/{category}/{slug}.md"
            if args.dry_run:
                print(f"[dry-run] would write MattZerg/{rel}  (title={clean_idea_title(title)!r})")
                routed += 1
                continue
            out = vault_write(rel, md)
            print(f"  ✓ {clean_idea_title(title)[:60]} → {category} ({out.name})")
            routed += 1
    verb = "would route" if args.dry_run else "routed"
    print(f"\nScanned {scanned} notes; {verb} {routed} idea-shaped notes to Ideas/.")
    return 0


def mode_import(args) -> int:
    IMPORT_DIR.mkdir(parents=True, exist_ok=True)
    folders = get_folders()
    print(f"Found {len(folders)} folders\n")
    total_saved = 0
    total_skipped = 0
    for folder in folders:
        if folder in SKIP_FOLDERS:
            continue
        if args.folder and folder != args.folder:
            continue
        notes = get_notes_in_folder(folder)
        if not notes:
            continue
        folder_dir = IMPORT_DIR / slugify(folder)
        folder_dir.mkdir(parents=True, exist_ok=True)
        print(f"[{folder}] — {len(notes)} notes")
        for note in notes:
            title = note["title"] or "Untitled"
            fname = folder_dir / f"{slugify(title)}.md"
            if fname.exists() and not args.force:
                total_skipped += 1
                continue
            try:
                mod_date, body = get_note_content(note["id"])
                body = html_to_text(body)
                content = (
                    "---\n"
                    f"created: {TODAY}\n"
                    "source: apple-notes-import\n"
                    f"folder: {folder}\n"
                    f"modified: {mod_date}\n"
                    "---\n\n"
                    f"# {title}\n\n"
                    f"{body}\n"
                )
                fname.write_text(content)
                print(f"  ✓ {title[:60]}")
                total_saved += 1
            except NotesAccessError:
                raise
            except Exception as e:  # noqa: BLE001
                print(f"  ✗ {title[:60]} — {e}")
    print(f"\nDone: {total_saved} imported, {total_skipped} skipped (already exist).")
    print(f"Location: {IMPORT_DIR}")
    return 0


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="apple-notes-skill")
    sub = ap.add_subparsers(dest="cmd")

    p_list = sub.add_parser("list", help="list folders + note titles (no writes)")
    p_list.add_argument("--folder")

    p_ideas = sub.add_parser("ideas", help="route idea-shaped notes to idea-backlog")
    p_ideas.add_argument("--dry-run", action="store_true")
    p_ideas.add_argument("--folder")
    p_ideas.add_argument("--category", choices=sorted(IDEA_CATEGORIES))

    p_import = sub.add_parser("import", help="plain import every note to Notes/Apple Notes/")
    p_import.add_argument("--force", action="store_true")
    p_import.add_argument("--folder")

    args = ap.parse_args(argv)
    if not args.cmd:
        args = ap.parse_args(["list"])

    try:
        if args.cmd == "list":
            return mode_list(args)
        if args.cmd == "ideas":
            return mode_ideas(args)
        if args.cmd == "import":
            return mode_import(args)
    except NotesAccessError as e:
        print(
            "[apple-notes-skill] Apple Notes access denied (TCC/Automation).\n"
            "  Reason: " + str(e)[:200] + "\n"
            "  Fix (one-time, interactive): run this script once in Terminal.app —\n"
            "    /usr/bin/python3 ~/.claude/skills/apple-notes-skill/run.py list\n"
            "  and approve the 'control Notes' prompt. Then re-run.\n",
            file=sys.stderr,
        )
        return 3
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
