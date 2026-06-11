#!/usr/bin/env python3
"""Eleven Labs Skill - AI Voice Generation, Cloning, and Sound Effects."""

import argparse
import json
import sys
import os
from pathlib import Path
from datetime import datetime

try:
    from elevenlabs import ElevenLabs, Voice, VoiceSettings
    from elevenlabs.client import ElevenLabs as ElevenLabsClient
except ImportError:
    print(json.dumps({"error": "elevenlabs not installed. Run: pip3 install elevenlabs"}))
    sys.exit(1)

CONFIG_DIR = Path(__file__).parent
CONFIG_FILE = CONFIG_DIR / "config.json"
OUTPUT_DIR = CONFIG_DIR / "output"


def output(data):
    """Output JSON response."""
    print(json.dumps(data, indent=2, default=str))


def load_config():
    """Load API key from config."""
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def save_config(config):
    """Save config to file."""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)


def get_client():
    """Get authenticated ElevenLabs client."""
    config = load_config()
    api_key = config.get('api_key') or os.environ.get('ELEVENLABS_API_KEY')

    if not api_key:
        return None, "API key not configured. Run: python3 eleven_labs_skill.py setup YOUR_API_KEY"

    try:
        client = ElevenLabsClient(api_key=api_key)
        return client, None
    except Exception as e:
        return None, f"Failed to initialize client: {str(e)}"


def cmd_setup(args):
    """Set up API key."""
    if not args.api_key:
        output({
            "error": "API key required",
            "usage": "python3 eleven_labs_skill.py setup YOUR_API_KEY",
            "get_key": "Get your API key at https://elevenlabs.io/api"
        })
        return

    config = load_config()
    config['api_key'] = args.api_key
    save_config(config)

    # Verify the key works
    client, error = get_client()
    if error:
        output({"error": error})
        return

    try:
        # Test by listing voices
        voices = client.voices.get_all()
        output({
            "status": "success",
            "message": "Eleven Labs configured successfully",
            "voices_available": len(voices.voices)
        })
    except Exception as e:
        output({"error": f"API key validation failed: {str(e)}"})


def cmd_voices(args):
    """List available voices."""
    client, error = get_client()
    if error:
        output({"error": error})
        return

    try:
        response = client.voices.get_all()
        voices = []

        for voice in response.voices:
            voice_info = {
                "voice_id": voice.voice_id,
                "name": voice.name,
                "category": voice.category if hasattr(voice, 'category') else None,
                "labels": voice.labels if hasattr(voice, 'labels') else None,
            }

            # Filter by category if specified
            if args.category:
                if voice_info.get('category') and args.category.lower() in voice_info['category'].lower():
                    voices.append(voice_info)
            else:
                voices.append(voice_info)

        output({"voices": voices, "count": len(voices)})

    except Exception as e:
        output({"error": f"Failed to list voices: {str(e)}"})


def cmd_speak(args):
    """Generate speech from text."""
    client, error = get_client()
    if error:
        output({"error": error})
        return

    if not args.text:
        output({"error": "Text required", "usage": "python3 eleven_labs_skill.py speak \"Hello world\""})
        return

    try:
        # Find voice by name or use voice_id directly (real IDs are ~20+ alphanumeric chars)
        import re as _re
        voice_id = args.voice
        if args.voice and not _re.fullmatch(r"[A-Za-z0-9]{20,}", args.voice):
            response = client.voices.get_all()
            for v in response.voices:
                if args.voice.lower() in v.name.lower():
                    voice_id = v.voice_id
                    break

        # Default to Rachel if no voice specified
        if not voice_id:
            voice_id = "21m00Tcm4TlvDq8ikWAM"  # Rachel

        # Generate audio (SDK v1+ removed client.generate; convert returns a bytes iterator)
        if hasattr(client, "text_to_speech"):
            audio = client.text_to_speech.convert(
                voice_id=voice_id,
                text=args.text,
                model_id=args.model or "eleven_multilingual_v2",
                output_format="mp3_44100_128",
            )
        else:  # legacy SDK (<1.0)
            audio = client.generate(
                text=args.text,
                voice=voice_id,
                model=args.model or "eleven_monolingual_v1"
            )

        # Save to file
        OUTPUT_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"speech_{timestamp}.mp3"
        filepath = OUTPUT_DIR / filename

        with open(filepath, 'wb') as f:
            for chunk in audio:
                f.write(chunk)

        output({
            "status": "success",
            "file": str(filepath),
            "text": args.text[:100] + "..." if len(args.text) > 100 else args.text,
            "voice": voice_id
        })

    except Exception as e:
        output({"error": f"Speech generation failed: {str(e)}"})


