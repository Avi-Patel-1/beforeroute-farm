#!/usr/bin/env python3
"""Condense transfer_gf180.py's summary.json into the headline tables (markdown on stdout).

Usage: transfer_summary.py <out dir of transfer_gf180.py> [--feature-set base]
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np


def f(x, pct=True, nd=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    return f"{100 * x:.{nd}f}%" if pct else f"{x:.3f}"


def mean(lst, key):
    v = [x.get(key) for x in lst if x.get(key) is not None]
    return (float(np.mean(v)), float(np.min(v)), float(np.max(v)), len(v)) if v else (None, None, None, 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    a = ap.parse_args()
    S = json.load(open(os.path.join(a.out, "summary.json")))
    designs = S["designs"]
    L = []
    L.append("### Zero-shot: sky130-trained model on GF180 (signal nets; per held-out design, pooled over its runs)\n")
    L.append("| GF180 design | runs | violator rate | perfect ranker: catch 95% at | est-slew: catch 95% / R@5% / PR-AUC | R8: catch 95% / R@5% / PR-AUC | "
             + " | ".join(f"zero-shot [{fs}]: catch 95% / R@5% / PR-AUC" for fs in S["arms"]) + " |")
    L.append("|---|---|---|---|---|---|" + "---|" * len(S["arms"]))
    for d in designs:
        x = S["describe"][d]
        b = S["baselines"][d]
        cells = [d, str(x["runs"]), f(x["violator_rate"]), f(0.95 * x["violator_rate"])]
        for m in (b["est_load_slew_ratio"], b["R8"]):
            cells.append(f"{f(m.get('frac_to_catch_95'))} / {f(m.get('recall@5%'))} / {f(m.get('pr_auc'), False)}")
        for fs, byd in S["arms"].items():
            zs = (byd.get(d, {}).get("zs") or {}).get("0")
            m = zs[0] if zs else {}
            cells.append(f"{f(m.get('frac_to_catch_95'))} / {f(m.get('recall@5%'))} / {f(m.get('pr_auc'), False)}")
        L.append("| " + " | ".join(cells) + " |")
    L.append("")
    if S.get("sky130_lodo"):
        L.append("### Reference: same designs held out within sky130 (base features)\n")
        L.append("| sky130 design | violator rate | perfect: catch 95% at | model: catch 95% / R@5% / PR-AUC | est-slew: catch 95% / R@5% / PR-AUC | R8: catch 95% / R@5% / PR-AUC |")
        L.append("|---|---|---|---|---|---|")
        for d, m in S["sky130_lodo"].items():
            r = m.get("base_rate")
            b, r8 = m["baseline_est_load_slew_ratio"], m["baseline_R8"]
            L.append(f"| {d} | {f(r)} | {f(0.95 * r if r else None)} | {f(m.get('frac_to_catch_95'))} / {f(m.get('recall@5%'))} / {f(m.get('pr_auc'), False)} | "
                     f"{f(b.get('frac_to_catch_95'))} / {f(b.get('recall@5%'))} / {f(b.get('pr_auc'), False)} | "
                     f"{f(r8.get('frac_to_catch_95'))} / {f(r8.get('recall@5%'))} / {f(r8.get('pr_auc'), False)} |")
        L.append("")
    L.append("### Zero-shot per GF180 run (signal nets)\n")
    fss = list(S["arms"])
    L.append("| run | violators / nets | perfect catch 95% | est-slew catch 95% / R@5% | R8 catch 95% / R@5% | "
             + " | ".join(f"zero-shot [{fs}] catch 95% / R@5% / PR-AUC" for fs in fss) + " |")
    L.append("|---|---|---|---|---|" + "---|" * len(fss))
    for d in designs:
        b = S["baselines"][d]
        est = {x["run"]: x for x in b["est_load_slew_ratio"].get("per_run", [])}
        r8 = {x["run"]: x for x in b["R8"].get("per_run", [])}
        zs = {fs: {x["run"]: x for x in ((S["arms"][fs].get(d, {}).get("zs") or {}).get("0") or [{}])[0].get("per_run", [])} for fs in fss}
        for run in sorted(est):
            e, r = est[run], r8.get(run, {})
            rate = e["positives"] / e["n"] if e.get("n") else None
            cells = [run, f"{e['positives']} / {e['n']}", f(0.95 * rate if rate else None),
                     f"{f(e.get('frac_to_catch_95'))} / {f(e.get('recall@5%'))}", f"{f(r.get('frac_to_catch_95'))} / {f(r.get('recall@5%'))}"]
            for fs in fss:
                z = zs[fs].get(run, {})
                cells.append(f"{f(z.get('frac_to_catch_95'))} / {f(z.get('recall@5%'))} / {f(z.get('pr_auc'), False)}")
            L.append("| " + " | ".join(cells) + " |")
    L.append("")
    L.append("### Blind spot: violators the pre-route estimate called clean (estimated worst load slew ratio <= 1)\n")
    L.append("| design | GF180 blind spot | GF180 violators | sky130 blind spot (same design) | sky130 violator rate |")
    L.append("|---|---|---|---|---|")
    for d in designs:
        x = S["describe"][d]
        sk = S["describe_sky130"].get(d, {})
        L.append(f"| {d} | {f(x['blind_spot_load'])} | {x['violators']} | {f(sk.get('blind_spot_load'))} | {f(sk.get('violator_rate'))} |")
    L.append("")
    for fs, byd in S["arms"].items():
        for key, label in (("frac_to_catch_95", "nets flagged to catch 95% (lower is better)"), ("recall@5%", "recall @ 5% flagged"), ("pr_auc", "PR-AUC")):
            ks = sorted({k for d in designs for arm in byd.get(d, {}).values() for k in arm}, key=lambda k: (k == "all", int(k) if k != "all" else 0))
            L.append(f"### Adaptation curve [{fs} features]: {label}; per held-out design, mean over draws (min-max)\n")
            L.append("| held-out | arm | " + " | ".join(f"k={k}" for k in ks) + " |")
            L.append("|---|---|" + "---|" * len(ks))
            for d in designs:
                A = byd.get(d, {})
                for arm, lab in (("zs", "zero-shot"), ("gfonly", "GF180-only"), ("merge", "merge"), ("mergew", "merge (re-weighted)"), ("ft", "fine-tune")):
                    if arm not in A:
                        continue
                    cells = []
                    for k in ks:
                        mu, lo, hi, n = mean(A[arm].get(k, []), key)
                        pct = key != "pr_auc"
                        if mu is None:
                            cells.append("")
                        elif n == 1:
                            cells.append(f(mu, pct))
                        else:
                            cells.append(f"{f(mu, pct)} ({f(lo, pct)}-{f(hi, pct)})")
                    L.append(f"| {d} | {lab} | " + " | ".join(cells) + " |")
            L.append("")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
