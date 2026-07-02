---
name: market-sizing
description: TAM / SAM / SOM market sizing with top-down + bottom-up + triangulation. Reads a JSON spec (segment definitions + units + ARPU + capture rate, plus top-down market reference + named source). Outputs `.md` narrative with both methods, gap analysis, and a stacked-bar chart showing TAM → SAM → SOM. Anchored on `MattZerg/_style/consultant_thinking_style.md`. Different from `cost-benefit` (NPV decisions), `scenario-modeler` (parameter sweeps), `competitive-review-skill` (competitor landscape). USE PROACTIVELY when Matt says "TAM", "SAM", "SOM", "market size", "addressable market", "market sizing", or before any business-case input that depends on market scale. REFUSES to render any number without a source citation. Never auto-posts.
allowed-tools: Bash, Read, Write
---

# Market Sizing

Phase 2 numbers-layer. TAM/SAM/SOM with mandatory source citations.

## When to invoke

- Matt says "TAM", "SAM", "SOM", "market size", "addressable market", "size the market", "how big is".
- Any business case input that depends on market scale.

## Modes

### `size` — JSON spec

```bash
python3 ~/.claude/skills/market-sizing/run.py size spec.json \
  --engagement <slug> --mode <mode>
```

Spec JSON shape:
```json
{
  "name": "Agent-aware project management market",
  "currency": "USD",
  "year": 2026,
  "bottom_up": [
    {"segment": "SMB (1-50)", "units": 5800000, "arpu": 240, "capture": 0.005, "source": "[source: Statista 2026 SMB count]"},
    {"segment": "MM (51-500)", "units": 95000, "arpu": 2400, "capture": 0.02, "source": "[source: Crunchbase MM filter]"}
  ],
  "top_down": {
    "total_market": 8400000000,
    "addressable_pct": 0.12,
    "obtainable_pct": 0.04,
    "source": "[source: Gartner PM tooling 2026 report]"
  }
}
```

Writes:
- `<engagement>/05-analysis/market-sizing/<name>.md`
- `.../charts/<name>-stacked.png` — TAM/SAM/SOM bars

## Anti-patterns

- Any segment without a `source` → render refused
- No top-down OR no bottom-up — flagged as single-method
- Bottom-up TAM > top-down TAM by >2x — flagged as inconsistent (likely double-count)
