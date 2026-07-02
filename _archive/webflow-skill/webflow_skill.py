#!/usr/bin/env python3
"""Webflow API skill — sites, custom domains, publish."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import urllib.parse
import urllib.request

API_BASE = "https://api.webflow.com/v2"


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


def wf_request(method: str, path: str, body=None) -> dict:
    token = keychain("webflow-api-token")
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json",
    }
    if body is not None:
        headers["content-type"] = "application/json"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode())
        except Exception:
            err = {"raw": "<unparseable>"}
        print(json.dumps({"error": f"HTTP {e.code}", "detail": err}, indent=2))
        sys.exit(1)


def resolve_site(site_arg: str) -> tuple[str, dict]:
    """Resolve a site argument (short name or ID) to (id, full_record)."""
    r = wf_request("GET", "/sites")
    sites = r.get("sites", [])
    # Direct ID match
    for s in sites:
        if s.get("id") == site_arg:
            return s["id"], s
    # Short name match (e.g., "matteisn" matches displayName/shortName/customDomains)
    arg_low = site_arg.lower()
    for s in sites:
        if (s.get("shortName", "").lower() == arg_low or
            s.get("displayName", "").lower() == arg_low or
            s.get("displayName", "").lower().replace(" ", "") == arg_low):
            return s["id"], s
    # Fallback: substring match on display name
    matches = [s for s in sites if arg_low in s.get("displayName", "").lower()
               or arg_low in s.get("shortName", "").lower()]
    if len(matches) == 1:
        return matches[0]["id"], matches[0]
    if len(matches) > 1:
        print(json.dumps({"error": f"ambiguous site '{site_arg}'",
                          "candidates": [{"id": s["id"], "displayName": s.get("displayName"),
                                           "shortName": s.get("shortName")} for s in matches]}, indent=2))
        sys.exit(1)
    print(json.dumps({"error": f"no site matches '{site_arg}'",
                      "available": [{"id": s["id"], "displayName": s.get("displayName"),
                                      "shortName": s.get("shortName")} for s in sites]}, indent=2))
    sys.exit(1)


# ---------- commands ----------

def cmd_whoami(args):
    """Best-effort 'whoami' — Webflow doesn't have a /user endpoint with bearer-token auth on v2,
    so we just verify by listing sites."""
    r = wf_request("GET", "/sites")
    sites = r.get("sites", [])
    print(json.dumps({"authed": True, "site_count": len(sites)}, indent=2))


def cmd_list_sites(args):
    r = wf_request("GET", "/sites")
    out = []
    for s in r.get("sites", []):
        out.append({
            "id": s.get("id"),
            "displayName": s.get("displayName"),
            "shortName": s.get("shortName"),
            "previewUrl": s.get("previewUrl"),
            "lastPublished": s.get("lastPublished"),
            "customDomains": [d.get("url") for d in s.get("customDomains", [])],
        })
    print(json.dumps(out, indent=2))


def cmd_get_site(args):
    sid, s = resolve_site(args.site)
    r = wf_request("GET", f"/sites/{sid}")
    print(json.dumps(r, indent=2))


def cmd_list_domains(args):
    sid, s = resolve_site(args.site)
    r = wf_request("GET", f"/sites/{sid}/custom_domains")
    domains = r.get("customDomains", []) if isinstance(r, dict) else []
    out = [{"id": d.get("id"), "url": d.get("url"),
            "lastPublished": d.get("lastPublished")} for d in domains]
    print(json.dumps(out, indent=2))


def cmd_find_domain(args):
    """Search across all sites for a given domain."""
    needle = args.domain.lower().lstrip("www.")
    r = wf_request("GET", "/sites")
    matches = []
    for s in r.get("sites", []):
        for d in s.get("customDomains", []):
            url = (d.get("url") or "").lower()
            if needle in url or url.lstrip("www.") == needle:
                matches.append({
                    "site_id": s.get("id"),
                    "site_displayName": s.get("displayName"),
                    "site_shortName": s.get("shortName"),
                    "domain_id": d.get("id"),
                    "domain_url": d.get("url"),
                })
    print(json.dumps({"query": args.domain, "matches": matches}, indent=2))


def _find_domain_id(site_id: str, domain: str) -> str | None:
    """Find the domain object id for a given URL within a site's customDomains."""
    needle = domain.lower()
    r = wf_request("GET", f"/sites/{site_id}/custom_domains")
    domains = r.get("customDomains", []) if isinstance(r, dict) else []
    for d in domains:
        if (d.get("url", "").lower() == needle or
            d.get("url", "").lower() == "www." + needle or
            d.get("url", "").lower() == needle.lstrip("www.")):
            return d.get("id")
    return None


