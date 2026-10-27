#!/usr/bin/env python3
"""Mapped-netlist equivalence: baseline final netlist (gold) vs an arm's final netlist (gate).

Usage: equiv.py --gold <base>/final/nl/<top>.nl.v --gate <arm>/final/nl/<top>.nl.v --top picorv32
                --liberty <tt lib> --out results/<arm>/equiv [--seq 8]
Recipe (same shape as the AfterClock checker): functional Liberty models, prep -flatten,
clk2fflogic, equiv_make/equiv_simple/equiv_induct, equiv_status -assert. Scope: mapped vs
mapped under an implicit global clock with zero-delay cell models; not RTL equivalence,
not timing.
"""
import argparse, json, os, subprocess, sys, time

ap = argparse.ArgumentParser()
ap.add_argument("--gold", required=True); ap.add_argument("--gate", required=True)
ap.add_argument("--top", required=True); ap.add_argument("--liberty", required=True)
ap.add_argument("--out", required=True); ap.add_argument("--seq", type=int, default=8)
ap.add_argument("--timeout", type=int, default=3600)
ap.add_argument("--negative-control", action="store_true", help="corrupt one gate of the gate netlist (nand2 -> nor2) and expect NOT PROVED")
a = ap.parse_args()
os.makedirs(a.out, exist_ok=True)
lib = os.path.abspath(a.liberty)
t0 = time.time()
def run(name, script):
    path = os.path.join(a.out, name + ".ys"); open(path, "w").write(script)
    r = subprocess.run(["yosys", "-q", "-l", os.path.join(a.out, name + ".log"), "-s", path], capture_output=True, text=True, timeout=a.timeout)
    return r.returncode
import re
PHYS = re.compile(r"^\s*sky130_fd_sc_hd__(tapvpwrvgnd|fill|decap|diode)\w*\s+\S+\s*\(", re.M)
def strip_physical(src, dst):
    """Drop physical-only cells (tap, fill, decap, antenna diodes) that have no logic function."""
    txt = open(src).read()
    out, i, dropped = [], 0, 0
    for m in PHYS.finditer(txt):
        end = txt.index(");", m.end()) + 2
        out.append(txt[i:m.start()]); i = end; dropped += 1
    out.append(txt[i:])
    open(dst, "w").write("".join(out))
    return dropped
rc = {}
for side, nl in (("gold", a.gold), ("gate", a.gate)):
    nl_f = os.path.join(a.out, side + "-logic.v")
    rc[side + "_physical_cells_dropped"] = strip_physical(nl, nl_f)
    if side == "gate" and a.negative_control:
        txt = open(nl_f).read()
        i = txt.find("sky130_fd_sc_hd__nand2_2 ")
        assert i >= 0, "no nand2_2 instance to corrupt"
        txt = txt[:i] + "sky130_fd_sc_hd__nor2_2 " + txt[i + len("sky130_fd_sc_hd__nand2_2 "):]
        open(nl_f, "w").write(txt)
        rc["negative_control"] = "one nand2_2 instance replaced by nor2_2 in the gate netlist"
    rc[side] = run(side, f"""read_liberty -ignore_miss_func -ignore_miss_dir -ignore_miss_data_latch {lib}
read_verilog {nl_f}
hierarchy -check -top {a.top}
prep -top {a.top} -flatten
opt -full
clk2fflogic
opt -full
clean
check -assert
rename {a.top} {side}
write_json {os.path.join(a.out, side + '.json')}
""")
rc["equiv"] = run("equiv", f"""read_json {os.path.join(a.out, 'gold.json')}
read_json {os.path.join(a.out, 'gate.json')}
equiv_make gold gate equiv
hierarchy -top equiv
equiv_simple -seq 2
equiv_induct -undef -seq {a.seq}
equiv_status -assert
""") if rc["gold"] == 0 and rc["gate"] == 0 else -1
res = {"gold": a.gold, "gate": a.gate, "top": a.top, "returncodes": rc, "seconds": time.time() - t0,
       "status": "PROVED" if rc.get("equiv") == 0 else "NOT PROVED", "negative_control": bool(a.negative_control),
       "scope": "mapped vs mapped, functional Liberty, clk2fflogic implicit global clock, zero delay; not RTL-level, not timing"}
try:
    log = open(os.path.join(a.out, "equiv.log")).read()
    res["log_lines"] = [l.strip()[:200] for l in log.splitlines() if "Found" in l or "unproven" in l.lower() or "Equivalence" in l or "proven" in l.lower()][-12:]
except Exception:
    pass
json.dump(res, open(os.path.join(a.out, "result.json"), "w"), indent=1)
print(json.dumps(res, indent=1)[:1500])
sys.exit(0 if (res['status']=='PROVED') != a.negative_control else 1)
