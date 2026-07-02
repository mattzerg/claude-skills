# ZergGuard Family Mode — design notes (not built yet)

Pre-implementation scoping for Phase 4 productization. One tech-savvy person (you) monitors security posture for multiple family members on their own Macs.

## Why this is the killer feature for the non-technical-user market

Most cybersec tools assume the user is the operator. Family Mode flips that: a tech-fluent adult deploys ZergGuard once for their parents / partner / kids, gets alerted when something concerning happens on THEIR machines, and remediates from afar.

## Architecture (proposed)

- **Per-device agent**: same ZergGuard install but config has `family.role = "agent"` and `family.report_to = <central endpoint>`.
- **Central hub**: a tiny server (Cloudflare Worker or a single VM) that receives HIGH-severity findings from agents + serves a multi-device dashboard.
- **Tech-fluent operator** has a "family view" — one screen showing posture for all family members, drill-down per device.
- **Encryption**: all payloads end-to-end encrypted with the operator's key; central hub stores ciphertext only.

## Privacy model

- Agents NEVER report iMessage content, just metadata (sender count, scam-check verdicts).
- Browser history isn't reported, just IOC-hit signals.
- Operator can OPT into deeper visibility per family-member consent.
- All consent revocable; agent stops reporting on consent withdrawal.

## Roadmap (post Phase 4 product extraction)

1. Define shared protocol (gRPC? HTTPS+JSON?)
2. Build central hub (Workers + KV)
3. Add `family-hub` skill on operator side
4. Onboarding video / family-friendly install
5. App Store distribution

## Scope guardrails

This file exists so future-Claude / future-Matt remember: Family Mode is the productization moat. Don't ship the standalone product without thinking about it. But don't build it now — needs Phase 0-3 working in the field first.
