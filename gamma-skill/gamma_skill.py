#!/usr/bin/env python3
"""Gamma Skill - Presentation/document generation via Gamma API v1.0.

Generate presentations, documents, webpages, and social content from text.
Supports themes, templates, card dimensions, headers/footers, sharing, and PDF/PPTX export.

Usage:
    python gamma_skill.py generate "Your content here" --format presentation
    python gamma_skill.py generate --file notes.md --dimensions 16x9 --wait
    python gamma_skill.py from-template GAMMA_ID "Update content" --share user@example.com
    python gamma_skill.py themes
    python gamma_skill.py status GENERATION_ID
    python gamma_skill.py export GENERATION_ID
"""

import argparse
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Dict, Any, Optional, Union

SKILL_DIR = Path(__file__).parent
CONFIG_FILE = SKILL_DIR / "config.json"
API_BASE = "https://public-api.gamma.app/v1.0"

# Default preferences
DEFAULT_IMAGE_MODEL = "gemini-2.5-flash-image"
PREFERRED_THEMES = ["zerg", "zerg-ai", "epoch"]

# Valid enum values
FORMATS = ["presentation", "document", "webpage", "social"]
TEXT_MODES = ["generate", "condense", "preserve"]
TEXT_AMOUNTS = ["brief", "medium", "detailed", "extensive"]
IMAGE_SOURCES = [
    "aiGenerated", "pictographic", "pexels", "giphy",
    "webAllImages", "webFreeToUse", "webFreeToUseCommercially",
    "placeholder", "noImages",
]
CARD_SPLITS = ["auto", "inputTextBreaks"]
EXPORT_FORMATS = ["pdf", "pptx"]

# Dimensions per format
DIMENSIONS = {
    "presentation": ["fluid", "16x9", "4x3"],
    "document": ["fluid", "pageless", "letter", "a4"],
    "social": ["1x1", "4x5", "9x16"],
    "webpage": ["fluid"],
}

# Header/footer positions
HEADER_FOOTER_POSITIONS = [
    "topLeft", "topRight", "topCenter",
    "bottomLeft", "bottomRight", "bottomCenter",
]
HEADER_FOOTER_TYPES = ["text", "image", "cardNumber"]

ACCESS_LEVELS = ["noAccess", "view", "comment", "edit", "fullAccess"]


def load_config() -> Dict:
    """Load API key from config."""
    if not CONFIG_FILE.exists():
        print(json.dumps({
            "error": "No config file found",
            "setup_required": True,
            "instructions": [
                "1. Go to Gamma Settings > Members > API key tab",
                "2. Create a new API key (requires Pro/Ultra/Teams/Business account)",
                f"3. Save: echo '{{\"api_key\": \"sk-gamma-xxx\"}}' > {CONFIG_FILE}"
            ]
        }, indent=2))
        sys.exit(1)

    with open(CONFIG_FILE) as f:
        config = json.load(f)

    if not config.get("api_key"):
        print(json.dumps({
            "error": "No api_key in config file",
            "instructions": [
                "Add your API key to config.json:",
                '{"api_key": "sk-gamma-xxxxxxxx"}'
            ]
        }, indent=2))
        sys.exit(1)

    return config


def api_request(method: str, endpoint: str, data: Optional[Dict] = None) -> Union[Dict, list]:
    """Make authenticated API request to Gamma."""
    config = load_config()
    url = f"{API_BASE}{endpoint}"

    headers = {
        "X-API-KEY": config["api_key"],
        "Content-Type": "application/json",
        "User-Agent": "GammaSkill/2.0 (Claude Code Integration)"
    }

    body = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)

    try:
        with urllib.request.urlopen(req) as response:
            response_text = response.read().decode()
            if not response_text:
                return {}
            return json.loads(response_text)
    except urllib.error.HTTPError as e:
        error_body = ""
        try:
            error_body = e.read().decode() if e.fp else str(e)
        except:
            error_body = str(e)

        try:
            error_json = json.loads(error_body)
            print(json.dumps({
                "error": f"HTTP {e.code}",
                "message": error_json.get("message", error_body),
                "details": error_json
            }, indent=2))
        except:
            print(json.dumps({
                "error": f"HTTP {e.code}",
                "details": error_body
            }, indent=2))
        sys.exit(1)
    except urllib.error.URLError as e:
        print(json.dumps({
            "error": "Network error",
            "details": str(e.reason)
        }, indent=2))
        sys.exit(1)


