# Fake Matt feedback — https://ca-org.fly.dev/org-chart

_Reviewed 2026-05-04 13:56; 8 pages, 90 findings (deduped from 98, merged 8)._

**Severity:** P0=8 · P1=50 · P2=32 · site-wide=1

## If I only fix three things
- The page is missing a lang attribute on the <html> element, causing screen readers to use incorrect pronunciation rules for employee names and location data. This is flagged as a serious violation by axe-core and blocks assistive technology from correctly interpreting multilingual content (Taiwan locations, Chinese names like 'Wang, Ben' and 'Chang, Charles'). (site-wide)
  - **Fix:** Add lang='en' to the <html> element. If the page contains substantial non-English content blocks (like Chinese employee names), consider wrapping those in <span lang='zh'> to provide correct pronunciation hints.
- Three select dropdowns ('Show [100] per page' dropdown and the two filter dropdowns for departments and locations) lack accessible names. Screen reader users encounter these as 'select, collapsed' without context about what they control. This violates WCAG 2.2 AA SC 4.1.2 and blocks effective navigation for keyboard-only and screen-reader users.
  - **Fix:** Add aria-label or associate visible labels via <label for="..."> for each select. For the pagination dropdown, use aria-label="Items per page". For the department filter, aria-label="Filter by department". For location filter, aria-label="Filter by location".
- The page is missing the required `lang` attribute on the `<html>` element, flagged by axe-core as a serious violation. This prevents screen readers from correctly announcing content in the appropriate language and is an automatic WCAG 2.2 Level A failure that blocks accessibility certification.
  - **Fix:** Add `lang="en"` (or appropriate language code) to the `<html>` tag: `<html lang="en" style="--zerg-drawer-width: 0px;">`

## Site-wide issues

_These findings showed up across 3+ pages. Fixing one likely fixes all of them._

### P0 — accessibility · broken _[site-wide]_
- **Affected pages (7):**
  - https://ca-org.fly.dev/org-chart
  - https://ca-org.fly.dev/employee-directory
  - https://ca-org.fly.dev/people/1001
  - https://ca-org.fly.dev/people/1032
  - https://ca-org.fly.dev/people/adp_UK001
  - https://ca-org.fly.dev/people/adp_TWN001
  - https://ca-org.fly.dev/people/adp_UK004
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_TWN001_desktop.png)
- **Finding:** The page is missing a lang attribute on the <html> element, causing screen readers to use incorrect pronunciation rules for employee names and location data. This is flagged as a serious violation by axe-core and blocks assistive technology from correctly interpreting multilingual content (Taiwan locations, Chinese names like 'Wang, Ben' and 'Chang, Charles').
- **Fix:** Add lang='en' to the <html> element. If the page contains substantial non-English content blocks (like Chinese employee names), consider wrapping those in <span lang='zh'> to provide correct pronunciation hints.
- **Role:** Applies to all viewer roles.
- **Provenance:** voice=`—` · principles=`p-0002`
- _Merged from 7 per-page findings._

## Per-page findings

### P0

### P0 — accessibility · broken
- **Where:** https://ca-org.fly.dev/employee-directory (`select[data-v-0db96779]`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/employee-directory_desktop.png)
- **Finding:** Three select dropdowns ('Show [100] per page' dropdown and the two filter dropdowns for departments and locations) lack accessible names. Screen reader users encounter these as 'select, collapsed' without context about what they control. This violates WCAG 2.2 AA SC 4.1.2 and blocks effective navigation for keyboard-only and screen-reader users.
- **Fix:** Add aria-label or associate visible labels via <label for="..."> for each select. For the pagination dropdown, use aria-label="Items per page". For the department filter, aria-label="Filter by department". For location filter, aria-label="Filter by location".
- **Provenance:** voice=`—` · principles=`p-0002`, `p-0110`

### P0 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people (`html`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_desktop.png)
- **Finding:** The page is missing the required `lang` attribute on the `<html>` element, flagged by axe-core as a serious violation. This prevents screen readers from correctly announcing content in the appropriate language and is an automatic WCAG 2.2 Level A failure that blocks accessibility certification.
- **Fix:** Add `lang="en"` (or appropriate language code) to the `<html>` tag: `<html lang="en" style="--zerg-drawer-width: 0px;">`
- **Provenance:** voice=`—` · principles=`p-0002`

### P0 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people/1001 (`input[type="file"][accept="image/*"]`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1001_desktop.png)
- **Finding:** The portrait image upload file input (triggered by 'Change Image' button) has no associated label, failing WCAG 4.1.2. Screen reader users cannot identify the purpose of this control, which blocks a core profile-editing task.
- **Fix:** Wrap the input in a <label> or add aria-label="Upload portrait image" to the input element. If the input is intentionally hidden and triggered by the 'Change Image' button, ensure the button itself is properly labeled and the input gets focus when activated.
- **Role:** Applies to super-admin and users with edit permissions.
- **Provenance:** voice=`—` · principles=`p-0002`, `p-0008`

### P0 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people/1032 (`input[type='file'][accept='image/*']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1032_desktop.png)
- **Finding:** The file input associated with 'Change Image' has no programmatic label (axe-core violation: label). Screen reader users encounter an unlabeled form control and cannot determine its purpose, blocking image upload functionality for assistive tech users.
- **Fix:** Wrap the visually-hidden file input in a <label> element or add an aria-label="Upload profile photo" attribute directly to the input. Ensure the associated 'Change Image' button triggers the input via a for/id association or JavaScript click handler.
- **Role:** Applies to all users with edit permissions; super-admins and profile owners see this control.
- **Provenance:** voice=`—` · principles=`p-0002`

### P0 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK001 (`input[type='file'][accept='image/*'].visually-hidden`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK001_desktop.png)
- **Finding:** The file input for portrait image upload has no associated <label>, meaning screen reader users cannot discover or activate it. axe-core flags this as a critical violation. The 'Change Image' button likely triggers this input, but the programmatic association is missing.
- **Fix:** Add an aria-label or associate a <label> element with the file input using for/id attributes. Ensure the 'Change Image' button has aria-controls pointing to the input ID.
- **Role:** Assumes user has edit permissions. Non-editors do not see this control.
- **Provenance:** voice=`—` · principles=`p-0002`, `p-0008`

### P0 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people/adp_TWN001 (`input[type='file'][accept='image/*']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_TWN001_desktop.png)
- **Finding:** The portrait upload input has no associated <label> element, making it invisible and inoperable for screen reader users. Axe-core flags this as a critical violation. Keyboard-only users and assistive tech users cannot discover or activate the upload function.
- **Fix:** Wrap the 'Upload Image' button and the hidden file input in a <label for='portrait-upload'> element, or add aria-label='Upload portrait image' directly to the input and ensure the button programmatically triggers the input via onclick.
- **Role:** Affects editors and super-admins who upload images.
- **Provenance:** voice=`—` · principles=`p-0002`, `p-0008`

### P0 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK004 (`input[type='file'][accept='image/*']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK004_desktop.png)
- **Finding:** The hidden file input under 'Change Image' has no associated label, making it impossible for screen reader users to understand its purpose. This violates WCAG 2.2 AA and blocks a core workflow.
- **Fix:** Add an aria-label="Upload profile image" attribute to the file input, or wrap it with a <label> element that includes visually-hidden text.
- **Role:** Applies to users with edit permissions who can change images
- **Provenance:** voice=`—` · principles=`p-0002`, `p-0011`

### P1

### P1 — accessibility · broken
- **Affected pages (2):**
  - https://ca-org.fly.dev/people/1001
  - https://ca-org.fly.dev/people/1032
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1001_desktop.png)
- **Finding:** The page contains two <main> landmarks (one nested inside another), and two <aside> landmarks with identical accessible names. This violates WCAG 1.3.1 and confuses screen reader users attempting to navigate by landmark, as they cannot distinguish between duplicate regions.
- **Fix:** Remove the outer <main class="content"> wrapper (the page-level main should contain the person-page main, not the reverse), or convert the outer main to a <div>. For the duplicate <aside> elements, add unique aria-label attributes: aria-label="Navigation sidebar" for the left nav and aria-label="Profile metadata" for any secondary aside.
- **Provenance:** voice=`—` · principles=`p-0002`
- _Merged from 2 per-page findings._

