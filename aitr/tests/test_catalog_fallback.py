"""Tests for catalog fallback chain: live → cache → stale → snapshot → exit 3."""
import json
import time
from pathlib import Path

import pytest

import catalog
from catalog import (
    CatalogUnavailable,
    load_catalog,
    load_routing_table,
)


SAMPLE_BODY = {
    "generated_at": "2026-06-01T00:00:00Z",
    "models": [
        {"id": "test__alpha", "provider": "test", "status": "ga",
         "context_window": 200000, "modalities": ["text"],
         "pricing": {"input_per_mtok": 1, "output_per_mtok": 5},
         "tags": ["test"]}
    ],
}


def _fake_fetcher_ok(url, timeout):
    return SAMPLE_BODY


def _fake_fetcher_503(url, timeout):
    raise CatalogUnavailable("upstream returned HTTP 503")


def _fake_fetcher_oserror(url, timeout):
    raise ConnectionError("dns resolution failed")


class TestCatalogFallback:
    def test_live_fetch_writes_cache(self, tmp_path):
        src = load_catalog(
            tracker_origin="https://t.example.com",
            cache_dir=tmp_path,
            fetcher=_fake_fetcher_ok,
        )
        assert src.source == "live"
        assert (tmp_path / "search.json").exists()
        cached = json.loads((tmp_path / "search.json").read_text())
        assert cached == SAMPLE_BODY

    def test_fresh_cache_served_without_refetch(self, tmp_path):
        cache_file = tmp_path / "search.json"
        cache_file.write_text(json.dumps(SAMPLE_BODY))
        # Override mtime to recent
        recent = time.time() - 60  # 1 minute ago
        import os
        os.utime(cache_file, (recent, recent))

        call_count = {"n": 0}
        def counting_fetcher(url, timeout):
            call_count["n"] += 1
            return SAMPLE_BODY

        src = load_catalog(
            tracker_origin="https://t.example.com",
            cache_dir=tmp_path,
            fetcher=counting_fetcher,
        )
        assert src.source == "cache"
        assert call_count["n"] == 0

    def test_stale_cache_when_live_fails(self, tmp_path):
        cache_file = tmp_path / "search.json"
        cache_file.write_text(json.dumps(SAMPLE_BODY))
        # Stale: 1 day ago
        import os
        old = time.time() - 86400
        os.utime(cache_file, (old, old))

        src = load_catalog(
            tracker_origin="https://t.example.com",
            cache_dir=tmp_path,
            ttl_seconds=60,
            fetcher=_fake_fetcher_503,
        )
        assert src.source == "stale-cache"
        assert src.body == SAMPLE_BODY

    def test_bundled_snapshot_when_no_cache(self, tmp_path):
        src = load_catalog(
            tracker_origin="https://t.example.com",
            cache_dir=tmp_path,
            fetcher=_fake_fetcher_503,
        )
        assert src.source == "snapshot"
        assert "models" in src.body
        # Bundled snapshot has at least the canonical models
        ids = {m["id"] for m in src.body["models"]}
        assert "anthropic__claude-opus-4-7" in ids

    def test_offline_skips_live(self, tmp_path):
        # cache is empty; offline=True should NOT hit live, should fall through to snapshot
        call_count = {"n": 0}
        def counting_fetcher(url, timeout):
            call_count["n"] += 1
            return SAMPLE_BODY

        src = load_catalog(
            tracker_origin="https://t.example.com",
            cache_dir=tmp_path,
            offline=True,
            fetcher=counting_fetcher,
        )
        assert call_count["n"] == 0
        assert src.source == "snapshot"

    def test_force_refresh_bypasses_fresh_cache(self, tmp_path):
        cache_file = tmp_path / "search.json"
        cache_file.write_text(json.dumps({"models": [], "ts": "old"}))
        import os
        recent = time.time() - 60
        os.utime(cache_file, (recent, recent))

        call_count = {"n": 0}
        def counting_fetcher(url, timeout):
            call_count["n"] += 1
            return SAMPLE_BODY

        src = load_catalog(
            tracker_origin="https://t.example.com",
            cache_dir=tmp_path,
            fetcher=counting_fetcher,
            force_refresh=True,
        )
        assert call_count["n"] == 1
        assert src.source == "live"

    def test_fail_loud_when_everything_missing(self, tmp_path, monkeypatch):
        # Move the bundled snapshot out of the way
        from catalog import BUNDLED_SNAPSHOT
        monkeypatch.setattr(catalog, "BUNDLED_SNAPSHOT", Path("/nonexistent/snapshot.json"))

        with pytest.raises(CatalogUnavailable, match="no live, no cache, no bundled snapshot"):
            load_catalog(
                tracker_origin="https://t.example.com",
                cache_dir=tmp_path,
                fetcher=_fake_fetcher_oserror,
            )

    def test_routing_table_loads(self):
        rt = load_routing_table()
        assert "task_kinds" in rt
        assert "code-review" in rt["task_kinds"]
        assert rt["task_kinds"]["code-review"]["latency_class"] == "medium"
        assert rt["composite_weights"]["capability"] == 0.5
