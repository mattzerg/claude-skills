"""Motion recipes — composable ffmpeg primitives for short product launch videos.

Every recipe is anchored to a measured exemplar from techniques.md. Numbers
in defaults reflect what was actually measured in real launch videos
(Linear, Cursor, Stripe, Notion Calendar, etc.). Don't tune off-recipe
without a reason — the value of this library is consistency.

Each function takes input/output paths + parameters and produces a clip
ready to concat. Output is always 1920×1080 H.264 30fps.

Priority order (see techniques.md §10):
  1. linear_push_in        — used in 6/10 references
  2. crash_cut_to_title    — Linear's structural signature
  3. interview_lower_third_slide_in
  4. typewriter_punctual
  5. kenburns_macro
  6. logo_card_silence
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path
from typing import Iterable

from PIL import Image, ImageDraw, ImageFont

# ── Brand palette (matches blog-imagery + end_card.py) ──
BG = (7, 17, 30)            # #07111E navy
CARD = (14, 27, 45)
ACCENT = (244, 162, 97)     # amber
ACCENT_BLUE = (68, 184, 255)
TEXT = (235, 241, 248)
MUTED = (148, 166, 186)

OUT_W, OUT_H = 1920, 1080
FPS = 30


# ── Font loading ──

_MONO_PATHS = [
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Supplemental/Andale Mono.ttf",
]
_SANS_PATHS = [
    "/System/Library/Fonts/Helvetica.ttc",
    "/System/Library/Fonts/HelveticaNeue.ttc",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
]


def _load_font(size, paths):
    for p in paths:
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def mono(size):
    return _load_font(size, _MONO_PATHS)


def sans(size):
    return _load_font(size, _SANS_PATHS)


# ── Recipe 1: linear_push_in ──

def linear_push_in(
    input_path: Path,
    output_path: Path,
    *,
    duration_s: float = 2.5,
    scale_start: float = 1.00,
    scale_end: float = 1.04,
    src_ss: float = 0.0,
) -> Path:
    """Slow LINEAR (no easing) zoom across a static UI shot.
    Measured: Cursor-3 0:35–0:40, Vercel-Workflows 0:11–0:15.

    Args:
        input_path: source video to push in on
        output_path: where to write the resulting clip
        duration_s: total clip length (default 2.5s — middle of measured 2.0–3.0s range)
        scale_start: starting zoom (default 1.00 = no zoom)
        scale_end: ending zoom (default 1.04 = 4% — measured average)
        src_ss: how far into source to start
    Anti-pattern: don't go past 1.06 — that becomes "zoomy" not "alive".
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    total_frames = max(1, int(duration_s * FPS))
    # Linear zoom: z(t) = scale_start + (scale_end - scale_start) * (on / total_frames)
    z_expr = f"({scale_start}+({scale_end - scale_start})*on/{total_frames})"
    # Center the zoom — keep the visual focus on the middle of the frame
    x_expr = "iw/2-(iw/zoom/2)"
    y_expr = "ih/2-(ih/zoom/2)"
    zoompan = (
        f"zoompan=z='{z_expr}':x='{x_expr}':y='{y_expr}':"
        f"d=1:s={OUT_W}x{OUT_H}:fps={FPS}"
    )
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(src_ss), "-i", str(input_path),
        "-t", str(duration_s),
        "-vf", f"{zoompan},setsar=1",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an", str(output_path),
    ], check=True)
    return output_path


# ── Recipe 2: crash_cut_to_title ──

