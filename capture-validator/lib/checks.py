"""
Capture-validator checks. Pure Pillow, no numpy.

Each check returns a dict:
  {"name": str, "passed": bool, "severity": "FAIL"|"WARN", "details": str, "bbox": (x,y,w,h)?}

The annotate.py module reads `bbox` to draw a red box on the violation PNG.
"""

from __future__ import annotations

import json
import statistics
import subprocess
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter

# Tunable thresholds
MIN_WIDTH = 1920
MIN_HEIGHT = 1080
APP_BBOX_COVERAGE_MIN = 0.95   # app content must cover ≥95% of frame
EDGE_BAND_PX_TOP = 28          # macOS menu bar is ~24-28px at 1× DPI
EDGE_BAND_PX_BOTTOM = 80       # dock area
NOTIFICATION_BANNER_W = 340    # macOS notification banner width
NOTIFICATION_BANNER_H = 95
TILT_TOLERANCE_DEG = 1.0       # ±1° axis-alignment


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------

def ffprobe_meta(video_path: Path) -> dict[str, Any]:
    """Extract resolution + duration via ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height,r_frame_rate:format=duration",
        "-of", "json",
        str(video_path),
    ]
    out = subprocess.check_output(cmd, text=True, stderr=subprocess.STDOUT)
    data = json.loads(out)
    stream = data.get("streams", [{}])[0]
    fmt = data.get("format", {})
    return {
        "width": int(stream.get("width", 0)),
        "height": int(stream.get("height", 0)),
        "fps": stream.get("r_frame_rate", "0/0"),
        "duration": float(fmt.get("duration", 0)),
    }


def extract_frame(video_path: Path, out_png: Path, t: float = 1.0) -> Path:
    """Extract a single frame at time t (default 1.0s)."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y", "-v", "error",
        "-ss", str(t),
        "-i", str(video_path),
        "-frames:v", "1",
        str(out_png),
    ]
    subprocess.run(cmd, check=True)
    return out_png


def _downscale_grayscale(img: Image.Image, target_w: int = 640) -> Image.Image:
    """Downscale to grayscale for variance / edge analysis."""
    w, h = img.size
    if w > target_w:
        scale = target_w / w
        img = img.resize((target_w, int(h * scale)))
    return img.convert("L")


def _edge_density_per_row(edges: Image.Image) -> list[float]:
    """Average pixel intensity per row of an edge-detected image."""
    w, h = edges.size
    data = list(edges.getdata())
    return [sum(data[y * w : (y + 1) * w]) / w for y in range(h)]


def _edge_density_per_col(edges: Image.Image) -> list[float]:
    """Average pixel intensity per column of an edge-detected image."""
    w, h = edges.size
    data = list(edges.getdata())
    out = [0.0] * w
    for y in range(h):
        for x in range(w):
            out[x] += data[y * w + x]
    return [v / h for v in out]


# ----------------------------------------------------------------------
# Individual checks
# ----------------------------------------------------------------------

def check_resolution(meta: dict) -> dict:
    w, h = meta["width"], meta["height"]
    passed = w >= MIN_WIDTH and h >= MIN_HEIGHT
    return {
        "name": "resolution",
        "passed": passed,
        "severity": "FAIL" if not passed else "PASS",
        "details": f"{w}×{h} (min {MIN_WIDTH}×{MIN_HEIGHT})",
    }


def _patch_mean_rgb(img: Image.Image, x: int, y: int, w: int, h: int) -> tuple:
    """Mean RGB of a patch."""
    patch = img.crop((x, y, x + w, y + h))
    pixels = list(patch.getdata())
    if not pixels:
        return (0, 0, 0)
    r = sum(p[0] for p in pixels) / len(pixels)
    g = sum(p[1] for p in pixels) / len(pixels)
    b = sum(p[2] for p in pixels) / len(pixels)
    return (r, g, b)


def _rgb_distance(a: tuple, b: tuple) -> float:
    return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2 + (a[2] - b[2]) ** 2) ** 0.5


