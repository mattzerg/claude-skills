---
name: amazon-skill
description: Search Amazon products, check prices, build multi-item carts, and manage shopping lists. Use when the user asks to find products on Amazon, check prices, build a shopping cart, or manage an Amazon buy list.
allowed-tools: Bash, Read
---


# Amazon Skill

Search products, check prices, build carts, and manage shopping lists on Amazon.

## Setup

No API keys needed. Uses web scraping with requests + BeautifulSoup.

Requirements (likely already installed):
```bash
pip install requests beautifulsoup4
```

## Commands

### Search

```bash
python3 ~/.claude/skills/amazon-skill/amazon_skill.py search "query" [--limit N] [--sort price-asc|price-desc|reviews|newest]
```

### Product Details

```bash
python3 ~/.claude/skills/amazon-skill/amazon_skill.py product ASIN_OR_URL
```

Accepts an ASIN (e.g., `B0BSHF7WHW`) or a full Amazon URL.

### Build Cart URL

Generate a single URL that adds multiple items to an Amazon cart when opened in a browser:

```bash
python3 ~/.claude/skills/amazon-skill/amazon_skill.py cart-url ASIN1[:QTY] ASIN2[:QTY] ...
```

Example:
```bash
python3 ~/.claude/skills/amazon-skill/amazon_skill.py cart-url B0BSHF7WHW:2 B07WDPT9JZ:1 B09N3XKQLH:3
```

### Shopping Lists

Save, load, and manage named shopping lists:

```bash
# Save a list
python3 ~/.claude/skills/amazon-skill/amazon_skill.py list-save "actuator-parts" B0BSHF7WHW:2 B07WDPT9JZ:1

# Show all lists
python3 ~/.claude/skills/amazon-skill/amazon_skill.py lists

# Load a list
python3 ~/.claude/skills/amazon-skill/amazon_skill.py list-load "actuator-parts"

# Fetch current prices for all items in a list
python3 ~/.claude/skills/amazon-skill/amazon_skill.py enrich-list "actuator-parts"

# Generate cart URL from a saved list
python3 ~/.claude/skills/amazon-skill/amazon_skill.py list-cart "actuator-parts"

# Delete a list
python3 ~/.claude/skills/amazon-skill/amazon_skill.py list-delete "actuator-parts"
```

## Workflow Example

```bash
# 1. Search for parts
python3 ~/.claude/skills/amazon-skill/amazon_skill.py search "AS5600 magnetic encoder breakout" --limit 5

# 2. Check a specific product
python3 ~/.claude/skills/amazon-skill/amazon_skill.py product B0BSHF7WHW

# 3. Save items to a list
python3 ~/.claude/skills/amazon-skill/amazon_skill.py list-save "phase-1" B0BSHF7WHW:3 B07WDPT9JZ:1

# 4. Get current prices for all items
python3 ~/.claude/skills/amazon-skill/amazon_skill.py enrich-list "phase-1"

# 5. Generate one-click cart URL
python3 ~/.claude/skills/amazon-skill/amazon_skill.py list-cart "phase-1"
```

## Output

All commands output JSON.

## Notes

- Amazon occasionally blocks automated requests. If you get empty results, wait a minute and retry.
- Cart URLs work by opening in your browser — they add items directly to your Amazon cart.
- Shopping lists are saved as JSON in `~/.claude/skills/amazon-skill/lists/`.
- The `enrich-list` command fetches live prices and saves them back to the list file.
- Use ASIN:QTY format to specify quantities (e.g., `B0BSHF7WHW:3` for 3 units). Default quantity is 1.
