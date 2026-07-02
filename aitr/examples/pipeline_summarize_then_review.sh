#!/usr/bin/env bash
# pipeline_summarize_then_review.sh — two-stage pipeline with per-stage models.
#
# Stage 1: summarize each input doc with a CHEAP model (aitr: summarize/cheap-ok
#          → typically haiku or an equivalent small model)
# Stage 2: review the combined summaries with a CAPABLE model (aitr:
#          prose-review/high-stakes → typically opus/sonnet)
#
# This is the canonical "cheap fan-out, expensive verify" shape — the place
# where per-stage routing saves the most money.
#
# Usage:
#   ./pipeline_summarize_then_review.sh 'docs/*.md' [out_dir]
set -euo pipefail

GLOB="${1:?usage: pipeline_summarize_then_review.sh '<glob>' [out-dir]}"
OUT_DIR="${2:-/tmp/aitr-pipeline-$$}"
AITR="python3 $HOME/.claude/skills/aitr/scripts/pick.py"

mkdir -p "$OUT_DIR/summaries"

# ---- Stage 0: routing picks (one per stage, NOT per item) ------------------
pick_model() {
  # $1 = task_kind, $2 = quality_floor. Echoes claude model alias or "".
  # provider_constraint=anthropic-only because this script executes via the
  # `claude` CLI — picks outside anthropic would be unusable here.
  local pick_json exit_code
  set +e
  pick_json=$($AITR pick "task_kind=$1" caller=pipeline-summarize-review "quality_floor=$2" provider_constraint=anthropic-only --format json)
  exit_code=$?
  set -e
  case $exit_code in
    0)
      echo "$pick_json" | python3 -c "
import sys, json
d = json.load(sys.stdin)
mc = d.get('model_class', '')
print(mc if mc in ('opus', 'sonnet', 'haiku') else '')
"
      echo "[pipeline] aitr ($1/$2): $(echo "$pick_json" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['model'], '—', d['reason'])")" >&2
      ;;
    1)
      echo "[pipeline] FATAL: aitr usage error for task_kind=$1" >&2
      exit 1
      ;;
    *)
      echo "[pipeline] WARNING: aitr exit $exit_code for task_kind=$1 — CLI default model (LOUD)" >&2
      echo ""
      ;;
  esac
}

SUMMARIZER=$(pick_model summarize cheap-ok)
REVIEWER=$(pick_model prose-review high-stakes)

# ---- Stage 1: cheap parallel summarization ---------------------------------
echo "[pipeline] stage 1: summarizing with model=${SUMMARIZER:-default}…" >&2

for doc in $GLOB; do
  [ -f "$doc" ] || continue
  base=$(basename "$doc")
  (
    claude -p "Summarize this document in 5 bullet points. Keep concrete numbers and named entities.

$(cat "$doc")" \
      ${SUMMARIZER:+--model "$SUMMARIZER"} \
      > "$OUT_DIR/summaries/$base.summary.md" 2> "$OUT_DIR/summaries/$base.err"
  ) &
done
wait

# ---- Stage 2: capable single-shot review ------------------------------------
echo "[pipeline] stage 2: reviewing with model=${REVIEWER:-default}…" >&2

claude -p "These are summaries of related documents. Review them as a set:
1. What themes recur across documents?
2. What contradictions exist between documents?
3. What's conspicuously missing?

$(cat "$OUT_DIR"/summaries/*.summary.md)" \
  ${REVIEWER:+--model "$REVIEWER"} \
  > "$OUT_DIR/review.md"

echo ""
echo "[pipeline] done."
echo "[pipeline] summaries: $OUT_DIR/summaries/"
echo "[pipeline] review:    $OUT_DIR/review.md"
