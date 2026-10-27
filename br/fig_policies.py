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
BASES_45 = [("d3b-sha512-000", "SHA-512"), ("d3b-ldpcenc-000", "LDPC"), ("d5-blabla-000", "BlaBla"),
            ("d5-chacha-000", "ChaCha"), ("d5-point_add-000", "point_add")]
# Rounds 4-5: BeforeRoute's p >= 0.5 arm is thr500-70 on Round 4 and thr500-70c on Round 5 (scored at the checkpoint)
ALIAS = {"thr500-70": ["thr500-70", "thr500-70c"]}
POL = [  # (arm, label, marker, color, size, filled)
    ("uni70", "uniform 70%, every net", "s", F.ROSE, 9, True),
    ("rcal213-10", "corrected estimate + stock repair, every net", "D", F.BLUE, 8, True),
    ("rct213-70", "corrected estimate's list + our repair", "D", F.BLUE, 8, False),
    ("thr500-70", "BeforeRoute (model p ≥ 0.5)", "*", F.GREEN, 15, True),
]
POL_A14 = [  # Addendum 14 (model list + corrected parasitics in the repair), drawn with --a14
    ("thr500-10cr", "model list, corrected parasitics, 10%", "^", F.GREEN, 9, False),
    ("thr500-30cr", "model list, corrected parasitics, 30%", "v", F.GREEN, 9, False),
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
        d = {"base": b, "label": lab + (" †" if H0 is not None and H0 <= 0 else ""), "V0": V0}
        for arm, *_ in POL:
            r = next((R[x] for x in ALIAS.get(arm, [arm]) if x in R), None)
            if r is None:
                continue
            d[arm] = {"left_pct": 100.0 * r["signoff_violating_data_nets"] / V0, "left": r["signoff_violating_data_nets"],
                      "cells": (r.get("resized") or 0) + (r.get("buffers") or 0),
                      "hold_pct": 100.0 * r["hold_ws"] / H0 if H0 and H0 > 0 and r.get("hold_ws") is not None else None}
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
    ap.add_argument("--a14", action="store_true", help="also draw the Addendum-14 arms")
    ap.add_argument("--rounds45", action="store_true", help="Round-4/5 bases; draws the Addendum-15 arm thr500-30cr")
    ap.add_argument("--with30cr", action="store_true", help="Round 3 plus the combined policy thr500-30cr (exploratory there)")
    ap.add_argument("--subtitle", default=None)
    ap.add_argument("--all11", action="store_true", help="Round 3 and Rounds 4-5 in one figure; BeforeRoute 70% vs the combined policy")
    a = ap.parse_args()
    global POL, BASES
    if a.a14:
        POL = POL + POL_A14
    if a.with30cr:
        POL = POL + [("thr500-30cr", "model list + corrected parasitics, 30%", "^", F.GREEN, 10, False)]
    if a.rounds45:
        BASES = BASES_45
        POL = [p for p in POL if p[0] != "rct213-70"] + [("thr500-30cr", "model list + corrected parasitics, 30% (Addendum 15)", "^", F.GREEN, 10, False)]
    if a.all11:
        BASES = BASES + BASES_45
        POL = [("uni70", "uniform 70%, every net", "s", F.ROSE, 9, True),
               ("rcal213-10", "corrected estimate + stock repair, every net", "D", F.BLUE, 8, True),
               ("thr500-70", "BeforeRoute: model list, 70% margin", "*", F.GREEN, 14, False),
               ("thr500-30cr", "BeforeRoute: model list, corrected wire cap, 30%", "^", F.GREEN, 12, True)]
    F.setup_style()
    D = rows(a.results)
    fig = plt.figure(figsize=(a.width, a.height))
    n = len(D)
    ys = np.arange(n)[::-1].astype(float)
    if a.all11:  # a gap between Round 3 and Rounds 4-5
        n3 = sum(1 for d in D if d["base"].startswith("d3-"))
        ys = np.array([n - i - (0 if i < n3 else 0.8) for i in range(n)], dtype=float) - 0.2
    panels = [("left_pct", "violators left, % of baseline", (0, None)), ("cells", "cells changed (log)", None),
              ("hold_pct", "hold slack kept, %", None)]
    left0, gap, top, bottom = (0.17 if (a.rounds45 or a.all11) else 0.145), 0.035, (0.80 if a.all11 else 0.78), (0.2 if a.all11 else 0.25)
    if not a.title:
        top = 0.88
        if a.all11:
            bottom = 0.27
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
                        mew=1.4 if filled else 1.8, zorder=(5 if arm == "thr500-30cr" else 4) if arm.startswith("thr500") else 3)
        ax.set_ylim(min(ys) - 0.6, max(ys) + 0.6)
        if a.all11:  # separator between Round 3 and Rounds 4-5
            n3 = sum(1 for d in D if d["base"].startswith("d3-"))
            ax.axhline((ys[n3 - 1] + ys[n3]) / 2, color=F.AXIS, lw=1.0, zorder=1)
        ax.set_yticks(ys)
        ax.set_yticklabels([f"{d['label']} ({d['V0']:,})" for d in D] if j == 0 else [])
        ax.tick_params(axis="y", length=0)
        ax.xaxis.grid(True, zorder=0)
        ax.set_axisbelow(True)
        ax.set_title(title, fontsize=F.FS, color=F.INK2, loc="left", pad=6)
        if key == "cells":
            ax.set_xscale("log")
            ax.set_xlim(200, 9000 if a.all11 else 7000)
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
    if a.title:
        fig.text(0.012, 0.975, a.title, fontsize=F.FS + 3,
                 fontweight="semibold", color=F.INK, va="top")
    sub = a.subtitle or ("Round 3: six design families the model never saw (baseline violators in brackets); "
                         "one run per arm; left of the dashed line = hold violated")
    fig.text(0.012, 0.895 if a.title else 0.985, sub, fontsize=F.FS - 1, color=F.INK2, va="top")
    items = [(mk, col, ms, lab, None, filled) for _, lab, mk, col, ms, filled in POL]
    if len(items) <= 4:
        F.key_row(fig, items[:2], 0.012, 0.115, gap=0.03)
        F.key_row(fig, items[2:], 0.012, 0.045, gap=0.03)
    else:
        F.key_row(fig, items[:3], 0.012, 0.13, gap=0.02)
        F.key_row(fig, items[3:], 0.012, 0.055, gap=0.02)
    nums = {d["base"]: {k: v for k, v in d.items() if k not in ("base",)} for d in D}
    F.save(fig, a.out, a.name, nums)
    print(json.dumps(nums, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
