# Fake Matt feedback — https://zergboard-preview.pages.dev

_Reviewed 2026-05-02 18:04; 3 pages, 23 findings (0 rejected for missing provenance)._

**Severity:** P0=6 · P1=14 · P2=3

## If I only fix three things
- Named enterprise customer logos are present on Asana, Jira, Cursor, Devin, Linear, ClickUp, Monday, and Trello — absent on Zergboard, replaced by category labels (YC STARTUP, DEV STUDIO, FINTECH SERIES B). But the damage isn't just absence: the footnote 'Real logos coming as our first cohort goes public' is an explicit on-page confession of zero social proof, which is categorically worse than omitting the section entirely. Engineering leaders evaluating a PM tool switch will read that line and stop reading. This credibility gap will suppress trial adoption regardless of product quality.
  - **Fix:** Remove the placeholder band and its confession footnote immediately. If no public logos exist yet, replace the section with one real quantified beta signal — '14 teams in private beta, avg. 3 standups eliminated per sprint' beats a category-label grid at any stage. The 'be a launch partner' ask is a good instinct but it must be a standalone CTA block, not a parenthetical apology on a broken proof section.
- DOMContentLoaded is 5,265ms on a 7KB page. THAT IS A BLOCKING SEO PROBLEM. A 7KB transfer size rules out asset weight entirely — this is render-blocking JavaScript or a long-running synchronous script. Google's Core Web Vitals use LCP as a direct search ranking signal; a 5-second load on a static marketing page will suppress organic discovery regardless of how well the copy converts. Additionally, /api/event is returning 405 on POST — analytics are silently broken, meaning there is no conversion funnel data being collected from any visitor on the site right now.
  - **Fix:** Profile the JS execution waterfall in Chrome DevTools Performance panel. A 7KB page should DOMContentLoad under 500ms — find and defer or eliminate whatever synchronous script is blocking first render. Fix /api/event separately: if this is Plausible or a custom handler, either the endpoint needs to accept POST or the tracking snippet needs updating. You cannot optimize a conversion funnel you cannot measure.
- The page doesn't just lack social proof — it confesses the absence. 'Real logos coming as our first cohort goes public' tells every visitor that no real customers exist yet, converting a credibility gap into a credibility crater. Named enterprise customer logos appear in a trust band on Asana, Jira, Linear, ClickUp, Monday, Trello — absent on Zergboard, and now explicitly flagged as absent. This is categorically worse than omitting the section entirely.
  - **Fix:** Remove the 'Real logos coming' editorial immediately. If you have no named customers yet, cut the trust band entirely until you do. One real name — even a single beta user who consents — beats six category placeholders. If launch is imminent, replace the section with a single genuine quote from a real person with their actual name, title, and company. Never editorialize the absence of proof.

## All findings

### P0 — social_proof
- **Where:** https://zergboard-preview.pages.dev/ (`text='Real logos coming as our first cohort goes public'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/home_desktop.png)
- **Finding:** Named enterprise customer logos are present on Asana, Jira, Cursor, Devin, Linear, ClickUp, Monday, and Trello — absent on Zergboard, replaced by category labels (YC STARTUP, DEV STUDIO, FINTECH SERIES B). But the damage isn't just absence: the footnote 'Real logos coming as our first cohort goes public' is an explicit on-page confession of zero social proof, which is categorically worse than omitting the section entirely. Engineering leaders evaluating a PM tool switch will read that line and stop reading. This credibility gap will suppress trial adoption regardless of product quality.
- **Fix:** Remove the placeholder band and its confession footnote immediately. If no public logos exist yet, replace the section with one real quantified beta signal — '14 teams in private beta, avg. 3 standups eliminated per sprint' beats a category-label grid at any stage. The 'be a launch partner' ask is a good instinct but it must be a standalone CTA block, not a parenthetical apology on a broken proof section.
- **Provenance:** voice=`q-0003` · principles=`p-0019`, `p-0042`, `p-0048`

