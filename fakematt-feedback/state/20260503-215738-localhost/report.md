# Fake Matt feedback — http://localhost:3001

_Reviewed 2026-05-03 22:02; 3 pages, 35 findings (0 rejected for missing provenance)._

**Severity:** P0=5 · P1=18 · P2=12

## If I only fix three things
- The <html> element is missing a lang attribute, triggering a serious axe-core violation. Screen readers cannot correctly pronounce content or switch language profiles without this attribute, causing immediate accessibility failures for vision-impaired users.
  - **Fix:** Add lang="en" to the <html> tag in the root layout or app.vue wrapper. If the app supports multiple locales, bind the lang attribute dynamically to the active locale setting.
- The <html> element lacks a lang attribute, flagged by axe as a serious violation. This breaks screen reader language detection and prevents browsers from offering accurate translation. For a financial application handling crypto wallets, this creates both accessibility and internationalization barriers.
  - **Fix:** Add lang="en" to the <html> tag (or the appropriate ISO 639-1 code if the app supports other languages). If the app is multilingual, dynamically set lang based on user preference or browser locale.
- Both email and password fields have empty name attributes (name=""). This will break form submission in many browsers and prevents password managers from correctly associating credentials with the domain. The form may submit but with unkeyed data or fail entirely depending on the backend expectation.
  - **Fix:** Set name="email" on the email input and name="password" on the password input. Add autocomplete="email" and autocomplete="current-password" respectively to enable browser autofill and password manager integration.

## All findings

### P0 — accessibility
- **Where:** http://localhost:3001/ (`html`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/home_desktop.png)
- **Finding:** The <html> element is missing a lang attribute, triggering a serious axe-core violation. Screen readers cannot correctly pronounce content or switch language profiles without this attribute, causing immediate accessibility failures for vision-impaired users.
- **Fix:** Add lang="en" to the <html> tag in the root layout or app.vue wrapper. If the app supports multiple locales, bind the lang attribute dynamically to the active locale setting.
- **Provenance:** voice=`None` · principles=`p-0002`

### P0 — accessibility
- **Where:** http://localhost:3001/login (`html`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/login_desktop.png)
- **Finding:** The <html> element lacks a lang attribute, flagged by axe as a serious violation. This breaks screen reader language detection and prevents browsers from offering accurate translation. For a financial application handling crypto wallets, this creates both accessibility and internationalization barriers.
- **Fix:** Add lang="en" to the <html> tag (or the appropriate ISO 639-1 code if the app supports other languages). If the app is multilingual, dynamically set lang based on user preference or browser locale.
- **Provenance:** voice=`None` · principles=`p-0002`, `p-0107`

### P0 — technical
- **Where:** http://localhost:3001/login (`form input[type="email"], form input[type="password"]`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/login_desktop.png)
- **Finding:** Both email and password fields have empty name attributes (name=""). This will break form submission in many browsers and prevents password managers from correctly associating credentials with the domain. The form may submit but with unkeyed data or fail entirely depending on the backend expectation.
- **Fix:** Set name="email" on the email input and name="password" on the password input. Add autocomplete="email" and autocomplete="current-password" respectively to enable browser autofill and password manager integration.
- **Provenance:** voice=`None` · principles=`p-0061`, `p-0109`

### P0 — technical
- **Where:** http://localhost:3001/signup (`form input[type='text'], form input[type='email'], form input[type='password']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/signup_desktop.png)
- **Finding:** All three form fields have empty name attributes (name=""). This breaks form submission — when the user submits, no field data will be sent to the server because HTML forms serialize only named inputs. The text field needs name='username' or 'name', the email field needs name='email', and the password field needs name='password'.
- **Fix:** Add explicit name attributes to all form inputs: the text field should have name='username' (or 'name'/'displayName' depending on backend expectations), email field name='email', password field name='password'. Verify that form submission payload includes all three fields after the fix.
- **Provenance:** voice=`None` · principles=`p-0109`

