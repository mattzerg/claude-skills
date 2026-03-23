#!/usr/bin/env python3
"""DreamHost DNS Management Skill - Manage DNS records via DreamHost API."""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
import urllib.parse
import uuid

SKILL_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(SKILL_DIR, "config.json")
API_BASE = "https://api.dreamhost.com/"


def load_config():
    if not os.path.exists(CONFIG_FILE):
        print(json.dumps({
            "error": "config.json not found",
            "setup": f"Create {CONFIG_FILE} with: {{\"api_key\": \"YOUR_KEY\"}}"
        }, indent=2))
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        config = json.load(f)
    if not config.get("api_key"):
        print(json.dumps({
            "error": "api_key required in config.json"
        }, indent=2))
        sys.exit(1)
    return config


def api_request(config, cmd, **params):
    """Make a DreamHost API request. All requests are GET with query params."""
    query = {
        "key": config["api_key"],
        "cmd": cmd,
        "format": "json",
        "unique_id": str(uuid.uuid4()),
    }
    query.update(params)
    url = f"{API_BASE}?{urllib.parse.urlencode(query)}"

    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            result = json.loads(raw)
            if result.get("result") == "error":
                print(json.dumps({
                    "error": "DreamHost API error",
                    "detail": result.get("data", "Unknown error")
                }, indent=2))
                sys.exit(1)
            return result
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        try:
            error_data = json.loads(error_body)
        except json.JSONDecodeError:
            error_data = {"raw": error_body}
        print(json.dumps({
            "error": f"HTTP {e.code}",
            "detail": error_data
        }, indent=2))
        sys.exit(1)


def get_all_records(config):
    """Fetch all DNS records from the account."""
    result = api_request(config, "dns-list_records")
    return result.get("data", [])


def resolve_record_name(name, domain):
    """Resolve a record name to a fully qualified domain name.

    '@' becomes the bare domain. Any name without a dot gets '.domain' appended.
    Names that already end with the domain are returned as-is.
    """
    if name == "@":
        return domain
    if name.endswith(f".{domain}"):
        return name
    if name == domain:
        return domain
    return f"{name}.{domain}"


def cmd_list_domains(args, config):
    """List all unique domains (zones) in the account."""
    records = get_all_records(config)
    zones = {}
    for r in records:
        zone = r.get("zone", "")
        if zone not in zones:
            zones[zone] = {"zone": zone, "record_count": 0, "editable_count": 0}
        zones[zone]["record_count"] += 1
        if r.get("editable") == "1":
            zones[zone]["editable_count"] += 1

    domains = sorted(zones.values(), key=lambda x: x["zone"])
    print(json.dumps({"domains": domains, "count": len(domains)}, indent=2))


def cmd_get_records(args, config):
    """Get DNS records for a domain, optionally filtered by type and name."""
    all_records = get_all_records(config)

    # Filter by domain (zone)
    records = [r for r in all_records if r.get("zone") == args.domain]

    # Further filter by type
    if args.type:
        records = [r for r in records if r.get("type", "").upper() == args.type.upper()]

    # Further filter by name
    if args.name:
        target_name = args.name
        if target_name == "@":
            target_name = args.domain
        records = [r for r in records if r.get("record") == target_name or r.get("record") == f"{target_name}.{args.domain}"]

    formatted = []
    for r in records:
        formatted.append({
            "record": r.get("record"),
            "type": r.get("type"),
            "value": r.get("value"),
            "editable": r.get("editable") == "1",
            "comment": r.get("comment", ""),
        })

    print(json.dumps({
        "domain": args.domain,
        "records": formatted,
        "count": len(formatted)
    }, indent=2))


def cmd_add_record(args, config):
    """Add a new DNS record."""
    record_name = resolve_record_name(args.name, args.domain)

    params = {
        "record": record_name,
        "type": args.type.upper(),
        "value": args.data,
    }
    if args.comment:
        params["comment"] = args.comment

    api_request(config, "dns-add_record", **params)
    print(json.dumps({
        "status": "ok",
        "action": "added",
        "domain": args.domain,
        "record": record_name,
        "type": args.type.upper(),
        "value": args.data,
    }, indent=2))


def cmd_remove_record(args, config):
    """Remove a DNS record (must specify exact record, type, and value)."""
    record_name = resolve_record_name(args.name, args.domain)

    params = {
        "record": record_name,
        "type": args.type.upper(),
        "value": args.data,
    }

    api_request(config, "dns-remove_record", **params)
    print(json.dumps({
        "status": "ok",
        "action": "removed",
        "domain": args.domain,
        "record": record_name,
        "type": args.type.upper(),
        "value": args.data,
    }, indent=2))


def cmd_set_record(args, config):
    """Set a DNS record (removes existing records of same type+name, then adds new one).

    Since DreamHost has no update API, this does remove-then-add.
    Only removes editable records that match the type and resolved name.
    """
    record_name = resolve_record_name(args.name, args.domain)

    rtype = args.type.upper()

    # Find existing records of the same type+name
    all_records = get_all_records(config)
    existing = [
        r for r in all_records
        if r.get("zone") == args.domain
        and r.get("record") == record_name
        and r.get("type", "").upper() == rtype
        and r.get("editable") == "1"
    ]

    removed = []
    for r in existing:
        try:
            api_request(config, "dns-remove_record",
                        record=r["record"], type=r["type"], value=r["value"])
            removed.append(r["value"])
        except SystemExit:
            print(json.dumps({
                "warning": f"Failed to remove existing record: {r['value']}"
            }, indent=2))

    # Add the new record
    params = {
        "record": record_name,
        "type": rtype,
        "value": args.data,
    }
    if args.comment:
        params["comment"] = args.comment

    api_request(config, "dns-add_record", **params)

    print(json.dumps({
        "status": "ok",
        "action": "set",
        "domain": args.domain,
        "record": record_name,
        "type": rtype,
        "value": args.data,
        "removed_old_values": removed,
    }, indent=2))