def cmd_clone(args):
    """Clone a voice from audio samples."""
    client, error = get_client()
    if error:
        output({"error": error})
        return

    if not args.name or not args.files:
        output({
            "error": "Name and audio files required",
            "usage": "python3 eleven_labs_skill.py clone \"Voice Name\" file1.mp3 file2.mp3"
        })
        return

    try:
        # Read audio files
        audio_files = []
        for file_path in args.files:
            path = Path(file_path)
            if not path.exists():
                output({"error": f"File not found: {file_path}"})
                return
            audio_files.append(open(path, 'rb'))

        # Create cloned voice
        voice = client.clone(
            name=args.name,
            description=args.description or f"Cloned voice: {args.name}",
            files=audio_files
        )

        # Close files
        for f in audio_files:
            f.close()

        output({
            "status": "success",
            "voice_id": voice.voice_id,
            "name": voice.name,
            "message": f"Voice '{args.name}' cloned successfully"
        })

    except Exception as e:
        output({"error": f"Voice cloning failed: {str(e)}"})


def cmd_sfx(args):
    """Generate sound effects from text description."""
    client, error = get_client()
    if error:
        output({"error": error})
        return

    if not args.description:
        output({
            "error": "Description required",
            "usage": "python3 eleven_labs_skill.py sfx \"thunder rolling in the distance\""
        })
        return

    try:
        # Generate sound effect
        audio = client.text_to_sound_effects.convert(
            text=args.description,
            duration_seconds=args.duration or 5.0
        )

        # Save to file
        OUTPUT_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Create safe filename from description
        safe_desc = "".join(c if c.isalnum() else "_" for c in args.description[:30])
        filename = f"sfx_{safe_desc}_{timestamp}.mp3"
        filepath = OUTPUT_DIR / filename

        with open(filepath, 'wb') as f:
            for chunk in audio:
                f.write(chunk)

        output({
            "status": "success",
            "file": str(filepath),
            "description": args.description,
            "duration": args.duration or 5.0
        })

    except Exception as e:
        output({"error": f"Sound effect generation failed: {str(e)}"})


def cmd_models(args):
    """List available models."""
    client, error = get_client()
    if error:
        output({"error": error})
        return

    try:
        models = client.models.get_all()
        model_list = []

        for model in models:
            model_list.append({
                "model_id": model.model_id,
                "name": model.name,
                "description": model.description if hasattr(model, 'description') else None,
                "can_do_text_to_speech": model.can_do_text_to_speech if hasattr(model, 'can_do_text_to_speech') else None,
                "languages": [lang.language_id for lang in model.languages] if hasattr(model, 'languages') and model.languages else None
            })

        output({"models": model_list, "count": len(model_list)})

    except Exception as e:
        output({"error": f"Failed to list models: {str(e)}"})


def cmd_history(args):
    """Get generation history."""
    client, error = get_client()
    if error:
        output({"error": error})
        return

    try:
        history = client.history.get_all(page_size=args.limit or 20)
        items = []

        for item in history.history:
            items.append({
                "history_item_id": item.history_item_id,
                "voice_name": item.voice_name if hasattr(item, 'voice_name') else None,
                "text": item.text[:100] + "..." if len(item.text) > 100 else item.text,
                "date_unix": item.date_unix if hasattr(item, 'date_unix') else None,
                "character_count": item.character_count_change_from if hasattr(item, 'character_count_change_from') else None
            })

        output({"history": items, "count": len(items)})

    except Exception as e:
        output({"error": f"Failed to get history: {str(e)}"})