def poll_until_complete(generation_id: str, interval: int = 5, timeout: int = 300, verbose: bool = False) -> Dict:
    """Poll generation status until complete or timeout."""
    start = time.time()
    attempts = 0

    while time.time() - start < timeout:
        attempts += 1
        result = api_request("GET", f"/generations/{generation_id}")

        status = result.get("status")
        if verbose and attempts > 1:
            elapsed = int(time.time() - start)
            print(json.dumps({"polling": True, "attempt": attempts, "elapsed_seconds": elapsed, "status": status}), file=sys.stderr)

        if status == "completed":
            return result
        if status == "failed":
            return {"error": "Generation failed", "details": result}

        time.sleep(interval)

    return {"error": "Timeout waiting for generation", "generation_id": generation_id, "timeout_seconds": timeout}


def find_preferred_theme() -> Optional[str]:
    """Check for preferred themes (zerg, etc.) and return theme ID if found."""
    try:
        result = api_request("GET", "/themes")
        themes = result.get("data", []) if isinstance(result, dict) else result

        for theme in themes:
            theme_id = theme.get("id", "").lower()
            theme_name = theme.get("name", "").lower()

            for preferred in PREFERRED_THEMES:
                if preferred in theme_id or preferred in theme_name:
                    return theme.get("id")

        return None
    except:
        return None


def build_card_options(args, fmt: str) -> Optional[Dict]:
    """Build cardOptions from args."""
    card_opts = {}

    # Dimensions
    if args.dimensions:
        valid = DIMENSIONS.get(fmt, [])
        if args.dimensions not in valid:
            print(json.dumps({
                "error": f"Invalid dimensions '{args.dimensions}' for format '{fmt}'",
                "valid": valid
            }, indent=2))
            sys.exit(1)
        card_opts["dimensions"] = args.dimensions

    # Header/footer
    if args.header_footer:
        hf = {}
        for item in args.header_footer:
            parts = item.split(":", 2)
            if len(parts) < 2:
                print(json.dumps({
                    "error": f"Invalid header-footer format: '{item}'",
                    "expected": "position:type[:value]  e.g. topLeft:text:Company Name"
                }, indent=2))
                sys.exit(1)

            position = parts[0]
            hf_type = parts[1]

            if position not in HEADER_FOOTER_POSITIONS:
                print(json.dumps({"error": f"Invalid position '{position}'", "valid": HEADER_FOOTER_POSITIONS}, indent=2))
                sys.exit(1)
            if hf_type not in HEADER_FOOTER_TYPES:
                print(json.dumps({"error": f"Invalid type '{hf_type}'", "valid": HEADER_FOOTER_TYPES}, indent=2))
                sys.exit(1)

            entry = {"type": hf_type}
            if hf_type == "text" and len(parts) == 3:
                entry["value"] = parts[2]
            elif hf_type == "image" and len(parts) == 3:
                entry["value"] = parts[2]

            hf[position] = entry

        if args.hf_hide_first:
            hf["hideFromFirstCard"] = True
        if args.hf_hide_last:
            hf["hideFromLastCard"] = True

        card_opts["headerFooter"] = hf

    return card_opts if card_opts else None


def build_sharing_options(args) -> Optional[Dict]:
    """Build sharingOptions from args."""
    sharing = {}

    if args.workspace_access:
        sharing["workspaceAccess"] = args.workspace_access
    if args.external_access:
        sharing["externalAccess"] = args.external_access
    if args.share:
        sharing["emailOptions"] = {
            "recipients": args.share,
            "access": args.share_access or "view",
        }

    return sharing if sharing else None


