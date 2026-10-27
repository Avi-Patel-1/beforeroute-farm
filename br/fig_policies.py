#!/usr/bin/env python3
"""Repair policies compared on the Round-3 bases (dark style of br/figs_v2.py): one row per base, three panels —
signal violators left at signoff (% of the re-run baseline), cells changed by the repair step, and hold slack kept
(% of the baseline's worst hold slack). Policies: uniform 70% margin on every net (default estimate), the stock
post-GRT repair at its default 10% margin with the wire cap scaled to extraction (rcal213-10), the calibrated list with
BeforeRoute's actuator (rct213-70), and BeforeRoute (model p >= 0.5, thr500-70). Missing arms are simply not drawn.

Usage: python3 br/fig_policies.py --out figures/v2 [--name policies] [--width 12.1 --height 4.6]
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

BASES = [("d3-des-000", "DES"), ("d3-y_huff-000", "y_huff"), ("d3-ocs_blitter-000", "ocs_blitter"),
         ("d3-bm64-000", "BM64"), ("d3-md5-000", "MD5"), ("d3-salsa20-000", "salsa20")]
POL = [  # (arm, label, marker, color, size, filled)
    ("uni70", "uniform 70% on every net", "s", F.ROSE, 9, True),
    ("rcal213-10", "wire cap ×2.13 + stock repair (10%, every net)", "D", F.BLUE, 8, True),
    ("rct213-70", "wire cap ×2.13 list + BeforeRoute repair", "D", F.BLUE, 8, False),
    ("thr500-70", "BeforeRoute (model p ≥ 0.5)", "*", F.GREEN, 15, True),
]


def rows(results):
    out = []
    for b, lab in BASES:
        p = os.path.join(results, b, "hero_summary.json")
        if not os.path.exists(p):
            continue
        R = {("base" if r["tag"] == b else r["tag"][len(b) + 1:]): r for r in json.load(open(p))["arms"]}
        ref = R.get("rerun") or R.get("base")
        V0, H0 = ref["signoff_violating_data_nets"], ref.get("hold_ws")
        d = {"base": b, "label": lab, "V0": V0}
        for arm, *_ in POL:
            r = R.get(arm)
            if r is None:
                continue
            d[arm] = {"left_pct": 100.0 * r["signoff_violating_data_nets"] / V0, "left": r["signoff_violating_data_nets"],
                      "cells": (r.get("resized") or 0) + (r.get("buffers") or 0),
                      "hold_pct": 100.0 * r["hold_ws"] / H0 if H0 and r.get("hold_ws") is not None else None}
        out.append(d)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=F.RESULTS)
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--name", default="policies")
    ap.add_argument("--width", type=float, default=12.1)
    ap.add_argument("--height", type=float, default=4.6)
    ap.add_argument("--title", default="Repair policies on six designs the model never saw")
    a = ap.parse_args()
    F.setup_style()
    D = rows(a.results)
    fig = plt.figure(figsize=(a.width, a.height))
    n = len(D)
    ys = np.arange(n)[::-1]
    panels = [("left_pct", "violators left, % of baseline", (0, None)), ("cells", "cells changed (log)", None),
              ("hold_pct", "hold slack kept, %", None)]
    left0, gap, top, bottom = 0.145, 0.035, 0.78, 0.25
    w = (0.985 - left0 - 2 * gap) / 3
    for j, (key, title, _) in enumerate(panels):
        ax = fig.add_axes([left0 + j * (w + gap), bottom, w, top - bottom])
        vals = []
        for y, d in zip(ys, D):
            for arm, lab, mk, col, ms, filled in POL:
                if arm not in d or d[arm][key] is None:
                    continue
                v = d[arm][key]
                vals.append(v)
                ax.plot(v, y, mk, ms=ms, color=col, mfc=col if filled else F.SURFACE, mec=F.SURFACE if filled else col,
                        mew=1.4 if filled else 1.8, zorder=4 if arm == "thr500-70" else 3)
        ax.set_ylim(-0.6, n - 0.4)
        ax.set_yticks(ys)
        ax.set_yticklabels([f"{d['label']} ({d['V0']:,})" for d in D] if j == 0 else [])
        ax.tick_params(axis="y", length=0)
        ax.xaxis.grid(True, zorder=0)
        ax.set_axisbelow(True)
        ax.set_title(title, fontsize=F.FS, color=F.INK2, loc="left", pad=6)
        if key == "cells":
            ax.set_xscale("log")
            ax.set_xlim(200, 7000)
            ax.set_xticks([300, 1000, 3000])
            ax.set_xticklabels(["300", "1,000", "3,000"])
            ax.xaxis.set_minor_formatter(F.mticker.NullFormatter())
        elif key == "left_pct":
            hi = max(vals + [10]) * 1.1
            ax.set_xlim(-0.5, hi)
            ax.set_xticks([t for t in (0, 5, 10, 15, 20, 25) if t <= hi])
            ax.xaxis.set_major_formatter(F.mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
        else:
            lo = min(vals + [0])
            ax.set_xlim(min(-30, lo - 10), 115)
            ax.axvline(0, color=F.CRIT, lw=1.0, ls=(0, (3, 2)), zorder=1)
            ax.xaxis.set_major_formatter(F.mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    fig.text(0.012, 0.975, a.title, fontsize=F.FS + 3,
             fontweight="semibold", color=F.INK, va="top")
    fig.text(0.012, 0.895, "Round 3: six design families the model never saw (baseline violators in brackets); "
             "one run per arm; left of the dashed line = hold violated", fontsize=F.FS - 1, color=F.INK2, va="top")
    items = [(mk, col, ms, lab, None, filled) for _, lab, mk, col, ms, filled in POL]
    F.key_row(fig, items[:2], 0.012, 0.115, gap=0.03)
    F.key_row(fig, items[2:], 0.012, 0.045, gap=0.03)
    nums = {d["base"]: {k: v for k, v in d.items() if k not in ("base",)} for d in D}
    F.save(fig, a.out, a.name, nums)
    print(json.dumps(nums, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
