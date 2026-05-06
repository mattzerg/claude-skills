#!/usr/bin/env python3
"""
Daily morning routine for Matt's Zerg vault.

Does three things:
1. Creates today's daily note (if it doesn't exist)
2. Ensures the Slack bridge is running
3. Prints a summary of what to fill in

Usage: python3 ~/.claude/skills/daily_start.py
       python3 ~/.claude/skills/daily_start.py --standup   (post standup after filling it in)
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

VAULT = Path("/Users/mattheweisner/Library/Mobile Documents/iCloud~md~obsidian/Documents/Zerg/MattZerg")
SLACK_BRIDGE = Path.home() / ".claude/skills/slack-skill/slack_bridge.py"
GMAIL_SKILL = Path.home() / ".claude/skills/gmail-skill/gmail_skill.py"


def today_info():
    now = datetime.now()
    year = now.strftime("%Y")
    month_num = now.strftime("%m")
    month_name = now.strftime("%b")        # Apr
    month_full = now.strftime("%B")        # April
    day_name = now.strftime("%A")          # Wednesday
    day_num = now.strftime("%d")           # 30
    iso_date = now.strftime("%Y-%m-%d")

    # Week number (ISO)
    week_num = now.strftime("%W").zfill(2)

    # Quarter
    quarter = (now.month - 1) // 3 + 1

    # Paths following vault convention: Daily/YYYY/qQ/MM-MMM/wWW/D-dddd.md
    daily_dir = VAULT / "Daily" / year / f"q{quarter}" / f"{month_num}-{month_name}" / f"w{week_num}"
    daily_file = daily_dir / f"{day_num}-{day_name}.md"

    # Navigation links (resolved)
    week_file = daily_dir / f"w{week_num}-weekly.md"
    month_file = VAULT / "Daily" / year / f"q{quarter}" / f"{month_num}-{month_name}" / f"{month_name}-monthly.md"
    quarter_file = VAULT / "Daily" / year / f"q{quarter}" / f"q{quarter}-quarterly.md"
    annual_file = VAULT / "Daily" / year / f"{str(now.year)[2:]}-annual.md"

    # Yesterday
    yesterday = now - timedelta(days=1)
    yq = (yesterday.month - 1) // 3 + 1
    yw = yesterday.strftime("%W").zfill(2)
    yesterday_path = (f"Daily/{yesterday.strftime('%Y')}/q{yq}/"
                      f"{yesterday.strftime('%m-%b')}/w{yw}/"
                      f"{yesterday.strftime('%d-%A')}")

    # Tomorrow
    tomorrow = now + timedelta(days=1)
    tq = (tomorrow.month - 1) // 3 + 1
    tw = tomorrow.strftime("%W").zfill(2)
    tomorrow_path = (f"Daily/{tomorrow.strftime('%Y')}/q{tq}/"
                     f"{tomorrow.strftime('%m-%b')}/w{tw}/"
                     f"{tomorrow.strftime('%d-%A')}")

    return {
        "iso_date": iso_date,
        "year": year,
        "month_num": month_num,
        "month_name": month_name,
        "month_full": month_full,
        "day_name": day_name,
        "day_num": day_num,
        "week_num": week_num,
        "quarter": quarter,
        "daily_dir": daily_dir,
        "daily_file": daily_file,
        "week_path": f"Daily/{year}/q{quarter}/{month_num}-{month_name}/w{week_num}/w{week_num}-weekly",
        "month_path": f"Daily/{year}/q{quarter}/{month_num}-{month_name}/{month_name}-monthly",
        "quarter_path": f"Daily/{year}/q{quarter}/q{quarter}-quarterly",
        "annual_path": f"Daily/{year}/{str(now.year)[2:]}-annual",
        "yesterday_path": yesterday_path,
        "tomorrow_path": tomorrow_path,
    }


def create_daily_note(t):
    """Create today's daily note from template."""
    daily_file = t["daily_file"]

    if daily_file.exists():
        print(f"Daily note already exists: {daily_file.name}")
        return False

    t["daily_dir"].mkdir(parents=True, exist_ok=True)

    content = f"""# {t['iso_date']} - {t['day_name']}

## Navigation

[[{t['week_path']}|Week {t['week_num']}]] • [[{t['month_path']}|{t['month_full']}]] • [[{t['quarter_path']}|Q{t['quarter']}]] • [[{t['annual_path']}|{t['year']}]]

### #todo

- [ ]

### Active Projects

<!-- Links to active projects with current phase/status. Include next step. Details live in project docs. -->
<!-- - [[path|Project]] - status (phase)
\t- Next: immediate next action -->

### Writing

<!-- In-progress writing projects. -->

## Standup

**today**
-

**yesterday**
-

**blocked**
-

## #log

<!-- Tag entries with #log for aggregation -->

## Daily Review

### What went well? #win

### What could improve? #improve

### Gratitude #gratitude

### Tomorrow's Priority

## Quick Links

[[{t['yesterday_path']}|← Yesterday]] | [[{t['tomorrow_path']}|Tomorrow →]]

#daily
"""
    daily_file.write_text(content)
    print(f"Created: {daily_file}")
    return True


