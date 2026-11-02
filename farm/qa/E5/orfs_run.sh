#!/usr/bin/env bash
# E5 (Addendum 41): one ORFS ASAP7 flow run, executed inside the pinned openroad/orfs image.
# Environment in: TAG DESIGN PERIOD NUM_CORES MAKE_VARS RUN_TIMEOUT (seconds).
# The design's own ORFS config.mk is used unchanged; knob overrides go on the make command line (as AutoTuner passes
# them) and the clock goes into a copy of the design's SDC with `set clk_period` replaced (AutoTuner's write_sdc
# substitution). The flow runs to the finish report (detailed route, OpenRCX extraction, post-route STA); GDS is not
# streamed. Outputs to /work/results/$TAG: metrics JSON, gzipped logs, reports, the SDC used, run.json.
set -uo pipefail

OUT=/work/results/$TAG
mkdir -p "$OUT/logs" "$OUT/reports"
cd /OpenROAD-flow-scripts/flow || { echo '{"status": "no_flow_dir"}' > "$OUT/run.json"; exit 2; }
# shellcheck disable=SC1091
. ../env.sh > /dev/null

case "$DESIGN" in
  aes) NICK=aes ;;
  ibex) NICK=ibex ;;
  *) NICK=$DESIGN ;;
esac
DCFG=./designs/asap7/$DESIGN/config.mk
SDC0=./designs/asap7/$DESIGN/constraint.sdc
WH=/tmp/wh/$TAG
LOGD=$WH/logs/asap7/$NICK/base
REPD=$WH/reports/asap7/$NICK/base
mkdir -p "$WH"

cp "$DCFG" "$OUT/config.mk"
cp "$SDC0" "$OUT/constraint.orig.sdc"
python3 - "$SDC0" "$OUT/constraint.sdc" "$PERIOD" <<'PY'
import re, sys
src, dst, per = sys.argv[1], sys.argv[2], sys.argv[3]
s = open(src).read()
n = len(re.findall(r"^set clk_period ", s, flags=re.M))
if n != 1:
    sys.exit(f"expected exactly one 'set clk_period' line in {src}, found {n}")
# the substitution AutoTuner's write_sdc applies for CLK_PERIOD (tools/AutoTuner/src/autotuner/utils.py)
s2 = re.sub(r"set clk_period .*\n(.*)", f"set clk_period {per}\n\\1", s)
open(dst, "w").write(s2)
PY
[ $? -eq 0 ] || { echo '{"status": "sdc_error"}' > "$OUT/run.json"; exit 2; }

# shellcheck disable=SC2086
VARS=(DESIGN_CONFIG="$DCFG" WORK_HOME="$WH" FLOW_VARIANT=base SDC_FILE="$OUT/constraint.sdc" NUM_CORES="$NUM_CORES"
      POST_FINAL_REPORT_TCL=/work/farm/qa/E5/e5_hook.tcl SHELL=bash $MAKE_VARS)
printf '%s\n' "${VARS[@]}" > "$OUT/make_vars.txt"
{ openroad -version 2>&1 | head -1; yosys -V 2>&1 | head -1; } > "$OUT/tool_versions.txt" || true

T0=$(date +%s)
timeout --signal=TERM --kill-after=120 "$RUN_TIMEOUT" make "${VARS[@]}" "$LOGD/6_report.log" > "$OUT/flow.log" 2>&1
RC=$?
T1=$(date +%s)
make "${VARS[@]}" metadata-generate > "$OUT/metadata-generate.log" 2>&1 || true

# collect: per-stage metrics JSON, logs (gzipped), reports (gzipped when large); no layouts
cp "$LOGD"/*.json "$OUT/logs/" 2>/dev/null || true
for f in "$LOGD"/*.log; do [ -f "$f" ] && gzip -c "$f" > "$OUT/logs/$(basename "$f").gz"; done
for f in "$REPD"/*; do
  [ -f "$f" ] || continue
  if [ "$(stat -c %s "$f")" -gt 262144 ]; then gzip -c "$f" > "$OUT/reports/$(basename "$f").gz"; else cp "$f" "$OUT/reports/"; fi
done
gzip -f "$OUT/flow.log"

STATUS=completed
{ [ "$RC" -eq 0 ] && [ -f "$LOGD/6_report.json" ]; } || STATUS=flow_error
[ "$RC" -eq 124 ] && STATUS=timeout
cat > "$OUT/run.json" <<EOF
{"tag": "$TAG", "design": "$DESIGN", "period": $PERIOD, "num_cores": $NUM_CORES, "make_vars": "$MAKE_VARS",
 "make_rc": $RC, "status": "$STATUS", "elapsed_s": $((T1 - T0)), "started_utc": "$(date -u -d @"$T0" +%FT%TZ)"}
EOF
exit 0