### P0 — technical
- **Where:** https://zergboard-preview.pages.dev/ (`document`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/home_desktop.png)
- **Finding:** DOMContentLoaded is 5,265ms on a 7KB page. THAT IS A BLOCKING SEO PROBLEM. A 7KB transfer size rules out asset weight entirely — this is render-blocking JavaScript or a long-running synchronous script. Google's Core Web Vitals use LCP as a direct search ranking signal; a 5-second load on a static marketing page will suppress organic discovery regardless of how well the copy converts. Additionally, /api/event is returning 405 on POST — analytics are silently broken, meaning there is no conversion funnel data being collected from any visitor on the site right now.
- **Fix:** Profile the JS execution waterfall in Chrome DevTools Performance panel. A 7KB page should DOMContentLoad under 500ms — find and defer or eliminate whatever synchronous script is blocking first render. Fix /api/event separately: if this is Plausible or a custom handler, either the endpoint needs to accept POST or the tracking snippet needs updating. You cannot optimize a conversion funnel you cannot measure.
- **Provenance:** voice=`q-0021` · principles=`p-0022`

### P0 — positioning
- **Where:** https://zergboard-preview.pages.dev/ (`p:contains('Real logos coming')`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/index_html_desktop.png)
- **Finding:** The page doesn't just lack social proof — it confesses the absence. 'Real logos coming as our first cohort goes public' tells every visitor that no real customers exist yet, converting a credibility gap into a credibility crater. Named enterprise customer logos appear in a trust band on Asana, Jira, Linear, ClickUp, Monday, Trello — absent on Zergboard, and now explicitly flagged as absent. This is categorically worse than omitting the section entirely.
- **Fix:** Remove the 'Real logos coming' editorial immediately. If you have no named customers yet, cut the trust band entirely until you do. One real name — even a single beta user who consents — beats six category placeholders. If launch is imminent, replace the section with a single genuine quote from a real person with their actual name, title, and company. Never editorialize the absence of proof.
- **Provenance:** voice=`q-0003` · principles=`p-0019`, `p-0042`

### P0 — technical
- **Where:** https://zergboard-preview.pages.dev/ (`N/A — network layer (/api/event)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/index_html_desktop.png)
- **Finding:** POST to /api/event returns 405 and aborts on every page load. The site is collecting zero conversion signal data — no visibility into which sections work, where visitors drop, or whether the primary CTA fires. Running any traffic to this page right now means every visitor acquired generates no measurable data. This is not a minor bug; it is a prerequisite failure that makes every other optimization on this page unverifiable.
- **Fix:** Fix the Cloudflare Pages function at /api/event to accept POST — likely a missing method handler or OPTIONS preflight response. Confirm via curl before any traffic runs. Verify 'START FREE' click events are captured end-to-end in your analytics sink before launch.
- **Provenance:** voice=`q-0014` · principles=`p-0071`

### P0 — social_proof
- **Where:** https://zergboard-preview.pages.dev/features (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** Zero social proof on the features page. No named customer logos, no adoption metrics, no testimonials — the page makes bold claims ('50ms,' 'CISO checklist, all of it') with nothing to validate them. Engineering buyers and budget holders use the features page to build an internal business case for switching. Without any third-party signal, they're being asked to trust assertions from the seller, which they won't. Named enterprise customer logos appear on Asana, Linear, Jira, ClickUp, Monday, Cursor, Devin — absent on Zergboard.
- **Fix:** Add a customer logo band immediately below the hero (3–6 logos minimum). Insert at least one quantified customer outcome per major section — e.g., under the API section: 'X engineering teams have automated Y workflows via the Zergboard API.' Use real numbers, not placeholder stats.
- **Provenance:** voice=`q-0003` · principles=`p-0019`, `p-0042`, `p-0048`

### P0 — accessibility
- **Where:** https://zergboard-preview.pages.dev/features (`.col-head`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** axe reports serious color-contrast violations on 18 nodes, starting with the column header text in the in-page board demo. This page explicitly targets CISOs with 'THE CISO CHECKLIST. ALL OF IT.' — shipping with 18 WCAG contrast failures is a live contradiction of that claim. Security-conscious enterprise buyers who run an accessibility scan as part of their procurement checklist will find this immediately. It undermines the exact trust signal the admin section is trying to build.
- **Fix:** Run axe or Stark against the full page and fix all 18 failing nodes to meet WCAG 2.2 AA (4.5:1 for body text, 3:1 for large text). Start with the board demo column headers — these are the most visible failure. This is a blocking issue before any enterprise sales motion.
- **Provenance:** voice=`q-0006` · principles=`p-0001`, `p-0095`

