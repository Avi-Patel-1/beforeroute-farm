#!/usr/bin/env python3
"""Export a compact per-net JSON for the interactive explorer page.

Usage: explorer_data.py --run-results results/<base> --scores <scores.csv> [--hero results/<base>/hero_summary.json]
                        [--arm <tag> ...] --out explorer.json
nets: [x, y, est, act, p, flags, fanout, hpwl, cls]  flags bit0 viol_slew, bit1 viol_cap, bit2 viol_fanout, bit3 is_clock
"""
from __future__ import annotations

import argparse
import json
import os

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-results", required=True)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--hero", default=None)
    ap.add_argument("--arm", action="append", default=[], help="arm tag whose remaining violators to overlay")
    ap.add_argument("--results", default="results")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    base = os.path.abspath(a.run_results)
    tag = os.path.basename(base)
    nets = [json.loads(l) for l in open(os.path.join(base, "nets.jsonl"))]
    lab = json.load(open(os.path.join(base, "labels.json")))
    sig = {r["net"]: r for r in lab["nets"]}
    sc = pd.read_csv(a.scores).set_index("net")
    summ = json.load(open(os.path.join(base, "dump_summary.json")))
    resolved = json.load(open(os.path.join(base, "resolved.json")))

    classes = []
    cls_idx = {}
    rows, index_of = [], {}
    inst_of = {}
    for n in nets:
        if n.get("sigtype") in ("POWER", "GROUND") or n.get("driver_kind") == "none":
            continue
        name = n["net"]
        s = sig.get(name)
        if s is None and name in sc.index and isinstance(sc.loc[name].get("net_s"), str):
            s = sig.get(sc.loc[name]["net_s"])
        est = n.get("worst_load_slew_ratio") or n.get("driver_slew_ratio") or 0.0
        act = (s or {}).get("worst_slew_ratio_s") or 0.0
        flags = 0
        if s:
            flags |= 1 if s.get("viol_slew") else 0
            flags |= 2 if s.get("viol_cap") else 0
            flags |= 4 if s.get("viol_fanout") else 0
        if n.get("is_clock"):
            flags |= 8
        p = float(sc.loc[name]["p"]) if name in sc.index else -1.0
        cls = (sc.loc[name]["driver_class"] if name in sc.index else None) or (n.get("driver_master") or "port").replace("sky130_fd_sc_hd__", "").split("_")[0]
        if cls not in cls_idx:
            cls_idx[cls] = len(classes)
            classes.append(cls)
        index_of[name] = len(rows)
        if n.get("driver_inst"):
            inst_of[n["driver_inst"]] = len(rows)
        rows.append([
            round(n.get("driver_x_um") or 0, 1), round(n.get("driver_y_um") or 0, 1),
            round(float(est), 3), round(float(act), 3), round(p, 4), flags,
            int(n.get("fanout") or 0), round(float(n.get("hpwl_um") or 0), 1), cls_idx[cls], name,
        ])

    arms = []
    hero = json.load(open(a.hero)) if a.hero else None
    hero_rows = {r["tag"]: r for r in hero["arms"]} if hero else {}
    for arm in a.arm:
        d = os.path.join(a.results, arm)
        try:
            al = json.load(open(os.path.join(d, "labels.json")))
        except Exception:
            continue
        remaining, unmapped = [], 0
        for r in al["nets"]:
            if not r.get("violated") or r.get("sigtype_s") != "SIGNAL":
                continue
            inst = (r.get("driver_s") or "").split("/")[0]
            i = index_of.get(r["net"], inst_of.get(inst))
            if i is None:
                unmapped += 1
            else:
                remaining.append(i)
        h = hero_rows.get(arm, {})
        arms.append({
            "tag": arm, "label": arm[len(tag) + 1:] if arm.startswith(tag + "-") else arm,
            "remaining": sorted(set(remaining)), "unmapped": unmapped,
            "violating_data_nets": h.get("signoff_violating_data_nets"), "clock_nets": h.get("signoff_violating_clock_nets"),
            "resized": h.get("resized"), "buffers": h.get("buffers"), "nets_touched": h.get("nets_touched"),
            "stdcell_area": h.get("stdcell_area"), "instances_stdcell": h.get("instances_stdcell"),
            "hold_ws": h.get("hold_ws"), "setup_ws": h.get("setup_ws"), "flagged": h.get("flagged"),
            "slew_pct": h.get("slew_pct"), "targeted": (h.get("targeted") or {}).get("n_flagged_found"),
        })
    basestats = hero_rows.get(tag, {})
    out = {
        "run": tag, "design": summ.get("design"),
        "core_area_um2": summ.get("core_area_um2"), "utilization": summ.get("utilization"),
        "clock_period_ns": resolved.get("CLOCK_PERIOD"), "fp_core_util": resolved.get("FP_CORE_UTIL"),
        "pl_density_pct": resolved.get("PL_TARGET_DENSITY_PCT"), "max_tran_ns": summ.get("sdc_max_transition_ns"),
        "inst_count": summ.get("inst_count"), "corners": lab["summary"].get("corners"),
        "classes": classes, "nets": rows, "arms": arms,
        "base": {k: basestats.get(k) for k in ("stdcell_area", "instances_stdcell", "hold_ws", "setup_ws", "signoff_violating_data_nets", "signoff_violating_clock_nets")},
    }
    json.dump(out, open(a.out, "w"), separators=(",", ":"))
    nv = sum(1 for r in rows if r[5] & 7 and not r[5] & 8)
    blind = sum(1 for r in rows if r[5] & 7 and not r[5] & 8 and r[2] <= 1.0)
    print(f"wrote {a.out}: {len(rows)} nets, {nv} signal violators, {blind} blind, arms={[(x['label'], len(x['remaining']), x['unmapped']) for x in arms]}, {os.path.getsize(a.out)/1e6:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
