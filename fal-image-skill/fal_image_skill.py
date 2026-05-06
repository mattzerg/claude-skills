#!/usr/bin/env python3
"""FAL Image Skill - Image generation using FAL.ai (Flux, Recraft, Ideogram, SDXL)."""

import argparse
import json
import sys
import os
import time
import requests
from pathlib import Path
from datetime import datetime

CONFIG_DIR = Path(__file__).parent
OUTPUT_DIR = CONFIG_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

MODELS = {
    "flux-pro": "fal-ai/flux-pro/v1.1-ultra",
    "flux-pro-1.1": "fal-ai/flux-pro/v1.1",
    "flux-pro-ultra": "fal-ai/flux-pro/v1.1-ultra",
    "flux-dev": "fal-ai/flux/dev",
    "flux-schnell": "fal-ai/flux/schnell",
    "flux-realism": "fal-ai/flux-realism",
    "recraft": "fal-ai/recraft-v3",
    "ideogram": "fal-ai/ideogram/v2",
    "ideogram-turbo": "fal-ai/ideogram/v2/turbo",
    "sdxl": "fal-ai/fast-sdxl",
    "sdxl-lightning": "fal-ai/fast-lightning-sdxl",
    "stable-diffusion-3.5": "fal-ai/stable-diffusion-v35-large",
}

DEFAULT_MODEL = "flux-pro"

ASPECT_RATIO_TO_SIZE = {
    "1:1": (1024, 1024),
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "4:3": (1024, 768),
    "3:4": (768, 1024),
    "21:9": (1536, 640),
}


def get_api_key():
    api_key = os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")
    if api_key:
        return api_key
    config_file = CONFIG_DIR / "config.json"
    if config_file.exists():
        with open(config_file) as f:
            return json.load(f).get("api_key")
    # Fall back to fal-video-skill config so users only configure once
    sibling = CONFIG_DIR.parent / "fal-video-skill" / "config.json"
    if sibling.exists():
        with open(sibling) as f:
            return json.load(f).get("api_key")
    return None


def output(data):
    print(json.dumps(data, indent=2, default=str))


def submit_fal_request(endpoint, payload, api_key):
    response = requests.post(
        f"https://queue.fal.run/{endpoint}",
        headers={
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json",
        },
        json=payload,
    )
    if response.status_code != 200:
        return {"error": f"FAL API error: {response.status_code} - {response.text}"}
    return response.json()


def run_fal_sync(endpoint, payload, api_key, timeout=180):
    submit_result = submit_fal_request(endpoint, payload, api_key)
    if "error" in submit_result:
        return submit_result

    request_id = submit_result.get("request_id")
    if not request_id:
        return {"error": "No request_id returned", "response": submit_result}

    status_url = submit_result.get("status_url") or f"https://queue.fal.run/{endpoint}/requests/{request_id}/status"
    response_url = submit_result.get("response_url") or f"https://queue.fal.run/{endpoint}/requests/{request_id}"

    start_time = time.time()
    while time.time() - start_time < timeout:
        r = requests.get(status_url, headers={"Authorization": f"Key {api_key}"})
        if r.status_code != 200:
            time.sleep(2)
            continue
        status = r.json()
        state = status.get("status")
        if state == "COMPLETED":
            result = requests.get(response_url, headers={"Authorization": f"Key {api_key}"})
            if result.status_code == 200:
                return result.json()
            return {"error": f"Failed to get result: {result.text}"}
        if state in ("FAILED", "CANCELLED"):
            return {"error": f"Request {state}", "details": status}
        if status.get("logs"):
            for log in status["logs"]:
                print(f"[FAL] {log.get('message', '')}", file=sys.stderr)
        time.sleep(2)

    return {"error": "Timeout waiting for result", "request_id": request_id, "status_url": status_url}


def download_image(url, output_path):
    r = requests.get(url, stream=True)
    if r.status_code != 200:
        return False
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)
    return True


def build_payload(model, args):
    payload = {"prompt": args.prompt}

    if args.negative_prompt:
        payload["negative_prompt"] = args.negative_prompt

    if model in ("flux-pro", "flux-pro-ultra"):
        if args.aspect_ratio:
            payload["aspect_ratio"] = args.aspect_ratio
        payload["num_images"] = args.num_images
        payload["enable_safety_checker"] = True
        if args.seed is not None:
            payload["seed"] = args.seed
    elif model == "flux-pro-1.1":
        if args.aspect_ratio and args.aspect_ratio in ASPECT_RATIO_TO_SIZE:
            w, h = ASPECT_RATIO_TO_SIZE[args.aspect_ratio]
            payload["image_size"] = {"width": w, "height": h}
        payload["num_images"] = args.num_images
        if args.seed is not None:
            payload["seed"] = args.seed
    elif model in ("flux-dev", "flux-schnell", "flux-realism", "sdxl", "sdxl-lightning", "stable-diffusion-3.5"):
        if args.aspect_ratio and args.aspect_ratio in ASPECT_RATIO_TO_SIZE:
            w, h = ASPECT_RATIO_TO_SIZE[args.aspect_ratio]
            payload["image_size"] = {"width": w, "height": h}
        payload["num_images"] = args.num_images
        if args.seed is not None:
            payload["seed"] = args.seed
    elif model == "recraft":
        if args.aspect_ratio and args.aspect_ratio in ASPECT_RATIO_TO_SIZE:
            w, h = ASPECT_RATIO_TO_SIZE[args.aspect_ratio]
            payload["image_size"] = {"width": w, "height": h}
        if args.style:
            payload["style"] = args.style
    elif model in ("ideogram", "ideogram-turbo"):
        if args.aspect_ratio:
            payload["aspect_ratio"] = args.aspect_ratio
        if args.style:
            payload["style"] = args.style
        if args.seed is not None:
            payload["seed"] = args.seed

    return payload


