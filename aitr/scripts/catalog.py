"""Catalog loader for aitr.

Fallback chain when loading the model catalog:
  1. Live HTTP fetch of `${tracker_origin}/api/search.json` (configurable)
  2. Local cache at `~/.cache/zerg/aitr/search.json` (1h TTL by default)
  3. Stale cache (any age) with warning to stderr
  4. Bundled snapshot at `<skill>/data/snapshot/search.json`
  5. Raise CatalogUnavailable (caller should exit 3 — fail loud)

Per-model detail (`/models/<id>.json`) cached for 24h at
`~/.cache/zerg/aitr/models/<id>.json`.

No third-party deps. Uses urllib (stdlib) for HTTP.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
import urllib.error
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple


SKILL_ROOT = Path(__file__).resolve().parent.parent
BUNDLED_SNAPSHOT = SKILL_ROOT / "data" / "snapshot" / "search.json"
BUNDLED_MODELS_DIR = SKILL_ROOT / "data" / "snapshot" / "models"

DEFAULT_TRACKER_ORIGIN = "https://zergai.com/resources/ai-tool-tracker"
DEFAULT_CACHE_DIR = Path.home() / ".cache" / "zerg" / "aitr"
DEFAULT_CATALOG_TTL_SECONDS = 60 * 60  # 1h
DEFAULT_MODEL_TTL_SECONDS = 24 * 60 * 60  # 24h
DEFAULT_HTTP_TIMEOUT = 8.0


class CatalogUnavailable(Exception):
    """Raised when no catalog source can be loaded — caller MUST fail loud."""


@dataclass(frozen=True)
class CatalogSource:
    body: dict
    source: str  # "live" | "cache" | "stale-cache" | "snapshot"
    fetched_at: float


def _load_config() -> dict:
    """Read ~/.config/zerg/aitr.toml if present. Returns {} if missing or unparseable.
    Uses tomllib (3.11+) when available; fall back to a minimal key=value parser
    otherwise so the skill still works on older interpreters.
    """
    cfg_path = Path.home() / ".config" / "zerg" / "aitr.toml"
    if not cfg_path.exists():
        return {}
    try:
        import tomllib  # py3.11+
        return tomllib.loads(cfg_path.read_text(encoding="utf-8"))
    except ImportError:
        pass
    except Exception:
        return {}
    # Minimal fallback parser: `key = "value"` lines, ignores tables.
    out: dict = {}
    try:
        for raw in cfg_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or line.startswith("["):
                continue
            if "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            out[k] = v
    except Exception:
        return {}
    return out


def resolve_tracker_origin() -> str:
    """Pick the tracker origin: env > config > default."""
    env_value = os.environ.get("TRACKER_ORIGIN") or os.environ.get("AITR_TRACKER_ORIGIN")
    if env_value:
        return env_value.rstrip("/")
    cfg = _load_config()
    cfg_value = cfg.get("tracker_origin")
    if cfg_value:
        return str(cfg_value).rstrip("/")
    return DEFAULT_TRACKER_ORIGIN


def resolve_cache_dir() -> Path:
    cfg = _load_config()
    cfg_value = cfg.get("cache_dir")
    if cfg_value:
        return Path(os.path.expanduser(str(cfg_value)))
    return DEFAULT_CACHE_DIR


def _http_get_json(url: str, timeout: float = DEFAULT_HTTP_TIMEOUT) -> dict:
    req = urllib.request.Request(url, headers={"Accept": "application/json", "User-Agent": "aitr/0.1"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        # file:// responses report status None (urllib addinfourl); only HTTP(S)
        # responses carry a real status code. This lets tracker_origin point at a
        # local export dir (file:///path/to/aitr-export) for fully-offline routing.
        status = getattr(resp, "status", None)
        if status is not None and status != 200:
            raise CatalogUnavailable(f"upstream returned HTTP {status} for {url}")
        body = resp.read().decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError as exc:
        raise CatalogUnavailable(f"upstream returned non-JSON for {url}: {exc}") from exc


def _write_cache_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data), encoding="utf-8")
    os.replace(tmp, path)


def _read_cache(path: Path, ttl_seconds: int) -> Optional[Tuple[dict, bool]]:
    """Return (body, fresh) where fresh=True if within TTL, False if stale.
    Returns None if cache file missing or unreadable."""
    if not path.exists():
        return None
    try:
        age = time.time() - path.stat().st_mtime
        body = json.loads(path.read_text(encoding="utf-8"))
        return body, age <= ttl_seconds
    except Exception:
        return None


def load_catalog(
    *,
    tracker_origin: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    ttl_seconds: int = DEFAULT_CATALOG_TTL_SECONDS,
    timeout: float = DEFAULT_HTTP_TIMEOUT,
    force_refresh: bool = False,
    offline: bool = False,
    fetcher=None,
) -> CatalogSource:
    """Load the catalog using the fallback chain.

    `fetcher` lets tests inject a fake HTTP getter with the same signature as
    `_http_get_json(url, timeout)`.
    """
    origin = (tracker_origin or resolve_tracker_origin()).rstrip("/")
    cache_dir = cache_dir or resolve_cache_dir()
    cache_path = cache_dir / "search.json"
    fetch = fetcher or _http_get_json

    # Step 1: live fetch (unless offline)
    if not offline:
        # Honor a fresh cache UNLESS force_refresh demands a network hop
        if not force_refresh:
            cached = _read_cache(cache_path, ttl_seconds)
            if cached:
                body, fresh = cached
                if fresh:
                    return CatalogSource(body=body, source="cache", fetched_at=time.time())
        url = f"{origin}/api/search.json"
        try:
            body = fetch(url, timeout)
            try:
                _write_cache_atomic(cache_path, body)
            except OSError as exc:
                print(f"aitr: failed to write cache {cache_path}: {exc}", file=sys.stderr)
            return CatalogSource(body=body, source="live", fetched_at=time.time())
        except (CatalogUnavailable, urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            print(f"aitr: live catalog fetch failed ({exc}); falling back to cache/snapshot", file=sys.stderr)

    # Step 2/3: stale cache (any age, with warning). Use the caller's actual
    # ttl_seconds so a not-yet-expired cache returns source="cache", and only
    # truly stale entries are flagged as such.
    cached = _read_cache(cache_path, ttl_seconds=ttl_seconds)
    if cached:
        body, fresh = cached
        if fresh:
            return CatalogSource(body=body, source="cache", fetched_at=time.time())
        print(f"aitr: serving stale catalog from {cache_path}", file=sys.stderr)
        return CatalogSource(body=body, source="stale-cache", fetched_at=time.time())

    # Step 4: bundled snapshot
    if BUNDLED_SNAPSHOT.exists():
        try:
            body = json.loads(BUNDLED_SNAPSHOT.read_text(encoding="utf-8"))
            print(f"aitr: serving bundled snapshot ({BUNDLED_SNAPSHOT})", file=sys.stderr)
            return CatalogSource(body=body, source="snapshot", fetched_at=time.time())
        except Exception as exc:
            print(f"aitr: bundled snapshot unreadable: {exc}", file=sys.stderr)

    # Step 5: fail loud
    raise CatalogUnavailable(
        "aitr: catalog unreachable — no live, no cache, no bundled snapshot. "
        "Caller must NOT silently default to a model."
    )


def load_model_detail(
    model_id: str,
    *,
    tracker_origin: Optional[str] = None,
    cache_dir: Optional[Path] = None,
    ttl_seconds: int = DEFAULT_MODEL_TTL_SECONDS,
    fetcher=None,
) -> Optional[dict]:
    """Fetch per-model detail; returns None if everything fails (not loud — detail is optional)."""
    origin = (tracker_origin or resolve_tracker_origin()).rstrip("/")
    cache_dir = cache_dir or resolve_cache_dir()
    cache_path = cache_dir / "models" / f"{model_id}.json"
    fetch = fetcher or _http_get_json

    cached = _read_cache(cache_path, ttl_seconds)
    if cached:
        body, fresh = cached
        if fresh:
            return body

    url = f"{origin}/models/{model_id}.json"
    try:
        body = fetch(url, DEFAULT_HTTP_TIMEOUT)
        _write_cache_atomic(cache_path, body)
        return body
    except Exception:
        pass

    # Stale cache
    cached = _read_cache(cache_path, ttl_seconds=10**12)
    if cached:
        return cached[0]

    # Bundled
    bundled = BUNDLED_MODELS_DIR / f"{model_id}.json"
    if bundled.exists():
        try:
            return json.loads(bundled.read_text(encoding="utf-8"))
        except Exception:
            return None

    return None


def load_routing_table() -> dict:
    """Read data/routing_table.json — pure JSON to avoid YAML parser dependency
    and edge-case bugs. The file is still human-editable and well-documented."""
    path = SKILL_ROOT / "data" / "routing_table.json"
    return json.loads(path.read_text(encoding="utf-8"))