### P1 — copy
- **Where:** https://zergboard-preview.pages.dev/ (`h1`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/home_desktop.png)
- **Finding:** 'THE PROJECT BOARD YOUR TEAM AND AGENTS SHARE' is a category description masquerading as a claim — every competitor from Trello to any AI-bolted-on Jira plugin could run this headline tomorrow. The agent-first positioning is the most defensible thing Zergboard has and it's stated defensively ('your team AND agents share') rather than asserted as a structural advantage. No competitor owns 'the board where agents are first-class collaborators' with clarity, but this H1 doesn't claim that ownership.
- **Fix:** Rewrite as a superlative or direct assertion. Candidates: 'THE FIRST BOARD WHERE AGENTS ARE FIRST-CLASS TEAMMATES.' or 'THE ONLY PM TOOL BUILT API-FIRST SO YOUR AGENTS WORK THE SAME WAY YOUR TEAM DOES.' The distinction between 'supports AI integrations' and 'built so agents operate natively without middleware' is the entire value proposition — the H1 must carry it, not bury it.
- **Provenance:** voice=`q-0007` · principles=`p-0030`, `p-0044`

### P1 — positioning
- **Where:** https://zergboard-preview.pages.dev/ (`text='Trello-simple for your team. API-complete for your agents.'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/home_desktop.png)
- **Finding:** 'API-complete for your agents' is insider language that speaks to engineers who already believe. The budget holders and engineering managers who approve a PM tool migration need the business case made explicit — and 'API-complete' requires them to do interpretive work they will not do. The differentiator is stated but never shown in terms that convert a skeptic: Cursor lands enterprise deals by quantifying adoption (80%, 40,000 engineers); Zergboard's hero subheadline leaves the translation entirely to the visitor.
- **Fix:** Add one outcome-framed clause that names the business consequence, not the technical property: 'Your Zerg or Claude agent creates cards, moves tickets, and posts release notes exactly the way your team does — no middleware, no custom integrations.' Then ensure the hero product animation's caption labels the outcome ('Agent filed 7 tickets from Sentry alerts — 0 human minutes') rather than leaving it uninterpreted.
- **Provenance:** voice=`q-0004` · principles=`p-0029`, `p-0043`, `p-0107`

### P1 — copy
- **Where:** https://zergboard-preview.pages.dev/ (`text='<90s FROM SIGNUP TO FIRST BOARD'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/home_desktop.png)
- **Finding:** The three hero stat blocks — '<90s from signup to first board', '100% of features in the API', '$0 until you outgrow the free tier' — are operational metrics about how Zergboard works, not customer outcome metrics about what buyers achieve. Devin leads with '20x cost savings, 8x efficiency, 6M lines migrated.' Cursor leads with '80% adoption.' These answer 'why should I switch'; Zergboard's stats answer 'how does it work.' That's the wrong question to be answering above the fold.
- **Fix:** Replace at least one stat block with a customer outcome metric sourced from the private beta cohort. Even an approximate but real number — 'Teams cut standup time by 40%' or '3x more cards closed by agents vs. humans in beta' — is more persuasive than '<90s to first board' because it answers the buyer's actual question. If no outcome data exists yet, these three stats should move below the fold and the space should be reclaimed for one real customer quote.
- **Provenance:** voice=`q-0005` · principles=`p-0032`, `p-0045`

### P1 — trust
- **Where:** https://zergboard-preview.pages.dev/ (`text='SOC 2 Type II in flight'`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/home_desktop.png)
- **Finding:** 'SOC 2 Type II in flight' tells enterprise buyers the certification doesn't exist yet. Linear and Asana are both SOC 2 Type II certified; engineering leaders evaluating a PM tool for F500 or regulated-industry teams will read 'in flight' as a present-tense disqualifier, not a forward-looking reassurance. Surfacing an incomplete credential in the hero subheadline — before any other trust signal has landed — is worse than omitting it entirely.
- **Fix:** Remove 'in flight' from hero copy until the certification is complete. Replace with what IS true today and enterprise-relevant: 'SSO, SCIM, and audit logs available now' — all of which map directly to the Admin controls feature block lower on the page. When SOC 2 certifies, put it back in the hero with the badge. An earned credential earns the space; an unearned one erodes it.
- **Provenance:** voice=`q-0002` · principles=`p-0021`, `p-0042`

