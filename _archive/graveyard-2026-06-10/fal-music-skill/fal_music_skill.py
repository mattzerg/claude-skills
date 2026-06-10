#!/usr/bin/env python3
"""FAL Music Skill - Music/audio generation using FAL.ai (Stable Audio, Beatoven, etc.)"""

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

# Available models and their FAL endpoints + response shapes
MODELS = {
    # Stable Audio Open (free/open, max 47s)
    "stable-audio": {
        "endpoint": "fal-ai/stable-audio",
        "audio_key": "audio_file",  # response.audio_file.url
        "max_duration": 47,
        "description": "Stable Audio Open — good for loops/SFX (max 47s)",
    },
    # Stable Audio 2.5 (enterprise quality, max 190s)
    "stable-audio-25": {
        "endpoint": "fal-ai/stable-audio-25/text-to-audio",
        "audio_key": "audio",  # response.audio.url
        "max_duration": 190,
        "description": "Stable Audio 2.5 — high quality music (max 190s, $0.20/gen)",
    },
    # Beatoven Maestro (best for music, max 150s)
    "beatoven": {
        "endpoint": "beatoven/music-generation",
        "audio_key": "audio",  # response.audio.url
        "max_duration": 150,
        "description": "Beatoven Maestro — best for full songs (max 150s)",
    },
    # CassetteAI (high quality, up to 180s, $0.02/min output)
    "cassetteai": {
        "endpoint": "cassetteai/music-generator",
        "audio_key": "audio_file",  # response.audio_file.url
        "max_duration": 180,
        "description": "CassetteAI — high quality music generation (max 180s, $0.02/min)",
    },
    # Google Lyria2 (excellent quality, 30s max, 48kHz WAV)
    "lyria2": {
        "endpoint": "fal-ai/lyria2",
        "audio_key": "audio",  # response.audio.url
        "max_duration": 30,
        "description": "Google Lyria2 — excellent quality, short tracks (max 30s)",
    },
}

DEFAULT_MODEL = "cassetteai"


def _load_zerg_secrets():
    """Populate os.environ from ~/.config/zerg/secrets.env (gitignored, chmod 600). Fail-open."""
    p = os.path.expanduser("~/.config/zerg/secrets.env")
    try:
        with open(p) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
    except Exception:
        pass


def get_api_key():
    """Get FAL API key from environment or config (shared with fal-video-skill)."""
    _load_zerg_secrets()
    api_key = os.environ.get("FAL_KEY") or os.environ.get("FAL_API_KEY")
    if api_key:
        return api_key

    # Check own config first
    config_file = CONFIG_DIR / "config.json"
    if config_file.exists():
        with open(config_file) as f:
            config = json.load(f)
            key = config.get("api_key")
            if key:
                return key

    # Fall back to fal-video-skill config (shared FAL key)
    video_config = CONFIG_DIR.parent / "fal-video-skill" / "config.json"
    if video_config.exists():
        with open(video_config) as f:
            config = json.load(f)
            return config.get("api_key")

    return None


def output(data):
    """Output JSON response."""
    print(json.dumps(data, indent=2, default=str))


def submit_fal_request(endpoint, payload, api_key):
    """Submit async request to FAL queue."""
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


def run_fal_sync(endpoint, payload, api_key, timeout=300):
    """Submit FAL request and poll until completion."""
    submit_result = submit_fal_request(endpoint, payload, api_key)

    if "error" in submit_result:
        return submit_result

    request_id = submit_result.get("request_id")
    if not request_id:
        return {"error": "No request_id returned", "response": submit_result}

    status_url = submit_result.get("status_url")
    response_url = submit_result.get("response_url")

    if not status_url or not response_url:
        status_url = f"https://queue.fal.run/{endpoint}/requests/{request_id}/status"
        response_url = f"https://queue.fal.run/{endpoint}/requests/{request_id}"

    start_time = time.time()
    while time.time() - start_time < timeout:
        response = requests.get(status_url, headers={"Authorization": f"Key {api_key}"})
        if response.status_code != 200:
            time.sleep(3)
            continue

        status = response.json()
        state = status.get("status")

        if state == "COMPLETED":
            result_response = requests.get(response_url, headers={"Authorization": f"Key {api_key}"})
            if result_response.status_code == 200:
                return result_response.json()
            return {"error": f"Failed to get result: {result_response.text}"}
        elif state in ["FAILED", "CANCELLED"]:
            return {"error": f"Request {state}", "details": status}

        if status.get("logs"):
            for log in status["logs"]:
                print(f"[FAL] {log.get('message', '')}", file=sys.stderr)

        time.sleep(3)

    return {"error": "Timeout waiting for result", "request_id": request_id}


def download_audio(url, output_path):
    """Download audio from URL to local file."""
    response = requests.get(url, stream=True)
    if response.status_code != 200:
        return False

    with open(output_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)

    return True


def sanitize_filename(text: str, max_length: int = 50) -> str:
    """Convert text to safe filename."""
    import re
    clean = re.sub(r'[^\w\s-]', '', text.lower())
    clean = re.sub(r'\s+', '_', clean)
    return clean[:max_length].rstrip('_')