def cmd_gen(args):
    api_key = get_api_key()
    if not api_key:
        output({"error": "FAL API key not configured. Set FAL_KEY env var or run: fal_image_skill.py config YOUR_KEY"})
        return

    if not args.prompt:
        output({"error": "Prompt required", "usage": "fal_image_skill.py gen 'PROMPT' [--model MODEL]"})
        return

    model = args.model or DEFAULT_MODEL
    if model not in MODELS:
        output({"error": f"Unknown model: {model}", "available": list(MODELS.keys())})
        return

    endpoint = MODELS[model]
    payload = build_payload(model, args)

    print(f"[FAL] Generating image with {model}...", file=sys.stderr)
    result = run_fal_sync(endpoint, payload, api_key, timeout=args.timeout)

    if "error" in result:
        output(result)
        return

    images = result.get("images") or []
    if not images and "image" in result:
        images = [result["image"]]
    if not images:
        output({"error": "No images in response", "response": result})
        return

    saved = []
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    for i, img in enumerate(images):
        url = img.get("url") if isinstance(img, dict) else img
        if not url:
            continue
        if args.output and len(images) == 1:
            out_path = Path(args.output)
        else:
            stem = Path(args.output).stem if args.output else f"image_{model}_{timestamp}"
            ext = Path(url.split("?")[0]).suffix or ".png"
            out_path = (Path(args.output).parent if args.output else OUTPUT_DIR) / f"{stem}_{i}{ext}" if len(images) > 1 else OUTPUT_DIR / f"{stem}{ext}"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if download_image(url, out_path):
            saved.append({"file": str(out_path), "url": url})
        else:
            saved.append({"url": url, "note": "download failed"})

    output({
        "status": "success",
        "model": model,
        "prompt": args.prompt,
        "seed": result.get("seed"),
        "images": saved,
    })


def cmd_models(args):
    output({
        "models": {
            "flux-pro": "Flux Pro 1.1 Ultra (top quality, photorealistic)",
            "flux-pro-1.1": "Flux Pro 1.1 (high quality, faster than ultra)",
            "flux-dev": "Flux Dev (good quality, cheaper)",
            "flux-schnell": "Flux Schnell (fastest, cheapest)",
            "flux-realism": "Flux Realism LoRA (photo-realistic faces/scenes)",
            "recraft": "Recraft v3 (designs, illustrations, brand style)",
            "ideogram": "Ideogram v2 (best for in-image text rendering)",
            "ideogram-turbo": "Ideogram v2 Turbo (faster Ideogram)",
            "sdxl": "Fast SDXL",
            "sdxl-lightning": "SDXL Lightning (very fast)",
            "stable-diffusion-3.5": "Stable Diffusion 3.5 Large",
        },
        "default": DEFAULT_MODEL,
        "recommendation": "flux-pro for memes/photo, ideogram if caption needs to render in-image, flux-schnell for cheap drafts",
    })


def cmd_config(args):
    if not args.api_key:
        api_key = get_api_key()
        if api_key:
            masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "****"
            output({"status": "configured", "api_key": masked})
        else:
            output({"status": "not configured", "help": "Run: fal_image_skill.py config YOUR_API_KEY"})
        return

    config_file = CONFIG_DIR / "config.json"
    with open(config_file, "w") as f:
        json.dump({"api_key": args.api_key}, f, indent=2)
    os.chmod(config_file, 0o600)
    output({"status": "success", "message": "API key saved", "config_file": str(config_file)})


def main():
    parser = argparse.ArgumentParser(description="FAL Image Generation Skill")
    sub = parser.add_subparsers(dest="command")

    g = sub.add_parser("gen", help="Generate image from text prompt")
    g.add_argument("prompt", nargs="?", help="Text prompt")
    g.add_argument("--model", "-m", help=f"Model (default: {DEFAULT_MODEL})")
    g.add_argument("--aspect-ratio", "-a", default="16:9", help="1:1, 16:9, 9:16, 4:3, 3:4, 21:9")
    g.add_argument("--num-images", "-n", type=int, default=1, help="Number of images")
    g.add_argument("--negative-prompt", help="Negative prompt")
    g.add_argument("--style", help="Style (Recraft/Ideogram only)")
    g.add_argument("--seed", type=int, help="Random seed for reproducibility")
    g.add_argument("--output", "-o", help="Output file path")
    g.add_argument("--timeout", "-t", type=int, default=180, help="Timeout in seconds")

    sub.add_parser("models", help="List available models")

    c = sub.add_parser("config", help="Configure API key")
    c.add_argument("api_key", nargs="?", help="FAL API key")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    {"gen": cmd_gen, "models": cmd_models, "config": cmd_config}[args.command](args)


if __name__ == "__main__":
    main()
