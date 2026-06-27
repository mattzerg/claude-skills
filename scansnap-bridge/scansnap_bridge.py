#!/usr/bin/env python3
"""
ScanSnap Bridge - Auto-process scans from ScanSnap iX1500 into the Obsidian vault.

Watches ~/scansnap-inbox/ for new PDFs. For each scan:
  1. Waits for file to stabilize (avoids mid-write processing).
  2. Runs ocrmypdf to add a searchable text layer (derivative, not modifying source).
  3. Moves the source PDF (unmodified) to ~/ScanArchive/YYYY/MM/.
  4. Extracts OCR text and spawns a Claude Code subprocess for classification.
  5. Executes the returned filing plan against the Obsidian vault.
  6. Posts a Slack DM summary.

Usage:
    python3 scansnap_bridge.py                 # Run daemon (foreground)
    python3 scansnap_bridge.py --once <path>   # Process a single PDF (debugging)
    python3 scansnap_bridge.py --status        # Check daemon status
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path

# ---- Paths / config ----------------------------------------------------------

SKILL_DIR = Path(__file__).parent
PROMPT_FILE = SKILL_DIR / "prompts" / "classify.md"
LOG_FILE = SKILL_DIR / "bridge.log"
PID_FILE = SKILL_DIR / ".bridge.pid"
STATE_FILE = SKILL_DIR / ".bridge.state.json"
CONFIG_FILE = SKILL_DIR / "config.json"

HOME = Path.home()
INBOX = HOME / "scansnap-inbox"
NEEDS_REVIEW = INBOX / "_needs_review"
ARCHIVE_ROOT = HOME / "ScanArchive"
def _resolve_vault_root(sub: str = "Zerg/MattZerg") -> Path:
    """Live vault is ~/Obsidian/<sub>; the iCloud path was retired 2026-06-24.
    Prefer the live path, fall back to the legacy iCloud path only if it still exists."""
    primary = Path.home() / "Obsidian" / sub
    if primary.exists():
        return primary
    legacy = (
        Path.home()
        / "Library" / "Mobile Documents" / "iCloud~md~obsidian" / "Documents" / sub
    )
    return legacy if legacy.exists() else primary


VAULT_ROOT = _resolve_vault_root("idanbeck")

CLAUDE_BIN = shutil.which("claude") or "/Users/idanbeck/.local/bin/claude"
SLACK_SKILL = HOME / ".claude" / "skills" / "slack-skill" / "slack_skill.py"

# Defaults (overridable via config.json)
DEFAULTS = {
    "slack_target": "#automation",   # Slack channel or @user for notifications
    "slack_enabled": True,
}


def _load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            return {**DEFAULTS, **json.loads(CONFIG_FILE.read_text())}
        except Exception:
            pass
    return dict(DEFAULTS)


CONFIG = _load_config()

POLL_INTERVAL_S = 2
STABILITY_CHECKS = 3        # consecutive unchanged checks before processing
STABILITY_TIMEOUT_S = 120   # give up if never stable
CLAUDE_TIMEOUT_S = 300      # 5 min classification timeout
OCR_TIMEOUT_S = 300         # 5 min OCR timeout

# ---- Utility -----------------------------------------------------------------

def log(msg: str, level: str = "INFO") -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {level}: {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            return {}
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def ensure_dirs() -> None:
    INBOX.mkdir(parents=True, exist_ok=True)
    NEEDS_REVIEW.mkdir(parents=True, exist_ok=True)
    ARCHIVE_ROOT.mkdir(parents=True, exist_ok=True)


def slugify(s: str, maxlen: int = 40) -> str:
    s = re.sub(r"[^\w\s-]", "", s).strip().lower()
    s = re.sub(r"[-\s]+", "-", s)
    return s[:maxlen] or "scan"


# ---- File stability check ----------------------------------------------------

def is_stable(path: Path, state: dict) -> bool:
    """Return True when file size has been unchanged for STABILITY_CHECKS polls."""
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return False

    key = str(path)
    entry = state.get(key, {"size": -1, "count": 0, "first_seen": time.time()})

    if size == entry["size"] and size > 0:
        entry["count"] += 1
    else:
        entry["size"] = size
        entry["count"] = 1
        entry["first_seen"] = entry.get("first_seen", time.time())

    state[key] = entry
    save_state(state)

    if entry["count"] >= STABILITY_CHECKS:
        return True

    # Timeout safety valve
    if time.time() - entry["first_seen"] > STABILITY_TIMEOUT_S:
        log(f"Stability timeout for {path.name}; processing anyway", "WARN")
        return True

    return False


# ---- Page rendering ----------------------------------------------------------

def render_pdf_to_images(pdf: Path, out_dir: Path, dpi: int = 200) -> list[Path]:
    """Convert each PDF page to a PNG via pdftoppm. Returns list of image paths.

    Claude Vision is used directly on these images — no OCR step. Handwriting,
    diagrams, mixed layouts all become first-class inputs.
    """
    if not shutil.which("pdftoppm"):
        log("pdftoppm not available (install poppler)", "ERROR")
        return []

    out_dir.mkdir(parents=True, exist_ok=True)
    prefix = out_dir / "page"
    try:
        subprocess.run(
            ["pdftoppm", "-png", "-r", str(dpi), str(pdf), str(prefix)],
            check=True, capture_output=True, timeout=120,
        )
    except subprocess.CalledProcessError as e:
        log(f"pdftoppm failed: {e.stderr.decode()[:500] if e.stderr else e}", "ERROR")
        return []
    except subprocess.TimeoutExpired:
        log("pdftoppm timed out", "ERROR")
        return []

    # pdftoppm names files page-1.png, page-2.png, ... (or page-01.png for 10+)
    pages = sorted(out_dir.glob("page-*.png"))
    return pages


# ---- Archive -----------------------------------------------------------------

def archive_source(source: Path, scan_ts: datetime) -> Path:
    """Move the unmodified source into ~/ScanArchive/YYYY/MM/. Returns archive path."""
    month_dir = ARCHIVE_ROOT / f"{scan_ts:%Y}" / f"{scan_ts:%m}"
    month_dir.mkdir(parents=True, exist_ok=True)
    archive_path = month_dir / f"{scan_ts:%Y-%m-%d_%H-%M-%S}.pdf"
    # Collision handling
    i = 1
    while archive_path.exists():
        archive_path = month_dir / f"{scan_ts:%Y-%m-%d_%H-%M-%S}_{i}.pdf"
        i += 1
    shutil.move(str(source), str(archive_path))
    return archive_path


# ---- Claude classification ---------------------------------------------------

def build_prompt(archive_path: Path, scan_ts: datetime, image_paths: list[Path]) -> str:
    """Build the classification prompt. Image paths are embedded as @ references
    so Claude Code CLI attaches them as vision inputs."""
    template = PROMPT_FILE.read_text()
    refs = "\n".join(f"@{p}" for p in image_paths)
    return (refs + "\n\n" + template
            .replace("{ARCHIVE_PATH}", str(archive_path))
            .replace("{SCAN_TIMESTAMP}", scan_ts.isoformat())
            .replace("{PAGE_COUNT}", str(len(image_paths))))


def _call_claude(prompt: str) -> str:
    """Raw Claude subprocess call. Prompt is piped via stdin so `@path` image
    references resolve reliably (argv path doesn't always attach images).
    Returns stdout (possibly empty on error).
    """
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "-p", "--dangerously-skip-permissions"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=CLAUDE_TIMEOUT_S,
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        log("Claude subprocess timed out", "ERROR")
        return ""
    except FileNotFoundError:
        log(f"Claude binary not found at {CLAUDE_BIN}", "ERROR")
        return ""


def _parse_json_from_output(output: str):
    """Try to locate and parse a JSON object in free-form Claude output.

    Returns (parsed_dict, cleaned_json_str, error_msg). Only parsed_dict is non-None on success.
    """
    output = output.strip()
    # Strip code fences
    output = re.sub(r"^```(?:json)?\s*", "", output)
    output = re.sub(r"\s*```$", "", output)
    # Strip <thinking> blocks
    output = re.sub(r"<thinking>.*?</thinking>\s*", "", output, flags=re.DOTALL)

    first_brace = output.find("{")
    last_brace = output.rfind("}")
    if first_brace == -1 or last_brace == -1:
        return None, "", "no JSON object in output"

    json_str = output[first_brace:last_brace + 1]
    try:
        return json.loads(json_str), json_str, ""
    except json.JSONDecodeError as e:
        return None, json_str, str(e)


def _dump_debug(label: str, content: str) -> Path:
    """Save raw output for post-mortem. Returns the debug file path."""
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    debug_path = SKILL_DIR / f"debug_{label}_{ts}.txt"
    debug_path.write_text(content)
    return debug_path


def classify_with_claude(prompt: str):
    """Run claude -p, parse JSON. Retries once with a corrective prompt on parse failure."""
    output = _call_claude(prompt)
    if not output:
        return None

    parsed, json_str, err = _parse_json_from_output(output)
    if parsed is not None:
        return parsed

    debug_path = _dump_debug("attempt1", output)
    log(f"Parse attempt 1 failed ({err}). Full output saved: {debug_path}", "WARN")

    # Retry once with an explicit fix prompt. Include the error and the broken JSON.
    retry_prompt = (
        "Your previous response failed to parse as JSON with this error:\n"
        f"  {err}\n\n"
        "Here was your (broken) output:\n"
        "```\n"
        f"{json_str[:10000]}\n"
        "```\n\n"
        "Return the same classification, but now emit STRICT valid JSON. "
        "Critical rules:\n"
        "  - Escape all double quotes INSIDE string values as \\\"\n"
        "  - Escape all backslashes as \\\\\n"
        "  - Escape all newlines inside strings as \\n\n"
        "  - Do NOT include raw control characters inside strings\n"
        "  - Do NOT wrap in markdown fences\n"
        "  - Emit ONLY the JSON object, nothing else.\n"
    )
    output2 = _call_claude(retry_prompt)
    if not output2:
        return None

    parsed2, json_str2, err2 = _parse_json_from_output(output2)
    if parsed2 is not None:
        log("Retry succeeded", "INFO")
        return parsed2

    debug_path2 = _dump_debug("attempt2", output2)
    log(f"Parse attempt 2 failed ({err2}). Full output saved: {debug_path2}", "ERROR")
    return None


# ---- Filing actions ----------------------------------------------------------

def resolve_vault_path(rel: str) -> Path:
    """Resolve a vault-relative path to an absolute path, safely."""
    p = (VAULT_ROOT / rel).resolve()
    vault_resolved = VAULT_ROOT.resolve()
    if not str(p).startswith(str(vault_resolved)):
        raise ValueError(f"Path {rel} escapes vault root")
    return p


def action_create_file(path: Path, content: str) -> str:
    if path.exists():
        return f"skipped create_file (exists): {path.relative_to(VAULT_ROOT)}"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)
    return f"created: {path.relative_to(VAULT_ROOT)}"


def action_append_to_file(path: Path, section: str | None, content: str) -> str:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text((f"# {path.stem}\n\n" if not content.startswith("#") else "") + content + "\n")
        return f"created + appended: {path.relative_to(VAULT_ROOT)}"

    existing = path.read_text()
    to_append = "\n" + content.rstrip() + "\n"

    if section:
        # Find the section header (case-insensitive, allow # or ##)
        pattern = re.compile(rf"^(#{{1,6}})\s*{re.escape(section)}\s*$", re.MULTILINE | re.IGNORECASE)
        m = pattern.search(existing)
        if m:
            # Find start of next section (same or higher level)
            level = len(m.group(1))
            after = existing[m.end():]
            next_header = re.search(rf"^#{{1,{level}}}\s", after, re.MULTILINE)
            insert_pos = m.end() + (next_header.start() if next_header else len(after))
            new_content = existing[:insert_pos].rstrip() + to_append + existing[insert_pos:]
            path.write_text(new_content)
            return f"appended to section [{section}]: {path.relative_to(VAULT_ROOT)}"

    # No section match — append to end
    path.write_text(existing.rstrip() + to_append)
    return f"appended: {path.relative_to(VAULT_ROOT)}"


def action_update_frontmatter(path: Path, fields: dict) -> str:
    if not path.exists():
        return f"skipped update_frontmatter (missing): {path.relative_to(VAULT_ROOT)}"
    content = path.read_text()
    if not content.startswith("---\n"):
        return f"skipped update_frontmatter (no frontmatter): {path.relative_to(VAULT_ROOT)}"
    end = content.find("\n---\n", 4)
    if end == -1:
        return f"skipped update_frontmatter (bad frontmatter): {path.relative_to(VAULT_ROOT)}"
    fm = content[4:end]
    for k, v in fields.items():
        pattern = re.compile(rf"^{re.escape(k)}\s*:.*$", re.MULTILINE)
        line = f"{k}: {json.dumps(v) if isinstance(v, (dict, list)) else v}"
        if pattern.search(fm):
            fm = pattern.sub(line, fm)
        else:
            fm = fm.rstrip() + "\n" + line + "\n"
    new = "---\n" + fm + "\n---\n" + content[end + 5:]
    path.write_text(new)
    return f"frontmatter updated: {path.relative_to(VAULT_ROOT)}"


def execute_filing_plan(plan: dict, archive_path: Path) -> tuple[list[str], list[str]]:
    """Execute filing_actions. Returns (successes, flags)."""
    successes: list[str] = []
    flags: list[str] = []

    for doc in plan.get("documents", []):
        for action in doc.get("filing_actions", []):
            atype = action.get("type")
            try:
                if atype == "create_file":
                    path = resolve_vault_path(action["path"])
                    successes.append(action_create_file(path, action["content"]))
                elif atype == "append_to_file":
                    path = resolve_vault_path(action["path"])
                    successes.append(action_append_to_file(path, action.get("section"), action["content"]))
                elif atype == "update_frontmatter":
                    path = resolve_vault_path(action["path"])
                    successes.append(action_update_frontmatter(path, action["fields"]))
                elif atype == "flag":
                    flags.append(action.get("reason", "no reason given"))
                else:
                    flags.append(f"unknown action type: {atype}")
            except Exception as e:
                flags.append(f"{atype} failed: {e}")
                log(f"Filing action error: {traceback.format_exc()}", "ERROR")

    return successes, flags


# ---- Notification ------------------------------------------------------------

def notify_slack(summary: str, archive_path: Path, successes: list[str], flags: list[str]) -> None:
    if not CONFIG.get("slack_enabled", True):
        return
    if not SLACK_SKILL.exists():
        log("Slack skill not found; skipping notification", "WARN")
        return

    target = CONFIG.get("slack_target", "#automation")

    lines = [f"*ScanSnap:* {summary}", f"_Archive:_ `{archive_path}`"]
    if successes:
        lines.append("*Filed:*")
        for s in successes:
            lines.append(f"  • {s}")
    if flags:
        lines.append("*Flagged:*")
        for f in flags:
            lines.append(f"  :warning: {f}")
    message = "\n".join(lines)

    try:
        result = subprocess.run(
            [sys.executable, str(SLACK_SKILL), "send", target, "-m", message],
            timeout=30, capture_output=True, text=True,
        )
        if result.returncode != 0:
            log(f"Slack notification failed (exit {result.returncode}): {result.stderr[:300]} stdout={result.stdout[:300]}", "WARN")
        else:
            log(f"Slack notification sent to {target}", "INFO")
    except Exception as e:
        log(f"Slack notification failed: {e}", "WARN")


# ---- Per-file processing -----------------------------------------------------

def process_pdf(source: Path) -> None:
    log(f"Processing {source.name}")
    scan_ts = datetime.fromtimestamp(source.stat().st_mtime)

    # 1. Archive source (immutable)
    try:
        archive_path = archive_source(source, scan_ts)
        log(f"Archived → {archive_path}")
    except Exception as e:
        log(f"Archive failed: {e}", "ERROR")
        return

    # 2. Render pages to PNGs for vision classification (temp dir, cleaned after)
    tmp_dir = Path(f"/tmp/scansnap_{os.getpid()}_{int(time.time())}")
    image_paths = render_pdf_to_images(archive_path, tmp_dir, dpi=300)

    if not image_paths:
        log(f"Could not render pages; moving to review: {archive_path}", "ERROR")
        notify_slack(
            summary=f"Page rendering failed for {archive_path.name}",
            archive_path=archive_path,
            successes=[],
            flags=["pdftoppm produced no images — scan may be corrupt."],
        )
        shutil.rmtree(tmp_dir, ignore_errors=True)
        return

    log(f"Rendered {len(image_paths)} page image(s) for vision classification")

    # 3. Classify with Claude Vision
    try:
        prompt = build_prompt(archive_path, scan_ts, image_paths)
        plan = classify_with_claude(prompt)
    finally:
        # Clean up temp page images regardless of outcome
        shutil.rmtree(tmp_dir, ignore_errors=True)

    if plan is None:
        log(f"Classification failed; leaving archive for review: {archive_path}", "ERROR")
        notify_slack(
            summary=f"Classification failed for {archive_path.name}",
            archive_path=archive_path,
            successes=[],
            flags=["Claude classification returned no valid plan — manual filing needed."],
        )
        return

    log(f"Plan: {plan.get('summary', '(no summary)')}")

    # 4. Execute filing actions
    successes, flags = execute_filing_plan(plan, archive_path)
    log(f"Filed {len(successes)} action(s), flagged {len(flags)}")

    # 5. Notify
    notify_slack(plan.get("summary", "Scan processed"), archive_path, successes, flags)


# ---- Daemon ------------------------------------------------------------------

_shutdown = False


def _signal_handler(signum, frame):
    global _shutdown
    _shutdown = True
    log(f"Received signal {signum}; shutting down")


def list_candidates() -> list[Path]:
    """PDFs in INBOX (not subdirs, not hidden)."""
    return sorted(p for p in INBOX.iterdir()
                  if p.is_file() and p.suffix.lower() == ".pdf" and not p.name.startswith("."))


def daemon_loop() -> None:
    ensure_dirs()
    log(f"ScanSnap bridge starting. Inbox: {INBOX}, Archive: {ARCHIVE_ROOT}")
    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    PID_FILE.write_text(str(os.getpid()))

    state = load_state()

    try:
        while not _shutdown:
            for candidate in list_candidates():
                if not candidate.exists():
                    continue
                if not is_stable(candidate, state):
                    continue

                # Remove from state tracking since we're about to move it
                state.pop(str(candidate), None)
                save_state(state)

                try:
                    process_pdf(candidate)
                except Exception as e:
                    log(f"Unhandled processing error: {traceback.format_exc()}", "ERROR")
                    # Move to _needs_review to avoid reprocessing loop
                    try:
                        dest = NEEDS_REVIEW / candidate.name
                        if candidate.exists():
                            shutil.move(str(candidate), str(dest))
                            log(f"Moved to needs_review: {dest}")
                    except Exception as move_err:
                        log(f"Could not move to needs_review: {move_err}", "ERROR")

            time.sleep(POLL_INTERVAL_S)
    finally:
        PID_FILE.unlink(missing_ok=True)
        log("ScanSnap bridge stopped")


# ---- CLI ---------------------------------------------------------------------

LAUNCHD_LABEL = "com.idanbeck.scansnap-bridge"
LAUNCHD_PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LAUNCHD_LABEL}.plist"


def _launchctl_loaded() -> bool:
    try:
        result = subprocess.run(["launchctl", "list"], capture_output=True, text=True, timeout=10)
        return LAUNCHD_LABEL in result.stdout
    except Exception:
        return False


def cmd_status() -> int:
    loaded = _launchctl_loaded()
    running = False
    pid = None
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            running = True
        except (ValueError, ProcessLookupError):
            pid = None

    print(f"launchd agent:  {'loaded' if loaded else 'not loaded'} ({LAUNCHD_LABEL})")
    print(f"daemon process: {'running (pid ' + str(pid) + ')' if running else 'not running'}")
    print(f"inbox:          {INBOX}")
    print(f"archive:        {ARCHIVE_ROOT}")
    try:
        pending = [p for p in INBOX.iterdir() if p.is_file() and p.suffix.lower() == ".pdf"]
        print(f"pending scans:  {len(pending)}")
        for p in pending:
            print(f"  - {p.name}")
    except FileNotFoundError:
        pass
    print(f"slack target:   {CONFIG.get('slack_target')} ({'enabled' if CONFIG.get('slack_enabled') else 'DISABLED'})")
    return 0 if (loaded or running) else 1


def cmd_start() -> int:
    if _launchctl_loaded():
        print("Already loaded.")
        return 0
    if not LAUNCHD_PLIST.exists():
        print(f"Plist not found at {LAUNCHD_PLIST}. Run install.sh first.")
        return 1
    result = subprocess.run(["launchctl", "load", str(LAUNCHD_PLIST)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"launchctl load failed: {result.stderr}")
        return result.returncode
    print(f"Loaded {LAUNCHD_LABEL}")
    time.sleep(1)
    return cmd_status()


def cmd_stop() -> int:
    if not _launchctl_loaded():
        print("Not loaded.")
        # Also kill any stray foreground daemon
        if PID_FILE.exists():
            try:
                pid = int(PID_FILE.read_text().strip())
                os.kill(pid, signal.SIGTERM)
                print(f"Sent SIGTERM to pid {pid}")
            except Exception:
                pass
        return 0
    result = subprocess.run(["launchctl", "unload", str(LAUNCHD_PLIST)], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"launchctl unload failed: {result.stderr}")
        return result.returncode
    print(f"Unloaded {LAUNCHD_LABEL}")
    return 0


def cmd_restart() -> int:
    cmd_stop()
    time.sleep(1)
    return cmd_start()


def cmd_logs(follow: bool, lines: int) -> int:
    if not LOG_FILE.exists():
        print(f"No log file yet at {LOG_FILE}")
        return 1
    if follow:
        subprocess.run(["tail", "-f", str(LOG_FILE)])
    else:
        subprocess.run(["tail", f"-{lines}", str(LOG_FILE)])
    return 0


def cmd_once(pdf_path: str) -> int:
    ensure_dirs()
    source = Path(pdf_path).expanduser().resolve()
    if not source.exists():
        print(f"Not found: {source}")
        return 1
    # Copy to inbox so the pipeline archives from there (keeps behavior identical)
    staged = INBOX / f"oneoff_{int(time.time())}_{source.name}"
    shutil.copy2(source, staged)
    process_pdf(staged)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="ScanSnap bridge — auto-classify scans into vault",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  scansnap start              # load launchd agent (always-on)
  scansnap stop               # unload launchd agent
  scansnap restart            # reload
  scansnap status             # show state, pending scans, slack config
  scansnap logs               # show recent log lines
  scansnap logs -f            # tail log live
  scansnap once path/to.pdf   # one-shot process (test)
  scansnap                    # run daemon in foreground (debug)
""",
    )
    sub = parser.add_subparsers(dest="cmd")
    sub.add_parser("start", help="Load the launchd agent")
    sub.add_parser("stop", help="Unload the launchd agent")
    sub.add_parser("restart", help="Reload the launchd agent")
    sub.add_parser("status", help="Show daemon status + pending scans")
    logs_p = sub.add_parser("logs", help="Show log file")
    logs_p.add_argument("-f", "--follow", action="store_true", help="Tail the log live")
    logs_p.add_argument("-n", "--lines", type=int, default=30, help="Lines to show (default 30)")
    once = sub.add_parser("once", help="Process a single PDF (one-shot, for testing)")
    once.add_argument("path", help="Path to PDF")
    args = parser.parse_args()

    cmd = args.cmd
    if cmd == "status":
        sys.exit(cmd_status())
    elif cmd == "start":
        sys.exit(cmd_start())
    elif cmd == "stop":
        sys.exit(cmd_stop())
    elif cmd == "restart":
        sys.exit(cmd_restart())
    elif cmd == "logs":
        sys.exit(cmd_logs(args.follow, args.lines))
    elif cmd == "once":
        sys.exit(cmd_once(args.path))
    else:
        daemon_loop()


if __name__ == "__main__":
    main()
