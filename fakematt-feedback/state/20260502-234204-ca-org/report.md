# Fake Matt feedback — https://ca-org.fly.dev/org-chart

_Reviewed 2026-05-02 23:47; 3 pages, 18 findings (0 rejected for missing provenance)._

**Severity:** P0=4 · P1=11 · P2=3

## If I only fix three things
- axe flags html-has-lang as **serious** — every screen reader defaults to OS-detected language when this attribute is absent, mispronouncing content and breaking all language-dependent AT behavior from the root element down. This is a one-attribute fix with zero excuse for being absent in production.
  - **Fix:** Add lang="en" (or the appropriate BCP 47 locale tag) to the <html> element. Resolves the axe violation in under one minute.
- The login page has one CTA (Sign in) and one escape (Forgot username/password?) — and nothing for the user who doesn't have credentials. A first-time user arriving via a shared link hits a dead end: no instruction, no action to take, no next step. That's not a login page; that's a wall. The page fails to convert on its own differentiating premise the moment anyone without an account lands on it.
  - **Fix:** Add a secondary link below the form: "Don't have an account? Contact your admin" linked to a mailto or provisioning request form. If self-serve signup is intentionally off, that's an acceptable product decision — but the page must acknowledge users without credentials and give them a forward path.
- Both form fields have empty `name` attributes. Password managers — 1Password, Bitwarden, browser autofill — key off `name` to match and fill credentials. An enterprise user who can't autofill hits a dead stop at the front door before they've seen a single feature. This isn't a polish issue; it's a login gate that actively discourages re-entry.
  - **Fix:** Add `name="email"` to the email input and `name="password"` to the password input. Also add `autocomplete="email"` and `autocomplete="current-password"` respectively — required for WHATWG autofill contracts that all major password managers rely on.

## All findings

### P0 — accessibility
- **Where:** https://ca-org.fly.dev/login (`html`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** axe flags html-has-lang as **serious** — every screen reader defaults to OS-detected language when this attribute is absent, mispronouncing content and breaking all language-dependent AT behavior from the root element down. This is a one-attribute fix with zero excuse for being absent in production.
- **Fix:** Add lang="en" (or the appropriate BCP 47 locale tag) to the <html> element. Resolves the axe violation in under one minute.
- **Provenance:** voice=`q-0022` · principles=`p-0002`

### P0 — cta
- **Where:** https://ca-org.fly.dev/login (`form`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** The login page has one CTA (Sign in) and one escape (Forgot username/password?) — and nothing for the user who doesn't have credentials. A first-time user arriving via a shared link hits a dead end: no instruction, no action to take, no next step. That's not a login page; that's a wall. The page fails to convert on its own differentiating premise the moment anyone without an account lands on it.
- **Fix:** Add a secondary link below the form: "Don't have an account? Contact your admin" linked to a mailto or provisioning request form. If self-serve signup is intentionally off, that's an acceptable product decision — but the page must acknowledge users without credentials and give them a forward path.
- **Provenance:** voice=`q-0006` · principles=`p-0047`, `p-0108`

### P0 — friction
- **Where:** https://ca-org.fly.dev/login (`form input[type='email'], form input[type='password']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/login_desktop.png)
- **Finding:** Both form fields have empty `name` attributes. Password managers — 1Password, Bitwarden, browser autofill — key off `name` to match and fill credentials. An enterprise user who can't autofill hits a dead stop at the front door before they've seen a single feature. This isn't a polish issue; it's a login gate that actively discourages re-entry.
- **Fix:** Add `name="email"` to the email input and `name="password"` to the password input. Also add `autocomplete="email"` and `autocomplete="current-password"` respectively — required for WHATWG autofill contracts that all major password managers rely on.
- **Provenance:** voice=`q-0015` · principles=`p-0061`, `p-0050`, `p-0109`

### P0 — accessibility
- **Where:** https://ca-org.fly.dev/login (`html`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/login_desktop.png)
- **Finding:** The `<html>` element has no `lang` attribute — a serious axe violation. Screen readers default to whatever language the OS is set to, meaning an English page gets read in whatever locale the assistive tech assumes. For a product targeting enterprise teams (where procurement reviews include accessibility compliance), this is a compliance gap, not a cosmetic one.
- **Fix:** Add `lang="en"` to the `<html>` element. One attribute, zero effort, eliminates the serious-impact axe violation.
- **Provenance:** voice=`q-0022` · principles=`p-0002`, `p-0107`

