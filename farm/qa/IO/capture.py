"""IO1 capture: run inside `openroad -python` by capture_run.py (step IOPins.Capture, a DumpNetsSignoff subclass).

Signoff view of a finished run (final ODB, the run's own RCX SPEF for every corner, propagated clocks), the same set-up
as br/dump_nets.py in signoff mode. Writes into $STEP_DIR:
  ports.json  die/core area, pin-layer track grids, every signal port (direction, net, pin shape, edge, position, worst
              setup slack over all corners, the instance pins on its net with their coordinates)
  paths.json  `report_checks -format json` (worst over all corners): the 50 worst setup paths (one per endpoint),
              the worst path from each input port and to each output port
Read-only: writes no views.
"""
import json
import os
import sys
import time

from openroad import Design, Tech, Timing  # noqa: E402

t0 = time.time()
STEP_DIR = os.environ["STEP_DIR"]
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iolib  # noqa: E402

tech = Tech()
design = Design(tech)


def tcl(cmd):
    return design.evalTclString(cmd)


def envget(name, default=None):
    if design.evalTclString(f"info exists ::env({name})") == "1":
        return design.evalTclString(f"set ::env({name})")
    return os.environ.get(name, default)


tcl("source $::env(SCRIPTS_DIR)/openroad/common/io.tcl")
tcl("read_current_odb")
tcl("set_propagated_clock [all_clocks]")
import fnmatch  # noqa: E402

spef_map = json.load(open(envget("BR_SPEF_MAP")))
i = 0
corners = []
while envget(f"_LIB_CORNER_{i}") is not None:
    cname = envget(f"_LIB_CORNER_{i}").split()[0]
    corners.append(cname)
    for pat, path in spef_map.items():
        if fnmatch.fnmatch(cname, pat):
            tcl(f"read_spef -corner {cname} {path}")
            break
    i += 1

block = design.getBlock()
dbu = block.getDbUnitsPerMicron()
timing = Timing(design)
MAX = Timing.Max
RISE, FALL = Timing.Rise, Timing.Fall
h_layer, v_layer = envget("IO_PIN_H_LAYER", "met3"), envget("IO_PIN_V_LAYER", "met2")
H, V = tech.getDB().getTech().findLayer(h_layer), tech.getDB().getTech().findLayer(v_layer)
da, ca = block.getDieArea(), block.getCoreArea()
die = [da.xMin(), da.yMin(), da.xMax(), da.yMax()]
ox, cx, sx = block.findTrackGrid(V).getGridPatternX(0)
oy, cy, sy = block.findTrackGrid(H).getGridPatternY(0)


def slack_of(term):
    vals = []
    for rf in (RISE, FALL):
        try:
            v = timing.getPinSlack(term, rf, MAX)
            if v is not None and abs(v) < 1e10:
                vals.append(v * 1e9)
        except Exception as e:  # noqa: BLE001
            return None, f"{type(e).__name__}: {e}"
    return (min(vals) if vals else None), None


ports = {}
slack_err = None
for bt in block.getBTerms():
    if bt.getSigType() in ("POWER", "GROUND"):
        continue
    rec = {"dir": bt.getIoType(), "sigtype": bt.getSigType(), "net": None, "edge": None, "pos": None, "box": None,
           "layer": None, "cells": []}
    bps = bt.getBPins()
    if len(bps):
        b = bps[0].getBoxes()[0]
        box = [b.xMin(), b.yMin(), b.xMax(), b.yMax()]
        e = iolib.edge_of_box(box, die)
        rec.update({"edge": e, "pos": iolib.pos_along(box, e) if e else None, "box": box,
                    "layer": b.getTechLayer().getName()})
    net = bt.getNet()
    if net is not None:
        rec["net"] = net.getName()
        for it in net.getITerms():
            ok, x, y = it.getAvgXY()
            rec["cells"].append({"inst": it.getInst().getName(), "master": it.getInst().getMaster().getName(),
                                 "pin": it.getMTerm().getName(), "io": it.getIoType(),
                                 "x": x if ok else None, "y": y if ok else None})
    s, err = slack_of(bt)
    rec["slack_ns"] = s if rec["cells"] else None    # a port with no instance pin has no timing path
    rec["connected"] = bool(rec["cells"])
    slack_err = slack_err or err
    ports[bt.getName()] = rec

FIELDS = "-fields {slew cap input_pins fanout} -digits 4"   # this OpenSTA names each pin's net anyway


def checks(args):
    tcl("sta::redirect_string_begin")
    try:
        tcl(f"report_checks -path_delay max -format json {FIELDS} {args}")
    finally:
        s = tcl("sta::redirect_string_end")
    try:
        return json.loads(s[s.index("{"):])          # skip any warning lines printed before the JSON
    except Exception:  # noqa: BLE001
        return {"raw": s}


def tclname(n):
    return "{" + n + "}"


paths = {"top": checks("-group_path_count 50 -endpoint_path_count 1"), "from_input": {}, "to_output": {}}
for name, p in sorted(ports.items()):
    if p["dir"] == "INPUT":
        paths["from_input"][name] = checks(f"-from [get_ports {tclname(name)}]")
    elif p["dir"] == "OUTPUT":
        paths["to_output"][name] = checks(f"-to [get_ports {tclname(name)}]")

floor = {"dbu": dbu, "die": die, "core": [ca.xMin(), ca.yMin(), ca.xMax(), ca.yMax()],
         "tracks": {"V": {"origin": ox, "count": cx, "step": sx}, "H": {"origin": oy, "count": cy, "step": sy}},
         "layers": {"V": v_layer, "H": h_layer}, "corners": corners, "design": block.getName(),
         "clock_port": envget("CLOCK_PORT"), "slack_api_error": slack_err}
json.dump({"floor": floor, "ports": ports}, open(os.path.join(STEP_DIR, "ports.json"), "w"), indent=0)
json.dump(paths, open(os.path.join(STEP_DIR, "paths.json"), "w"))
print(f"[iopins] capture: {len(ports)} ports, {len(paths['from_input'])} input and {len(paths['to_output'])} output "
      f"path reports in {time.time() - t0:.1f}s; slack api error: {slack_err}", flush=True)
