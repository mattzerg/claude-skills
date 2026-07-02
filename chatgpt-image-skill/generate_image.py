#!/usr/bin/env python3
"""Generate an image via OpenAI gpt-image-1.

Usage:
    python3 generate_image.py "prompt" [--size auto|1024x1024|1024x1536|1536x1024]
                                       [--quality auto|low|medium|high]
                                       [--output PATH]
                                       [--n N]
                                       [--no-brand-prefix]

Loads OPENAI_API_KEY from env, falling back to macOS Keychain entry of the same name.
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path

BRAND_PREFIX = (
    "Cream paper background (#f4f0e7), charcoal accents (#111514), "
    "burnt-orange highlights (#b3662f), green secondary (#6FBE31). "
    "Geometric flat-editorial illustration similar to Stripe blog illustrations. "
    "Space Grotesk feel — geometric, technical, but warm. "
    "No embedded text or logos. NOT cosmic, NOT space-themed, NOT circuit-board. "
    "Safe area in centered 80% of frame. "
    "Source: feedback_zerg_brand.md (live-site palette, ~/zerg/web/src/pages/index.vue). "
    "For dark-paper variants pass --no-brand-prefix and supply explicit dark instructions."
)


def load_api_key():
    key = os.environ.get("OPENAI_API_KEY")
    if key:
        return key
    try:
        result = subprocess.run(
            ["security", "find-generic-password", "-a", os.environ["USER"], "-s", "OPENAI_API_KEY", "-w"],
            capture_output=True, text=True, check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError, KeyError):
        return None


def generate(prompt, size, quality, n, output, no_brand_prefix):
    api_key = load_api_key()
    if not api_key:
        print("Error: OPENAI_API_KEY not set in env or macOS Keychain.", file=sys.stderr)
        print("  Add via: security add-generic-password -a $USER -s OPENAI_API_KEY -w 'sk-...'", file=sys.stderr)
        sys.exit(1)

    full_prompt = (BRAND_PREFIX if not no_brand_prefix else "") + prompt

    body = {
        "model": "gpt-image-1",
        "prompt": full_prompt,
        "n": n,
        "size": size,
        "quality": quality,
    }

    req = urllib.request.Request(
        "https://api.openai.com/v1/images/generations",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        err_body = e.read().decode(errors="ignore")
        # Surface failure on STDOUT so callers piping through `tail` still see it.
        print(f"FAILED: OpenAI API error {e.code} (output={output})")
        print(f"OpenAI API error {e.code}: {err_body}", file=sys.stderr)
        sys.exit(2)
    except urllib.error.URLError as e:
        print(f"FAILED: network error (output={output}): {e.reason}")
        print(f"Network error: {e.reason}", file=sys.stderr)
        sys.exit(2)

    if isinstance(data, dict) and data.get("error"):
        print(f"FAILED: OpenAI returned 200 with error body (output={output})")
        print(f"OpenAI error body: {json.dumps(data['error'])}", file=sys.stderr)
        sys.exit(2)

    output_paths = []
    out_dir = Path(output).parent if output.endswith(".png") else Path(output)
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, item in enumerate(data.get("data", [])):
        b64 = item.get("b64_json")
        if not b64:
            continue
        if output.endswith(".png") and n == 1:
            out_path = Path(output)
        else:
            stem = Path(output).stem if output.endswith(".png") else "gpt-image"
            out_path = out_dir / f"{stem}-{i+1}.png"
        out_path.write_bytes(base64.b64decode(b64))
        output_paths.append(out_path)
        print(f"Wrote {out_path} ({out_path.stat().st_size:,} bytes)")

    if not output_paths:
        print(f"FAILED: API returned no image data (output={output})")
        print("Error: API returned no image data.", file=sys.stderr)
        sys.exit(3)

    return output_paths


def main():
    parser = argparse.ArgumentParser(description="Generate an image via OpenAI gpt-image-1")
    parser.add_argument("prompt", help="The image prompt")
    parser.add_argument("--size", default="auto",
                        choices=["auto", "1024x1024", "1024x1536", "1536x1024"],
                        help="Output size (auto picks based on prompt)")
    parser.add_argument("--quality", default="auto",
                        choices=["auto", "low", "medium", "high"],
                        help="Quality tier (cost scales accordingly)")
    parser.add_argument("--output", default="./generated_images/gpt-image.png",
                        help="Output PNG path or directory")
    parser.add_argument("--n", type=int, default=1, help="Number of variations")
    parser.add_argument("--no-brand-prefix", action="store_true",
                        help="Skip the Zerg brand prompt prefix")
    args = parser.parse_args()
    generate(args.prompt, args.size, args.quality, args.n, args.output, args.no_brand_prefix)


if __name__ == "__main__":
    main()