def _render_title_card_png(
    text: str,
    *,
    out_path: Path,
    font_size_pct: float = 3.5,
    letter_spacing_em: float = 0.10,
    color: tuple = TEXT,
    bg: tuple = BG,
) -> Path:
    """Render a Linear-style title-card frame: mono caps, generous letter
    spacing, exactly centered, no decoration. The CUT is the entrance —
    no fade, no animation.
    """
    img = Image.new("RGB", (OUT_W, OUT_H), bg)
    d = ImageDraw.Draw(img)
    font_size = int(OUT_H * font_size_pct / 100.0)
    f = mono(font_size)

    # Letter-spacing simulation: render glyphs one at a time with tracking.
    # ImageDraw doesn't support letter-spacing natively, so we measure each
    # char and offset by font_size * letter_spacing_em between chars.
    text_upper = text.upper()
    char_widths = []
    for ch in text_upper:
        bbox = d.textbbox((0, 0), ch, font=f)
        char_widths.append(bbox[2] - bbox[0])
    spacing_px = font_size * letter_spacing_em
    total_w = sum(char_widths) + spacing_px * max(0, len(text_upper) - 1)
    bbox_h = d.textbbox((0, 0), "M", font=f)
    text_h = bbox_h[3] - bbox_h[1]
    cursor_x = (OUT_W - total_w) // 2
    cursor_y = (OUT_H - text_h) // 2 - bbox_h[1]
    for ch, cw in zip(text_upper, char_widths):
        d.text((cursor_x, cursor_y), ch, font=f, fill=color)
        cursor_x += cw + spacing_px

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, "PNG")
    return out_path


def title_card_branded(
    output_path: Path,
    *,
    headline: str = "Zergboard.",
    subtitle: str = "The board your AI agents can use.",
    brand_slug: str = "zergboard",
    hold_s: float = 1.5,
    fade_in_s: float = 0.0,
) -> Path:
    """Branded opening title card — Zergboard identity, NOT Linear-clone.
    Brand mark top-left + sans headline + sans subtitle + amber accent underline.
    Same visual language as `logo_card_silence` so the bookends match.

    Use this as the OPENING bookend on Zergboard videos. Use crash_cut_to_title
    only for INTERNAL section breaks within the video.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    end_card_script = Path.home() / ".claude/skills/product-video-skill/lib/end_card.py"
    png_path = output_path.with_suffix(".png")
    cmd = [
        "python3", str(end_card_script),
        "--headline", headline,
        "--brand", brand_slug,
        "--aspect", "16:9",
        "--no-cta", "--no-url",
        "--out", str(png_path),
    ]
    if subtitle:
        cmd += ["--subtitle", subtitle]
    subprocess.run(cmd, check=True)

    fade_filter = f",fade=t=in:st=0:d={fade_in_s}" if fade_in_s > 0 else ""
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-t", str(hold_s), "-i", str(png_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-vf", f"scale={OUT_W}:{OUT_H},setsar=1{fade_filter}",
        str(output_path),
    ], check=True)
    return output_path


def crash_cut_to_title(
    text: str,
    output_path: Path,
    *,
    hold_s: float = 1.7,
    font_size_pct: float = 3.5,
    letter_spacing_em: float = 0.10,
) -> Path:
    """LINEAR-style internal section break — pure-black frame with mono
    caps centered, hard cuts on both sides. NOT a brand bookend; use
    title_card_branded for the opening and logo_card_silence for the
    closing. This recipe is for mid-video punctuation only.

    Measured: 1.5–2.2s hold (default 1.7s = midpoint of measured range).
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    png_path = output_path.with_suffix(".png")
    _render_title_card_png(
        text, out_path=png_path,
        font_size_pct=font_size_pct,
        letter_spacing_em=letter_spacing_em,
    )
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-t", str(hold_s), "-i", str(png_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-vf", f"scale={OUT_W}:{OUT_H},setsar=1",
        str(output_path),
    ], check=True)
    return output_path


# ── Recipe 3: interview_lower_third_slide_in ──