### P1 — accessibility
- **Where:** https://ca-org.fly.dev/login (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** Two landmark violations fire together: no <main> element (landmark-one-main) and 5 content nodes outside any landmark region (region). On a login page where the entire job-to-be-done is a single form, forcing AT users to tab through every unfenced element before reaching the email field is friction on the only critical path the page has. The brand lockup, form, and surrounding content are all structurally invisible to landmark-navigation users.
- **Fix:** Wrap the brand lockup in <header> and the login form in <main>. One structural pass resolves both violations and costs under 10 minutes.
- **Provenance:** voice=`q-0024` · principles=`p-0002`, `p-0106`

### P1 — accessibility
- **Where:** https://ca-org.fly.dev/login (`.login-form h2, [class*='title']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** axe page-has-heading-one fires — "Sign in" exists as visual copy but not as a semantic h1, which means screen reader users navigating by heading land on a page with no document anchor. The visual treatment is irrelevant; the semantic outline is broken at the top level.
- **Fix:** Render "Sign in" as an <h1>. Visual size and weight are controlled by CSS independently. Zero layout impact, full heading-hierarchy fix.
- **Provenance:** voice=`q-0017` · principles=`p-0030`

### P1 — ux
- **Where:** https://ca-org.fly.dev/login (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** The page silently redirects /org-chart to /login with zero context. A user following a shared link to the org chart gets bounced to a sign-in screen with no message explaining why or what they're about to access after authenticating. Nielsen's first heuristic requires users to always know where they stand — this page fails that at the first pixel for every user arriving from a direct or forwarded URL.
- **Fix:** Detect redirect origin and surface a contextual flash above the form: "Sign in to view the org chart." Preserve the intended destination as a ?next=/org-chart param for automatic post-login redirect. 15 minutes of work with a measurable drop in sign-in abandonment.
- **Provenance:** voice=`q-0015` · principles=`p-0106`, `p-0108`

### P1 — positioning
- **Where:** https://ca-org.fly.dev/login (`div.login-brand`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** "Operations Atlas ORG" is a product name with zero description of what it does or what the user is authenticating into. An infrequent user arriving from a bookmark, a forwarded link, or a password manager autofill has no anchor for what this tool is. The brand lockup does less work than a favicon.
- **Fix:** Add a single-line descriptor directly beneath the product name: e.g., "Live org chart for [Company Name]" or "Your organization's reporting structure." One line of copy, no layout changes, eliminates all ambiguity for every user who doesn't log in daily.
- **Provenance:** voice=`q-0017` · principles=`p-0044`, `p-0107`

### P1 — friction
- **Where:** https://ca-org.fly.dev/forgot-password (`form input[type='email']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/forgot-password_desktop.png)
- **Finding:** The email field has no `name` attribute (`name=""`). Browser password managers and autofill use the name attribute to identify fields — without it, saved email addresses won't populate and mobile users have to type their address manually every time. On a recovery page where the user is already locked out, adding a manual typing burden is a second failure stacked on the first.
- **Fix:** Add `name="email"` and `autocomplete="email"` to the input element. Two attributes, zero rework.
- **Provenance:** voice=`q-0009` · principles=`p-0061`

### P1 — accessibility
- **Where:** https://ca-org.fly.dev/forgot-password (`html`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/forgot-password_desktop.png)
- **Finding:** The `<html>` element has no `lang` attribute — axe rates this serious. Screen readers fall back to the OS language setting, producing incorrect pronunciation for any non-English content and failing WCAG 3.1.1. This is a one-line fix that closes a real accessibility liability on a page that handles account recovery, where assistive technology use is disproportionately high.
- **Fix:** Add `lang="en"` (or the appropriate BCP 47 language tag) to the `<html>` element.
- **Provenance:** voice=`q-0009` · principles=`p-0002`

### P1 — accessibility
- **Where:** https://ca-org.fly.dev/forgot-password (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/forgot-password_desktop.png)
- **Finding:** The page has no `<main>` landmark and axe flags 6 content nodes living outside any landmark region. Keyboard and screen reader users navigating by landmark skip straight past the form — they land on the page and have no structural anchor to the recovery flow. Landmark violations on a form-only page with a single job to do are hard to excuse.
- **Fix:** Wrap the kicker, heading, instruction copy, and form in a single `<main>` element. Move the 'Back to sign in' link inside or immediately after `<main>`. Ensure nothing visible sits outside header/main/footer.
- **Provenance:** voice=`q-0009` · principles=`p-0002`, `p-0110`

### P1 — friction
- **Where:** https://ca-org.fly.dev/forgot-password (`form`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/forgot-password_desktop.png)
- **Finding:** There is no indication of inline validation on the email field. A malformed address submitted to this form surfaces its error post-submit — the user has to re-read the page, identify the field, and re-type. On a recovery flow where the user is already frustrated, submit-time errors compound the problem instead of resolving it. Every competitor auth form validates email format on blur.
- **Fix:** Add blur-time validation: if the value doesn't match a basic email pattern, display an inline error directly beneath the field — 'Enter a valid email address' — before the user clicks submit. Don't wait for the round-trip.
- **Provenance:** voice=`q-0022` · principles=`p-0060`, `p-0008`

