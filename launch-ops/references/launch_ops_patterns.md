# Launch Ops Patterns

These patterns are tuned for software and content launches with real dependency chains.

## Pattern 1: A launch has multiple sources of truth

Common launch state lives in different places:

- date / schedule
- publish state
- product or infra readiness
- CTA destinations
- attribution / tracking
- distribution drafts

A launch is fragile when those are implicit.

## Pattern 2: Four state bands are usually enough

- `blocked`
- `ready`
- `to-fire`
- `done`

This is better than one giant checklist where everything looks equally pending.

## Pattern 3: Readiness is cross-functional

Useful workstreams:

- platform / deploy
- content / assets
- tracking / attribution
- distribution / comms

If one of these is not represented, the plan is probably incomplete.

## Pattern 4: Launch-day plans need fallback rules

Define what happens if:

- the domain is not live
- event tracking is broken
- the launch date slips
- a core asset changes late
- a repost / partner dependency is unresolved

## Pattern 5: Content complete is not launch ready

The copy can be done while the launch is still blocked on:

- DNS
- product CTA destination
- event logging
- allowlists
- secrets
- newsletter or reply-to configuration

## Pattern 6: Post-launch capture should be designed before launch day

At minimum define:

- what metrics matter same-day
- where they will be read
- who checks them
- what counts as a healthy first read
