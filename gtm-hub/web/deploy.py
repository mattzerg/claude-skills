#!/usr/bin/env python3
"""Build the web bundle and deploy to Fly.io (`zerg-gtm-hub` on epoch-ai-in).

Usage:
    deploy.py [--no-build]   # skip build.py, deploy whatever's already in dist/

Pre-flight (one-time, Matt runs):
    cd ~/.claude/skills/gtm-hub/web
    flyctl launch --no-deploy --org epoch-ai-in --name zerg-gtm-hub --copy-config
    # then set auth:
    HASH=$(docker run --rm caddy:2-alpine caddy hash-password --plaintext '<your-password>')
    flyctl secrets set GTM_HUB_USER=matt GTM_HUB_AUTH_HASH="$HASH"
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

WEB_DIR = Path(__file__).resolve().parent
BUILD = WEB_DIR / "build.py"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--no-build", action="store_true", help="Skip rebuilding dist/")
    p.add_argument("--app", default="zerg-gtm-hub")
    args = p.parse_args()

    if not args.no_build:
        print(f"→ build: {BUILD}")
        rc = subprocess.run([sys.executable, str(BUILD)], cwd=WEB_DIR).returncode
        if rc:
            return rc

    print(f"→ flyctl deploy --app {args.app}")
    rc = subprocess.run(
        ["flyctl", "deploy", "--app", args.app, "--config", str(WEB_DIR / "fly.toml")],
        cwd=WEB_DIR,
    ).returncode
    return rc


if __name__ == "__main__":
    sys.exit(main())
