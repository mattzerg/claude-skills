#!/usr/bin/env python3
import argparse
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Tuple
from xml.etree import ElementTree as ET

NS_RE = re.compile(r"\{.*\}")
NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")
TRANS_RE = re.compile(r"(translate|rotate|scale)\(([^)]*)\)")
WORDMARK_RE = re.compile(r"wordmark", re.I)
COMMAND_RE = re.compile(r"--dangerously-skip-permissions")


@dataclass
class Finding:
    severity: str
    file: Path
    message: str


def strip_ns(tag: str) -> str:
    return NS_RE.sub("", tag)


def floats(raw: Optional[str]) -> list[float]:
    if not raw:
        return []
    return [float(x) for x in NUM_RE.findall(raw)]


def parse_viewbox(root: ET.Element) -> tuple[float, float, float, float]:
    values = floats(root.get("viewBox"))
    if len(values) == 4:
        return tuple(values)  # type: ignore[return-value]
    width = floats(root.get("width"))
    height = floats(root.get("height"))
    w = width[0] if width else 0.0
    h = height[0] if height else 0.0
    return (0.0, 0.0, w, h)


def transform_offset(transform: Optional[str]) -> tuple[float, float, bool]:
    x = y = 0.0
    rotated = False
    if not transform:
        return x, y, rotated
    for kind, args in TRANS_RE.findall(transform):
        values = floats(args)
        if kind == "translate" and values:
            x += values[0]
            y += values[1] if len(values) > 1 else 0
        elif kind == "rotate":
            rotated = True
    return x, y, rotated


def inherited_context(node: ET.Element, parents: list[ET.Element]) -> tuple[float, float, bool]:
    x = y = 0.0
    rotated = False
    for parent in parents:
        dx, dy, r = transform_offset(parent.get("transform"))
        x += dx
        y += dy
        rotated = rotated or r
    dx, dy, r = transform_offset(node.get("transform"))
    return x + dx, y + dy, rotated or r


def iter_nodes(root: ET.Element, parents: Optional[list[ET.Element]] = None) -> Iterable[tuple[ET.Element, list[ET.Element]]]:
    parents = parents or []
    yield root, parents
    for child in root:
        yield from iter_nodes(child, parents + [root])


def text_content(node: ET.Element) -> str:
    return "".join(node.itertext())


Box = Tuple[float, float, float, float]


def approx_text_box(node: ET.Element, parents: list[ET.Element]) -> Optional[Box]:
    text = text_content(node).strip()
    if not text:
        return None
    vals_x = floats(node.get("x"))
    vals_y = floats(node.get("y"))
    if not vals_x or not vals_y:
        return None
    size = floats(node.get("font-size"))
    font_size = size[0] if size else 24.0
    weight = (node.get("font-weight") or "").lower()
    weight_factor = 0.68 if weight in {"700", "800", "900", "bold"} else 0.58
    dx, dy, _ = inherited_context(node, parents)
    x = vals_x[0] + dx
    baseline = vals_y[0] + dy
    width = max(1.0, len(text) * font_size * weight_factor)
    height = font_size * 1.2
    anchor = (node.get("text-anchor") or "").lower()
    if anchor == "middle":
        x -= width / 2
    elif anchor == "end":
        x -= width
    return x, baseline - height, width, height


def rect_like_box(node: ET.Element, parents: list[ET.Element]) -> Optional[Box]:
    tag = strip_ns(node.tag)
    if tag not in {"rect", "image"}:
        return None
    xs = floats(node.get("x"))
    ys = floats(node.get("y"))
    ws = floats(node.get("width"))
    hs = floats(node.get("height"))
    if not ws or not hs:
        return None
    dx, dy, _ = inherited_context(node, parents)
    return (xs[0] if xs else 0.0) + dx, (ys[0] if ys else 0.0) + dy, ws[0], hs[0]


def href_value(node: ET.Element) -> str:
    return node.get("href") or node.get("{http://www.w3.org/1999/xlink}href") or ""


def subtree_rect_boxes(node: ET.Element, parents: list[ET.Element]) -> list[Box]:
    boxes: list[Box] = []
    for child in node:
        for desc, desc_parents in iter_nodes(child, parents + [node]):
            if strip_ns(desc.tag) in {"rect", "image"}:
                box = rect_like_box(desc, desc_parents)
                if box:
                    boxes.append(box)
    return boxes


def union_box(boxes: list[Box]) -> Optional[Box]:
    if not boxes:
        return None
    min_x = min(box[0] for box in boxes)
    min_y = min(box[1] for box in boxes)
    max_x = max(box[0] + box[2] for box in boxes)
    max_y = max(box[1] + box[3] for box in boxes)
    return min_x, min_y, max_x - min_x, max_y - min_y


def outside(box: tuple[float, float, float, float], view: tuple[float, float, float, float], pad: float = 0) -> bool:
    x, y, w, h = box
    vx, vy, vw, vh = view
    return x < vx + pad or y < vy + pad or x + w > vx + vw - pad or y + h > vy + vh - pad


def group_has_command(node: ET.Element) -> bool:
    return bool(COMMAND_RE.search(text_content(node)))


def group_has_wordmark_image(node: ET.Element) -> bool:
    for child in node.iter():
        if WORDMARK_RE.search(href_value(child)):
            return True
    return False