def cmd_remove_domain(args):
    sid, s = resolve_site(args.site)
    dom_id = _find_domain_id(sid, args.domain)
    if not dom_id:
        print(json.dumps({"error": f"domain '{args.domain}' not found on site '{args.site}'",
                          "tip": "use list-domains to see what's bound"}, indent=2))
        sys.exit(1)
    r = wf_request("DELETE", f"/sites/{sid}/custom_domains/{dom_id}")
    print(json.dumps({"removed": args.domain, "site": args.site, "result": r}, indent=2))


def cmd_unbind(args):
    """Find which site has the domain bound + remove it. Convenience for migrations."""
    needle = args.domain.lower()
    r = wf_request("GET", "/sites")
    target = None
    for s in r.get("sites", []):
        for d in s.get("customDomains", []):
            url = (d.get("url") or "").lower()
            # Match the apex (e.g. "matteisn.com") and the www variant
            if url == needle or url == f"www.{needle}" or url.lstrip("www.") == needle:
                target = (s, d)
                break
        if target:
            break
    if not target:
        print(json.dumps({"error": f"no site has '{args.domain}' bound",
                          "tip": "find-domain to confirm"}, indent=2))
        sys.exit(1)
    site, dom = target
    # Remove all variants on this site (the domain may be bound as both apex + www)
    r = wf_request("GET", f"/sites/{site['id']}/custom_domains")
    domains = r.get("customDomains", []) if isinstance(r, dict) else []
    removed = []
    for d in domains:
        url = (d.get("url") or "").lower()
        if url == needle or url == f"www.{needle}" or url.lstrip("www.") == needle:
            wf_request("DELETE", f"/sites/{site['id']}/custom_domains/{d['id']}")
            removed.append(d.get("url"))
    print(json.dumps({
        "site": {"id": site["id"], "displayName": site.get("displayName")},
        "removed_domains": removed,
    }, indent=2))


def cmd_publish(args):
    sid, s = resolve_site(args.site)
    body = {"customDomains": []} if not args.domains else {"customDomains": args.domains}
    if args.publish_to_webflow_subdomain:
        body["publishToWebflowSubdomain"] = True
    r = wf_request("POST", f"/sites/{sid}/publish", body)
    print(json.dumps(r, indent=2))


# ---------- main ----------

def main():
    p = argparse.ArgumentParser(prog="webflow-skill")
    sub = p.add_subparsers(dest="cmd", required=True)

    sub.add_parser("whoami").set_defaults(func=cmd_whoami)
    sub.add_parser("list-sites").set_defaults(func=cmd_list_sites)

    p_gs = sub.add_parser("get-site")
    p_gs.add_argument("site")
    p_gs.set_defaults(func=cmd_get_site)

    p_ld = sub.add_parser("list-domains")
    p_ld.add_argument("site")
    p_ld.set_defaults(func=cmd_list_domains)

    p_fd = sub.add_parser("find-domain")
    p_fd.add_argument("domain")
    p_fd.set_defaults(func=cmd_find_domain)

    p_rd = sub.add_parser("remove-domain")
    p_rd.add_argument("site")
    p_rd.add_argument("domain")
    p_rd.set_defaults(func=cmd_remove_domain)

    p_ub = sub.add_parser("unbind")
    p_ub.add_argument("domain")
    p_ub.set_defaults(func=cmd_unbind)

    p_pub = sub.add_parser("publish")
    p_pub.add_argument("site")
    p_pub.add_argument("--domains", nargs="*", default=None)
    p_pub.add_argument("--publish-to-webflow-subdomain", action="store_true", default=False)
    p_pub.set_defaults(func=cmd_publish)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
