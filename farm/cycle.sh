#!/usr/bin/env bash
# One progress cycle, run at every check-in:
#   collect farm artifacts -> hero tables for every base with arms -> pareto figure
#   -> pack new results -> (optionally) rebuild dataset + retrain in the background
# Usage: farm/cycle.sh [--train]   (idempotent; safe to run repeatedly)
set -uo pipefail
cd "$(dirname "$0")/.."
REPO=Avi-Patel-1/beforeroute-farm
TRAIN=0; [ "${1:-}" = "--train" ] && TRAIN=1
echo "== $(date '+%F %T') cycle start"

python3 farm/collect.py --repo $REPO --results results 2>&1 | tail -2

# keep a background collector polling between check-ins (self-healing: restarted if absent)
if ! pgrep -f "farm/collect_loop" > /dev/null; then
  setsid nohup bash farm/collect_loop.sh > results/collect_loop.log 2>&1 < /dev/null &
  echo "-- collector loop (re)started"
fi

# hero bases = any results dir that has a "-rerun" arm or arms on the farm
BASES=$(gh run list -R $REPO -w hero.yml --limit 20 --json databaseId --jq '.[].databaseId' | while read r; do gh run view $r -R $REPO --json jobs --jq '.jobs[0].name' 2>/dev/null; done | sed -E 's/-(rerun|uni[0-9]+|tgt[0-9]+-[0-9a-z]+|tier.*|lt[0-9].*|thr[0-9]+-[0-9a-z]+|det[0-9]+-[0-9a-z]+|lst-[0-9a-z]+-[0-9]+|exp[0-9]+-[0-9]+|est[0-9]+-[0-9]+|seed|dmp|rcal[0-9]+-[0-9]+|lsx-[0-9a-z]+)$//' | sort -u)
BASES=$(printf '%s\n' $BASES d1-aes_cipher-000 d1-picorv32-016 d1-picorv32-006 d3-salsa20-000 d3-des-000 d3-y_huff-000 d3-ocs_blitter-000 d3-bm64-000 d3-md5-000 d3b-sha512-000 d3b-ldpcenc-000 d5-chacha-000 d5-point_add-000 d5-blabla-000 nv1-nvdla_csc-000 | sort -u)
SUMMARIES=""
for b in $BASES; do
  out=$(python3 farm/hero_collect.py --repo $REPO --base "$b" --results results 2>&1)
  n=$(echo "$out" | grep -c " completed ")
  echo "-- hero $b: $((n-1)) arms collected"
  [ "$b" != "picorv32-base-v1" ] && [ -f "results/$b/hero_summary.json" ] && [ "$n" -gt 1 ] && SUMMARIES="$SUMMARIES --summary results/$b/hero_summary.json"
done
if [ -n "$SUMMARIES" ]; then
  mkdir -p figures
  python3 br/figures.py pareto $SUMMARIES --out figures/pareto_confirmatory.png --title "Targeted vs uniform post-GRT repair (models never saw the base design)" 2>&1 | tail -1
fi
[ -f results/picorv32-base-v1/hero_summary.json ] && python3 br/figures.py pareto --summary results/picorv32-base-v1/hero_summary.json --out figures/pareto_picorv32-base-v1.png --title "PicoRV32 exploratory sweep" 2>&1 | tail -1

# iterations-to-closure: advance the signoff-guided loop and BeforeRoute+cleanup chains
python3 farm/advance.py 2>&1 | tail -8
python3 farm/dispatch_r5.py 2>&1 | tail -6

NEW=$(python3 farm/pack_results.py | wc -l)
echo "-- packed $NEW new result archives"

if [ "$TRAIN" = 1 ]; then
  nruns=$(ls results/*/nets_signoff.jsonl 2>/dev/null | wc -l)
  last=$(cat results/.trained_on 2>/dev/null || echo 0)
  if [ "$nruns" -ge $((last + 3)) ]; then
    echo "-- rebuilding dataset ($nruns runs, last trained on $last) and retraining in background"
    setsid nohup bash -c "python3 br/build_dataset.py --results results > results/build_dataset.log 2>&1 && \
      python3 br/train.py --data results/dataset.parquet --out results/model_latest --holdout picorv32 > results/train_latest.log 2>&1 && \
      echo $nruns > results/.trained_on" > /dev/null 2>&1 < /dev/null &
  else
    echo "-- no retrain ($nruns runs, trained on $last)"
  fi
fi
echo "== $(date '+%F %T') cycle end"
