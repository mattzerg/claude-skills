#!/usr/bin/env python3
"""
Drive Skill - Durable read access to Matt's Google Drive.

Searches, lists, and reads Google Drive files (Docs, Sheets, Slides, PDFs,
folders, plain text). Modeled on gmail-skill's OAuth/token pattern.

Token reuse: this skill first tries its own tokens/ dir, then falls back to
reusing the gmail-skill's stored tokens (which already include the broad
`https://www.googleapis.com/auth/drive` scope). No separate browser auth is
needed if the gmail token already carries a Drive scope.

Usage:
    python drive_skill.py list [--account EMAIL] [--max N] [--owner me]
    python drive_skill.py search "QUERY" [--account EMAIL] [--max N] [--type doc|sheet|slide|pdf|folder]
    python drive_skill.py read FILE_ID [--account EMAIL] [--format md|txt]
    python drive_skill.py accounts
    python drive_skill.py auth [--account EMAIL]
"""

import argparse
import io
import json
import os
import re
import secrets
import sys
import webbrowser
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from typing import Optional
from urllib.parse import urlencode, parse_qs, urlparse


# Background launch agents use these skills for polling. They must never open
# OAuth browser windows unattended; explicit auth commands still work in a TTY.
def ensure_interactive_auth_allowed(auth_url: Optional[str] = None) -> None:
    if os.environ.get("GOOGLE_OAUTH_ALLOW_BROWSER") == "1":
        return
    if sys.stdin.isatty() and sys.stdout.isatty():
        return
    print(
        json.dumps(
            {
                "error": "google_oauth_interactive_required",
                "message": (
                    "Google Drive OAuth needs an interactive terminal; refusing to "
                    "open a browser from a background job. Run: "
                    "python3 ~/.claude/skills/drive-skill/drive_skill.py auth "
                    "--account matteisn@gmail.com"
                ),
                "auth_url": auth_url,
            }
        )
    )
    sys.exit(2)


# Check for required libraries
try:
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaIoBaseDownload
    import requests
except ImportError:
    print(
        json.dumps(
            {
                "error": "missing_dependencies",
                "message": "Required libraries not installed.",
                "fix": "pip install google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client requests",
            }
        )
    )
    sys.exit(1)


# Paths
SKILL_DIR = Path(__file__).parent
TOKENS_DIR = SKILL_DIR / "tokens"
CREDENTIALS_FILE = SKILL_DIR / "credentials.json"
ACCOUNTS_META_FILE = SKILL_DIR / "accounts.json"

# Sibling gmail-skill — its tokens already carry the `drive` scope, so we reuse
# them instead of forcing a separate browser auth.
GMAIL_SKILL_DIR = SKILL_DIR.parent / "gmail-skill"
GMAIL_TOKENS_DIR = GMAIL_SKILL_DIR / "tokens"
GMAIL_CREDENTIALS_FILE = GMAIL_SKILL_DIR / "credentials.json"

# Default to the Workspace account: its OAuth app is org-internal, so refresh
# tokens don't hit the 7-day "testing-mode" expiry that kills the personal
# matteisn@gmail.com token weekly (2026-06-17). Pass --account to override.
DEFAULT_ACCOUNT = "matthew@zergai.com"

# Read-only Drive scope this skill needs. The gmail-skill's broader
# `auth/drive` scope is a superset and satisfies it.
DRIVE_READONLY_SCOPE = "https://www.googleapis.com/auth/drive.readonly"
DRIVE_FULL_SCOPE = "https://www.googleapis.com/auth/drive"
DRIVE_SCOPES_ACCEPTED = {DRIVE_READONLY_SCOPE, DRIVE_FULL_SCOPE}

SCOPES = [
    DRIVE_READONLY_SCOPE,
    "https://www.googleapis.com/auth/userinfo.email",
]

# Google OAuth endpoints
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v2/userinfo"

