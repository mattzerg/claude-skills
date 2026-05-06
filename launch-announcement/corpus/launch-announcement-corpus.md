# Launch Announcement Corpus Scan

Source set: 15 canonical launch posts from technical/B2B SaaS companies (May 2024 – April 2026). Goal: extract the structural and rhetorical conventions of the genre so a Claude skill can mimic the best-practice template without re-reading the corpus.

## Per-announcement analysis

### 1. Stripe — Sessions 2026 ("Everything we announced") — https://stripe.com/blog/everything-we-announced-at-sessions-2026

1. Stripe / Sessions 2026 product roundup / ~8,500 words.
2. Cold open with the news (no scene, no problem). First sentences: *"This morning at our annual conference, Stripe Sessions, we shared 288 new products and features with more than 9,000 business leaders and builders. We're making Stripe even more programmable; protecting and propelling your business with the strength of the Stripe network; and building economic infrastructure for AI."*
3. News in **paragraph 1, top ~2%**. Stripe never withholds — the lead is the news.
4. Beats present, in order: news (1) → three pillars (2) → product-by-product walkthrough across 7 verticals (Payments, Radar, Revenue, Money Mgmt, Embedded Finance, Stablecoins, Platform) (3) → forward roadmap by quarter (4) → CTA (5). No problem framing, no customer testimonial as a discrete block — customer names are inlined as proof points throughout. No pricing or "how to get it" because most features auto-roll to existing accounts.
5. Specificity: *"Millions of global businesses use Stripe Radar to fight fraud, from leading AI companies like OpenAI, Anthropic, ElevenLabs, and Cursor to global enterprises like PepsiCo and Hertz."* Plus *"increase acceptance rates by an average of 3.8% and lower processing costs by up to 3.3%"* and *"Stripe Connect powers more than 16,000 platforms, including Shopify, DoorDash, and Substack."* Customer logos are used as table-stakes credibility, not as testimonials.
6. First-person plural, professional-but-confident, light technical depth. Rep sentence: *"We're making Stripe even more programmable; protecting and propelling your business with the strength of the Stripe network; and building economic infrastructure for AI."*
7. CTA: *"Like this post? Join our team."* (recruiting CTA, not product) plus a contact link. Surprising — they don't sell, they recruit.
8. Headline pattern: structural/declarative (*"Everything we announced at Sessions 2026"*). Not a product name, not benefit-led — it's an event recap framing.
9. One hero banner; section header images per vertical; no inline screenshots, no code, no embedded video. Light visual density for an 8.5K-word post.
10. Distinctive: the **288 number in sentence 1** and the **quarter-by-quarter forward roadmap** — Stripe is making credibility moves that few others make. Recruiting CTA at the end is a confidence move ("we're growing, you should join us").

---

### 2. Linear — Linear Agent — https://linear.app/changelog/2026-03-24-introducing-linear-agent

1. Linear / Linear Agent / ~2,100 words.
2. Cold open with the news, but unusually deferential. First sentences: *"We're excited to share the next major step in Linear's evolution. For the vision behind Linear Agent, read the letter from our CEO, Karri."* They split the announcement into "tactical post + vision letter" — this is the tactical one.
3. News headline + opening = top **~3%**. The substance ("Linear Agent brings all of that context within reach") lands in **paragraph 3, ~15%** — there's a brief problem framing first about "execution bottlenecks."
4. Beats: news (1) → very short problem framing (2) → core capabilities (3) → use-case examples (4) → forthcoming features (Code Intelligence) (5) → availability and pricing (6) → standard changelog footer with Improvements/Fixes/API Updates (7). The changelog footer is structurally distinctive — every Linear post bolts on bug fixes/keyboard shortcuts at the bottom, regardless of headline news.
5. Specificity: thin. *"In Slack, send: '@Linear Make issues based on the discussion here and assign them to me.'"* No customer names, no benchmarks, no metrics. Linear leans on **demonstrative use cases** instead of numbers.
6. First-person plural, conversational-professional. Rep sentence: *"For example, when starting a new project, instead of manually researching past feature requests, you can ask Linear to find related issues, group them by relevance, and pull the right ones in."*
7. CTA: none explicit. The post just dissolves into the changelog footer. (This appears to be a deliberate Linear pattern — the changelog page itself is the CTA.)
8. Headline: short noun-phrase product name (*"Introducing Linear Agent"*).
9. Moderate: video player at top, 2 inline screenshots, no code, no diagrams.
10. Distinctive: the **CEO vision letter / tactical post split** is unusual and lets Linear keep the launch post tight while still publishing the why-we-built-this rhetoric. Also: the **changelog tail** (improvements / fixes / API updates / shortcuts appended to every product launch) makes the announcement feel like part of an ongoing rhythm, not a one-off marketing event.

---

### 3. Vercel — Fluid Compute — https://vercel.com/blog/introducing-fluid-compute

