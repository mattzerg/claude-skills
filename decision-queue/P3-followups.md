# P3 throughput maximizers — followup tracker

These four items were scoped in the P0-P3 plan as "nice to have" — each is a single small project. They depend on P0/P1/P2 being in place, which they now are. Capture here so they don't get lost; each becomes its own decision-queue item when ready.

## P3.1 — iOS Shortcut wrapper around the swipe app

**Status:** Specced, not built.

**What:** Native iOS Shortcut that opens `https://<tailscale-ip>:8788/swipe` (or `http://localhost:8788/swipe` if at desk) as a home-screen app icon. Add a "Decision Queue" shortcut to Matt's home screen.

**Effort:** ~30 min. Shortcut → "Open URL" action → Add to Home Screen.

**Prereq:** Tailscale running on Matt's Mac + iPhone, or a Cloudflare Tunnel pointed at localhost:8788.

**Why not now:** Needs Matt's Tailscale/CF state confirmed + Shortcuts app interaction (not automatable from Claude).

## P3.2 — Voice replies via eleven-labs + Twilio

**Status:** Specced, not built.

**What:** SMS reply path that supports voice — "Tell me about decision 3" → audio briefing via `eleven-labs-skill` reads the briefing aloud; "Yes ship 3" voice transcription → recorded.

**Effort:** ~4-6h. Webhook handler on serve.py that accepts inbound Twilio SMS; if message starts with "tell me about", generates ElevenLabs audio + replies with link. Voice messages need Whisper transcription pass.

**Why not now:** P3.1 (iOS Shortcut) is probably enough for phone-side throughput; voice is a nice add but not critical until Matt validates the swipe + SMS flow.

## P3.3 — Idea-backlog idle ideas → morning-brief promotion

**Status:** Specced, not built.

**What:** Daily cron scans `MattZerg/Ideas/**/*.md`, finds ideas with `status=raw` AND `last_touched > 7d`, picks top 3 by conviction, and inserts them into morning-brief as decision-queue items: "promote idea X / archive / keep idle".

**Effort:** ~2h. New module `~/.claude/skills/decision-queue/sources/idea_promotion.py` that emits rows to `pre_pr_packs.jsonl` shape but with kind=`idea_promotion`.

**Why not now:** Need at least a week of decision-log + outcome data first to calibrate "what idea-promotion volume Matt actually wants per day."

## P3.4 — Skill audit: which skills haven't fired in 90d?

**Status:** Data is available; report not built.

**What:** Use `~/.claude/state/skill_invocation_log.jsonl` (written by `skill_invocation_log.py` PreToolUse hook) to find skills with zero invocations in 90 days. Propose deprecation / consolidation. Surface as decision-queue items.

**Effort:** ~1.5h. Read jsonl, list `~/.claude/skills/`, diff, render report.

**Why not now:** Low marginal value vs P0-P2 work, but easy to run quickly when there's idle capacity.

---

## Trigger

Re-evaluate priority on **first weekly mining-to-composite report** (Mondays 7:30am). If decisions_log shows ≥30 cleared decisions/week, P3.1 (iOS Shortcut) becomes highest leverage. If decision throughput stalls at <10/week, P3.3 (idea promotion) may not be needed.
