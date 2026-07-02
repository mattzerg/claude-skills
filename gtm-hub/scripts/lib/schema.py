"""Entity schema contracts. Validation drives `gtm-hub audit`."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any


# Directory name → entity type (singular form)
TYPE_DIRS: dict[str, str] = {
    "experiments": "experiment",
    "content": "content",
    "prospects": "prospect",
    "bd": "bd_target",
    "launches": "launch",
    "themes": "theme",
    "metrics": "metric",
    "workstreams": "workstream",
    "publishing": "publishing",  # owned by zpub skill, indexed read-only here
    "decisions": "decision",  # human-curated decisions Matt is actively weighing
    "projects": "project",    # cross-entity rollups (a launch, a campaign, a case study)
    "launch-backlog": "launch_backlog",  # serial-launch candidate queue; per-slot files filled by Matt
    "dogfood": "dogfood",  # dogfood walkthrough state per product (genre-relaxed; _active.txt + per-product logs)
    "measurement": "measurement",  # per-product Zergalytics measurement spec (genre-relaxed; <slug>.yaml files)
}

DIR_FOR_TYPE: dict[str, str] = {v: k for k, v in TYPE_DIRS.items()}

ENVELOPE_REQUIRED = {"id", "type", "title", "status", "owner", "created", "last_touch"}

STATUS_VALUES: dict[str, set[str]] = {
    "experiment": {
        "proposed",
        "running",
        "won",
        "killed",
        "inconclusive",
    },
    "content": {
        "idea",
        "drafted",
        "reviewed",
        "scheduled",
        "published",
        "distributed",
        "parked",
        "cancelled",
    },
    "prospect": {"inbound", "qualified", "scoped", "proposal-out", "won", "lost"},
    "bd_target": {
        "planned",
        "outreach",
        "engaged",
        "paused",
        "closed-won",
        "closed-lost",
    },
    "launch": {"proposed", "drafting", "ready", "scheduled", "shipped", "parked"},
    "theme": {"inbox", "tracking", "validated", "retired"},
    "metric": {"not-instrumented", "instrumented", "monitored", "deprecated"},
    "workstream": {"hot", "warm", "stale", "parked"},
    # zpub vocabulary (canonical) — wider than hub content's because it tracks
    # multiple genres (blog/launch/email/social/etc.) through one lifecycle.
    "publishing": {
        "ideating", "drafting", "review",
        "scheduled", "published", "distributed", "archived",
    },
    "decision": {"open", "deferred", "decided", "canceled"},
    "project": {"planning", "in-progress", "blocked", "shipped", "paused", "canceled"},
    "launch_backlog": {"tbd", "approved", "in-build", "launched", "killed"},
    # dogfood/measurement live in their own dirs but don't carry the standard
    # envelope (dogfood = _active.txt + per-product logs; measurement = YAML
    # specs). Genre-relaxed below so the walker doesn't choke; no status
    # vocabulary is enforced.
    "dogfood": set(),
    "measurement": set(),
}

# Entity types whose `type` frontmatter field is a content-genre (not the hub
# entity-type), so the validator should not insist that meta['type'] match the
# directory name. zpub-owned `publishing/` files declare `type: blog|launch|...`
# meaning the content kind, not the hub entity type.
# launch_backlog uses its own schema (slug/product_name/conviction/effort) rather
# than the standard envelope; treat it as genre-relaxed so audit doesn't choke.
# dogfood/measurement also bypass the envelope — dogfood log files and
# measurement YAMLs don't carry frontmatter at all (most measurement files are
# `.yaml` so the .md walker skips them; dogfood/_active.txt is similarly skipped).
_GENRE_TYPE_OK = {"publishing", "launch_backlog", "dogfood", "measurement"}


@dataclass
class ValidationError:
    file: str
    field: str
    message: str

    def __str__(self) -> str:  # pragma: no cover - cosmetic
        return f"{self.file}: {self.field}: {self.message}"


@dataclass
class Entity:
    path: str
    type: str
    meta: dict[str, Any] = field(default_factory=dict)
    body: str = ""

    @property
    def id(self) -> str:
        return str(self.meta.get("id", ""))


def parse_date(value: Any) -> dt.date | None:
    if value is None or value == "":
        return None
    if isinstance(value, dt.date):
        return value
    try:
        return dt.date.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None


def validate(entity: Entity) -> list[ValidationError]:
    errors: list[ValidationError] = []
    meta = entity.meta
    etype = entity.type

    # zpub-owned `publishing/` uses its own envelope (`updated_at` instead of
    # `last_touch`, no `created` field, `type` carries genre). Validate looser.
    # launch_backlog has its own schema (slug/product_name/conviction/effort);
    # only `status` is required so the audit can still flag bad status values.
    is_genre = etype in _GENRE_TYPE_OK
    if etype == "launch_backlog":
        envelope_required = {"status"}
    elif etype in {"dogfood", "measurement"}:
        # No envelope required — these dirs hold ad-hoc state, not entities.
        envelope_required = set()
    elif is_genre:
        envelope_required = ENVELOPE_REQUIRED - {"last_touch", "type", "created"}
    else:
        envelope_required = ENVELOPE_REQUIRED
    for f in envelope_required:
        if f not in meta or meta[f] in (None, ""):
            errors.append(ValidationError(entity.path, f, "missing required envelope field"))

    if not is_genre and meta.get("type") and meta["type"] != etype:
        errors.append(
            ValidationError(
                entity.path,
                "type",
                f"frontmatter says {meta['type']!r} but lives under {etype!r} directory",
            )
        )

    expected_id_from_filename = entity.path.rsplit("/", 1)[-1].removesuffix(".md")
    if meta.get("id") and meta["id"] != expected_id_from_filename:
        errors.append(
            ValidationError(
                entity.path,
                "id",
                f"id {meta['id']!r} does not match filename {expected_id_from_filename!r}",
            )
        )

    allowed = STATUS_VALUES.get(etype)
    if allowed and meta.get("status") and meta["status"] not in allowed:
        errors.append(
            ValidationError(
                entity.path,
                "status",
                f"status {meta['status']!r} not in allowed set {sorted(allowed)}",
            )
        )

    for date_field in ("created", "last_touch", "kill_date", "started", "concluded", "scheduled_date", "published_date", "ship_date", "shipped_date", "first_seen", "last_seen", "last_measured", "last_activity", "last_outbound", "first_touch_date", "proposal_out_at", "closed_at"):
        if date_field in meta and meta[date_field] not in (None, ""):
            if parse_date(meta[date_field]) is None:
                errors.append(
                    ValidationError(
                        entity.path,
                        date_field,
                        f"value {meta[date_field]!r} is not ISO YYYY-MM-DD",
                    )
                )

    if etype == "experiment" and meta.get("status") == "running":
        if not parse_date(meta.get("kill_date")):
            errors.append(
                ValidationError(entity.path, "kill_date", "experiments with status=running require kill_date")
            )

    return errors


def envelope_view(entity: Entity) -> dict[str, Any]:
    """Subset of meta we always carry in index.json."""
    m = entity.meta
    # publishing: zpub stores genre in `type`, last-mutation in `updated_at`.
    # Re-map so the index has consistent envelope fields downstream.
    if entity.type == "publishing":
        kind = m.get("type")  # zpub's "type" = content genre
        updated_at = m.get("updated_at") or ""
        last_touch = updated_at.split("T", 1)[0] if isinstance(updated_at, str) else ""
    else:
        kind = m.get("kind")
        last_touch = m.get("last_touch")
    return {
        "id": m.get("id"),
        "type": entity.type,
        "title": m.get("title"),
        "status": m.get("status"),
        "owner": m.get("owner"),
        "created": m.get("created"),
        "last_touch": last_touch,
        "path": entity.path,
        "linked": m.get("linked") or {},
        "zergboard_card": (m.get("linked") or {}).get("zergboard_card") if isinstance(m.get("linked"), dict) else None,
        # Type-specific fields we always want for decisions / rendering:
        "kill_date": m.get("kill_date"),
        "kill_threshold": m.get("kill_threshold"),
        "success_metric": m.get("success_metric"),
        "started": m.get("started"),
        "concluded": m.get("concluded"),
        "verdict": m.get("verdict"),
        "phase": m.get("phase"),
        "rice_score": m.get("rice_score"),
        "scheduled_date": m.get("scheduled_date"),
        "published_date": m.get("published_date"),
        "target_date": m.get("target_date"),
        "kind": m.get("kind"),
        "company": m.get("company"),
        "score": m.get("score"),
        "category": m.get("category"),
        "next_action": m.get("next_action"),
        "proposal_out_at": m.get("proposal_out_at"),
        "ship_date": m.get("ship_date"),
        "value": m.get("value"),
        "target": m.get("target"),
        "instrumentation_owner": m.get("instrumentation_owner"),
        "source_system": m.get("source_system"),
        "last_activity": m.get("last_activity"),
        "open_items": m.get("open_items"),
        # decision-specific
        "question": m.get("question"),
        "context": m.get("context"),
        "options": m.get("options"),
        "deadline": m.get("deadline"),
        "unblocks": m.get("unblocks"),
        "decided": m.get("decided"),
        "decided_at": m.get("decided_at"),
        "cascade": m.get("cascade"),
        "rationale": m.get("rationale"),
        # project-specific
        "start_date": m.get("start_date"),
        "progress_pct": m.get("progress_pct"),
        "status_summary": m.get("status_summary"),
        "linked_entities": m.get("linked_entities"),
        "blockers": m.get("blockers"),
        "rag": m.get("rag"),  # red / amber / green
    }
