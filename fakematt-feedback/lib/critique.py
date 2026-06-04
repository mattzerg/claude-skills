"""Critique pipeline: take captures + cached corpora, emit structured findings.

Uses the Anthropic SDK directly with prompt caching. The voice + principles
blocks are stable across pages within a run, so they go in `cache_control` —
this gives us ~10× cost reduction and ~10s/call latency reduction once warm.

Two reasons we moved off the `claude --print` CLI subprocess:
1. The CLI doesn't support cache breakpoints, so the 40K-char two-layer prompt
   was being re-billed and re-processed for every page.
2. Long context + the CLI's output buffering caused critique calls to hang
   indefinitely (observed: 35-min stalled subprocesses). The SDK has proper
   timeout + streaming we can rely on.

Voice direction (per `feedback_fakematt_feedback_voice.md`): the output
register is professional/technical/structured, NOT a Matt-voice cosplay.
The corpus is a coverage map (what to look for), not a style guide.
"""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Any

DEFAULT_MODEL = "claude-sonnet-4-5"  # loud fallback when aitr unavailable
DEFAULT_MAX_TOKENS = 8000  # was 4000; observed truncation mid-finding on rich pages

_AITR_SCRIPTS = Path.home() / ".claude" / "skills" / "aitr" / "scripts"
_routed_model_cache: str | None = None


def _routed_default_model() -> str:
    """UX critique sends page screenshots → needs vision. prose-review/medium.
    Loud fallback to DEFAULT_MODEL; memoized for multi-page runs."""
    global _routed_model_cache
    if _routed_model_cache is None:
        if str(_AITR_SCRIPTS) not in sys.path:
            sys.path.insert(0, str(_AITR_SCRIPTS))
        try:
            from skill_default import aitr_model_or
            _routed_model_cache = aitr_model_or(
                DEFAULT_MODEL, task_kind="prose-review", caller="fakematt-feedback",
                quality_floor="medium", modality_required="vision",
            )
        except ImportError:
            _routed_model_cache = DEFAULT_MODEL
    return _routed_model_cache

# Token budget: each PNG screenshot is ~1.5K tokens. We send up to 4 images
# per page (desktop, tablet, +1 interaction before/after pair). At 8 pages
# that's ~48K tokens of images per run. Acceptable.
MAX_IMAGE_BYTES = 5_000_000  # 5MB cap (post-downscale); Anthropic limit is 5MB
MAX_IMAGE_DIMENSION = 7500    # Anthropic vision rejects >8000px; leave headroom


def _image_block(path: str | None) -> dict | None:
    """Return an Anthropic content block for an image file, or None if the
    file doesn't exist / fails to read.

    Auto-downscales images that exceed Anthropic's 8000px dimension limit
    (full-page screenshots of long pages frequently bust this). Re-encodes as
    PNG bytes only if the source needed resizing — small images pass through
    untouched at byte-level fidelity. Fixes the "image dimensions exceed max
    allowed size: 8000 pixels" 400 error observed on matteisn.com 2026-05-09.
    """
    if not path:
        return None
    p = Path(path)
    if not p.exists() or not p.is_file():
        return None
    try:
        # Cheap dimension peek — if both axes are within bounds, raw bytes pass through.
        from PIL import Image  # lazy import — only loaded when an image is processed
        with Image.open(p) as im:
            w, h = im.size
            needs_resize = w > MAX_IMAGE_DIMENSION or h > MAX_IMAGE_DIMENSION

            if not needs_resize:
                size = p.stat().st_size
                if size <= MAX_IMAGE_BYTES:
                    data = base64.b64encode(p.read_bytes()).decode("ascii")
                    return {
                        "type": "image",
                        "source": {"type": "base64", "media_type": "image/png", "data": data},
                    }
                # Fallthrough to re-encode + downscale path

            # Compute target dims preserving aspect ratio
            scale = min(MAX_IMAGE_DIMENSION / w, MAX_IMAGE_DIMENSION / h, 1.0)
            new_w = int(w * scale)
            new_h = int(h * scale)
            resized = im.resize((new_w, new_h), Image.LANCZOS) if scale < 1.0 else im.copy()

            # Encode to PNG buffer — try progressively heavier compression if still over byte cap
            import io
            buf = io.BytesIO()
            if resized.mode not in ("RGB", "RGBA"):
                resized = resized.convert("RGB")
            resized.save(buf, "PNG", optimize=True)
            png_bytes = buf.getvalue()

            # If PNG still too big, fall back to JPEG (loses transparency but fine for screenshots)
            media_type = "image/png"
            if len(png_bytes) > MAX_IMAGE_BYTES:
                buf = io.BytesIO()
                rgb = resized.convert("RGB") if resized.mode != "RGB" else resized
                rgb.save(buf, "JPEG", quality=85, optimize=True)
                png_bytes = buf.getvalue()
                media_type = "image/jpeg"
                # If still too big, drop quality further
                if len(png_bytes) > MAX_IMAGE_BYTES:
                    buf = io.BytesIO()
                    rgb.save(buf, "JPEG", quality=70, optimize=True)
                    png_bytes = buf.getvalue()
                if len(png_bytes) > MAX_IMAGE_BYTES:
                    return None  # give up — caller treats as "no image"

            data = base64.b64encode(png_bytes).decode("ascii")
            return {
                "type": "image",
                "source": {"type": "base64", "media_type": media_type, "data": data},
            }
    except ImportError:
        # Pillow not available — fall back to raw byte path with size check only.
        # Will fail loudly on >8000px images, but that's same as before this fix.
        try:
            size = p.stat().st_size
            if size > MAX_IMAGE_BYTES:
                return None
            data = base64.b64encode(p.read_bytes()).decode("ascii")
            return {
                "type": "image",
                "source": {"type": "base64", "media_type": "image/png", "data": data},
            }
        except Exception:
            return None
    except Exception:
        return None


