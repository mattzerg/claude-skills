"""Read + expose the wizard config at ../config.json.

Single source of truth for stage-1..7 preferences. Every consumer (compare.py,
rank.py, cards.py, report.py) reads from here so we never re-derive defaults.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CONFIG_PATH = Path(__file__).resolve().parent.parent / "config.json"


@lru_cache(maxsize=1)
def load() -> dict:
    if not CONFIG_PATH.exists():
        return {}
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def stage(name: str) -> dict:
    return load().get(name, {}) or {}


# ----- stage 2: ranking -----

def bucket_threshold_table_stakes() -> float:
    pct = stage("stage_2_ranking").get("table_stakes_threshold_pct", 60)
    return pct / 100.0


def bucket_threshold_parity_lower() -> float:
    pct = stage("stage_2_ranking").get("differentiator_parity_lower_pct", 25)
    return pct / 100.0


def partial_presence_weight() -> float:
    return float(stage("stage_2_ranking").get("partial_presence_weight", 1.0))


def l_cost_cap_hard() -> bool:
    return stage("stage_2_ranking").get("l_cost_cap") == "hard_no_top10"


def batch_default_fit() -> int:
    return int(stage("stage_2_ranking").get("batch_default_fit", 3))


def batch_default_cost() -> str:
    return str(stage("stage_2_ranking").get("batch_default_cost", "M")).upper()


# ----- stage 3: report shape -----

def positioning_format() -> str:
    return str(stage("stage_3_report").get("positioning_format", "single_file"))


def positioning_short_filename() -> str:
    return str(stage("stage_3_report").get("positioning_short_filename", "positioning.md"))


def positioning_deep_filename() -> str:
    return str(stage("stage_3_report").get("positioning_deep_filename", "positioning-deep.md"))


def index_lead_section() -> str:
    return str(stage("stage_3_report").get("index_lead_section", "at_a_glance_counts"))


# ----- stage 5: card creation -----

def card_creation_paused() -> bool:
    return stage("stage_5_delivery").get("card_creation_mode") == "PAUSED_revisit_later"


def auto_create_buckets() -> list[str]:
    return list(stage("stage_5_delivery").get("card_creation_when_resumed", {}).get("auto_create_buckets", []))


def confirm_buckets() -> list[str]:
    return list(stage("stage_5_delivery").get("card_creation_when_resumed", {}).get("confirm_buckets", []))