1. Vercel / Fluid Compute / ~1,050 words.
2. Problem-first open. First sentences: *"While dedicated servers provide efficiency and always-on availability, they often lead to over-provisioning, scaling challenges, and operational overhead. Serverless computing improves this with auto-scaling and pay-as-you-go pricing, but can suffer from cold starts and inefficient use of idle time."*
3. News lands in **paragraph 2, ~12%** — *"It's time for a new, balanced approach… reduces compute costs by up to 85%."* The post is a textbook "set up the dichotomy, then dissolve it with our product."
4. Beats: problem framing (1) → market/incumbent context [servers vs serverless] (2) → news (3) → six principles of Fluid (4) → technical mechanism (cold starts, scaling, multi-region) (5) → activation instructions / CTA (6). No customer quote, no pricing, no roadmap.
5. *"reduce compute costs by up to 85%."* That's the only number in the post. Vercel relies on the architectural argument, not benchmarks.
6. First-person plural, formal-technical. Rep sentence: *"Fluid embraces a set of principles that optimize performance and cost while establishing a vision for meeting the demands of today's dynamic web."* Slightly grandiose for the genre.
7. CTA: *"Enable Fluid compute today"* button → docs.
8. Headline: noun-phrase product name (*"Introducing Fluid compute: The power of servers, in serverless form"*) with a benefit-y subtitle that frames the dichotomy.
9. Sparse — no inline images noted, no code, no diagrams. (A second post, "How we built serverless servers," carries the technical detail and diagrams.)
10. Distinctive: the **principles list** as a structural beat (six bullets, each with a one-line mantra). And the **paired post strategy** — a concise launch post + a deep technical post on the same day, each linking to the other. This lets the launch post stay readable while the engineering audience gets depth.

---

### 4. Anthropic — Claude Sonnet 4.5 — https://www.anthropic.com/news/claude-sonnet-4-5

1. Anthropic / Claude Sonnet 4.5 / ~4,500 words.
2. Cold open with a bold benchmark claim. First sentences: *"Claude Sonnet 4.5 is the best coding model in the world. It's the strongest model for building complex agents."*
3. News in **paragraph 1**, but the formal "we're releasing it" sentence lands in **paragraph 3, ~10%**.
4. Beats: superlative claim (1) → frontier intelligence with benchmark charts (2) → domain expertise (Finance/Law/Medicine/STEM) (3) → 13 customer testimonials (4) → safety/alignment (5) → developer tools (Claude Agent SDK) (6) → research preview "Imagine with Claude" (7) → further info / system card / docs (8). Anthropic does the **everything-bagel** structure — superlative, benchmarks, customers, safety, dev tools, bonus research, all in one post.
5. *"On OSWorld, a benchmark that tests AI models on real-world computer tasks, Sonnet 4.5 now leads at 61.4%, compared to Sonnet 4's 42.2% just four months ago."* And *"maintaining focus for more than 30 hours on complex, multi-step tasks."* Heavy specificity — multiple charts, named benchmarks, named customers in rotating quotes.
6. First-person plural, technical-but-readable. Rep sentence: *"We're releasing it along with a set of major upgrades to our products."* Anthropic's voice is more declarative than aspirational — they tend to underclaim in prose then overclaim in benchmark numbers.
7. CTA: layered — system card, model page, API docs, engineering posts; "drop-in replacement" upgrade hint for existing customers. Multiple paths, no single ask.
8. Headline: noun-phrase product name (*"Introducing Claude Sonnet 4.5"*).
9. High visual density — hero, 4 benchmark comparison charts, 13 customer logos with rotating testimonials, alignment behavior chart.
10. Distinctive: **the safety/alignment block as a load-bearing beat** — competitors either skip this or relegate it to a system card. Also the **rotating customer-quote carousel** packs 13 testimonials into the visual real estate of one. The bonus "research preview" inside the launch post is a clever way to get extra news cycles ("Imagine with Claude" got its own headlines off this post).

---

### 5. OpenAI — GPT-5 — https://openai.com/index/introducing-gpt-5/

1. OpenAI / GPT-5 / ~4,000 words.
2. Cold open with the news. First sentences: *"We are introducing GPT‑5, our best AI system yet. GPT‑5 is a significant leap in intelligence over all our previous models, featuring state-of-the-art performance across coding, math, writing, health, visual perception, and more."*
3. News in **paragraph 1, top ~2-3%**. The opening paragraph triple-stuffs the news + positioning + pricing tier breakdown ("Plus subscribers get more usage, Pro subscribers get GPT-5 pro").
4. Beats: news + tier breakdown (1) → "one unified system" (router architecture) (2) → "smarter, more widely useful model" (3) → coding (4) → creative expression and writing (5) → health (6) → faster, more efficient thinking (7) → robustness/honesty/safety (8) → safer responses + sycophancy + style (9) → custom personalities (10) → bio risk safeguards (11) → GPT-5 pro (12) → how to use it / availability / livestream replay (13) → contributor mega-list. Almost identical shape to Anthropic's: superlative + capability sweep + safety + availability.
5. *"It can often create beautiful and responsive websites, apps, and games with an eye for aesthetic sensibility in just one prompt."* Plus inline interactive demos (rolling ball minigame, pixel art, typing game) with the actual prompts pasted in. *"Compared to previous models, it acts more like an active thought partner, proactively flagging potential concerns and asking questions."* OpenAI relies less on numbers in prose, more on **try-it-yourself interactive demos embedded in the post**.
6. First-person plural, declarative-confident. Rep sentence: *"GPT‑5 is a unified system with a smart, efficient model that answers most questions, a deeper reasoning model (GPT‑5 thinking) for harder problems, and a real‑time router that quickly decides which to use."*
7. CTA: *"Try on ChatGPT"* button at top (above the body) plus tier upgrade prompts. The CTA is at the **top**, not bottom, because the post is long and most readers won't reach the bottom.
8. Headline: noun-phrase product name with subtitle (*"Introducing GPT-5 / Our smartest, fastest, most useful model yet, with built-in thinking that puts expert-level intelligence in everyone's hands."*) — superlative-stacked.
9. Very high — interactive embedded demos (playable minigames!), 5+ benchmark charts, side-by-side writing comparisons, multiple screenshots. Probably the most visually dense post in the corpus.
10. Distinctive: **CTA at top, not bottom** ("Try on ChatGPT" button beneath the dek). **Playable interactive demos** inside the post — no other launch in this corpus does this. **Massive contributor list** at the bottom (hundreds of names) — implicitly says "this took a lot of people," signaling scale.