CRITIQUE_INSTRUCTION = """You are producing a structured product/UX review of a web page.

Your output should read like a senior front-end engineer's UX audit — professional, technical, structured, and objective. Do NOT mimic the rhetorical style of the corpus quotes; the corpus is a coverage map of what to look for, not a style guide. Avoid first-person hedges, ALL-CAPS escalation, "stated but never shown" / "table stakes" / "credibility crater" / similar rhetorical moves. Just produce clean structured findings.

Coverage goals (use the VOICE corpus to ensure you cover what Matt would, then go beyond):
- Visible bugs / inconsistencies (e.g. one record formatted differently from the others, debug strings leaking into the UI)
- Information architecture (label clarity, redundant navigation, broken hierarchy)
- Responsive/layout behavior (signs of overflow, whitespace imbalance, column-width problems — call out probable behaviors at 768/1024/1440 widths even if you only have desktop+mobile screenshots)
- Interactive affordances (sortable headers, hover menus, click-to-expand) — flag both missing affordances and existing-but-unclear ones
- Copy / labels (ambiguity, missing units, raw timestamps, untranslated developer fields)
- Empty states (passive vs teaching, what to do next)
- Typography polish (sizing hierarchy, orphan/widow rules, contrast)
- Accessibility (axe violations from payload, plus visible issues like contrast, focus order)
- Additive features ("similar tools have X — should we add Y?") — this is a real mode of feedback, not a critique-only mode

Two output modes per page (mix freely): WHAT'S BROKEN and WHAT TO ADD. Both are valid finding categories.

Per-finding requirements:
1. `principle_provenance`: cite at least one principle_id from the principles library.
2. `voice_provenance`: cite a quote_id from the voice corpus IF the concern category aligns; if not, omit (set to null). Voice citation is no longer mandatory — the corpus is for coverage, not style.
3. `severity`: P0 (blocks core use, breaks trust, or directly costs money), P1 (real friction or inconsistency that hurts daily use), P2 (polish).
4. `category`: one of consistency|copy|ia|responsive|interaction|empty_state|typography|accessibility|positioning|cta|friction|ux|polish|technical|additive_feature.
5. `mode`: "broken" | "additive". Use "additive" for "should we add X" findings.
6. `finding`: 2-3 sentences. Plain technical English. No rhetorical flourishes.
7. `suggested_fix`: concrete, specific, implementable. Where possible, give a precise interaction spec ("toggle button whose label changes from 'Managers Only' to 'All Employees' on click") not just an abstraction.
8. `target_kind_relevance`: if the finding only matters for a specific target kind (e.g. positioning copy on a marketing page, but not on an internal tool), say so here. Internal tools should NOT receive marketing-CRO critique.
9. `role_assumption`: if the finding depends on the viewer's permission level, name it (e.g. "applies to end-users; super-admins see edit controls correctly").

Return ONLY a JSON array of findings (no preface, no markdown fence). Target 6-12 findings per page covering broad surface area. Skip findings you can't ground in a principle.

Schema per finding:
{
  "finding_id": "f-XXXX",
  "severity": "P0|P1|P2",
  "category": "...",
  "mode": "broken|additive",
  "location": {"url": "...", "selector": "<best css/text selector>", "screenshot": "<screenshot_desktop path from payload>"},
  "finding": "...",
  "suggested_fix": "...",
  "voice_provenance": "q-XXXX or null",
  "principle_provenance": ["p-XXXX", ...],
  "target_kind_relevance": "<short note or null>",
  "role_assumption": "<short note or null>"
}
"""