def cmd_generate(args):
    """Generate music from text prompt."""
    api_key = get_api_key()
    if not api_key:
        output({"error": "FAL API key not configured. Set FAL_KEY env var or add config.json"})
        return

    if not args.prompt:
        output({"error": "Prompt required"})
        return

    model_name = args.model or DEFAULT_MODEL
    model_info = MODELS.get(model_name)
    if not model_info:
        output({"error": f"Unknown model: {model_name}", "available": list(MODELS.keys())})
        return

    endpoint = model_info["endpoint"]
    duration = min(args.duration or 60, model_info["max_duration"])

    # Build payload per model
    if model_name == "stable-audio":
        payload = {
            "prompt": args.prompt,
            "seconds_total": duration,
            "steps": args.steps or 100,
        }
    elif model_name == "stable-audio-25":
        payload = {
            "prompt": args.prompt,
            "seconds_total": duration,
            "num_inference_steps": args.steps or 8,
            "guidance_scale": args.guidance or 1,
        }
    elif model_name == "beatoven":
        payload = {
            "prompt": args.prompt,
            "duration": duration,
            "refinement": args.steps or 100,
            "creativity": args.creativity or 16,
        }
        if args.negative_prompt:
            payload["negative_prompt"] = args.negative_prompt
    elif model_name == "cassetteai":
        payload = {
            "prompt": args.prompt,
            "duration": duration,
        }
    elif model_name == "lyria2":
        payload = {
            "prompt": args.prompt,
        }
        if args.negative_prompt:
            payload["negative_prompt"] = args.negative_prompt
    else:
        payload = {"prompt": args.prompt}

    if args.seed is not None:
        payload["seed"] = args.seed

    print(f"[FAL] Generating music with {model_name}...", file=sys.stderr)
    print(f"[FAL] Prompt: {args.prompt[:80]}{'...' if len(args.prompt) > 80 else ''}", file=sys.stderr)
    print(f"[FAL] Duration: {duration}s", file=sys.stderr)

    result = run_fal_sync(endpoint, payload, api_key, timeout=args.timeout or 300)

    if "error" in result:
        output(result)
        return

    # Extract audio URL — different models use different response shapes
    audio_key = model_info["audio_key"]
    audio_url = None
    audio_obj = result.get(audio_key, {})
    if isinstance(audio_obj, dict):
        audio_url = audio_obj.get("url")
    elif isinstance(audio_obj, str):
        audio_url = audio_obj

    if not audio_url:
        output({"error": "No audio URL in response", "response": result})
        return

    # Determine file extension from URL or default to wav
    ext = "wav"
    if ".mp3" in audio_url:
        ext = "mp3"
    elif ".flac" in audio_url:
        ext = "flac"

    # Build output path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_prompt = sanitize_filename(args.prompt)
    default_path = OUTPUT_DIR / f"{timestamp}_{model_name}_{safe_prompt}.{ext}"
    output_path = Path(args.output) if args.output else default_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if download_audio(audio_url, output_path):
        output({
            "status": "success",
            "model": model_name,
            "file": str(output_path),
            "url": audio_url,
            "duration": duration,
            "prompt": args.prompt,
        })
    else:
        output({
            "status": "success",
            "model": model_name,
            "url": audio_url,
            "note": "Audio URL returned but download failed. Use URL directly.",
        })


def cmd_models(args):
    """List available models."""
    model_list = {}
    for name, info in MODELS.items():
        model_list[name] = {
            "description": info["description"],
            "max_duration": f"{info['max_duration']}s",
            "endpoint": info["endpoint"],
        }
    output({
        "models": model_list,
        "default": DEFAULT_MODEL,
        "recommendation": "Use 'beatoven' for full songs, 'stable-audio-25' for quality music, 'stable-audio' for loops/SFX",
    })


def cmd_config(args):
    """Configure FAL API key."""
    if not args.api_key:
        api_key = get_api_key()
        if api_key:
            masked = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "****"
            output({"status": "configured", "api_key": masked})
        else:
            output({"status": "not configured", "help": "Run: fal_music_skill.py config API_KEY"})
        return

    config = {"api_key": args.api_key}
    config_file = CONFIG_DIR / "config.json"
    with open(config_file, "w") as f:
        json.dump(config, f, indent=2)
    os.chmod(config_file, 0o600)
    output({"status": "success", "message": "API key saved", "config_file": str(config_file)})


def main():
    parser = argparse.ArgumentParser(description="FAL Music Generation Skill")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Generate music
    gen_parser = subparsers.add_parser("generate", help="Generate music from text prompt")
    gen_parser.add_argument("prompt", nargs="?", help="Music description prompt")
    gen_parser.add_argument("--model", "-m", help=f"Model to use (default: {DEFAULT_MODEL})")
    gen_parser.add_argument("--duration", "-d", type=int, default=60, help="Duration in seconds (default: 60)")
    gen_parser.add_argument("--steps", "-s", type=int, help="Inference/refinement steps")
    gen_parser.add_argument("--guidance", "-g", type=int, help="Guidance scale (stable-audio-25)")
    gen_parser.add_argument("--creativity", type=float, help="Creativity level 1-20 (beatoven)")
    gen_parser.add_argument("--negative-prompt", "-n", help="What to avoid (beatoven)")
    gen_parser.add_argument("--seed", type=int, help="Random seed for reproducibility")
    gen_parser.add_argument("--output", "-o", help="Output file path")
    gen_parser.add_argument("--timeout", "-t", type=int, default=300, help="Timeout in seconds")

    # List models
    subparsers.add_parser("models", help="List available models")

    # Configure
    config_parser = subparsers.add_parser("config", help="Configure API key")
    config_parser.add_argument("api_key", nargs="?", help="FAL API key")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "generate": cmd_generate,
        "models": cmd_models,
        "config": cmd_config,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