def check_app_bbox(img: Image.Image) -> dict:
    """
    Detect wallpaper-bleed by comparing the four corner patches to the
    center patch. If any corner differs from the center by more than the
    threshold, wallpaper is bleeding in around the app window.

    Catches: tilted / off-center recording where macOS wallpaper is visible
    around the app (the Tycoon failure mode — Loom-style multi-app capture).
    """
    src_w, src_h = img.size
    rgb = img.convert("RGB")

    # Sample patches: each ~3% of width/height for stability
    pw = max(32, int(src_w * 0.03))
    ph = max(32, int(src_h * 0.03))
    cx = (src_w - pw) // 2
    cy = (src_h - ph) // 2

    # Center patches — use the central 25% area, sampled at 4 grid points
    # so we average across UI variation without lucking onto one element
    center_samples = [
        _patch_mean_rgb(rgb, cx - pw, cy - ph, pw, ph),
        _patch_mean_rgb(rgb, cx + pw, cy - ph, pw, ph),
        _patch_mean_rgb(rgb, cx - pw, cy + ph, pw, ph),
        _patch_mean_rgb(rgb, cx + pw, cy + ph, pw, ph),
        _patch_mean_rgb(rgb, cx, cy, pw, ph),
    ]
    center = (
        sum(c[0] for c in center_samples) / 5,
        sum(c[1] for c in center_samples) / 5,
        sum(c[2] for c in center_samples) / 5,
    )

    # Four corner patches
    corners = {
        "top_left": (0, 0),
        "top_right": (src_w - pw, 0),
        "bottom_left": (0, src_h - ph),
        "bottom_right": (src_w - pw, src_h - ph),
    }

    # Distance threshold: empirically 60 (in 0-255 RGB space) separates
    # "same UI background" from "different content like wallpaper".
    THRESHOLD = 60

    violations: list[dict] = []
    for name, (x, y) in corners.items():
        c_rgb = _patch_mean_rgb(rgb, x, y, pw, ph)
        d = _rgb_distance(c_rgb, center)
        if d > THRESHOLD:
            violations.append({"corner": name, "bbox": (x, y, pw, ph), "dist": d})

    if not violations:
        return {
            "name": "app_bbox_full_frame",
            "passed": True,
            "severity": "PASS",
            "details": (
                f"all 4 corners match center color (max dist "
                f"{max(_rgb_distance(_patch_mean_rgb(rgb, x, y, pw, ph), center) for _, (x, y) in corners.items()):.0f} < {THRESHOLD})"
            ),
            "coverage": 1.0,
        }

    # Escape hatch: if all 4 corners are similar to EACH OTHER (uniform
    # background), it's likely a centered-content frame (text on solid bg,
    # title card, etc.) — not wallpaper bleed. Wallpaper gradients vary
    # across corners; app backgrounds don't.
    corner_rgbs = [
        _patch_mean_rgb(rgb, x, y, pw, ph) for _, (x, y) in corners.items()
    ]
    max_corner_to_corner = 0.0
    for i in range(len(corner_rgbs)):
        for j in range(i + 1, len(corner_rgbs)):
            d = _rgb_distance(corner_rgbs[i], corner_rgbs[j])
            max_corner_to_corner = max(max_corner_to_corner, d)

    UNIFORM_BG_THRESHOLD = 40
    if max_corner_to_corner < UNIFORM_BG_THRESHOLD:
        return {
            "name": "app_bbox_full_frame",
            "passed": True,
            "severity": "PASS",
            "details": (
                f"corners differ from center but are uniform with each other "
                f"(max corner-to-corner Δ={max_corner_to_corner:.0f} < {UNIFORM_BG_THRESHOLD}); "
                f"likely centered content on uniform background — not wallpaper bleed"
            ),
            "coverage": 1.0,
        }

    # Build a composite bbox of all violating corners for annotation
    primary = max(violations, key=lambda v: v["dist"])
    summary = ", ".join(f"{v['corner']} (Δ={v['dist']:.0f})" for v in violations)

    return {
        "name": "app_bbox_full_frame",
        "passed": False,
        "severity": "FAIL",
        "details": (
            f"wallpaper bleed detected: {len(violations)}/4 corners differ "
            f"from center by >{THRESHOLD} AND corners vary among each other "
            f"(max corner-to-corner Δ={max_corner_to_corner:.0f}): {summary}"
        ),
        "bbox": primary["bbox"],
        "all_bboxes": [v["bbox"] for v in violations],
        "coverage": 1.0 - (len(violations) / 4) * 0.1,
    }