### P0 — accessibility
- **Where:** http://localhost:3001/signup (`html`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/signup_desktop.png)
- **Finding:** The <html> element has no lang attribute, triggering an axe 'serious' violation. Screen readers rely on lang to select the correct pronunciation dictionary and voice; browsers use it for translation and spell-check. This is a WCAG Level A requirement and one of the fastest accessibility fixes.
- **Fix:** Add lang='en' to the <html> tag (or the appropriate ISO 639-1 code if the app supports other languages). In Nuxt, this is typically set in nuxt.config.ts under app.head.htmlAttrs.lang.
- **Provenance:** voice=`None` · principles=`p-0002`

### P1 — accessibility
- **Where:** http://localhost:3001/ (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/home_desktop.png)
- **Finding:** Page content is not wrapped in semantic landmark regions (nav, main, footer), triggering an axe-core moderate violation. Keyboard and screen-reader users cannot navigate by landmark, forcing them to traverse the entire DOM linearly to reach the primary CTA.
- **Fix:** Wrap the logo and Login/Sign-up links in a <nav> element. Wrap the hero content (h1, description, CTAs) in a <main> element. If a footer exists, wrap it in <footer>. This provides skip-navigation targets for assistive tech.
- **Provenance:** voice=`None` · principles=`p-0002`, `p-0110`

### P1 — positioning
- **Where:** http://localhost:3001/ (`h1`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/home_desktop.png)
- **Finding:** The headline 'Zergwallet' and subhead 'A unified, AI-friendly wallet system for zergs' describe what the product is (category membership) rather than asserting why a user should choose it over alternatives. A visitor landing here cannot articulate the value proposition within five seconds, failing the headline test.
- **Fix:** Rewrite the headline to lead with the outcome or unique advantage. Example: 'One wallet for all your agents' USD, crypto, and cross-chain spending' or 'Give your AI agents unified custody across chains.' Test headline clarity with non-insiders before shipping.
- **Provenance:** voice=`q-0002` · principles=`p-0044`, `p-0043`

### P1 — positioning
- **Where:** http://localhost:3001/ (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/home_desktop.png)
- **Finding:** The page has zero social proof infrastructure—no customer logos, usage metrics, testimonials, or trust badges. Visitors evaluating Zergwallet against competitors cannot validate credibility or traction before committing to signup, increasing perceived risk and suppressing conversion.
- **Fix:** Add a trust band below the hero with 3–5 recognizable customer logos (if available) or quantified metrics ('Used by 1,200+ agent deployments' or 'Processing $X in agent transactions daily'). If early-stage, consider 'Backed by [investor]' or certification badges (SOC 2, etc.).
- **Provenance:** voice=`q-0002` · principles=`p-0019`, `p-0045`

### P1 — copy
- **Where:** http://localhost:3001/ (`p`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/home_desktop.png)
- **Finding:** The value proposition 'AI-friendly wallet system for zergs' and 'pluggable custody backends' uses insider/engineering language that assumes familiarity with the Zerg platform. Engineering leaders or finance stakeholders evaluating wallet tooling will not understand what problem this solves or why custody backends being 'pluggable' matters to them.
- **Fix:** Rewrite copy to lead with the user outcome in plain language. Example: 'Your AI agents need to hold and spend funds across chains. Zergwallet gives them a single wallet for USD, BTC, ETH, and ERC-20 tokens—no multi-chain integration work required.' Then mention technical flexibility as a secondary benefit.
- **Provenance:** voice=`q-0006` · principles=`p-0107`, `p-0043`

### P1 — friction
- **Where:** http://localhost:3001/ (`main`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/home_desktop.png)
- **Finding:** The entire value preview is gated behind 'Sign in to view your workspaces,' requiring authentication before a visitor can see any product UI, feature list, or demo. This high-commitment primary CTA forces users to decide whether to trust the product based solely on one sentence of copy, with no evidence of functionality.
- **Fix:** Add an ungated product preview section: screenshots of the dashboard, a feature list (multi-chain support, programmable spending limits, audit logs), or a demo video. Reframe the primary CTA from 'Login' to 'Start free trial' or 'See demo workspace.' Authentication can remain available as a secondary CTA in the top-right.
- **Provenance:** voice=`q-0002` · principles=`p-0047`, `p-0026`