def interview_lower_third_overlay(
    input_path: Path,
    output_path: Path,
    *,
    name: str,
    role: str,
    slide_in_at: float = 3.0,
    slide_in_dur: float = 0.4,
    hold_s: float = 3.0,
    fade_out_dur: float = 0.2,
    x_pct: float = 4.0,
    y_pct: float = 82.0,
) -> Path:
    """Overlay a name + role lower-third on an existing clip. Slides up
    from below frame edge with ease-out, holds, fades out.
    Measured: cursor-3 0:05.0 (Sualeh Asif/Co-Founder), vercel-workflows 0:08.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    name_size = int(OUT_H * 0.028)
    role_size = int(OUT_H * 0.016)

    # Render the lower-third as a transparent PNG
    png_path = output_path.with_suffix(".lt.png")
    f_name = sans(name_size)
    f_role = sans(role_size)
    pad = 18
    name_bb = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), name, font=f_name)
    role_bb = ImageDraw.Draw(Image.new("RGBA", (1, 1))).textbbox((0, 0), role, font=f_role)
    box_w = max(name_bb[2], role_bb[2]) + pad * 2
    box_h = (name_bb[3] - name_bb[1]) + (role_bb[3] - role_bb[1]) + pad * 2 + 6
    img = Image.new("RGBA", (box_w, box_h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, box_w, box_h], radius=8, fill=(7, 17, 30, 200))
    d.text((pad, pad), name, font=f_name, fill=TEXT)
    d.text((pad, pad + (name_bb[3] - name_bb[1]) + 6), role, font=f_role, fill=MUTED)
    img.save(png_path, "PNG")

    # Position
    x_px = int(OUT_W * x_pct / 100.0)
    y_target = int(OUT_H * y_pct / 100.0)
    y_offscreen = OUT_H + 50  # below frame
    # Slide-in: y goes from y_offscreen → y_target over slide_in_dur (ease-out)
    # ease-out = 1 - (1-u)^3 where u=(t - slide_in_at) / slide_in_dur
    fade_out_at = slide_in_at + slide_in_dur + hold_s
    end_at = fade_out_at + fade_out_dur

    # Use overlay with time-varying y
    # y(t) = y_offscreen for t < slide_in_at
    # y(t) = ease_out from y_offscreen to y_target during slide_in
    # y(t) = y_target for slide_in_at + slide_in_dur < t < fade_out_at
    # alpha for fade_out via format=rgba + colorkey... or just hide via overlay enable
    # Simpler: keep y constant after slide_in, use enable= for visibility window
    u = f"((t-{slide_in_at})/{slide_in_dur})"
    ease_u = f"(1-pow(1-min(1,max(0,{u})),3))"
    y_expr = (
        f"if(lt(t,{slide_in_at}),{y_offscreen},"
        f"if(lt(t,{slide_in_at + slide_in_dur}),"
        f"{y_offscreen}+({y_target - y_offscreen})*{ease_u},"
        f"{y_target}))"
    )
    enable_expr = f"between(t,{slide_in_at},{end_at})"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(input_path),
        "-i", str(png_path),
        "-filter_complex",
        f"[0:v][1:v]overlay=x={x_px}:y='{y_expr}':enable='{enable_expr}'[v]",
        "-map", "[v]",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        str(output_path),
    ], check=True)
    return output_path


# ── Recipe 4: typewriter_punctual ──

def typewriter_punctual(
    text: str,
    output_path: Path,
    *,
    chars_per_sec: float = 11.0,
    cursor_blink_hz: float = 2.0,
    hold_after_complete_s: float = 1.5,
    font_size_pct: float = 5.5,
    letter_spacing_em: float = 0.08,
    color: tuple = TEXT,
    bg: tuple = BG,
) -> Path:
    """Generate a clip where text appears one character at a time, then
    holds with a blinking block cursor.

    Measured: Linear-Releases 0:24–0:26 ("AVAILABLE NOW", 13 chars in 1.0s).
    Default chars_per_sec=11 sits at the lower-fast end of the measured 10–12 range.

    Total duration = (len(text) / chars_per_sec) + hold_after_complete_s.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    text_upper = text.upper()
    n_chars = len(text_upper)
    typing_dur = n_chars / chars_per_sec
    total_dur = typing_dur + hold_after_complete_s
    total_frames = max(1, int(total_dur * FPS))

    # Render each unique state as a frame: (chars_visible, cursor_on)
    # Then output a sequence at FPS via image2.
    tmp_dir = output_path.parent / f"{output_path.stem}_frames"
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)

    font_size = int(OUT_H * font_size_pct / 100.0)
    f = mono(font_size)
    # Pre-measure for centering
    bbox_full = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), text_upper, font=f)
    char_widths = []
    for ch in text_upper:
        b = ImageDraw.Draw(Image.new("RGB", (1, 1))).textbbox((0, 0), ch, font=f)
        char_widths.append(b[2] - b[0])
    spacing_px = font_size * letter_spacing_em
    total_w = sum(char_widths) + spacing_px * max(0, n_chars - 1)
    text_h = bbox_full[3] - bbox_full[1]
    base_x = (OUT_W - total_w) // 2
    base_y = (OUT_H - text_h) // 2 - bbox_full[1]

    cursor_period_frames = int(FPS / cursor_blink_hz)  # frames per blink half-cycle
    cursor_w = int(font_size * 0.55)  # block-cursor width
    cursor_h = text_h

    for frame_idx in range(total_frames):
        t = frame_idx / FPS
        chars_visible = min(n_chars, int(t * chars_per_sec))
        # Cursor on/off for blink. Always on while typing; blink after complete.
        if chars_visible < n_chars:
            cursor_on = True
        else:
            # 50% duty cycle at cursor_blink_hz
            cursor_on = ((frame_idx // cursor_period_frames) % 2) == 0

        img = Image.new("RGB", (OUT_W, OUT_H), bg)
        d = ImageDraw.Draw(img)
        cursor_x = base_x
        for i in range(chars_visible):
            d.text((cursor_x, base_y), text_upper[i], font=f, fill=color)
            cursor_x += char_widths[i] + spacing_px
        # Block cursor at current insertion point
        if cursor_on:
            d.rectangle(
                [cursor_x, base_y + 4, cursor_x + cursor_w, base_y + cursor_h + 4],
                fill=color,
            )
        img.save(tmp_dir / f"f{frame_idx:05d}.png", "PNG")

    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", str(FPS),
        "-i", str(tmp_dir / "f%05d.png"),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-vf", f"scale={OUT_W}:{OUT_H},setsar=1",
        str(output_path),
    ], check=True)
    shutil.rmtree(tmp_dir)
    return output_path


