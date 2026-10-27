#!/usr/bin/env python3
"""Flag rate vs the hidden signoff margin: share of signal nets the model flags before routing, binned by the
signoff slew/cap ratio the model never sees (baseline run of each held-out base). Dark slide style (figs_v2).

Usage: python3 br/fig_riskcurve.py --out figures/v2/
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs_v2 as F  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

BASES = [("d3-des-000", "DES", "thr500-70"), ("d3-y_huff-000", "y_huff", "thr500-70"),
         ("d3-ocs_blitter-000", "ocs_blitter", "thr500-70"), ("d3-bm64-000", "BM64", "thr500-70"),
         ("d3-md5-000", "MD5", "thr500-70"), ("d3-salsa20-000", "salsa20", "thr500-70")]
EDGES = [0.0, 0.8, 0.9, 0.97, 1.0, 99]
LABELS = ["< 0.8×", "0.8–0.9×", "0.9–0.97×", "0.97–1×", "≥ 1×"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=F.RESULTS)
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--name", default="riskcurve")
    a = ap.parse_args()
    F.setup_style()
    fig = plt.figure(figsize=(5.95, 4.5))
    ax = fig.add_axes([0.13, 0.25, 0.83, 0.55])
    x = np.arange(len(LABELS))
    nums = {}
    drawn, allrates, names = 0, [], []
    for base, label, arm in BASES:
        sc = os.path.join(a.results, base, f"flagged_{arm}.scores.csv")
        sp = os.path.join(a.results, base, "nets_signoff.jsonl")
        if not (os.path.exists(sc) and os.path.exists(sp)):
            continue
        p = {r["net"]: float(r["p"]) for r in csv.DictReader(open(sc))}
        so = {}
        for line in open(sp):
            r = json.loads(line)
            if r.get("sigtype") == "SIGNAL":
                so[r["net"]] = max(r.get("worst_load_slew_ratio") or 0, r.get("driver_slew_ratio") or 0, r.get("cap_ratio") or 0)
        rates, counts = [], []
        for lo, hi in zip(EDGES[:-1], EDGES[1:]):
            nets = [n for n, v in so.items() if lo <= v < hi and n in p]
            rates.append(100 * float(np.mean([p[n] >= 0.5 for n in nets])) if nets else np.nan)
            counts.append(len(nets))
        ax.plot(x, rates, "-", color=F.GREEN, lw=1.2, alpha=0.45, zorder=2)
        nums[label] = {"rates_pct": rates, "counts": counts}
        allrates.append(rates)
        names.append(label)
        drawn += 1
    if not drawn:
        print("[riskcurve] no inputs")
        return 0
    med = np.nanmedian(np.array(allrates, dtype=float), axis=0)
    ax.plot(x, med, "-o", color=F.GREEN, lw=3.0, ms=8, zorder=4)
    for xi, v in zip(x, med):
        ax.text(xi, v + 5, f"{v:.0f}%", color=F.INK, fontsize=F.FS, ha="center", va="bottom", zorder=5, path_effects=F.HALO)
    nums["median_rates_pct"] = [float(v) for v in med]
    ax.axvspan(2.5, 3.5, color=F.ROSE, alpha=0.14, lw=0, zorder=0)
    ax.text(3.0, 4, "near-misses", color=F.ROSE, fontsize=F.FS, ha="center")
    ax.set_xticks(x)
    ax.set_xticklabels(LABELS, fontsize=F.FS)
    ax.set_xlim(-0.4, len(LABELS) - 1 + 0.4)
    ax.set_ylim(0, 115)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels(["0", "25%", "50%", "75%", "100%"])
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_xlabel("signoff slew/cap ÷ limit (unknown before routing)", labelpad=4)
    fig.text(0.02, 0.965, "The model sees the signoff margin before routing", fontsize=F.FS + 1, fontweight="semibold", color=F.INK, va="top")
    fig.text(0.02, 0.89, f"nets flagged (p ≥ 0.5): median of {len(names)} unseen designs (thin: each)", fontsize=F.FS - 1, color=F.INK2, va="top")
    F.save(fig, a.out, a.name, nums)
    print(json.dumps(nums, indent=1)[:1500])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