---

### 6. Cloudflare — AI Week 2025 kickoff — https://blog.cloudflare.com/welcome-to-ai-week-2025/

1. Cloudflare / AI Week 2025 kickoff / ~2,100 words.
2. Scene/state-of-the-world open. First sentences: *"We are witnessing in real time as AI fundamentally changes how people work across every industry. Customer support agents can respond to ten times the tickets."*
3. News lands late — **paragraph 5+, ~35-40% through**. Cloudflare spends the first third on AI-trend setup before mentioning "we will be announcing new and powerful controls…"
4. Beats: state-of-AI hook (1) → the "but" / problem framing [security gaps, content theft] (2) → four-pillar agenda (3) → expanded discussion of each pillar (4) → CTA to follow the hub page (5). This is a **kickoff/preview post**, not a single-product launch — its shape reflects that. The actual product news happens in subsequent posts during the week.
5. *"Customer support agents can respond to ten times the tickets"* and *"it can be hundreds, or even thousands, of times harder to generate site traffic from an AI response versus a search engine result."* Numbers-as-trend-color, not numbers-as-product-proof.
6. First-person plural, conversational-strategic. Rep sentence: *"We're already starting to see stories of vibe coded apps leaking all their users' details."* Cloudflare's voice is loose enough to use phrases like "vibe coded apps."
7. CTA: *"Follow our AI Week hub page for all the latest releases."* The CTA is "stay tuned," not "buy/try."
8. Headline: event/series framing (*"Welcome to AI Week 2025"*). Not a product name.
9. Light — one hero, no inline screenshots / code / diagrams in the kickoff (those land in the daily posts).
10. Distinctive: the **launch-week kickoff genre** itself. Cloudflare and Supabase both run multi-day launch weeks where the kickoff is essentially a manifesto-shaped table of contents and the actual product launches are individual daily posts. The kickoff trades immediacy of news for narrative scaffolding.

---

### 7. Plaid — Plaid Layer — https://plaid.com/blog/introducing-plaid-layer/

1. Plaid / Plaid Layer / ~1,150 words.
2. Sweeping context open (history-of-the-internet framing). First sentences: *"When Plaid was founded, financial services were still designed for a world that had never envisioned the Internet. Almost anything is possible online today—from streaming the latest blockbusters to one-click grocery delivery."*
3. News lands in **paragraph 2, ~5-8%**: *"Today, we're excited to introduce Layer, a new platform for secure, instant experiences."*
4. Beats: history/context hook (1) → news (2) → speed/conversion benefits (3) → security mechanisms (4) → UX flexibility (5) → identity/KYC (6) → rollout + future roadmap (7) → CTA (8). Almost a textbook B2B fintech launch: hook → news → "what it does" rotated through several frames (speed, security, UX, identity).
5. *"Layer reduces the time it takes for someone to sign up for an app by nearly 90%"*. Customer mentions: *"Possible Finance and Empower are already seeing better user experiences and conversion improvements."*
6. First-person plural, professional-casual. Rep sentence: *"Layer combines our expertise building anti-fraud and KYC solutions with industry-leading security practices."*
7. CTA: *"Get access to Layer"* — gated — they want a sales conversation, not self-serve.
8. Headline: product-name + benefit-y subtitle (*"Introducing Plaid Layer: The future of secure instant financial experiences"*).
9. Light — one hero image, an author headshot, social share buttons. No inline screenshots of the product, no code.
10. Distinctive: the **history-of-the-internet hook** — quintessential fintech move, anchoring a feature launch in a civilizational story. Also the **gated CTA** — Plaid's product is enterprise-sold, so the launch post funnels to sales not signup.

---

### 8. Resend — new.email — https://resend.com/blog/introducing-new-email

1. Resend / new.email / ~650 words.
2. Cold open with the news. First sentences: *"Today, we're excited to announce new.email. It's a new way to build beautiful, responsive, and cross-platform emails using natural language."*
3. News in **paragraph 1, top ~5-8%**.
4. Beats: news (1) → why-now problem framing (2) → why-now market timing [LLM capabilities + 54-component library] (3) → CTA + waitlist (4). Resend posts use Q-as-section-headers (*"Why are we doing this? / What problem are we solving? / Why now?"*) which forces tight, structured prose.
5. *"Today, we have a library of 54 high-quality email components."* That's the only number. Resend leans on minimalism — short post, one fact, clear ask.
6. First-person plural, conversational-aspirational. Rep sentence: *"Email needs a revamp. A renovation. Modernized for the way we build apps today."*
7. CTA: *"Join the waitlist… Follow @newdotemail on X."* Waitlist + social, no gated sales.
8. Headline: short product-name (*"Introducing new.email"*).
9. Minimal — one inline diagram, no other images.
10. Distinctive: the **Q-as-headers structure** (*Why are we doing this? / What problem are we solving? / Why now?*) is rare in the corpus and forces the writer to actually answer each question. Also: **650 words is short** for a launch post, and that brevity is the point.

