#!/usr/bin/env python3
"""
Import Apple Notes into the Obsidian vault.
Uses AppleScript to read notes and writes them as markdown files.

Usage: python3 apple_notes_import.py [--force]
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

VAULT = Path("/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg")
IMPORT_DIR = VAULT / "Notes" / "Apple Notes"
TODAY = datetime.now().strftime("%Y-%m-%d")

SKIP_FOLDERS = {"Recently Deleted"}


def slugify(text):
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[-\s]+', '-', text)
    return text.strip('-').lower()[:80]


def run_applescript(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(r.stderr.strip())
    return r.stdout.strip()


def get_folders():
    script = """
tell application "Notes"
    set output to ""
    repeat with f in folders
        set output to output & name of f & "\n"
    end repeat
    return output
end tell
"""
    raw = run_applescript(script)
    return [f.strip() for f in raw.splitlines() if f.strip()]


def get_notes_in_folder(folder_name):
    safe_folder = folder_name.replace('"', '\\"')
    script = f"""
tell application "Notes"
    set output to ""
    repeat with f in folders
        if name of f is "{safe_folder}" then
            repeat with n in notes of f
                set output to output & (name of n) & "|||" & (id of n) & "\n"
            end repeat
        end if
    end repeat
    return output
end tell
"""
    raw = run_applescript(script)
    if not raw or raw == "missing value":
        return []
    notes = []
    for item in raw.splitlines():
        item = item.strip()
        if "|||" in item:
            parts = item.split("|||")
            notes.append({"title": parts[0].strip(), "id": parts[1].strip()})
    return notes


def get_note_content(note_id):
    # Escape the note ID for AppleScript
    safe_id = note_id.replace('"', '\\"')
    script = f"""
tell application "Notes"
    set n to note id "{safe_id}"
    set noteBody to plaintext of n
    set noteDate to modification date of n
    return (noteDate as string) & "|||" & noteBody
end tell
"""
    raw = run_applescript(script)
    if "|||" in raw:
        date_str, body = raw.split("|||", 1)
        return date_str.strip(), body.strip()
    return "", raw.strip()


def html_to_text(text):
    """Basic cleanup of any HTML tags that leak through."""
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r'&nbsp;', ' ', text)
    text = re.sub(r'&amp;', '&', text)
    text = re.sub(r'&lt;', '<', text)
    text = re.sub(r'&gt;', '>', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--folder", help="Only import a specific folder")
    args = parser.parse_args()

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
            note_id = note["id"]
            fname = folder_dir / f"{slugify(title)}.md"

            if fname.exists() and not args.force:
                total_skipped += 1
                continue

            try:
                mod_date, body = get_note_content(note_id)
                body = html_to_text(body)

                content = (
                    f"---\n"
                    f"created: {TODAY}\n"
                    f"source: apple-notes-import\n"
                    f"folder: {folder}\n"
                    f"modified: {mod_date}\n"
                    f"---\n\n"
                    f"# {title}\n\n"
                    f"{body}\n"
                )
                fname.write_text(content)
                print(f"  ✓ {title[:60]}")
                total_saved += 1
            except Exception as e:
                print(f"  ✗ {title[:60]} — {e}")

    print(f"\nDone: {total_saved} imported, {total_skipped} skipped (already exist).")
    print(f"Location: {IMPORT_DIR}")


if __name__ == "__main__":
    main()