### P1 — accessibility · broken
- **Affected pages (2):**
  - https://ca-org.fly.dev/people/adp_TWN001
  - https://ca-org.fly.dev/people/adp_UK004
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_TWN001_desktop.png)
- **Finding:** Heading hierarchy skips from H1 ('Wang, Ben') directly to H3 ('Direct Reports'), violating WCAG 1.3.1 and axe's heading-order rule. Screen reader users navigating by headings will miss structural cues and be disoriented when jumping multiple levels.
- **Fix:** Change section headings ('TEAM', 'SPAN', 'FILES') from uppercase label spans to semantic H2 elements, and make subsection headings ('Direct Reports', 'Manager Snapshot', 'Attachments') H3. This establishes a proper document outline: H1 → H2 → H3.
- **Role:** Applies to all viewer roles.
- **Provenance:** voice=`—` · principles=`p-0002`
- _Merged from 2 per-page findings._

### P1 — accessibility · broken
- **Where:** https://ca-org.fly.dev/org-chart (`html`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** The page contains no h1 heading, only section headings starting at h2 or lower. The axe violation 'page-has-heading-one' indicates a moderate accessibility issue: screen reader users navigating by heading landmarks cannot identify the primary page purpose. The page title 'Org Chart — CesiumAstro' should have a corresponding visible h1.
- **Fix:** Wrap the main 'Org Chart' text in the center panel (currently displayed as the page headline) in an h1 element. If 'LIVE STRUCTURE' is intended as context, make 'Org Chart' alone the h1 and keep 'LIVE STRUCTURE' as a smaller label above it.
- **Role:** All users, especially those using screen readers or heading navigation
- **Provenance:** voice=`—` · principles=`p-0011`

### P1 — ia · broken
- **Where:** https://ca-org.fly.dev/org-chart (`.product-trigger`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/interactions/org-chart_int0_after.png)
- **Finding:** The product switcher modal (triggered by 'CesiumAstro ORG' button in top-left) displays a card titled 'Organization' with subtitle 'People, reporting lines, business units, staffing, and HR intelligence.' and an 'EDITOR' role badge, but the modal heading reads 'SWITCH PRODUCT' while the centered title says 'CesiumAstro'. This creates confusion about whether the user is switching products or viewing product metadata. The interaction model is unclear: is this a switcher or a product detail view?
- **Fix:** If this is a single-product app, remove the 'SWITCH PRODUCT' heading and rename the button label to 'Product Info' or similar. If multiple products exist, show a list of products with the current one indicated, not a single card modal. Clarify the primary action: viewing metadata vs. switching context.
- **Role:** All users
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0108`

### P1 — interaction · broken
- **Where:** https://ca-org.fly.dev/org-chart (`.org-chart-node`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** Employee cards display expansion indicators ('↓ 10' for 10 direct reports, '↓ 3' for 3 direct reports) but there is no visible affordance showing these are interactive. The chevron-down icon appears as a static label rather than a button. Users cannot tell whether clicking the card, the chevron, or the number will expand the subtree. The 'Collapse' and 'Expand All' buttons in the top bar suggest tree interaction exists, but individual card affordances are missing.
- **Fix:** Make the chevron icon and direct-report count visually distinct as a button (add hover state, change cursor to pointer, increase contrast). Alternatively, add a '+' or 'Expand' button directly on each card that has direct reports. Ensure keyboard users can Tab to the expansion control and activate with Enter/Space.
- **Role:** All users, especially keyboard-only users
- **Provenance:** voice=`—` · principles=`p-0002`, `p-0100`

### P1 — consistency · broken
- **Where:** https://ca-org.fly.dev/org-chart (`.org-chart-node`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** The CEO card (Shey Sabripour) displays '517 people under / 10 DIRECT' while direct-report cards show only the count ('34 people under / 18 DIRECT', '416 people under / 18 DIRECT'). However, cards for individual contributors show 'IL' badge with no '0 people under' text, creating inconsistent information density. Some cards have matrix-reporting arrows ('↗ SPACE SYSTEMS') while others do not, but it's unclear if this is a data difference or a display bug.
- **Fix:** Standardize the card template: all cards should show '[N] people under / [M] DIRECT' if they have reports, or omit both fields if they don't (instead of mixing 'IL' badge with missing count). If matrix reporting is rare, consider showing it only on hover or in a detail panel rather than inline, to reduce visual clutter.
- **Role:** All users
- **Provenance:** voice=`—` · principles=`p-0097`, `p-0111`

### P1 — technical · broken
- **Where:** https://ca-org.fly.dev/org-chart (`network`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** A 403 Forbidden error is logged for '/api/admin/business-units' in the network panel. This suggests the current user (Matthew Eisner, role: editor) does not have permission to fetch business-unit data, but the UI does not surface this failure. If business-unit filtering or context is a planned feature, silent failure leaves users unaware of missing functionality. If the endpoint is unused, the request should not be made.
- **Fix:** If business-unit data is required for full functionality, show an in-app banner: 'Some organization data is unavailable due to permissions. Contact your admin to request access.' If the endpoint is deprecated or not yet implemented, remove the client-side request. If it's a backend error, return a more specific error message and handle it gracefully in the UI.
- **Role:** Editor role (Matthew Eisner); may differ for admin
- **Provenance:** voice=`—` · principles=`p-0106`, `p-0008`

### P1 — accessibility · broken
- **Where:** https://ca-org.fly.dev/employee-directory (`img[alt="Shey Sabripour"]`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/employee-directory_desktop.png)
- **Finding:** All 91 employee avatar images use alt text that duplicates the adjacent visible name text (e.g., alt="Shey Sabripour" immediately next to the clickable "Shey Sabripour" link). This violates WCAG 2.2 AA SC 1.1.1 (image-redundant-alt) and creates redundant announcements for screen reader users, who hear each name twice in succession.
- **Fix:** Set alt="" (empty string) on all avatar images since they are decorative and the name is already present in adjacent text. Alternatively, if avatars convey status or other non-decorative information, include that in the alt (e.g., alt="Profile photo").
- **Provenance:** voice=`—` · principles=`p-0011`

### P1 — interaction · broken
- **Where:** https://ca-org.fly.dev/employee-directory (`th[data-v-0db96779]`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/employee-directory_desktop.png)
- **Finding:** Table column headers (NAME, TITLE, DEPARTMENT, LOCATION, REPORTS TO, REPORTS) appear static and provide no visual affordance that they might be sortable. In data-heavy directory applications, users expect to sort by name, department, or report count. The absence of sort icons or hover states leaves users uncertain whether sorting is supported.
- **Fix:** Add sort affordances to headers: display ascending/descending arrow icons on hover or on the currently-sorted column. On click, sort the table and update the icon to reflect direction. If sorting is not yet implemented, add cursor:pointer and hover underline to signal interactivity, then implement client-side or server-side sorting.
- **Provenance:** voice=`—` · principles=`p-0110`, `p-0100`

### P1 — consistency · broken
- **Where:** https://ca-org.fly.dev/employee-directory (`td:nth-child(5)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/employee-directory_desktop.png)
- **Finding:** The 'REPORTS TO' column displays a mix of full names ('Shey Sabripour', 'Paulson, Brett') and em-dashes ('—') with inconsistent formatting. One row shows 'Shey Sabripour' while others show 'Paulson, Brett' (last name first). This inconsistency suggests either a data-import bug or missing normalization logic, and reduces scannability.
- **Fix:** Normalize all manager names to a single format: either 'First Last' or 'Last, First' throughout. Ensure the display logic consistently applies the same formatting rule to all rows, and validate data imports to catch format mismatches at ingestion time.
- **Provenance:** voice=`—` · principles=`p-0096`, `p-0107`

### P1 — responsive · broken
- **Where:** https://ca-org.fly.dev/employee-directory (`table`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/employee-directory_mobile.png)
- **Finding:** On tablet (768px), the table columns compress but retain all six columns side-by-side, resulting in severe horizontal cramping. The 'REPORTS TO' and 'REPORTS' columns become nearly illegible. On smaller viewports, this layout will fail entirely unless horizontal scroll is introduced, which violates WCAG 1.4.10 (Reflow).
- **Fix:** Implement a responsive table pattern: at 768px and below, hide 'LOCATION', 'REPORTS TO', and 'REPORTS' columns by default, and expose them via expandable row detail panels triggered by tapping a row. Alternatively, switch to a card-based layout where each employee is a card showing name, title, department, with expandable details.
- **Provenance:** voice=`—` · principles=`p-0010`, `p-0058`