def cmd_sync(args):
    """
    Parse a shot-list markdown file, extract per-cut VO lines, synthesize
    each to MP3, emit timing.json + timing.srt aligned to the cut schedule.
    """
    import re
    import subprocess as _subp
    from pathlib import Path as _Path

    VOICE_PRESETS = {
        # Male
        "adam": "pNInz6obpgDQGcFmaJgB",
        "daniel": "onwK4e9ZLuTAKqWW03F9",
        "antoni": "ErXwobaYiN019PkySvjV",
        "josh": "TxGEqnHWrfWFTfGW9XjX",
        # Female
        "rachel": "21m00Tcm4TlvDq8ikWAM",
        "jessica": "cgSgspJ2msm6clMCkdW9",   # TikTok-style young female narrator
        "bella": "EXAVITQu4vr4xnSDxMaC",
        "domi": "AZnzlk1XvdvUeBnXmlld",
        # Tagged aliases for clarity
        "tiktok-female": "cgSgspJ2msm6clMCkdW9",  # alias → jessica
        "matt-clone": None,
    }

    if not args.shotlist:
        output({"error": "shotlist path required", "usage": "sync --shotlist path.md --voice adam --out path/"})
        return

    shotlist_path = _Path(args.shotlist).expanduser()
    if not shotlist_path.exists():
        output({"error": f"shotlist not found: {shotlist_path}"})
        return

    md = shotlist_path.read_text()

    cuts = []
    in_table = False
    header_cols = []

    for raw_line in md.splitlines():
        line = raw_line.strip()
        if not line.startswith("|"):
            in_table = False
            header_cols = []
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(set(c) <= {"-", ":", " "} for c in cells if c):
            in_table = True
            continue
        if not in_table or not header_cols:
            if any("vo" in c.lower() or "caption" in c.lower() for c in cells):
                header_cols = [c.lower() for c in cells]
            continue
        if len(cells) < len(header_cols):
            continue

        row = dict(zip(header_cols, cells))
        cut_id = row.get("#") or row.get("id") or cells[0]
        time_col = row.get("time", "")
        dur_col = row.get("dur", "") or row.get("duration", "")
        vo_cell = None
        for k, v in row.items():
            if "vo" in k or "caption" in k:
                vo_cell = v
                break
        if vo_cell is None:
            continue

        vo_match = re.search(r'VO:\s*\*?["“]([^"”]+)["”]\*?', vo_cell)
        vo_text = vo_match.group(1) if vo_match else ""
        if not vo_text:
            vo_match2 = re.search(r"VO:\s*\*?([^*\n]+?)(?:\s*CAP:|$)", vo_cell)
            if vo_match2:
                vo_text = vo_match2.group(1).strip().strip('"“”\' ')
        cap_match = re.search(r"CAP:\s*`([^`]+)`", vo_cell)
        cap_text = cap_match.group(1) if cap_match else ""
        dur_match = re.match(r"([\d.]+)\s*s", dur_col)
        dur_expected = float(dur_match.group(1)) if dur_match else 0.0

        if vo_text or cap_text:
            cuts.append({
                "cut_id": cut_id,
                "time": time_col,
                "dur_expected": dur_expected,
                "vo_text": vo_text,
                "cap_text": cap_text,
            })

    vo_cuts = [c for c in cuts if c["vo_text"]]

    if args.dry_run:
        output({
            "shotlist": str(shotlist_path),
            "total_cuts_found": len(cuts),
            "vo_cuts": len(vo_cuts),
            "vo_lines": [{"cut_id": c["cut_id"], "dur_expected": c["dur_expected"], "vo_text": c["vo_text"]} for c in vo_cuts],
            "captions_only": [{"cut_id": c["cut_id"], "cap_text": c["cap_text"]} for c in cuts if not c["vo_text"] and c["cap_text"]],
        })
        return

    voice_arg = (args.voice or "adam").lower()
    voice_id = VOICE_PRESETS.get(voice_arg, voice_arg)
    if voice_id is None:
        output({"error": f"voice preset '{voice_arg}' not configured; use adam|daniel|rachel|antoni"})
        return

    out_dir = _Path(args.out).expanduser() if args.out else _Path.home() / "Downloads" / "eleven-labs-sync" / shotlist_path.stem
    out_dir.mkdir(parents=True, exist_ok=True)

    client, err = get_client()
    if err:
        output({"error": err})
        return

    timing = []
    srt_entries = []
    cumulative_t = 0.0
    srt_idx = 1

    for cut in cuts:
        cut_id = cut["cut_id"]
        dur_expected = cut["dur_expected"]
        vo_text = cut["vo_text"]
        cap_text = cut["cap_text"]
        start_t = cumulative_t
        end_t = cumulative_t + dur_expected

        mp3_path = None
        dur_actual = 0.0
        overflow = False

        if vo_text:
            mp3_path = out_dir / f"cut-{cut_id}.mp3"
            try:
                audio = client.text_to_speech.convert(
                    text=vo_text,
                    voice_id=voice_id,
                    model_id=args.model or "eleven_multilingual_v2",
                    output_format="mp3_44100_128",
                )
                with open(mp3_path, "wb") as f:
                    for chunk in audio:
                        f.write(chunk)
                try:
                    res = _subp.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                         "-of", "default=noprint_wrappers=1:nokey=1", str(mp3_path)],
                        capture_output=True, text=True, check=True,
                    )
                    dur_actual = float(res.stdout.strip())
                except Exception:
                    dur_actual = 0.0
                overflow = dur_actual > dur_expected + 0.2
            except Exception as e:
                output({"error": f"VO synthesis failed for cut {cut_id}: {e}"})
                return

        srt_text = vo_text or cap_text
        if srt_text and dur_expected > 0:
            def _ts(t):
                h, rem = divmod(t, 3600)
                m, s = divmod(rem, 60)
                ms = int((s - int(s)) * 1000)
                return f"{int(h):02d}:{int(m):02d}:{int(s):02d},{ms:03d}"
            srt_entries.append(f"{srt_idx}\n{_ts(start_t)} --> {_ts(end_t)}\n{srt_text}\n")
            srt_idx += 1

        timing.append({
            "cut_id": cut_id,
            "start": start_t,
            "end": end_t,
            "dur_expected": dur_expected,
            "dur_actual": dur_actual,
            "overflow_warn": overflow,
            "mp3": str(mp3_path) if mp3_path else None,
            "vo_text": vo_text,
            "cap_text": cap_text,
        })
        cumulative_t = end_t

    (out_dir / "timing.json").write_text(json.dumps({
        "shotlist": str(shotlist_path),
        "voice": voice_arg,
        "voice_id": voice_id,
        "total_duration": cumulative_t,
        "vo_count": sum(1 for t in timing if t["mp3"]),
        "caption_count": sum(1 for t in timing if t["cap_text"]),
        "overflow_count": sum(1 for t in timing if t["overflow_warn"]),
        "cuts": timing,
    }, indent=2))
    (out_dir / "timing.srt").write_text("\n".join(srt_entries))

    output({
        "status": "success",
        "out_dir": str(out_dir),
        "vo_count": sum(1 for t in timing if t['mp3']),
        "caption_count": sum(1 for t in timing if t['cap_text']),
        "overflow_count": sum(1 for t in timing if t['overflow_warn']),
        "total_duration": cumulative_t,
    })


