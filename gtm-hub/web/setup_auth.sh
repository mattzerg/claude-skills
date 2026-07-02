#!/usr/bin/env bash
# One-time setup for the zerg-gtm-hub Fly app.
#
# 1. Generates a strong random password
# 2. Bcrypts it via `caddy hash-password` (Docker or local binary)
# 3. Stores the plaintext in macOS Keychain (service: gtm-hub-auth, account: matt)
# 4. Sets fly secrets so Caddy basic_auth works
# 5. Runs the first deploy
#
# After this, retrieve the password anytime with:
#   security find-generic-password -a matt -s gtm-hub-auth -w
#
# Re-run to rotate (regenerates password + redeploys).

set -euo pipefail

APP="zerg-gtm-hub"
USER="matt"
KEYCHAIN_SERVICE="gtm-hub-auth"
WEB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- 1. Generate password (24 chars, alphanumeric, ~143 bits entropy) ---
# python3 avoids the `tr | head` SIGPIPE issue under `set -o pipefail`.
PASSWORD=$(python3 -c 'import secrets,string; print("".join(secrets.choice(string.ascii_letters+string.digits) for _ in range(24)))')
echo "✓ Generated password (${#PASSWORD} chars)"

# --- 2. Bcrypt the password ---
# Pipe via stdin instead of --plaintext "$PASSWORD" — argv is visible in `ps`
# for the lifetime of the process, which would leak the plaintext.
HASH=""
# Newer Caddy hash-password (2.7+) requires --plaintext when piped (no TTY).
# Inside an ephemeral docker container, argv visibility is negligible.
if command -v caddy >/dev/null 2>&1; then
  HASH=$(caddy hash-password --plaintext "$PASSWORD")
elif command -v docker >/dev/null 2>&1; then
  HASH=$(docker run --rm caddy:2-alpine caddy hash-password --plaintext "$PASSWORD")
else
  echo "✗ Need either 'caddy' or 'docker' to generate the bcrypt hash." >&2
  echo "  Install Caddy:  brew install caddy" >&2
  exit 1
fi
echo "✓ Bcrypted (Caddy hash-password)"

# --- 3. Store password in macOS Keychain ---
security delete-generic-password -a "$USER" -s "$KEYCHAIN_SERVICE" 2>/dev/null || true
security add-generic-password \
  -a "$USER" \
  -s "$KEYCHAIN_SERVICE" \
  -w "$PASSWORD" \
  -j "Zerg GTM Hub Fly app ($APP) basic_auth credential — created by gtm-hub/web/setup_auth.sh"
echo "✓ Stored in Keychain (service=$KEYCHAIN_SERVICE, account=$USER)"

# --- 4. Set Fly secrets ---
echo "→ Setting Fly secrets for $APP …"
flyctl secrets set \
  --app "$APP" \
  GTM_HUB_USER="$USER" \
  GTM_HUB_AUTH_HASH="$HASH"
echo "✓ Fly secrets set"

# --- 5. Deploy ---
cd "$WEB_DIR"
python3 build.py
echo "→ flyctl deploy --app $APP"
flyctl deploy --app "$APP" --config "$WEB_DIR/fly.toml"

cat <<EOF

═══════════════════════════════════════════════════════════════════
Zerg GTM Hub is live.

  URL:       https://${APP}.fly.dev
  Username:  ${USER}
  Password:  (retrieve below)

Retrieve password later:
  security find-generic-password -a ${USER} -s ${KEYCHAIN_SERVICE} -w

Rotate:
  rerun this script — generates a new password, updates secrets, redeploys.

NOT linked from anywhere public. Add Cloudflare Access in front later if you want
SSO instead of basic auth.
═══════════════════════════════════════════════════════════════════
EOF
