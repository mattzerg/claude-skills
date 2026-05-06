# Fake Matt feedback — https://zergboard-preview.pages.dev

_Reviewed 2026-05-04 14:02; 8 pages, 56 findings (2 rejected for missing provenance)._

**Severity:** P0=11 · P1=29 · P2=16

## If I only fix three things
- 18 elements fail WCAG AA contrast requirements (4.5:1 for normal text, 3:1 for large text). Most violations appear in the interactive board preview section where beige/cream text on light backgrounds renders labels and card metadata nearly unreadable. This directly blocks users with low vision and creates legal risk.
  - **Fix:** Audit all text in the board preview section. Replace beige (#E8DCC8 or similar) with a color that meets 4.5:1 against its background. For the 'Backlog 8' column header and similar elements, either darken the text to at least #6B5D4F or lighten the background. Run axe DevTools to verify all violations are resolved.
- Two POST requests to /api/event fail with 405 Method Not Allowed and ERR_ABORTED. If this endpoint is intended for analytics or conversion tracking, the failure means no visitor behavior data is being collected, making it impossible to measure feature-page effectiveness or attribute signups to this page.
  - **Fix:** Verify the /api/event endpoint exists and accepts POST requests. If this is a preview environment limitation, add environment detection to skip analytics calls on *.pages.dev domains. If the endpoint should exist, check CORS configuration and ensure the method is allowed in the route handler.
- Zero customer logos, quantified adoption metrics, or third-party validation appear anywhere on the page. Every competitor in the PM tool space (Linear, Asana, Jira, ClickUp, Monday) displays named enterprise logos or user counts within the first viewport. Absence of social proof forces visitors to trust claims about speed, API completeness, and CISO approval without external validation, which directly suppresses trial conversion among skeptical buyers.
  - **Fix:** Add a trust band immediately below the hero with 4–6 recognizable customer logos (if available) or quantified metrics ('Trusted by 12,000+ engineering teams' or 'Processing 8M API calls/day'). If you lack named customers, use proxy signals: 'Built by the team behind [credible prior product]' or 'SOC 2 Type II certified since [date]' with certification badge.

## All findings

### P0 — accessibility
- **Where:** https://zergboard-preview.pages.dev/features (`.col-head, .card, .workspace-item`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** 18 elements fail WCAG AA contrast requirements (4.5:1 for normal text, 3:1 for large text). Most violations appear in the interactive board preview section where beige/cream text on light backgrounds renders labels and card metadata nearly unreadable. This directly blocks users with low vision and creates legal risk.
- **Fix:** Audit all text in the board preview section. Replace beige (#E8DCC8 or similar) with a color that meets 4.5:1 against its background. For the 'Backlog 8' column header and similar elements, either darken the text to at least #6B5D4F or lighten the background. Run axe DevTools to verify all violations are resolved.
- **Provenance:** voice=`None` · principles=`p-0001`, `p-0095`

### P0 — technical
- **Where:** https://zergboard-preview.pages.dev/api/event (`Network panel`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** Two POST requests to /api/event fail with 405 Method Not Allowed and ERR_ABORTED. If this endpoint is intended for analytics or conversion tracking, the failure means no visitor behavior data is being collected, making it impossible to measure feature-page effectiveness or attribute signups to this page.
- **Fix:** Verify the /api/event endpoint exists and accepts POST requests. If this is a preview environment limitation, add environment detection to skip analytics calls on *.pages.dev domains. If the endpoint should exist, check CORS configuration and ensure the method is allowed in the route handler.
- **Provenance:** voice=`q-0014` · principles=`p-0106`

### P0 — social_proof
- **Where:** https://zergboard-preview.pages.dev/features (`Hero section (no trust band present)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** Zero customer logos, quantified adoption metrics, or third-party validation appear anywhere on the page. Every competitor in the PM tool space (Linear, Asana, Jira, ClickUp, Monday) displays named enterprise logos or user counts within the first viewport. Absence of social proof forces visitors to trust claims about speed, API completeness, and CISO approval without external validation, which directly suppresses trial conversion among skeptical buyers.
- **Fix:** Add a trust band immediately below the hero with 4–6 recognizable customer logos (if available) or quantified metrics ('Trusted by 12,000+ engineering teams' or 'Processing 8M API calls/day'). If you lack named customers, use proxy signals: 'Built by the team behind [credible prior product]' or 'SOC 2 Type II certified since [date]' with certification badge.
- **Provenance:** voice=`q-0007` · principles=`p-0019`, `p-0048`

### P0 — accessibility
- **Where:** https://zergboard-preview.pages.dev/pricing (`.name (Free tier header, Team tier header, and 7 other elements)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/pricing_html_desktop.png)
- **Finding:** Nine elements fail WCAG AA contrast ratio requirements (4.5:1 for normal text). The axe violation identifies tier name headers and other text elements that are insufficiently distinct from their backgrounds. This is particularly problematic on the pricing cards where the cream/beige background reduces the effective contrast of grey text.
- **Fix:** Darken all text that currently fails contrast to meet 4.5:1 minimum. For the tier card headers ('Free', 'Team', 'Business'), use #1f2937 or darker instead of the current lighter grey. For feature list text, ensure at least #374151. Run axe DevTools to verify all violations are resolved.
- **Provenance:** voice=`None` · principles=`p-0001`, `p-0095`

### P0 — technical
- **Where:** https://zergboard-preview.pages.dev/api/event (`Network request (console + network_errors payload)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/pricing_html_desktop.png)
- **Finding:** The page attempts to POST to /api/event and receives a 405 Method Not Allowed response, causing two console errors visible to any user with DevTools open. This indicates either a broken analytics endpoint or misconfigured event tracking. On a pricing page, failed conversion tracking means attribution data is being lost.
- **Fix:** Investigate the /api/event endpoint: verify the method is POST-compatible, ensure CORS headers are correct, and confirm the endpoint exists in the deployment environment. If this is an analytics beacon, wrap it in error handling so failures don't pollute the console. If the endpoint is not yet implemented, remove the tracking call until the backend is ready.
- **Provenance:** voice=`None` · principles=`p-0106`

### P0 — accessibility
- **Where:** https://zergboard-preview.pages.dev/use-cases (`p[style*='opacity: 0.8']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/use-cases_html_desktop.png)
- **Finding:** Nine text elements fail WCAG AA contrast requirements (axe violation: color-contrast, impact serious). The opacity: 0.8 styling on body copy reduces contrast below 4.5:1, making paragraphs harder to read for users with low vision and in bright-light mobile environments. This affects all feature descriptions and testimonial attribution text.
- **Fix:** Remove opacity: 0.8 from paragraph styles. Use a semantically darker grey (#4B5563 or #374151) directly in the color property instead of reducing opacity on black text. Test all body copy against WCAG 2.2 SC 1.4.3 to ensure 4.5:1 minimum contrast.
- **Provenance:** voice=`None` · principles=`p-0001`, `p-0095`

### P0 — cta
- **Where:** https://zergboard-preview.pages.dev/use-cases (`nav primary button`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/use-cases_html_desktop.png)
- **Finding:** Primary CTA in header reads 'ENGINEERING' instead of a verb or outcome. This appears to be a navigation label misidentified as the primary action, creating confusion about what action users should take. The structured payload confirms 'ENGINEERING' is marked as primary_cta but it functions as a section anchor, not a conversion point.
- **Fix:** Replace header CTA with 'START FREE' (already present in top-right) as the primary action button. Style it with higher visual weight (solid background, accent color). Ensure 'ENGINEERING', 'AGENCIES', 'FOUNDERS', 'INTERNAL IT' buttons are visually distinct as secondary navigation anchors, not primary CTAs.
- **Provenance:** voice=`q-0006` · principles=`p-0047`, `p-0100`

### P0 — accessibility
- **Where:** https://zergboard-preview.pages.dev/integrations (`.code span.c (comment spans in code examples)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/integrations_html_desktop.png)
- **Finding:** 30 code comment spans fail WCAG AA contrast requirements (4.5:1 minimum for normal text). These grey-on-black comments in code examples are unreadable for users with low vision and in bright mobile environments. The axe violation confirms 'serious' impact.
- **Fix:** Increase comment text color from current grey to at least #8B8B8B on #000000 background (meets 4.52:1). Test all syntax-highlighted token colors against background and ensure minimum 4.5:1 ratio.
- **Provenance:** voice=`None` · principles=`p-0001`, `p-0095`

### P0 — accessibility
- **Where:** https://zergboard-preview.pages.dev/compare (`th.us`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/compare_html_desktop.png)
- **Finding:** Axe detected 13 instances of color-contrast violations, starting with the 'Zergboard' column header in the comparison table. The beige text on cream background fails WCAG AA 4.5:1 minimum contrast ratio. This affects readability for users with low vision and in bright-light mobile environments, and creates legal/compliance risk.
- **Fix:** Increase contrast of all table text to meet WCAG AA: use #2D2D2D or darker for body text on cream backgrounds, or invert to dark background with light text. Test all combinations with a contrast checker before shipping.
- **Provenance:** voice=`None` · principles=`p-0001`, `p-0095`

### P0 — technical
- **Where:** https://zergboard-preview.pages.dev/api/event (`network console`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/compare_html_desktop.png)
- **Finding:** Two failed POST requests to /api/event (405 Method Not Allowed, ERR_ABORTED) appear in network logs. This indicates broken analytics or event tracking—either the endpoint doesn't exist yet or the deployment config is rejecting POST. All page interactions are going untracked.
- **Fix:** If /api/event is for conversion tracking, implement the endpoint or route to a working analytics service (Posthog, Mixpanel, GA4). If not yet needed, remove the client-side calls to eliminate console noise. Verify UTM and conversion pixel tracking work end-to-end before running paid campaigns.
- **Provenance:** voice=`q-0006` · principles=`p-0106`

### P0 — accessibility
- **Where:** https://zergboard-preview.pages.dev/signup (`a[href='#'][style*='color: var(--accent)']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/signup_html_desktop.png)
- **Finding:** The Terms and Privacy Policy links in the signup form footer fail WCAG AA contrast requirements and are not distinguishable from surrounding text except by color. axe-core reports both 'color-contrast' and 'link-in-text-block' violations with 'serious' impact across 3 instances. Users with low vision or colorblindness cannot reliably identify these links, and keyboard-only users navigating by text scanning may miss them entirely.
- **Fix:** Change the accent color to meet 4.5:1 contrast against the beige background, or add an underline to all inline links so they are distinguishable without relying on color. Verify the new color passes WebAIM contrast checker for both normal and large text sizes.
- **Provenance:** voice=`None` · principles=`p-0001`, `p-0011`

### P1 — accessibility
- **Where:** https://zergboard-preview.pages.dev/features (`h4 (Keyboard-first, Real-time everywhere, etc.)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** Four heading-level violations where h4 elements appear without parent h2/h3 structure. Screen readers rely on heading hierarchy to navigate page sections; skipping levels (h1 → h4) breaks assistive navigation and forces users to manually scan for content boundaries.
- **Fix:** Change all feature-name headings under 'CARDS & COLUMNS, IN 50MS' section from <h4> to <h3>. If visual size needs to remain the same, apply a class that sets font-size to match current h4 styling while preserving semantic correctness.
- **Provenance:** voice=`None` · principles=`p-0002`

### P1 — copy
- **Where:** https://zergboard-preview.pages.dev/features (`Hero headline`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** Headline 'EVERYTHING A FOCUSED PM TOOL NEEDS. NOTHING IT DOESN'T.' is a category descriptor that tells visitors what Zergboard is (a focused PM tool) but not why it wins. The statement is defensively framed — it signals restraint rather than superiority — and requires visitors to infer the benefit of 'focused' rather than asserting measurable outcomes.
- **Fix:** Lead with the outcome that focus delivers: 'SHIP 40% FASTER WITH THE BOARD AGENTS UNDERSTAND.' or 'THE ONLY PM TOOL YOUR CISO WILL APPROVE IN ONE MEETING.' This names a specific result (speed, compliance approval) that differentiates Zergboard from Linear/Jira rather than describing its design philosophy.
- **Provenance:** voice=`q-0006` · principles=`p-0029`, `p-0030`, `p-0043`

### P1 — positioning
- **Where:** https://zergboard-preview.pages.dev/features (`Hero subhead below headline`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** Hero subhead lists what Zergboard didn't ship (sprints, OKRs, docs, chat) before stating what it did ship. This inverts value communication: visitors see absence before presence, which reads as limitation rather than intentional focus. The genuine differentiation — 'API that covers 100% of it' and 'admin controls your CISO will actually approve' — is buried in the second half of a long sentence.
- **Fix:** Lead with the differentiation: 'A board faster than Linear. An API that covers 100% of the UI. Admin controls that pass SOC 2 audits in one review.' If you want to signal what's excluded, move that to a separate line below the primary value props so scanned readers don't see 'We didn't ship X' as the first complete thought.
- **Provenance:** voice=`q-0006` · principles=`p-0043`, `p-0035`

### P1 — ia
- **Where:** https://zergboard-preview.pages.dev/features (`Section headings: '01 · THE BOARD', '02 · WORKSPACES', '03 · API', '04 · ADMIN'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** Numeric prefixes ('01 · THE BOARD') imply a sequence or process that doesn't exist — these sections are independent feature categories, not steps. The numbered format creates false expectation that section 02 depends on understanding section 01, which increases cognitive load for scanners who jump directly to 'API' or 'ADMIN' sections.
- **Fix:** Remove numeric prefixes entirely, leaving only the category labels ('THE BOARD', 'WORKSPACES', 'API', 'ADMIN'). If you want visual rhythm, replace numbers with a consistent icon or graphic element that doesn't imply sequence. Alternatively, use category names that explicitly signal independence: 'Core Features', 'Multi-Tenant Architecture', 'Developer Platform', 'Enterprise Controls'.
- **Provenance:** voice=`None` · principles=`p-0107`, `p-0022`

### P1 — responsive
- **Where:** https://zergboard-preview.pages.dev/features (`.workspace-list section (desktop vs tablet comparison)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/features_html_mobile.png)
- **Finding:** The workspace list preview collapses to a narrow single column on tablet (768px) with excessive whitespace on the right, creating the appearance of a layout that hasn't reflowed correctly. The list feels cramped and under-utilizes available screen width, especially compared to the board preview which scales more gracefully.
- **Fix:** At 768px breakpoint, maintain two-column layout for workspace list items rather than forcing single column. Use 48% width per item with 4% gap, or switch to a card-based grid layout that uses full width more efficiently. Inspect current CSS media query to verify the column constraint is intentional and not a missing breakpoint.
- **Provenance:** voice=`None` · principles=`p-0010`, `p-0097`

### P1 — cta
- **Where:** https://zergboard-preview.pages.dev/features (`Primary CTA in hero (appears to be 'START FREE' in top-right, not visible in hero itself)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** No primary CTA is present in the hero section below the headline. The only visible CTA is 'START FREE' in the top navigation, which is small and far from the value proposition copy. Visitors who read the headline and subhead have no clear next action within the same viewport, increasing the probability they scroll away rather than convert.
- **Fix:** Add a prominent 'Start free — no credit card' button directly below the hero subhead, centered or left-aligned. Make it visually distinct (high contrast, 48px height minimum) and ensure it's reachable within 3 seconds of reading the headline. Duplicate the CTA above the footer as well to capture visitors who scroll through features.
- **Provenance:** voice=`q-0008` · principles=`p-0047`, `p-0100`

### P1 — accessibility
- **Where:** https://zergboard-preview.pages.dev/pricing (`Footer section starting with <h4>Product</h4>`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/pricing_html_desktop.png)
- **Finding:** Footer navigation uses an h4 heading immediately after the main h1, skipping h2 and h3 entirely. This violates WCAG heading-order requirements and breaks screen reader navigation hierarchy. Users relying on heading-level navigation will experience a disorienting jump from level 1 to level 4.
- **Fix:** Change footer section headings from <h4> to <h2>. If visual size must remain small, use CSS to style h2 elements to match the current h4 appearance (font-size: 0.875rem or similar). Update 'PRODUCT', 'SOLUTIONS', and 'COMPANY' headers accordingly.
- **Provenance:** voice=`None` · principles=`p-0107`

### P1 — ia
- **Where:** https://zergboard-preview.pages.dev/pricing (`primary_cta: 'SKIP TO CONTENT'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/pricing_html_desktop.png)
- **Finding:** The structured payload identifies 'SKIP TO CONTENT' as the primary CTA, which is an accessibility landmark link, not a conversion action. This suggests the actual primary CTA ('START FREE' or 'START 14-DAY TRIAL') is not being correctly identified, or the skip link is inappropriately prioritized in the DOM order or aria labeling.
- **Fix:** Verify that 'START FREE' is marked as the primary CTA in both semantic HTML (e.g., class='btn-primary' or role='button' with appropriate aria attributes) and visual hierarchy. Move the skip link outside the main navigation flow or ensure it only receives focus when Tab is pressed, not on page load. Update metadata extraction if needed to correctly identify conversion CTAs.
- **Provenance:** voice=`q-0008` · principles=`p-0047`, `p-0100`

### P1 — copy
- **Where:** https://zergboard-preview.pages.dev/pricing (`Comparison table: 'Audit Log' column for Linear and Asana`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/pricing_html_desktop.png)
- **Finding:** The 'AUDIT LOG' column in the competitor comparison table uses '+$$ Enterprise' and 'Enterprise only' inconsistently. '+$$ Enterprise' for Linear suggests an additional cost on top of the Business tier, while 'Enterprise only' for Asana and Monday Pro suggests unavailability at listed tiers. This ambiguity undermines the credibility of the comparison.
- **Fix:** Standardize the notation: use 'Enterprise only' when the feature is unavailable at the listed tier, and 'Enterprise tier required ($X/user)' when pricing is known. If Linear's Enterprise audit log pricing is unknown, use 'Enterprise tier required (contact sales)' to signal unavailability without implying an add-on cost.
- **Provenance:** voice=`q-0003` · principles=`p-0032`, `p-0045`

### P1 — cta
- **Where:** https://zergboard-preview.pages.dev/pricing (`Business tier card: 'TALK TO SALES' button`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/pricing_html_desktop.png)
- **Finding:** The Business tier uses 'TALK TO SALES' as its sole CTA, while the page copy explicitly critiques 'enterprise pricing' and promises no sales-call gates. This creates cognitive dissonance: the positioning says 'pricing is transparent,' but the highest tier still requires a conversation. Visitors who need SCIM or white-label are forced into a high-friction path.
- **Fix:** Add a secondary 'START 14-DAY TRIAL' button to the Business tier card that mirrors the Team tier CTA. Keep 'TALK TO SALES' as a tertiary text link below for custom contracts or volume discounts. This preserves self-serve access while still offering a high-touch path for complex needs.
- **Provenance:** voice=`q-0006` · principles=`p-0047`, `p-0062`

### P1 — responsive
- **Where:** https://zergboard-preview.pages.dev/pricing (`Comparison table at 768px width`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/pricing_html_mobile.png)
- **Finding:** On tablet view (768px), the comparison table retains its full desktop column structure, forcing horizontal scroll to see the 'AUDIT LOG' column. The table does not reflow into a card-based or accordion layout, making mobile comparison nearly unusable. Users must scroll horizontally and lose context of which row they are comparing.
- **Fix:** At breakpoints below 1024px, convert the table into vertically-stacked comparison cards: each vendor gets its own card showing Tool, Tier, Price, Team Cost, and Audit Log as labeled rows within the card. This eliminates horizontal scroll and keeps all data visible without context loss. Use a sticky 'Zergboard' comparison card at the top for reference.
- **Provenance:** voice=`None` · principles=`p-0010`, `p-0058`

### P1 — consistency
- **Where:** https://zergboard-preview.pages.dev/pricing (`Team tier: '$8 month-to-month' vs Business tier: '$18 month-to-month'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/pricing_html_desktop.png)
- **Finding:** The month-to-month pricing callout uses inconsistent formatting: '$8 month-to-month' for Team tier vs '$18 month-to-month' for Business tier. Neither includes the '/user' unit, making it unclear whether $8 is per-seat or total. The subheadline says 'For growing teams' but doesn't quantify 'growing' — is that 10–50 users, or 50–200?
- **Fix:** Standardize to '$8/user per month, month-to-month' and '$18/user per month, month-to-month'. Add explicit seat-range guidance in the subheadline: 'For growing teams (10–50 users)' and 'For regulated teams (50+ users)' or similar. This eliminates unit ambiguity and helps buyers self-select the right tier without needing a sales call.
- **Provenance:** voice=`None` · principles=`p-0032`, `p-0107`

### P1 — accessibility
- **Where:** https://zergboard-preview.pages.dev/use-cases (`h4`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/use-cases_html_desktop.png)
- **Finding:** Heading hierarchy skips levels (axe violation: heading-order, impact moderate, 5 instances). The page jumps from H1 ('A BOARD BUILT FOR...') directly to H4 ('Auto-create cards', 'Auto-move on PR merge') without intermediate H2/H3 levels. This breaks screen reader navigation and violates semantic HTML structure.
- **Fix:** Remap heading levels to follow proper hierarchy: use H2 for section titles ('CUT YOUR STANDUP IN HALF'), H3 for feature group headers ('STORY · 14-PERSON ENG TEAM'), and H4 for individual feature names ('Auto-create cards'). Adjust visual styling via CSS to maintain current design while fixing semantic structure.
- **Provenance:** voice=`None` · principles=`p-0002`

### P1 — consistency
- **Where:** https://zergboard-preview.pages.dev/use-cases (`.story-card attribution`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/use-cases_html_desktop.png)
- **Finding:** Testimonial attributions use inconsistent formatting. 'VP Eng, fintech series B' includes role + company stage but 'Founder, dev studio' includes only role + company type. The second testimonial on desktop also shows 'MIGRATED FROM JIRA' and 'MIGRATED FROM ASANA' tags but the first has none visible in the dark card.
- **Fix:** Standardize attribution format: '[Role], [Company Type/Stage]' for all testimonials. Add migration source tags to all testimonials if they apply, or remove them entirely if not universally available. Ensure tags are visible on dark backgrounds (check contrast).
- **Provenance:** voice=`None` · principles=`p-0032`

### P1 — accessibility
- **Where:** https://zergboard-preview.pages.dev/integrations (`h4 headings in 'AN MCP SERVER...' section`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/integrations_html_desktop.png)
- **Finding:** Heading hierarchy skips from h2 ('AN MCP SERVER...') directly to h4 ('Standard MCP transport', 'Built-in scopes', 'Idempotent writes'). This violates WCAG 1.3.1 and breaks screen reader navigation for users who jump by heading level.
- **Fix:** Change h4 elements to h3. If visual sizing must match current h4 styling, apply that styling to h3 tags via CSS rather than semantic markup.
- **Provenance:** voice=`None` · principles=`p-0002`

### P1 — accessibility
- **Where:** https://zergboard-preview.pages.dev/integrations (`pre.code[role='region'][aria-label='Code example']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/integrations_html_desktop.png)
- **Finding:** Multiple <pre> elements share identical aria-label='Code example', violating WCAG 2.4.6 (landmark-unique). Screen reader users navigating by landmark cannot distinguish between the six different code examples on the page.
- **Fix:** Give each code block a unique aria-label that describes its content: 'REST read examples', 'REST write examples', 'Webhook payload structure', 'TypeScript SDK usage', 'Python SDK usage', 'Go SDK usage'.
- **Provenance:** voice=`None` · principles=`p-0002`, `p-0011`

### P1 — technical
- **Where:** https://zergboard-preview.pages.dev/integrations (`network console`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/integrations_html_desktop.png)
- **Finding:** POST to /api/event returns 405 Method Not Allowed and appears twice in network log, once as 405 and once as ERR_ABORTED. This suggests broken analytics or tracking infrastructure that is logging console errors visible to any developer inspecting the page.
- **Fix:** Either implement the /api/event endpoint to accept POST requests, or remove the client-side code attempting to POST to it. If analytics tracking is not yet live, stub the endpoint to return 204 No Content rather than 405.
- **Provenance:** voice=`None` · principles=`p-0107`

### P1 — ia
- **Where:** https://zergboard-preview.pages.dev/integrations (`'THE HANDFUL YOU ACTUALLY NEED' section`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/integrations_html_desktop.png)
- **Finding:** The integrations grid lists 14 third-party tools (GitHub, GitLab, Slack, Discord, etc.) but provides no affordance to learn more, configure, or install them. Each card shows a name and one-line description with no button, link, or next step. Users cannot tell if these integrations are live, planned, or conceptual.
- **Fix:** Add a 'Learn more' or 'Configure' link to each card. If integrations are not yet available, replace with 'Coming soon' badge and email capture CTA ('Get notified'). If they are live, link to setup documentation or in-app config flow.
- **Provenance:** voice=`None` · principles=`p-0108`, `p-0100`

### P1 — responsive
- **Where:** https://zergboard-preview.pages.dev/integrations (`Stats row (100% / 3 / 14 / 1)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/integrations_html_mobile.png)
- **Finding:** On tablet (768px), the four-column stats row collapses into two rows of two stats each, but the whitespace distribution is uneven — there is more vertical space between the rows than between the stat number and its label within each card. This violates Gestalt proximity principles and makes it unclear which label belongs to which number.
- **Fix:** Reduce inter-row spacing from current value (appears ~40px) to ~24px, and ensure intra-card spacing (number to label) is tighter at ~8px. Alternatively, stack all four stats vertically in a single column on tablet for clearer hierarchy.
- **Provenance:** voice=`None` · principles=`p-0097`, `p-0058`

### P1 — cta
- **Where:** https://zergboard-preview.pages.dev/integrations (`Hero CTAs: 'READ THE DOCS' and 'SEE SDKS'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/integrations_html_desktop.png)
- **Finding:** The primary CTA 'READ THE DOCS' uses action-oriented language rather than outcome-oriented language. It tells users what to do (read) rather than what they will gain (build, integrate, deploy). The secondary CTA 'SEE SDKS' has the same problem and is visually underemphasized (appears as a text link rather than a button).
- **Fix:** Reframe primary CTA to outcome: 'Start building' or 'Explore the API'. Make secondary CTA a styled button (not just a text link) with outcome framing: 'Get SDKs' or 'Install SDK'. Ensure both CTAs have equal visual weight if both are primary paths.
- **Provenance:** voice=`q-0008` · principles=`p-0047`, `p-0043`

### P1 — accessibility
- **Where:** https://zergboard-preview.pages.dev/compare (`table th:first-child`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/compare_html_desktop.png)
- **Finding:** The comparison table contains an empty header cell in the top-left corner (axe violation: empty-table-header). Screen readers cannot announce the purpose of the first column, forcing AT users to infer the table structure from context.
- **Fix:** Add visually-hidden text 'Feature' or 'Attribute' to the first <th> element: <th><span class='sr-only'>Feature</span></th>. This preserves the visual layout while providing semantic structure for assistive technology.
- **Provenance:** voice=`None` · principles=`p-0107`

### P1 — accessibility
- **Where:** https://zergboard-preview.pages.dev/compare (`footer h4`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/compare_html_desktop.png)
- **Finding:** The footer uses an <h4> tag ('Product') without any preceding h2 or h3, violating heading hierarchy (axe: heading-order). This breaks document outline for screen readers and makes skip-navigation unreliable.
- **Fix:** Either change footer headings to <div class='footer-heading'> with appropriate ARIA if no semantic heading is needed, or establish proper h2/h3 hierarchy: page h1 → section h2s → footer h3s. Do not skip levels.
- **Provenance:** voice=`None` · principles=`p-0107`

### P1 — copy
- **Where:** https://zergboard-preview.pages.dev/compare (`table td containing 'Tr/Ji/Li/As'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20060504-135414-zergboard-preview/screenshots/compare_html_desktop.png)
- **Finding:** The 'Open import path' row uses unexplained abbreviations ('Tr/Ji/Li/As', 'via Asana/Tr') that require users to decode tool names. This increases cognitive load and makes scanning harder, especially for first-time visitors evaluating multiple tools.
- **Fix:** Spell out tool names in full: 'Trello, Jira, Linear, Asana' instead of 'Tr/Ji/Li/As'. If space is constrained, use tooltips or expand on hover. Consistency: competitors also use 'Jira/GitHub' and 'Asana/Jira' in full—match that pattern.
- **Provenance:** voice=`None` · principles=`p-0107`, `p-0022`

### P1 — responsive
- **Where:** https://zergboard-preview.pages.dev/compare (`table.comparison`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/compare_html_mobile.png)
- **Finding:** The 7-column comparison table on mobile (768px) forces horizontal scrolling with no sticky first column, making it difficult to track which feature corresponds to which vendor as users scroll right. The 'Zergboard' column disappears off-screen when viewing competitor columns.
- **Fix:** Implement sticky first column (position: sticky; left: 0) with a subtle right border/shadow to maintain context while scrolling. Alternatively, collapse to a card-based layout on <1024px where each vendor becomes a separate card with all features visible vertically.
- **Provenance:** voice=`None` · principles=`p-0010`, `p-0110`

### P1 — ia
- **Where:** https://zergboard-preview.pages.dev/compare (`nav.anchor-links`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/compare_html_desktop.png)
- **Finding:** The six competitor quick-links (VS JIRA, VS MONDAY, etc.) are not visually connected to the corresponding sections below—no highlighting on scroll, no indicator of current section. Users who click VS LINEAR and scroll to that section have no persistent signal that they're in the right place.
- **Fix:** Add scroll-spy behavior: highlight the active anchor link when its corresponding section enters the viewport. Use a subtle underline or background color change. Consider sticky positioning for the anchor nav on scroll so users can jump between comparisons without scrolling back to top.
- **Provenance:** voice=`None` · principles=`p-0106`, `p-0110`

### P1 — copy
- **Where:** https://zergboard-preview.pages.dev/compare (`table footer note`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/compare_html_desktop.png)
- **Finding:** The table footer note claims pricing data was 'rechecked last week' but the page payload shows 'April 2026' as the source date—a date in the future. This is either a placeholder that leaked into production or a typo, and it destroys credibility by signaling the data is fabricated or untested.
- **Fix:** Replace with accurate recency language: 'Prices sourced from vendor sites, verified [Month YYYY]' or 'Last verified: [actual date]'. If this is preview/staging content, add a banner: 'PREVIEW BUILD — pricing data is illustrative only'.
- **Provenance:** voice=`q-0006` · principles=`p-0032`, `p-0042`

### P1 — friction
- **Where:** https://zergboard-preview.pages.dev/signup (`select[name='source']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/signup_html_desktop.png)
- **Finding:** The 'HOW'D YOU FIND US?' dropdown defaults to an em-dash placeholder and lists six options including 'Already use Zerg AI'. This field is marked optional but interrupts the signup flow with a question that provides no value to the user. Each additional form field—even optional ones—increases cognitive load and drop-off probability during the critical moment before clicking 'CREATE WORKSPACE'.
- **Fix:** Remove the 'How'd you find us?' field entirely from the signup form. Collect attribution data post-signup via a lightweight one-question survey on the workspace dashboard, or infer it from UTM parameters and referrer headers captured server-side.
- **Provenance:** voice=`q-0008` · principles=`p-0063`, `p-0101`

### P1 — copy
- **Where:** https://zergboard-preview.pages.dev/signup (`label[for='workspace'] + .help-text`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/signup_html_desktop.png)
- **Finding:** The workspace name field shows helper text 'Lowercase, dashes only. Becomes your subdomain.' This is a technical constraint message that doesn't explain what a subdomain is or why it matters. Users unfamiliar with the concept of a subdomain may not understand they're choosing their permanent workspace URL (e.g. acme-eng.zergboard.com), which can lead to regret and support requests later.
- **Fix:** Rewrite the helper text to: 'This becomes your workspace URL: yourname.zergboard.com — choose carefully, it can't be changed later.' Add real-time inline preview that shows 'yourname.zergboard.com' updating as the user types, so the consequence is visible before submission.
- **Provenance:** voice=`None` · principles=`p-0107`, `p-0109`

### P1 — friction
- **Where:** https://zergboard-preview.pages.dev/signup (`form[action='https://app.zergboard.com/signup']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/signup_html_desktop.png)
- **Finding:** The payload shows no evidence of inline validation on the email or workspace name fields. Both fields have format constraints (email RFC compliance, workspace alphanumeric-plus-dashes only) that could be validated on blur to catch errors before the user clicks 'CREATE WORKSPACE'. Surfacing errors only after form submission forces users to mentally backtrack across the entire form, especially painful if the workspace name is taken and they need to brainstorm alternatives.
- **Fix:** Add onBlur validation to the email field (valid format check) and the workspace name field (format check + real-time availability check via API). Display green checkmark icon on success, red error message on failure, positioned directly below the field while the user is still in context.
- **Provenance:** voice=`None` · principles=`p-0060`, `p-0109`

### P2 — typography
- **Where:** https://zergboard-preview.pages.dev/features (`Feature description paragraphs under each section heading`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** Body copy appears to use line-height below 1.4, making multi-line paragraphs (especially in the 'MULTI-TENANT' section) feel dense and reducing readability on mobile where line wrapping increases. The tight leading creates visual clutter that competes with the intentional whitespace elsewhere on the page.
- **Fix:** Set line-height to 1.6 for all body copy (paragraphs, feature descriptions, list items). This is especially critical in the 'MULTI-TENANT' and 'API' sections where multi-sentence descriptions currently run together visually.
- **Provenance:** voice=`None` · principles=`p-0086`

### P2 — interaction
- **Where:** https://zergboard-preview.pages.dev/features (`Board preview section with cards`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** Board preview is a static image of the UI. Competitors (Linear, Asana) often use interactive demos or video walkthroughs that let visitors experience the product's speed and real-time behavior firsthand. A static preview makes claims about '50ms' and 'real-time everywhere' feel unsubstantiated because visitors cannot verify them.
- **Fix:** Embed a 10–15 second looping video showing a card being dragged across columns with visible real-time updates appearing on multiple simulated users' screens simultaneously. Alternatively, make the board preview live-interactive: let visitors drag one card and see it update instantly. This turns the speed claim from stated to demonstrated.
- **Provenance:** voice=`q-0006` · principles=`p-0048`, `p-0032`

### P2 — copy
- **Where:** https://zergboard-preview.pages.dev/features (`'ALL THE SMALL STUFF. NOTHING EXTRA TO INSTALL.' section`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** Feature grid uses vague, jargon-heavy descriptions that don't name the outcome. 'Search' says 'Full-text search cards, comments, attachments' — accurate but uncompelling. 'Automations' says 'Rules that execute…' which is a mechanical description rather than a use case. Visitors scanning this grid see ingredients, not meals, making it harder to visualize how these features solve their problems.
- **Fix:** Rewrite each feature blurb to lead with the outcome: 'Search — Find any card, comment, or file in under 200ms' (names the speed benefit). 'Automations — Auto-assign bugs to on-call engineers when Sentry fires' (names a concrete workflow). This pattern shifts from 'what it is' to 'what it does for you', aligning with Schwartz's principle of meeting desire where it exists.
- **Provenance:** voice=`None` · principles=`p-0043`, `p-0033`

### P2 — typography
- **Where:** https://zergboard-preview.pages.dev/pricing (`Hero headline: 'THREE TIERS. ONE ON THE HOMEPAGE. NONE OF THEM LIE.'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/pricing_html_desktop.png)
- **Finding:** The hero headline uses hard line breaks that create uneven rhythm and awkward orphans ('NONE OF THEM LIE.' isolated on its own line). On tablet view, the breaks are even more pronounced, making the headline feel fragmented rather than declarative. This reduces the punchy impact the copy is clearly aiming for.
- **Fix:** Remove hard <br> tags and let the headline reflow naturally based on viewport width, using CSS max-width (e.g., max-width: 18em on the headline container) to control line length. Alternatively, use <wbr> or soft hyphens to suggest break points without forcing them. Test at 768px, 1024px, and 1440px to ensure the breaks feel intentional.
- **Provenance:** voice=`None` · principles=`p-0085`, `p-0096`

### P2 — interaction
- **Where:** https://zergboard-preview.pages.dev/pricing (`Comparison table: 'TIER NEEDED FOR SSO' and 'PER-USER / MO' columns`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/pricing_html_desktop.png)
- **Finding:** The competitor comparison table has no sort or filter affordances, even though it contains numeric data (price, team cost) that users might want to reorder. Users comparing Zergboard to specific competitors must visually scan all rows to find the relevant vendor, increasing cognitive load.
- **Fix:** Add click-to-sort functionality on the 'PER-USER / MO' and '15-USER TEAM / YR' column headers. Use a small ↕ icon on sortable headers that changes to ↑ or ↓ on click. Ensure sort state persists if the user navigates away and returns. Alternatively, add a 'Compare to:' dropdown above the table that filters to show only Zergboard + the selected competitor.
- **Provenance:** voice=`None` · principles=`p-0110`, `p-0101`

### P2 — copy
- **Where:** https://zergboard-preview.pages.dev/pricing (`FAQ section: 'THINGS YOU'D ASK BEFORE YOU SWIPED.'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20060504-135414-zergboard-preview/screenshots/pricing_html_desktop.png)
- **Finding:** The FAQ section headline uses present-conditional framing ('THINGS YOU'D ASK') that assumes the reader is about to convert, but the questions themselves reveal doubt (downgrade policy, refunds, seat limits). This tonal mismatch makes the FAQ feel defensive rather than reassuring. The headline also uses 'SWIPED', which is credit-card language that doesn't match the free-tier-first positioning.
- **Fix:** Reframe the headline to acknowledge doubt explicitly: 'QUESTIONS BEFORE YOU START' or 'THINGS TEAMS ASK BEFORE COMMITTING'. This matches the reader's actual mental state (evaluating, not yet decided) and positions the FAQ as decision-support rather than objection-handling. Remove 'SWIPED' — it signals payment friction where the page promises a free start.
- **Provenance:** voice=`q-0007` · principles=`p-0029`, `p-0044`

### P2 — additive_feature
- **Where:** https://zergboard-preview.pages.dev/pricing (`Entire pricing page`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/pricing_html_desktop.png)
- **Finding:** The page has no ROI calculator or cost-comparison widget that lets users input their team size and see the annual cost delta between Zergboard and a selected competitor. Every serious B2B SaaS pricing page in the benchmarking set includes some form of interactive calculation to make the business case tangible.
- **Fix:** Add a 'Calculate your savings' module below the comparison table: two dropdowns (team size: 5/10/15/25/50, compare to: Linear/Asana/Monday/Jira) that dynamically show 'You'd pay $X with [competitor], $Y with Zergboard — save $Z per year'. Include a 'Share this comparison' button that generates a URL with params for the sales team to send in follow-up emails.
- **Provenance:** voice=`q-0004` · principles=`p-0045`, `p-0032`

### P2 — copy
- **Where:** https://zergboard-preview.pages.dev/integrations (`Hero paragraph text`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/integrations_html_desktop.png)
- **Finding:** Hero subheadline 'Zergboard treats the UI as one client, not the source of truth' uses insider engineering language ('source of truth') that may not resonate with non-technical decision-makers evaluating the product. The phrase assumes the reader already values API-first architecture.
- **Fix:** Reframe to outcome: 'Every feature ships to the API and UI simultaneously — no waiting for integrations, no second-class API access.' This explains the benefit (simultaneous access, no lag) rather than the philosophical stance.
- **Provenance:** voice=`q-0007` · principles=`p-0107`, `p-0043`

### P2 — interaction
- **Where:** https://zergboard-preview.pages.dev/integrations (`Code example <pre> blocks`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/integrations_html_desktop.png)
- **Finding:** Code examples have no copy-to-clipboard button, forcing users to manually select and copy long API calls and SDK snippets. Competitors (Stripe, Twilio, GitHub) universally provide one-click copy buttons on code blocks as a baseline dev-experience feature.
- **Fix:** Add a copy button to the top-right corner of each <pre> block. On click, copy the plaintext content to clipboard and change button label from 'Copy' to 'Copied!' for 2 seconds. Ensure button is keyboard-accessible (Tab + Enter).
- **Provenance:** voice=`None` · principles=`p-0047`, `p-0100`

### P2 — typography
- **Where:** https://zergboard-preview.pages.dev/integrations (`Section number labels (01, 02, 03, 04)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/integrations_html_desktop.png)
- **Finding:** Section number labels ('01 · THE SHAPE OF IT', '02 · WEBHOOKS', etc.) use a light grey that appears to be below the 4.5:1 contrast threshold against the cream background. While these are decorative, they serve as wayfinding cues and should meet minimum contrast for users scanning the page structure.
- **Fix:** Darken section number color to at least #757575 on the cream background (assuming #F5F5F0 or similar) to meet 4.5:1 ratio. Test with a contrast checker before deployment.
- **Provenance:** voice=`None` · principles=`p-0001`, `p-0093`

### P2 — additive_feature
- **Where:** https://zergboard-preview.pages.dev/integrations (`'PUSH, NOT JUST PULL' webhook section`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/integrations_html_desktop.png)
- **Finding:** The webhook event list (CARD.CREATED, CARD.MOVED, etc.) is displayed as static styled divs with no interactivity. Users cannot filter by category, search for a specific event, or expand to see payload schemas. Stripe and Twilio allow inline event filtering and schema preview on their webhook docs pages.
- **Fix:** Add a search/filter input above the event list to allow users to type and filter events (e.g., typing 'card' shows only CARD.* events). Alternatively, make each event name clickable to expand an inline payload schema example.
- **Provenance:** voice=`None` · principles=`p-0110`, `p-0100`

### P2 — polish
- **Where:** https://zergboard-preview.pages.dev/integrations (`Footer legal/compliance links`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/integrations_html_desktop.png)
- **Finding:** Footer includes standard legal links (Privacy, Terms, etc.) but text sizing and spacing is inconsistent with the rest of the page typography. The footer text appears smaller than body copy elsewhere, and link underlines are inconsistent (some links underlined, some not).
- **Fix:** Audit footer typography against the site's type scale (per p-0096). Set footer body text to match the smallest body size used elsewhere (likely 14px or 16px) and ensure all footer links have consistent underline treatment (recommend underline on hover only, or always underlined).
- **Provenance:** voice=`None` · principles=`p-0096`, `p-0099`

### P2 — typography
- **Where:** https://zergboard-preview.pages.dev/compare (`h1`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/compare_html_desktop.png)
- **Finding:** The h1 contains a line break encoded as literal \n ('WE'RE NOT FOR EVERYONE.\nHERE'S WHERE WE'RE NOT.') which renders as two lines but is stored as a single semantic string. This is non-standard and may cause issues with SEO crawlers or screen readers that read it as one continuous sentence.
- **Fix:** Mark up as proper semantic structure: <h1><span class='line1'>We're not for everyone.</span> <span class='line2'>Here's where we're not.</span></h1> and use CSS for line breaking. This preserves visual layout while maintaining semantic correctness.
- **Provenance:** voice=`None` · principles=`p-0107`

### P2 — additive_feature
- **Where:** https://zergboard-preview.pages.dev/compare (`section.comparison-cards`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/compare_html_desktop.png)
- **Finding:** Each competitor comparison section lists 'When [Tool] is the right call' and 'When Zergboard is the right call' but provides no direct way to test the claim. Users who are evaluating based on these criteria have no next step beyond 'START FREE' at the bottom—no tool-specific migration guide, no ROI calculator, no 'See Zergboard vs [Tool] demo'.
- **Fix:** Add a section-specific CTA to each comparison block: 'See Zergboard vs Jira in 2 minutes' linking to a short video walkthrough, or 'Import your Jira board now' linking directly to the importer. This reduces the gap between interest and action for users who resonate with a specific comparison.
- **Provenance:** voice=`q-0006` · principles=`p-0047`, `p-0024`

### P2 — interaction
- **Where:** https://zergboard-preview.pages.dev/compare (`table.comparison`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/compare_html_desktop.png)
- **Finding:** The comparison table shows static checkmarks and dashes with no way to filter or highlight rows by criteria. Users evaluating on specific features (e.g. 'Must have SSO under $10/user') must manually scan all rows. Competitors like G2 comparison grids allow column hiding or row filtering.
- **Fix:** Add filter toggles above the table: 'Show only: API coverage | SSO | Self-host | Agent-ready'. Clicking a toggle highlights or isolates matching rows. This reduces cognitive load for users with specific requirements and makes the differentiation more legible.
- **Provenance:** voice=`None` · principles=`p-0101`, `p-0110`

### P2 — polish
- **Where:** https://zergboard-preview.pages.dev/compare (`table td containing '~70%', '~60%'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260504-135414-zergboard-preview/screenshots/compare_html_desktop.png)
- **Finding:** The 'API coverage' row uses tilde approximations ('~70%', '~60%') for competitors but a definitive checkmark for Zergboard ('✓ 100% feature coverage'). This inconsistency in precision signals either that competitor data is estimated/unverified or that Zergboard's claim lacks the same rigor, depending on interpretation.
- **Fix:** Make precision consistent: either source exact percentages for all vendors ('Jira: 68% coverage per Atlassian API docs, audited 2025-04') or use the same approximation level for all ('Zergboard ~100%, Jira ~70%'). If exact data exists only for Zergboard, add a footnote explaining methodology.
- **Provenance:** voice=`q-0006` · principles=`p-0032`

## Rejected (missing provenance)
- _model_error_: 
- _model_error_: 
