# Fake Matt feedback — http://127.0.0.1:5151/?period=7d

_Reviewed 2026-05-03 22:54; 1 pages, 12 findings (0 rejected for missing provenance)._

**Severity:** P0=2 · P1=5 · P2=5

## If I only fix three things
- The period selector implements role='tablist' but does not contain required role='tab' children. This is a critical ARIA pattern violation that breaks screen reader navigation—assistive tech announces a tab control but cannot enumerate or select any tabs. Keyboard users receive no indication of which period is active.
  - **Fix:** Replace the tablist pattern with a proper implementation: wrap each period button in role='tab', add aria-selected='true' to the active tab, set tabindex='0' on the active tab and tabindex='-1' on inactive tabs, and add arrow-key navigation that moves focus and updates aria-selected. Alternatively, if tab semantics aren't needed, use role='group' with aria-label='Time period' and mark buttons with aria-pressed to indicate toggle state.
- Six delta indicators (e.g., '▲ 200.0% vs prior') fail WCAG AA color contrast requirements. The axe scan flags these as serious violations. Low-contrast deltas are unreadable for users with low vision and in bright mobile environments, making period-over-period comparison—a core dashboard function—unusable for a meaningful segment of users.
  - **Fix:** Increase contrast to meet 4.5:1 minimum for normal text. If the current green/red delta colors are brand-locked, darken them or add a semi-transparent dark background behind the text. Test final values with a contrast checker (e.g., WebAIM tool) and verify all six flagged nodes pass.

## All findings

### P0 — accessibility
- **Where:** http://127.0.0.1:5151/?period=7d (`div.period[role='tablist']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-225208-127/screenshots/home_desktop.png)
- **Finding:** The period selector implements role='tablist' but does not contain required role='tab' children. This is a critical ARIA pattern violation that breaks screen reader navigation—assistive tech announces a tab control but cannot enumerate or select any tabs. Keyboard users receive no indication of which period is active.
- **Fix:** Replace the tablist pattern with a proper implementation: wrap each period button in role='tab', add aria-selected='true' to the active tab, set tabindex='0' on the active tab and tabindex='-1' on inactive tabs, and add arrow-key navigation that moves focus and updates aria-selected. Alternatively, if tab semantics aren't needed, use role='group' with aria-label='Time period' and mark buttons with aria-pressed to indicate toggle state.
- **Provenance:** voice=`None` · principles=`p-0002`, `p-0110`

### P0 — accessibility
- **Where:** http://127.0.0.1:5151/?period=7d (`div.delta`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-225208-127/screenshots/home_desktop.png)
- **Finding:** Six delta indicators (e.g., '▲ 200.0% vs prior') fail WCAG AA color contrast requirements. The axe scan flags these as serious violations. Low-contrast deltas are unreadable for users with low vision and in bright mobile environments, making period-over-period comparison—a core dashboard function—unusable for a meaningful segment of users.
- **Fix:** Increase contrast to meet 4.5:1 minimum for normal text. If the current green/red delta colors are brand-locked, darken them or add a semi-transparent dark background behind the text. Test final values with a contrast checker (e.g., WebAIM tool) and verify all six flagged nodes pass.
- **Provenance:** voice=`None` · principles=`p-0001`, `p-0095`

### P1 — accessibility
- **Where:** http://127.0.0.1:5151/?period=7d (`h3:first-of-type`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-225208-127/screenshots/home_desktop.png)
- **Finding:** Heading hierarchy jumps from h1 ('Visitor analytics') directly to h3 ('What changed'), skipping h2. Screen reader users rely on heading levels to build a mental model of page structure; skipping levels breaks this navigation pattern and triggers an axe moderate violation.
- **Fix:** Either demote the h3 tags to h2 (if these are true top-level sections), or insert a visually-hidden h2 above the first h3 to maintain semantic structure. If the visual hierarchy requires different sizing, use CSS to style h2 elements to match the current h3 appearance.
- **Provenance:** voice=`None` · principles=`p-0002`, `p-0107`

### P1 — accessibility
- **Where:** http://127.0.0.1:5151/?period=7d (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-225208-127/screenshots/home_desktop.png)
- **Finding:** The page has no main landmark and 11 content nodes are not wrapped in semantic landmarks (main, nav, aside). Screen reader users cannot jump to primary content or skip repeated UI, and the structure is opaque to assistive tech. This is flagged as a moderate axe violation but impacts daily navigation efficiency for AT users.
- **Fix:** Wrap the dashboard content area (starting at 'Visitor analytics' heading) in a <main> element. If the top bar ('ADMIN · ANALYTICS') is navigation, mark it with <nav> and aria-label='Primary navigation'. Wrap any sidebar or supplementary content in <aside>. This gives AT users clear skip-to-main functionality and explicit content regions.
- **Provenance:** voice=`None` · principles=`p-0002`, `p-0106`

### P1 — consistency
- **Where:** http://127.0.0.1:5151/?period=7d (`.funnel-step, .delta`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-225208-127/screenshots/home_desktop.png)
- **Finding:** Delta formatting is inconsistent across the dashboard. Metric cards show '▲ 200.0% vs prior' with an arrow prefix, while funnel steps show '· 110.9% of prev' with a bullet prefix and different wording ('vs prior' vs 'of prev'). This inconsistency forces users to parse different comparison patterns in each section, increasing cognitive load.
- **Fix:** Standardize on a single delta format across all sections. Recommended pattern: '{arrow} {value}% vs prior' for all period-over-period comparisons. If the funnel logic differs (step-to-step vs period-over-period), use a distinct label like 'vs previous step' to signal the different baseline, but keep the arrow-value-label structure consistent.
- **Provenance:** voice=`None` · principles=`p-0022`, `p-0107`

