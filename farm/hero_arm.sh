#!/usr/bin/env bash
# Run one hero arm on a farm runner. Usage: hero_arm.sh <base_tag> <arm> <model_path> [jobs]
# <arm>: rerun | uni<H> | tgt<kkk>-<H>   (kkk = flagged fraction in tenths of a percent, e.g. 050 = 5%)
set -euo pipefail
BASE=$1; ARM=$2; MODEL=$3; JOBS=${4:-4}
IMAGE=${IMAGE:-ghcr.io/librelane/librelane@sha256:4bc9042ba177f73f275b5b39e7d372a07d3f4043f548a0ba7f640097b7205051}
DOCKER="docker run --rm -v $PWD:/work -w /work -e PDK_ROOT=/work/pdk $IMAGE"
SPEC=farm/jobs/$BASE.json
DESIGN=$(python3 -c "import json;print(json.load(open('$SPEC'))['design'])")
mkdir -p results
# 1. baseline to a kept checkpoint (deterministic; rebuilt per runner)
$DOCKER python3 br/run_job.py --job-spec $SPEC --design /work/$DESIGN --jobs $JOBS --results results --pdk-root /work/pdk --keep-run --timeout 16000
sudo chown -R "$(id -u):$(id -g)" results designs || true
test -f results/$BASE/nets.jsonl
BASE_RUN=/work/$DESIGN/runs/$BASE
case "$ARM" in
  rerun)
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm base --tag $BASE-rerun --results results --pdk-root /work/pdk --jobs $JOBS ;;
  uni*)
    H=${ARM#uni}
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm uniform --tag $BASE-$ARM --slew-pct $H --cap-pct $H --results results --pdk-root /work/pdk --jobs $JOBS ;;
  tgt*)
    K=${ARM#tgt}; K=${K%%-*}; H=${ARM##*-}
    FRAC=$(python3 -c "print(int('$K')/1000)")
    python3 -m pip install -q pandas pyarrow lightgbm scikit-learn
    python3 br/score.py --model $MODEL --run-results results/$BASE --frac $FRAC --out results/$BASE/flagged_$ARM.json
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm targeted --tag $BASE-$ARM --slew-pct $H --cap-pct $H --flagged /work/results/$BASE/flagged_$ARM.json --results results --pdk-root /work/pdk --jobs $JOBS ;;
  tier*)
    # tier020-70_050-40  ->  top 2% at 70%, next (up to 5%) at 40%
    SPEC=$(python3 -c "
import sys
a='$ARM'[4:]
print(','.join(f'{int(x.split(\"-\")[0])/1000}:{x.split(\"-\")[1]}' for x in a.split('_')))")
    python3 -m pip install -q pandas pyarrow lightgbm scikit-learn
    python3 br/score.py --model $MODEL --run-results results/$BASE --tiers "$SPEC" --out results/$BASE/tiers_$ARM.json
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm tiered --tag $BASE-$ARM --tiers /work/results/$BASE/tiers_$ARM.json --results results --pdk-root /work/pdk --jobs $JOBS ;;
  *) echo "unknown arm $ARM"; exit 2 ;;
esac
sudo chown -R "$(id -u):$(id -g)" results || true
ls results
