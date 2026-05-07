# Case Study Corpus — 12 Exemplars

corpus_last_updated: 2026-05-05
corpus_archetypes: consulting-engagement / ai-transformation / platform-customer-story / boutique-technical-delivery
corpus_size: 12 entries (3 per archetype)

This corpus anchors the case-study-skill. It is a per-entry analysis of 12 case studies from leading firms — chosen to span the genre's archetypes that Zerg case studies will need to draw from. Use these to ground exemplar references in `review` and `scaffold` outputs ("Stripe × Notion does this well", "Plaid × X demonstrates the anti-pattern"). Don't over-cite — at most one exemplar per beat.

## Per-entry analysis schema

For each exemplar, this analysis captures:

1. **Source + archetype + word count** — for length calibration.
2. **Opening pattern** — challenge-first / outcome-first / company-portrait / cold-open / civilizational hook.
3. **Challenge framing** — how, when, and how specifically the problem is described.
4. **Why-them positioning** — how the vendor justifies its selection.
5. **Approach narrative** — phased / methodology-named / dated / sprawling.
6. **Solution detail** — features beat workstreams or vice versa; visual register.
7. **Outcome metric format** — value + unit + baseline + timeframe; count of metrics; placement.
8. **Customer quote** — placement + length + named attribution.
9. **Stack/tools used** — sidebar / inline / absent.
10. **CTA** — primary action; secondary CTAs.
11. **Visual register** — logos / headshots / screenshots / data viz.
12. **Distinctive move** — one feature worth borrowing for Zerg case studies.

---

## Archetype 1: Consulting engagement

These are case studies from elite consulting firms (McKinsey, BCG, Thoughtworks, Deloitte, Accenture). They tend to be longer, methodology-anchored, and outcome-heavy. The Zerg `kind: advisory` flavor draws from this archetype most directly.

### 1. McKinsey — "Reinventing the global supply chain"

- **URL pattern:** mckinsey.com/our-work (industrial supply chain client engagement)
- **Archetype:** consulting engagement / 1,800-2,200 words
- **Opening:** Challenge-first. "When [client], a global industrial manufacturer, faced a supply chain disrupted by [specific event], they needed to rebuild from inventory visibility up." No company portrait, no civilizational framing — straight to the constraint.
- **Challenge framing:** Dated and scoped within the first 150 words. Specific event named (often a public crisis the reader recognizes), specific operational metric impacted (lead times, inventory turns, supplier concentration).
- **Why McKinsey:** Single sentence, often phrased as a prior-engagement reference: "McKinsey's prior work on [adjacent client/sector] gave us pattern recognition on [the specific failure mode]." Never "we partnered with."
- **Approach:** **Phased and named** — McKinsey's signature move. Three or four phases ("Diagnosis", "Pilot", "Scale", "Operate"), each with a date range and a named output. Phases are the structural backbone.
- **Solution detail:** Workstreams beat features. The case study lists what the joint team built (operating-model redesigns, control-tower dashboards, supplier-tier-2 visibility tooling), not which McKinsey IP they used. The output is the deliverable, not the methodology.
- **Outcome metrics:** Heavy density. 5-8 named outcomes, each with value + baseline + timeframe (e.g., "lead times reduced from 14 weeks to 6 weeks within 9 months"). Outcomes appear in a dedicated "Impact" section near the end, often with a chart.
- **Customer quote:** Often absent. When present, it's a CFO/COO-level executive, ≤30 words, placed in the impact section. Named attribution.
- **Stack/tools:** Absent. Consulting case studies don't surface tooling — the methodology is the product.
- **CTA:** Always "Contact our team" or "Read more about our [practice area]". Single primary CTA.
- **Visual register:** Custom data viz (charts, before/after diagrams). Rarely customer headshots. Logos are restrained — single client logo near the top.
- **Distinctive move:** **Phase-named approach with date ranges.** Worth borrowing for Zerg's `kind: delivery` case studies. "Phase 1 — Discovery, weeks 1-3. Output: deployment plan." Beats vague "we worked together over several months."

### 2. BCG — "Helping a leading bank scale GenAI"

