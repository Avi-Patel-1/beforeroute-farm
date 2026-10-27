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
# 1. baseline to a kept checkpoint (deterministic). Restored from the actions cache when available;
#    otherwise built here and pruned to the steps up to the post-GRT checkpoint so the cache stays small.
if [ -f results/$BASE/job.json ] && ls $DESIGN/runs/$BASE/*-openroad-checkantennas/state_out.json >/dev/null 2>&1 && [ -f $DESIGN/config.$BASE.json ]; then
  echo "[hero] baseline checkpoint restored from cache"
else
  $DOCKER python3 br/run_job.py --job-spec $SPEC --design /work/$DESIGN --jobs $JOBS --results results --pdk-root /work/pdk --keep-run --timeout 16000
  sudo chown -R "$(id -u):$(id -g)" results designs || true
  python3 - "$DESIGN/runs/$BASE" <<'PY'
import glob, os, re, shutil, sys
rd = sys.argv[1]
ck = sorted(glob.glob(os.path.join(rd, "*-openroad-checkantennas")))
if ck:
    idx = int(os.path.basename(ck[0]).split("-")[0])
    for d in os.listdir(rd):
        m = re.match(r"^(\d+)-", d)
        p = os.path.join(rd, d)
        if (m and int(m.group(1)) > idx) or d == "final":
            shutil.rmtree(p, ignore_errors=True)
    print(f"[hero] pruned run dir to steps <= {idx}")
PY
fi
test -f results/$BASE/nets.jsonl
BASE_RUN=/work/$DESIGN/runs/$BASE
case "$ARM" in
  seed)
    echo "[hero] seed: baseline checkpoint only (populates the cache)" ;;
  rerun)
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm base --tag $BASE-rerun --results results --pdk-root /work/pdk --jobs $JOBS ;;
  uni*)
    H=${ARM#uni}
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm uniform --tag $BASE-$ARM --slew-pct $H --cap-pct $H --results results --pdk-root /work/pdk --jobs $JOBS ;;
  lst-*)
    # lst-<name>-<H>: targeted repair on a committed net list farm/lists/<BASE>/<name>.json (signoff-guided loops, cleanup passes)
    NAME=${ARM#lst-}; H=${NAME##*-}; NAME=${NAME%-*}
    LIST=farm/lists/$BASE/$NAME.json
    test -f $LIST
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm targeted --tag $BASE-$ARM --slew-pct $H --cap-pct $H --flagged /work/$LIST --results results --pdk-root /work/pdk --jobs $JOBS ;;
  det*)
    # det050-70: top 5% of nets by the frozen deterministic rule R8 = max(est load slew, est driver slew, est cap ratio), margin 70 (AI ablation)
    K=${ARM#det}; K=${K%%-*}; H=${ARM##*-}
    FRAC=$(python3 -c "print(int('$K')/1000)")
    python3 -m pip install -q pandas pyarrow lightgbm scikit-learn
    python3 br/score.py --model none --rule R8 --run-results results/$BASE --frac $FRAC --out results/$BASE/flagged_$ARM.json
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm targeted --tag $BASE-$ARM --slew-pct $H --cap-pct $H --flagged /work/results/$BASE/flagged_$ARM.json --results results --pdk-root /work/pdk --jobs $JOBS ;;
  tgt*|thr*)
    # tgt050-70: top 5% of nets | thr500-70: every net with p >= 0.500 ; suffixes after H:
    #   p2 = two masked passes, f = + fanout rule, h = hold-fix delay cells protected from resizing, v3 = model tag
    case "$ARM" in tgt*) K=${ARM#tgt}; SEL=frac;; thr*) K=${ARM#thr}; SEL=thr;; esac
    K=${K%%-*}; REST=${ARM##*-}; H=${REST%%[pfhv]*}
    PASSES=1; case "$REST" in *p2*) PASSES=2;; esac
    RULE=""; case "$REST" in *f*) RULE="--rule-fanout";; esac
    PROT=""; case "$REST" in *h*) PROT="--protect-hold";; esac
    VAL=$(python3 -c "print(int('$K')/1000)")
    [ "$SEL" = frac ] && SELARG="--frac $VAL" || SELARG="--threshold $VAL"
    python3 -m pip install -q pandas pyarrow lightgbm scikit-learn
    python3 br/score.py --model $MODEL --run-results results/$BASE $SELARG $RULE --out results/$BASE/flagged_$ARM.json
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm targeted --tag $BASE-$ARM --slew-pct $H --cap-pct $H --passes $PASSES $PROT --flagged /work/results/$BASE/flagged_$ARM.json --results results --pdk-root /work/pdk --jobs $JOBS ;;
  lt*)
    # lt050-80-60-40: top 5% split by predicted signoff ratio (>=1.3 | >=1.1 | rest) at margins 80/60/40
    K=${ARM#lt}; K=${K%%-*}; M=${ARM#lt*-}; H1=${M%%-*}; M2=${M#*-}; H2=${M2%%-*}; H3=${M2#*-}
    FRAC=$(python3 -c "print(int('$K')/1000)")
    REG=$(echo "$MODEL" | sed 's#/model_#/reg_#')
    python3 -m pip install -q pandas pyarrow lightgbm scikit-learn
    python3 br/score.py --model $MODEL --run-results results/$BASE --frac $FRAC --reg-model $REG --reg-tiers "1.3:$H1,1.1:$H2,0:$H3" --out results/$BASE/tiers_$ARM.json
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm tiered --tag $BASE-$ARM --tiers /work/results/$BASE/tiers_$ARM.json --results results --pdk-root /work/pdk --jobs $JOBS ;;
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
