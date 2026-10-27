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
# state-cut check (br/equiv_cut.py): results-equiv-cut/<tag>/result.json; <tag>-negctrl are negative controls
# (expected COUNTEREXAMPLE), <tag>-yosyssat the cross-check engine; neither counts as an arm result
cut, cut_controls = {}, {}
for p in glob.glob("results/*/equiv_cut/result.json"):  # runner (hero_arm.sh), same tool
    cut[p.split("/")[1]] = json.load(open(p)).get("status")
for p in glob.glob("results-equiv-cut/*/result.json"):
    name = p.split("/")[1]
    d = json.load(open(p))
    if name.endswith("-negctrl") or name.endswith("-yosyssat-negctrl"):
        cut_controls[name] = {"status": d.get("status"), "expect": "COUNTEREXAMPLE",
                              "control_ok": d.get("status") == "COUNTEREXAMPLE", "seconds": d.get("seconds")}
        continue
    if name.endswith("-yosyssat"):
        continue
    cut[name] = d.get("status")
arms = {}
for t in set(runner) | set(local) | set(cut):
    r, l, k = runner.get(t), local.get(t), cut.get(t)
    if r == "PROVED":
        arms[t] = ("PROVED", "runner")
    elif k == "PROVED":
        arms[t] = ("PROVED", "cut")
    elif l == "PROVED":
        arms[t] = ("PROVED", "local")
    else:
        arms[t] = (r or k or l, "runner" if r else ("cut" if k else "local"))
controls.update(cut_controls)
timeouts = sorted(p.split("/")[1] for p in glob.glob("results/*/equiv/run.log")
                  if "TimeoutExpired" in open(p).read() and runner.get(p.split("/")[1]) is None)
c = collections.Counter(s for s, _ in arms.values())
src = collections.Counter(w for s, w in arms.values() if s == "PROVED")
out = {"proved": c.get("PROVED", 0), "proved_runner": src.get("runner", 0), "proved_local": src.get("local", 0),
       "proved_cut_only": src.get("cut", 0), "cut_checked": dict(collections.Counter(cut.values())),
       "not_proved": {t: s for t, (s, _) in arms.items() if s != "PROVED"}, "controls": controls,
       "runner_timeouts_without_local_proof": [t for t in timeouts if arms.get(t, ("", ""))[0] != "PROVED"]}
print(json.dumps(out, indent=1))
if a.json:
    json.dump({**out, "arms": {t: list(v) for t, v in sorted(arms.items())}}, open(a.json, "w"), indent=1)
