"""Run inside `openroad -python` by the BeforeRoute.DumpNetsPostGRT step.

Recreates the post-global-route repair view exactly as LibreLane's
repair_design_postgrt.tcl does (read_current_odb, propagated clocks, layer RC,
global route, estimate_parasitics -global_routing), then writes one JSON line per
signal net to $STEP_DIR/nets.jsonl with topology and the timer's own view
(estimated slews, caps, limits, slack) across the step's corners.
"""
import json
import math
import os
import re
import sys
import time

from openroad import Design, Tech, Timing  # noqa: E402

t0 = time.time()
STEP_DIR = os.environ["STEP_DIR"]
OUT = os.path.join(STEP_DIR, "nets.jsonl")  # (signoff mode writes nets_signoff.jsonl, see below)
SUMMARY = os.path.join(STEP_DIR, "dump_summary.json")

tech = Tech()
design = Design(tech)


def tcl(cmd):
    print(f"[br] tcl> {cmd}", flush=True)
    return design.evalTclString(cmd)


def envget(name, default=None):
    """Config variables reach Tcl's ::env but not Python's os.environ in openroad -python."""
    if design.evalTclString(f"info exists ::env({name})") == "1":
        return design.evalTclString(f"set ::env({name})")
    return os.environ.get(name, default)


def envfloat(name):
    v = envget(name)
    try:
        return float(v)
    except (TypeError, ValueError):
        return float("nan")


tcl("source $::env(SCRIPTS_DIR)/openroad/common/io.tcl")
tcl("read_current_odb")
sdc_max_tran_ns = envfloat("MAX_TRANSITION_CONSTRAINT")
sdc_max_cap_pf = envfloat("MAX_CAPACITANCE_CONSTRAINT")
sdc_max_fanout = envfloat("MAX_FANOUT_CONSTRAINT")
tcl("set_propagated_clock [all_clocks]")
BR_MODE = envget("BR_MODE", "postgrt")
if BR_MODE == "signoff":
    # read the extracted parasitics (RCX SPEF) for every corner: the signoff view
    import fnmatch
    spef_map = json.load(open(envget("BR_SPEF_MAP")))
    i = 0
    while envget(f"_LIB_CORNER_{i}") is not None:
        cname = envget(f"_LIB_CORNER_{i}").split()[0]
        for pat, path in spef_map.items():
            if fnmatch.fnmatch(cname, pat):
                tcl(f"read_spef -corner {cname} {path}")
                break
        i += 1
else:
    tcl("source $::env(SCRIPTS_DIR)/openroad/common/set_rc.tcl")
    tcl("source $::env(SCRIPTS_DIR)/openroad/common/grt.tcl")
    tcl("estimate_parasitics -global_routing")
t_setup = time.time() - t0

block = design.getBlock()
if block is None:
    print("[br] ERROR: no block after read_current_odb", file=sys.stderr)
    sys.exit(1)
dbu = block.getDbUnitsPerMicron()
timing = Timing(design)
# Corner objects carry no name binding here; the step defined the corners from
# _LIB_CORNER_<i> (first token = corner name), so resolve them by name.
corner_names = []
i = 0
while envget(f"_LIB_CORNER_{i}") is not None:
    corner_names.append(envget(f"_LIB_CORNER_{i}").split()[0])
    i += 1
corners = []
for cn in corner_names:
    c = timing.findCorner(cn)
    if c is None:
        print(f"[br] WARNING: corner {cn} not found in timer", flush=True)
    else:
        corners.append(c)
if not corners:
    corners = timing.getCorners()
    corner_names = [f"corner{i}" for i in range(len(corners))]
corner_of = dict(zip(corner_names, corners))
print(f"[br] corners: {corner_names}", flush=True)

MAX = Timing.Max
RISE, FALL = Timing.Rise, Timing.Fall




def um(v):
    return v / dbu


def safe(fn, *a, default=None):
    try:
        v = fn(*a)
        if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
            return default
        return v
    except Exception:
        return default


