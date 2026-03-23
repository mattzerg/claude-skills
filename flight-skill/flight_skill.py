#!/usr/bin/env python3
"""
Flight tracking skill using FlightRadar24 public API.

Usage:
    python3 flight_skill.py status WN3971
    python3 flight_skill.py status WN3971 --date 2026-03-16
    python3 flight_skill.py status WN3971 --live
    python3 flight_skill.py trip WN3971 WN1267
    python3 flight_skill.py trip WN3971 WN1267 --date 2026-03-16
    python3 flight_skill.py airport MDW --arrivals
    python3 flight_skill.py airport MDW --departures
"""

import argparse
import json
import sys
import urllib.request
import urllib.error
from datetime import datetime, timezone, timedelta


FR24_API = "https://api.flightradar24.com/common/v1/flight/list.json"
FR24_AIRPORT_API = "https://api.flightradar24.com/common/v1/airport.json"


def fetch_json(url):
    """Fetch JSON from URL."""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0",
        "Accept": "application/json",
    })
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        return {"error": f"HTTP {e.code}: {e.reason}"}
    except Exception as e:
        return {"error": str(e)}


def parse_timestamp(ts):
    """Convert unix timestamp to readable string."""
    if not ts:
        return None
    return datetime.fromtimestamp(ts, tz=timezone.utc)


def fmt_time(ts, tz_offset=None):
    """Format a timestamp for display."""
    if ts is None:
        return "N/A"
    dt = parse_timestamp(ts)
    if dt is None:
        return "N/A"
    if tz_offset is not None:
        dt = dt + timedelta(seconds=tz_offset)
    return dt.strftime("%I:%M %p")


def fmt_date(ts):
    """Format a timestamp as date."""
    if ts is None:
        return "N/A"
    dt = parse_timestamp(ts)
    if dt is None:
        return "N/A"
    return dt.strftime("%Y-%m-%d")


def get_flights(flight_number, limit=25):
    """Fetch flight data from FR24."""
    # Normalize flight number: remove spaces, uppercase
    flight_number = flight_number.replace(" ", "").upper()
    # Convert common formats: SWA3971 -> WN3971
    airline_map = {
        "SWA": "WN", "UAL": "UA", "DAL": "DL", "AAL": "AA",
        "JBU": "B6", "ASA": "AS", "NKS": "NK", "FFT": "F9",
    }
    for icao, iata in airline_map.items():
        if flight_number.startswith(icao):
            flight_number = iata + flight_number[len(icao):]
            break

    url = f"{FR24_API}?query={flight_number}&fetchBy=flight&page=1&limit={limit}&token="
    return fetch_json(url), flight_number


def parse_flight(f):
    """Parse a single flight entry into a clean dict."""
    status = f.get("status", {})
    origin = f.get("airport", {}).get("origin", {})
    dest = f.get("airport", {}).get("destination", {})
    time_data = f.get("time", {})
    aircraft = f.get("aircraft", {})

    sched_dep = time_data.get("scheduled", {}).get("departure")
    sched_arr = time_data.get("scheduled", {}).get("arrival")
    real_dep = time_data.get("real", {}).get("departure")
    real_arr = time_data.get("real", {}).get("arrival")
    est_dep = time_data.get("estimated", {}).get("departure")
    est_arr = time_data.get("estimated", {}).get("arrival")

    origin_tz = origin.get("timezone", {}).get("offset", 0)
    dest_tz = dest.get("timezone", {}).get("offset", 0)

    # Calculate delay
    delay_dep = None
    delay_arr = None
    if sched_dep and (real_dep or est_dep):
        actual = real_dep or est_dep
        delay_dep = (actual - sched_dep) // 60  # minutes
    if sched_arr and (real_arr or est_arr):
        actual = real_arr or est_arr
        delay_arr = (actual - sched_arr) // 60

    generic = status.get("generic", {}).get("status", {})

    return {
        "flight": f.get("identification", {}).get("number", {}).get("default", "?"),
        "status": status.get("text", "Unknown"),
        "status_color": generic.get("color", "gray"),
        "live": status.get("live", False),
        "origin": {
            "iata": origin.get("code", {}).get("iata", "?"),
            "name": origin.get("name", "?"),
            "city": origin.get("position", {}).get("region", {}).get("city", "?"),
            "tz": origin.get("timezone", {}).get("abbr", "?"),
            "tz_offset": origin_tz,
        },
        "destination": {
            "iata": dest.get("code", {}).get("iata", "?"),
            "name": dest.get("name", "?"),
            "city": dest.get("position", {}).get("region", {}).get("city", "?"),
            "tz": dest.get("timezone", {}).get("abbr", "?"),
            "tz_offset": dest_tz,
        },
        "times": {
            "sched_dep": sched_dep,
            "sched_arr": sched_arr,
            "est_dep": est_dep,
            "est_arr": est_arr,
            "real_dep": real_dep,
            "real_arr": real_arr,
            "sched_dep_local": fmt_time(sched_dep, origin_tz),
            "sched_arr_local": fmt_time(sched_arr, dest_tz),
            "est_dep_local": fmt_time(est_dep, origin_tz),
            "est_arr_local": fmt_time(est_arr, dest_tz),
            "real_dep_local": fmt_time(real_dep, origin_tz),
            "real_arr_local": fmt_time(real_arr, dest_tz),
        },
        "delay": {
            "departure_min": delay_dep,
            "arrival_min": delay_arr,
        },
        "aircraft": {
            "model": aircraft.get("model", {}).get("text") or aircraft.get("model", {}).get("code", "?"),
            "registration": aircraft.get("registration", None),
        },
        "date": fmt_date(sched_dep),
    }