def cmd_bulk_set(args, config):
    """Set multiple DNS records from a JSON file or inline JSON.

    For each record, removes existing editable records of the same type+name,
    then adds the new record.
    """
    if os.path.exists(args.records):
        with open(args.records) as f:
            records = json.load(f)
    else:
        records = json.loads(args.records)

    # Fetch all records once for efficiency
    all_records = get_all_records(config)

    results = []
    for rec in records:
        rtype = rec["type"].upper()
        name = rec["name"]
        data = rec["data"]
        comment = rec.get("comment", "")

        record_name = resolve_record_name(name, args.domain)

        # Remove existing editable records of this type+name
        existing = [
            r for r in all_records
            if r.get("zone") == args.domain
            and r.get("record") == record_name
            and r.get("type", "").upper() == rtype
            and r.get("editable") == "1"
        ]

        removed = []
        for r in existing:
            try:
                api_request(config, "dns-remove_record",
                            record=r["record"], type=r["type"], value=r["value"])
                removed.append(r["value"])
            except SystemExit:
                pass

        # Add the new record
        try:
            params = {"record": record_name, "type": rtype, "value": data}
            if comment:
                params["comment"] = comment
            api_request(config, "dns-add_record", **params)
            results.append({
                "record": record_name, "type": rtype, "value": data,
                "status": "ok", "removed_old": removed
            })
        except SystemExit:
            results.append({
                "record": record_name, "type": rtype, "value": data,
                "status": "error", "removed_old": removed
            })

    print(json.dumps({
        "domain": args.domain,
        "results": results,
        "total": len(results),
        "success": sum(1 for r in results if r["status"] == "ok"),
    }, indent=2))


def cmd_check_dns(args, config):
    """Check current DNS propagation for a domain using system dig."""
    import subprocess
    domain = args.domain
    checks = {}

    for rtype in ["A", "AAAA", "CNAME", "MX", "TXT", "NS"]:
        try:
            result = subprocess.run(
                ["dig", "+short", domain, rtype],
                capture_output=True, text=True, timeout=10
            )
            values = [v.strip() for v in result.stdout.strip().split("\n") if v.strip()]
            if values:
                checks[rtype] = values
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Also check www
    try:
        result = subprocess.run(
            ["dig", "+short", f"www.{domain}", "CNAME"],
            capture_output=True, text=True, timeout=10
        )
        www = [v.strip() for v in result.stdout.strip().split("\n") if v.strip()]
        if www:
            checks["www_CNAME"] = www
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    print(json.dumps({"domain": domain, "resolved": checks}, indent=2))


def main():
    parser = argparse.ArgumentParser(description="DreamHost DNS Management")
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # list-domains
    sub.add_parser("list-domains", help="List all domains/zones in account")

    # get-records
    p = sub.add_parser("get-records", help="Get DNS records for a domain")
    p.add_argument("domain", help="Domain name (e.g., epochml.com)")
    p.add_argument("--type", "-t", help="Filter by record type (A, AAAA, CNAME, MX, TXT, NS)")
    p.add_argument("--name", "-n", help="Filter by record name (@ for root, www, etc.)")

    # add-record
    p = sub.add_parser("add-record", help="Add a DNS record")
    p.add_argument("domain", help="Domain name")
    p.add_argument("type", help="Record type (A, AAAA, CNAME, NS, NAPTR, SRV, TXT)")
    p.add_argument("name", help="Record name (@ for root, www, etc.)")
    p.add_argument("data", help="Record value (IP, hostname, etc.)")
    p.add_argument("--comment", help="Optional comment for the record")

    # remove-record
    p = sub.add_parser("remove-record", help="Remove a DNS record (requires exact type+name+value)")
    p.add_argument("domain", help="Domain name")
    p.add_argument("type", help="Record type")
    p.add_argument("name", help="Record name (@ for root)")
    p.add_argument("data", help="Exact record value to remove")

    # set-record (remove old + add new)
    p = sub.add_parser("set-record", help="Set a DNS record (replaces existing editable records of same type+name)")
    p.add_argument("domain", help="Domain name")
    p.add_argument("type", help="Record type (A, AAAA, CNAME, TXT, etc.)")
    p.add_argument("name", help="Record name (@ for root, www, etc.)")
    p.add_argument("data", help="Record value (IP, hostname, etc.)")
    p.add_argument("--comment", help="Optional comment for the record")

    # bulk-set
    p = sub.add_parser("bulk-set", help="Set multiple DNS records from JSON")
    p.add_argument("domain", help="Domain name")
    p.add_argument("records", help="JSON array of records or path to JSON file")

    # check-dns
    p = sub.add_parser("check-dns", help="Check DNS propagation for a domain")
    p.add_argument("domain", help="Domain name")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = load_config()

    commands = {
        "list-domains": cmd_list_domains,
        "get-records": cmd_get_records,
        "add-record": cmd_add_record,
        "remove-record": cmd_remove_record,
        "set-record": cmd_set_record,
        "bulk-set": cmd_bulk_set,
        "check-dns": cmd_check_dns,
    }

    commands[args.command](args, config)


if __name__ == "__main__":
    main()
