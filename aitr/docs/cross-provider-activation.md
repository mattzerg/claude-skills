# Activating aitr cross-provider execution

`aitr_exec.py` can route non-Anthropic picks (DeepSeek, Gemini Flash, …) through
OpenRouter — but it ships **dormant** because two things are missing, and a wrong
slug means the wrong model runs and bills. Until both are in place, any
non-Anthropic pick raises `CrossProviderUnavailable` and the caller falls back to
an Anthropic-only re-pick. So today, with neither configured, behavior is
unchanged (Anthropic-only, zero risk).

## Why it's worth activating

Only **metered** callers (per-token API key, not Max-plan OAuth) save real dollars
from cross-provider routing. A cheap classify task on DeepSeek V4 Flash
($0.14/$0.28 per Mtok) vs Opus 4.8 ($5/$25) is ~97% cheaper *per call*. The flat
Max-OAuth callers (idea-backlog, calibrate, etc.) save nothing in dollars — do
NOT point them cross-provider; it converts $0 marginal into real spend.

## Step 1 — provide an OpenRouter key

Either:
- `export OPENROUTER_API_KEY=...` in the caller's environment, or
- store it in the macOS keychain under service `aitr-openrouter`:
  `security add-generic-password -s aitr-openrouter -a "$USER" -w`

`resolve_openrouter_key()` checks env first, then keychain. The value is never
logged.

## Step 2 — map ids → OpenRouter slugs (validated)

Our catalog ids (`deepseek__deepseek-v4-flash`) are our own convention, not
OpenRouter's slugs. Create `data/openrouter_slugs.json`:

```json
{
  "deepseek__deepseek-v4-flash": "deepseek/deepseek-chat",
  "openai__gpt-5.4-nano": "openai/gpt-5-nano"
}
```

Then validate every slug against OpenRouter's public model list (no key needed):

```bash
python3 ~/.claude/skills/aitr/scripts/aitr_exec.py validate-slugs
```

Exit 0 = all slugs exist. Any `MISSING` line means that id would fail — fix the
slug before any caller uses it.

## Step 3 — point a metered caller at it

In a metered caller (one using a per-token API key), replace the
`make_client().messages.create(...)` call with:

```python
from aitr_exec import complete, CrossProviderUnavailable

def _anthropic_exec(model, prompt, system, max_tokens):
    msg = client.messages.create(model=model, max_tokens=max_tokens,
        system=system or NOT_GIVEN,
        messages=[{"role": "user", "content": prompt}])
    return ("".join(b.text for b in msg.content if hasattr(b, "text")),
            msg.usage.input_tokens, msg.usage.output_tokens)

try:
    res = complete(prompt, task_kind="classify", caller="my-skill",
                   quality_floor="cheap-ok", billing_mode="metered",
                   max_tokens=1500, anthropic_executor=_anthropic_exec)
    text = res.text
except CrossProviderUnavailable:
    # key/slug not configured — re-pick anthropic-only (status quo)
    model = aitr_model_or(FALLBACK, task_kind="classify", caller="my-skill",
                          quality_floor="cheap-ok")
    text, *_ = _anthropic_exec(model, prompt, None, 1500)
```

Every `complete()` call logs actual token usage to
`~/.local/state/zerg/aitr/actuals.log`; the weekly report joins it so the metered
savings figure becomes real-token truth instead of an estimate.

## Preview without spending

`aitr_exec.py resolve <signal kv...>` prints what `complete()` would pick + which
execution path it would take + whether cross-provider is ready — no model call,
no spend.