---

### 9. Supabase — Launch Week 15 Top 10 — https://supabase.com/blog/launch-week-15-top-10

1. Supabase / LW15 wrap-up / ~850 words.
2. Cold open with a list framing. First sentences: *"Here are the top 10 launches from the past week. They're all very exciting so make sure to check out every single one."* Then jumps straight to #1.
3. News begins immediately — **top 2%**.
4. Beats: ten numbered features (each its own mini-launch with description + Read more link) → meetups subsection → hackathon subsection. There's no problem framing, no testimonial, no roadmap. It's a **wrap-up index post**, optimized for click-through to the underlying daily posts.
5. *"You can now upload files as large as 500 GB (up from 50 GB), enjoy much cheaper cached egress pricing at $0.03/GB (down from $0.09/GB)."* Specific before/after numbers in the index format.
6. First-person plural, casual-technical. Rep sentence: *"We've partnered with Figma so you can hook up a Supabase backend to your Figma Make project."*
7. CTA: hackathon signup + meetup discovery. (Each numbered item has its own "Read more" CTA.)
8. Headline: structural (*"Top 10 Launches of Launch Week 15"*) — list-bait.
9. Light/text-only in the index; the underlying daily posts carry the visuals.
10. Distinctive: the **wrap-up-as-launch-post** pattern. Launch Week is a five-day campaign, but the wrap-up gets the most cumulative SEO + social pickup. Treating the wrap as a first-class launch post is a structural choice worth stealing.

---

### 10. Modal — Series B — https://modal.com/blog/announcing-our-series-b

1. Modal / $87M Series B / ~1,100 words.
2. Cold open with the funding news. First sentences: *"We're excited to announce that we have raised more than $80M in a Series B round, led by Lux Capital, with existing investors participating as well."*
3. News in **paragraph 1, top 2%**.
4. Beats: news (1) → "AI-native companies need AI-native infrastructure" (philosophical framing) (2) → customer testimonials (3) → product suite overview (with diagram) (4) → what's next + hiring (5) → CTA (6). Funding announcements have a slightly different shape than product launches — the news is the funding, but the body has to **re-justify the product** for new readers and reinforce the thesis for existing ones.
6. *"Our post-money valuation is $1.1B. This brings our total money raised to $111M."* And: *"Meta's Code World Models used Modal for thousands of concurrent sandboxed environments."* Funding numbers + a flagship customer/usage anecdote.
7. First-person plural, friendly-professional with light tech depth. Rep sentence: *"By pooling the world's compute and managing the capacity at scale, we can drive efficiency and speed."*
8. CTA: *"Ship your first app in minutes"* + recruiting (*"check out our open roles"*) — dual CTA, like Stripe.
9. Moderate — author photos, one product diagram, otherwise text-heavy.
10. Distinctive: **funding announcements as a sub-genre** — Modal uses the funding moment to re-pitch the entire product and recruit, not just thank investors. The electricity analogy ("AI-native infrastructure" framing) is one of the more memorable narrative moves in the corpus.

---

### 11. Replit — Agent 4 — https://blog.replit.com/introducing-agent-4-built-for-creativity

1. Replit / Agent 4 / ~2,100 words.
2. Cold open with the news + thesis. First sentences: *"Introducing Agent 4 — our fastest, most versatile Agent yet. It's built around a simple idea: you should spend your time creating, not coordinating."*
3. News in **paragraph 1, top ~2-5%**.
4. Beats: news + four-pillar overview (1) → "design and build in same place" (2) → "do more at once" (parallel work) (3) → "focus on vision/Agent handles execution" (4) → "create everything in one project" (5) → philosophical close (6). Four-pillar overview-then-deep-dive is a recurring shape across model/agent launches (cf. Sonnet 4.5, GPT-5).
5. Customer quote: *"Agent 4 unlocks true collaboration and real-time learning — now our teams can design and build with our closest partners live."* — Doug Rodermund, Zillow. Replit relies more on customer voice than benchmark numbers.
6. First-person plural, conversational-builder-y. Rep sentence: *"Because Replit powers your full environment—projects, files, and execution—it can coordinate this work safely."*
7. CTA: social-share + links to companion launches (App Monitoring, Auto-Protect, Security Agent). Soft CTA.
8. Headline: product-name + benefit (*"Introducing Replit Agent 4: Built for Creativity"*).
9. Moderate — hero image, ~5 product images.
10. Distinctive: **shipping a cluster of related launches the same day** with each one cross-linking the others (the "companion launch" pattern). It compounds news coverage and forces the headline product to do less framing work.

---

### 12. Notion — Notion 3.0: Agents — https://www.notion.com/releases/2025-09-18

