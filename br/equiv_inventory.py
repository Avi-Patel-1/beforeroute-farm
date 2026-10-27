#!/usr/bin/env python3
"""Equivalence inventory: one status per repaired arm (runner check, else the best local proof), controls reported
separately, runner timeouts listed with whether a local proof exists. Usage: equiv_inventory.py [--json out]"""
import argparse, collections, glob, json, os

ap = argparse.ArgumentParser()
ap.add_argument("--root", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
ap.add_argument("--json", default=None)
a = ap.parse_args()
os.chdir(a.root)
runner = {p.split("/")[1]: json.load(open(p)).get("status") for p in glob.glob("results/*/equiv/result.json")}
local, controls = {}, {}
for p in glob.glob("results-equiv-local/*/result.json"):
    name = p.split("/")[1]
    d = json.load(open(p))
    if name.startswith("control-"):
        controls[name] = {k: d.get(k) for k in ("status", "expect", "control_ok", "seconds")}
        continue
    tag = name[:-len("-struct")] if name.endswith("-struct") else name
    if local.get(tag) != "PROVED":
        local[tag] = d.get("status")
arms = {}
for t in set(runner) | set(local):
    r, l = runner.get(t), local.get(t)
    arms[t] = ("PROVED", "runner") if r == "PROVED" else (("PROVED", "local") if l == "PROVED" else (r or l, "runner" if r else "local"))
timeouts = sorted(p.split("/")[1] for p in glob.glob("results/*/equiv/run.log")
                  if "TimeoutExpired" in open(p).read() and runner.get(p.split("/")[1]) is None)
c = collections.Counter(s for s, _ in arms.values())
src = collections.Counter(w for s, w in arms.values() if s == "PROVED")
out = {"proved": c.get("PROVED", 0), "proved_runner": src.get("runner", 0), "proved_local": src.get("local", 0),
       "not_proved": {t: s for t, (s, _) in arms.items() if s != "PROVED"}, "controls": controls,
       "runner_timeouts_without_local_proof": [t for t in timeouts if arms.get(t, ("", ""))[0] != "PROVED"]}
print(json.dumps(out, indent=1))
if a.json:
    json.dump({**out, "arms": {t: list(v) for t, v in sorted(arms.items())}}, open(a.json, "w"), indent=1)
