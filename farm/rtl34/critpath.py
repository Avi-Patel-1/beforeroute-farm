#!/usr/bin/env python3
"""Addendum 34: write the readable critical-path summary given to the RTL agent (argv[1] = a run artifact dir with checks/ and nets_signoff.jsonl, argv[2] = output file)."""
import json
import re
import sys

D = sys.argv[1]
OUT = sys.argv[2]
rpt = open(f"{D}/checks/max_ss_100C_1v60.checks.rpt").read().splitlines()
i = [k for k, l in enumerate(rpt) if l.startswith("Startpoint:") and "flip-flop" in l][0]
j = [k for k in range(i, len(rpt)) if "slack (" in rpt[k]][0]
blk = rpt[i:j + 1]
CELL = re.compile(r"\s+(\d+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([v^])\s+(\S+)\s+\((\S+)\)")
NET = re.compile(r"\s+(\S+) \(net\)")
rows = []          # (arrival, pin, cell, fanout, net)
cut = [k for k, l in enumerate(blk) if "data arrival time" in l][0]   # the launch side ends here; the capture clock follows
for k, l in enumerate(blk[:cut]):
    m = CELL.match(l)
    if m:
        net = None
        if k + 1 < len(blk):
            m2 = NET.match(blk[k + 1])
            net = m2.group(1) if m2 else None
        rows.append((float(m.group(5)), m.group(7), m.group(8).replace("sky130_fd_sc_hd__", ""), int(m.group(1)), net))
# the data path: from the launching flop's Q output to the endpoint D pin (first half of the report = launch side)
q = [n for n, r in enumerate(rows) if r[1].endswith("/Q")][0]
end = [n for n, r in enumerate(rows) if r[1].endswith("/D")][0] if any(r[1].endswith("/D") for r in rows) else None
data = rows[q:]
# stop at the endpoint D pin line (the report lists the D pin as an input line without fanout; keep cells up to the arrival)
val = lambda key: [l for l in blk if key in l][0].split()[0]
arr, req, sl = float(val("data arrival time")), float(val("data required time")), float(val("slack ("))
unc, setup = abs(float(val("clock uncertainty"))), abs(float(val("library setup time")))
clk_pin_arrival = rows[q - 1][0] if q > 0 else 0.0
start_flop = blk[0].split()[1]
end_flop = blk[1].split()[1]
# the endpoint net = the last net printed before the endpoint D pin
data_nets = [r[4] for r in data if r[4]]
end_net = data_nets[-1]

named = {}
masters = {}
with open(f"{D}/nets_signoff.jsonl") as f:
    for l in f:
        n = json.loads(l)
        if n.get("driver_inst"):
            masters[n["driver_inst"]] = n.get("driver_master", "")
        if n.get("sigtype") == "SIGNAL" and n.get("driver_slack_ns") is not None:
            named[n["net"]] = (n["driver_slack_ns"], n.get("driver_master", "").replace("sky130_fd_sc_hd__", ""), n.get("fanout"))
fn = json.load(open(f"{D}/final_nets.json"))
anon = re.compile(r"^(_\d+_|net\d+)$")
dnets = []
for net, v in fn["nets"].items():
    for p in v.get("pins", []):
        if "/" not in p:
            continue
        inst, pin = p.rsplit("/", 1)
        if pin == "D" and "df" in masters.get(inst, "") and net in named:
            dnets.append((named[net][0], net.replace("\\", "")))
            break
dnets.sort()
starts = sorted((s, n.replace("\\", ""), m, fo) for n, (s, m, fo) in named.items() if m.startswith("df") and not anon.match(n))

o = []
o.append("MD5 baseline run x7k-md5-004 (the setting of run x4c-md5-003, clock target 16.05 ns): signoff static timing at nine")
o.append("corners after detailed routing and parasitic extraction.")
o.append(f"Limiting corner: max_ss_100C_1v60 (slow-slow, 100 C, 1.60 V, maximum RC). Worst setup slack +{sl:.3f} ns. The worst")
o.append("path is register-to-register.")
o.append(f"Clock 16.05 ns; clock uncertainty {unc:.2f} ns; endpoint library setup time {setup:.3f} ns; the launching flop's clock pin")
o.append(f"is reached at {clk_pin_arrival:.2f} ns (clock tree), so the data path runs from {data[0][0]:.2f} ns to {arr:.2f} ns.")
o.append("")
o.append("WORST SETUP PATH at the limiting corner (signoff report_checks, one path per corner is reported):")
o.append(f"  startpoint: flop {start_flop}, output net {data[0][4].replace(chr(92), '')}")
o.append(f"  endpoint:   flop {end_flop}, D input net {end_net.replace(chr(92), '')}")
o.append(f"  arrival {arr:.3f} ns, required {req:.3f} ns, slack +{sl:.3f} ns")
o.append(f"  {len(data)} cells from the launching flop to the endpoint (arrival at the cell output in ns, cell, output net,")
o.append("  fanout):")
for t, p, c, f, net in data:
    o.append(f"    {t:7.3f}  {c:<12} {(net or '?').replace(chr(92), '')}  (fanout {f})")
o.append("")
o.append("WORST SETUP ENDPOINTS: the nets feeding flop D inputs with the lowest signoff slack (ns), worst corner. Names are the RTL")
o.append("signal names where synthesis kept them:")
for s, n in dnets[:30]:
    o.append(f"  {s:6.3f}  {n}")
o.append("")
o.append("WORST STARTPOINTS: flop output nets with the lowest signoff slack (ns), with cell type and fanout:")
for s, n, m, fo in starts[:20]:
    o.append(f"  {s:6.3f}  {n}  ({m}, fanout {fo})")
o.append("")
o.append("The endpoint and startpoint lists come from the run's per-net signoff dump: each net's slack is the worst slack of any")
o.append("path through it. Unnamed nets (_NNNNN_, netNNN) were created by synthesis or by the flow's buffering and repair.")
open(OUT, "w").write("\n".join(o) + "\n")
print("\n".join(o))