def filter_by_date(flights, target_date):
    """Filter flights to a specific date (UTC-based, but with some flexibility)."""
    results = []
    for f in flights:
        sched_dep = f.get("time", {}).get("scheduled", {}).get("departure")
        if sched_dep:
            dt = parse_timestamp(sched_dep)
            # Check if the flight's scheduled departure date matches
            # Allow +/- 1 day since timezones can shift things
            if dt:
                flight_date = dt.strftime("%Y-%m-%d")
                # Also check the day before/after in case of timezone shifts
                target = datetime.strptime(target_date, "%Y-%m-%d")
                flight_dt = datetime.strptime(flight_date, "%Y-%m-%d")
                if abs((flight_dt - target).days) <= 0:
                    results.append(f)
                elif abs((flight_dt - target).days) == 1:
                    # Include if within 12 hours of target date boundaries
                    results.append(f)
    return results


def get_today_flights(flights, flight_number):
    """Get the most relevant current/today flights."""
    now = datetime.now(timezone.utc)
    today = now.strftime("%Y-%m-%d")
    yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")

    relevant = []
    for f in flights:
        sched_dep = f.get("time", {}).get("scheduled", {}).get("departure")
        if sched_dep:
            dt = parse_timestamp(sched_dep)
            if dt:
                # Include flights from last 24 hours to next 24 hours
                diff = (now - dt).total_seconds() / 3600
                if -24 <= diff <= 24:
                    relevant.append(f)

    return relevant if relevant else flights[:4]  # fallback to most recent


def format_flight_display(parsed, verbose=False):
    """Format a parsed flight for display."""
    t = parsed["times"]
    d = parsed["delay"]
    o = parsed["origin"]
    dest = parsed["destination"]

    # Status emoji based on color
    status_icon = {
        "green": "ON TIME",
        "yellow": "MINOR DELAY",
        "red": "DELAYED",
        "gray": "SCHEDULED",
    }.get(parsed["status_color"], parsed["status"])

    live_marker = " [LIVE - IN AIR]" if parsed["live"] else ""

    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"  {parsed['flight']}  |  {status_icon}{live_marker}")
    lines.append(f"  {o['iata']} ({o['city']}) → {dest['iata']} ({dest['city']})")
    lines.append(f"{'='*60}")

    # Departure
    dep_line = f"  Departure ({o['tz']}):  Sched {t['sched_dep_local']}"
    if t["real_dep_local"] != "N/A":
        dep_line += f"  →  Actual {t['real_dep_local']}"
    elif t["est_dep_local"] != "N/A":
        dep_line += f"  →  Est {t['est_dep_local']}"
    if d["departure_min"] and d["departure_min"] > 0:
        dep_line += f"  ({d['departure_min']}min late)"
    lines.append(dep_line)

    # Arrival
    arr_line = f"  Arrival ({dest['tz']}):    Sched {t['sched_arr_local']}"
    if t["real_arr_local"] != "N/A":
        arr_line += f"  →  Actual {t['real_arr_local']}"
    elif t["est_arr_local"] != "N/A":
        arr_line += f"  →  Est {t['est_arr_local']}"
    if d["arrival_min"] and d["arrival_min"] > 0:
        arr_line += f"  ({d['arrival_min']}min late)"
    lines.append(arr_line)

    # Aircraft
    if verbose and parsed["aircraft"]["model"] != "?":
        lines.append(f"  Aircraft: {parsed['aircraft']['model']}")
        if parsed["aircraft"]["registration"]:
            lines.append(f"  Reg: {parsed['aircraft']['registration']}")

    lines.append(f"  Date: {parsed['date']}")
    lines.append(f"  Raw status: {parsed['status']}")
    lines.append("")

    return "\n".join(lines)


