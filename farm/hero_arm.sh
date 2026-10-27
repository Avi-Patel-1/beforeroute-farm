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
  NL=$(ls $DESIGN/runs/$BASE/final/nl/*.nl.v 2>/dev/null | head -1)
  [ -n "$NL" ] && gzip -c "$NL" > results/$BASE/final.nl.v.gz
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
# Scoring input. Default: the baseline's post-GRT dump (STAMidPNR-3 view, after antenna repair).
# Arms with suffix "c" score features dumped at the checkpoint itself, with no signoff data in the
# scoring directory at all: exactly what a deployed flow step would see.
SRC=results/$BASE
use_checkpoint_features() {
  local D=results/$BASE-ckpt
  if [ ! -f $D/nets.jsonl ]; then
    local ST
    ST=$(ls $DESIGN/runs/$BASE/*-openroad-checkantennas/state_out.json | head -1)
    mkdir -p $D
    $DOCKER python3 br/run_dump.py $BASE_RUN --state /work/$ST --out /work/$D/dump --pdk-root /work/pdk > $D/dump.log 2>&1 || true
    sudo chown -R "$(id -u):$(id -g)" results || true
    if [ ! -f $D/dump/nets.jsonl ]; then echo "[hero] checkpoint feature dump failed"; tail -20 $D/dump.log; exit 3; fi
    cp $D/dump/nets.jsonl $D/dump/dump_summary.json $D/
    rm -rf $D/dump
    cp results/$BASE/resolved.json $D/resolved.json
    python3 - "$D" "$BASE" <<'PY'
import json, os, sys
d, base = sys.argv[1], sys.argv[2]
json.dump({"tag": base + "-ckpt", "status": "completed", "kind": "checkpoint features only, no signoff data"}, open(os.path.join(d, "job.json"), "w"))
json.dump({"nets": [], "summary": {"nets_violating": 0, "corner_counts": {}}}, open(os.path.join(d, "labels.json"), "w"))
json.dump({"nets": {}}, open(os.path.join(d, "final_nets.json"), "w"))
json.dump({}, open(os.path.join(d, "metrics.json"), "w"))
PY
  fi
  SRC=$D
  echo "[hero] scoring checkpoint features ($D)"
}
case "$ARM" in
  seed)
    echo "[hero] seed: baseline checkpoint only (populates the cache)" ;;
  dmp)
    # decision-point dump: per-net features at the post-GRT checkpoint the arms resume from (before antenna
    # repair), to check that scoring there flags the same nets as scoring the STAMidPNR-3 view
    ST=$(ls $DESIGN/runs/$BASE/*-openroad-checkantennas/state_out.json | head -1)
    mkdir -p results/$BASE-dmp
    $DOCKER python3 br/run_dump.py $BASE_RUN --state /work/$ST --out /work/results/$BASE-dmp/dump --pdk-root /work/pdk > results/$BASE-dmp/dump.log 2>&1 || true
    sudo chown -R "$(id -u):$(id -g)" results || true
    cp results/$BASE-dmp/dump/nets.jsonl results/$BASE-dmp/nets.jsonl 2>/dev/null || true
    cp results/$BASE-dmp/dump/dump_summary.json results/$BASE-dmp/dump_summary.json 2>/dev/null || true
    rm -rf results/$BASE-dmp/dump
    if [ -f results/$BASE-dmp/nets.jsonl ]; then st=completed; else st=dump_failed; fi
    python3 -c "import json;json.dump({'tag':'$BASE-dmp','status':'$st','kind':'decision-point dump','state':'$ST'},open('results/$BASE-dmp/job.json','w'))"
    gzip -f results/$BASE-dmp/nets.jsonl 2>/dev/null || true ;;
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
  lsx-*)
    # lsx-<name>: escalation pass of a stalled chain — two-tier repair from a committed tiers file
    # farm/lists/<BASE>/<name>.json ({"tiers": [{"nets": list, 70}, {"nets": residual violators, 90}]})
    NAME=${ARM#lsx-}
    LIST=farm/lists/$BASE/$NAME.json
    test -f $LIST
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm tiered --tag $BASE-$ARM --tiers /work/$LIST --results results --pdk-root /work/pdk --jobs $JOBS ;;
  est*)
    # est050-70: top 5% of nets by the timer's own estimated worst-load slew ratio, margin 70 (strongest simple ablation at k=5%)
    K=${ARM#est}; K=${K%%-*}; H=${ARM##*-}
    case "$H" in *c) H=${H%c}; use_checkpoint_features;; esac
    FRAC=$(python3 -c "print(int('$K')/1000)")
    python3 -m pip install -q pandas pyarrow lightgbm scikit-learn
    python3 br/score.py --model none --rule EST --run-results $SRC --frac $FRAC --out results/$BASE/flagged_$ARM.json
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm targeted --tag $BASE-$ARM --slew-pct $H --cap-pct $H --flagged /work/results/$BASE/flagged_$ARM.json --results results --pdk-root /work/pdk --jobs $JOBS ;;
  det*)
    # det050-70: top 5% of nets by the frozen deterministic rule R8 = max(est load slew, est driver slew, est cap ratio), margin 70 (AI ablation)
    K=${ARM#det}; K=${K%%-*}; H=${ARM##*-}
    case "$H" in *c) H=${H%c}; use_checkpoint_features;; esac
    FRAC=$(python3 -c "print(int('$K')/1000)")
    python3 -m pip install -q pandas pyarrow lightgbm scikit-learn
    python3 br/score.py --model none --rule R8 --run-results $SRC --frac $FRAC --out results/$BASE/flagged_$ARM.json
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm targeted --tag $BASE-$ARM --slew-pct $H --cap-pct $H --flagged /work/results/$BASE/flagged_$ARM.json --results results --pdk-root /work/pdk --jobs $JOBS ;;
  exp*)
    # exp100-70: auto-budget = top round(1.00 * sum(p)) nets (the model's expected violator count), margin 70
    F=${ARM#exp}; F=${F%%-*}; H=${ARM##*-}
    case "$H" in *c) H=${H%c}; use_checkpoint_features;; esac
    FAC=$(python3 -c "print(int('$F')/100)")
    python3 -m pip install -q pandas pyarrow lightgbm scikit-learn
    python3 br/score.py --model $MODEL --run-results $SRC --expected-count $FAC --out results/$BASE/flagged_$ARM.json
    $DOCKER python3 br/arms.py --base-run $BASE_RUN --arm targeted --tag $BASE-$ARM --slew-pct $H --cap-pct $H --flagged /work/results/$BASE/flagged_$ARM.json --results results --pdk-root /work/pdk --jobs $JOBS ;;
  tgt*|thr*)
    # tgt050-70: top 5% of nets | thr500-70: every net with p >= 0.500 ; suffixes after H:
    #   p2 = two masked passes, f = + fanout rule, h = hold-fix delay cells protected from resizing, v3 = model tag,
    #   c = score features dumped at the checkpoint itself (deployment view)
    case "$ARM" in tgt*) K=${ARM#tgt}; SEL=frac;; thr*) K=${ARM#thr}; SEL=thr;; esac
    K=${K%%-*}; REST=${ARM##*-}; H=${REST%%[pfhvc]*}
    case "$REST" in *c*) use_checkpoint_features;; esac
    PASSES=1; case "$REST" in *p2*) PASSES=2;; esac
    RULE=""; case "$REST" in *f*) RULE="--rule-fanout";; esac
    PROT=""; case "$REST" in *h*) PROT="--protect-hold";; esac
    VAL=$(python3 -c "print(int('$K')/1000)")
    [ "$SEL" = frac ] && SELARG="--frac $VAL" || SELARG="--threshold $VAL"
    python3 -m pip install -q pandas pyarrow lightgbm scikit-learn
    python3 br/score.py --model $MODEL --run-results $SRC $SELARG $RULE --out results/$BASE/flagged_$ARM.json
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
# functional equivalence of the repaired netlist vs the baseline (targeted / threshold / rule / list arms)
case "$ARM" in tgt*|thr*|det*|lst-*|lsx-*|exp*|est*)
  if [ -f results/$BASE/final.nl.v.gz ] && [ -f results/$BASE-$ARM/final.nl.v.gz ]; then
    TOP=$(python3 -c "import json;print(json.load(open('results/$BASE/resolved.json'))['DESIGN_NAME'])")
    mkdir -p results/$BASE-$ARM/equiv
    gunzip -c results/$BASE/final.nl.v.gz > results/$BASE-$ARM/equiv/gold.nl.v
    gunzip -c results/$BASE-$ARM/final.nl.v.gz > results/$BASE-$ARM/equiv/gate.nl.v
    timeout 3000 $DOCKER python3 br/equiv.py --gold results/$BASE-$ARM/equiv/gold.nl.v --gate results/$BASE-$ARM/equiv/gate.nl.v \
      --top $TOP --liberty pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib --out results/$BASE-$ARM/equiv --timeout 2900 > results/$BASE-$ARM/equiv/run.log 2>&1 || true
    sudo chown -R "$(id -u):$(id -g)" results || true
    rm -f results/$BASE-$ARM/equiv/*.nl.v results/$BASE-$ARM/equiv/*-logic.v
    gzip -f results/$BASE-$ARM/equiv/gold.json results/$BASE-$ARM/equiv/gate.json 2>/dev/null || true
    grep -h '"status"' results/$BASE-$ARM/equiv/result.json || echo "[hero] equivalence did not finish"
  fi ;;
esac
ls results
