---
name: flight-search
description: Search cash airfares (one-way, round-trip, multi-city / open-jaw) and hunt SkyMiles / award deals. Use when shopping or PRICING flights — "cheapest flight", "find flights", "fare to X", "multi-city", "open-jaw", "Delta/SkyTeam options", "book with miles", "SkyMiles deal", "award space", "business class on points", "flight deal". Filters by alliance (SkyTeam) / airline / cabin / flexible dates via the free Amadeus API; emits delta.com SkyMiles flexible-calendar + flash-sale playbooks (SkyMiles has no public API — pull via playwright-skill). Sibling to flight-skill, which only TRACKS already-booked flights (day-of status / connections) — this one SHOPS. Pairs with gcal-skill to block the trip and flight-skill to track it once booked.
allowed-tools: Bash, Read
---

# Flight Search

Shop and price flights. Cash fares come from the Amadeus Self-Service API; SkyMiles/award
pricing is delivered as a delta.com playbook (no public award API exists — drive the
logged-in flexible calendar with `playwright-skill`).

> Companion to `flight-skill` (tracking only). Use **this** to find/price/compare; use
> **flight-skill** for day-of status and connection risk once flights are booked.

## One-time setup (cash search only)

Free Amadeus Self-Service key — https://developers.amadeus.com → create app:

```bash
export AMADEUS_CLIENT_ID=...
export AMADEUS_CLIENT_SECRET=...
export AMADEUS_ENV=production   # optional; default 'test' (free, limited inventory)
```

The `deals` and `award` subcommands need **no key**.

## Commands

```bash
SK=~/.claude/skills/flight-search/scripts/flight_search.py

# One-way / round-trip cash fares, SkyTeam + business
python3 $SK search DTW LHR 2026-07-12 --alliance SKYTEAM --cabin business
python3 $SK search DTW AMS 2026-07-12 2026-07-28 --airlines DL,KL,AF,VS --cabin economy

# Cheapest-date calendar (±N days on the outbound)
python3 $SK search DTW LHR 2026-07-12 --alliance SKYTEAM --flexible 3

# Multi-city / open-jaw — ORIG DEST YYYY-MM-DD triples, repeated
python3 $SK multi DTW LHR 2026-07-12 AMS DTW 2026-07-28 --alliance SKYTEAM --cabin economy --json

# SkyMiles + cash deal-hunting playbook (pre-filled deep links)
python3 $SK deals
python3 $SK deals --route DTW LHR 2026-07-12 --route AMS DTW 2026-07-28

# delta.com SkyMiles flexible-calendar playbook (then run the pull via playwright-skill)
python3 $SK award AMS DTW --date 2026-07-28 --flexible 2
```

Flags (search/multi): `--alliance SKYTEAM`, `--airlines DL,KL,AF,VS`, `--cabin
economy|premium|business|first`, `--adults N`, `--max-stops N`, `--nonstop`, `--limit N`,
`--json`.

## SkyMiles vs. transferable points (read before advising on awards)

Delta **SkyMiles** are airline miles — **not** transferable to Flying Blue or Virgin
Atlantic, so the cheap Flying Blue Promo Rewards (~36–45k one-way business) and the
Virgin→Delta One (50k) sweet spots are **off-limits**. With SkyMiles the levers are:
**Delta-operated Delta One out of a Delta hub** (e.g. DTW), the **delta.com flexible-date
calendar**, and **SkyMiles flash sales**. See `references/skyteam-and-skymiles.md`.

## How it composes

1. `search` / `multi` → cash baseline + cheapest dates (Amadeus).
2. `deals` / `award` → SkyMiles flash sales + delta.com flexible calendar (login via `playwright-skill`).
3. Compare miles-vs-cash, pick the legs.
4. `gcal-skill` → block flights + city stays on the calendar.
5. `flight-skill trip <flight numbers>` → day-of tracking + connection analysis once booked.
