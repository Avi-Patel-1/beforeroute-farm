#!/usr/bin/env python3
"""Paired chart for the deck and paper: per design, signal violators left after the corrected stock repair (hollow
diamond) and after BeforeRoute (triangle; hollow = exploratory for this policy), on a log axis, grouped as
prospective / replication / exploratory, with the no-repair count as a faint tick and the cells-changed ratio at right.
V = signal nets violating max slew or max cap at nine-corner signoff (labels.json).
Usage: fig_pairs.py [--other rcal213-10] [--policy thr500-30cr] [--name pairs14] [--title ...]
"""
from __future__ import annotations

import argparse
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs_v2 as F  # noqa: E402
import paper_table as PT  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402

GROUPS = [("Prospective, pre-registered (Rounds 4–5)", PT.BASES["Round 4-5 (Addendum 15)"], "pre"),
          ("Pre-registered replication (Round 1)", PT.BASES["Round 1 (Addendum 17)"], "rep"),
          ("Exploratory for this policy (Round 3)", PT.BASES["Round 3"], "exp")]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--other", default="rcal213-10")
    ap.add_argument("--policy", default="thr500-30cr")
    ap.add_argument("--other-label", default="Stock repair, corrected wire cap, every net, 10%")
    ap.add_argument("--policy-label", default="BeforeRoute: model list, corrected wire cap, 30%")
    ap.add_argument("--name", default="pairs14")
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--width", type=float, default=11.5)
    ap.add_argument("--rowh", type=float, default=0.36, help="inches per row")
    ap.add_argument("--fs", type=int, default=0, help="font size offset")
    a = ap.parse_args()
    F.setup_style()
    rows = {(r["base"], r["arm"]): r for r in PT.table(None, ["rerun", a.other, a.policy])}
    items = []
    for gname, bases, gk in GROUPS:
        items.append(("group", gname, gk))
        for b in bases:
            o, p, z = rows.get((b, a.other)), rows.get((b, a.policy)), rows.get((b, "rerun"))
            if o and p and o["V"] is not None and p["V"] is not None:
                items.append(("row", b, gk, o, p, z))
    n = len(items)
    F.FS = F.FS + a.fs
    fig = plt.figure(figsize=(a.width, a.rowh * n + 1.35))
    ax = fig.add_axes([0.2, 0.19, 0.66, 0.79])
    lo, hi = math.log10(0.45), math.log10(3000)
    y = 0
    tot = {"o": 0, "p": 0, "co": 0, "cp": 0}
    yt, yl = [], []
    for it in items:
        y -= 1
        if it[0] == "group":
            ax.text(lo - 0.02, y, it[1], ha="left", va="center", fontsize=F.FS - 2, color="#d79a52", fontweight="bold",
                    transform=ax.transData)
            continue
        _, b, gk, o, p, z = it
        lx = lambda v: math.log10(max(v, 0.6))
        if z and z["V"]:
            ax.plot([lx(z["V"])] * 2, [y - 0.28, y + 0.28], color=F.MUTED, lw=1.6, zorder=2)
        ax.plot([lx(o["V"]), lx(p["V"])], [y, y], color=F.AXIS, lw=2, zorder=2)
        ax.scatter([lx(o["V"])], [y], marker="D", s=58, facecolor=F.SURFACE, edgecolor=F.BLUE, linewidth=1.8, zorder=3)
        ax.scatter([lx(p["V"])], [y], marker="^", s=86, facecolor=(F.SURFACE if gk == "exp" else F.GREEN), edgecolor=F.GREEN,
                   linewidth=1.6, zorder=4)
        yt.append(y); yl.append(PT.NAMES[b])
        if o["cells"] and p["cells"]:
            ax.text(hi + 0.05, y, f"{p['cells'] / o['cells']:.2f}×", ha="left", va="center", fontsize=F.FS - 2, color=F.INK2,
                    transform=ax.transData, family="DejaVu Sans Mono")
            tot["co"] += o["cells"]; tot["cp"] += p["cells"]
        tot["o"] += o["V"]; tot["p"] += p["V"]
    ax.set_yticks(yt)
    ax.set_yticklabels(yl, fontsize=F.FS - 1, color=F.INK)
    ax.set_ylim(y - 0.6, 0.4)
    ticks = [0.6, 1, 3, 10, 30, 100, 300, 1000, 3000]
    ax.set_xticks([math.log10(t) for t in ticks])
    ax.set_xticklabels(["0" if t < 1 else f"{t:,}" for t in ticks], fontsize=F.FS - 2, color=F.INK2)
    ax.set_xlim(lo, hi)
    ax.grid(axis="x", color=F.GRID, lw=0.8)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color(F.AXIS)
    ax.tick_params(axis="y", length=0)
    ax.set_xlabel("signal nets still violating max slew/cap at nine-corner signoff (log)", fontsize=F.FS - 2, color=F.INK2)
    ax.text(hi + 0.05, -0.55, "cells changed\n(ratio)", ha="left", va="bottom", fontsize=F.FS - 4, color=F.MUTED, transform=ax.transData)
    # legend
    lg = fig.add_axes([0.2, 0.0, 0.78, 0.09]); lg.axis("off")
    lg.scatter([0.0], [0.72], marker="D", s=58, facecolor=F.SURFACE, edgecolor=F.BLUE, linewidth=1.8)
    lg.text(0.015, 0.72, a.other_label, va="center", fontsize=F.FS - 3, color=F.INK2)
    lg.scatter([0.0], [0.22], marker="^", s=86, facecolor=F.GREEN, edgecolor=F.GREEN)
    lg.text(0.015, 0.22, a.policy_label + " (hollow: exploratory design)", va="center", fontsize=F.FS - 3, color=F.INK2)
    lg.plot([0.62, 0.62], [0.6, 0.84], color=F.MUTED, lw=1.6)
    lg.text(0.632, 0.72, "no repair", va="center", fontsize=F.FS - 3, color=F.INK2)
    lg.set_xlim(-0.01, 1.0); lg.set_ylim(0, 1)
    nums = {"totals": tot, "cells_ratio_pooled": round(tot["cp"] / tot["co"], 3) if tot["co"] else None}
    F.save(fig, a.out, a.name, nums)
    print(nums)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