### P1 — ux · broken
- **Where:** https://ca-org.fly.dev/employee-directory (`.pagination`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/employee-directory_desktop.png)
- **Finding:** The pagination footer displays 'Showing 1–100 of 518' on the right and '‹ Prev | Page 1 of 6 | Next ›' in the center. The total-count phrasing '1–100 of 518' uses an en-dash that is visually similar to a hyphen, reducing clarity. Additionally, 'Prev' and 'Next' use abbreviated labels that add no space savings and reduce scannability.
- **Fix:** Change 'Showing 1–100 of 518' to 'Showing 1 to 100 of 518' (spelled-out 'to' for clarity). Expand 'Prev' to 'Previous' and ensure both buttons are large enough to meet 24×24px touch-target minimums per WCAG 2.5.8.
- **Provenance:** voice=`—` · principles=`p-0009`, `p-0107`

### P1 — technical · broken
- **Where:** https://ca-org.fly.dev/employee-directory (`network tab`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/employee-directory_desktop.png)
- **Finding:** The page logs a 403 Forbidden error for '/api/admin/business-units' in the network payload. This suggests the current user role (editor) is attempting to fetch data they do not have permission to access. While the page still renders, this error may indicate incomplete role-based access control (RBAC) logic or a data dependency that is silently failing.
- **Fix:** Audit the '/api/admin/business-units' endpoint call: determine if the editor role should have access (and fix permissions), or remove the call for non-admin users. Implement client-side role checks before making admin API requests, and log user-facing error messages if critical data fails to load.
- **Role:** Applies to 'editor' role; may not occur for 'admin' users
- **Provenance:** voice=`—` · principles=`p-0106`

### P1 — consistency · broken
- **Where:** https://ca-org.fly.dev/people (`.person-card:nth-child(11) .name`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_desktop.png)
- **Finding:** The person card for 'Alam, Zane' displays a truncated role title ending with 'Integra' instead of the full 'Communications Payload Integra[tion]'. This inconsistency with other cards (which display complete titles) suggests a CSS or character-limit issue specific to this entry. Users scanning for this person by full title may miss them.
- **Fix:** Investigate CSS overflow settings or character limits on the `.person-card .role` element. Ensure all role titles either wrap to multiple lines or use a consistent truncation pattern with ellipsis (e.g., 'Communications Payload Integ…').
- **Provenance:** voice=`—` · principles=`p-0110`, `p-0107`

### P1 — interaction · additive
- **Where:** https://ca-org.fly.dev/people (`.stat-card`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_desktop.png)
- **Finding:** The four summary stat cards (People: 518, Managers: 62, Departments: 27, Locations: 9) appear purely informational with no interactive affordance. In similar tools (e.g., Linear's project filters, Asana's workspace stats), clicking these cards filters the list below to that subset. Users who expect this pattern will click and receive no feedback.
- **Fix:** Make stat cards clickable filters: clicking 'Managers: 62' filters the list to show only managers, with a visual selected state (border or background accent). Add aria-pressed or aria-selected state and keyboard navigation. Include a 'Clear filters' affordance when any stat is active.
- **Provenance:** voice=`—` · principles=`p-0100`, `p-0107`

### P1 — ia · broken
- **Where:** https://ca-org.fly.dev/people (`.instruction-text`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_desktop.png)
- **Finding:** The instruction text 'Top 24 by report count — start typing to search all 518 people' buries two critical UX facts in one dense sentence: that the default view is sorted by report count (not alphabetical, not department), and that typing triggers a different search mode. Users who don't parse this instruction will assume the list is alphabetically sorted and may miss their target.
- **Fix:** Split into two explicit elements: a visible sort indicator above the results ('Sorted by: Report Count ↓' with dropdown to change sort) and move the search instruction into the placeholder text of the search input itself ('Search by name, title, department, or location').
- **Provenance:** voice=`—` · principles=`p-0110`, `p-0107`

### P1 — responsive · broken
- **Where:** https://ca-org.fly.dev/people (`.person-card-grid`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_mobile.png)
- **Finding:** At tablet width (768px), person cards stack into a single column which is appropriate, but the card height becomes inconsistent due to varying role title lengths. Cards with two-line titles ('Senior Engineering Manager, Mechanical Design') create noticeable vertical rhythm breaks compared to single-line titles ('CEO'), making the list harder to scan.
- **Fix:** Set a fixed or minimum height for person cards at tablet/mobile widths, or normalize title wrapping by setting a fixed line-height and max-height with overflow ellipsis. Alternatively, restructure mobile cards to use a horizontal layout (avatar left, content right) which naturally handles variable text lengths.
- **Provenance:** voice=`—` · principles=`p-0097`, `p-0086`

### P1 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people (`input[placeholder='Search by name or title...']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_desktop.png)
- **Finding:** The search input uses placeholder text as the only label ('Search by name or title…'), which violates WCAG 2.2 Level A Success Criterion 3.3.2 (Labels or Instructions). Placeholders disappear on focus, and screen readers often skip them entirely. Users with cognitive disabilities or screen readers cannot reliably identify the field's purpose once they start typing.
- **Fix:** Add a visually-hidden `<label for="search-input">` element with text like 'Search employees' above the input. Keep the placeholder as supplementary help text. Ensure the label remains programmatically associated with the input via the `for` attribute.
- **Provenance:** voice=`—` · principles=`p-0002`, `p-0008`

### P1 — technical · broken
- **Where:** https://ca-org.fly.dev/people (`network panel`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_desktop.png)
- **Finding:** Console shows a 403 error for `/api/admin/business-units`, indicating a permissions failure or missing auth header. If this endpoint is required for filtering or stat calculations, the page may be loading in a degraded state. If it's not required for this view, the client is making an unnecessary failing request.
- **Fix:** Investigate whether this endpoint is intended to be accessible for the 'editor' role. If not, remove the client-side request logic for non-admin users. If it should be accessible, fix the server-side authorization logic or ensure the client sends the correct auth token.
- **Role:** Viewer is logged in as 'editor'; admins may not see this error
- **Provenance:** voice=`—` · principles=`p-0106`

### P1 — interaction · additive
- **Where:** https://ca-org.fly.dev/people (`.search-results-footer`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_desktop.png)
- **Finding:** The footer text '494 more — type a name, title, department, or location to find them' indicates that most employees are hidden below the fold, but there is no 'Load More' button or infinite scroll behavior. Users must perform a search to access 95% of the directory, which is a significant friction point if they want to browse rather than search.
- **Fix:** Add a 'Load More' or 'Show All' button at the bottom of the initial 24 results. Alternatively, implement infinite scroll with a scroll-progress indicator. For power users, add a 'View All (518)' link that disables pagination entirely.
- **Provenance:** voice=`—` · principles=`p-0108`, `p-0050`

### P1 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people/1001 (`h3[data-v-1db00057]`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1001_desktop.png)
- **Finding:** The 'Direct Reports' heading is an h3, but there is no preceding h2 on the page, creating a non-sequential heading structure. Screen reader users who navigate by heading level expect a logical hierarchy (h1 → h2 → h3), and skipping levels breaks that expectation.
- **Fix:** Change the 'Direct Reports', 'Manager Snapshot', and 'Attachments' headings to h2 elements. If visual hierarchy needs to remain smaller, use CSS to reduce font size rather than using a lower heading level.
- **Provenance:** voice=`—` · principles=`p-0002`

### P1 — ia · broken
- **Where:** https://ca-org.fly.dev/people/1001 (`.sidebar`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1001_desktop.png)
- **Finding:** The left navigation shows 'People Search' as the current page, but the actual page is a person detail view. This creates a mismatch between the nav state and the user's location, making it unclear how to return to the search results or where the user is in the navigation hierarchy.
- **Fix:** Either (1) remove the active state from 'People Search' when viewing a person detail, or (2) add a breadcrumb or parent-page indicator above the person name (e.g. 'People Search > Shey Sabripour') to show the hierarchy. The '← Back to people search' link partially addresses this but should be more prominent.
- **Provenance:** voice=`—` · principles=`p-0106`