### P1 — additive_feature
- **Where:** http://localhost:3001/ (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/home_desktop.png)
- **Finding:** The page contains no product demo, video walkthrough, or screenshots of the wallet interface. Every serious competitor in the crypto wallet / fintech space shows the product in motion or at minimum provides annotated screenshots of the dashboard before asking for signup. Without this, visitors cannot evaluate whether the UX meets their needs.
- **Fix:** Add a 'See it in action' section with either a 60-second demo video showing an agent creating a wallet, receiving funds, and executing a cross-chain transfer, or a 3-panel screenshot carousel showing the dashboard, transaction history, and admin controls. Ideally both.
- **Provenance:** voice=`q-0006` · principles=`p-0043`, `p-0048`

### P1 — technical
- **Where:** http://localhost:3001/ (`console`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/home_desktop.png)
- **Finding:** The page fires two 401 errors to /api/auth/me on load, visible in both console logs and network errors. While these may be intentional auth-check requests, surfacing 401s in production creates the perception of a broken or misconfigured app and pollutes error-tracking dashboards with noise.
- **Fix:** Suppress expected 401s from appearing as console errors. Either handle the 401 response gracefully in the auth composable (catch and return null without logging) or implement a conditional fetch that only fires /api/auth/me if a session token exists in localStorage. Consider adding a try-online endpoint that returns 200 to verify API connectivity without auth requirements.
- **Provenance:** voice=`None` · principles=`p-0106`

### P1 — additive_feature
- **Where:** http://localhost:3001/login (`form`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/login_desktop.png)
- **Finding:** No 'Forgot password?' link is present. This is a universal pattern on login pages; its absence forces locked-out users to search for recovery flows or contact support. For a crypto wallet, account recovery is especially critical given the high-value nature of the assets.
- **Fix:** Add a 'Forgot password?' link below the password field or below the 'Sign in' button, linking to a password reset flow. Position it as a tertiary action (smaller, lower-contrast text) to maintain visual hierarchy with the primary CTA.
- **Provenance:** voice=`None` · principles=`p-0108`

### P1 — accessibility
- **Where:** http://localhost:3001/login (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/login_desktop.png)
- **Finding:** Axe flagged a moderate 'region' violation: page content is not contained within ARIA landmark regions. This forces screen reader users to navigate linearly through all content instead of jumping directly to the main form, increasing time-to-task.
- **Fix:** Wrap the login form in a <main> landmark. Wrap the top navigation ('ZERGWALLET', 'Login', 'Sign up' links) in a <nav> or <header role="banner">. This allows assistive technology users to skip directly to the form with a single keystroke.
- **Provenance:** voice=`None` · principles=`p-0002`, `p-0110`

### P1 — friction
- **Where:** http://localhost:3001/login (`form input[type="email"]`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/login_desktop.png)
- **Finding:** The email field appears to lack inline validation on blur. Users who mistype their email will only discover the error after clicking 'Sign in' and receiving a server error, forcing them to mentally backtrack and re-scan the form to locate the problem.
- **Fix:** Add onBlur validation to the email field that checks for basic format validity (presence of @, TLD) and displays an inline error message ('Please enter a valid email address') immediately below the field if invalid. Clear the error when the user starts typing again.
- **Provenance:** voice=`None` · principles=`p-0060`, `p-0109`

### P1 — ux
- **Where:** http://localhost:3001/login (`form`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/login_desktop.png)
- **Finding:** No visible security messaging or trust signals accompany the login form. For a crypto wallet application handling financial assets, users expect reassurance about encryption, secure authentication, or account protection before entering credentials. The absence of this creates a credibility gap relative to established wallet providers.
- **Fix:** Add a brief security note below the form or above the email field: 'Your connection is encrypted and your credentials are never stored in plain text.' Alternatively, add a small lock icon with tooltip text. This reassures first-time users without cluttering the interface.
- **Provenance:** voice=`q-0004` · principles=`p-0065`, `p-0042`

### P1 — ux
- **Where:** http://localhost:3001/login (`form button[type="submit"]`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/login_desktop.png)
- **Finding:** No loading or pending state is visible for the 'Sign in' button. During the authentication round-trip, users have no feedback confirming their click registered, leading to double-clicks or premature abandonment if the response is slow.
- **Fix:** On form submit, disable the button, replace 'Sign in' text with 'Signing in...' or a spinner, and visually dim the button (opacity: 0.6). Re-enable and restore original text if the request fails. This confirms action receipt and prevents duplicate submissions.
- **Provenance:** voice=`None` · principles=`p-0106`

