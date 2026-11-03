#!/usr/bin/env python3
"""Experiment E (reading the chip): deterministic choice of the 36 source runs (registered in docs/qa_week/E_PREREG.md).

Reads only the landed record (results/tune*/state.json, results/<tag>/metrics.json, farm/jobs/<tag>.json); no outcome of
any future run exists. Writes farm/qa/E/sources.json and one capture-enabled job spec per source,
farm/jobs/ers-<design>-<nn>.json (a copy of the original run's spec: same design, config and overrides, new tag,
"capture": true).

Rule (per test family, in this order):
  candidates  = record runs of the family's original RTL with metrics (setup WS present), not a closure/chain re-run
                (arms k, c), with a job spec on file;
  feasible    = detailed-route DRC 0, worst hold slack >= 0, max-slew + max-cap count (9 corners) <= the design's stock
                bar (the same bar the record's judge used);
  R1          = ceil05(C0), C0 = T0 - WS0 (claim); drop the run if the record already holds a run of the same setting
                (identical non-clock overrides) at R1 (its label would not be new), or if |R1 - T0| / T0 < 0.05;
  stratum     = by x = T0 / C0: tight x < 1, loose 1 <= x < 1.3, very loose x >= 1.3; quotas 4 / 3 / 2;
  order       = settings run at >= 2 distinct targets in the record first (so the two-point line has a second point),
                then SHA-256 of the tag, ascending; at most one source per setting.
Second point (two-point line, separate scoreboard): the same setting's record run whose target is nearest to T0
(T != T0, ties to the smaller target).
"""
from __future__ import annotations

import glob
import hashlib
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REC = os.environ.get("E_RECORD", "/home/claude/eda")          # the landed record (results/ is not in git)
TEST = ["zipdiv", "cic_decimator", "wbqspiflash", "picorv32"]   # HOLDOUT rule: first 4 by sha256 (see E_PREREG.md)
STOCK_BAR = {"zipdiv": ("x6d-zipdiv-001", 295), "cic_decimator": ("x6d-cic_decimator-006", 89),
             "wbqspiflash": ("x6d-wbqspiflash-001", 953), "picorv32": ("x1d-picorv32-001", 2881)}
QUOTA = [("tight", 4), ("loose", 3), ("very loose", 2)]


def ceil05(x):
    return round(math.ceil(round(x / 0.05, 6)) * 0.05, 2)


def drv(m):
    return (m.get("design__max_slew_violation__count") or 0) + (m.get("design__max_cap_violation__count") or 0)


def key_of(ov):
    return json.dumps({k: v for k, v in ov.items() if k != "CLOCK_PERIOD"}, sort_keys=True)


def sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def stratum(x):
    return "tight" if x < 1.0 else ("loose" if x < 1.3 else "very loose")


def record():
    runs = []
    for sp in sorted(glob.glob(os.path.join(REC, "results", "tune*", "state.json"))):
        study = os.path.basename(os.path.dirname(sp))
        for tag, v in json.load(open(sp))["tags"].items():
            if v.get("design") not in TEST or v.get("status") == "superseded" or not v.get("overrides"):
                continue
            mp = os.path.join(REC, "results", tag, "metrics.json")
            if not os.path.exists(mp):
                continue
            m = json.load(open(mp))
            ws = m.get("timing__setup__ws")
            if ws is None:
                continue
            T = float(v["overrides"]["CLOCK_PERIOD"])
            runs.append({"tag": tag, "study": study, "design": v["design"], "arm": v.get("arm"),
                         "variant": v.get("variant"), "T": T, "ws": ws, "ws_r2r": m.get("timing__setup_r2r__ws"),
                         "hold": m.get("timing__hold__ws"), "drc": m.get("route__drc_errors"), "drv": drv(m),
                         "key": key_of(v["overrides"]), "C": T - ws})
    return runs


def main() -> int:
    runs = record()
    by_key = {}
    for r in runs:
        by_key.setdefault((r["design"], r["key"]), []).append(r)
    sources = []
    for d in TEST:
        bar = STOCK_BAR[d][1]
        cands = []
        for r in runs:
            if r["design"] != d or r["variant"] not in (None, "orig") or r["arm"] in ("k", "c"):
                continue
            if not os.path.exists(os.path.join(REC, "farm", "jobs", r["tag"] + ".json")):
                continue
            if (r["drc"] or 0) != 0 or r["hold"] is None or r["hold"] < 0 or r["drv"] > bar:
                continue
            R1 = ceil05(r["C"])
            same = by_key[(d, r["key"])]
            if any(abs(o["T"] - R1) < 1e-6 for o in same):
                continue
            if abs(R1 - r["T"]) / r["T"] < 0.05:
                continue
            targets = sorted({round(o["T"], 4) for o in same})
            cands.append(dict(r, R1=R1, x=r["T"] / r["C"], stratum=stratum(r["T"] / r["C"]), n_targets=len(targets)))
        used = set()
        n = 0
        for st, q in QUOTA:
            pool = sorted((c for c in cands if c["stratum"] == st), key=lambda c: (c["n_targets"] < 2, sha(c["tag"])))
            took = 0
            for c in pool:
                if took == q:
                    break
                if c["key"] in used:
                    continue
                used.add(c["key"])
                others = [o for o in by_key[(d, c["key"])] if abs(o["T"] - c["T"]) > 1e-6]
                second = min(others, key=lambda o: (abs(o["T"] - c["T"]), o["T"])) if others else None
                n += 1
                sid = f"ers-{d}-{n:02d}"
                sources.append({"source": sid, "design": d, "stratum": st, "record_tag": c["tag"],
                                "record_study": c["study"], "record_arm": c["arm"], "T0": c["T"],
                                "ws0_record": c["ws"], "ws_r2r0_record": c["ws_r2r"], "C0_record": c["C"],
                                "R1_record": c["R1"], "x_T0_over_C0": round(c["x"], 4),
                                "n_targets_record": c["n_targets"], "stock_drv_bar": bar,
                                "stock_drv_ref_tag": STOCK_BAR[d][0],
                                "second_point": None if second is None else
                                {"tag": second["tag"], "T": second["T"], "C": second["C"], "ws": second["ws"]}})
                took += 1
            if took < q:
                print(f"[select] {d} {st}: only {took} of {q}", file=sys.stderr)
    out = {"about": __doc__.strip().splitlines()[0], "test_families": TEST, "n": len(sources), "sources": sources}
    json.dump(out, open(os.path.join(HERE, "sources.json"), "w"), indent=1)
    for s in sources:
        spec = json.load(open(os.path.join(REC, "farm", "jobs", s["record_tag"] + ".json")))
        assert abs(float(spec["overrides"]["CLOCK_PERIOD"]) - s["T0"]) < 1e-9, s
        spec["tag"] = s["source"]
        spec["capture"] = True
        spec["replay_of"] = s["record_tag"]
        json.dump(spec, open(os.path.join(WT, "farm", "jobs", s["source"] + ".json"), "w"), indent=1)
    for s in sources:
        sp = s["second_point"]
        print(f"{s['source']:22s} {s['stratum']:10s} {s['record_tag']:26s} T0 {s['T0']:7.3f} C0 {s['C0_record']:7.3f} "
              f"R1 {s['R1_record']:6.2f} x {s['x_T0_over_C0']:.3f} targets {s['n_targets_record']}"
              + (f"  2nd {sp['tag']} T {sp['T']:.3f}" if sp else ""))
    print(f"[select] {len(sources)} sources")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
