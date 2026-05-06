# Fake Matt feedback — https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/

_Reviewed 2026-05-05 18:12; 1 pages, 12 findings._

**Severity:** P0=1 · P1=6 · P2=5

## If I only fix three things
- Console error shows rollup fetch is failing due to credentials in URL. The error message reads 'Request cannot be constructed from a URL that includes credentials: /api/org/zerg/rollup?period=30d'. This blocks the primary data-loading path for the dashboard, meaning the analytics table remains empty and the page is non-functional for its core use case.
  - **Fix:** Remove credentials from the fetch URL construction in loadRollup() function at app.js:151. Use credential-free paths and rely on session-based auth or separate authorization headers instead of embedding credentials in the request URL.

## Per-page findings

### P0

### P0 — technical · broken
- **Where:** https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/ (`console error`)
- ![](/Users/mattheweisner/.claude/skills-matt/fakematt-feedback/state/20260505-181111-admin/screenshots/home_desktop.png)
- **Finding:** Console error shows rollup fetch is failing due to credentials in URL. The error message reads 'Request cannot be constructed from a URL that includes credentials: /api/org/zerg/rollup?period=30d'. This blocks the primary data-loading path for the dashboard, meaning the analytics table remains empty and the page is non-functional for its core use case.
- **Fix:** Remove credentials from the fetch URL construction in loadRollup() function at app.js:151. Use credential-free paths and rely on session-based auth or separate authorization headers instead of embedding credentials in the request URL.
- **Role:** Applies to all users; admin credentials present in URL suggest this is an admin view but the error affects core feature.
- **Provenance:** voice=`—` · principles=`p-0106`

### P1

### P1 — empty_state · broken
- **Where:** https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/ (`.table-container`)
- ![](/Users/mattheweisner/.claude/skills-matt/fakematt-feedback/state/20260505-181111-admin/screenshots/home_desktop.png)
- **Finding:** The 'All properties' table is completely empty with only column headers visible (PROPERTY, PRODUCT, SURFACE, VISITORS, PAGEVIEWS, TREND 7D, LAST SEEN). The descriptor text says 'across all 0 properties' which confirms zero state, but no guidance is provided on what to do next or why the table is empty. Users landing here for the first time have no actionable path forward.
- **Fix:** Add an empty state component inside the table area with centered content: (1) explanatory heading 'No properties tracked yet', (2) brief copy explaining how properties get added or why none exist, (3) if user can add properties, a primary CTA button 'Add your first property'; if not, copy like 'Properties will appear here once your team adds tracking to a site.'
- **Role:** Applies to all roles; if only admins can add properties, copy should indicate this.
- **Provenance:** voice=`—` · principles=`p-0106`, `p-0107`

### P1 — copy · broken
- **Where:** https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/ (`h1 + p`)
- ![](/Users/mattheweisner/.claude/skills-matt/fakematt-feedback/state/20260505-181111-admin/screenshots/home_desktop.png)
- **Finding:** The subtitle 'Pageviews and visitors across all 0 properties — without tracking anyone' contains a misleading contradiction. It says 'without tracking anyone' immediately after describing visitor analytics, which creates confusion about what the product actually does. The phrase likely intends to highlight privacy-first methodology but reads as a negation of the product's value proposition.
- **Fix:** Rewrite to clarify the privacy mechanism without undermining the core function. Suggested: 'Pageviews and visitors across all 0 properties — privacy-first, no cookies, no personal data stored.' This retains the privacy claim while making it clear the product does track visits, just not individuals.
- **Provenance:** voice=`q-0007` · principles=`p-0107`, `p-0029`

