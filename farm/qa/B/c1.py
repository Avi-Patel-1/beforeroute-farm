#!/usr/bin/env python3
"""Workstream B, arm C1 scoring (registered tests, docs/qa_week/B_PREREG.md): the audit replayed with frozen I/O.

  python3 -I farm/qa/B/c1.py --results /home/claude/qa/b/results [--record /home/claude/eda/results] [--out c1.json]

Inputs: results/b1r-*/ and b1t-*/ (metrics.json, b_meta.json, job.json; farm/qa/B/collect.py), farm/qa/B/plan.json.
Per setting: one point per target (median claim if repeated); F = agents/analysis/fixedpoint `crossing` of C(T) = T
(blib.crossing, verbatim); only bracketed ("interpolated") settings enter. e = (C - F)/F per run; bins by T/F.
  C1a: median port slope < 0.15      (settings with port-limited runs at >= 2 distinct targets; slope of C vs T over them)
  C1b: median register slope >= 0.25 (settings with no port-limited run; slope of T - ws_r2r vs T over all runs)
  C1c: tight median e < -0.08 AND >= 60% of tight runs e < -0.05, with n_tight >= 60 (else "insufficient")
  C1d: loose (1.1-1.5) median e >= +0.05
Control (ii): the 7 replays at their design's F_best must equal their source runs in every metrics.json key.
Verdicts stay "provisional" until every setting is complete (all replays landed; bracketed or 2 top-ups used).
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blib  # noqa: E402

BINS = (("tight (<0.9)", 0.0, 0.9), ("near (0.9-1.1)", 0.9, 1.1), ("loose (1.1-1.5)", 1.1, 1.5),
        ("very loose (>1.5)", 1.5, 99.0))


def J(p, default=None):
    try:
        return json.load(open(p))
    except Exception:
        return default


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--record", default="/home/claude/eda/results")
    ap.add_argument("--out", default=os.path.join(HERE, "c1.json"))
    a = ap.parse_args()
    plan = J(os.path.join(HERE, "plan.json"))
    fb = plan["fbest"]
    expected = {}
    for r in plan["c1"]["runs"]:
        expected.setdefault(r["setting"], []).append(r)
    runs = []
    for d in sorted(glob.glob(os.path.join(a.results, "b1[rt]-*"))):
        meta = J(os.path.join(d, "b_meta.json"))
        m = J(os.path.join(d, "metrics.json"), {}) or {}
        if not meta:
            continue
        T = float(meta["period"])
        ws, wr = m.get("timing__setup__ws"), m.get("timing__setup_r2r__ws")
        runs.append({"tag": meta["tag"], "kind": meta["kind"], "setting": meta["setting"], "design": meta["design"],
                     "source": meta.get("source"), "T": T, "ws": ws, "ws_r2r": wr,
                     "claim": (T - ws) if ws is not None else None,
                     "claim_r2r": (T - wr) if (wr is not None and math.isfinite(wr)) else None,
                     "port": (ws < wr - 1e-4) if (ws is not None and wr is not None) else None,
                     "io_value": meta.get("io_value"), "metrics": m})
    bys = {}
    for r in runs:
        bys.setdefault(r["setting"], []).append(r)
    settings, bias = [], []
    for sid in sorted(expected):
        rs = [r for r in bys.get(sid, []) if r["claim"] is not None]
        n_rep = sum(1 for r in bys.get(sid, []) if r["kind"] == "c1r")
        n_top = sum(1 for r in bys.get(sid, []) if r["kind"] == "c1t")
        byT = {}
        for r in rs:
            byT.setdefault(round(r["T"], 4), []).append(r["claim"])
        pts = sorted((T, st.median(v)) for T, v in byT.items())
        F, how = blib.crossing(pts) if len(pts) >= 2 else (None, "too few")
        bracketed = how == "interpolated"
        complete = n_rep == len(expected[sid]) and (bracketed or n_top >= 2)
        s = {"setting": sid, "design": expected[sid][0]["design"], "replays": n_rep, "expected": len(expected[sid]),
             "topups": n_top, "F": F, "how": how, "bracketed": bracketed, "complete": complete,
             "F_stock": expected[sid][0]["F_stock"]}
        if bracketed:
            port_pts = sorted((r["T"], r["claim"]) for r in rs if r["port"])
            if len({p[0] for p in port_pts}) >= 2:
                s["slope_port"] = blib.linfit([p[0] for p in port_pts], [p[1] for p in port_pts])[0]
            if not any(r["port"] for r in rs):
                rr = [(r["T"], r["claim_r2r"]) for r in rs if r["claim_r2r"] is not None]
                if len({p[0] for p in rr}) >= 2:
                    s["slope_r2r"] = blib.linfit([p[0] for p in rr], [p[1] for p in rr])[0]
            for r in rs:
                bias.append({"setting": sid, "design": s["design"], "tag": r["tag"], "ratio": r["T"] / F,
                             "e": (r["claim"] - F) / F, "port": r["port"]})
        settings.append(s)

    def summ(xs):
        xs = sorted(xs)
        return {"n": len(xs), "median": st.median(xs), "min": xs[0], "max": xs[-1],
                "share_beyond_minus5pct": sum(1 for x in xs if x < -0.05) / len(xs)} if xs else None
    bins = {lab: {k: summ([b["e"] for b in bias if lo <= b["ratio"] < hi and (k == "all" or (k == "port") == b["port"])])
                  for k in ("all", "port", "r2r")} for lab, lo, hi in BINS}
    sp = [s["slope_port"] for s in settings if s.get("slope_port") is not None]
    sr = [s["slope_r2r"] for s in settings if s.get("slope_r2r") is not None]
    tight, loose = bins["tight (<0.9)"]["all"], bins["loose (1.1-1.5)"]["all"]
    all_done = all(s["complete"] for s in settings)
    tag = "" if all_done else " (provisional)"
    res = {"settings_total": len(settings), "settings_complete": sum(1 for s in settings if s["complete"]),
           "settings_bracketed": sum(1 for s in settings if s["bracketed"]), "runs": len(runs),
           "C1a": {"median_port_slope": st.median(sp) if sp else None, "n": len(sp),
                   "verdict": (("PASS" if st.median(sp) < 0.15 else "FAIL") + tag) if sp else "insufficient"},
           "C1b": {"median_register_slope": st.median(sr) if sr else None, "n": len(sr),
                   "verdict": (("PASS" if st.median(sr) >= 0.25 else "FAIL") + tag) if sr else "insufficient"},
           "C1c": {"tight": tight, "verdict": ("insufficient (n_tight < 60)" if not tight or tight["n"] < 60 else
                                               ("PASS" if (tight["median"] < -0.08 and
                                                           tight["share_beyond_minus5pct"] >= 0.60) else "FAIL")) + tag},
           "C1d": {"loose": loose, "verdict": (("PASS" if loose["median"] >= 0.05 else "FAIL") + tag) if loose
                   else "insufficient"},
           "bins": bins, "settings": settings}
    # control (ii): replays at F_best equal their source runs
    ctl = []
    for r in runs:
        f = fb[r["design"]]
        if r["kind"] == "c1r" and f["F_best"] is not None and abs(r["T"] - f["F_best"]) < 1e-9:
            mo = J(os.path.join(a.record, r["source"], "metrics.json"), {}) or {}
            diff = sorted(k for k in set(mo) | set(r["metrics"]) if mo.get(k) != r["metrics"].get(k))
            ctl.append({"tag": r["tag"], "source": r["source"], "identical": not diff, "diff_keys": diff[:10]})
    res["control_ii"] = ctl
    for r in runs:
        r.pop("metrics", None)
    res["run_rows"] = runs
    json.dump(res, open(a.out, "w"), indent=1, default=str)
    print(f"settings complete {res['settings_complete']}/{len(settings)}, bracketed {res['settings_bracketed']}, "
          f"runs {len(runs)}")
    for k in ("C1a", "C1b", "C1c", "C1d"):
        print(k, {kk: v for kk, v in res[k].items()})
    print("control (ii):", [(c["tag"], c["identical"]) for c in ctl])


if __name__ == "__main__":
    main()