def check_no_menu_bar(img: Image.Image) -> dict:
    """
    Sample the top 28-px band. macOS menu bar shows as a horizontal strip
    with HIGH luminance variance (text on uniform background).

    Heuristic v1: if the top 28px row-band has variance noticeably HIGHER
    than the next 200px band, flag as menu bar.
    """
    gray = img.convert("L")
    w, h = gray.size
    band_h = min(EDGE_BAND_PX_TOP, h // 20)

    top_band = gray.crop((0, 0, w, band_h))
    body_band = gray.crop((0, band_h, w, min(band_h + 200, h)))

    def _stdev(im):
        pixels = list(im.getdata())
        if not pixels:
            return 0
        return statistics.stdev(pixels) if len(pixels) > 1 else 0

    top_std = _stdev(top_band)
    body_std = _stdev(body_band)
    # Menu bar shows higher variance than the body just below it
    suspicious = body_std > 0 and (top_std / max(body_std, 1)) > 2.0

    return {
        "name": "no_menu_bar",
        "passed": not suspicious,
        "severity": "FAIL" if suspicious else "PASS",
        "details": (
            f"top-band stdev={top_std:.1f}, body-band stdev={body_std:.1f} "
            f"(ratio {top_std/max(body_std,1):.2f}; >2.0 indicates menu bar)"
        ),
        "bbox": (0, 0, w, band_h) if suspicious else None,
    }


def check_no_dock(img: Image.Image) -> dict:
    """
    Sample the bottom 80-px band. Dock typically has rounded translucent
    background + icon clusters; shows up as high-saturation + variance.

    Heuristic v1: if the bottom band variance is much higher than the
    body band just above it (mirroring menu-bar heuristic).
    """
    gray = img.convert("L")
    w, h = gray.size
    band_h = min(EDGE_BAND_PX_BOTTOM, h // 8)

    bottom_band = gray.crop((0, h - band_h, w, h))
    body_band = gray.crop((0, max(0, h - band_h - 200), w, h - band_h))

    def _stdev(im):
        pixels = list(im.getdata())
        return statistics.stdev(pixels) if len(pixels) > 1 else 0

    bot_std = _stdev(bottom_band)
    body_std = _stdev(body_band)
    suspicious = body_std > 0 and (bot_std / max(body_std, 1)) > 1.8

    return {
        "name": "no_dock",
        "passed": not suspicious,
        "severity": "FAIL" if suspicious else "PASS",
        "details": (
            f"bottom-band stdev={bot_std:.1f}, body-band stdev={body_std:.1f} "
            f"(ratio {bot_std/max(body_std,1):.2f}; >1.8 indicates dock)"
        ),
        "bbox": (0, h - band_h, w, band_h) if suspicious else None,
    }


def check_no_notification_banner(img: Image.Image) -> dict:
    """
    Sample top-right corner for a banner-shaped high-contrast region.
    macOS notifications are ~340×95 in top-right.
    """
    gray = img.convert("L")
    w, h = gray.size
    band_w = min(NOTIFICATION_BANNER_W, w // 4)
    band_h = min(NOTIFICATION_BANNER_H, h // 8)

    # Compare top-right block stdev vs immediate-left block stdev
    tr = gray.crop((w - band_w, 0, w, band_h))
    left = gray.crop((w - 2 * band_w, 0, w - band_w, band_h))

    def _stdev(im):
        pixels = list(im.getdata())
        return statistics.stdev(pixels) if len(pixels) > 1 else 0

    tr_std = _stdev(tr)
    left_std = _stdev(left)
    suspicious = left_std > 0 and (tr_std / max(left_std, 1)) > 1.6

    return {
        "name": "no_notification_banner",
        "passed": not suspicious,
        "severity": "FAIL" if suspicious else "PASS",
        "details": (
            f"top-right stdev={tr_std:.1f}, left-adjacent stdev={left_std:.1f} "
            f"(ratio {tr_std/max(left_std,1):.2f}; >1.6 indicates banner)"
        ),
        "bbox": (w - band_w, 0, band_w, band_h) if suspicious else None,
    }


def check_axis_aligned(img: Image.Image, bbox_result: dict) -> dict:
    """
    Tilt detection. If app_bbox already passed, no tilt to worry about.
    If it failed, sample 4 corners at small rotation offsets — if rotation
    makes corners MATCH the center (Δ shrinks), the source was tilted.
    """
    if bbox_result.get("passed", True):
        return {
            "name": "axis_aligned",
            "passed": True,
            "severity": "PASS",
            "details": "app fills frame; tilt N/A",
        }

    # Try a small counter-rotation. If 4 corners become "more similar to
    # center" after rotation, the source was tilted.
    src_w, src_h = img.size
    pw = max(32, int(src_w * 0.03))
    ph = max(32, int(src_h * 0.03))
    rgb = img.convert("RGB")

    def _avg_corner_dist(image: Image.Image) -> float:
        cx = (src_w - pw) // 2
        cy = (src_h - ph) // 2
        center = _patch_mean_rgb(image, cx, cy, pw, ph)
        corners = [
            _patch_mean_rgb(image, 0, 0, pw, ph),
            _patch_mean_rgb(image, src_w - pw, 0, pw, ph),
            _patch_mean_rgb(image, 0, src_h - ph, pw, ph),
            _patch_mean_rgb(image, src_w - pw, src_h - ph, pw, ph),
        ]
        return sum(_rgb_distance(c, center) for c in corners) / 4

    orig_dist = _avg_corner_dist(rgb)

    # Try ±2° and ±5° rotations
    best_rot = None
    best_dist = orig_dist
    for angle in [-5, -3, -2, -1, 1, 2, 3, 5]:
        rotated = rgb.rotate(angle, expand=False, fillcolor=(0, 0, 0))
        d = _avg_corner_dist(rotated)
        if d < best_dist:
            best_dist = d
            best_rot = angle

    # If a small rotation reduces corner-to-center distance by >25%,
    # the source was tilted by approximately that angle.
    is_tilted = best_rot is not None and (orig_dist - best_dist) > orig_dist * 0.25

    return {
        "name": "axis_aligned",
        "passed": not is_tilted,
        "severity": "FAIL" if is_tilted else "WARN",
        "details": (
            f"corner-to-center distance: orig {orig_dist:.0f}, "
            f"best at {best_rot}° = {best_dist:.0f} "
            f"({'TILTED' if is_tilted else 'wallpaper-bleed (not tilt)'})"
        ),
    }


# ----------------------------------------------------------------------
# Screen Studio composition checks
# ----------------------------------------------------------------------

def _find_inner_content_bbox(img: Image.Image) -> tuple[int, int, int, int] | None:
    """
    Detect the inner captured-window rectangle inside a Screen Studio composition.
    SS composites the captured window onto a uniform designer background; the
    inner rect is bounded by pixels that differ from the background color.
    Returns (x, y, w, h) or None if no clear inner rect (composition is flat).

    Approach: sample the four outermost corners to estimate the background
    color, then find the bbox of all pixels whose distance from that
    background exceeds a threshold. More reliable than edge-density on a
    uniform-background composition.
    """
    src_w, src_h = img.size
    # Downscale for speed; ~320px wide is plenty for window-boundary detection.
    target_w = 320
    scale = target_w / src_w
    work = img.convert("RGB").resize((target_w, int(src_h * scale)))
    w, h = work.size
    pixels = list(work.getdata())  # row-major

    # Background sample: ~3px patches from each corner; median per channel.
    PATCH = 3
    samples: list[tuple[int, int, int]] = []
    for cx, cy in [(0, 0), (w - PATCH, 0), (0, h - PATCH), (w - PATCH, h - PATCH)]:
        for dy in range(PATCH):
            for dx in range(PATCH):
                samples.append(pixels[(cy + dy) * w + (cx + dx)])
    bg_r = statistics.median(s[0] for s in samples)
    bg_g = statistics.median(s[1] for s in samples)
    bg_b = statistics.median(s[2] for s in samples)
    BG_DIST_THRESHOLD = 25  # 0–255 space; anything closer is "background"

    def _is_fg(px: tuple[int, int, int]) -> bool:
        return (
            (px[0] - bg_r) ** 2 + (px[1] - bg_g) ** 2 + (px[2] - bg_b) ** 2
        ) ** 0.5 > BG_DIST_THRESHOLD

    min_x, min_y, max_x, max_y = w, h, -1, -1
    for y in range(h):
        row_off = y * w
        for x in range(w):
            if _is_fg(pixels[row_off + x]):
                if x < min_x: min_x = x
                if x > max_x: max_x = x
                if y < min_y: min_y = y
                if y > max_y: max_y = y
    if max_x < 0 or max_y < 0:
        return None  # entire frame matches background — flat composition
    inner_w = max_x - min_x + 1
    inner_h = max_y - min_y + 1
    if inner_w < w * 0.3 or inner_h < h * 0.3:
        return None
    # Scale back to source resolution
    sx = src_w / w
    sy = src_h / h
    return (int(min_x * sx), int(min_y * sy), int(inner_w * sx), int(inner_h * sy))


def check_screen_studio_composition(img: Image.Image) -> dict:
    """
    Verify the captured window is roughly centered and has reasonable padding
    inside a Screen Studio composition. FAIL if the inner rect is jammed
    against an edge (lost padding) or if no inner rect can be detected.
    """
    src_w, src_h = img.size
    bbox = _find_inner_content_bbox(img)
    if bbox is None:
        return {
            "name": "screen_studio_composition",
            "passed": False,
            "severity": "FAIL",
            "details": "could not detect an inner captured-window rect — composition may be flat / unfinished",
        }
    x, y, w, h = bbox
    cx_inner = x + w / 2
    cy_inner = y + h / 2
    off_x = abs(cx_inner - src_w / 2) / src_w
    off_y = abs(cy_inner - src_h / 2) / src_h
    pad_left = x / src_w
    pad_right = (src_w - (x + w)) / src_w
    pad_top = y / src_h
    pad_bottom = (src_h - (y + h)) / src_h
    min_pad = min(pad_left, pad_right, pad_top, pad_bottom)

    # Off-center >8% of frame, or any side padding <1.5%, fails.
    off_center = off_x > 0.08 or off_y > 0.08
    no_padding = min_pad < 0.015
    passed = not (off_center or no_padding)
    issues = []
    if off_center:
        issues.append(f"off-center (Δx={off_x:.1%}, Δy={off_y:.1%})")
    if no_padding:
        issues.append(f"insufficient padding (min={min_pad:.1%})")
    return {
        "name": "screen_studio_composition",
        "passed": passed,
        "severity": "FAIL" if not passed else "PASS",
        "details": (
            f"inner rect {w}×{h} at ({x},{y}); pad L={pad_left:.1%} R={pad_right:.1%} "
            f"T={pad_top:.1%} B={pad_bottom:.1%}"
            + (f"; {', '.join(issues)}" if issues else "")
        ),
        "bbox": bbox if not passed else None,
    }


# ----------------------------------------------------------------------
# Orchestrator
# ----------------------------------------------------------------------

# Sources that change which checks are valid. Default = raw screen capture
# (QuickTime, OBS, screencapture). screen-studio = composited output from
# Screen Studio, which by construction has no menu bar / dock / wallpaper
# bleed / tilt; the captured window is centered on a designer background.
SOURCE_DEFAULT = "default"
SOURCE_SCREEN_STUDIO = "screen-studio"
VALID_SOURCES = {SOURCE_DEFAULT, SOURCE_SCREEN_STUDIO}


def run_all(
    img: Image.Image,
    meta: dict | None = None,
    source: str = SOURCE_DEFAULT,
) -> list[dict]:
    """Run all checks against a frame + (optional) ffprobe meta."""
    if source not in VALID_SOURCES:
        raise ValueError(f"unknown source: {source!r} (valid: {sorted(VALID_SOURCES)})")

    results = []
    if meta is not None:
        results.append(check_resolution(meta))

    if source == SOURCE_SCREEN_STUDIO:
        # Screen Studio composites the captured window onto a designer
        # background. Raw-capture checks (wallpaper bleed, menu bar, dock,
        # tilt, top-right notification) are all by-construction inapplicable:
        # the background IS intentional, no OS chrome leaks through, and the
        # output is always axis-aligned. A real notification leak would appear
        # *inside* the inner captured window, not at the frame edge — TODO.
        results.append(check_screen_studio_composition(img))
        return results

    bbox = check_app_bbox(img)
    results.append(bbox)
    results.append(check_axis_aligned(img, bbox))
    results.append(check_no_menu_bar(img))
    results.append(check_no_dock(img))
    results.append(check_no_notification_banner(img))

    return results


def summarize(results: list[dict]) -> dict:
    failures = [r for r in results if r["severity"] == "FAIL" and not r["passed"]]
    warns = [r for r in results if r["severity"] == "WARN" and not r["passed"]]
    return {
        "passed": len(failures) == 0,
        "fail_count": len(failures),
        "warn_count": len(warns),
        "checks": results,
    }