### P1 — interaction · broken
- **Where:** https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/ (`.table thead th`)
- ![](/Users/mattheweisner/.claude/skills-matt/fakematt-feedback/state/20260505-181111-admin/screenshots/home_desktop.png)
- **Finding:** Table column headers (PROPERTY, PRODUCT, SURFACE, VISITORS, PAGEVIEWS, TREND 7D, LAST SEEN) have no visual affordance indicating whether they are sortable. No sort icons, no hover state change visible, and no cursor change is evident. Users cannot tell if clicking a header will sort the data or do nothing.
- **Fix:** Add sort affordance to all sortable columns: (1) append a ↕ icon to each sortable header label, (2) on hover, change cursor to pointer and apply subtle highlight, (3) when a column is actively sorted, replace ↕ with ↑ or ↓ and visually emphasize the active column header. If columns are not sortable, this is a missing feature (see f-0006).
- **Provenance:** voice=`—` · principles=`p-0110`, `p-0107`

### P1 — additive_feature · additive
- **Where:** https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/ (`.table thead`)
- ![](/Users/mattheweisner/.claude/skills-matt/fakematt-feedback/state/20260505-181111-admin/screenshots/home_desktop.png)
- **Finding:** The properties table lacks column sorting functionality. Competing analytics dashboards (Google Analytics, Plausible, Fathom) allow users to sort by pageviews, visitors, or last-seen date to quickly identify top performers or recently active properties. Without sorting, users with more than a few properties will struggle to find the data they need.
- **Fix:** Implement client-side or server-side column sorting. Allow users to click any column header to sort ascending/descending. Default sort should be by VISITORS descending (most-visited properties first) or LAST SEEN descending (most recently active first) to surface the most relevant data immediately.
- **Provenance:** voice=`—` · principles=`p-0110`, `p-0101`

### P1 — ia · broken
- **Where:** https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/ (`.card-header`)
- ![](/Users/mattheweisner/.claude/skills-matt/fakematt-feedback/state/20260505-181111-admin/screenshots/home_desktop.png)
- **Finding:** The 'All properties' card header shows '— LAST 30 DAYS' as the active filter, but this label does not update to reflect the actual selected time range when users switch to 24H, 7 DAYS, 6 MO, or 12 MO. The interaction screenshots show the time-range button changing state but the card header remaining static at '30 DAYS'. This creates a visibility-of-system-status failure where users cannot confirm their filter selection.
- **Fix:** Bind the card header subtitle to the active time range state. When a user clicks '24H', update the subtitle to read '— LAST 24 HOURS'. When '7 DAYS' is clicked, change to '— LAST 7 DAYS', etc. Ensure this updates synchronously with the button state change so users see immediate confirmation.
- **Provenance:** voice=`—` · principles=`p-0106`

### P1 — additive_feature · additive
- **Where:** https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/ (`.dropdown-placeholder`)
- ![](/Users/mattheweisner/.claude/skills-matt/fakematt-feedback/state/20260505-181111-admin/screenshots/home_desktop.png)
- **Finding:** A dropdown control appears to the left of the time-range buttons but has no visible label or selected value, making it impossible to know what it filters or controls. Unlabeled dropdowns force users to click and explore to understand their function, which increases cognitive load and error probability.
- **Fix:** Add a visible label to the dropdown: either a persistent label to its left ('Property:' or 'Filter:') or ensure the dropdown's selected value is always visible (e.g. 'All properties' or a specific property name). If the dropdown is for property selection, the label should read 'Property:' and default selection should read 'All properties (rollup)' to match the table header.
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0110`

### P2

### P2 — consistency · broken
- **Where:** https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/ (`.time-range-buttons`)
- ![](/Users/mattheweisner/.claude/skills-matt/fakematt-feedback/state/20260505-181111-admin/screenshots/home_desktop.png)
- **Finding:** Time range button labels use inconsistent formatting: '24H' and '7 DAYS' follow different conventions (one uses H suffix, the other spells out 'DAYS'), while '6 MO' and '12 MO' introduce a third abbreviation style. This creates visual inconsistency and forces users to parse three different label patterns for a single control group.
- **Fix:** Standardize all button labels to a single convention. Recommended: '24H', '7D', '30D', '6M', '12M' (consistent single-letter suffixes) or spell everything out: '24 Hours', '7 Days', '30 Days', '6 Months', '12 Months'. The abbreviated form is preferred for compact UI.
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0096`

