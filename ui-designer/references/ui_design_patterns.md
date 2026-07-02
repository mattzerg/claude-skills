# UI Design Patterns

These patterns are tuned for product and internal-tool interfaces, not marketing pages.

## Pattern 1: Start from the user job

Every screen needs a dominant purpose:

- decide
- act
- review
- configure
- monitor

If a screen is trying to do several at once, split the surface or create stronger hierarchy.

## Pattern 2: Primary action wins

For each screen, identify:

- primary action
- primary status signal
- primary object being manipulated

That should determine the top region and visual weight.

## Pattern 3: State design is not optional

Every interface spec should explicitly cover:

- empty state
- loading state
- success confirmation
- validation failure
- permission-restricted view

This is especially important for onboarding, settings, and admin UI.

## Pattern 4: Dense UIs need stable structure

Tables, dashboards, and boards should prioritize:

- stable alignment
- consistent status labels
- visible filters / sorting
- obvious next actions

Avoid hiding the main workflow behind hover-only or deep nested controls.

## Pattern 5: Progressive disclosure beats default clutter

Useful escalation ladder:

- show essential fields inline
- tuck advanced configuration behind expansion
- use modals for contained, high-focus edits
- use dedicated pages for multi-step or high-risk configuration

## Pattern 6: Handoff should mention data and instrumentation

A UI spec is incomplete without:

- data needed on load
- mutations / save events
- analytics or event hooks
- unresolved engineering constraints
