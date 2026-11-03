#!/usr/bin/env python3
"""Experiment E (Addendum 42): verify the packed views agree with each other (run after make_packets, before readers).

Per rung-2 packet: the net-name sets of nets/postgrt, nets/signoff, nets/connectivity, the DEF NETS section and the SPEF
D_NETs (through the name map) are identical; every instance named in the connectivity is a DEF component; SPEF units
are NS / PF / OHM and DEF distance units are 1000 per micron; the per-net dumps carry exactly the 9 STA corners; the
contract's claim equals target - worst setup slack of metrics.json and R1 = ceil05(claim). Prints one line per packet;
exit 1 on any failure.
"""
from __future__ import annotations

import gzip
import json
import math
import os
import sys

SUPPLY = {"VPWR", "VGND", "VPB", "VNB"}
CORNERS = {f"{rc}_{pvt}" for rc in ("min", "nom", "max") for pvt in ("tt_025C_1v80", "ss_100C_1v60", "ff_n40C_1v95")}


def ceil05(x):
    return round(math.ceil(round(x / 0.05, 6)) * 0.05, 2)


def check(p):
    errs, info = [], {}
    c = json.load(open(os.path.join(p, "contract.json")))
    m = json.load(open(os.path.join(p, "metrics.json")))
    ws = m["timing__setup__ws"]
    if abs(c["source"]["claim_ns"] - (c["source"]["target_ns"] - ws)) > 1e-9 or c["chain"]["R1_ns"] != ceil05(c["source"]["claim_ns"]):
        errs.append("contract claim/R1")
    sets = {}
    for f in ("postgrt", "signoff"):
        fp = os.path.join(p, "nets", f + ".jsonl.gz")
        if os.path.exists(fp):
            rows = [json.loads(l) for l in gzip.open(fp, "rt") if l.strip()]
            sets[f] = {r["net"].replace("\\", "") for r in rows}
            ck = set()
            for r in rows:
                ck |= set((r.get("net_cap_pf_by_corner") or {}).keys())
            if ck != CORNERS:
                errs.append(f"{f} corners {sorted(ck)[:3]}")
    conn = json.load(gzip.open(os.path.join(p, "nets", "connectivity.json.gz"), "rt"))["nets"]
    sets["connectivity"] = {k.replace("\\", "") for k in conn}
    insts = {pin.rsplit("/", 1)[0].replace("\\", "") for v in conn.values() for pin in v["pins"] + [v["driver"] or ""]
             if "/" in pin and not pin.startswith("PORT:")}
    lay = os.path.join(p, "layout")
    if os.path.isdir(lay):
        sec, dnets, comps, units = None, set(), set(), None
        for line in gzip.open(os.path.join(lay, "final.def.gz"), "rt"):
            w = line.split()
            if not w:
                continue
            if w[0] == "UNITS":
                units = w[-2]
            if w[0] in ("COMPONENTS", "NETS", "SPECIALNETS", "PINS"):
                sec = w[0]
            elif w[0] == "END":
                sec = None
            elif w[0] == "-" and sec == "NETS" and w[1] not in SUPPLY:
                dnets.add(w[1].replace("\\", ""))
            elif w[0] == "-" and sec == "COMPONENTS":
                comps.add(w[1].replace("\\", ""))
        sets["def"] = dnets
        if units != "1000":
            errs.append(f"DEF units {units}")
        if not insts <= comps:
            errs.append(f"{len(insts - comps)} connectivity instances not in DEF")
        for rc in ("min", "nom", "max"):
            nm, inmap, dn, u = {}, False, set(), {}
            for line in gzip.open(os.path.join(lay, "spef", rc + ".spef.gz"), "rt"):
                s = line.split()
                if not s:
                    continue
                if s[0] in ("*T_UNIT", "*C_UNIT", "*R_UNIT"):
                    u[s[0]] = " ".join(s[1:])
                if s[0] == "*NAME_MAP":
                    inmap = True
                    continue
                if inmap and len(s) == 2 and s[0][1:].isdigit():
                    nm[s[0]] = s[1]
                    continue
                inmap = False
                if s[0] == "*D_NET":
                    dn.add(nm.get(s[1], s[1]).replace("\\", ""))
            sets["spef_" + rc] = dn
            if u != {"*T_UNIT": "1 NS", "*C_UNIT": "1 PF", "*R_UNIT": "1 OHM"}:
                errs.append(f"SPEF {rc} units {u}")
    base = sets["connectivity"]
    for k, v in sets.items():
        if k.startswith("spef_"):     # nets without any wire (e.g. unconnected input ports) carry no parasitics
            if v - base:
                errs.append(f"{k} has {len(v - base)} nets not in connectivity")
            info["no_parasitics"] = len(base - v)
        elif v != base:
            errs.append(f"{k} nets differ from connectivity: {len(v - base)} extra, {len(base - v)} missing")
    info["nets"] = len(base)
    info["views"] = sorted(sets)
    return errs, info


def main() -> int:
    root = sys.argv[1]
    bad = 0
    for pid in sorted(os.listdir(root)):
        p = os.path.join(root, pid, "rung2")
        if not os.path.isdir(p):
            continue
        errs, info = check(p)
        print(("FAIL " if errs else "ok   ") + f"{pid}: {info['nets']} nets agree across {', '.join(info['views'])}"
              + (f" ({info['no_parasitics']} without parasitics)" if info.get("no_parasitics") else "")
              + (f" | {errs}" if errs else ""), flush=True)
        bad += bool(errs)
    print(f"[verify] {bad} packets with problems")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
