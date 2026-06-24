# Principle citation map

Every finding cites the principle it violates. This is a **coverage map** (what to check + what to cite),
not a style to mimic. Cite the specific principle, not "best practice."

## NN/g 10 usability heuristics (cite by name)
1. **Visibility of system status** — loading/empty/error/connection states communicated (no silent waits).
2. **Match between system & real world** — labels in user language; no internal identifiers/UTC-only/raw IDs.
3. **User control & freedom** — undo/escape; Esc-close + click-outside on overlays; cancel long actions.
4. **Consistency & standards** — platform conventions (e.g. split-Send for schedule, ⌘K palette).
5. **Error prevention** — disable double-submit; validate before submit; confirm destructive actions.
6. **Recognition rather than recall** — pickers over raw-ID text fields; presets over blank customization.
7. **Flexibility & efficiency** — shortcuts/presets for experts; sensible defaults for novices.
8. **Aesthetic & minimalist design** — visual hierarchy; one dominant element; no redundant navigation.
9. **Help users recognize/diagnose/recover from errors** — plain-language errors, NO raw payloads/env names.
10. **Help & documentation** — discoverable affordances; non-cryptic labels/icons (pair icon+text+tooltip).

## WCAG 2.2 AA — the blockers to check
- `<html lang>` set; heading order sequential; accessible name matches visible label (`label-content-name-mismatch`).
- Contrast ≥ 4.5:1 normal / 3:1 large — **measure on the composited (alpha-blended) background**, not a translucent layer.
- Keyboard: every action reachable without a mouse (right-click-only menus fail); visible focus
  (`:focus-visible` present); no focus traps; focus restored on modal close.
- ARIA on toggles/popovers: `aria-expanded`, `aria-haspopup`, `aria-pressed`, `role="dialog"`+label.
- Inputs ≥ 16px on mobile (prevents iOS zoom); tap targets ≥ 44px.

## Baymard / e-commerce-ish flow checks (where relevant)
- Form field count + labels; inline validation; don't ask for data the system already has.

## graphic-layout (for any rendered graphic/marketing asset — NOT product-UI screenshots)
- Top/bottom + left/right balance; eyebrow value test; single dominant headline; intentional whitespace;
  frame coherence across a sequence. (Run the `graphic-layout` skill for marketing assets; don't force it on UI.)

## frontend-design lens (anti-templated-default critique, for new/redesigned surfaces)
- Is there a signature element, or is it the generic default? Typographic hierarchy intentional? Palette
  considered (not Tailwind swatches)? Motion/empty-states designed, not afterthoughts?

## Severity calibration (UX lane, by USER impact)
Critical = can't complete a core task / guaranteed misread · High = needs help or misleads on first read ·
Medium = real friction / trust / wasted space · Low = polish. Judge against the product's stated goal
(e.g. "demo on <date>", "client-facing"), not generic taste.

## Lane routing (what is NOT a UX finding)
Math/persistence/auth/race/security/backend errors → the builder's lane. Note them as one-liners; run
`bug-sweep` to find them properly. A UX exception: when a UX choice makes CORRECT data LOOK wrong, that's UX.
