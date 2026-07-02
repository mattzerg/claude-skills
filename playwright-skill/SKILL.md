---
name: playwright-skill
description: Browser automation for web tasks. Use when the user needs to automate browser interactions, take screenshots, extract data from websites, fill forms, or perform web scraping. Supports persistent sessions for logged-in state.
allowed-tools: Bash, Read
---


# Playwright Skill - Browser Automation

Automate browser tasks: navigate, click, type, extract data, take screenshots, and more.

## First-Time Setup

```bash
pip install playwright
playwright install chromium
```

## Core Concepts

### Sessions
Sessions persist browser state (cookies, localStorage) across commands. Use named sessions for different accounts/sites:

```bash
# Default session
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py open https://example.com

# Named session for a specific site
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py open https://github.com --session github
```

Sessions are saved to `~/.claude/skills/playwright-skill/sessions/`

### Headless vs Visible
By default, browser runs headless (invisible). Use `--visible` to see what's happening:

```bash
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py open https://example.com --visible
```

## Commands

### Navigation

```bash
# Open a URL
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py open URL [--session NAME] [--visible]

# Wait for element to appear
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py wait SELECTOR [--timeout MS] [--session NAME]

# Scroll page
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py scroll [--direction up|down] [--amount PIXELS] [--session NAME]
```

### Interaction

```bash
# Click an element
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py click SELECTOR [--session NAME]

# Type text into input
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py type SELECTOR "text to type" [--clear] [--session NAME]

# Execute JavaScript
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py eval "document.title" [--session NAME]
```

### Data Extraction

```bash
# Extract text from element
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py extract SELECTOR [--session NAME]

# Extract attribute
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py extract "a.link" --attr href [--session NAME]

# Extract from all matching elements
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py extract "li.item" --all [--session NAME]

# Get page HTML
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py html [--selector SELECTOR] [--output FILE] [--session NAME]
```

### Screenshots & PDF

```bash
# Screenshot current page
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py screenshot [--output FILE] [--session NAME]

# Screenshot with URL
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py screenshot https://example.com --output example.png

# Full-page screenshot
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py screenshot --full-page --output full.png

# Save as PDF
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py pdf https://example.com --output page.pdf
```

### Cookies & Sessions

```bash
# List all cookies
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py cookies [--session NAME]

# Get specific cookie
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py cookies --name session_id [--session NAME]

# Set cookie
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py cookies --set "name=value" --domain example.com [--session NAME]

# List all sessions
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py sessions

# Close session (saves state)
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py close [--session NAME]

# Close all sessions
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py close --all
```

## Selectors

Playwright supports multiple selector types:

```bash
# CSS selectors
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py click "button.submit"
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py click "#login-form input[type=email]"

# Text selectors
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py click "text=Sign In"
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py click "text=Submit"

# XPath
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py click "xpath=//button[@type='submit']"

# Combining
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py click "form >> text=Submit"
```

## Examples

### Login Flow (Manual First Time)

```bash
# Open login page visibly
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py open https://example.com/login --visible --session mysite

# ... manually log in while browser is visible ...

# Close to save session
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py close --session mysite

# Future runs use saved session (logged in)
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py open https://example.com/dashboard --session mysite
```

### Scrape a List

```bash
# Open page
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py open https://news.ycombinator.com

# Extract all headlines
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py extract ".titleline a" --all

# Extract with links
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py extract ".titleline a" --attr href --all
```

### Fill a Form

```bash
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py open https://example.com/form --session formtest
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py type "input[name=email]" "user@example.com" --session formtest
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py type "input[name=message]" "Hello world" --session formtest
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py click "button[type=submit]" --session formtest
```

### Screenshot a Page

```bash
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py screenshot https://example.com --output example.png --full-page
```

### Run JavaScript

```bash
# Get page title
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py eval "document.title"

# Get scroll position
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py eval "window.scrollY"

# Count elements
/usr/bin/python3 ~/.claude/skills/playwright-skill/playwright_skill.py eval "document.querySelectorAll('a').length"
```

## Output

All commands output JSON for easy parsing.

## Requirements

- Python 3.9+
- `pip install playwright`
- `playwright install chromium`

## Tips

- **First login**: Use `--visible` to manually log in, then save session for headless reuse
- **Flaky selectors**: Use `wait` command before interacting with dynamic content
- **Rate limiting**: Add delays between actions with `eval "await new Promise(r => setTimeout(r, 2000))"`
- **Debugging**: Take screenshots to see what went wrong
- **Multiple accounts**: Use different session names for each account

## Security Notes

- Session files contain authentication cookies - keep `sessions/` directory secure
- Don't share session files - they can grant account access
- Clear sessions when done with sensitive sites: `close --session NAME`