1. Notion / Notion 3.0 Agents / ~1,200 words.
2. Cold open with the news. First sentences: *"Notion 3.0 is here! We've rebuilt Notion AI from the ground up as Agents."*
3. News headline + opening at **top ~5%**; substance ("Your personal Agent can take on a whole project…") at **paragraph 2, ~15%**.
4. Beats: news (1) → agent capabilities across pages (2) → personalization/memory (3) → custom agents preview (4) → row-level permissions (5) → AI connectors (6) → MCP ecosystem (7) → AI model choice (8) → formula generation (9) → recent releases footer (10). Like Linear, Notion staples a "recent releases" footer onto product launches.
5. *"Ben Levick (Ramp Head of AI & Ops): 'We can now instantly spin up ready-to-use systems that used to take hours of busywork.'"* Two named customer quotes (Ramp, Faire). No benchmark numbers.
6. First-person inclusive. Rep sentence: *"Unlike your personal Agent, Custom Agents can run autonomously on a schedule or triggers you set, so work keeps moving even while you're asleep."*
7. CTA: *"Give them a try inside any database or automation!"* — soft, in-product.
8. Headline: version-numbered product news (*"Notion 3.0: Agents"*) — version number signals "this is a real overhaul," subtitle is the feature.
9. High — 7-8 inline images/GIFs throughout.
10. Distinctive: **version-numbered branding** ("Notion 3.0") even though Notion is a SaaS product without traditional version cycles. It's a rhetorical move — the version number signals scale of change. Also: heavy GIF density carries the "show, don't tell" load.

---

### 13. Figma — Figma Make — https://www.figma.com/blog/introducing-figma-make/

1. Figma / Figma Make / ~1,800 words.
2. Aphoristic philosophical open. First sentences: *"Design is the art of problem-solving. But problem-solving isn't linear—where it starts, where it stops, and how it will evolve depends on where you are in the process, and where you think you might want to go."*
3. News lands in **paragraph 2-3, ~8-10%**: *"Today we are launching Figma Make, a new prompt-to-app tool…"*
4. Beats: philosophical hook (1) → news (2) → tech stack disclosure ("uses Claude 3.7 Sonnet") (3) → "start with design, not from scratch" (4) → "static to interactive in minutes" (5) → "multiplayer exploration in real-time" (6) → "point-and-prompt precision" (7) → "seamless canvas-to-code" (8) → "expanding design's possibilities" (9) → author bios (10). Designer-flavored hooks; benefit-stacked subheads.
5. *"Figma Make currently uses Claude 3.7 Sonnet; we will begin introducing other models in the future."* That's it for hard specifics. Three annotated screenshots (music player, settings panel animation, timestamp animation) carry the demo proof.
6. First-person plural, designer-aspirational. Rep sentence: *"Rather than replacing the deeply crafted, iterative work that is so critical to the design process—Figma Make reinforces it."*
7. CTA: *"We can't wait to see what you build."* Soft, no link. Plus author bios + related-articles ("explore Figma Sites and Figma Buzz").
8. Headline: product-name + benefit triplet (*"Introducing Figma Make: A New Way to Test, Edit, and Prompt Designs"*).
9. Moderate-high — 3 annotated product screenshots, 3 author headshots.
10. Distinctive: **disclosing the underlying model** ("uses Claude 3.7 Sonnet") inside the launch post — a transparency move you don't see from most prompt-to-X tools. **Three named author bios** at the bottom signal "this is a craft post by humans," matching Figma's designer-audience positioning.

---

### 14. GitHub — Copilot coding agent — https://github.blog/news-insights/product-news/github-copilot-meet-the-new-coding-agent/

1. GitHub / Copilot coding agent / ~1,500 words.
2. Cold open with the news. First sentences: *"We are excited to introduce a new coding agent for GitHub Copilot. Embedded directly into GitHub, the agent starts its work when you assign a GitHub issue to Copilot or prompt it in VS Code."*
3. News in **paragraph 1, top ~5%**.
4. Beats: news (1) → activation/UX (assign an issue) (2) → capabilities + task types (3) → technical implementation (RAG, MCP) (4) → human-review iteration loop (5) → security architecture (6) → availability + pricing (7) → getting started (8). Heavily ops-flavored — security and pricing get top-half real estate, not afterthought-paragraph treatment.
5. *"40 million daily GitHub Actions jobs executed"*; *"25,000+ actions in GitHub Marketplace."* Customer quote: *"The GitHub Copilot coding agent fits into our existing workflow and converts specifications to production code in minutes." —Alex Devkar, Carvana.* Plus pricing date (*"Premium request cost begins June 4, 2025"*) — most launch posts dodge dates that specific.
6. First-person plural, formal-technical. Rep sentence: *"Having Copilot on your team doesn't mean weakening your security posture—existing policies like branch protections still apply in exactly the way you'd expect."*
7. CTA: *"Visit the Docs to get started."*
8. Headline: short marketing-y phrase (*"GitHub Copilot: Meet the new coding agent"*) — verb-led, conversational.
9. Moderate — hero, 2 inline screenshots (agent logs, iteration workflow).
10. Distinctive: **security and pricing as load-bearing structural beats**, not afterthoughts. GitHub knows their audience reads launch posts to evaluate "can I bring this to my CISO." Putting branch-protection commentary mid-post is a deliberate enterprise-readiness signal.

