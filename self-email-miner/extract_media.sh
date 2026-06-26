#!/bin/bash
# extract_media.sh — download a video URL (or process a local video file) and emit
# caption metadata + Whisper transcript + a scene-frame contact sheet for visual reading.
#
# Usage: extract_media.sh <url-or-file> <outdir>
# Output in <outdir>: caption.txt, transcript.txt, contact.jpg (+ frames/, cleaned of raw media)
# Prints a SUMMARY block to stdout. Designed for IG reels / YouTube / TikTok / Loom / X video.

set -uo pipefail
SRC="${1:?need url-or-file}"
OUT="${2:?need outdir}"
VENV="$HOME/.claude/skills/self-email-miner/.venv"
WHISPER_MODEL="${WHISPER_MODEL:-mlx-community/whisper-base-mlx}"
mkdir -p "$OUT/frames"
cd "$OUT" || exit 1

VIDEO=""
if [[ "$SRC" =~ ^https?:// ]]; then
  # Fetch caption/metadata even if the video download fails.
  yt-dlp --no-warnings --skip-download --write-info-json -o "meta" "$SRC" >/dev/null 2>&1
  if [ -f meta.info.json ]; then
    "$VENV/bin/python" - "$SRC" <<'PY' > caption.txt 2>/dev/null
import json, glob, sys
f = glob.glob('meta*.info.json')
d = json.load(open(f[0])) if f else {}
print("URL:", sys.argv[1])
print("TITLE:", d.get('title') or '')
print("UPLOADER:", (d.get('uploader') or d.get('channel') or ''))
print("DURATION_S:", d.get('duration') or '')
print("CAPTION/DESCRIPTION:")
print((d.get('description') or '').strip())
PY
  fi
  yt-dlp --no-warnings --socket-timeout 30 -f "mp4/bestvideo+bestaudio/best" \
    -o "video.%(ext)s" "$SRC" >/dev/null 2>&1
  VIDEO="$(ls video.* 2>/dev/null | grep -Ev '\.info\.json$' | head -1)"
else
  VIDEO="$SRC"
fi

if [ -z "$VIDEO" ] || [ ! -f "$VIDEO" ]; then
  echo "SUMMARY"
  echo "STATUS: no-video (download failed or not a video URL)"
  [ -f caption.txt ] && { echo "--- caption ---"; cat caption.txt; }
  exit 0
fi

DUR=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$VIDEO" 2>/dev/null | cut -d. -f1)
DUR=${DUR:-0}

# Audio -> 16k mono wav -> whisper transcript
ffmpeg -nostdin -loglevel error -y -i "$VIDEO" -ar 16000 -ac 1 audio.wav 2>/dev/null
if [ -f audio.wav ]; then
  "$VENV/bin/mlx_whisper" --model "$WHISPER_MODEL" audio.wav \
    --output-dir . --output-format txt >/dev/null 2>&1
  [ -f audio.txt ] && mv -f audio.txt transcript.txt
fi

# Scene-change frames (distinct slides/text screens) + time-sampled fallback for short clips.
ffmpeg -nostdin -loglevel error -y -i "$VIDEO" \
  -vf "select='gt(scene,0.3)',scale=540:-1" -vsync vfr frames/s_%03d.jpg 2>/dev/null
NSCENE=$(ls frames/s_*.jpg 2>/dev/null | wc -l | tr -d ' ')
if [ "$NSCENE" -lt 4 ]; then
  RATE=2; [ "$DUR" -gt 40 ] && RATE=4
  ffmpeg -nostdin -loglevel error -y -i "$VIDEO" \
    -vf "fps=1/${RATE},scale=540:-1" frames/t_%03d.jpg 2>/dev/null
fi

# Contact sheet (one image to read instead of N frames). Cap at ~24 frames.
ls frames/*.jpg 2>/dev/null | head -24 > .flist
if [ -s .flist ]; then
  magick montage $(cat .flist) -tile 3x -geometry 360x+3+3 -background black contact.jpg 2>/dev/null
fi

# Clean up large media, keep transcript + caption + contact sheet.
rm -f "$VIDEO" audio.wav meta*.info.json .flist
rm -rf frames

echo "SUMMARY"
echo "STATUS: ok"
echo "DURATION_S: $DUR  SCENE_FRAMES: $NSCENE"
[ -f caption.txt ] && { echo "--- caption ---"; cat caption.txt; }
echo "--- transcript ---"
[ -f transcript.txt ] && cat transcript.txt || echo "(no transcript)"
echo "--- contact sheet ---"
[ -f contact.jpg ] && echo "$OUT/contact.jpg" || echo "(no contact sheet)"
