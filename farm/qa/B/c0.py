#!/usr/bin/env python3
"""Workstream B, arm C0 (registered analysis, no runs): score the existing sky130 audit by the register-to-register
claim C_r = T - timing__setup_r2r__ws (ORFS issue #4583's proposed metric, period - reg2reg worst slack).
Pre-registration: docs/qa_week/B_PREREG.md (SHA-256 in farm/prereg_hashes.txt, branch qa-b-frozen-io).

  python3 -I farm/qa/B/c0.py [--data /home/claude/eda/agents/analysis/fixedpoint/data.json] [--out farm/qa/B/c0.json]

Per setting with runs at >= 2 targets (data.json `groups`, 139): F_r = crossing of C_r(T) = T (one point per target, the
median C_r if repeated); settings whose F_r is bracketed ("interpolated") enter; e_r = (C_r - F_r) / F_r at each of their
runs, binned by T / F_r. Registered test: median e_r in the tight bin (T/F_r < 0.9) < -0.10 -> PASS.
Beside: the same on the 60 settings whose all-path fixed point is bracketed (the audit's population).
"""
from __future__ import annotations

import argparse
import json
import math
import statistics as st
from collections import defaultdict

BINS = (("tight (<0.9)", 0.0, 0.9), ("near (0.9-1.1)", 0.9, 1.1), ("loose (1.1-1.5)", 1.1, 1.5),
        ("very loose (>1.5)", 1.5, 99.0))


def linfit(xs, ys):                     # agents/analysis/fixedpoint/analyze.py linfit (copied verbatim)
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx < 1e-12:
        return None, None
    a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return a, my - a * mx


def crossing(pts):                      # agents/analysis/fixedpoint/analyze.py crossing (copied verbatim)
    """pts: [(T, teff)] distinct T, sorted ascending. Returns (F, how)."""
    g = [(T, te - T) for T, te in pts]
    for (t1, g1), (t2, g2) in zip(g, g[1:]):
        if g1 > 0 >= g2:
            return t1 + (t2 - t1) * g1 / (g1 - g2), "interpolated"

    def extra(p1, p2, how):
        a, b = linfit([p1[0], p2[0]], [p1[1], p2[1]])
        if a is None or a >= 0.999:
            return None, how + " (no crossing: slope >= 1)"
        return b / (1 - a), how
    if all(x <= 0 for _, x in g):
        return extra(pts[0], pts[1], "extrapolated below")
    if all(x > 0 for _, x in g):
        return extra(pts[-2], pts[-1], "extrapolated above")
    a, b = linfit([p[0] for p in pts], [p[1] for p in pts])
    if a is None or a >= 0.999:
        return None, "no crossing"
    return b / (1 - a), "fit all"


def summ(xs):
    """Registered statistic on all runs; beside it the same without non-finite errors (6 cic_decimator record runs
    report an infinite register-to-register slack, i.e. C_r = -inf; all sit at T/F_r > 1.3)."""
    xs = sorted(xs)
    if not xs:
        return None
    fin = [x for x in xs if math.isfinite(x)]
    return {"n": len(xs), "median": st.median(xs), "min": xs[0], "max": xs[-1],
            "beyond_minus5pct": sum(1 for x in xs if x < -0.05),
            "share_beyond_minus5pct": sum(1 for x in xs if x < -0.05) / len(xs),
            "nonfinite": len(xs) - len(fin), "median_finite": st.median(fin) if fin else None,
            "min_finite": fin[0] if fin else None}


def score(groups, key="t_r2r"):
    """Per-run register-claim errors for settings whose register fixed point is bracketed."""
    rows, used, how = [], [], defaultdict(int)
    for g in groups:
        byT = defaultdict(list)
        for p in g["points"]:
            byT[round(p["T"], 4)].append(p[key])
        pts = [(T, st.median(byT[T])) for T in sorted(byT)]
        F, h = crossing(pts)
        how[h] += 1
        if h != "interpolated":
            continue
        used.append({"design": g["design"], "F_r": F, "F_all": g.get("F_emp"), "F_all_how": g.get("F_emp_how"),
                     "n": len(g["points"])})
        for p in g["points"]:
            rows.append({"design": g["design"], "tag": p["tag"], "T": p["T"], "C_r": p[key], "F_r": F,
                         "ratio": p["T"] / F, "e_r": (p[key] - F) / F, "port": p["port"]})
    bins = {lab: summ([r["e_r"] for r in rows if lo <= r["ratio"] < hi]) for lab, lo, hi in BINS}
    by_design = {}
    for d in sorted({r["design"] for r in rows}):
        x = [r["e_r"] for r in rows if r["design"] == d and r["ratio"] < 0.9]
        if x:
            by_design[d] = {"n": len(x), "median": st.median(x)}
    fin = [r for r in rows if math.isfinite(r["e_r"])]
    worst = min(fin, key=lambda r: r["e_r"]) if fin else None
    return {"settings_in": len(groups), "bracketed": len(used), "how": dict(how), "runs": len(rows), "bins": bins,
            "tight_by_design": by_design, "worst": worst, "settings": used, "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/home/claude/eda/agents/analysis/fixedpoint/data.json")
    ap.add_argument("--out", default="farm/qa/B/c0.json")
    a = ap.parse_args()
    d = json.load(open(a.data))
    G = d["groups"]
    prim = score(G)
    sub = score([g for g in G if g["F_emp_how"] == "interpolated"])
    t = prim["bins"]["tight (<0.9)"]
    verdict = "PASS" if (t and t["median"] < -0.10) else "FAIL"
    ts = sub["bins"]["tight (<0.9)"]
    out = {"registered_test": "median e_r, tight bin (T/F_r < 0.9), settings with a bracketed register fixed point "
                              "among the 139 settings at >= 2 targets: < -0.10",
           "verdict": verdict, "primary": prim, "beside_60_audit_settings": sub,
           "beside_60_verdict_same_threshold": "PASS" if (ts and ts["median"] < -0.10) else "FAIL",
           "record_all_path_tight_60": d["interpolated"]["bias_bins"]["tight (<0.9)|all"]}
    def clean(o):                       # strict JSON: non-finite floats as strings
        if isinstance(o, float) and not math.isfinite(o):
            return str(o)
        if isinstance(o, dict):
            return {k: clean(v) for k, v in o.items()}
        if isinstance(o, list):
            return [clean(v) for v in o]
        return o
    json.dump(clean(out), open(a.out, "w"), indent=1)
    for name, r in (("primary (139 settings)", prim), ("beside (60 audit settings)", sub)):
        print(f"{name}: {r['bracketed']} bracketed of {r['settings_in']}, {r['runs']} runs; how {r['how']}")
        for lab, v in r["bins"].items():
            if v:
                print(f"   {lab:18s} n {v['n']:3d} median {v['median']*100:+6.2f}%  beyond -5%: {v['beyond_minus5pct']}"
                      f" ({v['share_beyond_minus5pct']*100:.0f}%)  min {v['min']*100:+.1f}%  max {v['max']*100:+.1f}%"
                      + (f"  [non-finite {v['nonfinite']}; finite median {v['median_finite']*100:+.2f}%, finite min "
                         f"{v['min_finite']*100:+.1f}%]" if v['nonfinite'] else ""))
        w = r["worst"]
        print(f"   worst (finite): {w['tag']} ({w['design']}) T {w['T']} C_r {w['C_r']:.3f} F_r {w['F_r']:.3f} "
              f"e_r {w['e_r']*100:+.1f}%")
    print("C0 verdict:", verdict, f"(tight median {t['median']*100:+.2f}%, n {t['n']})")


if __name__ == "__main__":
    main()