---

### 15. Mercury — Mercury Personal — https://mercury.com/blog/mercury-personal-launch

1. Mercury / Mercury Personal / ~1,100 words.
2. Cold open with the news, slightly playful. First sentences: *"Mercury is getting personal. Starting today, the power of the Mercury experience is no longer reserved for high-growth startups alone."*
3. News in **paragraph 1, top ~5%**; the explicit "tap into the same beloved banking and financial software for their personal accounts" lands in **paragraph 2, ~10%**.
4. Beats: news (1) → 3.25% APY savings (2) → automation/UI/$5M FDIC (3) → shared access (4) → $240/year subscription model (5) → forward roadmap (joint accounts, treasury, intl wires) (6) → waitlist CTA (7).
5. *"Mercury Personal offers a competitive annual percentage yield of 3.25% on your savings without any minimum balances."* Plus *"up to $5M FDIC protection"* and the $240/year price. Mercury foregrounds **price + APY in the body** — a fintech-specific move (most B2B SaaS launches dodge price).
6. First-person plural, warm-professional. Rep sentence: *"Those familiar with Mercury's UI and near-mind-reading automations will be glad to know Mercury Personal offers the same frictionless experience."*
7. CTA: *"Join the waitlist at mercury.com/personal-banking."*
8. Headline: thesis sentence (*"The magic of Mercury, now for personal banking"*) — possessive, brand-asserting.
9. Light — one hero/dashboard screenshot, related articles in footer.
10. Distinctive: **transparent pricing in the body** ($3.25% APY, $5M FDIC, $240/year) is unusual for a launch post. **"Now for X"-shaped headline** signals continuity with the existing product brand instead of treating Personal as a totally new thing.

---

## Synthesis

### Patterns that recur (10+/15)

1. **First-person plural ("we") voice — 15/15.** Universal. No company writes a launch post in third person.
2. **Product-name headline with the verb "Introducing" — 11/15** (Linear, Vercel, Anthropic, OpenAI, Plaid, Resend, Notion, Figma, Replit, Modal, Mercury via "Mercury is getting personal"). The remaining four use event/series framings (Stripe Sessions, AI Week, Launch Week 15, GitHub Copilot agent verb-led).
3. **Cold-open with the news — 11/15.** The default is "Today, we're announcing X" or a one-line capability claim. Only Vercel (problem-first), Cloudflare (state-of-AI hook), Plaid (history-of-internet), and Figma (philosophical aphorism) defer the news past paragraph 2.
4. **News lands in the top 15% of the post — 13/15.** Even the deferred-news posts (Vercel, Plaid, Figma) land the news by paragraph 2-3. Only Cloudflare's launch-week kickoff (~35-40%) is a true outlier, and that's a kickoff genre, not a single-product launch.
5. **At least one specific number — 13/15.** Benchmarks, percentages, customer counts, dollar amounts. Only Linear and Resend rely entirely on demonstrative use cases without quantitative proof.
6. **Concluding CTA to "try it" / "join waitlist" / "read docs" — 14/15.** Linear is the only one without a hard CTA (changelog footer takes its place).
7. **At least one inline visual (hero or screenshot) — 14/15.** Only Vercel's Fluid post is essentially text-only in the launch piece (visuals live in the companion technical post).
8. **A "what it does, concretely" beat with at least 3 capability subsections — 14/15.** Some shape of "here are the 3-7 things this enables" is universal.
9. **No marketing buzzwords like "revolutionary" / "game-changing" — 14/15.** The genre underclaims in adjectives. The strongest claims are usually benchmark-anchored ("best in the world" only when a benchmark backs it). Plaid's "future of secure instant financial experiences" subtitle is the closest the corpus gets to genre-violating.
10. **Customer-name dropping somewhere in the post — 11/15.** Stripe (OpenAI/Anthropic/PepsiCo/Hertz/Shopify/DoorDash), Anthropic (13 testimonials), GitHub (Carvana), Modal (Meta CWM), Notion (Ramp/Faire), Replit (Zillow), Plaid (Possible/Empower). Linear, Vercel, Resend, Figma, OpenAI, Cloudflare-kickoff, Mercury, Supabase-wrap mostly skip them — usually because the audience already knows the company is mainstream, or because the launch is brand-new and has no customers yet.

### High-variance choices

These are the deliberate forks where companies optimize differently:

