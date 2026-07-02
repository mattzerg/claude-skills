#!/usr/bin/env python3
"""
flight-search -- cash fare search (Amadeus) + SkyMiles award/deal-hunting playbooks.

Sibling to flight-skill (which TRACKS already-booked flights). This one SHOPS:

  search   one-way / round-trip cash fares (alliance + cabin + flexible-date filters)
  multi    multi-city / open-jaw cash fares (e.g. DTW->LHR ... BCN->DTW)
  deals    SkyMiles flash-sale + cash deal playbook with pre-filled deep links
  award    delta.com SkyMiles flexible-calendar playbook (run the pull via playwright-skill)

Cash search needs FREE Amadeus Self-Service creds in the environment:
    export AMADEUS_CLIENT_ID=...
    export AMADEUS_CLIENT_SECRET=...
    export AMADEUS_ENV=production    # optional; default is the free 'test' env
Get keys at https://developers.amadeus.com (Self-Service -> create app).

Why award pricing is a playbook, not an API call: Delta SkyMiles is dynamically
priced and exposed nowhere public. The only reliable source is the logged-in
delta.com flexible-date calendar -- drive it with the existing playwright-skill.

stdlib only. Python 3.9+.
"""

import argparse
import json
import os
import sys
import urllib.parse
import urllib.request
import urllib.error
from datetime import date, datetime, timedelta

# --- SkyTeam (+ Delta transatlantic JV partner Virgin Atlantic) IATA codes -----
SKYTEAM = ["DL", "KL", "AF", "AZ", "KE", "AM", "UX", "SV", "RO", "MU",
           "GA", "KQ", "ME", "VN", "MF", "OK", "VS"]  # VS = Virgin Atlantic (DL JV, not SkyTeam)
ALLIANCES = {"SKYTEAM": SKYTEAM}

CABINS = {
    "economy": "ECONOMY",
    "premium": "PREMIUM_ECONOMY",
    "business": "BUSINESS",
    "first": "FIRST",
}


def _base():
    env = os.environ.get("AMADEUS_ENV", "test").lower()
    return "https://api.amadeus.com" if env == "production" else "https://test.api.amadeus.com"


def _have_creds():
    return bool(os.environ.get("AMADEUS_CLIENT_ID") and os.environ.get("AMADEUS_CLIENT_SECRET"))


def _creds_help():
    return (
        "Amadeus credentials not found. Cash fare search needs a (free) key:\n"
        "    export AMADEUS_CLIENT_ID=...\n"
        "    export AMADEUS_CLIENT_SECRET=...\n"
        "    export AMADEUS_ENV=production   # optional; default 'test' (limited but free)\n"
        "Sign up at https://developers.amadeus.com -> Self-Service -> create an app.\n"
        "(The 'deals' and 'award' subcommands work WITHOUT a key.)"
    )


def _get_token():
    base = _base()
    data = urllib.parse.urlencode({
        "grant_type": "client_credentials",
        "client_id": os.environ["AMADEUS_CLIENT_ID"],
        "client_secret": os.environ["AMADEUS_CLIENT_SECRET"],
    }).encode()
    req = urllib.request.Request(
        base + "/v1/security/oauth2/token", data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)["access_token"]