def cmd_delete_voice(args):
    """Delete a cloned voice."""
    client, error = get_client()
    if error:
        output({"error": error})
        return

    if not args.voice_id:
        output({"error": "Voice ID required", "usage": "python3 eleven_labs_skill.py delete-voice VOICE_ID"})
        return

    try:
        client.voices.delete(voice_id=args.voice_id)
        output({"status": "success", "message": f"Voice {args.voice_id} deleted"})
    except Exception as e:
        output({"error": f"Failed to delete voice: {str(e)}"})


def main():
    parser = argparse.ArgumentParser(description="Eleven Labs Voice Generation")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Setup
    setup_parser = subparsers.add_parser("setup", help="Configure API key")
    setup_parser.add_argument("api_key", nargs="?", help="Eleven Labs API key")

    # List voices
    voices_parser = subparsers.add_parser("voices", help="List available voices")
    voices_parser.add_argument("--category", "-c", help="Filter by category (premade, cloned, etc)")

    # Generate speech
    speak_parser = subparsers.add_parser("speak", help="Generate speech from text")
    speak_parser.add_argument("text", nargs="?", help="Text to speak")
    speak_parser.add_argument("--voice", "-v", help="Voice name or ID")
    speak_parser.add_argument("--model", "-m", help="Model to use")
    speak_parser.add_argument("--file", "-f", help="Read text from file")

    # Clone voice
    clone_parser = subparsers.add_parser("clone", help="Clone a voice from audio samples")
    clone_parser.add_argument("name", nargs="?", help="Name for the cloned voice")
    clone_parser.add_argument("files", nargs="*", help="Audio files to use for cloning")
    clone_parser.add_argument("--description", "-d", help="Voice description")

    # Sound effects
    sfx_parser = subparsers.add_parser("sfx", help="Generate sound effects")
    sfx_parser.add_argument("description", nargs="?", help="Description of the sound effect")
    sfx_parser.add_argument("--duration", "-d", type=float, default=5.0, help="Duration in seconds")

    # List models
    subparsers.add_parser("models", help="List available models")

    # History
    history_parser = subparsers.add_parser("history", help="Get generation history")
    history_parser.add_argument("--limit", "-l", type=int, default=20, help="Number of items")

    # Delete voice
    delete_parser = subparsers.add_parser("delete-voice", help="Delete a cloned voice")
    delete_parser.add_argument("voice_id", nargs="?", help="Voice ID to delete")

    # Sync: shot-list → VO MP3s + SRT
    sync_parser = subparsers.add_parser("sync", help="Parse shot-list MD → per-cut MP3s + timing.srt")
    sync_parser.add_argument("--shotlist", required=False, help="Path to shot-list markdown")
    sync_parser.add_argument("--voice", default="adam", help="Voice preset (adam|daniel|rachel|antoni) or raw voice_id")
    sync_parser.add_argument("--model", default="eleven_multilingual_v2", help="ElevenLabs model")
    sync_parser.add_argument("--out", help="Output dir (default ~/Downloads/eleven-labs-sync/<basename>/)")
    sync_parser.add_argument("--dry-run", action="store_true", help="Parse only; don't synthesize")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    commands = {
        "setup": cmd_setup,
        "voices": cmd_voices,
        "speak": cmd_speak,
        "clone": cmd_clone,
        "sfx": cmd_sfx,
        "models": cmd_models,
        "history": cmd_history,
        "delete-voice": cmd_delete_voice,
        "sync": cmd_sync,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
