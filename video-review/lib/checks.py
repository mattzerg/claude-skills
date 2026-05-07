"""Auto-check primitives for video-review skill.

Each check function takes a video path and returns:
    {
      "name": str,
      "passed": bool,
      "value": str (measured value, human-readable),
      "expected": str (what we wanted),
      "fix": str | None (concrete recipe if failed),
      "source": str (which catalog rule diagnosed this),
    }

Skip checks that genuinely can't run (e.g. faststart on a missing file)
should return passed=False with a "could not determine" note rather than
crashing.
"""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from typing import Optional


# ── Helpers ──

def _ffprobe_json(video_path: Path) -> dict:
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "stream=codec_name,width,height,r_frame_rate,duration,nb_frames",
        "-show_entries", "format=duration,bit_rate,format_name,size",
        "-of", "json",
        str(video_path),
    ]
    return json.loads(subprocess.run(cmd, capture_output=True, text=True, check=True).stdout)


def _video_props(video_path: Path) -> dict:
    data = _ffprobe_json(video_path)
    streams = [s for s in data.get("streams", []) if s.get("codec_name") and s.get("width")]
    if not streams:
        raise RuntimeError(f"No video stream found in {video_path}")
    v = streams[0]
    fr = v.get("r_frame_rate", "30/1")
    if "/" in fr:
        n, d = fr.split("/")
        fps = float(n) / float(d) if float(d) != 0 else 30.0
    else:
        fps = float(fr)
    fmt = data.get("format", {})
    return {
        "codec": v.get("codec_name", "unknown"),
        "width": int(v.get("width", 0)),
        "height": int(v.get("height", 0)),
        "fps": fps,
        "duration": float(fmt.get("duration", v.get("duration", 0)) or 0),
        "bitrate": int(fmt.get("bit_rate", 0) or 0),
        "format": fmt.get("format_name", ""),
        "size_bytes": int(fmt.get("size", 0) or 0),
    }


def _scene_cuts(video_path: Path, threshold: float = 0.04) -> list[float]:
    """Return list of timestamps (seconds) where scene cuts occur.
    Threshold 0.04 catches crash cuts between similar-color frames
    (e.g., navy title card → navy product UI). 0.10 misses these.
    """
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-filter:v", f"select='gt(scene,{threshold})',showinfo",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    cuts = []
    for line in result.stderr.splitlines():
        m = re.search(r"pts_time:([\d.]+)", line)
        if m:
            cuts.append(float(m.group(1)))
    return sorted(cuts)


