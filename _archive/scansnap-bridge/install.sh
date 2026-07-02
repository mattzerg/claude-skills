#!/usr/bin/env bash
# Install and set up the ScanSnap bridge.
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOME_DIR="${HOME}"
INBOX="${HOME_DIR}/scansnap-inbox"
ARCHIVE="${HOME_DIR}/ScanArchive"
PLIST_SRC="${SKILL_DIR}/com.idanbeck.scansnap-bridge.plist"
PLIST_DEST="${HOME_DIR}/Library/LaunchAgents/com.idanbeck.scansnap-bridge.plist"

echo "==> Checking dependencies"

if ! command -v brew >/dev/null 2>&1; then
  echo "ERROR: Homebrew not found. Install from https://brew.sh first." >&2
  exit 1
fi

NEED_BREW=()
command -v ocrmypdf  >/dev/null 2>&1 || NEED_BREW+=("ocrmypdf")
command -v tesseract >/dev/null 2>&1 || NEED_BREW+=("tesseract")
command -v pdftotext >/dev/null 2>&1 || NEED_BREW+=("poppler")

if [ ${#NEED_BREW[@]} -gt 0 ]; then
  echo "==> Installing: ${NEED_BREW[*]}"
  brew install "${NEED_BREW[@]}"
else
  echo "    OCR deps present."
fi

if ! command -v claude >/dev/null 2>&1; then
  echo "WARN: 'claude' CLI not in PATH. Bridge needs it to classify scans." >&2
fi

echo "==> Creating directories"
mkdir -p "${INBOX}" "${INBOX}/_needs_review" "${ARCHIVE}"
echo "    Inbox:   ${INBOX}"
echo "    Archive: ${ARCHIVE}"

echo "==> Rendering launchd plist"
python3 - <<PY
from pathlib import Path
import os

home = os.path.expanduser("~")
skill_dir = "${SKILL_DIR}"
template = Path("${PLIST_SRC}").read_text() if Path("${PLIST_SRC}").exists() else ""
PY

# Write plist deterministically
cat > "${PLIST_SRC}" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.idanbeck.scansnap-bridge</string>

  <key>ProgramArguments</key>
  <array>
    <string>/usr/bin/python3</string>
    <string>${SKILL_DIR}/scansnap_bridge.py</string>
  </array>

  <key>RunAtLoad</key>
  <true/>

  <key>KeepAlive</key>
  <true/>

  <key>WorkingDirectory</key>
  <string>${SKILL_DIR}</string>

  <key>StandardOutPath</key>
  <string>${SKILL_DIR}/bridge.stdout.log</string>

  <key>StandardErrorPath</key>
  <string>${SKILL_DIR}/bridge.stderr.log</string>

  <key>EnvironmentVariables</key>
  <dict>
    <key>PATH</key>
    <string>/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${HOME_DIR}/.local/bin</string>
  </dict>
</dict>
</plist>
PLIST

echo "==> Installing launchd plist"
mkdir -p "${HOME_DIR}/Library/LaunchAgents"
cp "${PLIST_SRC}" "${PLIST_DEST}"
echo "    ${PLIST_DEST}"

echo
echo "==> Done."
echo
echo "To start the daemon:      launchctl load  ${PLIST_DEST}"
echo "To stop:                  launchctl unload ${PLIST_DEST}"
echo "To run in foreground:     python3 ${SKILL_DIR}/scansnap_bridge.py"
echo "To test a single PDF:     python3 ${SKILL_DIR}/scansnap_bridge.py once <file.pdf>"
echo "To check status:          python3 ${SKILL_DIR}/scansnap_bridge.py status"
echo "Logs:                     ${SKILL_DIR}/bridge.log"
echo
echo "Next: configure ScanSnap Home to save PDFs to ${INBOX} (see SKILL.md)."
