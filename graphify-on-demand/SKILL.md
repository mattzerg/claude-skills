---
name: graphify-on-demand
description: Use Graphify as a contained, on-demand code graph diagnostic for unfamiliar repos, architecture questions, symbol dependency exploration, or repeated code navigation. Run via `uvx --from graphifyy graphify` without global install, avoid semantic extraction unless an LLM backend/data policy is intentional, and never install Graphify Codex/Claude hooks unless Matt explicitly asks.
metadata:
  short-description: Safe on-demand Graphify code graphs
---

# Graphify On Demand

Use this when Matt asks to try Graphify, build a code graph, inspect architecture with Graphify, or when a repo is large enough that an AST graph may help.

## Default posture

- Prefer `rg` and direct file reads for ordinary code questions.
- Use Graphify for unfamiliar repos, repeated architecture questions, or symbol dependency exploration.
- Run Graphify through `uvx --from graphifyy graphify`; do not globally install it.
- Write outputs to a temp copy or disposable target unless Matt explicitly wants `graphify-out/` in the repo.
- Avoid docs/PDF/image semantic extraction unless the backend/API key and data residency are intentional.
- Do not run `graphify codex install`, `graphify claude install`, or `graphify hook install` unless Matt explicitly asks for hooks/integration.

## Safe workflow

1. Choose a target:
   - Code-only temp copy for a first pass.
   - Real repo only if writing `graphify-out/` there is acceptable.
2. Extract offline AST graph:

```bash
uvx --from graphifyy graphify extract /path/to/code-only-target --no-viz
```

3. Generate report without LLM labels:

```bash
uvx --from graphifyy graphify cluster-only /path/to/code-only-target --no-viz --no-label
```

4. Read:
   - `/path/to/code-only-target/graphify-out/GRAPH_REPORT.md`
   - targeted `explain` output:

```bash
uvx --from graphifyy graphify explain 'SymbolName' --graph /path/to/code-only-target/graphify-out/graph.json
```

5. Treat `query` and `path` as advisory only. Verify against source files with `rg`/reads before making code changes.

## Known behavior from Matt's 2026-06-08 pilot

- Package name is `graphifyy`; executable is `graphify`.
- v0.8.35 worked via `uvx`.
- Code-only extraction worked offline with zero token cost.
- Mixed code + docs refused to run without an LLM key, which is good for privacy.
- `explain` gave useful symbol context.
- `path` and natural-language `query` can choose misleading shortest paths or noisy traversal output.
- Good current verdict: on-demand diagnostic, not always-on hooks.

