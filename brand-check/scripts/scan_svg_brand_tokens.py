#!/usr/bin/env python3
import argparse
import re
from pathlib import Path
from xml.etree import ElementTree as ET

HEX_RE = re.compile(r"#[0-9a-fA-F]{3,8}")

def scan(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    ET.fromstring(text)
    return {
        "file": str(path),
        "hex_colors": sorted(set(m.group(0).lower() for m in HEX_RE.finditer(text))),
        "image_refs": re.findall(r'href="([^"]+)"', text),
        "text_strings": re.findall(r"<text[^>]*>(.*?)</text>", text, flags=re.S),
    }

def main() -> None:
    parser = argparse.ArgumentParser(description="Scan SVGs for brand-relevant tokens.")
    parser.add_argument("paths", nargs="+", help="SVG files or directories")
    args = parser.parse_args()
    files = []
    for raw in args.paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.rglob("*.svg")))
        else:
            files.append(p)
    for f in files:
        result = scan(f)
        print(result)

if __name__ == "__main__":
    main()