### P1 — accessibility
- **Where:** https://zergboard-preview.pages.dev/ (`span[style*='var(--accent)']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/home_desktop.png)
- **Finding:** 25 elements are failing WCAG AA color contrast, starting with the accent-colored 'live' indicator in the hero product animation — which is the first thing a visitor is meant to look at to understand the agent-first value proposition. Failing contrast in the hero means the demo that is supposed to make the differentiator visceral is partially illegible to a significant share of users, compounding the positioning problem. With 25 failing nodes this is a systemic token problem, not a one-off.
- **Fix:** Audit every instance of var(--accent) against its background context. The 'LIVE' badge and agent activity text in the hero mockup are the highest-priority fix — darken the accent or lighten its background until the ratio clears 4.5:1. Run axe-core locally post-fix; the goal is zero color-contrast violations before any paid acquisition is turned on, since contrast failures directly reduce conversion among users with low vision and in bright-light mobile environments.
- **Provenance:** voice=`q-0021` · principles=`p-0001`, `p-0095`

### P1 — positioning
- **Where:** https://zergboard-preview.pages.dev/ (`h1`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/index_html_desktop.png)
- **Finding:** 'THE PROJECT BOARD YOUR TEAM AND AGENTS SHARE' is a category description masquerading as a claim. It tells visitors what Zergboard is — it does not assert why it wins. Cursor, Linear, and Devin all lead with bold assertions or outcome promises; none lead with neutral descriptors. The most defensible position Zergboard owns — the only board where agents and humans operate identically with no API wrapper, no second-class automation tier — is understated into a subheadline clause and defended rather than declared.
- **Fix:** Rewrite H1 to assert the position directly. 'THE ONLY BOARD WHERE AGENTS ARE FIRST-CLASS TEAMMATES' or 'YOUR AGENTS SHIP TICKETS. YOUR TEAM SHIPS SOFTWARE.' — something a competitor can credibly dispute. Category descriptions belong in subheads; the headline must make a claim.
- **Provenance:** voice=`q-0007` · principles=`p-0030`, `p-0044`

### P1 — copy
- **Where:** https://zergboard-preview.pages.dev/ (`section:has(> *:contains('90s')), .metrics, [class*='stat']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/index_html_desktop.png)
- **Finding:** '<90s FROM SIGNUP TO FIRST BOARD', '100% OF FEATURES IN THE API', '$0 UNTIL YOU OUTGROW THE FREE TIER' are product specs — they describe what Zergboard does, not what it delivers. Cursor leads with 80% adoption at 40,000 engineers. Devin leads with 20x cost savings and 8x efficiency gains. Those are numbers a budget holder can take to a procurement conversation. '100% of features in the API' requires visitors to translate spec into business value themselves — work they will not do.
- **Fix:** Replace or augment spec metrics with customer-outcome metrics. Even beta data works: 'Teams cut standup time by X minutes' or 'X cards automated per team per week.' If no customer data exists yet, reframe specs as outcomes: 'Ship your first board in under 90 seconds' hits harder than a raw stat with no business referent.
- **Provenance:** voice=`q-0003` · principles=`p-0032`, `p-0045`, `p-0043`

### P1 — copy
- **Where:** https://zergboard-preview.pages.dev/ (`h1 + p, .hero p:contains('API-complete')`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/index_html_desktop.png)
- **Finding:** 'API-complete for your agents' is insider shorthand. Engineers who already believe parse it; engineering leaders and budget holders — the actual conversion target — do not. The technical differentiator (every UI action is one curl away; agents interact identically to humans) is stated but never shown in the hero. The compelling curl example that proves the claim is buried in section 2, unreachable by any visitor who skims.
- **Fix:** Replace 'API-complete for your agents' with a concrete behavior: 'Your agents create tickets, move cards, and post updates — the same way your team does.' Surface a condensed version of the curl snippet or a live agent-activity frame in the hero as direct proof, not a deferred section.
- **Provenance:** voice=`q-0004` · principles=`p-0107`, `p-0043`

