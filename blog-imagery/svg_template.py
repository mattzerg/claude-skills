#!/usr/bin/env python3
"""Render a brand-coherent SVG asset from a template + JSON config.

Usage:
    # List templates
    svg_template.py --list

    # Show example config for a template
    svg_template.py <template> --show-example

    # Render to SVG only
    svg_template.py <template> --config conf.json --out path.svg

    # Render to PNG (auto-derived dimensions from template)
    svg_template.py <template> --config conf.json --out path.png

    # Render with config from stdin
    cat conf.json | svg_template.py <template> --out path.png

Templates (Tier 1, technical/data posts only):
    stat-card   before/after big-number hero
    funnel      multi-stage compression visual
    tree        root + binary branching with comparison panels

For aspect overrides see each template module's docstring (config["aspect"]).
"""
import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


SCRIPT_DIR = Path(__file__).parent
sys.path.insert(0, str(SCRIPT_DIR))

import templates  # noqa: E402


def render_svg_to_png(svg_path: Path, png_path: Path, w: int, h: int):
    """Convert SVG to PNG via Chrome headless. Matches the recipe used
    on agents-that-remember (1× rasterization at native viewBox dims)."""
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if not Path(chrome).exists():
        chrome = subprocess.run(["which", "google-chrome"], capture_output=True, text=True).stdout.strip()
    if not chrome:
        chrome = subprocess.run(["which", "chromium"], capture_output=True, text=True).stdout.strip()
    if not chrome:
        raise RuntimeError("No Chrome/Chromium found. Install Google Chrome.")

    html = f"""<!DOCTYPE html><html><head><style>
        html,body{{margin:0;padding:0;background:#07111E}}
        img{{display:block;width:{w}px;height:{h}px}}
    </style></head><body>
    <img src="file://{svg_path}" />
    </body></html>"""
    html_path = Path(tempfile.mkstemp(suffix=".html")[1])
    html_path.write_text(html)

    try:
        subprocess.run([
            chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars",
            f"--window-size={w},{h}",
            "--default-background-color=00000000",
            f"--screenshot={png_path}",
            f"file://{html_path}",
        ], capture_output=True, timeout=60)
    finally:
        html_path.unlink(missing_ok=True)

    if not png_path.exists() or png_path.stat().st_size < 100:
        raise RuntimeError(f"Chrome failed to write {png_path}")


def parse_viewbox(svg: str):
    m = re.search(r'viewBox="0 0 (\d+) (\d+)"', svg)
    if not m:
        raise ValueError("Could not parse viewBox from SVG")
    return int(m.group(1)), int(m.group(2))


def main():
    parser = argparse.ArgumentParser(description="Render brand-coherent SVG/PNG from a template + config.")
    parser.add_argument("template", nargs="?", help="Template name: stat-card | funnel | tree")
    parser.add_argument("--config", help="Path to JSON config file (or - for stdin)")
    parser.add_argument("--out", help="Output path (.svg or .png)")
    parser.add_argument("--list", action="store_true", help="List available templates and exit")
    parser.add_argument("--show-example", action="store_true", help="Print the EXAMPLE_CONFIG for the named template and exit")

    args = parser.parse_args()

    if args.list:
        print("Available templates:")
        for name, mod in templates.REGISTRY.items():
            print(f"  {name:12s}  {getattr(mod, 'DESCRIPTION', '')}")
        return

    if not args.template:
        parser.error("template name required (or use --list)")

    mod = templates.get(args.template)

    if args.show_example:
        print(json.dumps(mod.EXAMPLE_CONFIG, indent=2))
        return

    if not args.config or not args.out:
        parser.error("--config and --out are required (unless --list / --show-example)")

    if args.config == "-":
        config = json.loads(sys.stdin.read())
    else:
        config = json.loads(Path(args.config).read_text())

    svg = mod.render(config)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)

    if out.suffix.lower() == ".svg":
        out.write_text(svg)
        print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
        return

    if out.suffix.lower() == ".png":
        # Stash SVG sibling to PNG so it's editable later
        svg_sibling = out.with_suffix(".svg")
        svg_sibling.write_text(svg)
        w, h = parse_viewbox(svg)
        render_svg_to_png(svg_sibling, out, w, h)
        print(f"Wrote {svg_sibling} ({svg_sibling.stat().st_size:,} bytes)")
        print(f"Wrote {out} ({out.stat().st_size:,} bytes)")
        # Post-render auto-lint per `feedback_graphic_basics.md` rule 8 (mandatory self-check).
        # Runs check_layout.py against the SVG sibling — rules 9/10/11 (geometry).
        # Skips the PNG-side rule 5 (top-padding) here because that has false positives on
        # eyebrow-led layouts; rule 5 is enforced when check_layout is invoked directly on .png.
        # HIGH findings exit non-zero so build scripts fail fast.
        check_layout = Path.home() / ".config" / "zerg" / "check_layout.py"
        if check_layout.exists():
            r = subprocess.run(
                ["python3", str(check_layout), str(svg_sibling)],
                capture_output=True, text=True,
            )
            if r.stdout.strip():
                print(r.stdout.strip())
            if r.stderr.strip():
                print(r.stderr.strip(), file=sys.stderr)
            if r.returncode != 0:
                print(f"!! check_layout reported HIGH SVG-geometry findings on {svg_sibling.name}. "
                      f"Fix the config or template before treating this image as shippable.",
                      file=sys.stderr)
                sys.exit(2)
        return

    parser.error(f"Unsupported output extension: {out.suffix} (use .svg or .png)")


if __name__ == "__main__":
    main()
