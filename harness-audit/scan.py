#!/usr/bin/env python3
"""harness-audit — read-only security scanner for Matt's own Claude Code config.

Audits the *inside* of ~/.claude (settings, hooks, agents, skills, MCP config)
for leaked secrets, over-broad permissions, dangerous shell in automation, and
MCP injection surface. Pure standard library. No network. Never writes outside
the dated report under ~/.claude/logs/.

This is the Matt-native rebuild of the idea behind ECC's "AgentShield" — no
third-party code runs, nothing reads your tokens and phones home.

Usage:
    python3 scan.py [--json] [--quiet] [--root DIR]

Pairs with: skill-scout (audits the outside world) and silo-scan (vault silos).
This one audits the inside config.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from pathlib import Path

HOME = Path.home()
DEFAULT_ROOT = HOME / ".claude"

# Directories we never descend into: noisy, generated, backups, transient, or
# third-party/vendored (not Matt's authored config — a different threat model).
SKIP_DIR_NAMES = {
    "__pycache__", ".venv", "venv", "node_modules", ".git",
    "backups", "memory-backups", "projects-archive", "file-history",
    "session-env", "sessions", "logs", "paste-cache", "cache",
    "rate-limit", "queued-patches", ".pytest_cache", "downloads",
    "harness-audit",   # never scan ourselves — our own regexes are not secrets
    "plugins",         # third-party marketplace/cache code (vendored, not authored)
    "conversation-ingest",  # ingested chat data, not config
    "_archive",        # retired skills
    "fakematt-today",  # generated daemon state
    "action_led_targets", "action-led-targets",  # generated state
    "data", "ide", "projects", "session-handoff",
    "insights", "state", "results", "corpus", "out",  # skill data/output subdirs
    "tokens",  # OAuth token caches (managed credential stores, not code leaks)
}

# The authored config surface we actually audit (relative to root). Anything
# outside these subtrees + the explicit settings/MCP files is ignored.
AUTHORED_SUBDIRS = ("hooks", "agents", "skills", "scripts")

# Only read files of these types as text.
TEXT_SUFFIXES = {
    ".md", ".py", ".sh", ".bash", ".zsh", ".js", ".mjs", ".cjs", ".ts",
    ".json", ".yaml", ".yml", ".toml", ".env", ".txt", ".cfg", ".ini", "",
}

MAX_FILE_BYTES = 2_000_000  # skip files bigger than ~2MB (data blobs, histories)

# --- secret patterns -------------------------------------------------------
# Provider-specific tokens are HIGH (very low false-positive). The generic
# assignment pattern is MED (heuristic).
PROVIDER_PATTERNS = [
    ("openai/anthropic key", re.compile(r"sk-(?:ant-|proj-|live-)?[A-Za-z0-9]{20,}")),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}")),
    ("slack token", re.compile(r"(?:xox[baprs]|xapp)-[A-Za-z0-9-]{10,}")),
    ("aws access key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("google api key", re.compile(r"AIza[0-9A-Za-z_-]{35}")),
    ("stripe secret key", re.compile(r"(?:sk|rk)_live_[A-Za-z0-9]{20,}")),
    ("private key block", re.compile(r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("url with inline creds", re.compile(r"[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s:@]+@")),
]
GENERIC_SECRET = re.compile(
    # Handles bare (api_key = "...") and JSON-quoted ("api_key": "...") forms.
    r"""(?i)["']?\b(api[_-]?key|api[_-]?token|access[_-]?key|client[_-]?secret|secret|token|password|passwd|pwd|auth[_-]?token|bearer)\b["']?\s*[:=]\s*["']([^"']{16,})["']"""
)

# A line containing any of these is treated as a placeholder / safe reference,
# not a live secret. Also filters the scanner's own regex-definition lines.
PLACEHOLDER_TOKENS = (
    "example", "placeholder", "dummy", "redacted", "your-", "your_", "yourkey",
    "xxxx", "changeme", "replace", "<", ">", "${", "$(", "os.environ", "getenv",
    "process.env", "%(", "{{", "test-", "sample", "fake", "abc123", "...",
    "user:pass", "default-token", "work-token", "camera_ip", "your_", "env_",
)
# Regex-ish metacharacters that mean we matched a *pattern definition*, not a value.
REGEX_NOISE = ("[a-z", "[A-Za", "[0-9", "\\b", "\\s", "(?:", "(?i)", "{20,}",
               "{16,}", "+}", "*}", "]+", "]{", "]*")


def _looks_placeholder(line: str) -> bool:
    low = line.lower()
    return any(tok in low for tok in PLACEHOLDER_TOKENS) or any(n in line for n in REGEX_NOISE)


# --- dangerous-shell patterns (hooks & skill scripts) ----------------------
SHELL_DANGER = [
    ("HIGH", "remote pipe-to-shell", re.compile(r"(?:curl|wget)\b[^\n|]*\|\s*(?:sudo\s+)?(?:ba|z)?sh\b")),
    ("MED", "recursive force remove", re.compile(r"\brm\s+-[a-z]*[rf][a-z]*\b")),
    ("MED", "force push", re.compile(r"\bgit\s+push\b[^\n]*(?:--force\b|\s-f\b)")),
    ("LOW", "python eval()", re.compile(r"(?<![A-Za-z_])eval\s*\(")),
    ("LOW", "subprocess shell=True", re.compile(r"shell\s*=\s*True")),
]

PERMISSION_BYPASS_KEYS = ("skipDangerousModePermissionPrompt", "skipAutoPermissionPrompt")


class Finding:
    __slots__ = ("severity", "category", "path", "line", "detail", "snippet")

    def __init__(self, severity, category, path, line, detail, snippet):
        self.severity = severity
        self.category = category
        self.path = path
        self.line = line
        self.detail = detail
        self.snippet = snippet[:160]

    def as_dict(self):
        return {
            "severity": self.severity, "category": self.category,
            "path": self.path, "line": self.line,
            "detail": self.detail, "snippet": self.snippet,
        }


SEV_ORDER = {"HIGH": 0, "MED": 1, "LOW": 2}


def iter_text_files(root: Path):
    # Authored surface only: the AUTHORED_SUBDIRS trees plus top-level config
    # markdown (CLAUDE.md). Vendored/generated trees are excluded by design.
    candidates = [root / d for d in AUTHORED_SUBDIRS if (root / d).is_dir()]
    walk = []
    for base in candidates:
        walk.extend(base.rglob("*"))
    walk.extend(root.glob("*.md"))  # CLAUDE.md and friends at the root
    for p in walk:
        if p.is_dir():
            continue
        if any(part in SKIP_DIR_NAMES for part in p.parts):
            continue
        if p.suffix.lower() not in TEXT_SUFFIXES:
            continue
        if ".bak" in p.name or p.name.endswith("~"):
            continue
        try:
            if p.stat().st_size > MAX_FILE_BYTES:
                continue
        except OSError:
            continue
        yield p


def rel(p: Path, root: Path) -> str:
    try:
        return str(p.relative_to(root.parent))
    except ValueError:
        return str(p)


def scan_secrets(p: Path, root: Path, findings: list):
    try:
        text = p.read_text(errors="replace")
    except (OSError, UnicodeError):
        return
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip() or _looks_placeholder(line):
            continue
        for label, pat in PROVIDER_PATTERNS:
            m = pat.search(line)
            if m:
                # Token-style secrets always contain a digit; doc placeholders
                # ("xapp-app-level-token", "sk-ant-example") do not.
                if label not in ("private key block", "url with inline creds") \
                        and not any(c.isdigit() for c in m.group(0)):
                    continue
                findings.append(Finding("HIGH", "SECRET", rel(p, root), i,
                                        f"possible {label}", line.strip()))
                break
        else:
            m = GENERIC_SECRET.search(line)
            if m:
                findings.append(Finding("MED", "SECRET", rel(p, root), i,
                                        f"hardcoded {m.group(1).lower()} assignment",
                                        line.strip()))


def scan_shell(p: Path, root: Path, findings: list):
    # Only meaningful for executable-ish files (hooks + skill scripts).
    if p.suffix.lower() not in {".py", ".sh", ".bash", ".zsh", ".js", ".mjs", ".ts"}:
        return
    try:
        text = p.read_text(errors="replace")
    except (OSError, UnicodeError):
        return
    for i, line in enumerate(text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        # Skip regex *pattern definitions* in security tooling (e.g. a list of
        # DESTRUCTIVE_PATTERNS, or a grep -E pattern) — these describe danger,
        # they don't execute it.
        if any(tok in line for tok in (r"\s", r"\b", "grep -qE", "grep -E",
                                       "re.compile", "PATTERNS", "_PATTERN")):
            continue
        # Skip shell message/label assignments (e.g. WARN="...rm -r..."): these
        # are human-readable strings describing danger, not executed commands.
        if re.match(r"\s*[A-Z][A-Z0-9_]*=[\"']", line):
            continue
        for sev, label, pat in SHELL_DANGER:
            if pat.search(line):
                findings.append(Finding(sev, "HOOK_DANGER", rel(p, root), i,
                                        label, stripped))


def scan_settings(root: Path, findings: list):
    for name in ("settings.json", "settings.local.json"):
        sp = root / name
        if not sp.exists():
            continue
        try:
            data = json.loads(sp.read_text())
        except (OSError, ValueError):
            continue
        for key in PERMISSION_BYPASS_KEYS:
            if data.get(key) is True:
                findings.append(Finding("MED", "PERMISSION", rel(sp, root), 0,
                                        f"{key}=true (auto-approves actions)", f'"{key}": true'))
        perms = data.get("permissions", {})
        for bucket in ("allow", "ask", "deny"):
            for entry in perms.get(bucket, []) or []:
                if bucket == "allow" and isinstance(entry, str) and \
                        re.search(r"\b(Bash|Write|Edit)\s*\(\s*\*", entry):
                    findings.append(Finding("MED", "PERMISSION", rel(sp, root), 0,
                                            f"broad allow rule: {entry}", entry))


def scan_mcp(findings: list):
    cfg = HOME / ".claude.json"
    if not cfg.exists():
        return
    try:
        data = json.loads(cfg.read_text())
    except (OSError, ValueError):
        return

    def walk_servers(servers, where):
        if not isinstance(servers, dict):
            return
        for name, spec in servers.items():
            blob = json.dumps(spec)
            for label, pat in PROVIDER_PATTERNS:
                if pat.search(blob) and not _looks_placeholder(blob):
                    findings.append(Finding("MED", "MCP", "~/.claude.json", 0,
                                            f"MCP server '{name}' ({where}) may embed a {label}",
                                            f"{name}: {blob[:120]}"))
                    break
            url = (spec.get("url") if isinstance(spec, dict) else "") or ""
            if url and not re.match(r"https?://(localhost|127\.0\.0\.1)", url) \
                    and url.startswith("http://"):
                findings.append(Finding("LOW", "MCP", "~/.claude.json", 0,
                                        f"MCP server '{name}' uses plaintext http endpoint", url))

    walk_servers(data.get("mcpServers"), "global")
    for proj, pdata in (data.get("projects") or {}).items():
        if isinstance(pdata, dict):
            walk_servers(pdata.get("mcpServers"), f"project {proj}")


def run_scan(root: Path) -> list:
    findings: list = []
    for p in iter_text_files(root):
        scan_secrets(p, root, findings)
        scan_shell(p, root, findings)
    scan_settings(root, findings)
    scan_mcp(findings)
    findings.sort(key=lambda f: (SEV_ORDER.get(f.severity, 9), f.category, f.path, f.line))
    return findings


def render_markdown(findings: list, root: Path, when: str) -> str:
    counts = {"HIGH": 0, "MED": 0, "LOW": 0}
    for f in findings:
        counts[f.severity] = counts.get(f.severity, 0) + 1
    lines = [
        f"# harness-audit report — {when}",
        "",
        f"Scanned: `{root}` (read-only).",
        "",
        f"**Summary:** {counts['HIGH']} HIGH · {counts['MED']} MED · {counts['LOW']} LOW "
        f"· {len(findings)} total",
        "",
    ]
    if not findings:
        lines.append("No findings. Config surface is clean against current rules.")
        return "\n".join(lines) + "\n"
    cur = None
    for f in findings:
        if f.severity != cur:
            cur = f.severity
            lines += ["", f"## {f.severity}", ""]
        loc = f"`{f.path}`" + (f":{f.line}" if f.line else "")
        lines.append(f"- **[{f.category}]** {loc} — {f.detail}")
        if f.snippet:
            lines.append(f"  - `{f.snippet}`")
    return "\n".join(lines) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description="Read-only security audit of ~/.claude config.")
    ap.add_argument("--json", action="store_true", help="emit JSON to stdout")
    ap.add_argument("--quiet", action="store_true", help="suppress the stdout summary")
    ap.add_argument("--root", default=str(DEFAULT_ROOT), help="config root to scan")
    args = ap.parse_args(argv)

    root = Path(args.root).expanduser()
    if not root.exists():
        print(f"root not found: {root}", file=sys.stderr)
        return 1

    findings = run_scan(root)
    today = _dt.date.today().strftime("%Y%m%d")
    when = _dt.date.today().isoformat()
    report_dir = HOME / ".claude" / "logs"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"harness-audit-{today}.md"
    report_path.write_text(render_markdown(findings, root, when))

    if args.json:
        json.dump([f.as_dict() for f in findings], sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    if not args.quiet:
        counts = {"HIGH": 0, "MED": 0, "LOW": 0}
        for f in findings:
            counts[f.severity] = counts.get(f.severity, 0) + 1
        print(f"harness-audit: {counts['HIGH']} HIGH · {counts['MED']} MED · "
              f"{counts['LOW']} LOW · {len(findings)} total")
        print(f"report: {report_path}")
        for f in findings[:25]:
            loc = f"{f.path}" + (f":{f.line}" if f.line else "")
            print(f"  [{f.severity:<4}] {f.category:<12} {loc} — {f.detail}")
        if len(findings) > 25:
            print(f"  … {len(findings) - 25} more in the report")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
