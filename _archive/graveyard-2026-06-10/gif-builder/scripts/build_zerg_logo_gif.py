#!/usr/bin/env python3
from __future__ import annotations

import argparse
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

BG = (244, 240, 231, 255)
INK = (17, 21, 20, 255)
SPARK = (179, 102, 47, 255)
SPARK_SOFT = (213, 122, 50, 255)


def tokenize_path(d: str) -> list[str]:
    return re.findall(r"[MLHVCSZmlhvcsz]|-?\d*\.?\d+(?:e[-+]?\d+)?", d)


def cubic(p0: tuple[float, float], p1: tuple[float, float], p2: tuple[float, float], p3: tuple[float, float], steps: int = 18) -> list[tuple[float, float]]:
    points = []
    for i in range(1, steps + 1):
        t = i / steps
        mt = 1 - t
        x = mt**3 * p0[0] + 3 * mt**2 * t * p1[0] + 3 * mt * t**2 * p2[0] + t**3 * p3[0]
        y = mt**3 * p0[1] + 3 * mt**2 * t * p1[1] + 3 * mt * t**2 * p2[1] + t**3 * p3[1]
        points.append((x, y))
    return points


def parse_path(d: str) -> list[list[tuple[float, float]]]:
    tokens = tokenize_path(d)
    subpaths: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    i = 0
    cmd = ""
    x = y = sx = sy = 0.0

    def num() -> float:
        nonlocal i
        value = float(tokens[i])
        i += 1
        return value

    while i < len(tokens):
        if re.match(r"[A-Za-z]", tokens[i]):
            cmd = tokens[i]
            i += 1
        if cmd == "M":
            if current:
                subpaths.append(current)
            x, y = num(), num()
            sx, sy = x, y
            current = [(x, y)]
            cmd = "L"
        elif cmd == "L":
            x, y = num(), num()
            current.append((x, y))
        elif cmd == "H":
            x = num()
            current.append((x, y))
        elif cmd == "V":
            y = num()
            current.append((x, y))
        elif cmd == "C":
            p0 = (x, y)
            p1 = (num(), num())
            p2 = (num(), num())
            p3 = (num(), num())
            current.extend(cubic(p0, p1, p2, p3))
            x, y = p3
        elif cmd == "Z":
            current.append((sx, sy))
            subpaths.append(current)
            current = []
            cmd = ""
        else:
            raise ValueError(f"Unsupported SVG path command: {cmd}")
    if current:
        subpaths.append(current)
    return subpaths


def area(poly: list[tuple[float, float]]) -> float:
    return abs(sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1] for i in range(len(poly))) / 2)


def render_logo(svg_path: Path, size: int) -> Image.Image:
    tree = ET.parse(svg_path)
    root = tree.getroot()
    view_box = root.attrib.get("viewBox", "0 0 33 32")
    _, _, vbw, vbh = [float(v) for v in view_box.split()]
    scale = size / max(vbw, vbh)
    ox = (size - vbw * scale) / 2
    oy = (size - vbh * scale) / 2

    hires = size * 4
    logo = Image.new("RGBA", (hires, hires), (0, 0, 0, 0))
    ns = "{http://www.w3.org/2000/svg}"
    for path in root.findall(f".//{ns}path"):
        path_layer = Image.new("RGBA", (hires, hires), (0, 0, 0, 0))
        draw = ImageDraw.Draw(path_layer)
        subpaths = parse_path(path.attrib["d"])
        fill_rule = path.attrib.get("fill-rule")
        ordered = sorted(subpaths, key=area, reverse=True) if fill_rule == "evenodd" else subpaths
        for idx, subpath in enumerate(ordered):
            color = (0, 0, 0, 0) if fill_rule == "evenodd" and idx % 2 else INK
            pts = [((x * scale + ox) * 4, (y * scale + oy) * 4) for x, y in subpath]
            draw.polygon(pts, fill=color)
        logo.alpha_composite(path_layer)
    return logo.resize((size, size), Image.Resampling.LANCZOS)


def sparkle_points(cx: float, cy: float, radius: float) -> list[tuple[float, float]]:
    inner = radius * 0.34
    points = []
    for i in range(8):
        angle = -math.pi / 2 + i * math.pi / 4
        r = radius if i % 2 == 0 else inner
        points.append((cx + math.cos(angle) * r, cy + math.sin(angle) * r))
    return points


