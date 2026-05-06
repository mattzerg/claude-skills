#!/usr/bin/env python3
"""Cloudflare API skill — zones, DNS records, Pages projects."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import urllib.parse
import urllib.request
from typing import Any

API_BASE = "https://api.cloudflare.com/client/v4"


def keychain(svc: str, account: str = "matteisn") -> str:
    try:
        return subprocess.check_output(
            ["security", "find-generic-password", "-s", svc, "-a", account, "-w"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except subprocess.CalledProcessError:
        print(json.dumps({"error": f"keychain entry not found: -s {svc} -a {account}",
                          "fix": f"security add-generic-password -s '{svc}' -a {account} -w '...' -U"}, indent=2))
        sys.exit(1)


def cf_request(method: str, path: str, body: Any = None) -> dict:
    email = keychain("cloudflare-email")
    key = keychain("cloudflare-global-key")
    url = f"{API_BASE}{path}"
    headers = {
        "X-Auth-Email": email,
        "X-Auth-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err_body = json.loads(e.read().decode())
        except Exception:
            err_body = {"raw": "<unparseable>"}
        return err_body


def require_success(r: dict) -> dict:
    if not r.get("success"):
        print(json.dumps({"error": "API call failed", "errors": r.get("errors", [])}, indent=2))
        sys.exit(1)
    return r


def get_zone_id(domain: str) -> str:
    r = cf_request("GET", f"/zones?name={urllib.parse.quote(domain)}")
    require_success(r)
    zones = r.get("result", [])
    if not zones:
        print(json.dumps({"error": f"zone not found: {domain}",
                          "hint": "use add-zone to create it"}, indent=2))
        sys.exit(1)
    return zones[0]["id"]


def get_account_id(specified: str | None = None) -> str:
    if specified:
        return specified
    r = cf_request("GET", "/accounts")
    require_success(r)
    accts = r.get("result", [])
    if not accts:
        print(json.dumps({"error": "no accounts available"}, indent=2))
        sys.exit(1)
    if len(accts) > 1:
        print(json.dumps({"error": "multiple accounts; specify --account",
                          "accounts": [{"id": a["id"], "name": a["name"]} for a in accts]}, indent=2))
        sys.exit(1)
    return accts[0]["id"]


# ---------- commands ----------

def cmd_whoami(args):
    r_user = cf_request("GET", "/user")
    r_accts = cf_request("GET", "/accounts")
    out = {
        "user": r_user.get("result", {}).get("email", "?") if r_user.get("success") else r_user.get("errors"),
        "accounts": [{"id": a["id"], "name": a["name"]} for a in r_accts.get("result", [])],
    }
    print(json.dumps(out, indent=2))


def cmd_list_zones(args):
    r = cf_request("GET", "/zones?per_page=50")
    require_success(r)
    out = [{"name": z["name"], "id": z["id"], "status": z["status"],
            "name_servers": z.get("name_servers", [])} for z in r.get("result", [])]
    print(json.dumps(out, indent=2))


def cmd_add_zone(args):
    account_id = get_account_id(args.account)
    body = {"name": args.domain, "account": {"id": account_id}, "type": "full"}
    r = cf_request("POST", "/zones", body)
    if not r.get("success"):
        # check if already exists
        errs = r.get("errors", [])
        if any("already exists" in str(e).lower() for e in errs):
            print(json.dumps({"already_exists": True, "domain": args.domain,
                              "tip": "run get-zone to fetch nameservers"}, indent=2))
            return
        print(json.dumps({"error": "add-zone failed", "errors": errs}, indent=2))
        sys.exit(1)
    z = r["result"]
    print(json.dumps({
        "id": z["id"],
        "name": z["name"],
        "status": z["status"],
        "name_servers": z.get("name_servers", []),
        "next_step": "Set these nameservers at the registrar (e.g., namecheap-skill set-nameservers).",
    }, indent=2))


def cmd_get_zone(args):
    zid = get_zone_id(args.domain)
    r = cf_request("GET", f"/zones/{zid}")
    require_success(r)
    z = r["result"]
    print(json.dumps({
        "name": z["name"],
        "id": z["id"],
        "status": z["status"],
        "name_servers": z.get("name_servers", []),
        "original_name_servers": z.get("original_name_servers", []),
        "activated_on": z.get("activated_on"),
        "modified_on": z.get("modified_on"),
    }, indent=2))


def cmd_delete_zone(args):
    zid = get_zone_id(args.domain)
    r = cf_request("DELETE", f"/zones/{zid}")
    require_success(r)
    print(json.dumps({"deleted": args.domain, "result": r.get("result")}, indent=2))


def cmd_list_records(args):
    zid = get_zone_id(args.domain)
    r = cf_request("GET", f"/zones/{zid}/dns_records?per_page=100")
    require_success(r)
    out = [{
        "id": rec["id"],
        "type": rec["type"],
        "name": rec["name"],
        "content": rec["content"],
        "ttl": rec.get("ttl"),
        "proxied": rec.get("proxied"),
    } for rec in r.get("result", [])]
    print(json.dumps(out, indent=2))


def cmd_add_record(args):
    zid = get_zone_id(args.domain)
    name = args.name if args.name != "@" else args.domain
    body = {
        "type": args.type.upper(),
        "name": name,
        "content": args.value,
        "ttl": args.ttl,
        "proxied": args.proxied,
    }
    r = cf_request("POST", f"/zones/{zid}/dns_records", body)
    require_success(r)
    rec = r["result"]
    print(json.dumps({
        "id": rec["id"], "type": rec["type"], "name": rec["name"],
        "content": rec["content"], "proxied": rec.get("proxied"),
    }, indent=2))


def cmd_update_record(args):
    zid = get_zone_id(args.domain)
    body: dict = {}
    if args.type: body["type"] = args.type.upper()
    if args.name: body["name"] = args.name if args.name != "@" else args.domain
    if args.value: body["content"] = args.value
    if args.ttl is not None: body["ttl"] = args.ttl
    if args.proxied is not None: body["proxied"] = args.proxied
    r = cf_request("PATCH", f"/zones/{zid}/dns_records/{args.record_id}", body)
    require_success(r)
    print(json.dumps(r["result"], indent=2))


def cmd_delete_record(args):
    zid = get_zone_id(args.domain)
    r = cf_request("DELETE", f"/zones/{zid}/dns_records/{args.record_id}")
    require_success(r)
    print(json.dumps({"deleted": args.record_id, "result": r.get("result")}, indent=2))


def cmd_pages_list(args):
    account_id = get_account_id(args.account)
    r = cf_request("GET", f"/accounts/{account_id}/pages/projects")
    require_success(r)
    out = [{"name": p["name"], "subdomain": p.get("subdomain"),
            "domains": p.get("domains", [])} for p in r.get("result", [])]
    print(json.dumps(out, indent=2))


def cmd_pages_add_domain(args):
    account_id = get_account_id(args.account)
    r = cf_request("POST", f"/accounts/{account_id}/pages/projects/{args.project}/domains",
                   {"name": args.domain})
    require_success(r)
    print(json.dumps(r["result"], indent=2))


def cmd_pages_list_domains(args):
    account_id = get_account_id(args.account)
    r = cf_request("GET", f"/accounts/{account_id}/pages/projects/{args.project}/domains")
    require_success(r)
    print(json.dumps(r["result"], indent=2))


# ---------- main ----------

def main():
    p = argparse.ArgumentParser(prog="cloudflare-skill")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami").set_defaults(func=cmd_whoami)
    sub.add_parser("list-zones").set_defaults(func=cmd_list_zones)

    p_add = sub.add_parser("add-zone")
    p_add.add_argument("domain")
    p_add.add_argument("--account", default=None)
    p_add.set_defaults(func=cmd_add_zone)

    p_get = sub.add_parser("get-zone")
    p_get.add_argument("domain")
    p_get.set_defaults(func=cmd_get_zone)

    p_del = sub.add_parser("delete-zone")
    p_del.add_argument("domain")
    p_del.set_defaults(func=cmd_delete_zone)

    p_lr = sub.add_parser("list-records")
    p_lr.add_argument("domain")
    p_lr.set_defaults(func=cmd_list_records)

    p_ar = sub.add_parser("add-record")
    p_ar.add_argument("domain")
    p_ar.add_argument("type")
    p_ar.add_argument("name")
    p_ar.add_argument("value")
    p_ar.add_argument("--proxied", action="store_true", default=False)
    p_ar.add_argument("--ttl", type=int, default=1)  # 1 = automatic
    p_ar.set_defaults(func=cmd_add_record)

    p_ur = sub.add_parser("update-record")
    p_ur.add_argument("domain")
    p_ur.add_argument("record_id")
    p_ur.add_argument("--type")
    p_ur.add_argument("--name")
    p_ur.add_argument("--value")
    p_ur.add_argument("--ttl", type=int, default=None)
    p_ur.add_argument("--proxied", type=lambda x: x.lower() in ("true","1","yes"), default=None)
    p_ur.set_defaults(func=cmd_update_record)

    p_dr = sub.add_parser("delete-record")
    p_dr.add_argument("domain")
    p_dr.add_argument("record_id")
    p_dr.set_defaults(func=cmd_delete_record)

    p_pl = sub.add_parser("pages-list")
    p_pl.add_argument("--account", default=None)
    p_pl.set_defaults(func=cmd_pages_list)

    p_pa = sub.add_parser("pages-add-domain")
    p_pa.add_argument("project")
    p_pa.add_argument("domain")
    p_pa.add_argument("--account", default=None)
    p_pa.set_defaults(func=cmd_pages_add_domain)

    p_pld = sub.add_parser("pages-list-domains")
    p_pld.add_argument("project")
    p_pld.add_argument("--account", default=None)
    p_pld.set_defaults(func=cmd_pages_list_domains)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