# MIME types
MIME_GOOGLE_DOC = "application/vnd.google-apps.document"
MIME_GOOGLE_SHEET = "application/vnd.google-apps.spreadsheet"
MIME_GOOGLE_SLIDE = "application/vnd.google-apps.presentation"
MIME_GOOGLE_FOLDER = "application/vnd.google-apps.folder"
MIME_PDF = "application/pdf"

TYPE_TO_MIME = {
    "doc": MIME_GOOGLE_DOC,
    "sheet": MIME_GOOGLE_SHEET,
    "slide": MIME_GOOGLE_SLIDE,
    "pdf": MIME_PDF,
    "folder": MIME_GOOGLE_FOLDER,
}

FILE_FIELDS = "id, name, mimeType, modifiedTime, owners(displayName,emailAddress), webViewLink"


def get_client_config() -> dict:
    """Load OAuth client configuration (prefer local, fall back to gmail-skill)."""
    for path in (CREDENTIALS_FILE, GMAIL_CREDENTIALS_FILE):
        if path.exists():
            with open(path) as f:
                return json.load(f)
    print(
        json.dumps(
            {
                "error": "no_credentials",
                "message": (
                    "No OAuth client credentials found. Expected "
                    f"{CREDENTIALS_FILE} or {GMAIL_CREDENTIALS_FILE}."
                ),
            }
        )
    )
    sys.exit(1)