def cmd_status(args):
    """Look up flight status."""
    data, flight_number = get_flights(args.flight_number, limit=25)

    if "error" in data:
        print(json.dumps({"error": data["error"]}))
        return

    flights = data.get("result", {}).get("response", {}).get("data", [])
    if not flights:
        print(json.dumps({"error": f"No flights found for {flight_number}"}))
        return

    if args.date:
        flights = filter_by_date(flights, args.date)
    elif args.live:
        flights = [f for f in flights if f.get("status", {}).get("live", False)]
        if not flights:
            # Fall back to today's flights
            flights = data.get("result", {}).get("response", {}).get("data", [])
            flights = get_today_flights(flights, flight_number)
    else:
        flights = get_today_flights(flights, flight_number)

    if not flights:
        print(json.dumps({"error": f"No flights found for {flight_number} on specified date"}))
        return

    if args.json:
        parsed = [parse_flight(f) for f in flights]
        print(json.dumps(parsed, indent=2))
    else:
        for f in flights:
            parsed = parse_flight(f)
            print(format_flight_display(parsed, verbose=args.verbose))


def cmd_trip(args):
    """Look up multiple connecting flights."""
    all_flights = []

    for fn in args.flight_numbers:
        data, flight_number = get_flights(fn, limit=25)
        if "error" in data:
            print(f"Error looking up {flight_number}: {data['error']}")
            continue

        flights = data.get("result", {}).get("response", {}).get("data", [])
        if not flights:
            print(f"No flights found for {flight_number}")
            continue

        if args.date:
            day_flights = filter_by_date(flights, args.date)
        else:
            day_flights = get_today_flights(flights, flight_number)

        if not day_flights:
            print(f"No flights found for {flight_number} today")
            continue

        for f in day_flights:
            all_flights.append(parse_flight(f))

    if not all_flights:
        print(json.dumps({"error": "No flights found"}))
        return

    # Sort by scheduled departure
    all_flights.sort(key=lambda x: x["times"]["sched_dep"] or 0)

    if args.json:
        print(json.dumps(all_flights, indent=2))
        return

    print(f"\n{'#'*60}")
    print(f"  TRIP STATUS - {len(all_flights)} segment(s)")
    print(f"{'#'*60}\n")

    for i, f in enumerate(all_flights):
        print(format_flight_display(f, verbose=args.verbose))

    # Connection analysis
    if len(all_flights) >= 2:
        print(f"{'='*60}")
        print(f"  CONNECTION ANALYSIS")
        print(f"{'='*60}")

        for i in range(len(all_flights) - 1):
            leg1 = all_flights[i]
            leg2 = all_flights[i + 1]

            # Check if they connect (leg1 dest = leg2 origin)
            if leg1["destination"]["iata"] == leg2["origin"]["iata"]:
                arr = leg1["times"]["real_arr"] or leg1["times"]["est_arr"] or leg1["times"]["sched_arr"]
                dep = leg2["times"]["real_dep"] or leg2["times"]["est_dep"] or leg2["times"]["sched_dep"]

                if arr and dep:
                    connection_min = (dep - arr) // 60
                    airport = leg1["destination"]["iata"]

                    print(f"\n  {leg1['flight']} → {leg2['flight']} at {airport}")
                    print(f"  Leg 1 arrives:  {fmt_time(arr, leg1['destination']['tz_offset'])} {leg1['destination']['tz']}")
                    print(f"  Leg 2 departs:  {fmt_time(dep, leg2['origin']['tz_offset'])} {leg2['origin']['tz']}")

                    if connection_min >= 0:
                        print(f"  Connection time: {connection_min} minutes")
                        if connection_min < 30:
                            print(f"  *** TIGHT CONNECTION - HIGH RISK OF MISSED FLIGHT ***")
                        elif connection_min < 60:
                            print(f"  ** Connection is tight but possible **")
                        else:
                            print(f"  Connection looks comfortable")
                    else:
                        print(f"  *** MISSED CONNECTION - Leg 2 departs {abs(connection_min)} min BEFORE Leg 1 arrives ***")
            else:
                print(f"\n  Note: {leg1['flight']} arrives at {leg1['destination']['iata']} but {leg2['flight']} departs from {leg2['origin']['iata']}")

        print()


