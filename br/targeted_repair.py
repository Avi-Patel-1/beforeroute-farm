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
import re
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
tiers_file = envget("BR_FLAGGED_TIERS_FILE", "")
block = design.getBlock()

def all_signal_nets():
    return [n for n in block.getNets() if n.getSigType() not in ("POWER", "GROUND")]

# Build the tier list: each tier = (set of touchable net names, slew_pct, cap_pct).
# Plain flagged file -> one tier at the step's configured margins. "ALL"/absent -> stock behaviour.
default_slew = envget("GRT_DESIGN_REPAIR_MAX_SLEW_PCT", "10")
default_cap = envget("GRT_DESIGN_REPAIR_MAX_CAP_PCT", "10")
tiers = []
if tiers_file and os.path.exists(tiers_file):
    for t in json.load(open(tiers_file))["tiers"]:
        nets = t["nets"]
        tiers.append((None if nets == "ALL" else set(nets), str(t.get("slew_pct", default_slew)), str(t.get("cap_pct", default_cap))))
elif flag_file and flag_file != "ALL" and os.path.exists(flag_file):
    tiers.append((set(json.load(open(flag_file))), default_slew, default_cap))
else:
    tiers.append((None, default_slew, default_cap))  # None = touch everything (stock)
print(f"[br] tiers: {[(len(t[0]) if t[0] is not None else 'ALL', t[1], t[2]) for t in tiers]}", flush=True)

tcl("source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl")
tcl("source $::env(SCRIPTS_DIR)/openroad/common/grt.tcl")
tcl("estimate_parasitics -global_routing")

protect_hold = str(envget("BR_PROTECT_HOLD_CELLS", "0")).lower() in ("1", "true")
protected = []
if protect_hold:
    for inst in block.getInsts():
        m = inst.getMaster().getName()
        if inst.getName().startswith("hold") or "clkdlybuf" in m or "dlygate" in m:
            if not inst.isDoNotTouch():
                inst.setDoNotTouch(True)
                protected.append(inst)
    print(f"[br] protected {len(protected)} hold-fix delay cells from resizing", flush=True)

restore = str(envget("BR_HOLD_FAMILY_RESTORE", "0")).lower() in ("1", "true")
FAMILY_RE = re.compile(r"^(sky130_fd_sc_hd__clkdlybuf4s(?:15|18|25|50))_1$")
REVERTIBLE = {"sky130_fd_sc_hd__buf_1", "sky130_fd_sc_hd__buf_2", "sky130_fd_sc_hd__clkbuf_1", "sky130_fd_sc_hd__clkbuf_2"}
family_before = {}
if restore:
    for inst in block.getInsts():
        m = FAMILY_RE.match(inst.getMaster().getName())
        if m:
            family_before[inst.getName()] = m.group(1)
    print(f"[br] hold-family restore armed: {len(family_before)} delay cells recorded", flush=True)

n_inst_before = len(block.getInsts())
tier_summaries = []
n_flagged_found = 0
n_masked = 0
for ti, (allowed, slew_pct, cap_pct) in enumerate(tiers):
    masked = []
    found = 0
    if allowed is not None:
        for net in all_signal_nets():
            if net.getName() in allowed:
                found += 1
            elif not net.isDoNotTouch():
                net.setDoNotTouch(True)
                masked.append(net)
    n_flagged_found += found
    n_masked = max(n_masked, len(masked))
    args = [
        "-verbose",
        "-max_wire_length", envget("GRT_DESIGN_REPAIR_MAX_WIRE_LENGTH", "0"),
        "-slew_margin", slew_pct,
        "-cap_margin", cap_pct,
    ]
    if envget("GRT_DESIGN_REPAIR_MAX_UTILIZATION"):
        args += ["-max_utilization", envget("GRT_DESIGN_REPAIR_MAX_UTILIZATION")]
    before = len(block.getInsts())
    if ti > 0:
        # re-route and re-estimate after the previous tier's edits and legalization
        tcl("source $::env(SCRIPTS_DIR)/openroad/common/grt.tcl")
        tcl("estimate_parasitics -global_routing")
    n_passes = int(envget("BR_REPAIR_PASSES", "1") or 1)
    for pi in range(n_passes):
        if pi > 0:
            # second pass on the same eligible set: re-route, re-estimate, repair what pass 1 created
            tcl("source $::env(SCRIPTS_DIR)/openroad/common/grt.tcl")
            tcl("estimate_parasitics -global_routing")
        tcl("log_cmd repair_design " + " ".join(args))
        tcl("source $::env(SCRIPTS_DIR)/openroad/common/dpl.tcl")
    for net in masked:
        net.setDoNotTouch(False)
    tier_summaries.append({"tier": ti, "allowed": (len(allowed) if allowed is not None else "ALL"), "found": found,
                           "masked": len(masked), "slew_pct": slew_pct, "cap_pct": cap_pct, "passes": n_passes,
                           "insts_added": len(block.getInsts()) - before})
    print(f"[br] tier {ti}: allowed={len(allowed) if allowed is not None else 'ALL'} found={found} masked={len(masked)} margins={slew_pct}/{cap_pct} insts_added={len(block.getInsts()) - before}", flush=True)
for inst in protected:
    inst.setDoNotTouch(False)
family = {"recorded": len(family_before), "restored": 0, "resized_stronger": 0, "kept": 0, "removed": 0, "to": {}}
if restore:
    db = tech.getDB()
    for name, fam in family_before.items():
        inst = block.findInst(name)
        if inst is None:
            family["removed"] += 1
            continue
        now = inst.getMaster().getName()
        if now == fam + "_1":
            family["kept"] += 1
            continue
        if now in REVERTIBLE:
            target = db.findMaster(fam + "_2")
            if target is not None and inst.swapMaster(target):
                family["restored"] += 1
                family["to"][now] = family["to"].get(now, 0) + 1
                continue
        family["resized_stronger"] += 1
    print(f"[br] hold-family restore: {family}", flush=True)
    if family["restored"]:
        tcl("source $::env(SCRIPTS_DIR)/openroad/common/dpl.tcl")  # the _2 cells can be wider than the buffers they replace
n_inst_after = len(block.getInsts())
tcl("unset_dont_touch_objects")
if envget("GRT_DESIGN_REPAIR_RUN_GRT", "1") in ("1", "true", "True"):
    tcl("source $::env(SCRIPTS_DIR)/openroad/common/grt.tcl")
tcl("write_views")

summary = {
    "flag_file": flag_file,
    "tiers_file": tiers_file,
    "tiers": tier_summaries,
    "n_flagged_found": n_flagged_found,
    "n_masked": n_masked,
    "protected_hold_cells": len(protected),
    "hold_family_restore": family,
    "insts_before": n_inst_before,
    "insts_after": n_inst_after,
    "insts_added": n_inst_after - n_inst_before,
    "seconds": time.time() - t0,
}
json.dump(summary, open(os.path.join(os.environ["STEP_DIR"], "targeted_summary.json"), "w"), indent=1)
print(f"[br] targeted repair done: {summary}", flush=True)