### P2 — typography · broken
- **Where:** https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/ (`.privacy-posture`)
- ![](/Users/mattheweisner/.claude/skills-matt/fakematt-feedback/state/20260505-181111-admin/screenshots/home_desktop.png)
- **Finding:** The 'Privacy posture' paragraph contains inline code-style formatting for the hash algorithm 'SHA256(daily_salt + ip + ua + domain)' which breaks the reading flow and is inconsistent with the surrounding plain text. The technical detail is important but the visual treatment makes the paragraph harder to scan.
- **Fix:** Either remove the code formatting and render the hash formula in plain text with the same font as the rest of the paragraph, or move the technical implementation details to a collapsible 'Technical details' disclosure below the summary. Preferred: summary sentence 'Visitor identity uses a daily-rotated hash; no raw IPs or user-agents are stored' with optional expandable section for engineers who want the formula.
- **Provenance:** voice=`—` · principles=`p-0085`, `p-0086`

### P2 — responsive · broken
- **Where:** https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/ (`.time-range-buttons`)
- ![](/Users/mattheweisner/.claude/skills-matt/fakematt-feedback/state/20260505-181111-admin/screenshots/home_mobile.png)
- **Finding:** On tablet view (768px), the time-range button group maintains desktop horizontal layout but buttons appear slightly cramped. At probable mobile widths (≤375px), this row of 5 buttons plus checkbox will either force horizontal scroll or compress buttons to illegibility. The 'AUTO-REFRESH: OFF' checkbox compounds the width problem.
- **Fix:** At breakpoints ≤768px, stack the time-range controls: place the 5 time buttons in a single row that wraps or scrolls horizontally (with scroll-snap if needed), and move the 'AUTO-REFRESH' toggle to a second row below. At ≤480px, consider converting the button group to a native select dropdown to save space.
- **Provenance:** voice=`—` · principles=`p-0010`, `p-0058`

### P2 — copy · broken
- **Where:** https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/ (`.privacy-posture`)
- ![](/Users/mattheweisner/.claude/skills-matt/fakematt-feedback/state/20260505-181111-admin/screenshots/home_desktop.png)
- **Finding:** The 'Privacy posture' paragraph uses passive, technical language ('Referrers are reduced to hostname only. URLs strip query strings before storage.') that obscures the user benefit. Engineers understand these details but non-technical stakeholders need to know what this means for compliance and user privacy.
- **Fix:** Rewrite the paragraph to lead with outcome, then provide technical details for engineers. Example: 'Privacy posture: This dashboard is GDPR-compliant and requires no cookie banners. Visitor identity is hashed daily (no IP retention), referrers show only domain (no full URLs), and query parameters are stripped before storage. Technical details: SHA256(daily_salt + ip + ua + domain) truncated to 16 chars; salt rotates every UTC day.'
- **Provenance:** voice=`q-0003` · principles=`p-0043`, `p-0107`

### P2 — additive_feature · additive
- **Where:** https://admin:8FBYgxNGAjeQEWFvTEEoVufWZ9dK7aT_CQt_mBKjmoM@zerglytics-epoch.fly.dev/ (`.table-container`)
- ![](/Users/mattheweisner/.claude/skills-matt/fakematt-feedback/state/20260505-181111-admin/screenshots/home_desktop.png)
- **Finding:** The properties table shows 7 columns but has no pagination, search, or filter controls visible. Once the user has more than ~20 properties, they will need to scroll through a long table or use browser search to find a specific property. Competing tools (Plausible, Fathom) provide at minimum a search box above the table.
- **Fix:** Add a search input field above the table with placeholder text 'Search properties by name or domain'. Implement client-side filtering that narrows the table rows as the user types. If server-side pagination is implemented, include page controls (Previous/Next, or page numbers) below the table and show 'Showing X–Y of Z properties' status text.
- **Provenance:** voice=`—` · principles=`p-0110`, `p-0101`