### P1 — copy · broken
- **Where:** https://ca-org.fly.dev/people/1001 (`.last-synced-field`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1001_desktop.png)
- **Finding:** The 'LAST SYNCED' timestamp is displayed as a raw ISO 8601 string (2026-04-30T17:08:21.995Z), which is developer-facing format that most users cannot parse. This makes it impossible to quickly assess data freshness without mental translation.
- **Fix:** Format the timestamp as a relative time ('2 hours ago', 'Last updated yesterday') or human-readable absolute time ('Apr 30, 2026 at 5:08 PM'). Reserve the raw ISO string for a tooltip on hover if precise millisecond data is needed for debugging.
- **Provenance:** voice=`—` · principles=`p-0107`

### P1 — interaction · broken
- **Where:** https://ca-org.fly.dev/people/1001 (`.team-list .person-card`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1001_desktop.png)
- **Finding:** Direct report cards in the 'Team' section do not show any hover state or click affordance, making it unclear whether the cards are clickable links to the person's detail page. Users may not realize they can drill down into each report's profile.
- **Fix:** Add a hover state (subtle background color change, border highlight, or shadow) and a cursor:pointer style to each person card. Consider adding a subtle arrow icon (→) in the top-right corner of each card to signal navigation.
- **Provenance:** voice=`—` · principles=`p-0100`

### P1 — responsive · broken
- **Where:** https://ca-org.fly.dev/people/1001 (`.team-list`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1001_mobile.png)
- **Finding:** On tablet (768px), the 'Direct Reports' section switches to a two-column grid, but several cards have long titles ('Chief Propulsion Systems Engineer') that create uneven row heights and visual imbalance. The grid does not adapt gracefully to varying content lengths.
- **Fix:** Either (1) enforce a min-height on all person cards to normalize the grid, (2) truncate long titles with ellipsis and show full title on hover/tap, or (3) switch to a single-column layout at tablet widths to avoid the ragged-grid effect.
- **Provenance:** voice=`—` · principles=`p-0058`, `p-0097`

### P1 — additive_feature · additive
- **Where:** https://ca-org.fly.dev/people/1001 (`.team-list`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1001_desktop.png)
- **Finding:** The 'Direct Reports' list shows 10 reports but provides no way to filter, sort, or search within this list. For users with 50+ direct reports (e.g. a VP-level executive), scrolling through an unsorted list to find a specific person is inefficient.
- **Fix:** Add a small search/filter input above the 'Direct Reports' heading that filters cards in real-time as the user types. Consider adding sort controls (by name, by title, by department) as a dropdown or toggle buttons. This is especially valuable for the 'TOTAL: 517' view if that expands to show all indirect reports.
- **Provenance:** voice=`—` · principles=`p-0110`

### P1 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people/1032 (`h3:contains('Direct Reports')`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1032_desktop.png)
- **Finding:** Heading levels jump from h1 ('Pappas, Trey' in the PERSON PROFILE section) directly to h3 ('Direct Reports'), skipping h2 entirely (axe-core violation: heading-order). This breaks the document outline and confuses screen reader users navigating by heading structure.
- **Fix:** Demote 'Direct Reports' to an h2 element, or insert an h2 between the page h1 and the current h3 to maintain sequential heading hierarchy. Ensure all major sections (TEAM, SPAN, FILES) use h2 tags.
- **Provenance:** voice=`—` · principles=`p-0002`

### P1 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people/1032 (`aside.sidebar`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1032_desktop.png)
- **Finding:** Multiple <aside> landmarks exist on the page without unique accessible names (axe-core violation: landmark-unique). Screen reader users navigating by landmark cannot differentiate between the left sidebar navigation and any other complementary regions.
- **Fix:** Add aria-label attributes to each <aside> to distinguish them (e.g., aria-label="Organization navigation" for the sidebar, aria-label="Manager snapshot" for the span card if it uses aside).
- **Provenance:** voice=`—` · principles=`p-0002`

### P1 — consistency · broken
- **Where:** https://ca-org.fly.dev/people/1032 (`.team-members`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1032_desktop.png)
- **Finding:** Some direct reports display a '3 reports' / '10 reports' / '1 report' subordinate count below their name, while most do not. The inconsistency suggests either incomplete data or a missing visual indicator that some managers have no direct reports (which should be surfaced explicitly).
- **Fix:** For managers with zero reports, display '0 reports' or omit the line entirely but add a consistent visual cue (e.g., a dimmed people-icon or no icon at all). Ensure every manager card renders the subordinate-count field in the same position for scanability.
- **Provenance:** voice=`—` · principles=`p-0097`