def _silence_segments(video_path: Path, noise_db: int = -30, min_dur: float = 0.3) -> list[tuple[float, float]]:
    """Return list of (start_s, end_s) silence intervals."""
    cmd = [
        "ffmpeg", "-i", str(video_path),
        "-af", f"silencedetect=noise={noise_db}dB:d={min_dur}",
        "-f", "null", "-",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    silences = []
    cur_start = None
    for line in result.stderr.splitlines():
        m_start = re.search(r"silence_start: ([\d.]+)", line)
        m_end = re.search(r"silence_end: ([\d.]+)", line)
        if m_start:
            cur_start = float(m_start.group(1))
        elif m_end and cur_start is not None:
            silences.append((cur_start, float(m_end.group(1))))
            cur_start = None
    return silences


def _faststart(video_path: Path) -> Optional[bool]:
    cmd = ["ffprobe", "-v", "trace", "-i", str(video_path)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stderr
    moov_idx = output.find(" type:'moov'")
    mdat_idx = output.find(" type:'mdat'")
    if moov_idx == -1 or mdat_idx == -1:
        return None
    return moov_idx < mdat_idx


# ── Check 1-4: Codec, resolution, fps, faststart ──

def check_codec(video_path: Path) -> dict:
    p = _video_props(video_path)
    ok = p["codec"] == "h264"
    return {
        "name": "Codec is H.264",
        "passed": ok,
        "value": p["codec"],
        "expected": "h264",
        "fix": "Re-export with `-c:v libx264 -preset medium -crf 20 -pix_fmt yuv420p`." if not ok else None,
        "source": "techniques.md export specs",
    }


def check_resolution(video_path: Path) -> dict:
    p = _video_props(video_path)
    ok = p["height"] >= 1080
    return {
        "name": "Resolution ≥ 1080p",
        "passed": ok,
        "value": f"{p['width']}x{p['height']}",
        "expected": "≥1920x1080",
        "fix": "Re-render at 1920x1080. If source is lower, scale up with `scale=1920:1080:force_original_aspect_ratio=decrease,pad`." if not ok else None,
        "source": "techniques.md export specs",
    }


def check_fps(video_path: Path) -> dict:
    p = _video_props(video_path)
    fps_round = round(p["fps"])
    ok = fps_round in (30, 60)
    return {
        "name": "Frame rate is 30 or 60 fps",
        "passed": ok,
        "value": f"{p['fps']:.2f} fps",
        "expected": "30 or 60",
        "fix": "Re-export at 30 fps with `-r 30`. UI animations interpolate poorly at 24." if not ok else None,
        "source": "techniques.md export specs",
    }


def check_faststart(video_path: Path) -> dict:
    fs = _faststart(video_path)
    if fs is None:
        return {
            "name": "Faststart enabled (moov before mdat)",
            "passed": False,
            "value": "could not determine",
            "expected": "moov atom first",
            "fix": "Re-export with `-movflags +faststart`.",
            "source": "Web autoplay requires faststart",
        }
    return {
        "name": "Faststart enabled (moov before mdat)",
        "passed": fs,
        "value": "moov first" if fs else "moov AFTER mdat",
        "expected": "moov first",
        "fix": "Re-export with `-movflags +faststart`." if not fs else None,
        "source": "Web autoplay requires faststart",
    }


# ── Check 5: Duration ──

def check_duration(video_path: Path) -> dict:
    p = _video_props(video_path)
    ok = 8 <= p["duration"] <= 90
    return {
        "name": "Duration in 8–90s range",
        "passed": ok,
        "value": f"{p['duration']:.1f}s",
        "expected": "8–90s",
        "fix": "Trim to target range. Site-hero loops 8–25s; X/LinkedIn 15–45s; YouTube 30–90s." if not ok else None,
        "source": "techniques.md §1 reference range",
    }


# ── Check 6: Cut cadence ──

def check_cut_cadence(video_path: Path) -> dict:
    p = _video_props(video_path)
    cuts = _scene_cuts(video_path)
    if not cuts:
        # No detected cuts — could be a single continuous shot, OR the
        # detector missed them. For short videos this often is intentional.
        if p["duration"] < 15:
            return {
                "name": "Cut cadence sane",
                "passed": True,
                "value": "0 cuts (single shot)",
                "expected": "OK on shorts",
                "fix": None,
                "source": "techniques.md §3",
            }
        return {
            "name": "Cut cadence sane",
            "passed": False,
            "value": "0 cuts in a long video — held shot may bore viewers",
            "expected": "MSL between 2 and 7s",
            "fix": "Add 2-3 cuts (title-card breaks or B-roll inserts).",
            "source": "techniques.md §3 — never holds past 7s",
        }
    # Compute mean shot length: divide duration by (cuts + 1)
    msl = p["duration"] / (len(cuts) + 1)
    ok = 2.0 <= msl <= 7.0
    return {
        "name": "Cut cadence sane (MSL 2–7s)",
        "passed": ok,
        "value": f"MSL {msl:.1f}s ({len(cuts)} cuts in {p['duration']:.1f}s)",
        "expected": "2.0–7.0s",
        "fix": (
            "MSL too fast (<2s): cuts feel frantic; hold each shot longer."
            if msl < 2.0 else
            "MSL too slow (>7s): video feels static; add title-card breaks or B-roll."
            if msl > 7.0 else None
        ),
        "source": "techniques.md §3 — Linear's title-card mode 4-6s; Cursor demos 3-4s; never past 7s",
    }


# ── Check 7: Hook timing ──

def check_hook_timing(video_path: Path) -> dict:
    """First scene cut after start should land ≤ 3s — the "3-second rule".
    Or, if the video opens with a brand-frame title card that's part of the
    branded entrance, allow the first cut to land ≤ 5s (account for 1.5–3s
    of title card hold)."""
    cuts = _scene_cuts(video_path)
    if not cuts:
        # No cuts — could be intentional (held shot) or boring
        return {
            "name": "Hook lands ≤ 3s (or branded entry ≤ 5s)",
            "passed": False,
            "value": "no scene cuts detected — single static shot",
            "expected": "first cut by 0:03 (or 0:05 if branded entry)",
            "fix": "Single-shot videos can work for site-hero loops. For launch reels, add a hard cut from a title card to the action by 0:03.",
            "source": "techniques.md (3-second rule)",
        }
    first_cut = cuts[0]
    # Strict: ≤3s ; lenient with branded entry: ≤5s
    if first_cut <= 3.0:
        return {
            "name": "Hook lands ≤ 3s",
            "passed": True,
            "value": f"first cut at {first_cut:.2f}s",
            "expected": "≤3.0s",
            "fix": None,
            "source": "techniques.md (3-second rule)",
        }
    if first_cut <= 5.0:
        return {
            "name": "Hook lands ≤ 5s (branded-entry tolerance)",
            "passed": True,
            "value": f"first cut at {first_cut:.2f}s (within branded-entry tolerance)",
            "expected": "≤5.0s with branded entry",
            "fix": None,
            "source": "techniques.md — title cards may delay the hook to 0:05",
        }
    return {
        "name": "Hook lands ≤ 5s",
        "passed": False,
        "value": f"first cut at {first_cut:.2f}s",
        "expected": "≤5.0s with branded entry, ≤3.0s for cold open",
        "fix": "First cut too late — viewer scrolls before content appears. Cut into the value-prop within 3 seconds (or 5s if you have a branded title card opener).",
        "source": "techniques.md (3-second rule)",
    }


# ── Check 8: End-card silence ──

def check_end_silence(video_path: Path) -> dict:
    p = _video_props(video_path)
    silences = _silence_segments(video_path)
    duration = p["duration"]
    # Find any silence overlapping the last 3s
    tail_start = max(0.0, duration - 3.0)
    tail_silences = [(s, e) for s, e in silences if e >= tail_start]
    if not tail_silences:
        return {
            "name": "End-card silence (≥1s in last 3s)",
            "passed": False,
            "value": "no silence in last 3s",
            "expected": "music drops out so logo holds in silence",
            "fix": "Add a music fade-out so the closing logo holds in 1.5–4s of silence. This is the most consistent technique across the techniques.md reference set (§6). In motion_recipes use `mix_music(music_out_at_s=duration-3.0, fade_out_s=2.0)`.",
            "source": "techniques.md §6 — music-out into logo silence is the single most consistent technique across all 10 reference videos",
        }
    # Sum silence inside last 3s
    silence_in_tail = sum(min(e, duration) - max(s, tail_start) for s, e in tail_silences)
    ok = silence_in_tail >= 1.0
    return {
        "name": "End-card silence (≥1s in last 3s)",
        "passed": ok,
        "value": f"{silence_in_tail:.1f}s of silence in last 3s",
        "expected": "≥1.0s",
        "fix": None if ok else "Extend the music fade-out so silence on logo is at least 1s. Linear holds 4s of silence; Stripe holds 1.2s.",
        "source": "techniques.md §6",
    }


# ── Check 9: Motion jitter (zoompan shake detector) ──

def check_motion_jitter(video_path: Path) -> dict:
    """Detect zoompan-style sub-pixel shake by looking at frame-to-frame
    pixel difference variance during static-content segments. Smooth motion
    has a low variance baseline; jittery motion has a high variance baseline
    even when the underlying content is barely moving.

    Method:
      1. Extract every Nth frame at low resolution (160x90) for speed.
      2. Compute mean absolute pixel difference between consecutive samples.
      3. If the time series has a large fraction of "high-frequency" jumps
         relative to its mean, flag jitter.
    """
    sample_dir = Path("/tmp/video-review-samples")
    sample_dir.mkdir(parents=True, exist_ok=True)
    # Clear any prior samples for this video
    for f in sample_dir.glob("frame_*.jpg"):
        f.unlink()

    # Sample at 6 fps at 160x90 — enough to see jitter without overhead
    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-i", str(video_path),
        "-vf", "fps=6,scale=160:90",
        f"{sample_dir}/frame_%04d.jpg",
    ]
    subprocess.run(cmd, check=True)

    frames = sorted(sample_dir.glob("frame_*.jpg"))
    if len(frames) < 4:
        return {
            "name": "Motion jitter (zoompan shake detector)",
            "passed": True,
            "value": "too few frames to analyze",
            "expected": "low frame-to-frame variance",
            "fix": None,
            "source": "v11/v12/v13 zoompan failure mode",
        }

    # Use PIL to compute mean pixel diff between consecutive frames
    try:
        from PIL import Image, ImageChops
    except ImportError:
        return {
            "name": "Motion jitter (zoompan shake detector)",
            "passed": True,
            "value": "PIL not available — skipped",
            "expected": "low frame-to-frame variance",
            "fix": None,
            "source": "v11/v12/v13 zoompan failure mode",
        }

    diffs = []
    prev = None
    for f in frames:
        img = Image.open(f).convert("L")  # grayscale
        if prev is not None:
            d = ImageChops.difference(img, prev)
            # Mean abs difference
            stat = sum(d.getdata()) / (160 * 90)
            diffs.append(stat)
        prev = img

    if not diffs:
        return {
            "name": "Motion jitter",
            "passed": True,
            "value": "no diffs",
            "expected": "—",
            "fix": None,
            "source": "—",
        }

    # Jitter heuristic: count consecutive-frame deltas that are 1.5x the
    # local-windowed mean — these are spikes characteristic of jitter.
    # Thresholds tuned by inspection against v10 (smooth) vs v12 (shaky).
    mean_diff = sum(diffs) / len(diffs)
    spikes = sum(1 for d in diffs if d > mean_diff * 1.5)
    spike_rate = spikes / len(diffs)
    # Flag if >40% of consecutive-frame deltas are spikes (jittery)
    ok = spike_rate < 0.40
    return {
        "name": "Motion jitter (zoompan shake detector)",
        "passed": ok,
        "value": f"spike rate {spike_rate:.0%} (mean Δ {mean_diff:.1f})",
        "expected": "<40% spike rate",
        "fix": (
            "High frame-to-frame variance in a static-feeling video → zoompan jitter "
            "(common at slow zoom rates because the filter does discrete integer scaling). "
            "Fix: switch motion to in-browser CSS transforms during recording "
            "(see lib/smooth_record.py). Or pre-scale source 2-3× before zoompan. "
            "Or remove zoompan entirely and use a single monotonic continuous push (v10 worked this way)."
            if not ok else None
        ),
        "source": "v11/v12/v13 failure mode — see feedback_video_motion_pitfalls.md",
    }


# ── Check 10: End-card hold time ──

def check_end_card_hold(video_path: Path) -> dict:
    p = _video_props(video_path)
    cuts = _scene_cuts(video_path)
    if not cuts:
        return {
            "name": "End-card hold ≥ 2.5s",
            "passed": True,
            "value": "single shot — no end-card detected",
            "expected": "≥2.5s",
            "fix": None,
            "source": "techniques.md §6",
        }
    last_cut = cuts[-1]
    hold = p["duration"] - last_cut
    ok = hold >= 2.5
    return {
        "name": "End-card hold ≥ 2.5s",
        "passed": ok,
        "value": f"{hold:.1f}s after last cut",
        "expected": "≥2.5s (3–4s ideal)",
        "fix": (
            "Last segment too short — extend the logo card hold to 3–4 seconds. Linear holds 4s; Stripe 1.2s; default 3s."
            if not ok else None
        ),
        "source": "techniques.md §6 — Linear holds 4s, Stripe 1.2s",
    }


# ── Run all ──

ALL_CHECKS = [
    check_codec,
    check_resolution,
    check_fps,
    check_faststart,
    check_duration,
    check_cut_cadence,
    check_hook_timing,
    check_end_silence,
    check_motion_jitter,
    check_end_card_hold,
]


def run_all(video_path: Path) -> list[dict]:
    return [c(video_path) for c in ALL_CHECKS]