def check_slack_bridge():
    """Ensure Slack bridge is running, start it if not."""
    result = subprocess.run(
        ["pgrep", "-f", "slack_bridge.py"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        pid = result.stdout.strip().split()[0]
        print(f"Slack bridge running (PID {pid})")
        return True

    print("Slack bridge not running — starting...")
    workdir = str(VAULT)
    subprocess.Popen(
        [sys.executable, str(SLACK_BRIDGE), "--auto", "--workdir", workdir],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    import time; time.sleep(2)
    result = subprocess.run(["pgrep", "-f", "slack_bridge.py"], capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Slack bridge started (PID {result.stdout.strip().split()[0]})")
        return True
    else:
        print("WARNING: Slack bridge failed to start")
        return False


def check_gmail(t):
    """Check both Gmail accounts and append inbox summary to today's daily note."""
    if not GMAIL_SKILL.exists():
        return

    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y/%m/%d")
    accounts = [
        ("matteisn@gmail.com", "Personal"),
        ("matthew@zergai.com", "Zerg"),
    ]

    all_sections = []

    for account, label in accounts:
        print(f"\nChecking Gmail ({account})...")
        try:
            result = subprocess.run(
                [sys.executable, str(GMAIL_SKILL), "search",
                 f"after:{yesterday} is:unread -category:promotions -category:social",
                 "--account", account, "--max-results", "15"],
                capture_output=True, text=True, timeout=30
            )
            if result.returncode != 0 or not result.stdout.strip():
                print(f"  No results or error")
                continue

            data = json.loads(result.stdout)
            emails = data if isinstance(data, list) else data.get("threads", [])

            if not emails:
                print(f"  No unread emails")
                all_sections.append(f"**{label} ({account}):** No unread emails")
                continue

            print(f"  {len(emails)} unread:")
            lines = [f"**{label} ({account}):** {len(emails)} unread"]
            for e in emails[:10]:
                subj = (e.get("subject") or e.get("snippet") or "")[:80].strip()
                sender = e.get("from", e.get("sender", ""))[:40]
                print(f"    • {subj}")
                lines.append(f"- {subj}" + (f" _(from {sender})_" if sender else ""))
            all_sections.append("\n".join(lines))

        except Exception as e:
            print(f"  Skipped ({e})")

    # Append inbox summary to the daily note
    if all_sections and t["daily_file"].exists():
        summary_block = "\n\n### Inbox\n\n" + "\n\n".join(all_sections) + "\n"
        existing = t["daily_file"].read_text()
        if "### Inbox" not in existing:
            # Insert after #log header
            if "## #log" in existing:
                existing = existing.replace("## #log", "## #log" + summary_block, 1)
            else:
                existing += summary_block
            t["daily_file"].write_text(existing)
            print("\nInbox summary written to daily note.")


def check_calendar(t):
    """Fetch today's calendar events and prepend to daily note."""
    gcal = Path.home() / ".claude/skills/gcal-skill/gcal_skill.py"
    if not gcal.exists():
        return

    accounts = ["matthew@zergai.com", "matteisn@gmail.com"]
    print("\nChecking Google Calendar...")
    all_events = []

    for account in accounts:
        try:
            result = subprocess.run(
                [sys.executable, str(gcal), "today", "--account", account],
                capture_output=True, text=True, timeout=20
            )
            if result.returncode != 0 or not result.stdout.strip():
                continue
            data = json.loads(result.stdout)
            events = data.get("events", [])
            for e in events:
                e["_account"] = account
            all_events.extend(events)
        except Exception as e:
            print(f"  Calendar ({account}) skipped: {e}")

    # Deduplicate by title+start
    seen = set()
    unique_events = []
    for e in all_events:
        key = (e.get("title"), e.get("start"))
        if key not in seen:
            seen.add(key)
            unique_events.append(e)

    unique_events.sort(key=lambda e: e.get("start", ""))

    if not unique_events:
        print("  No events today")
        return

    print(f"  {len(unique_events)} event(s) today:")
    lines = [f"**Today's Calendar:** {len(unique_events)} event(s)", ""]
    for e in unique_events:
        title = e.get("title", "Untitled")
        start = e.get("start", "")[-5:] if e.get("start") else ""
        end = e.get("end", "")
        loc = e.get("location", "")
        attendees = [a["email"].split("@")[0] for a in (e.get("attendees") or [])
                     if a.get("email") != "matthew@zergai.com" and a.get("email") != "matteisn@gmail.com"]
        detail = f"{start}–{end}"
        if loc:
            detail += f" · {loc[:40]}"
        if attendees:
            detail += f" · with {', '.join(attendees[:3])}"
        print(f"    • {start} {title}")
        lines.append(f"- **{title}** {detail}")

    if t["daily_file"].exists():
        block = "### Schedule\n\n" + "\n".join(lines) + "\n\n"
        existing = t["daily_file"].read_text()
        if "### Schedule" not in existing:
            # Insert at top, right after navigation
            existing = existing.replace("### #todo", block + "### #todo", 1)
            t["daily_file"].write_text(existing)
            print("  Schedule written to daily note.")


def check_zergboard(t):
    """Fetch assigned Zergboard cards and append to daily note."""
    zb = Path.home() / ".claude/skills/zergboard-skill/zergboard_skill.py"
    if not zb.exists():
        return

    print("\nChecking Zergboard...")
    try:
        result = subprocess.run(
            [sys.executable, str(zb), "my-cards", "--limit", "20"],
            capture_output=True, text=True, timeout=20
        )
        if result.returncode != 0 or not result.stdout.strip():
            print("  No cards or error")
            return

        data = json.loads(result.stdout)
        cards = data.get("cards", [])
        if not cards:
            print("  No assigned cards")
            return

        # Sort: in-progress first, then by due date
        priority_order = {"urgent": 0, "high": 1, "medium": 2, "low": 3, "none": 4}
        in_progress = [c for c in cards if "progress" in (c.get("column_name") or "").lower()]
        todo = [c for c in cards if "progress" not in (c.get("column_name") or "").lower()]
        sorted_cards = in_progress + todo

        print(f"  {len(cards)} assigned cards:")
        lines = [f"**Zergboard:** {len(cards)} assigned"]
        for c in sorted_cards[:10]:
            title = c.get("title", "Untitled")
            board = c.get("board_name", "")
            col = c.get("column_name", "")
            eid = c.get("external_id", "")
            due = c.get("due_at", "")[:10] if c.get("due_at") else ""
            pri = c.get("priority", "")
            flag = "🔴" if pri == "urgent" else "🟠" if pri == "high" else "🟡" if pri == "medium" else "⚪"
            due_str = f" _(due {due})_" if due else ""
            print(f"    {flag} [{eid}] {title}")
            lines.append(f"- {flag} **{eid}** {title} [{col}]{due_str}")

        # Write to daily note under a Zergboard section
        if t["daily_file"].exists():
            block = "\n\n### Zergboard\n\n" + "\n".join(lines) + "\n"
            existing = t["daily_file"].read_text()
            if "### Zergboard" not in existing:
                if "## #log" in existing:
                    existing = existing.replace("## #log", "## #log" + block, 1)
                else:
                    existing += block
                t["daily_file"].write_text(existing)
                print("  Zergboard cards written to daily note.")

    except Exception as e:
        print(f"  Zergboard check skipped ({e})")


def check_slack_mentions(t):
    """Scan key Slack channels for recent mentions and unreplied threads."""
    slack = Path.home() / ".claude/skills/slack-skill/slack_skill.py"
    if not slack.exists():
        return

    MATT_USER_ID = "U0AFSSPNB1N"
    CHANNELS_TO_SCAN = ["#standup", "#general", "#dev", "#marketing", "#product"]
    cutoff = (datetime.now() - timedelta(hours=18)).strftime("%Y-%m-%d")

    print("\nChecking Slack for mentions...")
    mentions = []

    for channel in CHANNELS_TO_SCAN:
        try:
            result = subprocess.run(
                [sys.executable, str(slack), "read", channel, "--limit", "30"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode != 0 or not result.stdout.strip():
                continue
            data = json.loads(result.stdout)
            messages = data.get("messages", [])
            for msg in messages:
                text = msg.get("text", "")
                if MATT_USER_ID in text or "@Matt" in text or "@matthew" in text.lower():
                    ts_date = msg.get("time", "")[:10]
                    if ts_date >= cutoff:
                        user = msg.get("user", "Someone")
                        snippet = text.replace(f"<@{MATT_USER_ID}>", "@Matt")[:80]
                        mentions.append({
                            "channel": channel,
                            "user": user,
                            "text": snippet,
                            "ts": msg.get("ts", ""),
                        })
        except Exception:
            continue

    if not mentions:
        print("  No recent mentions")
        return

    print(f"  {len(mentions)} mention(s):")
    lines = [f"**Slack mentions:** {len(mentions)}"]
    for m in mentions[:10]:
        print(f"    • {m['channel']} — {m['text'][:60]}")
        lines.append(f"- {m['channel']} _{m['user']}_: {m['text']}")

    if t["daily_file"].exists():
        block = "\n\n### Slack Mentions\n\n" + "\n".join(lines) + "\n"
        existing = t["daily_file"].read_text()
        if "### Slack Mentions" not in existing:
            if "## #log" in existing:
                existing = existing.replace("## #log", "## #log" + block, 1)
            else:
                existing += block
            t["daily_file"].write_text(existing)
            print("  Slack mentions written to daily note.")


def post_standup(t):
    """Read today's standup section and post to Slack #standup."""
    daily_file = t["daily_file"]
    if not daily_file.exists():
        print("No daily note found.")
        return

    content = daily_file.read_text()

    # Extract standup section
    import re
    m = re.search(r"## Standup\s*\n(.*?)(?=\n## |\Z)", content, re.DOTALL)
    if not m:
        print("No Standup section found in today's note.")
        return

    standup_text = m.group(1).strip()
    if not standup_text or standup_text == "**today**\n-\n\n**yesterday**\n-\n\n**blocked**\n-":
        print("Standup section is empty — fill it in first.")
        return

    print(f"Posting standup:\n{standup_text}\n")
    slack_skill = Path.home() / ".claude/skills/slack-skill/slack_skill.py"
    if slack_skill.exists():
        result = subprocess.run(
            [sys.executable, str(slack_skill), "send", "#standup", standup_text],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print("Posted to #standup")
        else:
            print(f"Failed: {result.stderr[:200]}")
    else:
        print("Slack skill not found.")


def main():
    parser = argparse.ArgumentParser(description="Daily morning startup routine")
    parser.add_argument("--standup", action="store_true", help="Post standup to Slack")
    parser.add_argument("--no-gmail", action="store_true", help="Skip Gmail check")
    args = parser.parse_args()

    t = today_info()
    print(f"\n{'='*50}")
    print(f"  Good morning — {t['day_name']}, {t['month_full']} {int(t['day_num'])}")
    print(f"{'='*50}\n")

    if args.standup:
        post_standup(t)
        return

    # 1. Create daily note
    created = create_daily_note(t)

    # 2. Slack bridge
    print()
    check_slack_bridge()

    # 3. Gmail
    if not args.no_gmail:
        check_gmail(t)

    # 4. Google Calendar
    check_calendar(t)

    # 5. Zergboard
    check_zergboard(t)

    # 6. Slack mentions
    check_slack_mentions(t)

    # 7. Summary
    print(f"""
{'='*50}
Daily note: {t['daily_file'].relative_to(VAULT)}

Next steps:
  1. Fill in #todo section
  2. Update Active Projects
  3. Fill in Standup section, then run:
       python3 ~/.claude/skills/daily_start.py --standup
{'='*50}
""")


if __name__ == "__main__":
    main()
