"""Pure ranker for aitr.

`rank(signal, catalog, routing_table) -> List[Candidate]`

No I/O, no dependencies beyond stdlib. The CLI (pick.py) loads catalog +
routing_table from disk/HTTP and passes them in. Tests stub both.

Catalog shape (from snapshot/search.json or live /api/search.json):
  { "models": [ <model record>, ... ] }

Model record (minimum fields used here):
  id, name, provider, model_class, released (ISO date)
  status (must be "ga" to be considered)
  context_window (int), output_window (int)
  modalities (list[str])
  pricing.{input_per_mtok, output_per_mtok}  (USD per million tokens)
  tags (list[str])
  benchmarks (optional dict[str, float] — 0..1)

Routing table shape (from routing_table.yaml):
  composite_weights: { capability, cost, latency }
  quality_floors: { cheap-ok, medium, high-stakes }   # capability thresholds
  high_stakes_whitelist: [model_class, ...]
  task_kinds:
    <task_kind>:
      preferred_tags: [str, ...]
      min_context: int
      latency_class: fast|medium|slow
      benchmark_key: str  (optional)
      opposite_provider: bool  (optional)
      delegate_to: str  (optional — caller should route OUT)
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional


@dataclass(frozen=True)
class Candidate:
    model: str
    provider: str
    model_class: str
    score: float
    capability: float
    cost: float
    latency: float
    estimated_cost_usd: float
    context_window: int
    reason: str

    def to_dict(self) -> dict:
        return asdict(self)


class RankerError(Exception):
    """Raised when the ranker cannot proceed (e.g., empty catalog)."""


# ---- Scoring helpers -------------------------------------------------------

LATENCY_CLASS_TARGETS = {"fast": 5, "medium": 30, "slow": 120}  # seconds, rough
LATENCY_TAG_BIAS = {
    "fast": 1.0,
    "small-model": 1.0,
    "extended-thinking": 0.3,
    "reasoning": 0.5,
}


def _jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def benchmark_ranges(models: list[dict]) -> Dict[str, tuple]:
    """(min, max) per benchmark across the catalog, for normalizing non-fraction
    scores (e.g. Arena Elo ~1200-1500) to [0,1]. Fractions (≤1) skip this."""
    from collections import defaultdict
    vals: Dict[str, list] = defaultdict(list)
    for m in models:
        for k, v in (m.get("benchmarks") or {}).items():
            if isinstance(v, (int, float)) and v > 1.0:
                vals[k].append(float(v))
    return {k: (min(xs), max(xs)) for k, xs in vals.items() if xs}


def _normalize_benchmark(value, bench: str, norm: Dict[str, tuple]) -> Optional[float]:
    """Benchmark value → [0,1]. Fractions pass through; >1 scores (Elo) min-max
    normalized against the catalog range. None when unscoreable."""
    if not isinstance(value, (int, float)):
        return None
    v = float(value)
    if 0.0 <= v <= 1.0:
        return v
    rng = norm.get(bench)
    if not rng:
        return None
    lo, hi = rng
    if hi <= lo:
        return None
    return max(0.0, min(1.0, (v - lo) / (hi - lo)))


def capability_score(model: dict, rules: dict, *, benchmark_norm: Optional[Dict[str, tuple]] = None) -> float:
    """Quality score in [0,1]: tag fit blended with a real benchmark PROFILE.

    Tags alone are a coarse proxy. When a task defines a `benchmark_profile`
    (weighted set of evals — e.g. code-review = swe_bench_verified + swe_bench_pro
    + terminal_bench), capability becomes 50% tag fit + 50% the model's
    weighted-average score on whichever profile benchmarks it actually publishes.
    Models with no profile data fall back to tag-only (no penalty for missing
    evals). `benchmark_key` (single) is still honored as a one-entry profile.
    """
    benchmark_norm = benchmark_norm or {}
    model_tags = set(model.get("tags") or [])
    preferred = set(rules.get("preferred_tags") or [])
    base = _jaccard(model_tags, preferred)

    profile = rules.get("benchmark_profile")
    if not profile and rules.get("benchmark_key"):
        profile = {rules["benchmark_key"]: 1.0}
    if profile:
        bms = model.get("benchmarks") or {}
        num = wsum = 0.0
        for bench, weight in profile.items():
            nv = _normalize_benchmark(bms.get(bench), bench, benchmark_norm)
            if nv is not None:
                num += float(weight) * nv
                wsum += float(weight)
        if wsum > 0:
            return min(1.0, 0.5 * base + 0.5 * (num / wsum))
    return base


def estimated_cost_usd(model: dict, artifact_size_tokens: int, output_estimate: int = 2000) -> float:
    pricing = model.get("pricing") or {}
    in_rate = float(pricing.get("input_per_mtok") or 0.0)
    out_rate = float(pricing.get("output_per_mtok") or 0.0)
    return (artifact_size_tokens * in_rate + output_estimate * out_rate) / 1_000_000.0


def cost_score(cost_usd: float, budget: Optional[float], cheapest_cost: float) -> float:
    """Lower cost = higher score. If budget set, hard floor + linear within budget.
    Otherwise compare to cheapest candidate (log-friendly normalization)."""
    if cost_usd <= 0:
        return 1.0
    if budget is not None and budget > 0:
        if cost_usd > budget:
            return 0.0
        return 1.0 - (cost_usd / budget)
    if cheapest_cost <= 0:
        return 1.0
    ratio = cheapest_cost / cost_usd
    return max(0.0, min(1.0, ratio))


def latency_score(model: dict, latency_class: str, budget_seconds: Optional[int]) -> float:
    """Tag-based; budget only enforces hard floor when set."""
    tags = set(model.get("tags") or [])
    bias_terms = [LATENCY_TAG_BIAS[t] for t in tags if t in LATENCY_TAG_BIAS]
    base = sum(bias_terms) / len(bias_terms) if bias_terms else 0.5
    # Bias by requested latency class
    class_target = LATENCY_CLASS_TARGETS.get(latency_class, 30)
    if class_target <= 10:
        base = min(1.0, base + 0.1)
    elif class_target >= 60:
        base = max(0.0, base - 0.1)
    if budget_seconds is not None and budget_seconds < 10 and base < 0.5:
        # caller demanded fast but model leans slow — penalize hard
        return 0.0
    return max(0.0, min(1.0, base))


# ---- Filtering -------------------------------------------------------------


def _provider_allowed(provider: str, constraint: str, active_provider: Optional[str]) -> bool:
    if constraint == "anthropic-only":
        return provider == "anthropic"
    if constraint == "openai-only":
        return provider == "openai"
    if constraint == "google-only":
        return provider == "google"
    return True


def _hard_filter(
    model: dict,
    signal_dict: dict,
    rules: dict,
    active_provider: Optional[str],
) -> Optional[str]:
    """Return None to keep the model, or a rejection reason string to drop it."""
    if model.get("status") != "ga":
        return f"status={model.get('status')!r} (not ga)"

    modalities = set(model.get("modalities") or [])
    required_modality = signal_dict.get("modality_required")
    if required_modality and required_modality not in modalities:
        return f"missing modality {required_modality!r}"

    provider = model.get("provider", "")
    constraint = signal_dict.get("provider_constraint", "any")
    if not _provider_allowed(provider, constraint, active_provider):
        return f"provider {provider!r} violates constraint {constraint!r}"

    # Opposite-provider hint: if active_provider known and rules ask for opposite,
    # drop models that match the active provider.
    if rules.get("opposite_provider") and active_provider and provider == active_provider:
        return f"opposite_provider required; {provider!r} matches active session"

    ctx = int(model.get("context_window") or 0)
    artifact = int(signal_dict.get("artifact_size_tokens") or 0)
    min_required = max(int(rules.get("min_context") or 0), int(artifact * 1.3))
    if ctx < min_required:
        return f"context_window {ctx} < required {min_required}"

    return None


# ---- Public API ------------------------------------------------------------


def rank(
    signal_dict: dict,
    catalog: dict,
    routing_table: dict,
    *,
    active_provider: Optional[str] = None,
    top_n: int = 5,
    penalties: Optional[Dict[tuple, float]] = None,
    reputation: Optional[Dict[tuple, float]] = None,
) -> List[Candidate]:
    """Score and rank all candidate models against the signal.

    `signal_dict` may be either a Signal.to_dict() or a plain dict. Required keys:
    task_kind, caller. Optional: artifact_size_tokens, latency_budget_seconds,
    cost_budget_usd, quality_floor, provider_constraint, modality_required.

    `active_provider` is the currently-active session provider (e.g. "anthropic"),
    used by the opposite_provider hint in routing rules and by caller-side
    diversification.

    `penalties` is an optional {(caller, task_kind, model_id): negative_float} map
    from explicit wrong-model-picked corrections (penalties.py) — sharp negative.

    `reputation` is an optional {(caller, task_kind, model_id): float} map of
    realized-quality priors from observed outcomes (quality.py) — gentle two-sided,
    bounded ±0.15 so it nudges below the penalty floor. Applied after penalty.

    Returns Candidates sorted by composite score, descending.
    Raises RankerError if no candidates survive hard filters.
    """
    models = list(catalog.get("models") or [])
    if not models:
        raise RankerError("catalog has zero models")

    task_kind = signal_dict.get("task_kind")
    task_rules = ((routing_table.get("task_kinds") or {}).get(task_kind) or {})
    # Per-task weight override beats the global default, so quality-critical tasks
    # (code-review, research) can down-weight cost and let quality lead.
    weights = task_rules.get("weights") or (routing_table.get("composite_weights") or {})
    w_cap = float(weights.get("capability", 0.5))
    w_cost = float(weights.get("cost", 0.3))
    w_lat = float(weights.get("latency", 0.2))
    weights_sum = max(w_cap + w_cost + w_lat, 1e-6)

    # Catalog-wide benchmark ranges, for normalizing non-fraction scores (Elo).
    benchmark_norm = benchmark_ranges(models)

    quality_floor = signal_dict.get("quality_floor") or "medium"
    floors = routing_table.get("quality_floors") or {}
    capability_floor = float(floors.get(quality_floor, 0.5))
    high_stakes_whitelist = set(routing_table.get("high_stakes_whitelist") or [])

    artifact = int(signal_dict.get("artifact_size_tokens") or 4000)
    cost_budget = signal_dict.get("cost_budget_usd")
    latency_budget = signal_dict.get("latency_budget_seconds")
    latency_class = task_rules.get("latency_class", "medium")

    survivors: List[tuple[dict, float, str]] = []  # (model, cost, reject_reason)
    dropped: List[tuple[str, str]] = []
    for m in models:
        reject = _hard_filter(m, signal_dict, task_rules, active_provider)
        if reject:
            dropped.append((m.get("id", "?"), reject))
            continue
        cost = estimated_cost_usd(m, artifact)
        survivors.append((m, cost, ""))

    if not survivors:
        raise RankerError(
            "no candidate survives hard filters; reasons: "
            + ", ".join(f"{i}:{r}" for i, r in dropped[:8])
        )

    # High-stakes is whitelist-FIRST (decision 2026-06-03): when any whitelisted-class
    # model survives the hard filters, only whitelisted models compete. This stops
    # perfect-tag-fit cheap reasoners (e.g. deepseek-r1) from outscoring frontier
    # models on cost at high stakes. When a provider constraint excludes every
    # whitelisted class (e.g. google-only), fall back to the open field so
    # constrained picks still resolve.
    if quality_floor == "high-stakes" and high_stakes_whitelist:
        whitelisted_survivors = [
            s for s in survivors if s[0].get("model_class", "") in high_stakes_whitelist
        ]
        if whitelisted_survivors:
            survivors = whitelisted_survivors

    cheapest_cost = min((c for _, c, _ in survivors if c > 0), default=0.0)

    candidates: List[Candidate] = []
    for m, cost, _ in survivors:
        cap = capability_score(m, task_rules, benchmark_norm=benchmark_norm)
        # Quality-floor gate
        model_class = m.get("model_class", "")
        if quality_floor == "high-stakes" and cap < capability_floor:
            if model_class not in high_stakes_whitelist:
                continue
        elif cap < capability_floor:
            continue
        c_score = cost_score(cost, cost_budget if isinstance(cost_budget, (int, float)) else None, cheapest_cost)
        l_score = latency_score(m, latency_class, latency_budget)
        composite = (w_cap * cap + w_cost * c_score + w_lat * l_score) / weights_sum

        # Feedback penalty: corrections filed via llm-feedback (wrong-model-picked)
        # against this exact (caller, task_kind, model) push it down the ranking.
        rep_key = (signal_dict.get("caller", ""), task_kind, m.get("id", ""))
        feedback_penalty = 0.0
        if penalties:
            feedback_penalty = penalties.get(rep_key, 0.0)
            composite = max(0.0, composite + feedback_penalty)

        # Realized-quality reputation: gentle two-sided prior from observed
        # outcomes (quality.py). Applied after penalty; bounded ±0.15.
        rep_adj = 0.0
        if reputation:
            rep_adj = reputation.get(rep_key, 0.0)
            composite = max(0.0, composite + rep_adj)

        # Build a one-line reason
        reasons = []
        if feedback_penalty < 0:
            reasons.append(f"feedback penalty {feedback_penalty:.2f}")
        if rep_adj > 0:
            reasons.append(f"+{rep_adj:.2f} quality reputation")
        elif rep_adj < 0:
            reasons.append(f"{rep_adj:.2f} quality reputation")
        if cap >= 0.75:
            reasons.append("strong tag fit")
        elif cap >= 0.5:
            reasons.append("ok tag fit")
        else:
            reasons.append("weak tag fit, allowed by floor")
        if cost_budget and cost <= cost_budget:
            reasons.append(f"within ${cost_budget:.2f} budget at ${cost:.3f}")
        else:
            reasons.append(f"~${cost:.3f} estimated")
        if l_score >= 0.8:
            reasons.append("low-latency tags")
        elif l_score <= 0.3:
            reasons.append("higher-latency tags")
        reason = ", ".join(reasons)

        candidates.append(
            Candidate(
                model=m.get("id", ""),
                provider=m.get("provider", ""),
                model_class=model_class,
                score=round(composite, 4),
                capability=round(cap, 4),
                cost=round(c_score, 4),
                latency=round(l_score, 4),
                estimated_cost_usd=round(cost, 5),
                context_window=int(m.get("context_window") or 0),
                reason=reason,
            )
        )

    if not candidates:
        raise RankerError(
            f"all survivors blocked by quality_floor={quality_floor!r} "
            f"(capability_floor={capability_floor})"
        )

    # Sort by composite desc, tie-break by cheaper cost then most-recent release
    def _sort_key(cand: Candidate) -> tuple:
        # Find the model record for tie-breaking
        m_rec = next((x for x in models if x.get("id") == cand.model), {})
        released = m_rec.get("released", "")
        return (-cand.score, cand.estimated_cost_usd, -_release_sort(released))

    candidates.sort(key=_sort_key)
    return candidates[:top_n]


def _release_sort(released: str) -> int:
    """Convert ISO date to a sortable int. Empty/invalid → 0."""
    if not released:
        return 0
    digits = released.replace("-", "")
    try:
        return int(digits[:8])
    except ValueError:
        return 0
