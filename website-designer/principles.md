# Website design principles — personal & agency

Codified from sites Matt rates 8+, with the aesthetic Matt actually responds to.

## 1. Distinctiveness over polish

A 7/10 distinctive site beats a 9/10 generic site. The polish floor of AI-generated personal sites is now high enough that polish alone signals "made by tool, not by person."

**Test**: Could you swap this site's headline + photo for any other personal site without anyone noticing? If yes, it's generic.

## 2. Typography is identity

Inter + Fraunces is fine but it's now the AI-personal-site default pairing. At least one of these should be true:
- Use a less common pairing (eg Söhne, GT America, Ranade, Fraunces *with custom optical-size axis*, EB Garamond, IBM Plex, Tiempos, Söhne)
- Use a SINGLE font with strong character (Söhne for everything, or Ranade for everything)
- Use a custom font (paid or open-source like Mona Sans, Geist, Manrope, Fraktion)
- If you DO use Inter+Fraunces, deviate elsewhere significantly

**Anti-pattern signal**: Inter sans + Fraunces serif w/ italic accent in headline.

## 3. Hierarchy through size, not noise

One thing dominates per screen. The AI-stencil failure mode is cramming the hero with kicker + huge headline + lede + 2 buttons + photo + abstract blob — that's 6 competing elements.

**Better**: One absurdly large headline, OR a single piece of imagery, OR one quote. Whitespace doing the work.

Reference: frankchimero.com — homepage is essentially text with massive whitespace and a single photo.

## 4. Color: 1 strong accent, lots of neutral

Cap accent usage at ~5% of pixels. Neutral 90%+. Color used to direct the eye to one thing per section, not to "decorate."

**Anti-pattern**: Soft-tint backgrounds for sections (`#f8f7f3` warm, `#f6f7f9` cool, `#f4f8f7` teal) and "alt" sections with slightly different tints. Reads as PowerPoint background-color-rotation. Use full white OR full deep-color, alternation should be more dramatic.

## 5. Photography > stock > illustration > abstract gradient blob

If you have a real photo of the person, use it large and uncropped. If you don't, prefer monochrome B&W abstract texture over a colored gradient blob.

**Anti-pattern**: animated gradient blobs / orbs / shapes as "hero accent." This is the #1 AI-stencil tell of 2026.

## 6. Specificity > Lists

A specific quote with a name ("$60m TVL in 24 months at Dinari") beats a generic stat strip ("0X/Y/Z"). Lists of 4 numbers feel like a template field-row.

**Test**: Is the section telling me a story or filling fields?

## 7. Voice is structural, not just a paragraph

The site's *organization* should reflect the person's identity. If you build "Currently / Selected Roles / Testimonials / CTA" then the structure is stencil — the words inside don't compensate.

**Better**: Custom structure derived from THIS person's actual story arc. If Matt is "operator first, allocator second" then the structure should *enact* that — operator stuff dominates, allocator stuff is sidebar.

## 8. Density signals confidence

Premium personal sites are often denser than mid-tier ones. AI-stencil sites use enormous padding everywhere because that's the safe move. Real designers know when to crowd.

**Test**: Does the page have any moment where a lot of information is packed tight (like a published-resume density)? If everything is `padding: 96px 0;` it's stencil.

## 9. Idiosyncrasy budget

Every site needs at least 3 things that aren't in any template:
- A non-rectangular section (eg a quote that breaks the column grid)
- A footnote / aside / pull-out that interrupts
- A specific micro-interaction tied to specific content (not a generic hover lift)
- A unique color call-out that ONLY appears once
- An off-grid image
- Hand-set kerning on the wordmark
- A handwritten note / scribble / signature scan

Without 3+ of these, the site reads as machine-generated.

## 10. The 1-second test

Open the URL. After 1 second, what's the impression? "Personal site of operator/investor based in SF" is generic. "Oh, this person is —" with a SPECIFIC adjective is good.

Goal: someone who lands on the site can describe its personality in one specific word that distinguishes it from 10 other operator personal sites.

## 11. Footer ≠ feature

Multi-column footer with "Connect / Companies / Based in" is template. Real personal sites either:
- Have NO footer (just site map link or copyright)
- Have a maximalist footer that's part of the design (not just an org chart of links)

The stencil footer with kicker + lists in 4 columns is dead.

## 12. The Webflow trap

Sites built in Webflow (or any low-code tool) tend toward the same defaults:
- Full-bleed alternating sections with subtle bg color
- 4-column grids
- Hover-up cards with soft shadow
- Pill buttons with one filled + one outline
- "Service icon + title + 1-line description" cards

These all exist in our 3 sites. They are the tell.

## 13. Rhythm > uniform spacing

AI-stencil sites have one section padding (96px) everywhere. Real designs vary section heights. Hero might be 400px, services 800px, quote 200px, portfolio 1200px.

## 14. Rejection list — auto-fail on these

If a design has any of these, it fails the bar:
- Animated gradient blob art in hero
- 4-number stat strip with `/` separators
- "Currently" → "Selected X" → "Testimonials" → "Get in touch" generic structure
- Inter+Fraunces with italic-accent in headline as ONLY type system
- Universal `padding: 96px 0;` on every section
- Hover-up cards with soft shadow as the only interaction
- Soft-tint alt-section backgrounds (`#f5f5f0` etc)
- 3 or 4 perfectly-equal-sized testimonial cards in a row
