#!/usr/bin/env python3
"""Workstream B, arm C3 scoring (registered tests, docs/qa_week/B_PREREG.md on qa-b-frozen-io).

  python3 -I farm/qa/B3/c3.py --results DIR [--e5 /home/claude/qa/asap7/results] [--out farm/qa/B3/c3.json]

Picks = the chains' winners (top 3 per design by AutoTuner's score among the 10 frozen grid runs, chosen on the runner).
C0 = pick's claim; R1 = first rebuild (ceil5(C0)); C1 its claim; d1 = C1/C0 - 1; K = kept clock (smallest passing clock).
  C3-gcd:  each of gcd's 3 picks has |K/C0 - 1| <= 0.02, or its first rebuild is register-limited (not port-limited)
  C3-aes:  >= 2 of aes's 3 picks fail their first rebuild
  C3-ibex: each of ibex's 3 picks has |K/C0 - 1| <= 0.01
Control: b3g-<design>-003 (T = P0) equals E5's e5g-<design>-003 in every metric except execution-time keys.
Beside: claim-error bins with frozen budgets (agents/analysis/fixedpoint `crossing`, as E5's S1/S2), E5's numbers.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "E5"))
import e5lib  # noqa: E402
import e5  # noqa: E402  (crossing, linfit: copies of agents/analysis/fixedpoint/analyze.py)

DESIGNS = ["gcd", "aes", "ibex"]
BINS = (("tight (<0.9)", 0.0, 0.9), ("near (0.9-1.1)", 0.9, 1.1), ("loose (1.1-1.5)", 1.1, 1.5),
        ("very loose (>1.5)", 1.5, 99.0))


def merged_logs(d):
    m = {}
    for p in sorted(glob.glob(os.path.join(d, "logs", "*.json"))):
        try:
            x = json.load(open(p))
        except Exception:
            continue
        if isinstance(x, dict):
            m.update(x)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--e5", default="/home/claude/qa/asap7/results")
    ap.add_argument("--out", default=os.path.join(HERE, "c3.json"))
    a = ap.parse_args()
    R = {}
    for d in sorted(os.listdir(a.results)):
        if d.startswith(("b3g-", "b3k-")) and os.path.isdir(os.path.join(a.results, d)):
            R[d] = e5lib.load_run(os.path.join(a.results, d))
    chains = {}
    for p in sorted(glob.glob(os.path.join(a.results, "chains", "b3k-*.json"))):
        c = json.load(open(p))
        chains[c["chain_id"]] = c
    picks = {d: [] for d in DESIGNS}
    for cid, c in sorted(chains.items()):
        w = c["winner"]
        st_ = c["chain"]
        r1 = st_[1] if len(st_) > 1 else (st_[0] if (w.get("pass") and e5lib.ceil_grid(w["claim"]) >= w["period"])
                                         else None)
        r1run = R.get(r1["tag"]) if r1 else None
        K = c.get("kept_clock")
        row = {"chain_id": cid, "winner": w["tag"], "setting": c.get("setting"), "T0": w["period"], "C0": w["claim"],
               "W_port": (R.get(w["tag"]) or {}).get("port"),
               "R1": r1 and r1["period"], "R1_pass": r1 and r1.get("pass"), "C1": r1 and r1.get("claim"),
               "d1": (r1["claim"] / w["claim"] - 1) if (r1 and r1.get("claim") is not None) else None,
               "R1_port": r1run and r1run.get("port"), "R1_ws": r1run and r1run.get("ws"),
               "R1_ws_r2r": r1run and r1run.get("ws_r2r"),
               "K": K, "K_over_C0": (K / w["claim"]) if K else None,
               "chain": [(x["tag"], x["period"], x.get("claim"), x.get("pass")) for x in st_]}
        picks[c["design"]].append(row)
    out = {"picks": picks}
    g = picks["gcd"]
    ok_g = [((r["K_over_C0"] is not None and abs(r["K_over_C0"] - 1) <= 0.02) or (r["R1_port"] is False)) for r in g]
    out["C3_gcd"] = {"n": len(g), "each_ok": ok_g,
                     "verdict": ("PASS" if len(g) == 3 and all(ok_g) else "FAIL" if len(g) == 3 else "pending")}
    aa = picks["aes"]
    nf = sum(1 for r in aa if r["R1_pass"] is False)
    out["C3_aes"] = {"n": len(aa), "first_rebuild_fails": nf,
                     "verdict": "PASS" if nf >= 2 else ("FAIL" if len(aa) == 3 else "pending")}
    ib = picks["ibex"]
    ok_i = [(r["K_over_C0"] is not None and abs(r["K_over_C0"] - 1) <= 0.01) for r in ib]
    out["C3_ibex"] = {"n": len(ib), "each_ok": ok_i,
                      "verdict": ("PASS" if len(ib) == 3 and all(ok_i) else "FAIL" if len(ib) == 3 else "pending")}
    # control
    ctl = {}
    for d in DESIGNS:
        t = f"b3g-{d}-003"
        if t not in R:
            ctl[d] = "not landed"
            continue
        m, mo = merged_logs(os.path.join(a.results, t)), merged_logs(os.path.join(a.e5, f"e5g-{d}-003"))
        diff = sorted(k for k in set(m) | set(mo) if m.get(k) != mo.get(k) and not ("runtime" in k or k.endswith("_s")))
        ctl[d] = {"identical": not diff and bool(m), "diff_keys": diff[:20], "n_keys": len(mo)}
    out["control"] = ctl
    # beside: claim-error bins with frozen budgets (grid + chain runs), per setting crossing
    pts = {}
    for t, r in R.items():
        if r.get("claim") is None:
            continue
        key = (r["design"], json.dumps(r.get("vars") or {}, sort_keys=True))
        pts.setdefault(key, []).append(r)
    bias = []
    for key, rs in pts.items():
        byT = {}
        for r in rs:
            byT.setdefault(float(r["period"]), []).append(r["claim"])
        P = sorted((T, st.median(v)) for T, v in byT.items())
        if len(P) < 2:
            continue
        F, how = e5.crossing(P)
        if how != "interpolated":
            continue
        for r in rs:
            bias.append({"design": key[0], "tag": r["tag"], "ratio": float(r["period"]) / F,
                         "e": (r["claim"] - F) / F, "port": r.get("port")})
    out["bins"] = {lab: (lambda xs: {"n": len(xs), "median": st.median(xs)} if xs else None)(
        [b["e"] for b in bias if lo <= b["ratio"] < hi]) for lab, lo, hi in BINS}
    json.dump(out, open(a.out, "w"), indent=1, default=str)
    for d in DESIGNS:
        for r in picks[d]:
            print(f"{r['chain_id']}: {r['winner']} ({r['setting']}) T0 {r['T0']} C0 {r['C0']:.1f} W_port {r['W_port']} | "
                  f"R1 {r['R1']} pass {r['R1_pass']} C1 {r['C1'] and round(r['C1'], 1)} d1 "
                  f"{r['d1'] and round(100 * r['d1'], 2)}% port {r['R1_port']} | K {r['K']} "
                  f"K/C0 {r['K_over_C0'] and round(r['K_over_C0'], 4)}")
    print("C3-gcd :", out["C3_gcd"])
    print("C3-aes :", out["C3_aes"])
    print("C3-ibex:", out["C3_ibex"])
    print("control:", ctl)
    print("bins   :", out["bins"])


if __name__ == "__main__":
    main()