def _build_system_blocks(
    voice_block: str,
    principles_block: str,
    persona: str | None,
    target_kind: str | None,
) -> list[dict]:
    """Two cache breakpoints: voice corpus + principles library. Both are stable
    across all pages in a run; the per-page payload goes in the user message.

    Cache hit on the second page onward = ~90% token cost reduction on the
    cached prefix.
    """
    context_lines = []
    if persona:
        context_lines.append(f"VIEWER ROLE: {persona}. Do NOT flag controls that are correct for this role (e.g. don't flag edit buttons as a problem if the viewer is a super-admin).")
    if target_kind:
        context_lines.append(f"TARGET KIND: {target_kind}. Apply the evaluation rubric for this kind. Internal tools / dashboards should NOT receive marketing-CRO critique (no 'value prop missing', no 'social proof absent', no 'CTA friction' findings unless directly relevant).")
    context_block = "\n".join(context_lines) or "VIEWER ROLE: not specified. TARGET KIND: not specified — treat as a general web product."

    return [
        {
            "type": "text",
            "text": "# CONTEXT\n\n" + context_block,
        },
        {
            "type": "text",
            "text": "# VOICE COVERAGE MAP\n\n_Use this to know what Matt would surface. Do NOT mimic its register in your output._\n\n" + voice_block,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": "# PRINCIPLES LIBRARY\n\n" + principles_block,
            "cache_control": {"type": "ephemeral"},
        },
        {
            "type": "text",
            "text": "# TASK\n\n" + CRITIQUE_INSTRUCTION,
        },
    ]


def _extract_json_array(raw: str) -> list[dict]:
    """Extract a JSON array from model output, tolerating two failure modes:
    1. The output is wrapped in a markdown code fence (```json ... ```).
    2. The output was truncated mid-object (stop_reason=max_tokens). In that
       case, find the array opening, walk forward parsing complete objects
       one at a time, and return what we got.
    """
    import re
    raw = re.sub(r"^```(?:json)?\n?", "", raw.strip())
    raw = re.sub(r"\n?```$", "", raw)
    first = raw.find("[")
    if first == -1:
        return []
    last = raw.rfind("]")
    # Try the clean parse first
    if last > first:
        try:
            result = json.loads(raw[first : last + 1])
            if isinstance(result, list):
                return result
        except json.JSONDecodeError:
            pass
    # Fallback: incremental object-by-object parse to recover partial output
    decoder = json.JSONDecoder()
    pos = first + 1  # skip the opening [
    out: list[dict] = []
    while pos < len(raw):
        # Skip whitespace and commas between objects
        while pos < len(raw) and raw[pos] in " \t\r\n,":
            pos += 1
        if pos >= len(raw) or raw[pos] != "{":
            break
        try:
            obj, end = decoder.raw_decode(raw, pos)
        except json.JSONDecodeError:
            break  # truncated mid-object — stop here, keep what we have
        if isinstance(obj, dict):
            out.append(obj)
        pos = end
    return out


