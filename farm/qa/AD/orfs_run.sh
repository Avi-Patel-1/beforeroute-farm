#!/usr/bin/env bash
# AD (TrueClock overnight, experiments A and D): one ORFS flow run, executed inside the pinned openroad/orfs image.
# Derived from farm/qa/E5/orfs_run.sh (Addendum 41, frozen) with four additions:
#   - PLATFORM (asap7, sky130hd or gt2n; all three ship in the same pinned image); the design's own ORFS config.mk
#     and constraint.sdc for that platform are used unchanged;
#   - the clock target arrives in ps (PERIOD_PS) and is written into the SDC in the platform's time unit
#     (ns for sky130hd, ps for asap7 and gt2n), with AutoTuner's write_sdc substitution as in E5;
#   - AD_ABC_D=1 (T2b only): ABC is told the clock target (see the patch block below);
#   - AD_RETIME=1 (T3 only): the read-only report hook also re-times the finished layout (ad_hook.tcl).
# Environment in: TAG DESIGN PLATFORM PERIOD_PS NUM_CORES MAKE_VARS RUN_TIMEOUT (s) [AD_ABC_D] [AD_RETIME]
#                 [MAKE_STOP=synth] (smoke only: stop after synthesis).
# Outputs to /work/results/$TAG: metrics JSON, gzipped logs, reports, the SDC used, run.json. No layouts.
set -uo pipefail

OUT=/work/results/$TAG
mkdir -p "$OUT/logs" "$OUT/reports"
cd /OpenROAD-flow-scripts/flow || { echo '{"status": "no_flow_dir"}' > "$OUT/run.json"; exit 2; }
# shellcheck disable=SC1091
. ../env.sh > /dev/null

PLATFORM=${PLATFORM:-asap7}
case "$PLATFORM" in
  sky130hd) UNIT_PS=1000 ;;      # sky130hd liberty/SDC time unit: ns
  asap7|gt2n) UNIT_PS=1 ;;       # ps
  *) echo '{"status": "bad_platform"}' > "$OUT/run.json"; exit 2 ;;
esac
NICK=$DESIGN
DCFG=./designs/$PLATFORM/$DESIGN/config.mk
SDC0=./designs/$PLATFORM/$DESIGN/constraint.sdc
[ -f "$DCFG" ] || { echo '{"status": "no_design_config"}' > "$OUT/run.json"; exit 2; }
WH=/tmp/wh/$TAG
LOGD=$WH/logs/$PLATFORM/$NICK/base
REPD=$WH/reports/$PLATFORM/$NICK/base
mkdir -p "$WH"

cp "$DCFG" "$OUT/config.mk"
cp "$SDC0" "$OUT/constraint.orig.sdc"
PERIOD_U=$(python3 -c "import sys; ps=int(sys.argv[1]); u=int(sys.argv[2]); print(ps if u == 1 else '%.3f' % (ps / u))" "$PERIOD_PS" "$UNIT_PS")
python3 - "$SDC0" "$OUT/constraint.sdc" "$PERIOD_U" <<'PY'
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

# ---- T2b: ABC is told the clock target (AD_ABC_D=1). Applied to this run's fresh container only.
# Yosys substitutes the delay target given with `abc -D` / `abc_new -D` only where the string {D} occurs in an inline
# ("+"-prefixed) ABC script; ORFS's ABC scripts are files without {D}, so `-D` alone would change nothing. The patch
# therefore (1) appends `-D <target ps>` to abc_args in synth_preamble.tcl, and (2) passes ORFS's own ABC script inline
# with {D} appended to the commands that take a delay target (&nf, upsize, dnsize; the places Yosys's built-in
# script puts {D}): in synth_preamble.tcl for the `abc` path, in synth.tcl (scratchpad abc9.script) for the
# `abc_new` path, and in synth_wrap_operators.tcl for the arithmetic-operator modules. Nothing else changes.
AD_ABC_D=${AD_ABC_D:-0}
if [ "$AD_ABC_D" = "1" ]; then
  export AD_ABC_D_PS=$PERIOD_PS
  python3 - <<'PY' > "$OUT/ad_abc_patch.txt" 2>&1
import sys
S = "/OpenROAD-flow-scripts/flow/scripts/"
def patch(fn, old, new):
    p = S + fn
    s = open(p).read()
    if s.count(old) != 1:
        print(f"PATCH FAILED: {fn}: anchor found {s.count(old)} times"); sys.exit(3)
    open(p, "w").write(s.replace(old, new))
    print(f"patched {fn}")
old = ("set abc_args [list -script $abc_script \\\n"
       "  {*}$lib_args {*}$lib_dont_use_args -constr $::env(OBJECTS_DIR)/abc.constr]\n")
new = old + r'''
# --- AD (TrueClock T2b): ABC is told the clock target -----------------------------------------
proc ad_inline_abc_script { path } {
  set fh [open $path r]
  set txt [read $fh]
  close $fh
  set cmds {}
  foreach line [split $txt "\n"] {
    set line [string trim $line]
    if { $line eq "" || [string index $line 0] eq "#" } { continue }
    set w [lindex [split $line " "] 0]
    if { $w eq "&nf" || $w eq "upsize" || $w eq "dnsize" } { append line " {D}" }
    lappend cmds [string map {" " ","} $line]
  }
  return "+[join $cmds {;}]"
}
if { [info exists ::env(AD_ABC_D_PS)] && $::env(AD_ABC_D_PS) ne "" } {
  set ad_inline [ad_inline_abc_script $abc_script]
  lset abc_args 1 $ad_inline
  lappend abc_args -D $::env(AD_ABC_D_PS)
  puts "AD-ABC-D: delay target $::env(AD_ABC_D_PS) ps; abc script inline: $ad_inline"
}
# ----------------------------------------------------------------------------------------------
'''
patch("synth_preamble.tcl", old, new)
old2 = "  scratchpad -set abc9.script $::env(SCRIPTS_DIR)/abc_speed_gia_only.script\n"
new2 = ("  if { [info exists ::env(AD_ABC_D_PS)] && $::env(AD_ABC_D_PS) ne \"\" } {\n"
        "    set ad_s9 [ad_inline_abc_script $::env(SCRIPTS_DIR)/abc_speed_gia_only.script]\n"
        "    puts \"AD-ABC-D: abc_new script inline: $ad_s9\"\n"
        "    scratchpad -set abc9.script $ad_s9\n"
        "  } else {\n"
        "  scratchpad -set abc9.script $::env(SCRIPTS_DIR)/abc_speed_gia_only.script\n"
        "  }\n")