### P1 — accessibility
- **Where:** https://zergboard-preview.pages.dev/ (`span[style*='var(--accent)']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/index_html_desktop.png)
- **Finding:** The --accent CSS variable fails WCAG AA minimum contrast (4.5:1) across 25 nodes — the first being the 'LIVE' status badge in the hero product mockup. On a page where the agent-activity feed is the primary product demo, illegible status indicators actively undermine the demo itself. This is a serious axe violation with 25 affected nodes, not a polish note.
- **Fix:** Audit the --accent token against every background it appears on using the Deque axe contrast checker or browser DevTools contrast inspector. The 'LIVE' badge and all colored inline text must pass 4.5:1 against their respective backgrounds. Update the CSS variable or add per-context overrides where the background changes.
- **Provenance:** voice=`q-0021` · principles=`p-0001`, `p-0095`

### P1 — positioning
- **Where:** https://zergboard-preview.pages.dev/features (`h1`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** 'EVERYTHING A FOCUSED PM TOOL NEEDS. NOTHING IT DOESN'T.' is a category description masquerading as a winning claim. It tells the visitor what Zergboard is (a focused PM tool), not why it beats Linear, Jira, or Asana. A skeptical engineering director reads this and has zero reason to keep reading — any of those competitors could print the same headline. The headline fails the five-second test: a stranger cannot articulate Zergboard's differentiation from it.
- **Fix:** Replace with a superlative anchored in the one claim competitors can't match: the multi-tenant-by-design architecture or the 100% API parity. Example: 'THE ONLY BOARD BUILT FOR OPERATORS, NOT JUST TEAMS.' or 'THE PM BOARD WHERE EVERY FEATURE IS IN THE API. EVERY ONE.' Lead with the differentiator, not the product category.
- **Provenance:** voice=`q-0007` · principles=`p-0030`, `p-0044`

### P1 — positioning
- **Where:** https://zergboard-preview.pages.dev/features (`section:nth-of-type(2), h2:contains('MULTI-TENANT')`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** 'MULTI-TENANT. BY DESIGN, NOT BY ADD-ON.' is the one claim on this page that no named competitor owns cleanly — Asana, Linear, ClickUp, Jira, Monday all built around a single-team assumption. Yet it's section 02, below the fold, weighted identically to keyboard shortcuts. This is the claim that creates a new category ('the board for operators, not just teams') and it's buried. The most defensible differentiator placed below the fold is functionally invisible to the majority of visitors who skim.
- **Fix:** Promote multi-tenant as the primary differentiating pillar — move it to section 01 or incorporate it into the H1. Add a named-use-case callout for agencies, holding companies, and SaaS embeds with at least one customer name per vertical. This is the section that justifies the pricing premium; it needs to be the first thing buyers see.
- **Provenance:** voice=`q-0004` · principles=`p-0043`, `p-0075`

### P1 — copy
- **Where:** https://zergboard-preview.pages.dev/features (`h2:contains('CARDS & COLUMNS')`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** 'CARDS & COLUMNS, IN 50MS.' and '<200ms' real-time sync are stated but never shown. The page delivers a static board screenshot to prove a speed claim. Linear's site ships a live interactive demo; Notion and Jira both embed product video in feature sections. The 50ms claim is Zergboard's most visceral differentiator on this section — it requires visitors to take it entirely on faith, which is exactly the interpretive work they will not do.
- **Fix:** Replace the static board screenshot with either an embedded video of a card drag propagating to a second screen in real-time, or a live embedded demo with actual latency displayed. If neither is feasible short-term, add a Loom-style GIF and overlay the measured latency ('< 50ms. Measured.') with a methodology link.
- **Provenance:** voice=`q-0006` · principles=`p-0032`, `p-0045`