def draw_sparkle(img: Image.Image, size: int, intensity: float) -> Image.Image:
    if intensity <= 0.01:
        return img
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    scale = size / 128
    cx = size * 0.72
    cy = size * 0.23
    radius = (4.0 + 3.0 * intensity) * scale
    alpha = int(190 * intensity)
    draw.polygon(sparkle_points(cx, cy, radius), fill=SPARK[:3] + (alpha,))
    draw.ellipse([cx - 1.2 * scale, cy - 1.2 * scale, cx + 1.2 * scale, cy + 1.2 * scale], fill=SPARK_SOFT[:3] + (min(255, alpha + 35),))
    img.alpha_composite(overlay)
    return img


def draw_frame(logo: Image.Image, size: int, frame_index: int, frame_count: int) -> Image.Image:
    frame = Image.new("RGBA", (size, size), BG)
    logo_size = int(size * 0.66)
    logo_img = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
    offset = ((size - logo_size) // 2, (size - logo_size) // 2)
    frame.alpha_composite(logo_img, offset)
    t = frame_index / frame_count
    sparkle = max(0.0, math.sin(math.pi * min(1.0, max(0.0, (t - 0.10) / 0.34))))
    if t > 0.44:
        sparkle = 0.0
    return draw_sparkle(frame, size, sparkle)


def draw_gentle_frame(logo: Image.Image, size: int, frame_index: int, frame_count: int) -> Image.Image:
    frame = Image.new("RGBA", (size, size), BG)
    pulse = (1 - math.cos(2 * math.pi * frame_index / frame_count)) / 2

    glow = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    gd = ImageDraw.Draw(glow)
    pad = int(size * (0.075 - 0.015 * pulse))
    gd.rounded_rectangle([pad, pad, size - pad, size - pad], radius=int(size * 0.11), fill=SPARK[:3] + (int(18 + 26 * pulse),))
    frame.alpha_composite(glow.filter(ImageFilter.GaussianBlur(radius=max(2, int(size * 0.043)))))

    logo_size = int(size * 0.78)
    logo_img = logo.resize((logo_size, logo_size), Image.Resampling.LANCZOS)
    offset = ((size - logo_size) // 2, (size - logo_size) // 2)
    frame.alpha_composite(logo_img, offset)

    draw = ImageDraw.Draw(frame)
    green = (111, 190, 49, 255)
    line_y = int(size * 0.80)
    start = int(size * 0.19)
    end = int(start + size * (0.12 + 0.20 * pulse))
    draw.rectangle([start, line_y, end, line_y + int(size * 0.030)], fill=green[:3] + (int(105 + 115 * pulse),))

    tick_x = int(size * 0.815)
    tick_h = int(size * (0.06 + 0.08 * pulse))
    tick_y = int(size * 0.43 - tick_h / 2)
    draw.rectangle([tick_x, tick_y, tick_x + int(size * 0.026), tick_y + tick_h], fill=SPARK[:3] + (int(110 + 120 * pulse),))
    return frame


def save_gif(frames: list[Image.Image], path: Path, size: int, duration: int) -> None:
    resized = [f.resize((size, size), Image.Resampling.LANCZOS).convert("P", palette=Image.Palette.ADAPTIVE, colors=64) for f in frames]
    resized[0].save(path, save_all=True, append_images=resized[1:], duration=duration, loop=0, disposal=2, optimize=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--logo-svg", type=Path, default=Path("MattZerg/Brand/assets/logos/zerg/zerg-mark-currentColor.svg"))
    parser.add_argument("--frames", type=int, default=32)
    parser.add_argument("--duration", type=int, default=80)
    args = parser.parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)

    logo = render_logo(args.logo_svg, 512)
    frames = [draw_frame(logo, 512, i, args.frames) for i in range(args.frames)]
    for size in (512, 256, 128):
        save_gif(frames, args.out_dir / f"zerg-mark-sparkle-loop-{size}.gif", size, args.duration)
    frames[0].save(args.out_dir / "zerg-mark-sparkle-loop-preview.png")
    frames[8].save(args.out_dir / "zerg-mark-sparkle-loop-peak.png")

    gentle_frames = [draw_gentle_frame(logo, 512, i, 36) for i in range(36)]
    for size in (512, 256, 128):
        save_gif(gentle_frames, args.out_dir / f"zerg-mark-gentle-loop-{size}.gif", size, 70)
    gentle_frames[0].save(args.out_dir / "zerg-mark-gentle-loop-preview.png")
    gentle_frames[18].save(args.out_dir / "zerg-mark-gentle-loop-peak.png")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