def critique_page(
    voice_block: str,
    principles_block: str,
    page_payload: dict,
    *,
    model: str | None = None,
    timeout: int = 180,
    persona: str | None = None,
    target_kind: str | None = None,
) -> list[dict]:
    """One critique call per page. Returns list of finding dicts.

    Uses Anthropic SDK with prompt caching. Falls back to subprocess CLI
    if SDK not available or ANTHROPIC_API_KEY is missing.
    """
    if model is None:
        model = _routed_default_model()
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _sys.path.insert(0, str(_Path.home() / ".config" / "zerg"))
        from anthropic_client import make_client
    except ImportError:
        return _critique_via_cli_fallback(voice_block, principles_block, page_payload, model=model, timeout=timeout, persona=persona, target_kind=target_kind)

    api_key = os.environ.get("ANTHROPIC_API_KEY") or _read_api_key_from_config()
    if not api_key:
        return _critique_via_cli_fallback(voice_block, principles_block, page_payload, model=model, timeout=timeout, persona=persona, target_kind=target_kind)

    system_blocks = _build_system_blocks(voice_block, principles_block, persona, target_kind)

    # Build user message as a content array: desktop image + optional tablet
    # image + optional interaction before/after pair + payload text. Giving
    # the model actual visual access to the page is the biggest single
    # quality lever — text-only payload misses contrast, tiny-text-on-org-
    # chart, button-vs-label mismatches, and any visual hierarchy issue.
    content: list[dict] = []

    screenshots = page_payload.get("screenshots") or {}
    desktop_path = screenshots.get("desktop") or page_payload.get("screenshot_desktop")
    tablet_path = screenshots.get("tablet")

    desktop_block = _image_block(desktop_path)
    if desktop_block:
        content.append({"type": "text", "text": "## DESKTOP VIEW (1440×900)\n"})
        content.append(desktop_block)
    tablet_block = _image_block(tablet_path)
    if tablet_block:
        content.append({"type": "text", "text": "\n## TABLET VIEW (768×1024)\n"})
        content.append(tablet_block)

    interactions = page_payload.get("interactions") or []
    # Attach the first valid interaction pair (before+after) so the model
    # can see what one click actually does. Skip oversized or errored items.
    for interaction in interactions:
        if interaction.get("error"):
            continue
        before_block = _image_block(interaction.get("before"))
        after_block = _image_block(interaction.get("after"))
        if before_block and after_block:
            label = interaction.get("label") or interaction.get("kind") or "interaction"
            content.append({"type": "text", "text": f"\n## INTERACTION: {label}\nBEFORE:\n"})
            content.append(before_block)
            content.append({"type": "text", "text": "AFTER:\n"})
            content.append(after_block)
            break  # one interaction pair per page is enough

    # Strip the b64 image data from the JSON payload so it's not duplicated
    payload_text = page_payload.copy() if isinstance(page_payload, dict) else dict(page_payload)
    payload_text.pop("screenshots", None)  # already attached as images
    content.append({
        "type": "text",
        "text": (
            "\n## STRUCTURED PAGE PAYLOAD\n\n```json\n"
            + json.dumps(payload_text, indent=2)
            + "\n```\n\nReturn the JSON array of findings now. Use the visual evidence above (screenshots and interaction state-changes) alongside the structured payload to inform every finding."
        ),
    })

    # 429-aware retry with exponential backoff + jitter. Skip-mode
    # (ANTHROPIC_429_SKIP_MODE=1) returns a sentinel finding instead of
    # crashing the per-page critique loop — `validate_findings` already
    # routes `_error` items to the rejected list, so the marker flows
    # through to the report without poisoning kept findings. See
    # ~/.config/zerg/anthropic_retry.py + feedback_429_skill_hardening.md.
    try:
        import sys as _sys
        from pathlib import Path as _Path
        _sys.path.insert(0, str(_Path.home() / ".config" / "zerg"))
        from anthropic_retry import call_with_429_retry, is_429_skip_sentinel, SKIP_MARKER_TEXT
    except ImportError:
        call_with_429_retry = None  # type: ignore[assignment]
        is_429_skip_sentinel = None  # type: ignore[assignment]
        SKIP_MARKER_TEXT = "[SKIPPED 429 after {attempts} retries]"

    try:
        # `anthropic_client.make_client` only accepts `source`; older callers
        # passed api_key/timeout but the reconstructed-2026-05-12 module
        # doesn't accept them. Pass only `source` and set timeout via
        # client.with_options() if needed. api_key is honored via env var
        # (already loaded above) for the API-key fallback path.
        client = make_client(source="fakematt-feedback")
        if timeout:
            try:
                client = client.with_options(timeout=timeout)
            except Exception:
                pass  # SDK version without with_options — request-level timeout fallback below

        def _do_call():
            return client.messages.create(
                model=model,
                max_tokens=DEFAULT_MAX_TOKENS,
                system=system_blocks,
                messages=[{"role": "user", "content": content}],
            )

        if call_with_429_retry is not None:
            resp = call_with_429_retry(_do_call, source="fakematt-feedback/critique", max_attempts=4)
            if is_429_skip_sentinel is not None and is_429_skip_sentinel(resp):
                attempts = resp.get("_attempts", 4)
                return [{
                    "_error": SKIP_MARKER_TEXT.format(attempts=attempts),
                    "_429_skipped": True,
                    "_attempts": attempts,
                }]
        else:
            resp = _do_call()

        text = "".join(b.text for b in resp.content if hasattr(b, "text"))
        return _extract_json_array(text)
    except Exception as exc:
        return [{"_error": f"sdk: {str(exc)[:300]}"}]