### P1 — cta
- **Where:** https://zergboard-preview.pages.dev/features (`main`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** The page's detected primary CTA is 'SKIP TO CONTENT' — a skip-nav accessibility link. No conversion CTA appears in the hero or within the feature sections. A buyer who reads through the API section or CISO checklist and wants to act must scroll to the closing section or hunt the nav for 'START FREE.' The close-ready moments — after the API proof block, after the admin checklist — have no CTA present. Fitts's Law: the action the visitor wants to take next must be immediately reachable at the moment they want to take it.
- **Fix:** Add a 'START FREE' CTA button inside the hero subtext and after each major section (Board, API, Admin). The API section especially should close with a developer-targeted CTA: 'READ THE API DOCS →' alongside 'START FREE.' Never make a convinced visitor hunt for the action.
- **Provenance:** voice=`q-0003` · principles=`p-0100`, `p-0047`

### P1 — technical
- **Where:** https://zergboard-preview.pages.dev/features (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** The page fires a POST to /api/event and receives a 405 Method Not Allowed, logged as a console error. This is a broken analytics or event-tracking call that fires on every page load. On a features page being reviewed by enterprise buyers and CISOs, a console error is a credibility signal — any buyer who opens DevTools as part of evaluation (and senior engineers do) sees it immediately. It directly contradicts the 'THE CISO CHECKLIST. ALL OF IT.' positioning.
- **Fix:** Fix or remove the /api/event endpoint. If it's a Cloudflare Pages analytics hook, configure the worker to accept POST requests. If it's dead instrumentation, delete the call. Console errors on a public marketing page should be treated as P0 before any enterprise outreach.
- **Provenance:** voice=`q-0006` · principles=`p-0072`, `p-0107`

### P2 — accessibility
- **Where:** https://zergboard-preview.pages.dev/ (`table th:empty`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/index_html_desktop.png)
- **Finding:** The competitive comparison table has an empty <th> in the first column. Screen readers announce this as an untitled column, making the table navigation meaningless for keyboard and assistive-technology users. The comparison section is exactly where skeptical buyers validate the purchase decision — accessibility failures there affect real conversion, not just audit scores.
- **Fix:** Add visually-hidden label text to the empty header: <th><span class="sr-only">Feature</span></th>. Any descriptive label naming what the column contains satisfies both the axe rule and screen reader navigation.
- **Provenance:** voice=`q-0018` · principles=`p-0002`, `p-0110`

### P2 — technical
- **Where:** https://zergboard-preview.pages.dev/ (`h4:contains('Product')`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/index_html_desktop.png)
- **Finding:** An <h4>Product</h4> in the footer nav appears without a preceding h3, skipping a heading level. This breaks the document outline that search crawlers and screen readers use to parse page structure — a direct SEO and accessibility liability on every page this footer appears. HEADING HIERARCHY IS NOT OPTIONAL IF YOU WANT SEO BENEFIT FROM STRUCTURED CONTENT.
- **Fix:** Footer navigation labels are not semantic headings. Replace <h4> with <p class="footer-nav-heading"> or <span> with explicit font-weight styling, and verify heading levels increment sequentially from H1 through any H2/H3 used on the page before the footer. Never use heading tags for visual size.
- **Provenance:** voice=`q-0024` · principles=`p-0002`

### P2 — copy
- **Where:** https://zergboard-preview.pages.dev/features (`section:contains('ALL THE SMALL STUFF')`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-175604-zergboard-preview/screenshots/features_html_desktop.png)
- **Finding:** 'ALL THE SMALL STUFF. NOTHING EXTRA TO INSTALL.' lists search, mentions, attachments, filters, automations, templates, notifications, mobile apps, import/export. Every single one of these exists identically on Linear, Asana, ClickUp, Jira, Monday, and Trello. Listing them without any differentiation callout confirms Zergboard is at the minimum bar — it requires visitors to do the 'and here's why ours is better' interpretive work themselves, which they won't.
- **Fix:** For each feature in this section, add a one-line differentiator or remove the feature from the list entirely. If Zergboard's search is faster, say 'Search: results in <100ms, no Algolia add-on required.' If mobile is genuinely full-featured (not just read-only), say so explicitly vs. Jira's notoriously broken mobile. Otherwise collapse this section — a parity list is a conversion neutral at best, a trust negative at worst.
- **Provenance:** voice=`q-0008` · principles=`p-0029`, `p-0111`

