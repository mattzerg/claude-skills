# AI-stencil anti-patterns — the 2026 personal-site cliché playbook

These are the patterns that signal "AI generated this, not a designer." Each entry: name, why it reads as template, and the cure.

The 3 sites I shipped on 2026-05-07 (matteisn.com, vang.capital, vangadvisory.com) hit nearly all of these. Matt rated them 1/10. They are the ground truth examples.

---

## AP-1: blob-hero

**Pattern**: Hero contains 2-4 absolute-positioned `div` elements with gradient backgrounds, opacity 0.6, blur, and a `@keyframes float` animation.

**Why it's stencil**: This is the #1 visual signal of "I asked an LLM to make me a personal site in 2026." Every default v0/Lovable/AI-tool output uses some variant.

**Cure**: Use a single piece of real photography (the person, or a real artifact from their work — book cover, product screenshot, hand-drawn note). If no photo available, use a single piece of distinctive monochrome art — high-contrast B&W, halftone, or hand-drawn. Never use multiple animated blurred shapes.

**Concrete in our v2**: vang.capital `style.css` has `.art-blob`, `.blob-1` thru `.blob-4`, `@keyframes float`. vang-advisory the same. Delete entirely.

---

## AP-2: 4-stat-strip

**Pattern**: Full-width band with 3-4 large numbers separated visually, each with a small italicized label below: `60+ clients / 6 continents / $100M+ ARR / 7-fig revenue`.

**Why it's stencil**: This is the "trust band" template from every Webflow personal-site theme since 2021. The numbers feel like form fields. Often the numbers themselves are vague enough to be unverifiable.

**Cure**: One specific stat used as a pull quote in the hero or an interrupting block. NOT a 4-column grid. Better: the stat is embedded in a sentence that tells a story. "The 8 strategic investments I led DD on at NTT include Algorand, RELAYTO, and citizenM" beats "60+ clients / 6 continents."

**Concrete in our v2**: All 3 sites have a `.stats-strip` with 4 numbers. Delete or rewrite as a single in-line specific stat.

---

## AP-3: AI-default-type-pairing

**Pattern**: Inter (sans) + Fraunces (serif) loaded from Google Fonts CDN, with the headline using Fraunces-italic for accent.

**Why it's stencil**: These two fonts are the AI personal-site default in 2026. Half of the sites at v0.dev use this exact pairing. Fraunces-italic-headline is now ubiquitous.

**Cure**: 
- Single-font: pick one strong-character font (Söhne, Ranade, Mona Sans, IBM Plex Sans, GT America, Manrope) and use it everywhere
- Or: still Inter or similar grotesk, but pair with EB Garamond, Tiempos, Söhne Mono, IBM Plex Serif — anything not Fraunces
- Or: if you must use Fraunces, do it without italic-accent in headline

**Concrete in our v2**: All 3 sites import `Inter:wght@400;500;600;700&family=Fraunces:opsz...` from Google Fonts. Hero headlines use `<span class="serif italic">`. Replace.

---

## AP-4: stencil-section-order

**Pattern**: The site goes Hero → Currently → Selected (Roles/Portfolio/Clients) → Testimonials → Get in touch → Footer.

**Why it's stencil**: This is the AI's default IA when you tell it "build me a personal/agency landing page." Same shape, same order, same labels. Even when the words inside differ, the rhythm reads as template.

**Cure**: Find what's true and unrepeated about this person/firm and structure around it. For Matt: maybe Hero → "What I do this week" (Zerg, Vang, advisory all juxtaposed against each other) → "Things I've shipped" (mixed list, not categorized) → "Contact." Or for Vang Capital: Hero with thesis as huge text → 1 deep portfolio company callout → micro list of others → contact. The structure should feel non-obvious.

**Concrete in our v2**: matteisn.com goes Hero → Currently → Selected operating roles → Investment/Innovation → Research & honors → Testimonials → Get in touch → Footer. Textbook.

---

## AP-5: hover-up-cards

**Pattern**: Service/role/portfolio cards with `transform: translateY(-4px); box-shadow: 0 10px 30px rgba(0,0,0,0.08); transition: 0.2s;` on hover.

**Why it's stencil**: Single most over-used micro-interaction. Every Webflow template has it. Says nothing about the content.

**Cure**: Either no hover effect (rely on the design itself) or a content-specific hover that reveals something or makes a thematic statement (border-color flicker matching the brand, a specific cursor, a tiny content reveal). Generic uniform hover-lift is dead.

---

## AP-6: soft-tint-alt-section

**Pattern**: Sections alternate between `background: white;` and `background: #f8f7f3;` (or `#f6f7f9` cool, or `#f4f8f7` teal) — barely-there tints.

**Why it's stencil**: PowerPoint background-rotation. Reads as "I needed sections to feel different but couldn't commit." When the tints are subtle they feel weak.

