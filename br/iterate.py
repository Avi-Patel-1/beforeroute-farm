#!/usr/bin/env python3
"""Build the net list for the next pass of a signoff-guided repair loop.

Usage: iterate.py --base <base_tag> --out farm/lists/<base>/<name>.json
                  [--prev-list <json>] [--prev-arm <arm_tag>]
List = (previous list) U (signal nets violating at the previous arm's nine-corner signoff;
the baseline's signoff when there is no previous arm). Violating nets are identified by
their driver instance/pin so that renamed nets still map; nets that do not exist at the
post-GRT point of the base (buffers created later) are dropped and counted.
"""
import argparse, json, os
ap = argparse.ArgumentParser()
ap.add_argument("--base", required=True); ap.add_argument("--out", required=True)
ap.add_argument("--prev-list", default=None); ap.add_argument("--prev-arm", default=None)
ap.add_argument("--results", default="results")
a = ap.parse_args()
base_nets = {}
for line in open(os.path.join(a.results, a.base, "nets.jsonl")):
    n = json.loads(line)
    if n.get("sigtype") in ("POWER", "GROUND"):
        continue
    base_nets[n["net"]] = n
    if n.get("driver_inst"):
        base_nets.setdefault("__inst__" + n["driver_inst"], n)
prev = set(json.load(open(a.prev_list))) if a.prev_list else set()
src = os.path.join(a.results, a.prev_arm or a.base, "labels.json")
lab = json.load(open(src))
added, dropped = [], 0
for r in lab["nets"]:
    if not r.get("violated") or r.get("sigtype_s") != "SIGNAL":
        continue
    name = r["net"]
    if name not in base_nets:
        inst = (r.get("driver_s") or "").split("/")[0]
        n = base_nets.get("__inst__" + inst)
        if n is None:
            dropped += 1
            continue
        name = n["net"]
    if name not in prev:
        added.append(name)
new = sorted(prev | set(added))
os.makedirs(os.path.dirname(a.out), exist_ok=True)
json.dump(new, open(a.out, "w"))
print(json.dumps({"base": a.base, "from": a.prev_arm or a.base, "prev": len(prev), "added": len(added), "dropped_unmapped": dropped, "total": len(new), "out": a.out}))