# --------------------------------------------------------------------------
# OAuth flow (mirrors gmail-skill: custom local-callback server, raw token JSON)
# --------------------------------------------------------------------------
class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """HTTP handler to receive OAuth callback."""

    def log_message(self, format, *args):
        pass  # Suppress logging

    def do_GET(self):
        query = parse_qs(urlparse(self.path).query)
        if "code" in query:
            self.server.auth_code = query["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                b"""
                <html><body style="font-family: system-ui; text-align: center; padding: 50px;">
                <h1>Drive access granted!</h1>
                <p>You can close this window and return to the terminal.</p>
                <script>window.close();</script>
                </body></html>
            """
            )
        elif "error" in query:
            self.server.auth_error = query.get("error", ["Unknown error"])[0]
            self.send_response(400)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(
                f"<html><body><h1>Error: {self.server.auth_error}</h1></body></html>".encode()
            )
        else:
            self.send_response(400)
            self.end_headers()


def do_oauth_flow(client_config: dict, login_hint: str = None, force_consent: bool = True) -> dict:
    """Perform OAuth flow with browser and local callback server."""
    ensure_interactive_auth_allowed()

    client_id = client_config["installed"]["client_id"]
    client_secret = client_config["installed"]["client_secret"]

    import socket

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("", 0))
        port = s.getsockname()[1]

    redirect_uri = f"http://localhost:{port}"
    state = secrets.token_urlsafe(32)

    auth_params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(SCOPES),
        "access_type": "offline",
        "state": state,
    }
    if force_consent:
        auth_params["prompt"] = "consent"
    if login_hint:
        auth_params["login_hint"] = login_hint

    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(auth_params)}"

    server = HTTPServer(("localhost", port), OAuthCallbackHandler)
    server.auth_code = None
    server.auth_error = None
    server.timeout = 120

    print("\n" + "=" * 50)
    print(f"  AUTHENTICATING DRIVE: {login_hint or 'New account'}")
    print("=" * 50)
    print("Opening browser - select the account above and grant Drive read access.")
    print(f"If browser doesn't open, visit:\n{auth_url}\n")

    ensure_interactive_auth_allowed(auth_url)
    webbrowser.open(auth_url)

    while server.auth_code is None and server.auth_error is None:
        server.handle_request()

    if server.auth_error:
        print(f"Authentication error: {server.auth_error}")
        sys.exit(1)

    token_data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": server.auth_code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri,
    }
    response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
    if response.status_code != 200:
        print(f"Token exchange failed: {response.text}")
        sys.exit(1)

    tokens = response.json()

    if "expires_in" in tokens:
        from datetime import timedelta

        expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(seconds=tokens["expires_in"])
        tokens["expiry"] = expiry.isoformat() + "Z"

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    user_response = requests.get(GOOGLE_USERINFO_URL, headers=headers)
    if user_response.status_code == 200:
        tokens["email"] = user_response.json().get("email")

    return tokens


# --------------------------------------------------------------------------
# Token storage / account resolution
# --------------------------------------------------------------------------
def sanitize_email(email: str) -> str:
    return re.sub(r"[^\w\-.]", "_", email.lower())


def get_token_path(account: Optional[str] = None) -> Path:
    """Get token file path in this skill's own tokens/ dir."""
    TOKENS_DIR.mkdir(parents=True, exist_ok=True)
    if account:
        return TOKENS_DIR / f"token_{sanitize_email(account)}.json"
    tokens = list(TOKENS_DIR.glob("token_*.json"))
    if tokens:
        return tokens[0]
    return TOKENS_DIR / "token_default.json"


def token_has_drive_scope(token_data: dict) -> bool:
    scope_str = token_data.get("scope", "") or ""
    granted = set(scope_str.split())
    return bool(granted & DRIVE_SCOPES_ACCEPTED)


def find_reusable_gmail_token(account: Optional[str]) -> Optional[Path]:
    """Find a gmail-skill token (with drive scope) for this account."""
    if not GMAIL_TOKENS_DIR.exists():
        return None
    candidates = []
    if account:
        named = GMAIL_TOKENS_DIR / f"token_{sanitize_email(account)}.json"
        if named.exists():
            candidates.append(named)
    candidates.extend(sorted(GMAIL_TOKENS_DIR.glob("token_*.json")))
    for path in candidates:
        try:
            with open(path) as f:
                data = json.load(f)
        except Exception:
            continue
        if account and data.get("email") and data["email"].lower() != account.lower():
            continue
        if token_has_drive_scope(data):
            return path
    return None


def load_accounts_meta() -> dict:
    if ACCOUNTS_META_FILE.exists():
        try:
            with open(ACCOUNTS_META_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def resolve_account_email(account: Optional[str]) -> str:
    """Resolve account alias to email; default to DEFAULT_ACCOUNT."""
    if not account:
        return DEFAULT_ACCOUNT
    if "@" in account:
        return account
    meta = load_accounts_meta()
    for email, info in meta.items():
        if info.get("label", "").lower() == account.lower():
            return email
    return account


def _creds_from_token_data(token_data: dict, client_config: dict) -> Credentials:
    expiry = None
    if "expiry" in token_data:
        try:
            expiry = datetime.fromisoformat(
                token_data["expiry"].replace("Z", "+00:00")
            ).replace(tzinfo=None)
        except Exception:
            pass
    return Credentials(
        token=token_data.get("access_token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=GOOGLE_TOKEN_URL,
        client_id=client_config["installed"]["client_id"],
        client_secret=client_config["installed"]["client_secret"],
        scopes=(token_data.get("scope") or " ".join(SCOPES)).split(),
        expiry=expiry,
    )


def get_credentials(account: Optional[str] = None) -> Credentials:
    """Get or refresh OAuth2 credentials, reusing gmail-skill tokens if possible."""
    client_config = get_client_config()
    account_email = resolve_account_email(account)

    # 1) Prefer this skill's own token if present and drive-scoped.
    own_token_path = get_token_path(account_email)
    token_path = None
    token_data = None
    if own_token_path.exists():
        try:
            with open(own_token_path) as f:
                td = json.load(f)
            if token_has_drive_scope(td):
                token_path, token_data = own_token_path, td
        except Exception:
            pass

    # 2) Fall back to reusing a gmail-skill token that already has drive scope.
    if token_data is None:
        gmail_token = find_reusable_gmail_token(account_email)
        if gmail_token:
            try:
                with open(gmail_token) as f:
                    token_data = json.load(f)
                token_path = gmail_token
            except Exception:
                token_data = None

    # 3) Nothing usable -> need interactive auth.
    if token_data is None:
        token_data = do_oauth_flow(client_config, login_hint=account_email, force_consent=True)
        token_path = get_token_path(token_data.get("email", account_email))
        with open(token_path, "w") as f:
            json.dump(token_data, f, indent=2)
        token_path.chmod(0o600)
        print(f"Authenticated as: {token_data.get('email', 'unknown')}", file=sys.stderr)

    creds = _creds_from_token_data(token_data, client_config)

    if not creds.valid:
        if creds.refresh_token:
            try:
                creds.refresh(Request())
                # Persist refreshed access token back to whichever file we read.
                token_data["access_token"] = creds.token
                if creds.expiry:
                    token_data["expiry"] = creds.expiry.replace(tzinfo=None).isoformat() + "Z"
                with open(token_path, "w") as f:
                    json.dump(token_data, f, indent=2)
                token_path.chmod(0o600)
            except Exception as e:
                print(f"Token refresh failed, re-authenticating: {e}", file=sys.stderr)
                token_data = do_oauth_flow(
                    client_config, login_hint=account_email, force_consent=True
                )
                token_path = get_token_path(token_data.get("email", account_email))
                with open(token_path, "w") as f:
                    json.dump(token_data, f, indent=2)
                token_path.chmod(0o600)
                creds = _creds_from_token_data(token_data, client_config)
        else:
            token_data = do_oauth_flow(
                client_config, login_hint=account_email, force_consent=True
            )
            token_path = get_token_path(token_data.get("email", account_email))
            with open(token_path, "w") as f:
                json.dump(token_data, f, indent=2)
            token_path.chmod(0o600)
            creds = _creds_from_token_data(token_data, client_config)

    return creds


def get_drive_service(account: Optional[str] = None):
    creds = get_credentials(account)
    return build("drive", "v3", credentials=creds, cache_discovery=False)


# --------------------------------------------------------------------------
# Account listing
# --------------------------------------------------------------------------
def list_accounts() -> list:
    """List accounts available to this skill (own tokens + reusable gmail tokens)."""
    meta = load_accounts_meta()
    by_email = {}

    def add(email, source, path, drive_ok):
        if not email:
            return
        existing = by_email.get(email)
        if existing:
            if drive_ok:
                existing["drive_scope"] = True
            existing["sources"] = sorted(set(existing["sources"] + [source]))
            return
        by_email[email] = {
            "email": email,
            "label": meta.get(email, {}).get("label", ""),
            "is_default": email == DEFAULT_ACCOUNT,
            "drive_scope": drive_ok,
            "sources": [source],
            "file": str(path),
        }

    if TOKENS_DIR.exists():
        for tf in sorted(TOKENS_DIR.glob("token_*.json")):
            try:
                with open(tf) as f:
                    data = json.load(f)
            except Exception:
                continue
            add(data.get("email", "unknown"), "drive-skill", tf, token_has_drive_scope(data))

    if GMAIL_TOKENS_DIR.exists():
        for tf in sorted(GMAIL_TOKENS_DIR.glob("token_*.json")):
            try:
                with open(tf) as f:
                    data = json.load(f)
            except Exception:
                continue
            add(data.get("email", "unknown"), "gmail-skill", tf, token_has_drive_scope(data))

    return list(by_email.values())


# --------------------------------------------------------------------------
# Verbs
# --------------------------------------------------------------------------
def _owner_strings(file_obj: dict) -> list:
    owners = []
    for o in file_obj.get("owners", []) or []:
        name = o.get("displayName") or ""
        email = o.get("emailAddress") or ""
        owners.append({"name": name, "email": email})
    return owners


def _format_file(file_obj: dict) -> dict:
    return {
        "id": file_obj.get("id"),
        "name": file_obj.get("name"),
        "mimeType": file_obj.get("mimeType"),
        "modifiedTime": file_obj.get("modifiedTime"),
        "owners": _owner_strings(file_obj),
        "webViewLink": file_obj.get("webViewLink"),
    }


def cmd_list(args):
    service = get_drive_service(args.account)
    q_parts = ["trashed = false"]
    if args.owner == "me":
        q_parts.append("'me' in owners")
    q = " and ".join(q_parts)
    try:
        results = (
            service.files()
            .list(
                q=q,
                orderBy="modifiedTime desc",
                pageSize=max(1, min(args.max, 1000)),
                fields=f"files({FILE_FIELDS})",
                spaces="drive",
                corpora="user",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
    except HttpError as e:
        print(json.dumps({"error": "drive_api_error", "message": str(e)}))
        sys.exit(1)
    files = [_format_file(f) for f in results.get("files", [])]
    print(json.dumps({"account": resolve_account_email(args.account), "count": len(files), "files": files}, indent=2))


def cmd_search(args):
    service = get_drive_service(args.account)
    escaped = args.query.replace("\\", "\\\\").replace("'", "\\'")
    q_parts = [
        "trashed = false",
        f"(fullText contains '{escaped}' or name contains '{escaped}')",
    ]
    if args.type:
        mime = TYPE_TO_MIME.get(args.type)
        if mime:
            q_parts.append(f"mimeType = '{mime}'")
    q = " and ".join(q_parts)
    try:
        results = (
            service.files()
            .list(
                q=q,
                orderBy="modifiedTime desc",
                pageSize=max(1, min(args.max, 1000)),
                fields=f"files({FILE_FIELDS})",
                spaces="drive",
                corpora="user",
                supportsAllDrives=True,
                includeItemsFromAllDrives=True,
            )
            .execute()
        )
    except HttpError as e:
        print(json.dumps({"error": "drive_api_error", "message": str(e)}))
        sys.exit(1)
    files = [_format_file(f) for f in results.get("files", [])]
    print(
        json.dumps(
            {
                "account": resolve_account_email(args.account),
                "query": args.query,
                "type": args.type,
                "count": len(files),
                "files": files,
            },
            indent=2,
        )
    )


def _download_binary(service, file_id: str) -> bytes:
    request = service.files().get_media(fileId=file_id, supportsAllDrives=True)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def _export(service, file_id: str, mime_type: str) -> bytes:
    request = service.files().export_media(fileId=file_id, mimeType=mime_type)
    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    return buf.getvalue()


def cmd_read(args):
    service = get_drive_service(args.account)
    try:
        meta = (
            service.files()
            .get(fileId=args.file_id, fields=FILE_FIELDS, supportsAllDrives=True)
            .execute()
        )
    except HttpError as e:
        print(json.dumps({"error": "drive_api_error", "message": str(e)}))
        sys.exit(1)

    mime = meta.get("mimeType", "")
    name = meta.get("name", "")
    content = None
    export_mime = None

    try:
        if mime == MIME_GOOGLE_DOC:
            # Markdown export supported by Drive; fall back to text/plain.
            if args.format == "md":
                try:
                    content = _export(service, args.file_id, "text/markdown").decode(
                        "utf-8", errors="replace"
                    )
                    export_mime = "text/markdown"
                except HttpError:
                    content = _export(service, args.file_id, "text/plain").decode(
                        "utf-8", errors="replace"
                    )
                    export_mime = "text/plain"
            else:
                content = _export(service, args.file_id, "text/plain").decode(
                    "utf-8", errors="replace"
                )
                export_mime = "text/plain"
        elif mime == MIME_GOOGLE_SHEET:
            content = _export(service, args.file_id, "text/csv").decode(
                "utf-8", errors="replace"
            )
            export_mime = "text/csv"
        elif mime == MIME_GOOGLE_SLIDE:
            content = _export(service, args.file_id, "text/plain").decode(
                "utf-8", errors="replace"
            )
            export_mime = "text/plain"
        elif mime.startswith("text/") or mime in (
            "application/json",
            "application/xml",
        ):
            content = _download_binary(service, args.file_id).decode(
                "utf-8", errors="replace"
            )
            export_mime = mime
        elif mime == MIME_GOOGLE_FOLDER:
            print(
                json.dumps(
                    {
                        "error": "is_folder",
                        "message": f"'{name}' is a folder. Use 'list' or 'search' to see its contents.",
                        "id": args.file_id,
                    }
                )
            )
            sys.exit(1)
        else:
            print(
                json.dumps(
                    {
                        "error": "unsupported_type",
                        "message": (
                            f"Cannot extract text from mimeType '{mime}'. "
                            "Open via webViewLink instead."
                        ),
                        "id": args.file_id,
                        "name": name,
                        "mimeType": mime,
                        "webViewLink": meta.get("webViewLink"),
                    }
                )
            )
            sys.exit(1)
    except HttpError as e:
        print(json.dumps({"error": "drive_api_error", "message": str(e)}))
        sys.exit(1)

    # Print a small JSON header to stderr-style metadata, then content to stdout.
    header = {
        "id": args.file_id,
        "name": name,
        "mimeType": mime,
        "exportedAs": export_mime,
        "modifiedTime": meta.get("modifiedTime"),
        "webViewLink": meta.get("webViewLink"),
    }
    print(json.dumps(header, indent=2))
    print("---")
    print(content)


def cmd_accounts(args):
    accounts = list_accounts()
    print(
        json.dumps(
            {"default": DEFAULT_ACCOUNT, "count": len(accounts), "accounts": accounts},
            indent=2,
        )
    )


def cmd_auth(args):
    """Force an interactive OAuth flow and store a drive-scoped token locally."""
    account_email = resolve_account_email(args.account)
    client_config = get_client_config()
    token_data = do_oauth_flow(client_config, login_hint=account_email, force_consent=True)
    token_path = get_token_path(token_data.get("email", account_email))
    with open(token_path, "w") as f:
        json.dump(token_data, f, indent=2)
    token_path.chmod(0o600)
    print(
        json.dumps(
            {
                "status": "authenticated",
                "email": token_data.get("email"),
                "drive_scope": token_has_drive_scope(token_data),
                "token_file": str(token_path),
            },
            indent=2,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only Google Drive access (search, list, read)."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_list = sub.add_parser("list", help="List recent files (modifiedTime desc).")
    p_list.add_argument("--account", default=None)
    p_list.add_argument("--max", type=int, default=25)
    p_list.add_argument("--owner", choices=["me"], default=None)
    p_list.set_defaults(func=cmd_list)

    p_search = sub.add_parser("search", help="Full-text + name search.")
    p_search.add_argument("query")
    p_search.add_argument("--account", default=None)
    p_search.add_argument("--max", type=int, default=25)
    p_search.add_argument("--type", choices=list(TYPE_TO_MIME.keys()), default=None)
    p_search.set_defaults(func=cmd_search)

    p_read = sub.add_parser("read", help="Read/export a file's text content.")
    p_read.add_argument("file_id")
    p_read.add_argument("--account", default=None)
    p_read.add_argument("--format", choices=["md", "txt"], default="md")
    p_read.set_defaults(func=cmd_read)

    p_accounts = sub.add_parser("accounts", help="List configured accounts.")
    p_accounts.set_defaults(func=cmd_accounts)

    p_auth = sub.add_parser("auth", help="One-time interactive browser auth.")
    p_auth.add_argument("--account", default=DEFAULT_ACCOUNT)
    p_auth.set_defaults(func=cmd_auth)

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
