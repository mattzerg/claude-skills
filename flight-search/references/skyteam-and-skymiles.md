# SkyTeam carriers, SkyMiles cheat-sheet & Amadeus setup

## SkyTeam member airlines (IATA codes)

| Code | Airline | Code | Airline |
|------|---------|------|---------|
| DL | Delta | KL | KLM |
| AF | Air France | AZ | ITA Airways |
| KE | Korean Air | AM | Aeroméxico |
| UX | Air Europa | SV | Saudia |
| RO | Tarom | MU | China Eastern |
| GA | Garuda | KQ | Kenya Airways |
| ME | Middle East Airlines | VN | Vietnam Airlines |
| MF | Xiamen Air | OK | Czech Airlines |

**Not SkyTeam, but Delta transatlantic JV partner** (book/earn like Delta on Atlantic routes):
- **VS** — Virgin Atlantic.

The `--alliance SKYTEAM` flag in `flight_search.py` expands to: `DL,KL,AF,AZ,KE,AM,UX,SV,RO,MU,GA,KQ,ME,VN,MF,OK,VS`.

Cheap intra-Europe carriers that are **NOT** SkyTeam (use cash, not a SkyTeam filter):
Vueling (VY), easyJet (U2), Ryanair (FR), Transavia (HV — KLM's LCC, partial), British Airways (BA), Iberia (IB — oneworld).

## SkyMiles vs. transferable points — DON'T conflate

| | Delta SkyMiles | Transferable (Amex MR / Chase UR / Cap One / Citi) |
|--|--|--|
| Transfer to Flying Blue (AF/KLM)? | ❌ No | ✅ 1:1 |
| Transfer to Virgin Atlantic? | ❌ No | ✅ 1:1 |
| Flying Blue Promo Rewards (~36–45k OW biz)? | ❌ Not accessible | ✅ Yes |
| Virgin → Delta One (50k OW)? | ❌ Not accessible | ✅ Yes (but ~$1,000+ surcharges now) |
| Best lever | Delta-metal Delta One from a Delta hub + flash sales + flexible calendar | Flying Blue promos / Virgin sweet spots |

**Rule for SkyMiles asks:** route value through **Delta-operated** Delta One out of a
Delta hub (ATL, DTW, MSP, JFK, SLC, BOS, SEA, LAX), watch **delta.com flexible-date
calendar** day-to-day, and chase **SkyMiles flash sales** (Delta has run ~19k one-way /
RT economy-to-Europe drops). Delta One **ex-Europe** taxes are low; originating-US can be
higher. Typical Delta One US↔Europe ≈ **57.5–85k SkyMiles one-way** on good days (dynamic).

## Award pricing has no public API → pull via playwright-skill

`flight_search.py award` prints the playbook; execute the pull with `playwright-skill`:
1. Open https://www.delta.com using the saved Delta login session.
2. Search the leg, toggle **Shop with Miles**, set cabin = **Delta One (Business)**.
3. Open the **Flexible Dates / Low Fare Calendar** (5-week grid).
4. Read SkyMiles price + taxes per date across the window; return the cheapest.
5. Prefer **Delta-operated** segments (hub departures) for best Delta One space.

## Amadeus Self-Service notes

- Token: `POST {base}/v1/security/oauth2/token` (client_credentials).
- Cash search GET (one-way/RT): `/v2/shopping/flight-offers` — params incl. `travelClass`,
  `includedAirlineCodes`, `nonStop`, `maxNumberOfConnections`, `currencyCode`, `max`.
- Multi-city: **POST** `/v2/shopping/flight-offers` with `originDestinations[]`,
  `searchCriteria.flightFilters.cabinRestrictions` + `carrierRestrictions.includedCarrierCodes`.
- `base` = `https://test.api.amadeus.com` (free, limited) or `https://api.amadeus.com`
  (production; set `AMADEUS_ENV=production`).
- Amadeus returns **cash** fares only — it does **not** price SkyMiles awards.