**Cure**: Either pure white throughout (let content separate sections), OR commit to high-contrast section breaks (white vs. deep navy, or full-bleed photo, or full-color band). No half-measures.

**Concrete in our v2**: vang-advisory `--bg-alt: #f4f8f7;`. matteisn `--bg-alt: #f8f7f3;`. Delete the alt and use white throughout, or invert dramatically.

---

## AP-7: kicker-eyebrow

**Pattern**: Every section starts with a `.kicker` or `.section-kicker`: tiny, uppercase, letter-spaced, gray text reading "What we help with" / "Selected clients" / "How we work."

**Why it's stencil**: The eyebrow text adds noise and looks like Mailchimp template. Real designers either skip the kicker or make it feel intentional.

**Cure**: Drop the kicker entirely most of the time. The section title and content speak for themselves. If you want a label, make it a number or a date or something idiosyncratic ("§3" / "Spring 2026" / a footnote-style anchor).

---

## AP-8: 3-equal-testimonial-cards

**Pattern**: Testimonials section has 3 (always 3) equal-sized cards with quote + avatar + name + title.

**Why it's stencil**: Trust-signal template. Always 3, always equal-width, always with a tiny round avatar.

**Cure**: One huge pull quote dominating a section. Or zero testimonials (real personal sites often skip them). Or testimonials integrated into the body text as footnote-style asides. NOT 3 equal cards.

---

## AP-9: 4-col-footer-with-labels

**Pattern**: Footer is a 4-column grid: "Brand description" / "Family" / "Connect" / "Reach." Each column has a tiny H5 uppercase label and a list.

**Why it's stencil**: SaaS footer template. Personal sites don't need this much footer.

**Cure**: 1-line footer with copyright + maybe one link. Or a maximalist footer that's part of the design (like nytimes.com's footer is dense + intentional). Not the half-corporate org-chart style.

---

## AP-10: pill-button-pair

**Pattern**: Hero has 2 buttons side-by-side: one filled `background: var(--accent)`, one outline `border: 1px solid`. Both rounded `border-radius: 999px;`.

**Why it's stencil**: Bootstrap 4 levels of generic. Filled+outline pair is universal.

**Cure**: Single button (the only action that matters) styled distinctively. Or no buttons at all — just a visible email address as a styled inline link. Or unusual button shape (sharp corners, oversized, underlined-text style).

---

## AP-11: numbered-service-cards

**Pattern**: Services section with `01 / 02 / 03 / 04 / 05` overlay numbers on each card.

**Why it's stencil**: 2018 design trend that's now ubiquitous. Adds nothing.

**Cure**: Drop the numbers. Or replace with something specific (a year, a client name, a one-word identifier). If you're going to number, make it intentional — like sequential steps.

**Concrete in our v2**: vangadvisory has `01 Growth + GTM` through `05 Fractional growth leadership`. Drop numbers, or restructure as a non-list.

---

## AP-12: lazy-photo-treatment

**Pattern**: Personal site has a headshot in a circle, 200-400px, somewhere in the hero or a "currently" card.

**Why it's stencil**: Default avatar treatment. The circle hides the most expressive parts of a photo.

**Cure**: Use the photo at full size or near-full-bleed if it's good. Crop deliberately (top of head, hand, side profile). Put it somewhere unexpected. NOT a polite circle.

---

## AP-13: gradient-CTA-section

**Pattern**: "Get in touch" section has a dark or accent-colored full-bleed background, large headline, single button.

**Why it's stencil**: Every SaaS landing page since 2019. Dark CTA = template.

**Cure**: Email address as a styled inline link in the body. Or a CTA that's not a section but a sticky element (footer pinned with email always visible). Or the whole site has been a CTA so the section is unnecessary.

---

## AP-14: faux-handwritten-italic-script

**Pattern**: Decorative italic sometimes used as if it were "designer flourish."

**Why it's stencil**: Italic is doing too much work. Often pasted on a serif word in the headline.

**Cure**: Use weight contrast or size contrast for emphasis. Italic only when grammatically needed (book title, foreign word).

---

## AP-15: container-1080-everywhere

**Pattern**: Every section has `.container { max-width: 1080px; margin: 0 auto; padding: 0 24px; }` and content sits in this single column.

**Why it's stencil**: Content always centered in a generous gutter — feels safe, never bold.

**Cure**: Vary container widths per section. Hero might be edge-to-edge with content positioned 30% from left. A quote might break out of the container. A photo might full-bleed. Center column for body text only.

---

## Quick-detect: 5-question screen

When evaluating a draft, ask:

1. Could you swap the words for a generic operator's words and would the design still work? → STENCIL
2. Are there animated blurred shapes anywhere? → STENCIL
3. Is the type pairing Inter + Fraunces? → STENCIL (or borderline)
4. Are the section labels generic verbs ("What we help with", "How we work")? → STENCIL
5. Does the page have a 4-stat strip? → STENCIL

3+ yes = ship-blocker.