def build_image_options(args) -> Optional[Dict]:
    """Build imageOptions from args."""
    image_opts = {}

    if args.no_images:
        image_opts["source"] = "noImages"
    elif args.image_source:
        image_opts["source"] = args.image_source
        if args.image_source == "aiGenerated":
            image_opts["model"] = args.image_model or DEFAULT_IMAGE_MODEL
    elif args.image_model:
        image_opts["source"] = "aiGenerated"
        image_opts["model"] = args.image_model
    else:
        image_opts["source"] = "aiGenerated"
        image_opts["model"] = DEFAULT_IMAGE_MODEL

    if args.image_style:
        image_opts["style"] = args.image_style

    return image_opts if image_opts else None


# Command handlers

def cmd_generate(args):
    """Generate presentation/document from text."""
    input_text = args.text
    if args.file:
        try:
            with open(args.file) as f:
                input_text = f.read()
        except FileNotFoundError:
            print(json.dumps({"error": f"File not found: {args.file}"}))
            sys.exit(1)

    if not input_text:
        print(json.dumps({"error": "No input text provided. Use positional argument or --file"}))
        sys.exit(1)

    # Auto-detect theme
    theme_id = args.theme
    if not theme_id and args.auto_theme:
        theme_id = find_preferred_theme()
        if theme_id:
            print(json.dumps({"info": f"Auto-detected theme: {theme_id}"}), file=sys.stderr)

    # Build request
    data = {
        "inputText": input_text,
        "textMode": args.text_mode,
        "format": args.format,
    }

    if theme_id:
        data["themeId"] = theme_id
    if args.num_cards:
        data["numCards"] = args.num_cards
    if args.instructions:
        data["additionalInstructions"] = args.instructions
    if args.export_as:
        data["exportAs"] = args.export_as
    if args.folder:
        data["folderIds"] = [args.folder]
    if args.card_split:
        data["cardSplit"] = args.card_split

    # Text options
    text_opts = {}
    if args.tone:
        text_opts["tone"] = args.tone
    if args.audience:
        text_opts["audience"] = args.audience
    if args.language:
        text_opts["language"] = args.language
    if args.text_amount:
        text_opts["amount"] = args.text_amount
    if text_opts:
        data["textOptions"] = text_opts

    # Image options
    image_opts = build_image_options(args)
    if image_opts:
        data["imageOptions"] = image_opts

    # Card options (dimensions, header/footer)
    card_opts = build_card_options(args, args.format)
    if card_opts:
        data["cardOptions"] = card_opts

    # Sharing options
    sharing = build_sharing_options(args)
    if sharing:
        data["sharingOptions"] = sharing

    # Make the generation request
    result = api_request("POST", "/generations", data)
    generation_id = result.get("generationId")

    if not generation_id:
        print(json.dumps({"error": "No generation ID returned", "response": result}))
        sys.exit(1)

    if args.wait and generation_id:
        result = poll_until_complete(generation_id, args.poll_interval, args.timeout, verbose=True)

    result["generation_id"] = generation_id
    print(json.dumps(result, indent=2))


def cmd_from_template(args):
    """Create from existing template."""
    data = {
        "gammaId": args.template_id,
        "prompt": args.prompt,
    }

    if args.theme:
        data["themeId"] = args.theme
    if args.folder:
        data["folderIds"] = [args.folder]
    if args.export_as:
        data["exportAs"] = args.export_as

    # Image options for templates
    image_opts = {}
    if args.image_model:
        image_opts["model"] = args.image_model
    if args.image_style:
        image_opts["style"] = args.image_style
    if image_opts:
        data["imageOptions"] = image_opts

    # Sharing options
    sharing = build_sharing_options(args)
    if sharing:
        data["sharingOptions"] = sharing

    result = api_request("POST", "/generations-from-template", data)
    generation_id = result.get("generationId")

    if args.wait and generation_id:
        result = poll_until_complete(generation_id, args.poll_interval, args.timeout, verbose=True)

    if generation_id:
        result["generation_id"] = generation_id
    print(json.dumps(result, indent=2))