- **News position: top-1% (Stripe, OpenAI, Replit, Modal) vs. top-10% after a setup paragraph (Anthropic, Mercury, Notion, GitHub, Plaid, Figma) vs. top-30%+ (Cloudflare kickoff, Vercel arguably).** Cold-open optimizes for "skim readers + headline-driven aggregators." Setup-first optimizes for "the post is the brand essay." Pick based on whether you expect readers to share the headline or read the body.
- **Post length: ~650 words (Resend) vs. ~8,500 words (Stripe Sessions roundup).** Short posts with one news beat work for waitlist launches and feature ships. Long posts work for once-a-year umbrella events. Mid-range (1,000-2,000 words) is the sweet spot for a single-product launch.
- **CTA target: self-serve "try it" (OpenAI, Modal, Replit, GitHub) vs. waitlist (Resend, Mercury, Plaid Layer) vs. sales/contact (Plaid implicit) vs. recruiting (Stripe, Modal) vs. none / changelog footer (Linear).** Recruiting CTAs are a subtle confidence move ("we're growing"). Linear's no-CTA is a strong choice that signals "this is how we ship — read the next changelog entry next week."
- **Pricing in the body — yes (Mercury 3.25% APY + $240/yr, GitHub premium request + date, Anthropic $3/$15) vs. no (most others).** Show price when (a) it's competitive on its face or (b) your audience won't engage without it. Hide price when sales process needs to happen.
- **Customer testimonials as discrete beat (Anthropic 13-quote carousel, Notion's two named quotes, GitHub's Carvana, Modal's customer block) vs. inlined name-drops (Stripe inlines OpenAI/Anthropic/PepsiCo as casual proof points) vs. omitted entirely (Linear, Resend, Figma).** Carousels feel like sales decks. Inlined name-drops feel more confident. Omission works only when the demo carries it.
- **Problem framing — full setup paragraph (Vercel servers-vs-serverless dichotomy, Plaid's history-of-internet, Cloudflare's AI-trend hook) vs. one-sentence ("execution bottlenecks," Linear) vs. none (Stripe, OpenAI, Replit, Modal).** Problem framing works when the news will land flat without context. It hurts when the audience already gets the problem.
- **Visual density — sparse text-only (Vercel, Plaid, Cloudflare kickoff, Mercury) vs. moderate inline (Linear, Modal, GitHub, Replit, Figma) vs. heavy / interactive (OpenAI's playable demos, Anthropic's chart suite, Notion's GIF-per-feature).** Heavier visuals cost more but compress demo proof.

### Distinctive moves worth stealing

These are tactics that 1-2 companies use and most don't, but transfer well:

1. **Paired post strategy (Vercel).** Concise launch post for the broad audience + deep technical "how we built it" post for engineers, published the same day, cross-linking each other. Doubles your news cycles without bloating either post. Anthropic does a softer version with system cards.
2. **CEO vision letter / tactical post split (Linear).** The launch post stays product-tactical; the why-we-built-this manifesto lives as a separate "letter from the CEO" linked in line one. Lets the launch post be ruthlessly skimmable while still publishing the rhetoric.
3. **Quarter-by-quarter forward roadmap (Stripe Sessions).** Sessions ends with a "what's coming Q1, Q2, Q3" block — extraordinarily rare, and a credibility flex. Most companies hide roadmaps. Telegraphing them turns the launch post into a strategic anchor.
4. **CTA above the body, not just at the end (OpenAI).** "Try GPT-5 on ChatGPT" button beneath the dek. Long posts lose readers; putting the CTA up top harvests the skim audience.
5. **Q-as-headers structure (Resend).** "Why are we doing this? / What problem are we solving? / Why now?" forces the writer to actually answer each question instead of vamping. Great pattern for ~600-1000 word posts.
6. **Playable interactive demos in-post (OpenAI).** Embedded minigames generated by GPT-5. No other launch in the corpus matches this. Even one interactive widget materially changes the post's stickiness.
7. **Recruiting as the closing CTA (Stripe, Modal).** Confidence-signaling move. "Like this post? Join our team." Suggests the company is both shipping AND growing — implicit anti-rumor that you're stagnating.
8. **Companion launches the same day (Replit Agent 4 + App Monitoring + Auto-Protect + Security Agent).** Cluster-launch days compound news coverage and let the headline product do less work.
9. **Disclose the underlying tech stack (Figma — "uses Claude 3.7 Sonnet").** Transparency about the model/dependency builds trust with technical audiences, especially for AI-built products. Most launches dodge this.
10. **Wrap-up post as a first-class launch post (Supabase LW15 Top 10).** The day-by-day launch posts get more depth, but the wrap is the SEO and social winner. Treat the wrap as the canonical entry.
11. **Inlined customer name-drops as casual proof (Stripe).** "Leading AI companies like OpenAI, Anthropic, ElevenLabs, and Cursor" mid-paragraph hits harder than a quote box — feels confident, not solicited.
12. **Version-numbered branding ("Notion 3.0").** Even SaaS without traditional versions can use "3.0" / "Agent 4" / "Sonnet 4.5" branding to telegraph "this is a real overhaul." Cheap rhetorical move that compounds over time.

### Anti-patterns

Moves that recur but seem to hurt:

- **Vague mission-y subtitles** like Vercel's "the power of servers, in serverless form" or Plaid's "the future of secure instant financial experiences" — these read as marketing-fluff and the post does fine without them. The strongest headlines in the corpus (Stripe, GitHub, Linear, Modal, OpenAI) keep subtitles concrete or omit them.
- **Long civilizational hooks** (Plaid's "When Plaid was founded, financial services were still designed for a world that had never envisioned the Internet…") that delay the news to paragraph 2-3. They work in some contexts (Mercury's "Mercury is getting personal" lands quickly), but Plaid's hook is genre-cliché. Compress to one sentence or skip.
- **Carousels of 13+ rotating customer testimonials** (Anthropic). The raw count signals desperation more than credibility — most readers can't even read all 13. 2-3 well-chosen quotes hit harder.
- **No CTA / drift-into-changelog endings** (Linear). Defensible as a brand choice but leaves traffic on the floor for one-time readers who landed via social.
- **Solo metric callouts without comparator** ("up to 85% lower compute costs," Vercel). Without a baseline or a benchmark, the number reads as marketing. Anthropic does this well by always citing the prior model's score (61.4% vs 42.2%).
- **Aphoristic philosophical openings on technical-audience posts** (Figma's "Design is the art of problem-solving. But problem-solving isn't linear…"). Works for designer audience; would tank for an infra audience.
- **"Excited to announce" / "thrilled to share" as the opening verb** (Linear, Modal, Resend, Plaid, Notion). Genre filler. Stripe and OpenAI both demonstrate that the news can land harder without it ("This morning at our annual conference… 288 new products"; "We are introducing GPT-5, our best AI system yet").
- **Padded "what's next" sections** that promise vague future work without dates. Stripe's Sessions roadmap escapes this by being quarter-specific. Most companies should either drop the section or commit to dates.

### Recommended structural template

For a single-product B2B SaaS launch (1,000-2,000 words), this is the shape that combines what works:

```
HEADLINE: "Introducing [Product Name]" or "[Verb-led]: [product]"
         Subtitle (optional): one concrete benefit, no buzzwords

DEK / SOCIAL CARD: one sentence, the strongest specific claim

[paragraph 1] — News + the strongest specific proof in the same breath
   Pattern: "Today we're launching [X]. [One concrete capability claim with a number or named comparator.]"
   ↑ CTA button HERE for long posts

[paragraph 2] — Who it's for + the problem in one sentence
   Avoid civilizational framing; keep it ≤ 2 sentences

[section: What it does]
   3-5 capability subsections, each with a screenshot or short demo
   Each subsection: capability name → one-sentence explanation → concrete example/screenshot

[section: How it works (optional, for technical audience)]
   Architectural specifics, not marketing claims
   Diagram or code block

[section: Who's using it / proof]
   2-3 named customers with one-sentence inline mention
   OR 1 strong named quote (not a 13-quote carousel)
   OR a benchmark chart with a comparator

[section: Availability / pricing / how to get it]
   Be specific on dates, plans, geos, limits
   Hide price only if you must (and explain why — e.g., "contact sales")

[paragraph: What's next] — Optional, only if you can name dates or quarters

[CTA]
   ONE primary action: "Try it" or "Read the docs" or "Join the waitlist"
   Optional secondary: recruiting ("Join our team") if the moment supports it
```

Companion strategy: ship a parallel "how we built it" / "behind the scenes" technical post the same day, cross-linked. Lets the launch post stay tight without losing the engineering audience.

Length target: **1,200-1,800 words** for a single product. Below 800 leaves credibility on the floor; above 2,500 starts losing readers unless you're Stripe Sessions.

### Voice/register recommendations

The Anthropic / Linear / Stripe register the brief is targeting:

1. **First-person plural, declarative, present-tense.** "We're launching X. It does Y." Not "We are excited to announce that X will soon be available to..."
2. **Underclaim in adjectives, overclaim in numbers.** "Best coding model in the world" works because Anthropic immediately backs it with a benchmark. "Revolutionary platform that transforms..." works for nobody.
3. **Specificity > sweep.** Prefer "16,000 platforms including Shopify, DoorDash, and Substack" to "thousands of leading brands." Prefer "61.4%, up from 42.2% four months ago" to "significantly improved."
4. **Active verbs, short clauses.** Stripe and OpenAI both lean on subject-verb-object with named entities. Avoid passive voice ("X is being launched today by us") and nominalizations ("the launch represents a significant advancement").
5. **One number per sentence, max two per paragraph.** Beyond that, numbers stop reading as proof and start reading as a spec sheet. Anthropic's benchmark sections work because they break out the numbers into charts, not prose.
6. **Cut "excited to announce" / "thrilled to share" / "today marks a new chapter."** Genre filler. Replace with the news.
7. **Avoid mission-y subheads.** "Built for the future of financial experiences" → "Pay bills directly from your bank account." Concrete > aspirational.
8. **Customer voice in their words, not yours.** If you must include a quote, use the customer's actual phrasing — operational specifics ("converts specifications to production code in minutes") beat marketing bromides ("a game-changer for our team").
9. **Show the work.** Disclose the underlying model/architecture/dependencies (Figma's "uses Claude 3.7 Sonnet"). Disclose dates (GitHub's "Premium request cost begins June 4, 2025"). Disclose what's missing or coming next. The genre rewards transparency.
10. **Match register to audience density.** Designers tolerate aphorism (Figma); infra engineers don't (Vercel keeps it tight). When in doubt, write for the most senior technical reader on the buying committee — they're the toughest skim audience.

If Matt's brand (Zerg, ZergStack, Zergwallet, Zergboard, ZergSend) is targeting the Stripe/Anthropic/Linear register, the highest-leverage moves to copy first: cold-open with the news + one specific number; companion technical post; Q-as-headers for shorter posts; named-customer inline drops; quarter-specific forward roadmap; recruiting CTA when the moment supports it. The highest-leverage moves to avoid: civilizational hooks, "excited to announce," 13-quote carousels, vague subtitle benefits, aspirational mission-y subheads, no-comparator percentages.
