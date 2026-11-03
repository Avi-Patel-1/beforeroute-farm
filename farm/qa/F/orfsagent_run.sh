#!/usr/bin/env bash
# F (overnight workstream F): one ORFS-agent-harness flow run, inside openroad/orfs:v3.0-1548-gce8d36a7 (ORFS ce8d36a7).
# Reproduces ORFS-agent's AutoTuner-integration job script (github.com/ABKGroup/ORFS-Agent @ 730f1fa,
# AutoTuner-integration/AutoTuner/run_or_job.sh) line for line: every knob is EXPORTED to the environment (not a make
# command-line override), the clock goes to CLK_PERIOD (read by their SDC template) and ABC_CLOCK_PERIOD_IN_PS, the
# design config is their <design>_<tech>.mk, FASTROUTE_TCL is their fastroute_<tech>.tcl, NUM_CORES=4, and the make
# target is their `tunereport` (6_report.log, 6_final.v/.sdc/.def). Their IO_PLACER exports compare the tech name in
# upper case, so with the lower-case names their runs used (TECH_asap7 / TECH_sky130hd) none applies; same here.
# Environment in: TAG DESIGN TECH PERIOD UTIL LB_ADDON TNS HIER GP_PAD DP_PAD DPO CTS_CSIZE CTS_CDIA PIN_ADJ UP_ADJ
#                 AR POWER_EFFORT RD TD RUN_TIMEOUT CFG_DIR (their autotune_configs, fetched and hash-checked)
set -uo pipefail

OUT=/work/results/$TAG
mkdir -p "$OUT/logs" "$OUT/reports"
cd /OpenROAD-flow-scripts/flow || { echo '{"status": "no_flow_dir"}' > "$OUT/run.json"; exit 2; }
# shellcheck disable=SC1091
. ../env.sh > /dev/null 2>&1 || true

export CLK_PERIOD="$PERIOD"
export ABC_CLOCK_PERIOD_IN_PS="$PERIOD"
export CORE_UTILIZATION="$UTIL"
export CORE_ASPECT_RATIO="$AR"
export PLACE_DENSITY_LB_ADDON="$LB_ADDON"
export TNS_END_PERCENT="$TNS"
export RECOVER_POWER="$POWER_EFFORT"
export SYNTH_HIERARCHICAL="$HIER"
export CELL_PAD_IN_SITES_GLOBAL_PLACEMENT="$GP_PAD"
export CELL_PAD_IN_SITES_DETAIL_PLACEMENT="$DP_PAD"
export ENABLE_DPO="$DPO"
export GPL_TIMING_DRIVEN="$TD"
export GPL_ROUTABILITY_DRIVEN="$RD"
export CTS_CLUSTER_SIZE="$CTS_CSIZE"
export CTS_CLUSTER_DIAMETER="$CTS_CDIA"
export PIN_LAYER_ADJUST="$PIN_ADJ"
export UP_LAYER_ADJUST="$UP_ADJ"
export NUM_CORES=4
export OMP_NUM_THREADS=4
export MKL_NUM_THREADS=4
export RUN_DIR="$CFG_DIR"
export FASTROUTE_TCL="$RUN_DIR/fastroute_${TECH}.tcl"
export WORK_HOME=/tmp/wh/$TAG
export FLOW_VARIANT=base
mkdir -p "$WORK_HOME"

case "$DESIGN" in aes) DNAME=aes_cipher_top ;; ibex) DNAME=ibex_core ;; *) DNAME=$DESIGN ;; esac
LOGD=$WORK_HOME/logs/$TECH/$DESIGN/base
REPD=$WORK_HOME/reports/$TECH/$DESIGN/base
RESD=$WORK_HOME/results/$TECH/$DESIGN/base

cp "$RUN_DIR/${DESIGN}_${TECH}.mk" "$OUT/config.mk"
cp "$RUN_DIR/${DNAME}.sdc" "$OUT/template.sdc"
env | grep -E '^(CLK_PERIOD|ABC_CLOCK_PERIOD_IN_PS|CORE_[A-Z_]*|PLACE_DENSITY[A-Z_]*|TNS_END_PERCENT|RECOVER_POWER|SYNTH_HIERARCHICAL|CELL_PAD_[A-Z_]*|ENABLE_DPO|GPL_[A-Z_]*|CTS_CLUSTER_[A-Z_]*|PIN_LAYER_ADJUST|UP_LAYER_ADJUST|NUM_CORES|FASTROUTE_TCL|RUN_DIR|FLOW_VARIANT)=' \
  | sort > "$OUT/env_exports.txt"
{ openroad -version 2>&1 | head -1; yosys -V 2>&1 | head -1; } > "$OUT/tool_versions.txt" || true

T0=$(date +%s)
timeout --signal=TERM --kill-after=120 "$RUN_TIMEOUT" \
  make tunereport PRIVATE_DIR="$RUN_DIR" DESIGN_CONFIG="$RUN_DIR/${DESIGN}_${TECH}.mk" > "$OUT/flow.log" 2>&1
RC=$?
T1=$(date +%s)

cp "$LOGD"/*.json "$OUT/logs/" 2>/dev/null || true
for f in "$LOGD"/*.log; do [ -f "$f" ] && gzip -c "$f" > "$OUT/logs/$(basename "$f").gz"; done
for f in "$REPD"/*; do
  [ -f "$f" ] || continue
  case "$f" in *.webp|*.png|*.jpg) continue ;; esac
  if [ "$(stat -c %s "$f")" -gt 262144 ]; then gzip -c "$f" > "$OUT/reports/$(basename "$f").gz"; else cp "$f" "$OUT/reports/"; fi
done
[ -f "$RESD/6_final.sdc" ] && cp "$RESD/6_final.sdc" "$OUT/6_final.sdc"
[ -f "$RESD/clock_period.txt" ] && cp "$RESD/clock_period.txt" "$OUT/clock_period.txt"
gzip -f "$OUT/flow.log"

STATUS=completed
{ [ "$RC" -eq 0 ] && [ -f "$LOGD/6_report.json" ]; } || STATUS=flow_error
[ "$RC" -eq 124 ] && STATUS=timeout
cat > "$OUT/run.json" <<EOF
{"tag": "$TAG", "harness": "orfsagent", "design": "$DESIGN", "platform": "$TECH", "period": $PERIOD,
 "make_rc": $RC, "status": "$STATUS", "elapsed_s": $((T1 - T0)), "started_utc": "$(date -u -d @"$T0" +%FT%TZ)"}
EOF
exit 0
