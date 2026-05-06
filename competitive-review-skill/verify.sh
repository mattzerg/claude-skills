#!/usr/bin/env bash
# Smoke test for competitive-review-skill — verifies imports, dependencies, and
# the offline pieces of the pipeline. Does NOT make Claude calls or scrape sites
# (those cost time/money and flake on network).
#
# Usage: bash verify.sh

set -euo pipefail
cd "$(dirname "$0")"

echo "=== 1. Python imports ==="
python3 -c "from lib import claude, scraper, vault, priors, sources, state; print('  ok')"

echo
echo "=== 2. Phase scripts respond to --help ==="
for s in discover.py scan.py compare.py rank.py report.py cards.py competitive_review.py; do
  python3 "$s" --help >/dev/null && echo "  ok  $s"
done

echo
echo "=== 3. Vault paths exist ==="
python3 -c "
from lib import vault
assert vault.VAULT_ROOT.exists(), 'vault root missing'
assert vault.ZSTACK_DIR.exists(), 'zstack dir missing'
assert vault.CONVERSATIONS_DIR.exists(), 'conversations dir missing'
print('  ok  all vault paths reachable')
"

echo
echo "=== 4. Product spec parsing ==="
python3 -c "
from lib import vault
spec = vault.read_product_spec('Zergboard')
assert spec, 'Zergboard spec not found'
assert spec['live_url'] == 'https://zergboard.fly.dev', f'wrong live_url: {spec[\"live_url\"]}'
assert spec['frontmatter'].get('fly_app') == 'zergboard', 'fly_app missing from frontmatter'
print(f'  ok  spec={spec[\"path\"]}')
print(f'      live_url={spec[\"live_url\"]}')
"

echo
echo "=== 5. Prior audits finder ==="
python3 -c "
from lib import priors
hits = priors.find_prior_audits('competitive-positioning', ['Cursor', 'Sourcegraph', 'Linear'])
assert len(hits) > 0, 'no prior audits found'
print(f'  ok  found {len(hits)} prior audits, top={hits[0][\"filename\"]}')
"

echo
echo "=== 6. HN Algolia API ==="
python3 -c "
from lib import sources
hits = sources.hn_search('linear app', limit=3)
assert len(hits) > 0, 'HN returned 0 hits'
print(f'  ok  {len(hits)} HN hits')
"

echo
echo "=== 7. Dependencies ==="
[ -L ~/.local/bin/claude ] && echo "  ok  claude CLI present" || echo "  WARN claude CLI symlink missing at ~/.local/bin/claude"
[ -f ~/.claude/skills/zergboard-skill/config.json ] && echo "  ok  zergboard config present" || echo "  WARN zergboard config missing — cards.py --yes will fail"
python3 -c "from playwright.sync_api import sync_playwright; print('  ok  playwright import')"
python3 -c "import bs4; print('  ok  bs4 import')"

echo
echo "All smoke tests passed."
echo
echo "To run a real review (will make Claude calls + scrape sites):"
echo "  python3 competitive_review.py pm-software --product Zergboard linear.app asana.com --phase discover"