def _read_api_key_from_config() -> str | None:
    """Resolve ANTHROPIC_API_KEY from (in order): env var, macOS Keychain via
    `security find-generic-password`, or legacy JSON config files.

    Keychain is the canonical path per `feedback_api_keys_via_keychain.md` —
    `.zshrc` sources `~/.config/zerg/load_anthropic_key.sh` for interactive
    shells, but cron daemons + nohup-launched processes don't get that, so we
    shell out to `security` directly here. Same service name (`anthropic-api-key`)
    and account (`matteisn`) the loader uses.
    """
    # Already in env (interactive shell with .zshrc loaded, or explicit export)
    env_val = os.environ.get("ANTHROPIC_API_KEY")
    if env_val:
        return env_val
    # macOS Keychain — works in any process context
    try:
        import subprocess
        result = subprocess.run(
            ["security", "find-generic-password", "-a", "matteisn", "-s", "anthropic-api-key", "-w"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            key = result.stdout.strip()
            if key:
                return key
    except Exception:
        pass
    # Legacy fallback — JSON files (kept for back-compat; not the canonical path)
    candidates = [
        Path.home() / ".claude" / "anthropic.json",
        Path.home() / ".anthropic" / "config.json",
    ]
    for p in candidates:
        if p.exists():
            try:
                cfg = json.loads(p.read_text())
                if "api_key" in cfg:
                    return cfg["api_key"]
            except Exception:
                continue
    return None


def _critique_via_cli_fallback(
    voice_block: str,
    principles_block: str,
    page_payload: dict,
    *,
    model: str,
    timeout: int,
    persona: str | None,
    target_kind: str | None,
) -> list[dict]:
    """Last-resort CLI path. Discouraged: no caching, susceptible to subprocess
    hangs we observed in practice. Kept as a no-API-key fallback only.
    """
    import subprocess
    CLAUDE_BIN = str(Path.home() / ".local" / "bin" / "claude")
    context_block = ""
    if persona:
        context_block += f"VIEWER ROLE: {persona}.\n"
    if target_kind:
        context_block += f"TARGET KIND: {target_kind}.\n"
    prompt = (
        "## CONTEXT\n\n" + (context_block or "(no role/kind specified)\n")
        + "\n## VOICE COVERAGE MAP\n\n" + voice_block
        + "\n\n## PRINCIPLES LIBRARY\n\n" + principles_block
        + "\n\n## TASK\n\n" + CRITIQUE_INSTRUCTION
        + "\n\n## PAGE PAYLOAD\n\n```json\n"
        + json.dumps(page_payload, indent=2)
        + "\n```\n"
    )
    try:
        result = subprocess.run(
            [CLAUDE_BIN, "--print", "--model", model, "--tools", ""],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return [{"_error": f"cli timeout after {timeout}s"}]
    if result.returncode != 0:
        return [{"_error": f"cli: {result.stderr.strip()[:300]}"}]
    return _extract_json_array(result.stdout)


def validate_findings(findings: list[dict], voice_quote_ids: set[str], principle_ids: set[str]) -> tuple[list[dict], list[dict]]:
    """Split into (kept, rejected_with_reason). Voice citation is now optional
    (per voice-direction calibration); principle citation is still required.

    Findings missing principle citation are rejected.
    Findings without voice citation are kept (no opinion_only flag — coverage
    over voice is the whole point now).
    """
    kept: list[dict] = []
    rejected: list[dict] = []
    for i, f in enumerate(findings):
        if "_error" in f:
            rejected.append({"reason": "model_error", "finding": f})
            continue
        pps = f.get("principle_provenance") or []
        if isinstance(pps, str):
            pps = [pps]
        p_ok = any(p in principle_ids for p in pps)
        if not p_ok:
            rejected.append({"reason": "no_principle", "finding": f})
            continue
        # Re-ID for stability
        f.setdefault("finding_id", f"f-{i+1:04d}")
        # Optional voice citation, no opinion_only flag anymore
        kept.append(f)
    return kept, rejected