def scan_file(path: Path) -> list[Finding]:
    findings: list[Finding] = []
    root = ET.parse(path).getroot()
    view = parse_viewbox(root)
    name = path.name.lower()
    xml = path.read_text(encoding="utf-8")

    if view[2] <= 0 or view[3] <= 0:
        findings.append(Finding("HIGH", path, "Missing usable viewBox/width/height."))
        return findings

    for node, parents in iter_nodes(root):
        tag = strip_ns(node.tag)
        if tag in {"rect", "image"}:
            box = rect_like_box(node, parents)
            if box and outside(box, view):
                findings.append(Finding("HIGH", path, f"{tag} bleeds off the SVG artboard: {tuple(round(v, 1) for v in box)}."))
            if tag == "image" and "shirt" in name and box and WORDMARK_RE.search(href_value(node)):
                x, y, w, _ = box
                if x > view[2] * 0.62 and 320 < y < 500:
                    findings.append(Finding("HIGH", path, "Full wordmark sits in the shirt sleeve/armpit danger zone; use neck, hem, or a clearly visible sleeve plane."))
                if y > view[3] * 0.72 and w > view[2] * 0.10:
                    findings.append(Finding("HIGH", path, "Lower-hem full wordmark is oversized for a T-shirt mockup; use a small woven/tag detail or move it to the neck zone."))
                if y > view[3] * 0.76:
                    findings.append(Finding("HIGH", path, "T-shirt full wordmark is too low and risks reading as a cropped/floating label; move it to a real side-seam or hem-tag position."))
            if tag == "image" and "mug" in name and box and WORDMARK_RE.search(href_value(node)):
                x, y, w, _ = box
                if x > view[2] * 0.55 and y > view[3] * 0.52:
                    findings.append(Finding("HIGH", path, "Mug full wordmark sits in the handle-side danger zone; center it under the front print or move it clearly to a separate side-view mockup."))
                if x + w > view[2] * 0.73:
                    findings.append(Finding("HIGH", path, "Mug full wordmark extends into the handle/crop region and will read as clipped or pasted on."))
        if tag == "text":
            box = approx_text_box(node, parents)
            text = text_content(node).strip().replace("\n", " ")
            if box and outside(box, view, pad=8):
                findings.append(Finding("HIGH", path, f"Text likely clips or bleeds off-canvas: {text[:80]!r}."))
            if box and (box[0] < 40 or box[1] < 40):
                findings.append(Finding("MEDIUM", path, f"Text sits too close to page edge for a review sheet: {text[:80]!r}."))
        if tag == "g":
            _, _, rotated = inherited_context(node, parents)
            if group_has_command(node) and group_has_wordmark_image(node):
                findings.append(Finding("HIGH", path, "Full wordmark appears inside the same group as the terminal command; use compact mark in the hero panel and move full logo to a secondary item zone."))
            if "shirt" in name and group_has_command(node):
                bbox = union_box(subtree_rect_boxes(node, parents))
                if bbox and (bbox[2] > view[2] * 0.34 or bbox[3] > view[3] * 0.20):
                    findings.append(Finding("HIGH", path, f"T-shirt chest graphic is too large for a believable apparel mockup: {tuple(round(v, 1) for v in bbox)}."))
            if rotated and group_has_wordmark_image(node):
                findings.append(Finding("MEDIUM", path, "Rotated full wordmark detected. This is often a fake placement unless it matches a real object plane and remains legible."))

    if "hoodie" in name:
        # Catch T-shirt pretending to be hoodie: hoodies should have hood or pocket anatomy.
        if "pocket" not in xml.lower() and "drawstring" not in xml.lower() and "hood" not in xml.lower():
            findings.append(Finding("HIGH", path, "Hoodie mockup lacks hoodie anatomy markers such as hood, drawstrings, or pocket."))
        if re.search(r"<title>[^<]*t-?shirt", xml, re.I):
            findings.append(Finding("HIGH", path, "File/title indicates T-shirt while filename says hoodie."))

    if "mug" in name:
        if "handle" not in xml.lower():
            findings.append(Finding("HIGH", path, "Mug mockup/spec lacks handle-side placement language."))

    if "mockup" in name and "preview" not in name:
        if len(re.findall(r"<image[^>]+wordmark", xml, flags=re.I)) > 2:
            findings.append(Finding("MEDIUM", path, "More than two full wordmark image refs in one mockup; likely redundant branding."))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description="Preflight swag SVG mockups for easy-to-catch brand and layout failures.")
    parser.add_argument("paths", nargs="+", help="SVG files or folders")
    parser.add_argument("--strict", action="store_true", help="Fail on MEDIUM findings as well as HIGH findings")
    args = parser.parse_args()

    files: list[Path] = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.svg")))
        else:
            files.append(p)

    all_findings: list[Finding] = []
    for file in files:
        all_findings.extend(scan_file(file))

    for finding in all_findings:
        print(f"{finding.severity}: {finding.file}: {finding.message}")

    fail_levels = {"HIGH", "MEDIUM"} if args.strict else {"HIGH"}
    return 1 if any(f.severity in fail_levels for f in all_findings) else 0


if __name__ == "__main__":
    sys.exit(main())
