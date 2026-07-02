#!/usr/bin/env python3
"""ZergGuard Phase 2 — scam scanner. Paste text/url/phone/sender, get verdict."""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

LIB = Path.home() / ".config" / "zerg-guard" / "lib"
sys.path.insert(0, str(LIB))

from ioc import (  # noqa: E402
    KNOWN_BAD_DOMAINS,
    SUSPICIOUS_TLDS,
    url_is_known_bad,
    url_has_suspicious_tld,
)

# Urgency / fear keywords commonly used in phishing.
URGENCY_KEYWORDS = [
    "locked", "suspended", "verify immediately", "verify your", "click here now",
    "within 24 hours", "within 48 hours", "act now", "expires today",
    "unauthorized", "fraud detected", "your account will be",
    "final notice", "last warning", "immediate action required",
]

# Refund-scam phrasing.
REFUND_KEYWORDS = [
    "you have been charged", "you've been charged", "to dispute call",
    "to cancel call", "refund department", "geek squad", "norton renewal",
    "mcafee renewal", "your subscription has been renewed",
]

# Brand names commonly impersonated.
SPOOFED_BRANDS = [
    "apple", "icloud", "paypal", "amazon", "microsoft", "google",
    "chase", "bank of america", "wells fargo", "venmo", "zelle",
    "fedex", "ups", "usps", "dhl", "irs", "social security",
    "netflix", "spotify", "stripe", "coinbase",
]

BRAND_OFFICIAL_DOMAINS = {
    "apple": ["apple.com", "icloud.com"],
    "icloud": ["apple.com", "icloud.com"],
    "paypal": ["paypal.com"],
    "amazon": ["amazon.com"],
    "microsoft": ["microsoft.com", "live.com", "outlook.com"],
    "google": ["google.com", "gmail.com"],
    "chase": ["chase.com"],
    "venmo": ["venmo.com"],
    "fedex": ["fedex.com"],
    "ups": ["ups.com"],
    "usps": ["usps.com"],
    "dhl": ["dhl.com"],
    "irs": ["irs.gov"],
    "netflix": ["netflix.com"],
    "spotify": ["spotify.com"],
    "stripe": ["stripe.com"],
    "coinbase": ["coinbase.com"],
}


@dataclass
class Reason:
    weight: int  # severity points
    text: str


@dataclass
class Verdict:
    score: int = 0
    reasons: list[Reason] = field(default_factory=list)

    @property
    def label(self) -> str:
        if self.score >= 7:
            return "PHISH"
        if self.score >= 3:
            return "SUSPICIOUS"
        return "SAFE"

    @property
    def action(self) -> str:
        if self.label == "PHISH":
            return "Block sender. Do not click. Do not reply. Delete."
        if self.label == "SUSPICIOUS":
            return "Be cautious. Verify via a known-good channel (call the company directly using the phone number on your card / their official site). Do not click links."
        return "Looks fine, but ZergGuard can't catch everything. Use judgment."


URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
EMAIL_RE = re.compile(r"<?([\w.+-]+@[\w.-]+\.[a-z]{2,})>?", re.IGNORECASE)
NAME_EMAIL_RE = re.compile(r"^\s*([^<]+?)\s*<([^>]+@[\w.-]+)>\s*$")


def check_text(text: str, verdict: Verdict) -> None:
    lower = text.lower()
    for kw in URGENCY_KEYWORDS:
        if kw in lower:
            verdict.score += 2
            verdict.reasons.append(Reason(2, f'Urgency keyword: "{kw}"'))
            break  # one urgency hit is enough; don't pile on
    for kw in REFUND_KEYWORDS:
        if kw in lower:
            verdict.score += 3
            verdict.reasons.append(Reason(3, f'Refund-scam phrasing: "{kw}"'))
            break
    # All-caps frequency
    if len(text) > 30:
        caps_ratio = sum(1 for c in text if c.isupper()) / max(1, sum(1 for c in text if c.isalpha()))
        if caps_ratio > 0.4:
            verdict.score += 1
            verdict.reasons.append(Reason(1, "High proportion of ALL CAPS — common in scams"))


def check_url(url: str, verdict: Verdict) -> None:
    bad = url_is_known_bad(url)
    if bad:
        verdict.score += 8
        verdict.reasons.append(Reason(8, f"URL contains known-bad domain `{bad}` from ZergGuard IOC list"))
        return  # Don't pile on; this alone is dispositive
    tld = url_has_suspicious_tld(url)
    if tld:
        verdict.score += 3
        verdict.reasons.append(Reason(3, f"Suspicious TLD `{tld}` — cheap/abuse-heavy registration"))
    parsed = urlparse(url if "://" in url else "http://" + url)
    host = (parsed.hostname or "").lower()
    if re.match(r"^\d{1,3}(\.\d{1,3}){3}$", host):
        verdict.score += 4
        verdict.reasons.append(Reason(4, f"URL uses IP address `{host}` instead of domain — atypical for legitimate services"))
    if re.search(r"[a-zA-Z0-9+/]{30,}={0,2}", url):
        verdict.score += 2
        verdict.reasons.append(Reason(2, "URL contains long base64-like blob — payload obfuscation pattern"))
    # Lookalike: brand-name + dash + word
    for brand in SPOOFED_BRANDS:
        if brand in host and host not in BRAND_OFFICIAL_DOMAINS.get(brand, [brand + ".com"]):
            # e.g. apple-secure.click
            verdict.score += 4
            verdict.reasons.append(
                Reason(4, f'Domain "{host}" contains brand "{brand}" but is NOT the official domain ({", ".join(BRAND_OFFICIAL_DOMAINS.get(brand, [brand + ".com"]))})')
            )
            break