### P1 — accessibility
- **Where:** http://localhost:3001/signup (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/signup_desktop.png)
- **Finding:** Page content is not wrapped in semantic landmark elements (axe 'region' violation). Screen reader users navigate pages by jumping between landmarks (main, nav, aside); when everything sits in a flat div structure, they lose that navigation shortcut. The signup form and 'Already have an account?' text should live inside a <main> landmark.
- **Fix:** Wrap the form and surrounding content in <main role='main'>. If the top navigation ('ZERGWALLET', 'Login', 'Sign up' links) is present, wrap that in <nav role='navigation'>. This gives screen reader users a predictable page structure.
- **Provenance:** voice=`None` · principles=`p-0002`, `p-0110`

### P1 — friction
- **Where:** http://localhost:3001/signup (`form input[type='password']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/signup_desktop.png)
- **Finding:** The password field has no visibility toggle. Users who mistype a password on signup must either submit and wait for an error, or delete and re-enter blind. This increases signup friction, especially on mobile where typing is slower and autocorrect often interferes.
- **Fix:** Add a show/hide password toggle button adjacent to the password field. On click, toggle the input type between 'password' and 'text', and swap the button icon/label between an eye icon (show) and a crossed-eye icon (hide). Ensure the toggle button has an accessible label for screen readers.
- **Provenance:** voice=`None` · principles=`p-0050`, `p-0109`

### P1 — copy
- **Where:** http://localhost:3001/signup (`h1, button[type='submit']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/signup_desktop.png)
- **Finding:** The text excerpt shows 'Create account' appearing twice in sequence, suggesting the h1 and submit button use identical text. This is visually redundant and misses an opportunity to make the CTA more action-oriented. The button should reinforce the immediate value or next step, not repeat the page title.
- **Fix:** Change the submit button text to 'Get started' or 'Create my account' to differentiate it from the h1. If the product has a clear immediate outcome (e.g., 'Start mining' for a crypto wallet), use that as the CTA to signal what happens after signup.
- **Provenance:** voice=`q-0001` · principles=`p-0047`, `p-0094`

### P1 — friction
- **Where:** http://localhost:3001/signup (`form`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/signup_desktop.png)
- **Finding:** No password requirements are communicated to the user before they type. Users who enter a password below the minimum length or missing required character types will only learn about the requirement after submit, forcing re-entry. This is a common abandonment point on signup forms.
- **Fix:** Display password requirements as helper text below or adjacent to the password field: 'Must be at least 8 characters with one uppercase letter, one number, and one special character' (or whatever the backend requires). Use inline validation on blur to show a green checkmark when the password meets requirements, or red error text if it does not.
- **Provenance:** voice=`None` · principles=`p-0060`, `p-0109`

### P1 — technical
- **Where:** http://localhost:3001/signup (`network`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/signup_desktop.png)
- **Finding:** A 401 error on /api/auth/me fires on page load. While this is expected behavior for an unauthenticated visitor hitting a signup page, the error appears in the console and may cause React/Vue hydration warnings or flash-of-wrong-content issues. If the app is checking auth state on every route, signup and login pages should skip that check.
- **Fix:** Add middleware or route guard logic to skip the /api/auth/me call on public routes (signup, login, password reset). Alternatively, handle the 401 silently on these pages without logging an error, since 'not authenticated' is the expected state.
- **Provenance:** voice=`None` · principles=`p-0106`

### P1 — mobile_seo
- **Where:** http://localhost:3001/signup (`form input[type='email'], form input[type='text']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/signup_mobile.png)
- **Finding:** The email field correctly uses type='email', but the first text field (likely username or full name) uses type='text' instead of a more specific type. On mobile, type='text' defaults to the full keyboard; if the field is for a username, it should use autocomplete='username' to trigger credential autofill. If it's for a name, it should use autocomplete='name'.
- **Fix:** Add autocomplete='username' to the first text field if it represents a username, or autocomplete='name' if it represents the user's full name. This triggers browser/OS autofill on mobile and desktop, reducing typing friction. Ensure all three fields have appropriate autocomplete attributes: username/name, email, and new-password.
- **Provenance:** voice=`None` · principles=`p-0061`

