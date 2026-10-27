#!/usr/bin/env python3
"""Calibration ladder figure (half-slide, dark style of br/figs_v2.py): nets flagged to catch 95% of signoff violators,
median over the held-out designs, for the timer's estimate, rule R8, R8 with three RC calibrations of the estimated net
cap fit on the other designs (one wire-cap scale; per-layer; per-layer + length/fanout/density), the full GBM, and R8
with each net's true extracted cap (an upper bound for any cap calibration); floor = flag only violators.

Input: agents/analysis/calib_ladder.json (br/calib_ladder.py). Usage: python3 br/fig_calib_ladder.py --out figures/v2
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs_v2 as F  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

ROWS = [  # (key in calib_ladder.json designs, label, marker, color, filled)
    ("est_slew_ablation", "Timer's estimate", "o", F.GREY, True),
    ("rule_R8_ablation", "Rule R8", "s", F.BLUE, True),
    ("rc_wire", "R8, wire cap × 2.05", "D", F.INK2, False),
    ("lgbm_full_ablation", "GBM (BeforeRoute)", "*", F.GREEN, True),
    ("rc_oracle", "R8, true extracted cap", "o", F.MUTED, False),
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(F.ROOT, "agents", "analysis", "calib_ladder.json"))
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--name", default="calib_ladder")
    a = ap.parse_args()
    F.setup_style()
    D = json.load(open(a.data))["designs"]
    med = {k: float(np.median([d[k] for d in D.values()])) for k, *_ in ROWS}
    fl = float(np.median([d["floor"] for d in D.values()]))
    wins_cal = sum(1 for d in D.values() if d["lgbm_full_ablation"] < d["rc_wire"])
    s_med = float(np.median([d["s_wire"] for d in D.values()]))
    wins_r8 = sum(1 for d in D.values() if d["lgbm_full_ablation"] < d["rule_R8_ablation"])
    from scipy.stats import binomtest
    p_cal = binomtest(wins_cal, len(D), 0.5).pvalue
    fig = plt.figure(figsize=(5.6, 4.5))
    ax = fig.add_axes([0.445, 0.255, 0.525, 0.44])
    ny = len(ROWS)
    ys = np.arange(ny)[::-1]
    ax.axvline(100 * fl, color=F.INK2, lw=1.5, ls=(0, (1, 2.2)), zorder=1)
    for y, (k, lab, mk, col, filled) in zip(ys, ROWS):
        v = 100 * med[k]
        ms = {"*": 19, "s": 10, "o": 11, "D": 9}[mk]
        ax.plot([100 * fl, v], [y, y], color=F.AXIS, lw=1.0, zorder=2)
        ax.plot(v, y, mk, ms=ms, color=col, mfc=col if filled else F.SURFACE, mec=F.SURFACE if filled else col,
                mew=1.4 if filled else 1.8, zorder=4)
        ax.text(v + 0.35, y, f"{v:.1f}%", fontsize=F.FS, color=F.INK if k.startswith("lgbm") else F.INK2, va="center",
                ha="left", zorder=5)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[1] for r in ROWS])
    for t, r in zip(ax.get_yticklabels(), ROWS):
        t.set_color(F.INK if r[0].startswith("lgbm") else (F.MUTED if r[0] == "rc_oracle" else F.INK2))
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlim(0, 8)
    ax.set_xticks([0, 2, 4, 6, 8])
    ax.set_xticklabels(["0", "2%", "4%", "6%", "8%"])
    ax.set_ylim(-0.6, ny - 0.4)
    ax.grid(True, axis="x", zorder=0)
    ax.text(100 * fl, ny - 0.45, f"floor {100 * fl:.1f}%", fontsize=F.FS, color=F.INK2, ha="center", va="bottom", zorder=5)
    fig.text(0.012, 0.975, "Most of the estimate's error is one\nnumber: its wire cap is about 2× low", fontsize=F.FS + 1,
             fontweight="semibold", color=F.INK, va="top", linespacing=1.15)
    fig.text(0.012, 0.835, "Nets flagged to catch 95% of violators", fontsize=F.FS, color=F.INK2, va="top")
    lines = [f"Median of {len(D)} unseen designs; scale fit on the others.",
             f"GBM beats the scaled estimate on {wins_cal} of {len(D)} (p ≈ {float(f'{p_cal:.1g}'):g})."]
    fig.text(0.012, 0.012, "\n".join(lines), fontsize=F.FS, color=F.MUTED, va="bottom", linespacing=1.25)
    nums = {"median_pct": {k: round(100 * v, 3) for k, v in med.items()}, "floor_pct": round(100 * fl, 3),
            "gbm_beats_wire_scale": wins_cal, "wire_scale_median_fit": s_med, "gbm_beats_R8": wins_r8, "designs": len(D), "sign_test_p_vs_best_fit": p_cal,
            "source": os.path.relpath(a.data, F.ROOT)}
    F.save(fig, a.out, a.name, nums)
    print(json.dumps(nums, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