### P1 — empty_state · broken
- **Where:** https://ca-org.fly.dev/people/1032 (`.attachments-section`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1032_desktop.png)
- **Finding:** The Attachments section shows a passive empty state ('No attachments yet.') without guiding the user on what to attach or why. This is a missed onboarding opportunity for a feature that likely sees low adoption due to unclear value.
- **Fix:** Replace the empty state with teaching copy: 'Upload contracts, resumes, or offer letters here. Drag files or click to upload.' Consider adding a sample file type (e.g., 'Try uploading Trey's signed offer letter') for first-time editors.
- **Role:** Applies to editors and super-admins; read-only viewers see no upload affordance.
- **Provenance:** voice=`—` · principles=`p-0109`

### P1 — interaction · broken
- **Where:** https://ca-org.fly.dev/people/1032 (`.direct-reports-section h3`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1032_desktop.png)
- **Finding:** The 'Direct Reports' section heading displays a count badge ('18') but the list is truncated to ~17 visible cards in the desktop view, requiring scroll to see the rest. There is no visual indicator (scrollbar, 'Show all' button, pagination) that more reports exist below the fold.
- **Fix:** Add a subtle scrollbar or shadow fade at the bottom of the Direct Reports container to signal additional content, or append a 'Show all 18 reports' expand button if the list is intentionally collapsed. Alternatively, display all reports and let the section naturally scroll.
- **Provenance:** voice=`—` · principles=`p-0106`

### P1 — responsive · broken
- **Where:** https://ca-org.fly.dev/people/1032 (`.manager-snapshot-card`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1032_mobile.png)
- **Finding:** On tablet (768px), the Manager Snapshot card and Attachments card stack vertically but consume equal full-width, making the '5 managers / 13 ICs' stat card feel empty and the Attachments dropzone feel cramped. The desktop 2-column layout is abandoned prematurely.
- **Fix:** Maintain the 2-column layout for SPAN and FILES sections down to 768px width, collapsing to single-column only below 640px. Alternatively, use a 60/40 width split at tablet breakpoint so the denser card (Attachments) gets more horizontal space.
- **Provenance:** voice=`—` · principles=`p-0010`

### P1 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK001 (`h3[data-v-1db00057] (Direct Reports heading)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK001_desktop.png)
- **Finding:** Heading hierarchy is broken: the page jumps from h1 ('Nannetti, Gianni') directly to h3 ('Direct Reports') without an intervening h2. This confuses screen reader users navigating by heading level and signals poor document structure. axe-core flags this as a moderate violation.
- **Fix:** Change 'TEAM' label to an h2, and make 'Direct Reports' an h3 beneath it. Alternatively, demote 'Direct Reports' to h2 if no parent section heading is semantically appropriate.
- **Provenance:** voice=`—` · principles=`p-0002`

### P1 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK001 (`main.person-page, main.content`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK001_desktop.png)
- **Finding:** Two <main> landmarks are present on the page, and one is nested inside an <aside>. axe-core flags this as a moderate violation. Screen reader users navigating by landmark will encounter duplicate 'main' regions, causing confusion about the primary content area.
- **Fix:** Remove the <main> wrapper from 'person-page' or rename it to <article> or <section>. Keep only one <main> element per page, wrapping the entire primary content region (sidebar + person detail).
- **Provenance:** voice=`—` · principles=`p-0002`

### P1 — consistency · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK001 (`.team-member card (Makarov, Alex)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK001_desktop.png)
- **Finding:** One employee card displays initials 'MA' in a badge instead of a portrait photo, while all other cards show photos. This inconsistency is unexplained and looks like missing data. Users may assume the record is incomplete or that the UI failed to load.
- **Fix:** If no portrait is available, apply this fallback treatment consistently (initials badge) to all employees without photos, and consider adding a tooltip explaining 'No photo uploaded'. Alternatively, use a generic avatar silhouette for all missing photos.
- **Provenance:** voice=`—` · principles=`p-0022`

### P1 — copy · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK001 (`.profile-section LAST SYNCED`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK001_desktop.png)
- **Finding:** The 'LAST SYNCED' timestamp is rendered in raw ISO 8601 format (2026-04-30T17:08:23.544Z), which most users cannot parse quickly. This is a developer artifact leaking into the UI and signals unfinished implementation.
- **Fix:** Format this as a relative time ('Synced 2 hours ago') or a localized absolute date ('Synced Apr 30, 2026 at 5:08 PM'). Consider adding a tooltip showing the full ISO timestamp for debugging if needed.
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0022`

### P1 — empty_state · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK001 (`.attachments-section`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK001_desktop.png)
- **Finding:** The 'Attachments' empty state shows passive copy ('No attachments yet.') and a large dashed upload dropzone, but provides no context about what attachments are for or why a user would add one. This is a teaching opportunity missed.
- **Fix:** Replace 'No attachments yet.' with teaching copy: 'Upload performance reviews, onboarding docs, or notes for this employee.' Consider adding a small example list of common attachment types.
- **Role:** Assumes user has upload permissions (editor role).
- **Provenance:** voice=`—` · principles=`p-0106`

### P1 — responsive · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK001 (`.manager-snapshot, .attachments-section on tablet`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK001_mobile.png)
- **Finding:** At tablet width (768px), the 'Manager Snapshot' and 'Attachments' sections stack below the fold, requiring significant scrolling to reach. The desktop layout shows these in a right sidebar, preserving above-the-fold visibility.
- **Fix:** At tablet breakpoint, consider collapsing 'Manager Snapshot' into an accordion or summary card near the top of the page, and deferring 'Attachments' to a secondary tab or modal to prioritize team list visibility.
- **Provenance:** voice=`—` · principles=`p-0010`, `p-0061`

### P1 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people/adp_TWN001 (`main.person-page`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_TWN001_desktop.png)
- **Finding:** The page contains two <main> landmarks (one wrapping the entire content area, one wrapping the person-page), and the person-page main is nested inside the outer main. Axe flags this as a moderate violation; screen reader users navigating by landmark will encounter ambiguous structure and may skip content.
- **Fix:** Remove the redundant inner <main class='person-page'> and replace it with <section> or <article>. The outer <main class='content'> should be the only main landmark on the page.
- **Role:** Applies to all viewer roles.
- **Provenance:** voice=`—` · principles=`p-0002`

### P1 — accessibility · broken
- **Where:** https://ca-org.fly.dev/people/adp_TWN001 (`aside.sidebar`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_TWN001_desktop.png)
- **Finding:** Two <aside> elements (left sidebar and possibly another complementary region) share the same role without unique accessible names, violating WCAG 1.3.1. Screen reader users navigating by landmark will hear 'complementary' twice with no distinguishing label, forcing manual exploration to determine which is which.
- **Fix:** Add aria-label='Organization navigation' to the sidebar <aside> and aria-label='Profile details' (or similar) to the other complementary region if one exists. Alternatively, ensure only one <aside> is present and wrap other secondary content in <section>.
- **Role:** Applies to all viewer roles.
- **Provenance:** voice=`—` · principles=`p-0002`

### P1 — copy · broken
- **Where:** https://ca-org.fly.dev/people/adp_TWN001 (`.profile-card .last-synced`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_TWN001_desktop.png)
- **Finding:** The 'LAST SYNCED' timestamp displays as a raw ISO 8601 string ('2026-04-30T17:08:27.380Z'), which is unreadable and lacks timezone context for users. This is a developer field that leaked into the UI without formatting. Users cannot determine recency at a glance.
- **Fix:** Format the timestamp as a relative time string ('Synced 2 hours ago') or absolute local time ('Apr 30, 2026 at 10:08 AM PDT'). Use a library like date-fns or Intl.DateTimeFormat to respect the user's locale and timezone.
- **Role:** Applies to all viewer roles.
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0032`

### P1 — ia · broken
- **Where:** https://ca-org.fly.dev/people/adp_TWN001 (`.person-profile .reports-through`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_TWN001_desktop.png)
- **Finding:** The 'REPORTS THROUGH' chain in the top-right profile card is duplicated in the 'MANAGER' field in the left profile card, creating redundant navigation paths and visual clutter. Users see 'Pappas, Trey' in two places within 400px of each other with no clear functional difference.
- **Fix:** Remove the 'REPORTS THROUGH' element from the top-right card and consolidate all hierarchical metadata (manager, location, department) into the left profile card. If showing the full reporting chain is important, expand the left card's 'MANAGER' field to display multi-level paths only there.
- **Role:** Applies to all viewer roles.
- **Provenance:** voice=`—` · principles=`p-0111`, `p-0107`

### P1 — empty_state · broken
- **Where:** https://ca-org.fly.dev/people/adp_TWN001 (`.attachments-card .empty-state`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_TWN001_desktop.png)
- **Finding:** The Attachments empty state says 'No attachments yet.' below a drop zone, but provides no context on what attachments are for or what users should upload. This is a passive empty state that misses the opportunity to teach users the feature's purpose (résumés? contracts? performance reviews?).
- **Fix:** Replace 'No attachments yet.' with teaching copy: 'Upload résumés, contracts, or performance reviews for Wang, Ben. Accepted formats: PDF, DOCX, TXT — up to 30 MB each.' This positions the feature as a document repository with clear use cases.
- **Role:** Most relevant to editors and super-admins who manage profiles.
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0043`

### P1 — technical · broken
- **Where:** https://ca-org.fly.dev/people/adp_TWN001 (`network: /api/admin/business-units`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_TWN001_desktop.png)
- **Finding:** Console shows a 403 error for /api/admin/business-units, indicating a failed API call that likely populates the 'Organization' dropdown in the product switcher. The dropdown may be broken or showing stale data for non-admin users, but the UI provides no error message to explain the failure.
- **Fix:** If the user lacks permission to view business units, either suppress the API call entirely or display a graceful 'Not available for your role' message in the dropdown. Failing silently in the console while showing potentially incomplete data erodes trust in the system's accuracy.
- **Role:** Likely affects viewers without admin permissions.
- **Provenance:** voice=`—` · principles=`p-0108`, `p-0106`

### P1 — copy · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK004 (`.profile-card .last-synced`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK004_desktop.png)
- **Finding:** The 'LAST SYNCED' timestamp displays as an ISO 8601 string ('2026-04-30T17:08:26.518Z') instead of a human-readable format. This raw developer output reduces user confidence that the data is current and well-maintained.
- **Fix:** Format as relative time ('2 hours ago', 'Last synced April 30, 2026 at 5:08 PM') or at minimum as a localized datetime string without milliseconds. Consider showing relative time by default with full timestamp on hover.
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0022`

### P1 — ia · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK004 (`.person-page main`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK004_desktop.png)
- **Finding:** The page contains two <main> landmarks (one for .person-page, one for .content), violating WCAG landmark uniqueness rules and causing screen reader confusion about the page's primary content region.
- **Fix:** Remove the <main> tag from either .person-page or .content. The outer .content container should likely be a <div>, with .person-page remaining as <main>.
- **Provenance:** voice=`—` · principles=`p-0002`

### P1 — ia · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK004 (`aside.sidebar`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK004_desktop.png)
- **Finding:** Two <aside> elements (the left navigation sidebar and likely the user menu) have no distinguishing aria-label or role/label combination, violating WCAG landmark uniqueness. Screen reader users cannot differentiate them when navigating by landmark.
- **Fix:** Add aria-label="Main navigation" to the left sidebar <aside> and aria-label="User account menu" to the user menu <aside> (or whatever descriptive label matches its content).
- **Provenance:** voice=`—` · principles=`p-0002`, `p-0107`

### P1 — empty_state · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK004 (`.direct-reports-section`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK004_desktop.png)
- **Finding:** The 'No direct reports' empty state is purely passive — it states the absence of data without explaining whether this is expected or how to add direct reports if relevant. Users with edit permissions have no next action.
- **Fix:** If the viewer is a manager or HR admin, add copy like 'No direct reports yet. Assign employees via [Employee Directory link] or your HRIS sync.' If the viewer lacks permissions, the current passive state is acceptable but should clarify 'This employee has no direct reports.'
- **Role:** Improvement applies primarily to editors/managers; read-only users see acceptable passive state
- **Provenance:** voice=`—` · principles=`p-0106`, `p-0073`

### P1 — technical · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK004 (`console / network`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK004_desktop.png)
- **Finding:** A 403 error on /api/admin/business-units is logged in the console and network log. This suggests a failed permissions check or missing backend resource that may be blocking a feature (likely the 'Switch Product' dropdown in the OPERATIONS ATLAS menu, which attempts to load business units). The user sees no error message, so the failure is silent.
- **Fix:** Add proper error handling that either (a) suppresses the request if the user lacks permissions, or (b) shows a user-facing message if business units are required for the UI to function. Investigate why the request fires for a non-admin user.
- **Role:** Likely fires for non-admin users who don't need business-unit data; admin users may see it succeed
- **Provenance:** voice=`—` · principles=`p-0106`, `p-0108`

### P1 — consistency · broken
- **Where:** /people/{ID} (`h1`)
- **Finding:** Heading name format is inconsistent across the /people/{ID} template. 1 pages use 'firstname-lastname', but 1 use a different format (e.g. 'Pappas, Trey'). Pick one and apply it everywhere.
- **Fix:** Normalize to 'firstname-lastname' on every page in this template, or document which records are intentionally different and why.
- **Provenance:** voice=`—` · principles=`p-recognition`

### P2

### P2 — typography · broken
- **Where:** https://ca-org.fly.dev/org-chart (`.org-chart-node`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** Employee cards in the org chart show inline role badges (IL = Individual Contributor, PB = ?, 10 DIRECT, etc.) but these abbreviations are not defined anywhere visible. First-time users cannot decode 'IL', 'PB', or the downward-arrow-with-number pattern without guessing or asking. The 'IL' badge appears on multiple cards (Caponio, Carwell, Conwell, Dadic) but its meaning is implicit.
- **Fix:** Add a legend/key toggle button in the top control bar next to 'Org', 'Collapse', 'Expand All' that reveals a tooltip or drawer explaining each badge type: 'IL = Individual Contributor', 'PB = [meaning]', '↓ N = N Direct Reports', '↗ SPACE SYSTEMS = Matrix reporting'. Alternatively, use full-word badges on hover or expand.
- **Role:** New users or infrequent viewers
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0110`

### P2 — responsive · broken
- **Where:** https://ca-org.fly.dev/org-chart (`.org-chart-viewport`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/org-chart_mobile.png)
- **Finding:** On tablet (768px), the org chart truncates the rightmost employees (Carwell, Conwell, Dadic are cut off) without horizontal scroll affordance or indication that more content exists off-screen. The zoom controls ('Fit', '58%', '-', '+') are present but do not solve discoverability: users cannot see that content is clipped. The desktop view (1440px) shows 11 employees in the second row; tablet shows only 6 fully visible.
- **Fix:** Add a subtle horizontal scroll indicator (gradient fade at edges, or horizontal scrollbar that appears on hover/touch). Alternatively, adjust the 'Fit' button default behavior to ensure all nodes are visible within viewport on load for tablet widths. Consider a two-finger pinch-zoom gesture for touch devices with a toast message on first load: 'Pinch to zoom, drag to pan'.
- **Role:** All users on tablet/mobile devices
- **Provenance:** voice=`—` · principles=`p-0010`, `p-0106`

### P2 — copy · broken
- **Where:** https://ca-org.fly.dev/org-chart (`.org-chart-node`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** The 'PB' badge on Paulson, Brett's card is unexplained and appears nowhere else in the visible org chart. Unlike 'IL' (which appears on multiple cards and can be inferred as 'Individual Contributor' by pattern), 'PB' is a singleton abbreviation. This could be initials, a role code, or a data error — users cannot distinguish without a legend or hover tooltip.
- **Fix:** If 'PB' is a role/project badge, add it to the legend (see f-0004). If it is a data artifact or debug string, remove it. If it represents a unique attribute (e.g. 'Project Bridge' or 'Principal Architect'), spell it out or add a tooltip on hover: '[PB] = Project Bridge Lead'.
- **Role:** All users
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0032`

### P2 — additive_feature · additive
- **Where:** https://ca-org.fly.dev/org-chart (`.org-chart-controls`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** The control bar offers 'Collapse' and 'Expand All' but lacks a 'Reset View' or 'Center on CEO' button. If a user zooms/pans and loses their place, the only recovery path is manual panning or clicking 'Fit' (which adjusts zoom but may not center the root node). Similar tools (Lucidchart, Miro, Figma) provide a 'Reset to Default View' action.
- **Fix:** Add a 'Center' or 'Reset View' button that resets zoom to default (e.g. 58% or 'Fit') and centers the viewport on the root node (Shey Sabripour). Place it in the control bar between 'Expand All' and the zoom controls. Keyboard shortcut: '0' (zero) or 'Home' key.
- **Role:** All users
- **Provenance:** voice=`—` · principles=`p-0108`, `p-0110`

### P2 — additive_feature · additive
- **Where:** https://ca-org.fly.dev/org-chart (`.org-chart-node`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** Employee cards are linked (clicking a name navigates to /people/[id]) but there is no visual indication that cards are clickable beyond the name being a different color. Competing org tools (ChartHop, Lattice, Hibob) add a hover state (shadow lift, border highlight) to the entire card to signal interactivity. Without this, users may not discover the click behavior.
- **Fix:** Add a hover state to the entire employee card: subtle box-shadow increase, border color change, or background lightening. Ensure the cursor changes to pointer on hover over the entire card, not just the name link. For keyboard users, ensure Tab focus on a card shows a clear focus ring around the entire card boundary.
- **Role:** All users
- **Provenance:** voice=`—` · principles=`p-0003`, `p-0100`

### P2 — additive_feature · additive
- **Where:** https://ca-org.fly.dev/org-chart (`.org-chart-controls`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** The org chart has no visible export or share functionality. Users who need to present the chart in a meeting or document cannot easily capture a clean view (screenshot tools will include the sidebar and browser chrome). Competing tools (Lucidchart, Miro, OrgWeaver) offer 'Export as PNG/PDF' or 'Share Link' buttons.
- **Fix:** Add an 'Export' button in the control bar that generates a PNG or PDF of the current visible org chart view (respecting zoom level and expansion state). Alternatively, add a 'Copy Shareable Link' button that encodes the current view state in a URL parameter (e.g. ?zoom=58&expanded=1001,1032) so recipients see the same view.
- **Role:** All users with sharing needs (managers, HR, exec assistants)
- **Provenance:** voice=`—` · principles=`p-0074`

### P2 — ia · broken
- **Where:** https://ca-org.fly.dev/employee-directory (`.org-nav a[href='/employee-directory'], .org-nav a[href='/people']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/employee-directory_desktop.png)
- **Finding:** The left navigation exposes both 'Employee Directory' and 'People Search' as separate links, but the payload shows '/people' and '/employee-directory' URLs with no clear functional distinction documented. Users are forced to click both to learn the difference, creating unnecessary friction in a tool meant for quick lookups.
- **Fix:** Add hover tooltips or adjacent help text explaining the difference (e.g., 'Employee Directory: Browse by department' vs 'People Search: Find by keyword'). If the pages serve the same purpose, consolidate them into a single view with tabbed or toggled modes.
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0110`

### P2 — copy · broken
- **Where:** https://ca-org.fly.dev/employee-directory (`.hero-description`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/employee-directory_desktop.png)
- **Finding:** The subheadline 'Search the org, slice by department or location, and jump directly into a person profile' uses informal, conversational phrasing ('slice', 'jump directly into') that may feel out of place in an enterprise HR tool context. While approachable, it does not match the formal tone of other enterprise org tools.
- **Fix:** Revise to professional phrasing: 'Search the directory, filter by department or location, and view detailed employee profiles.' This maintains clarity while aligning with the tone expected in internal HR/people systems.
- **Provenance:** voice=`—` · principles=`p-0107`

### P2 — additive_feature · additive
- **Where:** https://ca-org.fly.dev/employee-directory (`table`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/employee-directory_desktop.png)
- **Finding:** The directory lacks inline contact actions (email, Teams/Slack link, calendar) within each row. Users who want to reach out to an employee must click through to the profile, copy the email, and return — a multi-step flow that breaks momentum in a tool designed for rapid lookups.
- **Fix:** Add icon buttons in each row for common actions: 'Email' (mailto: link), 'Message' (if integrated with Slack/Teams), and 'View Profile'. Place these in a new rightmost column labeled 'ACTIONS'. This reduces clicks-to-contact from 3+ to 1.
- **Provenance:** voice=`—` · principles=`p-0071`, `p-0108`

### P2 — additive_feature · additive
- **Where:** https://ca-org.fly.dev/employee-directory (`.filter-controls`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/employee-directory_desktop.png)
- **Finding:** The department and location filters are single-select dropdowns, which forces users to choose one value at a time. In organizations with matrixed teams or remote employees spanning multiple offices, users may want to filter 'Software OR Manufacturing' or 'Austin OR Remote' simultaneously. The current UI does not support multi-select filtering.
- **Fix:** Convert the department and location filters to multi-select dropdowns (e.g., using checkboxes within the dropdown menu). Display selected filters as removable tags above the table. Add a 'Clear filters' button to reset all selections at once.
- **Provenance:** voice=`—` · principles=`p-0071`, `p-0101`

### P2 — interaction · additive
- **Where:** https://ca-org.fly.dev/people (`.person-card`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_desktop.png)
- **Finding:** Person cards show report count badges ('39 reports', '21 reports') but clicking the badge performs the same action as clicking anywhere else on the card (navigating to the person's detail page). Users familiar with org tools like ChartHop or Lattice expect clicking the report count to expand an inline direct-reports preview or navigate directly to that person's org chart view.
- **Fix:** Make the report-count badge a separate interactive target: clicking it opens the person's Org Chart view filtered to show their direct reports. Add a tooltip on hover ('View 39 direct reports') and ensure the badge has distinct :hover and :focus states separate from the parent card.
- **Provenance:** voice=`—` · principles=`p-0110`, `p-0100`

### P2 — copy · broken
- **Where:** https://ca-org.fly.dev/people (`.page-description`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_desktop.png)
- **Finding:** The description 'Search for anyone in the organization to open their full profile, reporting chain, GA hours, and staffing allocations' uses the acronym 'GA hours' without definition. Users unfamiliar with this internal term (likely meaning 'General Availability' or 'Generally Allocated') must guess its meaning or ignore the feature.
- **Fix:** Either spell out the acronym on first use ('GA (General Availability) hours') or replace with plain language ('availability hours', 'scheduled hours'). If GA is a specific product term, add a tooltip or help icon next to it.
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0022`

### P2 — polish · additive
- **Where:** https://ca-org.fly.dev/people (`.person-card .avatar`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_desktop.png)
- **Finding:** Several person cards show generic avatar placeholders (single-letter initials or silhouettes) instead of profile photos. While functionally acceptable, this reduces visual scanability — users who recognize colleagues by face must read every name. Competitors like Lattice and BambooHR make photo upload a high-visibility prompt.
- **Fix:** Add a gentle prompt or banner for users without profile photos: 'Help your team recognize you — add a profile photo'. For admins viewing this page, consider adding a batch-upload flow or highlighting incomplete profiles in an 'Onboarding Tasks' dashboard section.
- **Role:** Applies to end-users without photos and admins managing onboarding completeness
- **Provenance:** voice=`—` · principles=`p-0110`, `p-0097`

### P2 — typography · broken
- **Where:** https://ca-org.fly.dev/people (`.person-card .department-tag`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_desktop.png)
- **Finding:** Department tags (e.g., 'Digital/Mixed Signal', 'Systems Eng Integration & Test', 'Remote / Offsite') use inconsistent text sizing and truncation behavior. Some are displayed at full width while others appear compressed or abbreviated, creating visual noise. The styling does not clearly distinguish department from location tags.
- **Fix:** Standardize tag typography: use a single text size (e.g., 12px), set max-width with ellipsis overflow, and differentiate department vs. location tags with subtle color or icon differences (e.g., location tags in muted grey, department tags in brand accent color).
- **Provenance:** voice=`—` · principles=`p-0096`, `p-0097`

### P2 — consistency · broken
- **Where:** https://ca-org.fly.dev/people/1001 (`.team-list`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1001_desktop.png)
- **Finding:** Most direct reports show avatars with photos, but 'Paulson, Brett' shows only initials ('PB') on a colored background. This inconsistency is visually jarring and may signal incomplete data entry, even if the user simply hasn't uploaded a photo.
- **Fix:** Ensure all avatar placeholders use a consistent visual treatment (e.g. all initials on colored backgrounds, or a default silhouette icon). If photos are preferred, add a tooltip or indicator on the 'PB' avatar encouraging the user to upload a photo ('Click to add photo').
- **Provenance:** voice=`—` · principles=`p-0022`

### P2 — typography · broken
- **Where:** https://ca-org.fly.dev/people/1001 (`.person-card .title`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1001_desktop.png)
- **Finding:** The person's name and title within each direct-report card have nearly identical visual weight (both appear to be ~14-15px, similar color), making it difficult to quickly scan the list for names vs. roles. The name should be the dominant element.
- **Fix:** Increase the font-weight of the name (font-weight: 600) and/or increase its size by 2px relative to the title. Reduce the opacity of the title line to 0.7 to create secondary hierarchy, per Refactoring UI's 'de-emphasize with color' pattern.
- **Provenance:** voice=`—` · principles=`p-0093`, `p-0094`

### P2 — additive_feature · additive
- **Where:** https://ca-org.fly.dev/people/1001 (`.span-card`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1001_desktop.png)
- **Finding:** The 'Manager Snapshot' card shows MANAGERS: 6 and ICS: 4 but provides no explanation of what 'ICS' means (likely 'Individual Contributors'). This acronym is not universally known and may confuse new users or external stakeholders viewing the tool.
- **Fix:** Spell out 'Individual Contributors' in full, or add a small info icon (ⓘ) next to 'ICS' that reveals a tooltip on hover: 'Individual Contributors — employees with no direct reports.' Consider adding a brief explainer of the snapshot metrics as a collapsed accordion under the card.
- **Provenance:** voice=`—` · principles=`p-0107`

### P2 — copy · broken
- **Where:** https://ca-org.fly.dev/people/1032 (`.external-id-field`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1032_desktop.png)
- **Finding:** The 'EXTERNAL ID' field displays '1032' without context. Users unfamiliar with the internal HR system won't know if this is an ADP ID, a badge number, or another identifier. The label is technically accurate but assumes insider knowledge.
- **Fix:** Rename the label to match the source system (e.g., 'ADP ID', 'Employee Number', 'Workday ID') or add helper text below the value explaining what the number represents. If multiple ID systems coexist, consider a format like 'External ID (ADP): 1032'.
- **Provenance:** voice=`—` · principles=`p-0107`

### P2 — copy · broken
- **Where:** https://ca-org.fly.dev/people/1032 (`.last-synced-field`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1032_desktop.png)
- **Finding:** The 'LAST SYNCED' timestamp is displayed as '2026-04-30T17:08:22.112Z' in raw ISO 8601 format. This is unreadable for non-technical users and provides no indication of timezone or relative recency (e.g., '2 hours ago').
- **Fix:** Format the timestamp in a human-readable format: 'April 30, 2026 at 5:08 PM UTC' or 'Synced 2 hours ago'. If the application serves multiple timezones, display the time in the user's local timezone with a timezone label.
- **Provenance:** voice=`—` · principles=`p-0107`

### P2 — typography · broken
- **Where:** https://ca-org.fly.dev/people/1032 (`.person-card .title`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1032_desktop.png)
- **Finding:** Job titles in the Direct Reports cards (e.g., 'Vice President, Business Development & Govern') are truncated mid-word without ellipsis or tooltip. This happens on 'Myhill, Robert' where 'Government' is cut to 'Govern', making the title ambiguous.
- **Fix:** Apply CSS text-overflow: ellipsis and a title attribute (or tooltip on hover) to the title field so users can read the full text. Alternatively, allow the title to wrap to two lines with a max-height constraint.
- **Provenance:** voice=`—` · principles=`p-0085`

### P2 — additive_feature · additive
- **Where:** https://ca-org.fly.dev/people/1032 (`.person-card`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_1032_desktop.png)
- **Finding:** The Direct Reports list shows name, title, department, and location for each person, but does not display tenure, start date, or employment type (FTE/contractor). Similar org tools (BambooHR, Lattice) expose these fields to help managers quickly identify new hires or contractors during planning.
- **Fix:** Add a small badge or secondary metadata line to each person card showing 'Started Apr 2024' or 'Contractor • 6 months' if that data is available in the system. Make it collapsible or toggleable via a 'Show details' checkbox in the section header if density is a concern.
- **Role:** Relevant for managers and HR; may not apply to peer viewers.
- **Provenance:** voice=`—` · principles=`p-0110`

### P2 — ia · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK001 (`.profile-section, .person-profile-section`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK001_desktop.png)
- **Finding:** The left panel heading reads 'PROFILE' and the right panel heading reads 'PERSON PROFILE', both describing the same entity. This redundancy suggests unclear information architecture and could confuse users scanning the layout.
- **Fix:** Rename left panel to 'Details' or 'Summary' and right panel to 'Team & Reporting' to clarify each section's purpose. Alternatively, merge semantically redundant sections if they serve the same function.
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0111`

### P2 — interaction · additive
- **Where:** https://ca-org.fly.dev/people/adp_UK001 (`.team-member cards in Direct Reports section`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK001_desktop.png)
- **Finding:** The list of 12 direct reports is displayed as a flat vertical stack with no grouping, sorting, or filtering controls. In orgs with larger teams (20+ reports), this list becomes unwieldy and unscannable.
- **Fix:** Add sortable column headers (by name, title, location) or filter chips (by department, location) above the list. Consider grouping by team or seniority level if those fields are available.
- **Provenance:** voice=`—` · principles=`p-0110`, `p-0101`

### P2 — typography · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK001 (`Labels like 'DIRECT', 'TOTAL', 'MANAGER', 'LOCATION', 'DEPARTMENT'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK001_desktop.png)
- **Finding:** All-caps labels ('DIRECT', 'TOTAL', 'MANAGER') are used inconsistently for field labels. Some sections (left profile) use all-caps, while others (right panel) use title case. This creates visual noise and reduces readability.
- **Fix:** Standardize on either title case (better readability) or all-caps (stronger hierarchy) across all field labels. If using all-caps, reduce font size or weight to prevent shouting effect.
- **Provenance:** voice=`—` · principles=`p-0096`, `p-0093`

