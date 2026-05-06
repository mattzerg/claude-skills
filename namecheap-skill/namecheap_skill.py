#!/usr/bin/env python3
"""Namecheap API skill — manage domains + DNS via Namecheap's public REST API.

Setup: see SKILL.md. Credentials stored in macOS Keychain via `security` cli.
"""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

NS = "http://api.namecheap.com/xml.response"


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


def api_url(sandbox: bool = False) -> str:
    return "https://api.sandbox.namecheap.com/xml.response" if sandbox else "https://api.namecheap.com/xml.response"


def call(command: str, params: dict, sandbox: bool = False) -> ET.Element:
    user = keychain("namecheap-api-user")
    api_key = keychain("namecheap-api-key")
    client_ip = keychain("namecheap-api-ip")

    body = {
        "ApiUser": user,
        "ApiKey": api_key,
        "UserName": user,
        "ClientIp": client_ip,
        "Command": command,
    }
    body.update(params)

    data = urllib.parse.urlencode(body).encode()
    req = urllib.request.Request(api_url(sandbox), data=data, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
    except urllib.error.HTTPError as e:
        print(json.dumps({"error": f"HTTP {e.code}", "body": e.read().decode()[:500]}, indent=2))
        sys.exit(1)

    root = ET.fromstring(raw)
    status = root.attrib.get("Status", "")
    if status != "OK":
        # extract error nodes
        errors = []
        for err in root.iter():
            if err.tag.endswith("Error") or err.tag.endswith("}Error"):
                errors.append({"number": err.attrib.get("Number", ""), "text": err.text or ""})
        print(json.dumps({
            "error": "API returned non-OK",
            "status": status,
            "errors": errors,
            "command": command,
        }, indent=2))
        sys.exit(1)
    return root


def strip_ns(tag: str) -> str:
    """Strip XML namespace: '{http://...}TagName' → 'TagName'"""
    return tag.split("}", 1)[-1] if "}" in tag else tag


def find_first(root: ET.Element, tag: str) -> ET.Element | None:
    for e in root.iter():
        if strip_ns(e.tag) == tag:
            return e
    return None


def find_all(root: ET.Element, tag: str) -> list[ET.Element]:
    return [e for e in root.iter() if strip_ns(e.tag) == tag]


# ---------- commands ----------

def cmd_whoami(args):
    root = call("namecheap.users.getBalances", {}, sandbox=args.sandbox)
    res = find_first(root, "UserGetBalancesResult")
    out = {
        "user": keychain("namecheap-api-user"),
        "client_ip": keychain("namecheap-api-ip"),
        "balance": res.attrib if res is not None else None,
        "endpoint": api_url(args.sandbox),
    }
    print(json.dumps(out, indent=2))


def cmd_list_domains(args):
    root = call("namecheap.domains.getList", {"PageSize": 100}, sandbox=args.sandbox)
    domains = []
    for d in find_all(root, "Domain"):
        domains.append({
            "name": d.attrib.get("Name", ""),
            "id": d.attrib.get("ID", ""),
            "expires": d.attrib.get("Expires", ""),
            "auto_renew": d.attrib.get("AutoRenew", ""),
            "is_locked": d.attrib.get("IsLocked", ""),
        })
    print(json.dumps(domains, indent=2))


def split_sld_tld(domain: str) -> tuple[str, str]:
    """Split 'matteisn.com' → ('matteisn', 'com'). Handles e.g. 'vang.capital'."""
    parts = domain.split(".")
    if len(parts) < 2:
        print(json.dumps({"error": f"invalid domain: {domain}"}, indent=2)); sys.exit(1)
    sld = ".".join(parts[:-1])
    tld = parts[-1]
    return sld, tld


def cmd_get_nameservers(args):
    sld, tld = split_sld_tld(args.domain)
    root = call("namecheap.domains.dns.getList", {"SLD": sld, "TLD": tld}, sandbox=args.sandbox)
    res = find_first(root, "DomainDNSGetListResult")
    out = {
        "domain": args.domain,
        "is_using_our_dns": res.attrib.get("IsUsingOurDNS", "") if res is not None else "",
        "is_premium_dns": res.attrib.get("IsPremiumDNS", "") if res is not None else "",
        "nameservers": [n.text for n in find_all(root, "Nameserver")],
    }
    print(json.dumps(out, indent=2))


def cmd_set_nameservers(args):
    sld, tld = split_sld_tld(args.domain)
    nameservers = ",".join(args.nameservers)
    root = call("namecheap.domains.dns.setCustom",
                {"SLD": sld, "TLD": tld, "Nameservers": nameservers},
                sandbox=args.sandbox)
    res = find_first(root, "DomainDNSSetCustomResult")
    out = {
        "domain": args.domain,
        "nameservers_set": args.nameservers,
        "updated": res.attrib.get("Updated", "") if res is not None else "",
    }
    print(json.dumps(out, indent=2))


def cmd_set_default_nameservers(args):
    sld, tld = split_sld_tld(args.domain)
    root = call("namecheap.domains.dns.setDefault", {"SLD": sld, "TLD": tld}, sandbox=args.sandbox)
    res = find_first(root, "DomainDNSSetDefaultResult")
    out = {
        "domain": args.domain,
        "reset_to_default": True,
        "updated": res.attrib.get("Updated", "") if res is not None else "",
    }
    print(json.dumps(out, indent=2))


def cmd_get_records(args):
    sld, tld = split_sld_tld(args.domain)
    root = call("namecheap.domains.dns.getHosts", {"SLD": sld, "TLD": tld}, sandbox=args.sandbox)
    records = []
    for h in find_all(root, "host"):
        records.append({
            "host": h.attrib.get("Name", ""),
            "type": h.attrib.get("Type", ""),
            "value": h.attrib.get("Address", ""),
            "ttl": h.attrib.get("TTL", ""),
            "mx_pref": h.attrib.get("MXPref", "") if h.attrib.get("Type") == "MX" else None,
            "host_id": h.attrib.get("HostId", ""),
            "associated_app_title": h.attrib.get("AssociatedAppTitle", ""),
        })
    print(json.dumps({"domain": args.domain, "records": records}, indent=2))


def cmd_set_records(args):
    """Replace all host records for a domain with the contents of <records.json>.

    records.json shape:
      [
        {"type": "CNAME", "host": "www", "value": "matteisn.pages.dev", "ttl": 1800},
        {"type": "ALIAS", "host": "@", "value": "matteisn.pages.dev", "ttl": 1800}
      ]

    NB: Namecheap's setHosts replaces ALL records. To add one record, first
    get-records, append the new one to the existing list, then set-records.
    """
    sld, tld = split_sld_tld(args.domain)
    with open(args.file) as f:
        records = json.load(f)
    if not isinstance(records, list):
        print(json.dumps({"error": "records file must be a JSON array"}, indent=2)); sys.exit(1)

    params = {"SLD": sld, "TLD": tld}
    for i, rec in enumerate(records, start=1):
        params[f"HostName{i}"] = rec.get("host", "@")
        params[f"RecordType{i}"] = rec.get("type", "A")
        params[f"Address{i}"] = rec.get("value", "")
        params[f"TTL{i}"] = str(rec.get("ttl", 1800))
        if rec.get("type", "").upper() == "MX":
            params[f"MXPref{i}"] = str(rec.get("mx_pref", 10))
            params[f"EmailType"] = "MX"

    root = call("namecheap.domains.dns.setHosts", params, sandbox=args.sandbox)
    res = find_first(root, "DomainDNSSetHostsResult")
    print(json.dumps({
        "domain": args.domain,
        "records_set": len(records),
        "is_success": res.attrib.get("IsSuccess", "") if res is not None else "",
    }, indent=2))


# ---------- main ----------

def main():
    p = argparse.ArgumentParser(prog="namecheap-skill")
    p.add_argument("--sandbox", action="store_true", help="use Namecheap sandbox API")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami").set_defaults(func=cmd_whoami)
    sub.add_parser("list-domains").set_defaults(func=cmd_list_domains)

    p_gn = sub.add_parser("get-nameservers")
    p_gn.add_argument("domain")
    p_gn.set_defaults(func=cmd_get_nameservers)

    p_sn = sub.add_parser("set-nameservers")
    p_sn.add_argument("domain")
    p_sn.add_argument("nameservers", nargs="+")
    p_sn.set_defaults(func=cmd_set_nameservers)

    p_dn = sub.add_parser("set-default-nameservers")
    p_dn.add_argument("domain")
    p_dn.set_defaults(func=cmd_set_default_nameservers)

    p_gr = sub.add_parser("get-records")
    p_gr.add_argument("domain")
    p_gr.set_defaults(func=cmd_get_records)

    p_sr = sub.add_parser("set-records")
    p_sr.add_argument("domain")
    p_sr.add_argument("file", help="path to JSON file with record list")
    p_sr.set_defaults(func=cmd_set_records)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
