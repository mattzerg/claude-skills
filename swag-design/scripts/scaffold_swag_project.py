#!/usr/bin/env python3
import argparse
from pathlib import Path

README = """# {title}

## Goal

Describe the swag set, audience, and review stage.

## Items

- Item:
  - Hero element:
  - Full-logo zone:
  - Print method:
  - Notes:

## Required Review Gate

- Item mockups show actual item silhouettes.
- Full logo appears in an item-specific zone on each item.
- Campaign text is visually legible and not clipped.
- Production files are separate from mockups.
- Vendor notes include colors, dimensions, and print methods.
"""

def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold a swag design project folder.")
    parser.add_argument("name", help="Project folder name")
    parser.add_argument("--root", default=".", help="Root directory to create the project in")
    parser.add_argument("--title", default=None, help="Human-readable project title")
    args = parser.parse_args()

    root = Path(args.root).expanduser().resolve()
    project = root / args.name
    for subdir in ["brand-assets", "mockups", "production-art", "previews", "vendor-spec"]:
        (project / subdir).mkdir(parents=True, exist_ok=True)

    title = args.title or args.name.replace("-", " ").title()
    readme = project / "vendor-spec" / "README.md"
    if not readme.exists():
        readme.write_text(README.format(title=title), encoding="utf-8")

    print(project)

if __name__ == "__main__":
    main()