# ── Recipe 5: kenburns_macro ──

def kenburns_macro(
    input_path: Path,
    output_path: Path,
    *,
    duration_s: float = 3.5,
    scale_start: float = 1.00,
    scale_end: float = 1.10,
    pan_x_px: int = 60,  # ±60 px measured average
    pan_y_px: int = 0,
    src_ss: float = 0.0,
) -> Path:
    """Slow combined zoom+drift on a still or B-roll. ease-in-out.
    Measured: Replit-Agent4 0:10–0:14 (Marin County aerial).
    Anti-pattern: never under 3.5s — twitchy.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if duration_s < 3.5:
        print(f"[kenburns_macro] WARN: duration {duration_s}s < 3.5s minimum; will look twitchy")
    total_frames = max(1, int(duration_s * FPS))
    # ease-in-out: smoothstep
    u = f"min(1,on/{total_frames})"
    e = f"({u}*{u}*(3-2*{u}))"
    z_expr = f"({scale_start}+({scale_end - scale_start})*{e})"
    x_center = f"iw/2-(iw/zoom/2)+({pan_x_px})*{e}"
    y_center = f"ih/2-(ih/zoom/2)+({pan_y_px})*{e}"
    zoompan = (
        f"zoompan=z='{z_expr}':x='{x_center}':y='{y_center}':"
        f"d=1:s={OUT_W}x{OUT_H}:fps={FPS}"
    )
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-ss", str(src_ss), "-i", str(input_path),
        "-t", str(duration_s),
        "-vf", f"{zoompan},setsar=1",
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-an", str(output_path),
    ], check=True)
    return output_path


# ── Recipe 6: logo_card_silence ──

def logo_card_silence(
    output_path: Path,
    *,
    headline: str = "Zergboard.",
    subtitle: str = "",
    cta: str = "",
    url: str = "",
    brand_slug: str = "zergboard",
    hold_s: float = 4.0,
) -> Path:
    """End card held for hold_s seconds. Designed to be paired with a
    music-out so the silence falls on the logo.

    Measured: linear-agent 4.0s, linear-releases 2.5s, stripe 1.2s.
    Default 4.0s = Linear's pattern (most prestigious). The KEY is that
    music drops out under or before this clip, so logo is in silence.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    end_card_script = Path.home() / ".claude/skills/product-video-skill/lib/end_card.py"
    png_path = output_path.with_suffix(".png")
    cmd = [
        "python3", str(end_card_script),
        "--headline", headline,
        "--brand", brand_slug,
        "--aspect", "16:9",
        "--out", str(png_path),
    ]
    if subtitle:
        cmd += ["--subtitle", subtitle]
    if cta:
        cmd += ["--cta", cta]
    else:
        cmd += ["--no-cta"]
    if url:
        cmd += ["--url", url]
    else:
        cmd += ["--no-url"]
    subprocess.run(cmd, check=True)

    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-loop", "1", "-t", str(hold_s), "-i", str(png_path),
        "-c:v", "libx264", "-preset", "medium", "-crf", "20",
        "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-vf", f"scale={OUT_W}:{OUT_H},setsar=1,fade=t=in:st=0:d=0.5",
        str(output_path),
    ], check=True)
    return output_path