def check_phone(phone: str, verdict: Verdict) -> None:
    digits = re.sub(r"\D", "", phone)
    # Letters in phone number (alphanumeric vanity) — uncommon for legit cold calls
    if re.search(r"[A-Za-z]", phone):
        verdict.score += 2
        verdict.reasons.append(Reason(2, "Phone number contains letters (vanity dial) — atypical for unsolicited contact"))
    # Sequential / repeated digits
    if re.search(r"(\d)\1{4,}", digits):
        verdict.score += 2
        verdict.reasons.append(Reason(2, "Phone has 5+ repeated digits — common spoof pattern"))
    if re.search(r"01234|12345|23456|34567|45678|56789", digits):
        verdict.score += 2
        verdict.reasons.append(Reason(2, "Phone has sequential digits — common spoof pattern"))


def check_sender(sender: str, verdict: Verdict) -> None:
    # Parse "Display Name <email@domain>"
    m = NAME_EMAIL_RE.match(sender)
    display, email = (m.group(1).strip(), m.group(2).strip()) if m else (sender.strip(), "")
    display_lower = display.lower()
    # 1) Brand name in display but non-brand domain
    if email:
        domain = email.split("@")[-1].lower()
        for brand in SPOOFED_BRANDS:
            if brand in display_lower:
                official = BRAND_OFFICIAL_DOMAINS.get(brand, [brand + ".com"])
                if not any(domain.endswith(d) for d in official):
                    verdict.score += 5
                    verdict.reasons.append(
                        Reason(5, f'Display "{display}" claims to be {brand} but email domain "{domain}" is not official ({", ".join(official)})')
                    )
                    break
    # 2) Word-order spoof ("Inc Apple" vs "Apple Inc.")
    for brand in SPOOFED_BRANDS:
        if brand in display_lower:
            # Check if "Inc Brand" or "Brand Inc" reversed
            if re.search(rf"\binc\s+{brand}\b", display_lower):
                verdict.score += 4
                verdict.reasons.append(
                    Reason(4, f'Display "{display}" reverses "Inc" — "{brand.title()} Inc" is the legitimate company name')
                )
                break


def looks_like_url(s: str) -> bool:
    return bool(URL_RE.search(s)) or s.startswith(("http://", "https://", "www."))


def looks_like_phone(s: str) -> bool:
    digits = re.sub(r"\D", "", s)
    return len(digits) >= 7 and re.match(r"^[+\d\s().A-Za-z-]+$", s.strip()) is not None and not looks_like_url(s)


def looks_like_sender(s: str) -> bool:
    return bool(NAME_EMAIL_RE.match(s)) or bool(EMAIL_RE.search(s))


def auto_check(text: str, verdict: Verdict) -> None:
    """Run all applicable checks against a single text blob."""
    # Extract URLs and check each
    for url in URL_RE.findall(text):
        check_url(url, verdict)
    # If sender-shaped, run sender check
    if looks_like_sender(text):
        check_sender(text, verdict)
    # Always check text body for keywords
    check_text(text, verdict)


def render(verdict: Verdict) -> str:
    lines = [
        f"VERDICT: {verdict.label}",
        f"SCORE:   {verdict.score}/10+",
    ]
    if verdict.reasons:
        lines.append("REASONS:")
        for r in sorted(verdict.reasons, key=lambda x: -x.weight):
            lines.append(f"  - {r.text}")
    else:
        lines.append("REASONS:")
        lines.append("  - No red flags matched ZergGuard's v1 heuristics.")
    lines.append(f"ACTION:  {verdict.action}")
    return "\n".join(lines)


def vt_enrich(url: str, verdict: Verdict) -> None:
    """If VT_API_KEY env is set, upgrade verdict using VirusTotal stats."""
    try:
        sys.path.insert(0, str(Path.home() / ".config" / "zerg-guard" / "lib"))
        from virustotal import lookup_url, upgrade_verdict  # noqa: E402
    except Exception:
        return
    stats = lookup_url(url)
    new_score, reason = upgrade_verdict(stats, verdict.score)
    if reason:
        verdict.score = new_score
        verdict.reasons.append(Reason(new_score - verdict.score + 1, reason))


def main(argv: list[str]) -> int:
    ap = argparse.ArgumentParser(prog="zergguard-scam-check")
    ap.add_argument("input", nargs="?", help="Text/URL/sender to check; reads stdin if omitted")
    ap.add_argument("--url", help="Treat input as URL")
    ap.add_argument("--phone", help="Treat input as phone number")
    ap.add_argument("--sender", help="Treat input as sender 'Name <email>'")
    ap.add_argument("--vt", action="store_true", help="Also query VirusTotal (needs VT_API_KEY env)")
    args = ap.parse_args(argv)

    verdict = Verdict()

    if args.url:
        check_url(args.url, verdict)
        if args.vt:
            vt_enrich(args.url, verdict)
    elif args.phone:
        check_phone(args.phone, verdict)
    elif args.sender:
        check_sender(args.sender, verdict)
    else:
        text = args.input
        if not text:
            text = sys.stdin.read().strip()
        if not text:
            print("(no input — pass text as arg or pipe to stdin)", file=sys.stderr)
            return 1
        # Auto-classify
        if looks_like_phone(text):
            check_phone(text, verdict)
        else:
            auto_check(text, verdict)

    print(render(verdict))
    # Exit code reflects severity for shell scripting
    if verdict.label == "PHISH":
        return 2
    if verdict.label == "SUSPICIOUS":
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