# ---- placement density grid (core area, NBIN x NBIN) ------------------------
core = block.getCoreArea()
cx0, cy0, cx1, cy1 = core.xMin(), core.yMin(), core.xMax(), core.yMax()
NBIN = 48
bw = max(1, (cx1 - cx0) // NBIN + 1)
bh = max(1, (cy1 - cy0) // NBIN + 1)
grid = [[0.0] * NBIN for _ in range(NBIN)]
total_inst_area = 0.0
inst_count = 0
for inst in block.getInsts():
    m = inst.getMaster()
    if m.isFiller() or m.getType() in ("CORE_SPACER",):
        continue
    bb = inst.getBBox()
    if bb is None:
        continue
    x0, y0, x1, y1 = bb.xMin(), bb.yMin(), bb.xMax(), bb.yMax()
    area = (x1 - x0) * (y1 - y0)
    total_inst_area += area
    inst_count += 1
    i0 = max(0, min(NBIN - 1, (x0 - cx0) // bw))
    i1 = max(0, min(NBIN - 1, (x1 - cx0) // bw))
    j0 = max(0, min(NBIN - 1, (y0 - cy0) // bh))
    j1 = max(0, min(NBIN - 1, (y1 - cy0) // bh))
    n = (i1 - i0 + 1) * (j1 - j0 + 1)
    share = area / n
    for i in range(int(i0), int(i1) + 1):
        for j in range(int(j0), int(j1) + 1):
            grid[i][j] += share
bin_area = float(bw * bh)
core_area = float((cx1 - cx0) * (cy1 - cy0))


def density_over(x0, y0, x1, y1):
    i0 = max(0, min(NBIN - 1, (x0 - cx0) // bw))
    i1 = max(0, min(NBIN - 1, (x1 - cx0) // bw))
    j0 = max(0, min(NBIN - 1, (y0 - cy0) // bh))
    j1 = max(0, min(NBIN - 1, (y1 - cy0) // bh))
    vals = []
    for i in range(int(i0), int(i1) + 1):
        for j in range(int(j0), int(j1) + 1):
            vals.append(grid[i][j] / bin_area)
    if not vals:
        return None, None
    return sum(vals) / len(vals), max(vals)


# ---- per-net dump -----------------------------------------------------------
n_written = 0
n_skipped = 0
if BR_MODE == "signoff":
    OUT = os.path.join(STEP_DIR, "nets_signoff.jsonl")
with open(OUT, "w") as fh:
    for net in block.getNets():
        st = net.getSigType()
        if st in ("POWER", "GROUND"):
            n_skipped += 1
            continue
        iterms = net.getITerms()
        bterms = net.getBTerms()
        drv_it = None
        loads_it = []
        for it in iterms:
            io = it.getIoType()
            if io == "OUTPUT" or (io == "INOUT" and drv_it is None):
                if drv_it is None:
                    drv_it = it
                else:
                    loads_it.append(it)  # multi-driver oddity: keep the first as driver
            else:
                loads_it.append(it)
        drv_bt = None
        loads_bt = []
        for bt in bterms:
            if bt.getIoType() == "INPUT":
                drv_bt = bt
            else:
                loads_bt.append(bt)

        pts = []
        row = {
            "net": net.getName(),
            "sigtype": st,
            "is_clock": 1 if st == "CLOCK" else 0,
            "fanout": len(loads_it) + len(loads_bt),
            "n_load_ports": len(loads_bt),
        }

        # driver
        if drv_it is not None:
            inst = drv_it.getInst()
            mt = drv_it.getMTerm()
            master = inst.getMaster()
            ok, x, y = drv_it.getAvgXY()
            if ok:
                pts.append((x, y))
            row.update(
                {
                    "driver_kind": "inst",
                    "driver_inst": inst.getName(),
                    "driver_pin": mt.getName(),
                    "driver_master": master.getName(),
                    "driver_x_um": um(x) if ok else None,
                    "driver_y_um": um(y) if ok else None,
                    "driver_slew_ns": (safe(timing.getPinSlew, drv_it, MAX) or 0.0) * 1e9,
                    "driver_slew_limit_lib_ns": (safe(timing.getMaxSlewLimit, mt) or float("nan")) * 1e9,
                    "driver_cap_limit_lib_pf": (safe(timing.getMaxCapLimit, mt) or float("nan")) * 1e12,
                    "driver_slack_ns": min(
                        safe(timing.getPinSlack, drv_it, RISE, MAX, default=1e9),
                        safe(timing.getPinSlack, drv_it, FALL, MAX, default=1e9),
                    )
                    * 1e9,
                }
            )
        elif drv_bt is not None:
            x, y = 0, 0
            ok, x, y = drv_bt.getFirstPinLocation()
            if ok:
                pts.append((x, y))
            row.update(
                {
                    "driver_kind": "port",
                    "driver_inst": None,
                    "driver_pin": drv_bt.getName(),
                    "driver_master": None,
                    "driver_x_um": um(x) if ok else None,
                    "driver_y_um": um(y) if ok else None,
                    "driver_slew_ns": (safe(timing.getPinSlew, drv_bt, MAX) or 0.0) * 1e9,
                    "driver_slew_limit_lib_ns": None,
                    "driver_cap_limit_lib_pf": None,
                    "driver_slack_ns": None,
                }
            )
        else:
            row.update({"driver_kind": "none"})

        # loads
        load_keys = []
        worst_load_slew = 0.0
        worst_load_slew_ratio = 0.0
        load_lim_min = None
        pin_cap_by_corner = {}
        for it in loads_it:
            inst = it.getInst()
            mt = it.getMTerm()
            ok, x, y = it.getAvgXY()
            if ok:
                pts.append((x, y))
            load_keys.append(f"{inst.getName()}/{mt.getName()}")
            s = (safe(timing.getPinSlew, it, MAX) or 0.0) * 1e9
            lim = safe(timing.getMaxSlewLimit, mt)
            lim_ns = lim * 1e9 if lim else None
            eff = min([v for v in (lim_ns, sdc_max_tran_ns) if v and not math.isnan(v)] or [float("nan")])
            if s > worst_load_slew:
                worst_load_slew = s
            if eff and not math.isnan(eff) and eff > 0 and s / eff > worst_load_slew_ratio:
                worst_load_slew_ratio = s / eff
            if lim_ns is not None and (load_lim_min is None or lim_ns < load_lim_min):
                load_lim_min = lim_ns
            for cn, c in corner_of.items():
                pc = safe(timing.getPortCap, it, c, MAX, default=0.0) or 0.0
                pin_cap_by_corner[cn] = pin_cap_by_corner.get(cn, 0.0) + pc
        for bt in loads_bt:
            ok, x, y = bt.getFirstPinLocation()
            if ok:
                pts.append((x, y))
            load_keys.append(f"PORT:{bt.getName()}")

        # geometry
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
            dmean, dmax = density_over(x0, y0, x1, y1)
            row.update(
                {
                    "hpwl_um": um((x1 - x0) + (y1 - y0)),
                    "bbox_w_um": um(x1 - x0),
                    "bbox_h_um": um(y1 - y0),
                    "density_mean": dmean,
                    "density_max": dmax,
                }
            )
        # global-route guides
        glen = {}
        gtot = 0
        try:
            for g in net.getGuides():
                b = g.getBox()
                L = (b.xMax() - b.xMin()) + (b.yMax() - b.yMin())
                ln = g.getLayer().getName()
                glen[ln] = glen.get(ln, 0) + L
                gtot += L
        except Exception:
            pass
        row["guide_len_um"] = um(gtot)
        row["guide_len_by_layer_um"] = {k: um(v) for k, v in glen.items()}

        # net capacitance per corner (timer's estimate incl. wire)
        netcap = {}
        for cn, c in corner_of.items():
            v = safe(timing.getNetCap, net, c, MAX)
            if v is not None:
                netcap[cn] = v * 1e12
        row["net_cap_pf_by_corner"] = netcap
        row["net_cap_pf_max"] = max(netcap.values()) if netcap else None
        row["pin_cap_pf_by_corner"] = {k: v * 1e12 for k, v in pin_cap_by_corner.items()}
        row["pin_cap_pf_max"] = max(pin_cap_by_corner.values()) * 1e12 if pin_cap_by_corner else 0.0

        # the tool's own view: ratios to effective limits
        dl = row.get("driver_slew_limit_lib_ns")
        eff_d = min([v for v in (dl, sdc_max_tran_ns) if v and not math.isnan(v)] or [float("nan")])
        ds = row.get("driver_slew_ns") or 0.0
        row["driver_slew_ratio"] = (ds / eff_d) if eff_d and not math.isnan(eff_d) and eff_d > 0 else None
        row["worst_load_slew_ns"] = worst_load_slew
        row["worst_load_slew_ratio"] = worst_load_slew_ratio
        cl = row.get("driver_cap_limit_lib_pf")
        eff_c = min([v for v in (cl, sdc_max_cap_pf) if v and not math.isnan(v)] or [float("nan")])
        nc = row.get("net_cap_pf_max") or 0.0
        row["cap_ratio"] = (nc / eff_c) if eff_c and not math.isnan(eff_c) and eff_c > 0 else None
        row["fanout_ratio"] = (row["fanout"] / sdc_max_fanout) if sdc_max_fanout and not math.isnan(sdc_max_fanout) else None
        row["load_keys"] = load_keys

        fh.write(json.dumps(row) + "\n")
        n_written += 1

summary = {
    "mode": BR_MODE,
    "design": block.getName(),
    "nets_written": n_written,
    "nets_skipped_pg": n_skipped,
    "corners": corner_names,
    "inst_count": inst_count,
    "core_area_um2": core_area / (dbu * dbu),
    "utilization": (total_inst_area / core_area) if core_area else None,
    "sdc_max_transition_ns": sdc_max_tran_ns,
    "sdc_max_capacitance_pf": sdc_max_cap_pf,
    "sdc_max_fanout": sdc_max_fanout,
    "setup_seconds": t_setup,
    "total_seconds": time.time() - t0,
}
with open(SUMMARY, "w") as fh:
    json.dump(summary, fh, indent=1)
print(f"[br] wrote {n_written} nets to {OUT} in {time.time() - t0:.1f}s", flush=True)