def cmd_status(args):
    """Check generation status."""
    result = api_request("GET", f"/generations/{args.generation_id}")
    print(json.dumps(result, indent=2))


def cmd_export(args):
    """Get export URLs (PDF/PPTX) for a generation.

    Uses the status endpoint which includes exportUrl when available.
    """
    result = api_request("GET", f"/generations/{args.generation_id}")
    export_url = result.get("exportUrl")
    if export_url:
        print(json.dumps({"exportUrl": export_url}, indent=2))
    else:
        print(json.dumps({
            "error": "No export URL available",
            "hint": "Use --export-as pdf or --export-as pptx when generating to get an export URL",
            "status": result.get("status"),
            "gammaUrl": result.get("gammaUrl")
        }, indent=2))


def cmd_themes(args):
    """List available themes."""
    result = api_request("GET", "/themes")
    themes = result.get("data", []) if isinstance(result, dict) else result
    if args.search:
        search = args.search.lower()
        themes = [t for t in themes if search in t.get("name", "").lower() or search in t.get("id", "").lower()]
    if args.limit:
        themes = themes[:args.limit]
    print(json.dumps(themes, indent=2))


def cmd_folders(args):
    """List available folders."""
    result = api_request("GET", "/folders")
    print(json.dumps(result, indent=2))


def add_sharing_args(parser):
    """Add sharing arguments to a subparser."""
    sharing = parser.add_argument_group("sharing")
    sharing.add_argument("--share", nargs="+", metavar="EMAIL", help="Share with email addresses")
    sharing.add_argument("--share-access", choices=["view", "comment", "edit", "fullAccess"],
                         default="view", help="Access level for shared users (default: view)")
    sharing.add_argument("--workspace-access", choices=ACCESS_LEVELS, help="Workspace member access level")
    sharing.add_argument("--external-access", choices=["noAccess", "view", "comment", "edit"],
                         help="External user access level")


def add_wait_args(parser):
    """Add wait/polling arguments to a subparser."""
    parser.add_argument("--wait", "-w", action="store_true", help="Wait for completion")
    parser.add_argument("--poll-interval", type=int, default=5, help="Seconds between status checks (default: 5)")
    parser.add_argument("--timeout", type=int, default=300, help="Max wait time in seconds (default: 300)")


