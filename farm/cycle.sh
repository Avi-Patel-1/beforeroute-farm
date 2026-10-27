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
# equivalence logs are never read after the check: keep them compressed (they were 2.8 GB of 14 GB)
find results -path "*/equiv/*.log" -size +1M -print0 2>/dev/null | xargs -0 -r -n 20 gzip -f

# keep a background collector polling between check-ins (self-healing: restarted if absent)
if ! pgrep -f "farm/collect_loop" > /dev/null; then
  setsid nohup bash farm/collect_loop.sh > results/collect_loop.log 2>&1 < /dev/null &
  echo "-- collector loop (re)started"
fi

# hero bases to (re)collect: only those with finished runs not yet collected (farm/bases_to_collect.py keeps the
# collected run ids in results/.collected_runs.json); a full pass over ~50 bases took longer than the check-in budget
BASES=$(python3 farm/bases_to_collect.py 2>/dev/null)
echo "-- hero bases with new finished runs: $(echo $BASES | wc -w)"
for b in $BASES; do
  out=$(python3 farm/hero_collect.py --repo $REPO --base "$b" --results results 2>&1)
  n=$(echo "$out" | grep -c " completed \| flow_failed")
  echo "-- hero $b: $n rows"
done
python3 farm/bases_to_collect.py --mark
SUMMARIES=""
for b in d1-aes_cipher-000 d1-picorv32-016 d1-picorv32-006 d3-salsa20-000 d3-des-000 d3-y_huff-000 d3-ocs_blitter-000 d3-bm64-000 d3-md5-000 d3b-sha512-000 d3b-ldpcenc-000 d5-chacha-000 d5-point_add-000 d5-blabla-000 nv1-nvdla_csc-000; do
  [ -f "results/$b/hero_summary.json" ] && SUMMARIES="$SUMMARIES --summary results/$b/hero_summary.json"
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