### P2 — copy
- **Where:** http://localhost:3001/ (`p`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/home_desktop.png)
- **Finding:** The value proposition lacks any quantified specificity—no transaction volume, number of supported chains, latency SLA, uptime metric, or cost comparison. Visitors evaluating custody solutions expect concrete numbers ('99.9% uptime,' 'supports 12 chains,' '$0.02 per transaction') to make a business case internally.
- **Fix:** Add at least one specific, measurable claim to the hero copy. Examples: 'Supports 8 chains including Ethereum, Polygon, and Solana,' 'Sub-second transaction confirmation,' or 'Used by 500+ production agents.' If metrics are not yet available, add them to a roadmap and prioritize instrumentation.
- **Provenance:** voice=`q-0001` · principles=`p-0032`, `p-0045`

### P2 — empty_state
- **Where:** http://localhost:3001/ (`main`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/home_desktop.png)
- **Finding:** The unauthenticated state message 'Sign in to view your workspaces' is passive and instructional rather than motivational. It doesn't teach the user what they'll gain by signing in or provide an intermediate action for hesitant visitors (watch demo, read docs, see pricing).
- **Fix:** Replace with an outcome-oriented message: 'Create your first agent wallet in under 60 seconds' or 'See how Zerg agents manage multi-chain funds.' Pair with a two-CTA layout: primary 'Start free' and secondary 'Watch demo' to reduce commitment anxiety.
- **Provenance:** voice=`None` · principles=`p-0024`, `p-0047`

### P2 — ia
- **Where:** http://localhost:3001/ (`nav`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/home_desktop.png)
- **Finding:** The top navigation presents 'Login' and 'Sign up' with no other links (Docs, Pricing, API, About). Visitors who want to evaluate the product before committing to an account have no intermediate path—they must either sign up immediately or leave.
- **Fix:** Add at least 'Docs' and 'Pricing' links to the top nav. If pricing is not yet public, add 'Features' or 'How it works' that expands the value prop with feature breakdowns, supported chains, and security architecture. This provides education paths for low-intent visitors.
- **Provenance:** voice=`None` · principles=`p-0108`, `p-0026`

### P2 — additive_feature
- **Where:** http://localhost:3001/ (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/home_desktop.png)
- **Finding:** There is no FAQ, security statement, or compliance badge section. Wallet and custody products face extreme trust barriers—users need to know how keys are managed, whether funds are insured, and what happens in breach scenarios before they deposit real value.
- **Fix:** Add a 'Security & Compliance' section with answers to common trust questions: 'How are private keys stored?', 'Is my wallet non-custodial?', 'What chains are supported?', 'Do you have SOC 2 / audit reports?' Link to a dedicated security page if content is extensive.
- **Provenance:** voice=`None` · principles=`p-0021`, `p-0065`

### P2 — consistency
- **Where:** http://localhost:3001/login (`nav, form + p`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/login_desktop.png)
- **Finding:** The 'Sign up' link appears twice: once in the top navigation and once below the form ('No account? Sign up.'). This redundancy is harmless but violates minimalist design principles and slightly increases visual noise.
- **Fix:** Remove the 'Sign up' link from the top navigation on the login page specifically, leaving only the contextual link below the form. Alternatively, keep the nav link and remove the redundant text below the form. The contextual placement is stronger because it appears after the user has already seen the login form.
- **Provenance:** voice=`None` · principles=`p-0111`

### P2 — technical
- **Where:** http://localhost:3001/login (`n/a (network request)`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/login_desktop.png)
- **Finding:** The page triggers a 401 error on load by requesting /api/auth/me before the user has authenticated. While this is likely intentional (checking for existing session), if error handling isn't graceful, it may log spurious errors to monitoring systems or briefly flash an error state to the user.
- **Fix:** Suppress or gracefully handle the 401 response from /api/auth/me on the login page. If the check is necessary, wrap it in a try-catch that silently redirects authenticated users to the dashboard and does nothing for unauthenticated users. Avoid logging 401s as errors in this specific context.
- **Provenance:** voice=`None` · principles=`p-0109`, `p-0106`