def cmd_airport(args):
    """Look up airport flight board (arrivals/departures)."""
    code = args.airport_code.upper()
    page = "arrivals" if args.arrivals else "departures"

    url = f"{FR24_AIRPORT_API}?code={code}&plugin[]=&plugin-setting[schedule][mode]={page}&plugin-setting[schedule][timestamp]={int(datetime.now(timezone.utc).timestamp())}&page=1&limit=50&token="
    data = fetch_json(url)

    if "error" in data:
        print(json.dumps({"error": data["error"]}))
        return

    schedule = data.get("result", {}).get("response", {}).get("airport", {}).get("plugin", {}).get("schedule", {})
    flights = schedule.get(page, {}).get("data", [])

    if not flights:
        print(json.dumps({"error": f"No {page} found for {code}"}))
        return

    if args.json:
        parsed = [parse_flight(f) for f in flights]
        print(json.dumps(parsed, indent=2))
    else:
        print(f"\n  {code} - {page.upper()}")
        print(f"{'='*60}")
        for f in flights[:30]:  # limit display
            parsed = parse_flight(f)
            status_short = parsed["status"][:20]
            t = parsed["times"]
            if page == "arrivals":
                sched = t["sched_arr_local"]
                actual = t["real_arr_local"] if t["real_arr_local"] != "N/A" else t["est_arr_local"]
                from_to = f"from {parsed['origin']['iata']}"
            else:
                sched = t["sched_dep_local"]
                actual = t["real_dep_local"] if t["real_dep_local"] != "N/A" else t["est_dep_local"]
                from_to = f"to {parsed['destination']['iata']}"

            time_str = f"{sched}"
            if actual != "N/A" and actual != sched:
                time_str += f" → {actual}"

            print(f"  {parsed['flight']:>8}  {from_to:<10}  {time_str:<25}  {status_short}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Flight tracking skill")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # status command
    p_status = subparsers.add_parser("status", help="Look up flight status")
    p_status.add_argument("flight_number", help="Flight number (e.g., WN3971, SWA3971, UA123)")
    p_status.add_argument("--date", help="Filter to specific date (YYYY-MM-DD)")
    p_status.add_argument("--live", action="store_true", help="Show only live/in-air flights")
    p_status.add_argument("--json", action="store_true", help="Output as JSON")
    p_status.add_argument("--verbose", "-v", action="store_true", help="Show extra details")

    # trip command
    p_trip = subparsers.add_parser("trip", help="Look up connecting flights")
    p_trip.add_argument("flight_numbers", nargs="+", help="Flight numbers in order")
    p_trip.add_argument("--date", help="Filter to specific date (YYYY-MM-DD)")
    p_trip.add_argument("--json", action="store_true", help="Output as JSON")
    p_trip.add_argument("--verbose", "-v", action="store_true", help="Show extra details")

    # airport command
    p_airport = subparsers.add_parser("airport", help="Airport flight board")
    p_airport.add_argument("airport_code", help="Airport IATA code (e.g., MDW, SFO)")
    p_airport.add_argument("--arrivals", action="store_true", help="Show arrivals")
    p_airport.add_argument("--departures", action="store_true", help="Show departures")
    p_airport.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    if args.command == "status":
        cmd_status(args)
    elif args.command == "trip":
        cmd_trip(args)
    elif args.command == "airport":
        cmd_airport(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
