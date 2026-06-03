#!/usr/bin/env bash
# fanout_refute.sh — adversarial verification fan-out with aitr-routed models.
#
# Takes a file of claims (one per line) and asks the OPPOSITE provider's model
# to refute each one in parallel. Demonstrates aitr Pattern 2 (Bash fan-out)
# with the refute task_kind, which prefers cross-provider diversity.
#
# Usage:
#   ./fanout_refute.sh claims.txt [out_dir]
#
# Requires: claude CLI (or zclaude), python3, aitr skill installed.
set -euo pipefail

CLAIMS_FILE="${1:?usage: fanout_refute.sh <claims-file> [out-dir]}"
OUT_DIR="${2:-/tmp/aitr-refute-$$}"
AITR="python3 $HOME/.claude/skills/aitr/scripts/pick.py"

mkdir -p "$OUT_DIR"

# ---- Stage 0: routing pick (one pick for the whole fan-out) ----------------
# This script executes via the `claude` CLI, so only anthropic models are
# reachable — constrain the pick accordingly. (For true cross-provider refutation,
# use cross-model-check instead, which can dispatch to codex.)
echo "[refute] asking aitr for the refuter model…" >&2
set +e
PICK_JSON=$($AITR pick task_kind=refute caller=fanout-refute quality_floor=high-stakes provider_constraint=anthropic-only --format json)
PICK_EXIT=$?
set -e

REFUTER_MODEL=""
case $PICK_EXIT in
  0)
    REFUTER_MODEL=$(echo "$PICK_JSON" | python3 -c "
import sys, json
d = json.load(sys.stdin)
mc = d.get('model_class', '')
print(mc if mc in ('opus', 'sonnet', 'haiku') else '')
")
    echo "[refute] aitr picked: $(echo "$PICK_JSON" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['model'], '—', d['reason'])")" >&2
    ;;
  1)
    echo "[refute] FATAL: aitr usage error — fix this script's signal" >&2
    exit 1
    ;;
  2|3)
    echo "[refute] WARNING: aitr exit $PICK_EXIT — proceeding with CLI default model (LOUD: routing not optimized)" >&2
    ;;
esac

# ---- Stage 1: parallel refutation ------------------------------------------
echo "[refute] fanning out over $(wc -l < "$CLAIMS_FILE" | tr -d ' ') claims…" >&2

i=0
while IFS= read -r claim; do
  [ -z "$claim" ] && continue
  i=$((i + 1))
  (
    claude -p "Try to refute this claim. Default to 'REFUTED' if you find any solid counter-evidence; 'STANDS' only if it survives scrutiny. End with exactly one line: VERDICT: REFUTED or VERDICT: STANDS.

Claim: $claim" \
      ${REFUTER_MODEL:+--model "$REFUTER_MODEL"} \
      > "$OUT_DIR/claim-$i.refutation.md" 2> "$OUT_DIR/claim-$i.err"
  ) &
done < "$CLAIMS_FILE"
wait

# ---- Stage 2: tally ---------------------------------------------------------
refuted=$(grep -l "VERDICT: REFUTED" "$OUT_DIR"/claim-*.refutation.md 2>/dev/null | wc -l | tr -d ' ')
stands=$(grep -l "VERDICT: STANDS" "$OUT_DIR"/claim-*.refutation.md 2>/dev/null | wc -l | tr -d ' ')

echo ""
echo "[refute] done: $stands stand, $refuted refuted"
echo "[refute] details: $OUT_DIR/"