### P2 — copy
- **Where:** http://localhost:3001/login (`form button[type="submit"]`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/login_desktop.png)
- **Finding:** The primary CTA reads 'Sign in', which is generic and action-focused rather than outcome-focused. While this is a standard pattern and not broken, value-naming the CTA can incrementally improve click-through by framing the user benefit.
- **Fix:** Consider testing 'Access your wallet' or 'Log in to Zergwallet' to name the outcome rather than the action. This is a marginal improvement and optional — 'Sign in' is industry-standard and perfectly functional.
- **Provenance:** voice=`None` · principles=`p-0047`

### P2 — additive_feature
- **Where:** http://localhost:3001/login (`form`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/login_desktop.png)
- **Finding:** No 'Remember me' checkbox is present. For a crypto wallet, this omission may be intentional (forcing re-authentication improves security), but if sessions are long-lived by default, users may expect explicit control over session persistence.
- **Fix:** If sessions are short-lived (e.g., 1 hour), no action needed. If sessions persist across browser restarts by default, add a 'Keep me signed in' checkbox (unchecked by default) to give users explicit control. Include helper text: 'Not recommended on shared devices.'
- **Provenance:** voice=`None` · principles=`p-0108`, `p-0073`

### P2 — typography
- **Where:** http://localhost:3001/login (`form label`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/login_desktop.png)
- **Finding:** Cannot confirm from the payload whether form labels are top-aligned or left-aligned, but given the minimalist text excerpt, there may be no visible labels at all — only placeholder text. Placeholder-only fields are an anti-pattern: placeholder text disappears on focus, forcing users to recall what the field requires if they need to backtrack.
- **Fix:** Ensure each field has a persistent, top-aligned label ('Email address', 'Password') that remains visible when the field is focused or filled. Placeholders can remain as helper text ('e.g., you@example.com') but should not replace labels.
- **Provenance:** voice=`None` · principles=`p-0059`, `p-0110`

### P2 — additive_feature
- **Where:** http://localhost:3001/signup (`form`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/signup_desktop.png)
- **Finding:** The signup form offers only email/password registration. For a B2B SaaS product, OAuth signup (Google, GitHub, Microsoft) is table stakes — it reduces friction, eliminates password fatigue, and signals trust by association with known providers. Competitors in this space (Notion, Linear, Cursor) all offer OAuth as the primary signup path.
- **Fix:** Add OAuth signup buttons above the email/password form: 'Continue with Google', 'Continue with GitHub', 'Continue with Microsoft'. Use the provider's official branding (logo, color). Place a visual separator ('or' with horizontal rules) between OAuth and email signup. Track OAuth vs email signup rates to understand user preference.
- **Provenance:** voice=`q-0003` · principles=`p-0050`, `p-0062`

### P2 — additive_feature
- **Where:** http://localhost:3001/signup (`form`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/signup_desktop.png)
- **Finding:** No trust or privacy reassurance is visible near the signup CTA. B2B users — especially in crypto or finance — need explicit signals that their data will not be sold or misused. Competitors often include 'We never share your data' or 'GDPR compliant' micro-copy below the submit button.
- **Fix:** Add a single line of micro-copy below the submit button: 'By creating an account, you agree to our Terms of Service and Privacy Policy. We never share your data.' Link 'Terms of Service' and 'Privacy Policy' to the respective pages. Use a muted text color (#6b7280 or similar) to distinguish it from the CTA.
- **Provenance:** voice=`q-0006` · principles=`p-0065`, `p-0042`

### P2 — ux
- **Where:** http://localhost:3001/signup (`form input`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260503-215738-localhost/screenshots/signup_desktop.png)
- **Finding:** The form likely lacks input labels (none are visible in the text excerpt, which would include aria-label or visible label text). If the design uses placeholder-only labels, those disappear once the user starts typing, causing disorientation if they need to verify which field they're in. This is a common pattern mistake on minimal signup forms.
- **Fix:** Use persistent top-aligned labels for all fields: 'Name' (or 'Username'), 'Email', 'Password'. If the design requires placeholders, keep them as example values ('yourname@company.com') rather than repeating the label. Ensure labels are associated with inputs via for/id attributes or wrapped in <label> tags for screen reader compatibility.
- **Provenance:** voice=`None` · principles=`p-0059`, `p-0107`

