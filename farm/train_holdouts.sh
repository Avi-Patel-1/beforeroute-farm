#!/usr/bin/env bash
# Idempotent: train one held-out model per design listed, skipping designs whose model already exists.
# Usage: farm/train_holdouts.sh salsa20:salsa20 des:des ...   (<file tag>:<design name in dataset>)
cd "$(dirname "$0")/.."
for pair in "$@"; do
  tag=${pair%%:*}; d=${pair#*:}
  [ -f models/model_holdout_${tag}_v4.txt ] && { echo "$(date +%H:%M) skip $tag (exists)"; continue; }
  python3 br/train.py --data results/dataset.parquet --out results/model_v4_$tag --holdout $d --no-lodo > results/train_v4_$tag.log 2>&1 \
    && cp results/model_v4_$tag/model_holdout_$d.txt models/model_holdout_${tag}_v4.txt \
    && { [ -f results/model_v4_$tag/reg_holdout_$d.txt ] && cp results/model_v4_$tag/reg_holdout_$d.txt models/reg_holdout_${tag}_v4.txt; true; } \
    && echo "$(date +%H:%M) trained $tag"
done
echo "$(date +%H:%M) train_holdouts done"