### P1 — interaction
- **Where:** http://127.0.0.1:5151/?period=7d (`button:contains('AUTO-REFRESH')`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-225208-127/screenshots/home_desktop.png)
- **Finding:** The 'AUTO-REFRESH' control does not indicate its current state. Users cannot tell whether auto-refresh is currently enabled or disabled without clicking it and observing behavior. This ambiguity is especially problematic in a monitoring dashboard where refresh behavior directly affects data freshness.
- **Fix:** Change the button label to reflect state: 'Auto-refresh: ON' or 'Auto-refresh: OFF'. Add aria-pressed='true|false' to expose toggle state to assistive tech. Consider a more explicit toggle UI (switch or checkbox) if space permits, as these afford clearer on/off semantics than a text button.
- **Provenance:** voice=`None` · principles=`p-0106`, `p-0107`

### P1 — accessibility
- **Where:** http://127.0.0.1:5151/?period=7d (`table th`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-225208-127/screenshots/home_desktop.png)
- **Finding:** The Campaign matrix table displays column labels (CAMPAIGN, MEDIUM, SOURCE, VISITORS, PAGEVIEWS) but these are not marked up as <th> elements. Screen readers cannot associate data cells with their column headers, making the table structure illegible to AT users navigating cell-by-cell.
- **Fix:** Wrap the first row in <thead> and mark each column label as <th scope='col'>. Wrap the data rows in <tbody>. This allows screen readers to announce 'Campaign: blog-launch' instead of just 'blog-launch', providing essential context for each cell.
- **Provenance:** voice=`None` · principles=`p-0002`, `p-0107`

### P2 — empty_state
- **Where:** http://127.0.0.1:5151/?period=7d (`section:contains('No goals fired')`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-225208-127/screenshots/home_desktop.png)
- **Finding:** The 'No goals fired yet' empty state is passive—it states what's missing but doesn't guide the admin on next steps. The follow-up instruction ('Fire goals from the page with window.zb…') is present but visually subordinate, making the path forward less obvious than it should be for a first-time user.
- **Fix:** Restructure the empty state to lead with the action: 'Set up your first goal' as a heading, followed by the code snippet in a highlighted code block, and a 'View documentation' link if docs exist. Alternatively, show a working example ('Track signups: window.zb("signup_completed", { plan: "team" })') as a copyable snippet with a button to copy to clipboard.
- **Provenance:** voice=`None` · principles=`p-0074`, `p-0109`

### P2 — typography
- **Where:** http://127.0.0.1:5151/?period=7d (`.metric-card .delta`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-225208-127/screenshots/home_desktop.png)
- **Finding:** In the metric cards (Unique Visitors, Total Pageviews, etc.), the large primary number (e.g., '447') and the delta ('▲ 200.0% vs prior') have similar visual weight, making it unclear which value is the current metric and which is the comparison. The delta should be visually subordinate to the primary value.
- **Fix:** Reduce the delta text size by at least 2 steps in the type scale, and reduce opacity to 0.7 or use a lighter grey. This creates clear hierarchy: the primary metric dominates, and the delta reads as supporting context. Refer to Refactoring UI's hierarchy guidance on using both size and color for emphasis.
- **Provenance:** voice=`None` · principles=`p-0093`, `p-0096`

### P2 — additive_feature
- **Where:** http://127.0.0.1:5151/?period=7d (`section:contains('Top pages')`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-225208-127/screenshots/home_desktop.png)
- **Finding:** The 'Top pages' and 'Top sources' lists show raw counts but no context on what share of total traffic each represents. Adding a visual share indicator (bar chart or percentage) would allow admins to quickly assess traffic concentration without doing mental math across multiple sections.
- **Fix:** Add a horizontal bar behind each row, scaled to the max value in that section, and optionally show the percentage in parentheses after the count: '/pricing 122 (27%)'. This is a common pattern in analytics tools (Plausible, Fathom) and improves scannability without requiring additional table columns.
- **Provenance:** voice=`None` · principles=`p-0106`, `p-0110`

### P2 — responsive
- **Where:** http://127.0.0.1:5151/?period=7d (`.period button`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-225208-127/screenshots/home_mobile.png)
- **Finding:** The period selector buttons (24H, 7 DAYS, 30 DAYS, 6 MO, 12 MO, AUTO-REFRESH) are likely to overflow or wrap awkwardly on mobile viewports, especially if labels are long. The mobile screenshot should confirm whether horizontal scroll or button wrapping occurs.
- **Fix:** If overflow is present, implement a horizontal scrollable button group (overflow-x: auto with scroll-snap-type: x mandatory) so users can swipe through period options on touch devices. Ensure the active button is scrolled into view on page load. Alternatively, collapse less-used periods (6 MO, 12 MO) into a dropdown on small screens.
- **Provenance:** voice=`None` · principles=`p-0058`, `p-0010`

### P2 — copy
- **Where:** http://127.0.0.1:5151/?period=7d (`.hint`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-225208-127/screenshots/home_desktop.png)
- **Finding:** Hint labels use midpoint bullets ('·') as separators, which render inconsistently across fonts and may be unclear to non-native English readers. The pattern 'AI SUMMARY · VS PRIOR PERIOD' reads as a title-subtitle pair but the relationship is ambiguous—is 'vs prior period' a filter on the summary or a clarification of the comparison baseline?
- **Fix:** Replace midpoint separators with em dashes or parentheses for clearer grouping: 'AI summary — vs prior period' or 'AI summary (vs prior period)'. If the hint structure is consistent across all sections, consider a lighter color or smaller size to further distinguish it from primary headings.
- **Provenance:** voice=`None` · principles=`p-0107`, `p-0011`

