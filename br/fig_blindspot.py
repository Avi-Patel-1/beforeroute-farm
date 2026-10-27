#!/usr/bin/env python3
"""Blind-spot hero for the problem slide: estimated vs signoff worst load-slew ratio per signal net of one run;
red = signoff violators the post-global-route estimate called clean. Same panel, palette and dark slide style as
br/figs_v2.py (fig_blindspot), with the stage named "post-global-route" (not "pre-route") and a free height so it
can sit beside another half-slide figure.

Usage: python3 br/fig_blindspot.py --out figures/v2/ [--run d1-picorv32-006] [--label PicoRV32] [--height 3.35]
       [--name blindspot_v3]
Reads only the rows of --run from results/dataset.parquet (pyarrow row filter, a few columns), so memory stays small.
Also prints the per-run blind share of the eight hero baselines (figs_v2.BLIND_GRID_RUNS) with their median, the
cross-design number quoted next to this figure. All text >= 14 pt at the drawn size.
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

COLS = ["run", "join_how", "driver_kind", "sigtype", "worst_load_slew_ratio", "act_load_slew_ratio"]


def run_rows(runs):
    """Signal nets with a joined driver (the project-wide filter of figs_v2.signal_nets), for the given runs only."""
    import pyarrow.parquet as pq

    t = pq.read_table(F.DATASET, columns=COLS, filters=[("run", "in", list(runs))])
    d = t.to_pandas()
    d = d[(d["join_how"] != "none") & (d["driver_kind"] != "none") & (d["sigtype"] == "SIGNAL")]
    return d[d["act_load_slew_ratio"].notna() & d["worst_load_slew_ratio"].notna()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="d1-picorv32-006")
    ap.add_argument("--label", default="PicoRV32")
    ap.add_argument("--height", type=float, default=3.35, help="figure height in inches (width 5.95)")
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--name", default="blindspot_v3")
    ap.add_argument("--title", default="The estimate misses most signoff violators",
                    help="bold title line above the run header ('' for none)")
    a = ap.parse_args()
    F.setup_style()
    grid = [r for r, _ in F.BLIND_GRID_RUNS]
    d = run_rows(sorted(set(grid) | {a.run}))
    x = d[d["run"] == a.run]
    if not len(x):
        print(f"[blindspot] no rows for {a.run}")
        return 1
    W, H = 5.95, a.height
    fig = plt.figure(figsize=(W, H))
    head = 0.75 if a.title else 0.40                        # inches: title + header line, or header line only
    top, bottom, left, right = head, 0.70, 0.60, 0.20      # header / x label / y label / last tick
    ax = fig.add_axes([left / W, bottom / H, (W - left - right) / W, (H - top - bottom) / H])
    nums = F._blind_panel(ax, x["worst_load_slew_ratio"].values, x["act_load_slew_ratio"].values, gx=(46, 19))
    ax.set_xlabel("Estimated slew ÷ limit  (post-global-route)", labelpad=3)
    ax.set_ylabel("Signoff slew ÷ limit", labelpad=4)
    Y = F.YMAX
    ax.text(0.04, Y - 0.14, f"{nums['blind']:,} of {nums['signoff_slew_violators']:,}", fontsize=F.FS + 8,
            fontweight="semibold", color=F.INK, va="top", ha="left", zorder=6, path_effects=F.HALO)
    ax.text(0.04, Y - 0.95, f"signoff slew violators ({F.pct(nums['blind_frac'])})\nlooked clean to the estimate",
            fontsize=F.FS, color=F.INK, va="top", ha="left", linespacing=1.15, zorder=6, path_effects=F.HALO)
    ax.text(F.XMAX - 0.03, 1.06, f"caught: {nums['caught_by_estimate']:,}", fontsize=F.FS, color=F.INK2, va="bottom",
            ha="right", zorder=6, path_effects=F.HALO)
    ax.text(F.XMAX - 0.03, 0.62, f"false alarms: {nums['false_alarms']:,}", fontsize=F.FS, color=F.INK2, va="center",
            ha="right", zorder=6)
    ax.text(F.XMAX - 0.03, 0.22, "diagonal: estimate = signoff", fontsize=F.FS, color=F.GREY, va="center", ha="right", zorder=6)
    if a.title:
        fig.text(0.012, 1 - 0.05 / H, a.title, fontsize=F.FS + 1, fontweight="semibold", color=F.INK, va="top", ha="left")
    fig.text(0.012, 1 - (0.40 if a.title else 0.05) / H, f"{a.label}, one run: {nums['nets']:,} signal nets, worst of 9 corners",
             fontsize=F.FS, color=F.INK2, va="top", ha="left")
    # cross-design context: blind share per hero baseline (same definition), quoted beside the figure
    per = {}
    for r in grid:
        g = d[d["run"] == r]
        est, act = g["worst_load_slew_ratio"].values, g["act_load_slew_ratio"].values
        v = int((act > 1).sum())
        if v:
            per[r] = {"violators": v, "blind": int(((act > 1) & (est <= 1)).sum()),
                      "false_alarms": int(((est > 1) & (act <= 1)).sum())}
            per[r]["blind_frac"] = per[r]["blind"] / v
    fr = [p["blind_frac"] for p in per.values()]
    nums.update(run=a.run, label=a.label, size_in=[W, H], hero_baselines=per,
                hero_blind_median=float(np.median(fr)) if fr else None,
                hero_blind_range=[float(min(fr)), float(max(fr))] if fr else None,
                hero_false_alarms_range=[min(p["false_alarms"] for p in per.values()),
                                         max(p["false_alarms"] for p in per.values())] if per else None)
    F.save(fig, a.out, a.name, nums)
    print(json.dumps({k: v for k, v in nums.items() if k != "hero_baselines"}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