- **Archetype:** consulting engagement (AI flavor) / 1,500-1,900 words
- **Opening:** Outcome-tease. "Within nine months, [the bank] had moved from no production GenAI to 14 deployed use cases generating measurable cost reductions." Top-line specific number lands in para 1.
- **Challenge framing:** Two-part: business challenge (cost pressure, regulatory) + technical challenge (data fragmentation, governance). ~150 words combined.
- **Why BCG:** Specific capability — "BCG's Lighthouse [proprietary methodology] had been used at three peer banks." Names the IP; no shame in naming.
- **Approach:** Phased — "Discover → Build → Scale" — each phase tied to a deliverable. Diagrams appear here, not in the solution section.
- **Solution detail:** Mixed workstreams + features. Names specific use cases ("automated KYC summarization", "client-meeting prep"), each with a 2-3 sentence depth pass. Concrete enough to credible-flex without revealing client IP.
- **Outcome metrics:** 4-6 named outcomes. Mix of hard (cost reduction in $M) and soft (time saved per analyst per week). Always with a baseline. "30% reduction in time-to-prepare client meetings, from ~2 hours to ~40 minutes" is the canonical shape.
- **Customer quote:** One named exec quote, ≤40 words, named attribution (Head of Innovation level). Placed after results.
- **Stack/tools:** Tactically vague — "leveraged a leading foundation model and BCG's secure deployment scaffolding." Doesn't name vendors (preserves vendor-neutral positioning).
- **CTA:** "Contact us about your AI strategy" or "Read our GenAI playbook". Sometimes a download CTA for a related thought-leadership piece.
- **Visual register:** Custom diagrams. No customer faces. BCG branding restrained.
- **Distinctive move:** **Outcome-tease opening** — the strongest specific number in the very first sentence, before the challenge is even named. Borrow this for Zerg case studies where the outcome is unambiguously strong (e.g., a TVL or deployment-scale metric).

### 3. Thoughtworks — "Mercado Libre's digital platform transformation"

- **Archetype:** consulting / boutique technical / 2,000-2,500 words (long-form)
- **Opening:** Company portrait — "Mercado Libre is the largest e-commerce platform in Latin America, processing X transactions per second across 18 countries." Sets stakes via scale. Then transitions to the challenge in para 2.
- **Challenge framing:** Detailed. Names the specific architectural problem (monolith → microservices migration) and the business pressure (peak-traffic days breaking the platform). ~200 words.
- **Why Thoughtworks:** Named capability + multi-year relationship. "Thoughtworks had worked with Mercado Libre's platform team since 2014, including on [prior named project]." History as credibility.
- **Approach:** Heavily phased. Often has a timeline diagram. Multi-year engagement broken into named eras ("Phase 1: 2014-2016 monolith decomposition", "Phase 2: 2017-2019 platform extraction").
- **Solution detail:** Heavy on engineering specifics. Names the technologies ("Kafka, Kubernetes, custom service mesh"), the team structure ("co-located paired engineering", "rotating embed model"), and the cultural changes. This is the archetype for engineering-heavy case studies.
- **Outcome metrics:** Mix of business outcomes and engineering outcomes. "Service deployment cadence increased from monthly to ~50 per day" is the kind of metric this archetype lands. Always with a before/after.
- **Customer quote:** Often multiple — one engineering leader, one business leader. Named, ≤50 words each. Embedded in approach + impact sections.
- **Stack/tools:** Detailed inline mentions throughout the solution section. No sidebar — instead, technologies are named in context as they become relevant.
- **CTA:** Subdued — "Talk to our team" or "Explore our engineering culture". Thoughtworks under-CTAs versus Big-3 consulting.
- **Visual register:** Architecture diagrams; team-structure diagrams. Customer headshots rare.
- **Distinctive move:** **Multi-year era-by-era timeline.** Borrow for Zerg case studies where the engagement is genuinely long-running (Andesite-style multi-quarter commitments). Don't borrow for short pilots — would oversell.

---

## Archetype 2: AI transformation

These are AI-vendor case studies (Anthropic, OpenAI, Glean, Hebbia, Cohere). They tend to be tighter than consulting case studies, with metric-heavy openings and a strong "what changed for engineering teams" framing. The Zerg `kind: delivery` flavor for AI/ML deployments draws from this archetype.

### 4. Anthropic × Cursor

