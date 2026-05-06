"""Internal-usage signal: pull friction quotes from Matt's Slack/Conversations vault.

When Matt complains about Linear/Slack/Notion in #standup or in a Claude session,
that's first-party data sharper than any G2 review. This module greps the
ingested conversations for category-relevant pain quotes and surfaces them so the
positioning prompt can use them.

Public API:
    find_internal_friction(category, competitors, *, limit=10)
        -> list of {filename, channel, snippet, matched_terms, score}
"""

from __future__ import annotations

import re
from pathlib import Path

from . import vault


# Generic friction markers in standup-like prose. Tuned for Matt's voice.
FRICTION_MARKERS = [
    "annoying", "broken", "frustrating", "slow", "blocked", "blocker",
    "stuck", "hate", "hates", "ugly", "useless", "doesn't work", "wtf",
    "ridiculous", "missing", "wish", "should be", "why doesn't", "why can't",
    "fucking", "painful", "garbage", "trash", "kludge", "workaround",
    "screwed up", "fucked up", "shitty", "hack",
]

# Per-category synonym terms — broaden category match against actual prose
CATEGORY_TERMS = {
    "pm-software": ["linear", "asana", "jira", "monday", "clickup", "notion", "trello", "shortcut", "kanban", "sprint", "ticket", "card", "issue tracker"],
    "internal-chat": ["slack", "teams", "discord", "mattermost", "twist", "channel", "DM", "thread"],
    "workspace-email": ["gmail", "outlook", "superhuman", "hey.com", "fastmail", "inbox", "email"],
    "calendar": ["google calendar", "gcal", "outlook calendar", "reclaim", "motion", "fantastical", "calendar"],
    "video-meetings": ["zoom", "google meet", "ms teams", "around", "tuple", "whereby", "video call", "huddle"],
    "sms-messaging": ["twilio", "messagebird", "sinch", "plivo", "vonage", "telnyx", "SMS", "text message"],
    "crm": ["salesforce", "hubspot", "attio", "pipedrive", "folk", "clay", "CRM", "pipeline"],
    "file-storage": ["google drive", "dropbox", "box", "onedrive", "icloud", "file sharing"],
    "analytics": ["google analytics", "mixpanel", "amplitude", "posthog", "june", "plausible", "analytics", "tracking"],
    "finance-and-wallets": ["metamask", "rainbow", "coinbase", "phantom", "ynab", "monarch", "copilot money", "wallet"],
    "personal-finance-managers": ["monarch", "copilot money", "ynab", "rocket money", "mint", "personal capital", "budget"],
    "email-marketing": ["mailchimp", "klaviyo", "customer.io", "beehiiv", "resend", "convertkit", "newsletter", "drip"],
    "customer-support": ["zendesk", "intercom", "front", "plain", "helpscout", "gorgias", "ticket", "support"],
    "accounting": ["quickbooks", "xero", "wave", "bench", "freshbooks", "sage", "bookkeeping"],
    "expense-management": ["brex", "ramp", "expensify", "pleo", "navan", "expense report"],
    "hris-payroll": ["gusto", "rippling", "justworks", "deel", "bamboohr", "payroll", "HRIS"],
    "marketing-automation": ["hubspot", "marketo", "activecampaign", "autopilot", "automation"],
    "notes-wiki": ["notion", "confluence", "coda", "obsidian", "slite", "mem.ai", "wiki"],
    "all-in-one-platforms": ["notion", "airtable", "clickup", "coda", "fibery"],
}


def _slack_files() -> list[Path]:
    base = vault.VAULT_ROOT / "Conversations" / "Slack"
    if not base.exists():
        return []
    return list(base.rglob("*.md"))


def _claude_files() -> list[Path]:
    base = vault.VAULT_ROOT / "Conversations" / "Claude"
    if not base.exists():
        return []
    return list(base.glob("*.md"))


def find_internal_friction(category: str, competitors: list[str], *, limit: int = 10) -> list[dict]:
    """Walk Slack + Claude conversation logs; surface lines containing both a
    category/competitor term AND a friction marker. Returns short snippet quotes
    with channel/file context."""
    cat_terms = CATEGORY_TERMS.get(category, []) + [vault.slugify(category).split("-")[0]]
    comp_terms = [c.lower() for c in competitors if c]
    needles = [t.lower() for t in (cat_terms + comp_terms) if t]
    if not needles:
        return []

    results = []
    for path in _slack_files() + _claude_files():
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue
        # Skip files that don't mention any term cheaply
        text_lower = text.lower()
        if not any(n in text_lower for n in needles):
            continue
        # Walk lines, find those with both a term + friction marker
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if len(line) < 30 or len(line) > 400:
                continue
            ll = line.lower()
            term_hit = next((n for n in needles if n in ll), None)
            if not term_hit:
                continue
            friction_hit = next((m for m in FRICTION_MARKERS if m in ll), None)
            if not friction_hit:
                continue
            # Skip pure links or markdown headers
            if line.startswith(("http://", "https://", "#", "```")):
                continue
            channel = path.parent.name if path.parent != path.parent.parent else ""
            results.append({
                "filename": path.name,
                "channel": channel,
                "snippet": line,
                "matched_term": term_hit,
                "matched_friction": friction_hit,
                "score": (3 if term_hit in comp_terms else 1) + (1 if path.parent.name == "standup" else 0),
            })
    results.sort(key=lambda r: r["score"], reverse=True)
    # Dedupe near-identical snippets (first 80 chars)
    seen, out = set(), []
    for r in results:
        key = r["snippet"][:80]
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= limit:
            break
    return out


def render_for_prompt(quotes: list[dict]) -> str:
    """Format internal friction quotes for inclusion in a Claude positioning prompt."""
    if not quotes:
        return "(none surfaced from Matt's Slack/conversations)"
    lines = []
    for q in quotes:
        ch = f"#{q['channel']}" if q.get("channel") else q.get("filename", "?")
        lines.append(f'- ({ch}) "{q["snippet"]}" [matched: {q["matched_term"]} + {q["matched_friction"]}]')
    return "\n".join(lines)