def _api(path, token, params=None, body=None):
    base = _base()
    headers = {"Authorization": "Bearer " + token}
    if body is None:
        url = base + path + ("?" + urllib.parse.urlencode(params) if params else "")
        req = urllib.request.Request(url, headers=headers)
    else:
        headers["Content-Type"] = "application/json"
        req = urllib.request.Request(base + path, data=json.dumps(body).encode(), headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")
        raise SystemExit("Amadeus API error %s:\n%s" % (e.code, detail))


def _carriers(args):
    """Resolve --alliance / --airlines into an includedAirlineCodes list (or None)."""
    if getattr(args, "airlines", None):
        return [c.strip().upper() for c in args.airlines.split(",") if c.strip()]
    if getattr(args, "alliance", None):
        al = args.alliance.upper()
        if al not in ALLIANCES:
            raise SystemExit("Unknown alliance %r. Known: %s" % (args.alliance, ", ".join(ALLIANCES)))
        return list(ALLIANCES[al])
    return None


# ----------------------------- formatting -------------------------------------
def _fmt_dt(iso):
    try:
        d = datetime.fromisoformat(iso)
        return d.strftime("%m/%d %H:%M")
    except Exception:
        return iso


def _fmt_dur(iso):
    return (iso or "").replace("PT", "").replace("H", "h").replace("M", "m").lower()


def _segline(seg):
    dep, arr = seg["departure"], seg["arrival"]
    return "%s %s -> %s %s  %s%s  [%s]" % (
        dep["iataCode"], _fmt_dt(dep["at"]),
        arr["iataCode"], _fmt_dt(arr["at"]),
        seg["carrierCode"], seg["number"], _fmt_dur(seg.get("duration")))


def _fmt_offer(offer, n):
    price = offer["price"]
    val = ",".join(offer.get("validatingAirlineCodes", []) or ["?"])
    out = ["#%d  %s %s   (plates: %s)" % (n, price.get("grandTotal", price.get("total")),
                                          price.get("currency", ""), val)]
    for i, it in enumerate(offer["itineraries"]):
        segs = it["segments"]
        stops = len(segs) - 1
        carriers = "/".join(sorted({s["carrierCode"] for s in segs}))
        out.append("   leg %d: %s  (%d stop%s, %s, %s)" % (
            i + 1, segs[0]["departure"]["iataCode"] + "->" + segs[-1]["arrival"]["iataCode"],
            stops, "" if stops == 1 else "s", carriers, _fmt_dur(it.get("duration"))))
        for s in segs:
            out.append("        " + _segline(s))
    return "\n".join(out)


def _print_offers(resp, args, limit):
    offers = resp.get("data", [])
    if not offers:
        print("No offers found (try widening dates, cabin, or carriers).")
        return
    offers.sort(key=lambda o: float(o["price"].get("grandTotal", o["price"].get("total", 1e9))))
    if args.json:
        print(json.dumps(offers[:limit], indent=2))
        return
    for n, o in enumerate(offers[:limit], 1):
        print(_fmt_offer(o, n))
        print()


# ----------------------------- subcommands ------------------------------------
def cmd_search(args):
    if not _have_creds():
        raise SystemExit(_creds_help())
    token = _get_token()
    carriers = _carriers(args)

    def one(dep_date):
        params = {
            "originLocationCode": args.origin.upper(),
            "destinationLocationCode": args.dest.upper(),
            "departureDate": dep_date,
            "adults": args.adults,
            "currencyCode": "USD",
            "max": 50 if args.flexible else args.limit,
            "travelClass": CABINS[args.cabin],
        }
        if args.return_date:
            params["returnDate"] = args.return_date
        if carriers:
            params["includedAirlineCodes"] = ",".join(carriers)
        if args.nonstop:
            params["nonStop"] = "true"
        if args.max_stops is not None and not args.nonstop:
            params["maxNumberOfConnections"] = args.max_stops
        return _api("/v2/shopping/flight-offers", token, params=params)

    if not args.flexible:
        _print_offers(one(args.date), args, args.limit)
        return

    # flexible-date calendar: cheapest offer per outbound date in +/- N window
    base_d = datetime.strptime(args.date, "%Y-%m-%d").date()
    rows = []
    for off in range(-args.flexible, args.flexible + 1):
        d = (base_d + timedelta(days=off)).isoformat()
        try:
            data = one(d).get("data", [])
        except SystemExit:
            data = []
        if data:
            best = min(data, key=lambda o: float(o["price"]["grandTotal"]))
            rows.append((d, best["price"]["grandTotal"], best["price"]["currency"],
                         "/".join(sorted({s["carrierCode"] for s in best["itineraries"][0]["segments"]})),
                         len(best["itineraries"][0]["segments"]) - 1))
        else:
            rows.append((d, None, "", "", None))
    if args.json:
        print(json.dumps([{"date": r[0], "price": r[1], "currency": r[2],
                           "carriers": r[3], "stops": r[4]} for r in rows], indent=2))
        return
    print("Flexible-date cheapest (%s->%s, %s):" % (args.origin.upper(), args.dest.upper(), args.cabin))
    for d, p, c, car, st in rows:
        print("  %s  %s" % (d, "no offers" if p is None else "%8s %s  %s  %s stop(s)" % (p, c, car, st)))


def cmd_multi(args):
    if not _have_creds():
        raise SystemExit(_creds_help())
    if len(args.legs) % 3 != 0 or len(args.legs) < 6:
        raise SystemExit("multi needs legs as ORIG DEST YYYY-MM-DD triples (>=2 legs). "
                         "e.g. DTW LHR 2026-07-12 BCN DTW 2026-07-25")
    token = _get_token()
    carriers = _carriers(args)
    ods, ids = [], []
    for i in range(0, len(args.legs), 3):
        oid = str(i // 3 + 1)
        ids.append(oid)
        ods.append({"id": oid, "originLocationCode": args.legs[i].upper(),
                    "destinationLocationCode": args.legs[i + 1].upper(),
                    "departureDateTimeRange": {"date": args.legs[i + 2]}})
    body = {
        "currencyCode": "USD",
        "originDestinations": ods,
        "travelers": [{"id": str(k + 1), "travelerType": "ADULT"} for k in range(args.adults)],
        "sources": ["GDS"],
        "searchCriteria": {
            "maxFlightOffers": args.limit,
            "flightFilters": {
                "cabinRestrictions": [{"cabin": CABINS[args.cabin],
                                       "coverage": "MOST_SEGMENTS",
                                       "originDestinationIds": ids}],
            },
        },
    }
    if carriers:
        body["searchCriteria"]["flightFilters"]["carrierRestrictions"] = {"includedCarrierCodes": carriers}
    _print_offers(_api("/v2/shopping/flight-offers", token, body=body), args, args.limit)


def _gf(orig, dest, d):
    return "https://www.google.com/travel/flights?q=" + urllib.parse.quote(
        "flights from %s to %s on %s" % (orig.upper(), dest.upper(), d))


def cmd_deals(args):
    legs = args.route or [("DTW", "LHR", "2026-07-12"), ("AMS", "DTW", "2026-07-28")]
    print("=== SkyMiles + cash deal-hunting playbook (DTW <-> Europe) ===\n")
    print("100k Delta SkyMiles are airline miles (NOT transferable to Flying Blue/Virgin),")
    print("so the levers are Delta-metal Delta One out of the DTW hub + flash sales.\n")
    print("1. Delta SkyMiles flash sales -- the #1 lever for SkyMiles value:")
    print("   - https://www.delta.com/us/en/flight-deals/all-flight-deals")
    print("   - https://thriftytraveler.com/tag/delta/   (and TPG Delta deal alerts)")
    print("2. delta.com flexible-date calendar (LOGIN -> 'Shop with Miles'); see `award`.")
    print("3. Cash cross-check (bank miles if a cash deal wins):")
    for o, d_, dt in legs:
        print("   - %s->%s %s : %s" % (o, d_, dt, _gf(o, d_, dt)))
    print("4. ITA Matrix for fare construction / open-jaw cash: https://matrix.itasoftware.com")
    print("\nRule of thumb: Delta One DTW<->Europe ~57.5-85k SkyMiles one-way on good days;")
    print("if cash business is cheap or a SkyMiles flash sale hits, grab business both ways.")


def cmd_award(args):
    o, d_ = args.origin.upper(), args.dest.upper()
    flex = args.flexible or 2
    print("=== delta.com SkyMiles award playbook: %s -> %s (+/- %d days) ===\n" % (o, d_, flex))
    print("SkyMiles dynamic pricing has no public API. Pull it from the LOGGED-IN")
    print("delta.com flexible calendar -- drive it with the playwright-skill:\n")
    print("  1. playwright-skill: open https://www.delta.com (use saved Delta login session)")
    print("  2. Search %s -> %s, toggle 'Shop with Miles', cabin = Delta One (Business)" % (o, d_))
    print("  3. Open the 'Flexible Dates / Low Fare Calendar' (5-week grid)")
    print("  4. Read the SkyMiles price + taxes for each date in the window; return cheapest")
    print("  5. Prefer Delta-OPERATED metal (DTW hub) for best Delta One space\n")
    print("Manual fallback (no automation): delta.com -> Advanced Search -> Shop with Miles.")
    print("Cash sanity check for the same leg: %s" % _gf(o, d_, args.date or "2026-07-12"))


# --------------------------------- CLI ----------------------------------------
def build_parser():
    p = argparse.ArgumentParser(prog="flight_search", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)

    def add_common(sp):
        sp.add_argument("--alliance", help="filter by alliance (e.g. SKYTEAM)")
        sp.add_argument("--airlines", help="comma list of IATA carrier codes (e.g. DL,KL,AF,VS)")
        sp.add_argument("--cabin", choices=list(CABINS), default="economy")
        sp.add_argument("--adults", type=int, default=1)
        sp.add_argument("--max-stops", type=int, default=None, dest="max_stops")
        sp.add_argument("--nonstop", action="store_true")
        sp.add_argument("--limit", type=int, default=10)
        sp.add_argument("--json", action="store_true")

    s = sub.add_parser("search", help="one-way / round-trip cash fares")
    s.add_argument("origin"); s.add_argument("dest"); s.add_argument("date")
    s.add_argument("return_date", nargs="?", default=None)
    s.add_argument("--flexible", type=int, default=0, metavar="N",
                   help="cheapest-fare calendar across +/- N days on the outbound")
    add_common(s)
    s.set_defaults(func=cmd_search)

    m = sub.add_parser("multi", help="multi-city / open-jaw cash fares")
    m.add_argument("legs", nargs="+", help="ORIG DEST YYYY-MM-DD triples, repeated")
    add_common(m)
    m.set_defaults(func=cmd_multi)

    dl = sub.add_parser("deals", help="SkyMiles + cash deal playbook with deep links")
    dl.add_argument("--route", action="append", nargs=3, metavar=("ORIG", "DEST", "DATE"),
                    help="override default legs; repeatable")
    dl.set_defaults(func=cmd_deals)

    aw = sub.add_parser("award", help="delta.com SkyMiles flexible-calendar playbook")
    aw.add_argument("origin"); aw.add_argument("dest")
    aw.add_argument("--date", default=None, help="anchor date for the cash sanity link")
    aw.add_argument("--flexible", type=int, default=2, metavar="N")
    aw.set_defaults(func=cmd_award)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