### P1 — accessibility
- **Where:** https://ca-org.fly.dev/login (`body`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/login_desktop.png)
- **Finding:** No `<main>` landmark exists, and 5 content nodes sit outside any landmark region. Screen reader users navigating by landmark — the standard skip-nav pattern — land in a void. The `page-has-heading-one` violation compounds this: the visible 'Sign in' heading is not an H1, so document structure is flat. Three moderate axe violations on a single login page signals that accessibility was never tested, which raises questions about the rest of the product.
- **Fix:** Wrap the login card in `<main>`. Promote the 'Sign in' heading to `<h1>`. This resolves landmark-one-main, region, and page-has-heading-one in one pass.
- **Provenance:** voice=`q-0024` · principles=`p-0002`, `p-0003`, `p-0106`

### P1 — copy
- **Where:** https://ca-org.fly.dev/login (`a[href*='forgot-password']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/login_desktop.png)
- **Finding:** 'Forgot username/password?' implies the login field accepts a username, but the form takes an email address. Users don't 'forget' their email — they forget their password. The conflated copy creates a half-second of doubt ('wait, do I have a username for this?') that is unnecessary friction at a moment when the user just wants to get in.
- **Fix:** Change link text to 'Forgot password?' or 'Reset password' — whichever matches the actual recovery flow. If the system does support a separate username field somewhere, separate the two recovery paths.
- **Provenance:** voice=`q-0017` · principles=`p-0107`, `p-0022`

### P1 — ux
- **Where:** https://ca-org.fly.dev/login (`form`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/login_desktop.png)
- **Finding:** No inline validation is detectable from the payload — errors will surface only on submit. A user who miskeys their email format or caps-locks their password gets no signal until they've already clicked through. Submit-only validation forces backtracking to a field that's no longer in context, and on a login form where every failed attempt erodes confidence, preventing that error in the first place is worth more than recovering gracefully from it.
- **Fix:** Add blur-triggered inline validation on the email field (format check) and a visible caps-lock warning on the password field. Surface credential error messages inline adjacent to the relevant field, not just as a banner above the form.
- **Provenance:** voice=`q-0015` · principles=`p-0060`, `p-0109`, `p-0008`

### P2 — copy
- **Where:** https://ca-org.fly.dev/login (`a[href='/forgot-password']`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/org-chart_desktop.png)
- **Finding:** "Forgot username/password?" conflates two distinct recovery flows into one ambiguous CTA. Password reset is automated via email; username recovery usually isn't. A user who only forgot their password pauses on "username" unnecessarily — micro-friction at the one moment they're already stuck.
- **Fix:** Change to "Forgot password?" unless a genuine, distinct username recovery flow exists and is reachable from the same destination. If both flows exist, split into two separate links with explicit labels.
- **Provenance:** voice=`q-0022` · principles=`p-0050`, `p-0047`

### P2 — copy
- **Where:** https://ca-org.fly.dev/forgot-password (`p.page-kicker ~ p`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/forgot-password_desktop.png)
- **Finding:** "Enter your work email and we will send a reset link" sets no expectation for when the email arrives. Users who don't see it in 30 seconds will submit again (creating duplicate tokens) or open a support ticket. The instruction is also silent on spam filtering — a near-universal failure mode for transactional email. Vague copy that doesn't answer the next obvious question forces support to answer it instead.
- **Fix:** Update to: "Enter your work email. We'll send a reset link within a few minutes — check your spam folder if it doesn't arrive." Optionally surface a support contact link beneath the CTA for users whose email domain blocks transactional mail.
- **Provenance:** voice=`q-0017` · principles=`p-0106`

### P2 — technical
- **Where:** https://ca-org.fly.dev/login (`html`)
- ![](/Users/mattheweisner/.claude/skills/fakematt-feedback/state/20260502-234204-ca-org/screenshots/login_desktop.png)
- **Finding:** Page title is 'Operations Atlas' with no suffix indicating login state (e.g., 'Sign In — Operations Atlas'). Browser tabs, OS-level window switchers, and screen reader page announcements all read the title verbatim. For a user with multiple tabs open, this makes the login tab indistinguishable from any other app page.
- **Fix:** Set `<title>Sign In — Operations Atlas</title>`. Consistent title patterns across all pages also improve screen reader navigation and reduce user confusion in multi-tab workflows.
- **Provenance:** voice=`q-0024` · principles=`p-0106`, `p-0107`