- **URL:** anthropic.com/customers/cursor (representative format)
- **Archetype:** AI transformation / 900-1,200 words (tight)
- **Opening:** Outcome-first. "Cursor uses Claude to power its AI code editor, helping engineers ship code faster." One sentence; the rest of para 1 immediately stacks specific numbers.
- **Challenge framing:** ~80 words, integrated with the opening. "Cursor needed a model that could handle long codebases and reason about cross-file context — a constraint that made smaller models insufficient."
- **Why Anthropic:** Brief, capability-anchored: "Claude's long-context handling and instruction-following matched Cursor's needs for reasoning across large repos." No history, no "partnership" language.
- **Approach:** Lightweight. Often single-paragraph: how the integration was done, who from each side worked on it, how long it took. Anthropic case studies don't dwell on approach.
- **Solution detail:** Foregrounds the customer's product, not the model. The Cursor case study is mostly about Cursor's features (composer, agent mode, tab completion) — Claude shows up as the engine in 1-2 paragraphs.
- **Outcome metrics:** 3-5 specific numbers, often in bullet list. Mix of customer-side ("X% faster to first PR", "N hours saved per engineer per week") and model-side ("Y tokens per second", "Z context window").
- **Customer quote:** One quote, ~30 words, named attribution at VP/C-level. Placed in middle, often as a pull quote.
- **Stack/tools:** Just Claude — and the model variant is named ("Claude 3.5 Sonnet", "Claude 4 Opus"). Show-the-work signal.
- **CTA:** Two-CTA shape: "Try Claude in the API" + "See more customer stories". Short, low-friction.
- **Visual register:** Hero screenshot of customer product. Customer logo. Sometimes a 30-second video clip embedded.
- **Distinctive move:** **Foreground the customer's product, not yours.** Anthropic's case studies read as Cursor stories more than Anthropic stories. Borrow for Zerg case studies where the client's product is the externally-visible win — e.g., CesiumAstro Atlas deployment foregrounds Atlas, not the underlying Zerg orchestration.

### 5. OpenAI × Klarna

