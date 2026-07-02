# ZergGuard iPhone Shortcut — "Is this a scam?"

Paste suspicious text on iPhone, get verdict from your Mac.

## Build the Shortcut

1. iPhone → Shortcuts app → tap `+` → "New Shortcut."
2. Name it: **Is this a scam?**
3. Add actions in this order:

| # | Action | Settings |
|---|--------|---------|
| 1 | **Get Clipboard** | (no settings) |
| 2 | **Get Contents of URL** | URL: `http://<your-mac-tailscale-ip>:54322/check` <br/> Method: `POST` <br/> Headers: `Content-Type: text/plain` <br/> Request Body: `Text` → magic variable "Clipboard" |
| 3 | **Show Result** | Magic variable from action 2 |

(If you don't use Tailscale, swap step 2 for an email-to-yourself + `gmail-skill` polling.)

## On the Mac

Run this once:

```bash
python3 ~/.claude/skills/zergguard-scam-check/server.py
```

(TODO: ship `server.py` — tiny http.server wrapper around `check.py`. Skeleton below.)

```python
# server.py — minimal HTTP wrapper
from http.server import BaseHTTPRequestHandler, HTTPServer
import subprocess, json
class H(BaseHTTPRequestHandler):
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(n).decode("utf-8", errors="replace")
        out = subprocess.run(
            ["python3", "/Users/mattheweisner/.claude/skills/zergguard-scam-check/check.py", body],
            capture_output=True, text=True, timeout=15,
        )
        self.send_response(200); self.send_header("Content-Type", "text/plain"); self.end_headers()
        self.wfile.write(out.stdout.encode("utf-8"))
HTTPServer(("127.0.0.1", 54322), H).serve_forever()
```

## When to use

Whenever you get a suspicious text on iPhone: copy → run Shortcut → instant verdict.

## Privacy

Everything stays on your devices (Mac + iPhone). Nothing leaves your network.