def main():
    parser = argparse.ArgumentParser(
        description="Gamma Skill v2.0 - Generate presentations, documents, and webpages",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate a presentation with 16:9 slides
  %(prog)s generate "Introduction to AI..." --format presentation --dimensions 16x9 --wait

  # Generate from a file with header/footer
  %(prog)s generate --file notes.md --header-footer "bottomRight:text:Zerg AI" --wait

  # Use stock photos instead of AI images
  %(prog)s generate "Company overview" --image-source pexels --wait

  # Generate and share via email
  %(prog)s generate "Q1 Report" --share user@company.com --share-access view --wait

  # Create from template with sharing
  %(prog)s from-template g_abc123 "Update with our Q1 data" --share team@company.com --wait

  # Social media cards (4:5 aspect ratio)
  %(prog)s generate "Key product features" --format social --dimensions 4x5 --wait

  # Search themes
  %(prog)s themes --search zerg
"""
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # generate
    p_gen = subparsers.add_parser("generate", help="Generate presentation/document from text")
    p_gen.add_argument("text", nargs="?", default="", help="Input text/content")
    p_gen.add_argument("--file", "-F", help="Read input from file instead")
    p_gen.add_argument("--format", "-f", choices=FORMATS, default="presentation", help="Output format (default: presentation)")
    p_gen.add_argument("--text-mode", "-m", choices=TEXT_MODES, default="generate", help="Text handling mode (default: generate)")
    p_gen.add_argument("--theme", "-t", help="Theme ID to apply (or use --auto-theme)")
    p_gen.add_argument("--auto-theme", "-T", action="store_true", help="Auto-detect preferred theme (zerg, etc.)")
    p_gen.add_argument("--num-cards", "-n", type=int, help="Number of slides/cards (1-60 Pro, 1-75 Ultra)")
    p_gen.add_argument("--instructions", "-i", help="Additional instructions (max 2000 chars)")
    p_gen.add_argument("--export-as", "-e", choices=EXPORT_FORMATS, help="Also export as PDF/PPTX")
    p_gen.add_argument("--folder", help="Folder ID to save to")
    p_gen.add_argument("--card-split", choices=CARD_SPLITS, help="Card splitting strategy (default: auto)")

    # Text options
    text_group = p_gen.add_argument_group("text options")
    text_group.add_argument("--tone", help="Content tone (e.g., professional, casual)")
    text_group.add_argument("--audience", help="Target audience")
    text_group.add_argument("--language", help="Output language (ISO code, e.g., en, he, es)")
    text_group.add_argument("--text-amount", choices=TEXT_AMOUNTS, help="Text density per card")

    # Image options
    img_group = p_gen.add_argument_group("image options")
    img_group.add_argument("--image-source", choices=IMAGE_SOURCES, help="Image source type")
    img_group.add_argument("--image-style", help="AI image style description (max 500 chars)")
    img_group.add_argument("--image-model", help="AI image model (default: gemini-2.5-flash-image)")
    img_group.add_argument("--no-images", action="store_true", help="Disable images entirely")

    # Card options
    card_group = p_gen.add_argument_group("card options")
    card_group.add_argument("--dimensions", "-d",
                            help="Card dimensions: presentation(fluid/16x9/4x3), document(fluid/pageless/letter/a4), social(1x1/4x5/9x16)")
    card_group.add_argument("--header-footer", nargs="+", metavar="POS:TYPE[:VALUE]",
                            help="Header/footer items, e.g. 'bottomRight:text:Company Name' 'topLeft:image:https://logo.png' 'bottomCenter:cardNumber'")
    card_group.add_argument("--hf-hide-first", action="store_true", help="Hide header/footer from first card")
    card_group.add_argument("--hf-hide-last", action="store_true", help="Hide header/footer from last card")

    add_sharing_args(p_gen)
    add_wait_args(p_gen)
    p_gen.set_defaults(func=cmd_generate)

    # from-template
    p_tmpl = subparsers.add_parser("from-template", help="Create from existing template (Remix)")
    p_tmpl.add_argument("template_id", help="Gamma ID of the template (e.g., g_abcdef123456)")
    p_tmpl.add_argument("prompt", help="Content/instructions for the template")
    p_tmpl.add_argument("--theme", "-t", help="Theme ID to apply (overrides template theme)")
    p_tmpl.add_argument("--folder", help="Folder ID to save to")
    p_tmpl.add_argument("--export-as", "-e", choices=EXPORT_FORMATS, help="Also export as PDF/PPTX")
    p_tmpl.add_argument("--image-model", help="AI image model for template images")
    p_tmpl.add_argument("--image-style", help="AI image style description")
    add_sharing_args(p_tmpl)
    add_wait_args(p_tmpl)
    p_tmpl.set_defaults(func=cmd_from_template)

    # status
    p_status = subparsers.add_parser("status", help="Check generation status")
    p_status.add_argument("generation_id", help="Generation ID to check")
    p_status.set_defaults(func=cmd_status)

    # export
    p_export = subparsers.add_parser("export", help="Get export URLs (PDF/PPTX)")
    p_export.add_argument("generation_id", help="Generation ID")
    p_export.set_defaults(func=cmd_export)

    # themes
    p_themes = subparsers.add_parser("themes", help="List available themes")
    p_themes.add_argument("--limit", "-l", type=int, help="Limit number of results")
    p_themes.add_argument("--search", "-s", help="Search themes by name")
    p_themes.set_defaults(func=cmd_themes)

    # folders
    p_folders = subparsers.add_parser("folders", help="List available folders")
    p_folders.set_defaults(func=cmd_folders)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