- **Archetype:** AI transformation / 1,000-1,200 words
- **Opening:** Pure outcome-first, headline-grabbing number. "Klarna's AI assistant is now handling the equivalent workload of 700 full-time agents, resolving customer service issues in 2 minutes (down from 11)." This is the canonical "headline number" opener.
- **Challenge framing:** ~100 words, focused on scale of customer service ops (35M users, 24/7 multilingual support).
- **Why OpenAI:** Single line. "Klarna built on OpenAI's models because they needed multilingual capability and a reasoning ceiling that no smaller-model alternative offered." Specific.
- **Approach:** Brief. ~150 words. Names the integration partners (Klarna's internal AI team, OpenAI solutions engineers) and the timeline (development → pilot → rollout).
- **Solution detail:** Mid-depth. Describes what the AI assistant does (handles refunds, returns, payment disputes), the channels it operates on (in-app chat), and the human handoff model.
- **Outcome metrics:** Headline-tier. "Equivalent of 700 FTE agents", "$40M projected profit improvement in 2024", "~2/3 of all chats handled". 4-5 numbers, all with baselines or comparators.
- **Customer quote:** One quote, ~40 words, from the CEO (Sebastian Siemiatkowski). Named, placed prominently after results.
- **Stack/tools:** "GPT-4" named explicitly. Show-the-work signal.
- **CTA:** "Build with the OpenAI API" + link to enterprise contact form.
- **Visual register:** Klarna product screenshot, hero. CEO headshot inline with quote.
- **Distinctive move:** **Equivalent-workload framing.** "Equivalent of 700 FTE agents" is a more visceral framing than "$X cost saved" or "Y% efficiency gain". Borrow for Zerg case studies where the outcome is automation/throughput — e.g., "Metamorph generates connector reports that previously took an analyst N hours each."

### 6. Glean × Reddit

- **Archetype:** AI transformation / enterprise search / 1,200-1,400 words
- **Opening:** Hybrid challenge + outcome. "Reddit's engineers spent hours per week searching across Slack, Confluence, and GitHub for context. Glean cut that to seconds." Two sentences, paired.
- **Challenge framing:** ~120 words. Specific: enterprise search fragmentation, tribal knowledge problem, onboarding-time impact.
- **Why Glean:** Specific capability + result-oriented. "Glean's permissions-aware connectors meant we could index sensitive engineering docs without rebuilding our access model." Specific technical anchor.
- **Approach:** Lightweight, ~150 words. Phased ("pilot with one team", "expand to engineering", "company-wide rollout") but loose.
- **Solution detail:** Mixed. Foregrounds Glean's features (permissions-aware search, in-context AI answers, connector breadth) with a screenshot per feature. ~400 words.
- **Outcome metrics:** 4-5 metrics, mix of search-volume ("X queries per week") and outcome ("N hours saved per engineer per week", "engineer onboarding time reduced from N to M weeks"). Strong baseline discipline.
- **Customer quote:** One quote, ~40 words, from VP Engineering. Named, named title, named team scope. Placed after results.
- **Stack/tools:** Glean only — but lists the indexed sources (Slack, Confluence, GitHub, Notion, Drive) as a kind of inverse stack-used sidebar. "What we indexed" instead of "what we used."
- **CTA:** "Request a demo" + "See more customer stories". Two-CTA, demo-first.
- **Visual register:** Reddit logo, screenshots of Glean searching Reddit's docs. No headshot.
- **Distinctive move:** **"Indexed sources" sidebar.** A variant of the stack-used sidebar that makes sense for integration-heavy products. Borrow for Zerg case studies where the engagement involved connecting Zerg to a long list of client systems — list the systems integrated rather than the Zerg products used.

---

## Archetype 3: Platform customer story

These are platform-vendor case studies (Stripe, Vercel, Cloudflare, Snowflake, Databricks, Notion). They tend to be polished, screenshot-heavy, and stack-explicit. The Zerg `kind: delivery` flavor for platform-style integrations draws from this archetype.

### 7. Stripe × Notion

- **URL pattern:** stripe.com/customers/notion
- **Archetype:** platform customer story / 1,200-1,500 words
- **Opening:** Company-portrait. "Notion is an all-in-one workspace used by over 30 million people for tasks, docs, wikis, and projects." Sets stakes via scale; doesn't lead with the challenge.
- **Challenge framing:** Para 2. Specific: "scaling subscription billing across 190+ countries while supporting both individual and team plans." ~80 words.
- **Why Stripe:** Single sentence, capability-anchored. "Notion needed a billing platform that could handle complex pricing, global tax, and high-volume subscription operations from day one." Specific.
- **Approach:** Brief. ~100 words. Names which Stripe products were adopted in which order (Billing first, then Tax, then Connect for app marketplace).
- **Solution detail:** Mid-depth, ~400 words. Each Stripe product gets a 2-3 sentence pass: what Notion uses it for, what it replaces.
- **Outcome metrics:** 3-4 metrics, often softer than AI archetypes. "30+ million users supported", "190+ countries", "40% reduction in billing engineering effort" is the canonical shape. Some metrics are scale-of-operation rather than improvement.
- **Customer quote:** One quote, ~40 words, often from CFO or VP Finance. Named, placed mid-piece.
- **Stack/tools:** **Sidebar callout box.** "Stripe products used: Billing, Tax, Connect, Sigma." Bulleted, prominent. **The single most-borrowable feature for Zerg case studies.**
- **CTA:** "Talk to sales" + "Read more customer stories". Two-CTA, sales-first for B2B platform.
- **Visual register:** Notion product screenshot, hero. Stripe-Notion logo lockup. Sometimes a CFO headshot.
- **Distinctive move:** **Stack-used sidebar.** Pull this verbatim into the Zerg case-study template — for `kind: delivery`, every case study should have a "Zerg products used" sidebar listing exactly which Zstack components ran on the engagement. Self-documenting + answers the most common buyer question.

### 8. Vercel × Sonos

- **Archetype:** platform customer story / 1,400-1,700 words
- **Opening:** Hybrid. "Sonos rebuilt its consumer-facing site on Vercel and shipped 4× more product updates per quarter as a result." Outcome up front, but tied to a specific change action.
- **Challenge framing:** ~150 words. Specific: legacy WordPress monolith, 6-week deploy cycle, engineering bottlenecks for marketing changes.
- **Why Vercel:** Specific capability + DX framing. "Vercel's preview deployments let marketing PMs stage copy changes without engineering involvement, which broke the bottleneck."
- **Approach:** Loosely phased. Migration milestones named ("week 1: shadow deploys", "week 6: traffic split", "week 12: full cutover").
- **Solution detail:** Heavy on Vercel's primitives — incremental static regeneration, edge functions, image optimization. Each gets a 2-3 sentence deep dive with one screenshot.
- **Outcome metrics:** 5-6 metrics. Mix of performance (LCP, TTFB), velocity (deploys per week), and business (conversion lift, page-load-time-driven revenue). "4× more product updates per quarter" is the framing-anchor.
- **Customer quote:** One quote, ~50 words, from VP Engineering or Head of Web. Named, placed prominently after results.
- **Stack/tools:** Inline mentions throughout. Sometimes a "tech stack" callout near the top: "Next.js, Vercel, Sanity CMS, [other]." Mixed inline + sidebar approach.
- **CTA:** "Get started with Vercel" + "Talk to sales". Self-serve and enterprise CTAs.
- **Visual register:** Sonos product screenshots, hero animation. Performance dashboards inline (real Vercel analytics screenshots).
- **Distinctive move:** **Velocity-framed outcome.** "4× more product updates per quarter" beats "30% faster page loads" for a buyer audience that cares about shipping speed. Borrow for Zerg case studies where the win is throughput/deployment cadence rather than runtime performance.

### 9. Snowflake × Capital One

- **Archetype:** platform customer story (enterprise data) / 1,800-2,200 words (long-form)
- **Opening:** Company-portrait + scale framing. "Capital One operates one of the largest banking data ecosystems in the U.S., processing X billion transactions per day." Scale-first; positions the case study as a credibility flex for Snowflake.
- **Challenge framing:** ~250 words. Detailed: data warehouse modernization, governance, regulatory compliance, multi-petabyte scale. Names the prior architecture (Teradata) and the constraint (capex + agility).
- **Why Snowflake:** Specific capability — separation of compute and storage, governance primitives, scale economics. ~100 words; named technical advantages.
- **Approach:** Heavily phased. Often a multi-year migration, with each year named and tied to specific workloads moved.
- **Solution detail:** Workstreams + features mixed. Names which workloads moved (analytics first, ML second, etc.) and which Snowflake primitives backed each (Snowpark, Streams & Tasks, etc.).
- **Outcome metrics:** 6-8 metrics. Mix of operational (query latency, concurrent user counts) and business (cost reduction, new use cases enabled). Heavy baseline discipline.
- **Customer quote:** Multiple quotes — one from CIO/CTO, one from a data engineering leader. Named, paragraph-length.
- **Stack/tools:** Detailed inline. Sometimes a "Snowflake products used" sidebar near the top.
- **CTA:** "Contact sales" + a "Modernize your data platform" downloadable thought-leadership PDF.
- **Visual register:** Custom architecture diagrams. Capital One logo, Snowflake-Capital One lockup. Rare headshots.
- **Distinctive move:** **Multi-year migration framing for enterprise stakes.** Use for Zerg case studies where the engagement is a phased platform replacement (not a quick pilot) and the client cares about the depth of change demonstrated.

---

## Archetype 4: Boutique technical delivery

These are case studies from engineering-heavy boutique vendors (Vercel partner stories, Pivotal Labs, Modal, custom-software shops). Tighter than consulting case studies, denser than platform stories, and engineering-credibility-flex-heavy. The Zerg `kind: delivery` flavor for custom builds draws from this archetype most directly.

### 10. Vercel "Built with v0" partner stories

- **Archetype:** boutique technical delivery (V0-built sites) / 600-900 words (very tight)
- **Opening:** Outcome + speed. "[Partner] built and shipped [client]'s redesigned product page in 5 days using v0 and Vercel." Time-to-launch up front; this archetype trades on speed.
- **Challenge framing:** ~80 words. Always has a deadline element — "the team had two weeks to ship before [event/launch]."
- **Why partner/Vercel:** Combined. "v0's design-to-code generation plus the partner's senior engineers gave us a path to ship without scaling the team." One sentence.
- **Approach:** Often single-paragraph. Names the workflow: brief → v0 prompt → partner refinement → Vercel deploy. Tight.
- **Solution detail:** Light. ~200 words. Foregrounds the visible artifact — the shipped page or product. Less about the build process, more about what shipped.
- **Outcome metrics:** 2-3 metrics, sharp. Time-to-ship is always one. Sometimes traffic uplift or conversion delta. "Shipped in 5 days, 2× faster than original estimate" is the shape.
- **Customer quote:** Optional. When present, very short — 15-25 words, often from a marketing or product lead.
- **Stack/tools:** Inline mention. v0, Vercel, Next.js named in passing.
- **CTA:** "Find a Vercel partner" + "Try v0". Two-CTA, partner-discovery first.
- **Visual register:** Hero screenshot of the shipped artifact. Partner logo + client logo lockup. No headshot.
- **Distinctive move:** **Time-to-ship as the headline metric.** Borrow for Zerg case studies where speed-of-delivery is the win — e.g., a CesiumAstro Atlas deployment that went from contract to live in <60 days.

### 11. Pivotal Labs × Ford Labs (representative archetype)

- **Archetype:** boutique technical delivery (paired engineering) / 1,500-2,000 words
- **Opening:** Company-portrait + cultural-shift framing. "Ford built a new software organization, Ford Labs, modeled on lean software practices. Pivotal helped them get there in 18 months." Outcome + named methodology.
- **Challenge framing:** ~200 words. Cultural and technical: legacy automotive software practices, slow release cadence, talent challenges, OTA capability gap.
- **Why Pivotal:** Methodology-anchored. "Pivotal's paired-engineering model and TDD-first culture were what Ford needed to inject into a 100-year-old engineering org." Names the IP.
- **Approach:** Heavily phased and methodology-named. "Pair programming embed", "TDD discovery", "balanced team formation". This archetype's case studies are method-as-product.
- **Solution detail:** Mostly cultural + process. Names the team structure (one Ford engineer paired with one Pivotal engineer at a time), the practices (daily standups, retrospectives, paired tests). The shipped artifacts get less coverage than the changed working model.
- **Outcome metrics:** Mix of process (release frequency, defect rates, time-to-deploy) and cultural (NPS scores from internal engineering surveys, retention numbers). "Release cadence increased from monthly to weekly within 6 months" is the canonical shape.
- **Customer quote:** Multiple, often two — one from a Ford engineering leader, one from an embedded engineer. Both named.
- **Stack/tools:** Lighter than other archetypes. Mentions the practices more than the technologies.
- **CTA:** "Talk to us about your engineering transformation" — single CTA, sales-first.
- **Visual register:** Photos of paired engineers at workstations. Workshop photos. Customer logo. This archetype uses photos more than diagrams.
- **Distinctive move:** **Methodology-as-deliverable framing.** When the engagement output is a changed working model rather than shipped software, frame the case study around the methodology. Borrow for Zerg `kind: advisory` case studies where the win is "we taught the client how to operate the new system."

### 12. Modal × Suno

- **Archetype:** boutique technical delivery (compute platform) / 800-1,000 words (tight)
- **Opening:** Outcome + scale. "Suno generates millions of AI music tracks per day on Modal's serverless GPU infrastructure." One sentence; anchors scale and dependence.
- **Challenge framing:** ~100 words. Specific: training and inference at consumer-music scale, GPU cost management, latency requirements.
- **Why Modal:** Specific capability — fast cold-starts, GPU autoscaling, dev-loop ergonomics. ~80 words.
- **Approach:** Brief. ~150 words. Names how Suno deploys (decorator-based Python deployment), the migration story (from prior provider), and the team scope (small team).
- **Solution detail:** Heavy on Modal primitives — `@modal.function`, GPU types used, cold-start optimization. Code snippets inline. ~300 words.
- **Outcome metrics:** 3-4 metrics. "Cold-start time: <2s." "GPU cost per million inferences: $X." "Engineer-hours saved per week: N." All with baselines or comparators.
- **Customer quote:** One quote, ~30 words, from Suno's CTO or platform lead. Named, placed after solution.
- **Stack/tools:** Modal named throughout. Often inline code blocks showing actual production code. Sometimes a "stack" callout: "Python, PyTorch, Modal, [client-side stack]."
- **CTA:** "Try Modal" + "Read the docs". Self-serve developer CTA.
- **Visual register:** Code snippets. Sometimes a chart showing GPU utilization or cost. No headshots.
- **Distinctive move:** **Inline code snippets as proof.** When the engagement is technical and the audience is engineers, showing actual production code is the highest-credibility move. Borrow for Zerg case studies where the engagement involves Zerg code that customers can see (Atlas configurations, ZCloud orchestration manifests, etc.) — and where NDA permits it.

---

## Visual block coverage matrix

Mapping the 13 marketing-grade visual blocks (per `MattZerg/_style/case_study_style.md`) to which corpus exemplars use each. Used by the renderer at `~/.claude/skills/case-study-skill/render.py` to argue every block from corpus precedent rather than invention.

| Block | Stripe×Notion | Anthropic×Cursor | OpenAI×Klarna | Glean×Reddit | Vercel×Sonos | Snowflake×CapOne | McKinsey | BCG | Thoughtworks×ML | Pivotal×Ford | Modal×Suno | Vercel-v0 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1. Brand bar / logo lockup | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 2. Hero (H1 + dek) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 3. Stats strip (3-4 cells) | ✓ | ✓ | ✓✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  | ✓ | ✓ |
| 4a. Exec summary "At a glance" |  |  |  |  | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |
| 4b. About-customer sidebar | ✓✓ | ✓ |  | ✓ | ✓ | ✓ |  |  |  |  |  | ✓ |
| 5. Section eyebrows (01/02/...) |  |  |  |  | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  |
| 6. Phase cards / timeline |  |  |  |  | ✓ | ✓ | ✓✓ | ✓✓ | ✓✓ | ✓ |  |  |
| 7. Architecture diagram (SVG) |  |  |  |  | ✓ | ✓✓ | ✓ | ✓ | ✓ |  | ✓ |  |
| 8. Stack-used callout box | ✓✓ | ✓ |  |  | ✓ | ✓ |  |  | ✓ |  | ✓ |  |
| 9. Pull-quote (1, named) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓✓ | ✓✓ | ✓ |  |
| 10. Results bullets (cards) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 11. CTA box (dark inverse) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| 12. Related case studies footer | ✓ | ✓ |  | ✓ | ✓ | ✓ | ✓ | ✓ |  |  |  | ✓ |
| 13. Footer rule | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |

Legend: ✓ present · ✓✓ signature move (worth borrowing as the canonical shape).

**Read across rows:** every block has at least 4 corpus precedents, justifying its inclusion in the Zerg renderer. **Read down columns:** Stripe×Notion and Snowflake×Capital One ship the densest visual treatments (10+ blocks each); McKinsey and BCG ship roughly the same count via consulting-format conventions; Vercel-v0 partner stories ship the fewest (~7) because they're tight-format speed-led case studies.

**Signature moves to default to** (✓✓ in matrix):
- **Stack-used callout** — Stripe × Notion. Bullet list of products + role on the engagement. The single most-borrowable block. Mandatory for `kind: delivery`.
- **Phase cards** — McKinsey, BCG, Thoughtworks. Renders Approach as 3-card horizontal grid, not prose blob.
- **Architecture diagram** — Snowflake × Capital One. SVG showing the deployed shape. Mandatory when work is technical + NDA permits.
- **Multiple named quotes** — Pivotal × Ford, Thoughtworks × ML. Two quotes (engineering-side + business-side) when the engagement has both audiences. **Cap at 2; never 3+** (Anthropic 13-quote carousel is the canonical anti-pattern).
- **Outcome-tease opening + headline metric** — OpenAI × Klarna ("equivalent of 700 FTE agents"). Lead with the strongest specific number when the win is unambiguous.

## Synthesis — what to steal first

For Zerg case studies, the highest-leverage moves to copy across all four archetypes:

1. **Stack-used sidebar (Stripe × Notion).** Mandatory for `kind: delivery`. Lists exact Zstack products used.
2. **Phased approach with date ranges (McKinsey).** "Phase 1 — Discovery, weeks 1-3. Output: deployment plan." Beats vague approach prose.
3. **Outcome-tease opening (BCG).** Lead with the strongest specific number when the outcome is unambiguous.
4. **Equivalent-workload framing (OpenAI × Klarna).** "Equivalent of N FTE analysts" or "previously took an engineer X hours" — visceral framing for automation wins.
5. **Customer-product foregrounding (Anthropic × Cursor).** When the client's product is the externally-visible win, foreground it; Zerg's role shows up as the engine in 1-2 paragraphs.
6. **Time-to-ship as headline (Vercel × v0).** When speed-of-delivery is the win, lead with it.
7. **Inline code snippets (Modal × Suno).** For engineering-audience case studies where NDA permits.

## Anti-patterns observed across the corpus

- **"Partnered with"** — surfaces in mid-tier case studies, almost never in elite consulting or top platform stories.
- **Quote carousels** — 5+ quotes in a single case study reads as desperation. Anthropic and Glean cap at 1 named quote; Stripe at 1; consulting often at 0.
- **Logo walls without narrative** — logos on a page without a per-client story aren't case studies, they're trust badges. Don't conflate.
- **Solo metrics without baselines** — "30% faster" without a from/to is the most common failure mode. Always pair with a baseline.
- **"Transformative journey" register** — McKinsey and BCG carefully avoid this; mid-tier consulting case studies fall into it. Watch for it in Zerg drafts.