patch("synth.tcl", old2, new2)
old3 = 'setattr -mod -set abc9_script {"+&dch;&nf -R 5;"} A:arithmetic_operator\n'
new3 = ('if { [info exists ::env(AD_ABC_D_PS)] && $::env(AD_ABC_D_PS) ne "" } {\n'
        '  setattr -mod -set abc9_script {"+&dch;&nf -R 5 {D};"} A:arithmetic_operator\n'
        '} else {\n'
        'setattr -mod -set abc9_script {"+&dch;&nf -R 5;"} A:arithmetic_operator\n'
        '}\n')
patch("synth_wrap_operators.tcl", old3, new3)
PY
  [ $? -eq 0 ] || { echo '{"status": "abc_patch_failed"}' > "$OUT/run.json"; exit 2; }
fi

# shellcheck disable=SC2086
VARS=(DESIGN_CONFIG="$DCFG" WORK_HOME="$WH" FLOW_VARIANT=base SDC_FILE="$OUT/constraint.sdc" NUM_CORES="$NUM_CORES"
      POST_FINAL_REPORT_TCL=/work/farm/qa/AD/ad_hook.tcl SHELL=bash $MAKE_VARS)
printf '%s\n' "${VARS[@]}" > "$OUT/make_vars.txt"
{ openroad -version 2>&1 | head -1; yosys -V 2>&1 | head -1; } > "$OUT/tool_versions.txt" || true

export AD_PERIOD_U=$PERIOD_U AD_UNIT_PS=$UNIT_PS AD_RESULTS_DIR=$OUT AD_RETIME=${AD_RETIME:-0}
TARGET="$LOGD/6_report.log"
[ "${MAKE_STOP:-}" = "synth" ] && TARGET="$WH/results/$PLATFORM/$NICK/base/1_synth.odb"
T0=$(date +%s)
timeout --signal=TERM --kill-after=120 "$RUN_TIMEOUT" make "${VARS[@]}" "$TARGET" > "$OUT/flow.log" 2>&1
RC=$?
T1=$(date +%s)
make "${VARS[@]}" metadata-generate > "$OUT/metadata-generate.log" 2>&1 || true

# collect: per-stage metrics JSON, logs (gzipped), reports (gzipped when large); no layouts
cp "$LOGD"/*.json "$OUT/logs/" 2>/dev/null || true
for f in "$LOGD"/*.log; do [ -f "$f" ] && gzip -c "$f" > "$OUT/logs/$(basename "$f").gz"; done
for f in "$REPD"/*; do
  [ -f "$f" ] || continue
  case "$f" in *.webp|*.png|*.jpg) continue ;; esac   # layout renderings: not collected
  if [ "$(stat -c %s "$f")" -gt 262144 ]; then gzip -c "$f" > "$OUT/reports/$(basename "$f").gz"; else cp "$f" "$OUT/reports/"; fi
done
gzip -f "$OUT/flow.log"
# the synthesized netlist's hash and the AD-ABC-D evidence lines (T2b: proof that ABC saw the target)
SYN=$WH/results/$PLATFORM/$NICK/base/1_2_yosys.v          # Yosys path: ABC's mapped netlist
[ -f "$SYN" ] || SYN=$WH/results/$PLATFORM/$NICK/base/1_synth.v   # OpenROAD syn path
NETSHA=$( [ -f "$SYN" ] && sha1sum "$SYN" | cut -c1-40 || echo none)
DHITS=0
for f in "$LOGD"/1_*.log; do [ -f "$f" ] && DHITS=$((DHITS + $(grep -c -- "-D $PERIOD_PS" "$f" || true))); done
grep -h "AD-ABC-D" "$LOGD"/1_*.log 2>/dev/null | cut -c1-600 > "$OUT/ad_abc_evidence.txt" || true

STATUS=completed
{ [ "$RC" -eq 0 ] && [ -f "$TARGET" ]; } || STATUS=flow_error
[ "$RC" -eq 124 ] && STATUS=timeout
[ "${MAKE_STOP:-}" = "synth" ] && [ "$STATUS" = completed ] && STATUS=synth_only
cat > "$OUT/run.json" <<EOF
{"tag": "$TAG", "design": "$DESIGN", "platform": "$PLATFORM", "period_ps": $PERIOD_PS, "period_sdc": "$PERIOD_U",
 "time_unit_ps": $UNIT_PS, "num_cores": $NUM_CORES, "make_vars": "$MAKE_VARS", "ad_abc_d": $AD_ABC_D,
 "ad_retime": ${AD_RETIME:-0}, "synth_netlist_sha1": "$NETSHA", "abc_d_log_hits": $DHITS,
 "make_rc": $RC, "status": "$STATUS", "elapsed_s": $((T1 - T0)), "started_utc": "$(date -u -d @"$T0" +%FT%TZ)"}
EOF
exit 0