### P2 — additive_feature · additive
- **Where:** https://ca-org.fly.dev/people/adp_UK001 (`.team-member cards`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK001_desktop.png)
- **Finding:** Each direct report card shows title and location but omits tenure, last review date, or performance indicators. Similar tools (BambooHR, Lattice) surface this context inline to help managers prioritize 1:1s and spot flight risk.
- **Fix:** Add a small metadata line to each card: 'Hired Jan 2024 · Last review: Dec 2024'. Consider adding a visual indicator (dot, badge) for employees due for review or nearing tenure milestones.
- **Role:** Assumes viewer is a manager or HR admin with access to performance data.
- **Provenance:** voice=`—` · principles=`p-0110`

### P2 — typography · broken
- **Where:** https://ca-org.fly.dev/people/adp_TWN001 (`.profile-card .section-label`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_TWN001_desktop.png)
- **Finding:** Section labels ('PORTRAIT', 'PERSON PROFILE', 'TEAM', 'SPAN', 'FILES') use all-caps styling without reduced tracking (letter-spacing), making them feel visually cramped and harder to scan. Desktop screenshots show labels like 'REPORTS THROUGH' and 'MANAGER' tightly packed.
- **Fix:** Add letter-spacing: 0.05em to all-caps labels to improve readability and visual rhythm. This is a standard typographic adjustment for uppercase text and will make section headers feel more polished.
- **Role:** Applies to all viewer roles.
- **Provenance:** voice=`—` · principles=`p-0096`, `p-0086`