# ── Concat helper ──

def concat_clips(clip_paths: Iterable[Path], output_path: Path) -> Path:
    """Concat multiple clips into one. Assumes all clips are 1920×1080
    H.264 30fps.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    list_path = output_path.with_suffix(".list.txt")
    list_path.write_text("\n".join(f"file '{p}'" for p in clip_paths) + "\n")
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", str(list_path),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ], check=True)
    return output_path


# ── Music mix helper ──

def mix_music(
    silent_video_path: Path,
    music_path: Path,
    output_path: Path,
    *,
    duration_s: float = None,
    music_out_at_s: float = None,
    volume: float = 0.55,
    fade_in_s: float = 0.5,
    fade_out_s: float = 0.8,
) -> Path:
    """Mix a music bed under a silent video. Critical pattern: if
    music_out_at_s is set, music fades out before the end so the closing
    logo card holds in silence. This is the most consistent pattern across
    all 10 reference videos (techniques.md §6).

    Default `volume=0.55` is what we measured working across the dataset.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if duration_s is None:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(silent_video_path)],
            capture_output=True, text=True, check=True,
        )
        duration_s = float(result.stdout.strip())

    if music_out_at_s is None:
        music_out_at_s = max(0.5, duration_s - fade_out_s)

    # Music goes from 0 to music_out_at_s, fades from (music_out_at_s - fade_out_s) to music_out_at_s
    fade_out_st = max(0.0, music_out_at_s - fade_out_s)
    audio_filter = (
        f"[1:a]atrim=0:{music_out_at_s},"
        f"afade=t=in:st=0:d={fade_in_s},"
        f"afade=t=out:st={fade_out_st}:d={fade_out_s},"
        f"volume={volume},"
        f"apad=whole_dur={duration_s}[m]"
    )
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(silent_video_path),
        "-stream_loop", "-1", "-i", str(music_path),
        "-filter_complex", audio_filter,
        "-map", "0:v", "-map", "[m]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
        "-shortest",
        "-movflags", "+faststart",
        str(output_path),
    ], check=True)
    return output_path


if __name__ == "__main__":
    # Smoke test: render one of each primitive to /tmp
    print("Smoke-testing recipes...")
    out = Path("/tmp/motion_recipes_smoke")
    out.mkdir(parents=True, exist_ok=True)
    # Title card
    crash_cut_to_title("PROJECT BOARDS FOR AGENTS", out / "title.mp4")
    # Typewriter
    typewriter_punctual("AVAILABLE NOW", out / "typewriter.mp4")
    # Logo card
    logo_card_silence(out / "logo.mp4", headline="Zergboard.",
                      subtitle="The board your AI agents can use.")
    print(f"Smoke test outputs in {out}:")
    for p in sorted(out.glob("*.mp4")):
        size_kb = p.stat().st_size // 1024
        print(f"  {p.name}  {size_kb} KB")
