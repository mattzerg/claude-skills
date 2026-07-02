#!/bin/bash
# extract_hires.sh — completeness re-pass: full-resolution scene frames + tesseract OCR, to catch
# small/brief on-screen text (GitHub URLs in address bars, repo names, @handles) that a downscaled
# contact sheet can miss. Keeps full-res frames + an OCR dump for a focused re-read.
# Usage: extract_hires.sh <url> <outdir>
set -uo pipefail
SRC="${1:?url}"; OUT="${2:?outdir}"
mkdir -p "$OUT/hires"; cd "$OUT" || exit 1
yt-dlp --no-warnings --socket-timeout 30 -f "mp4/bestvideo+bestaudio/best" -o "v.%(ext)s" "$SRC" >/dev/null 2>&1
V="$(ls v.* 2>/dev/null | grep -Ev '\.info\.json$' | head -1)"
[ -z "$V" ] && { echo "STATUS: no-video"; exit 0; }
# scene frames at FULL native resolution (no downscale), plus denser time sampling
ffmpeg -nostdin -loglevel error -y -i "$V" -vf "select='gt(scene,0.25)'" -vsync vfr hires/s_%03d.png 2>/dev/null
ffmpeg -nostdin -loglevel error -y -i "$V" -vf "fps=1/2" hires/t_%03d.png 2>/dev/null
# OCR every frame; collect anything that looks like a URL/repo/handle
: > ocr.txt
for f in hires/*.png; do
  tesseract "$f" stdout --psm 6 2>/dev/null >> ocr.txt
  echo "" >> ocr.txt
done
echo "=== OCR URL/REPO/HANDLE candidates ($V) ==="
grep -oiE '(https?://[^ ]+|[a-z0-9_.-]+/[a-z0-9_.-]+|github\.com[^ ]*|@[a-z0-9_.]+|npx [a-z0-9 @/-]+)' ocr.txt \
  | sed 's/[.,)]*$//' | sort -u | grep -viE '^https?://$' | head -60
rm -f "$V" v.*.info.json
echo "=== (full-res frames kept in $OUT/hires for visual re-read) ==="
ls hires/*.png 2>/dev/null | wc -l | xargs echo "frame count:"