### P2 — responsive · broken
- **Where:** https://ca-org.fly.dev/people/adp_TWN001 (`.manager-snapshot`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_TWN001_mobile.png)
- **Finding:** On tablet view (768px), the 'Manager Snapshot' card displays 'MANAGERS: 0' and 'ICS: 1' side-by-side, but 'ICS' is an unexplained abbreviation that likely means 'Individual Contributors'. This label is unclear for non-HR users and lacks hover explanation or help text.
- **Fix:** Change 'ICS' to 'Individual Contributors' or add a tooltip on hover that explains 'ICS = Individual Contributors'. If space is constrained on mobile, use 'ICs' (common HR shorthand) instead of 'ICS'.
- **Role:** Applies to all viewer roles.
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0032`

### P2 — interaction · additive
- **Where:** https://ca-org.fly.dev/people/adp_TWN001 (`.direct-reports .employee-card`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_TWN001_desktop.png)
- **Finding:** The 'Direct Reports' section shows one employee card (Chang, Charles) with no visible click target or hover state. Users cannot tell if the card is clickable to view Chang's profile. Similar org-chart tools (Pingboard, BambooHR, ChartHop) make employee cards visually interactive.
- **Fix:** Add a hover state (subtle border color change or shadow lift) to the employee card to signal clickability, and make the entire card a clickable link to Chang's profile page. Ensure the card also responds to keyboard focus with a visible outline.
- **Role:** Applies to all viewer roles.
- **Provenance:** voice=`—` · principles=`p-0100`, `p-0003`

### P2 — consistency · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK004 (`.person-profile-card, .profile-card`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK004_desktop.png)
- **Finding:** The employee's name, title, and org location appear in three places (PORTRAIT card, PERSON PROFILE card upper-right, PROFILE card lower-left), but with slight formatting differences. The PERSON PROFILE version uses 'Waveform · Milton Keynes' with a middot separator, while the PROFILE card lists 'Waveform' under DEPARTMENT and 'Milton Keynes' under LOCATION as separate fields. This inconsistency suggests accidental duplication rather than intentional progressive disclosure.
- **Fix:** Remove the redundant PERSON PROFILE card in the upper-right if the detailed PROFILE card below always displays the same data, or clarify their distinct purposes. If PERSON PROFILE is a persistent sidebar summary, ensure it uses identical field formatting to the detailed card.
- **Provenance:** voice=`—` · principles=`p-0111`, `p-0096`

### P2 — interaction · broken
- **Where:** https://ca-org.fly.dev/people/adp_UK004 (`.reports-through a`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK004_desktop.png)
- **Finding:** The 'REPORTS THROUGH' chain (Shey Sabripour → Paulson, Brett → Nannetti, Gianni) displays as hyperlinks, but the interaction model is unclear: clicking navigates to each person's profile, but there's no visual affordance (underline, icon, hover state visible in screenshots) to signal this. Users may not realize the chain is interactive.
- **Fix:** Add a subtle underline or change link color on hover to signal interactivity. Consider adding a tooltip on hover that says 'View [Name]'s profile' to clarify the action.
- **Provenance:** voice=`—` · principles=`p-0100`, `p-0011`

### P2 — additive_feature · additive
- **Where:** https://ca-org.fly.dev/people/adp_UK004 (`.person-page`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK004_desktop.png)
- **Finding:** The page shows DIRECT reports count (0) but does not surface TOTAL reports (also 0 in this case, but the field exists). For managers with indirect reports (reports-of-reports), showing 'Direct: 0, Total: 5' would clarify their span of influence. This is common in similar tools (BambooHR, Lattice).
- **Fix:** Add a 'Total Reports: N' line under 'Direct Reports: N' in the TEAM section. If Total = Direct, show only one line to avoid redundancy.
- **Provenance:** voice=`—` · principles=`p-0106`, `p-0072`

### P2 — additive_feature · additive
- **Where:** https://ca-org.fly.dev/people/adp_UK004 (`.attachments-section`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-134212-ca-org/screenshots/people_adp_UK004_desktop.png)
- **Finding:** The Attachments dropzone accepts 'PDF, DOCX, TXT — up to 30 MB each' but provides no examples of what documents are typically uploaded here (onboarding forms, contracts, performance reviews, certifications). New users may hesitate to use the feature without this context.
- **Fix:** Add helper text under the file-type line: 'Examples: offer letters, performance reviews, certifications, training records.' This guides usage without constraining it.
- **Role:** Applies to editors who can upload files
- **Provenance:** voice=`—` · principles=`p-0107`, `p-0076`
