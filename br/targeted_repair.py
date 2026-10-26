"""Run inside `openroad -python` by BeforeRoute.TargetedRepairPostGRT.

Same sequence as LibreLane's repair_design_postgrt.tcl, except that before
`repair_design` every signal net NOT listed in $BR_FLAGGED_NETS_FILE is marked
do-not-touch directly in the database (no name quoting through Tcl lists), so
the stock resizer spends its slew/cap margins only on the flagged nets.
Set BR_FLAGGED_NETS_FILE to "ALL" (or leave the file absent) to touch every net,
which reproduces the stock step exactly.
"""
import json
import os
import time

from openroad import Design, Tech  # noqa: E402

t0 = time.time()
tech = Tech()
design = Design(tech)


def tcl(cmd):
    print(f"[br] tcl> {cmd[:120]}", flush=True)
    return design.evalTclString(cmd)


def envget(name, default=None):
    if design.evalTclString(f"info exists ::env({name})") == "1":
        return design.evalTclString(f"set ::env({name})")
    return default


tcl("source $::env(SCRIPTS_DIR)/openroad/common/io.tcl")
tcl("source $::env(SCRIPTS_DIR)/openroad/common/resizer.tcl")
tcl("read_current_odb")
tcl("set_propagated_clock [all_clocks]")
tcl("set_dont_touch_objects")

flag_file = envget("BR_FLAGGED_NETS_FILE", "ALL")
block = design.getBlock()
masked = []
n_flagged_found = 0
if flag_file and flag_file != "ALL" and os.path.exists(flag_file):
    flagged = set(json.load(open(flag_file)))
    for net in block.getNets():
        if net.getSigType() in ("POWER", "GROUND"):
            continue
        if net.getName() in flagged:
            n_flagged_found += 1
        elif not net.isDoNotTouch():
            net.setDoNotTouch(True)
            masked.append(net)
    print(f"[br] mask: {len(flagged)} flagged ({n_flagged_found} found), {len(masked)} nets masked", flush=True)
else:
    print("[br] mask: none (stock behaviour)", flush=True)

tcl("source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl")
tcl("source $::env(SCRIPTS_DIR)/openroad/common/grt.tcl")
tcl("estimate_parasitics -global_routing")

args = [
    "-verbose",
    "-max_wire_length", envget("GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH", "0"),
    "-slew_margin", envget("GRT_DESIGN_REPAIR_MAX_SLEW_PCT", "10"),
    "-cap_margin", envget("GRT_DESIGN_REPAIR_MAX_CAP_PCT", "10"),
]
if envget("GRT_DESIGN_REPAIR_MAX_UTILIZATION"):
    args += ["-max_utilization", envget("GRT_DESIGN_REPAIR_MAX_UTILIZATION")]
n_inst_before = len(block.getInsts())
tcl("log_cmd repair_design " + " ".join(args))
n_inst_after = len(block.getInsts())

tcl("source $::env(SCRIPTS_DIR)/openroad/common/dpl.tcl")
for net in masked:
    net.setDoNotTouch(False)
tcl("unset_dont_touch_objects")
if envget("GRT_DESIGN_REPAIR_RUN_GRT", "1") in ("1", "true", "True"):
    tcl("source $::env(SCRIPTS_DIR)/openroad/common/grt.tcl")
tcl("write_views")

summary = {
    "flag_file": flag_file,
    "n_flagged_found": n_flagged_found,
    "n_masked": len(masked),
    "insts_before": n_inst_before,
    "insts_after": n_inst_after,
    "insts_added": n_inst_after - n_inst_before,
    "seconds": time.time() - t0,
}
json.dump(summary, open(os.path.join(os.environ["STEP_DIR"], "targeted_summary.json"), "w"), indent=1)
print(f"[br] targeted repair done: {summary}", flush=True)
