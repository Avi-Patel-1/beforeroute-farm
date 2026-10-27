#!/usr/bin/env python3
"""'Fix what failed' vs 'fix what is at risk': residual signoff violators after repairing exactly the
baseline's violators (signoff-guided loop, pass 1) vs after repairing the model's p >= 0.5 list, split into
violators that already failed at baseline and new ones; plus where the new ones sat before the ECO.
Same dark slide style as br/figs_v2.py.

Usage: python3 br/fig_whackamole.py --out figures/v2/
       python3 br/fig_whackamole.py --compact --out figures/v2/     (half-slide slot: whackamole_compact.png)
--compact redraws the hindsight half only, at 5.95 x --height in (default 3.35) with every label >= 14 pt: per base,
the share of the violators left after one fix-what-failed pass that are new (count of new of left), plus where the new
ones sat before the fix and the loop-design caveat.
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
from matplotlib.patches import Rectangle  # noqa: E402

BASES = [("d3-des-000", "DES"), ("d3-y_huff-000", "y_huff"), ("d3-ocs_blitter-000", "ocs_blitter"),
         ("d3-bm64-000", "BM64"), ("d3-md5-000", "MD5"), ("d3-salsa20-000", "salsa20"),
         ("d1-picorv32-006", "PicoRV32-006"), ("d1-picorv32-016", "PicoRV32-016"), ("d1-aes_cipher-000", "AES")]


def violators(results, tag):
    p = os.path.join(results, tag, "labels.json")
    if not os.path.exists(p):
        return None
    return {r["net"] for r in json.load(open(p))["nets"] if r.get("violated") and r.get("sigtype_s") == "SIGNAL"}


def draw_compact(rows, near, out, name, size):
    """Half-slide version (>= 14 pt): share of the residual violators of one fix-what-failed pass that are new."""
    W, H = size
    fig = plt.figure(figsize=size)

    def fy(inch_from_top):
        return 1 - inch_from_top / H

    fig.text(0.012, fy(0.05), "Fixing exactly what failed creates new failures", fontsize=F.FS + 1, fontweight="semibold",
             color=F.INK, va="top")
    fig.text(0.012, fy(0.40), "violators left after one pass: share that are new", fontsize=F.FS, color=F.INK2, va="top")
    foot = 0.62                                     # two footer lines (in)
    top, bottom = 0.86, foot + 0.42                 # plot area (in from top / from bottom, incl. tick labels)
    left, right = 1.30, 1.10                        # base names / count labels (in)
    ax = fig.add_axes([left / W, bottom / H, (W - left - right) / W, (H - top - bottom) / H])
    n = len(rows)
    y = np.arange(n)[::-1]
    share = np.array([100.0 * r["hind_new"] / max(1, r["hind_old"] + r["hind_new"]) for r in rows])
    ax.barh(y, [100] * n, 0.66, color="#1c1c1c", zorder=1)          # 100% track: the rest failed at baseline too
    ax.barh(y, share, 0.66, color=F.ROSE, zorder=2)
    for yi, r, s in zip(y, rows, share):
        tot = r["hind_old"] + r["hind_new"]
        ax.text(s - 1.5, yi, f"{s:.0f}%", va="center", ha="right", fontsize=F.FS, fontweight="semibold", color=F.INK, zorder=3)
        ax.text(102, yi, f"{r['hind_new']} of {tot}", va="center", ha="left", fontsize=F.FS, color=F.INK2,
                zorder=3, clip_on=False)
    ax.set_yticks(y)
    ax.set_yticklabels([r["label"] for r in rows], fontsize=F.FS)
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 100)
    ax.set_ylim(-0.6, n - 0.4)
    ax.set_xticks([0, 50, 100])
    ax.set_xticklabels(["0", "50%", "100%"])
    ax.spines["left"].set_visible(False)
    ax.xaxis.grid(True, zorder=0)
    ax.set_axisbelow(True)
    med = float(np.median(near)) if near else None
    lines = []
    if med is not None:
        lines.append(f"New ones sat at a median {med:.2f}× the limit before the fix.")
    lines.append("Caveat: re-routed from post-GRT, no guard band (not an ECO).")
    fig.text(0.012, 0.012, "\n".join(lines), fontsize=F.FS, color=F.MUTED, va="bottom", linespacing=1.25)
    tot_new = sum(r["hind_new"] for r in rows)
    tot_left = sum(r["hind_old"] + r["hind_new"] for r in rows)
    nums = dict(rows=rows, share_new_pct=[float(s) for s in share], share_new_range_pct=[float(share.min()), float(share.max())],
                new_total=tot_new, left_total=tot_left, near_median=med, n_new=len(near))
    F.save(fig, out, name, nums)
    return nums


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=F.RESULTS)
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--name", default=None, help="output name (default whackamole, or whackamole_compact with --compact)")
    ap.add_argument("--model-arm", default="thr500-70")
    ap.add_argument("--compact", action="store_true", help="half-slide version (hindsight pass only), >= 14 pt")
    ap.add_argument("--height", type=float, default=3.35, help="height in inches of the --compact version (width 5.95)")
    a = ap.parse_args()
    a.name = a.name or ("whackamole_compact" if a.compact else "whackamole")
    F.setup_style()
    rows, near, flagged_new, flagged_on = [], [], [0, 0], []
    for base, label in BASES:
        # reference = the rerun arm (same rebuilt checkpoint as the arms), as for every Round-3 number
        b = violators(a.results, f"{base}-rerun") or violators(a.results, base)
        h = violators(a.results, f"{base}-lst-sgl1-70")
        m = violators(a.results, f"{base}-{a.model_arm}")
        if b is None or h is None:
            continue
        h_new = h - b
        rows.append(dict(base=base, label=label, baseline=len(b), hind_old=len(h & b), hind_new=len(h_new),
                         model_old=len(m & b) if m is not None else None, model_new=len(m - b) if m is not None else None))
        so = {}
        sp = os.path.join(a.results, base, "nets_signoff.jsonl")
        if os.path.exists(sp):
            for line in open(sp):
                r = json.loads(line)
                so[r["net"]] = max(r.get("worst_load_slew_ratio") or 0, r.get("driver_slew_ratio") or 0, r.get("cap_ratio") or 0)
            near += [so[n] for n in h_new if n in so]
        sc = os.path.join(a.results, base, f"flagged_{a.model_arm}.scores.csv")
        if os.path.exists(sc):
            p = {r["net"]: float(r["p"]) for r in csv.DictReader(open(sc))}
            flagged_new[0] += sum(1 for n in h_new if p.get(n, 0) >= 0.5)
            flagged_new[1] += sum(1 for n in h_new if n in p)
            flagged_on.append(label)
    if not rows:
        print("[whackamole] no bases with a loop pass-1 arm yet")
        return 0
    if a.compact:
        nums = draw_compact(rows, near, a.out, a.name, (5.95, a.height))
        nums["model_flagged_new"] = flagged_new
        print(json.dumps(nums, indent=1))
        return 0
    fig = plt.figure(figsize=(12.1, 5.3))
    ax = fig.add_axes([0.07, 0.24, 0.56, 0.55])
    x = np.arange(len(rows))
    w = 0.36
    base_n = np.array([max(1, r["baseline"]) for r in rows], dtype=float)
    ho = np.array([r["hind_old"] for r in rows]) / base_n * 100
    hn = np.array([r["hind_new"] for r in rows]) / base_n * 100
    ax.bar(x - w / 2, ho, w, color=F.GREY, zorder=2)
    ax.bar(x - w / 2, hn, w, bottom=ho, color=F.ROSE, zorder=2)
    tops = []
    for i, r in enumerate(rows):
        hcount = r["hind_old"] + r["hind_new"]
        ax.text(x[i] - w / 2, ho[i] + hn[i] + 0.25, str(hcount), ha="center", va="bottom", fontsize=F.FS, color=F.INK)
        tops.append(ho[i] + hn[i])
        if r["model_old"] is not None:
            mo, mn = r["model_old"] / base_n[i] * 100, r["model_new"] / base_n[i] * 100
            ax.bar(x[i] + w / 2, mo, w, color=F.GREY, zorder=2)
            ax.bar(x[i] + w / 2, mn, w, bottom=mo, color=F.GREEN, zorder=2)
            ax.text(x[i] + w / 2, mo + mn + 0.25, str(r["model_old"] + r["model_new"]), ha="center", va="bottom", fontsize=F.FS, color=F.INK)
            tops.append(mo + mn)
        else:
            ax.text(x[i] + w / 2, 0.3, "pending", ha="center", va="bottom", fontsize=F.FS - 2, color=F.MUTED, rotation=90)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{r['label']}\n({r['baseline']})" for r in rows], fontsize=F.FS - 1)
    ax.set_ylabel("left at signoff, % of baseline")
    ax.yaxis.grid(True)
    ax.set_axisbelow(True)
    ax.set_ylim(0, max(tops) * 1.22 + 0.5)
    ax.yaxis.set_major_locator(F.mticker.MaxNLocator(nbins=5, integer=True))
    ax.yaxis.set_major_formatter(F.mticker.FuncFormatter(lambda v, _: f"{v:.0f}%"))
    fig.text(0.07, 0.965, "Fixing exactly what failed creates new failures", fontsize=F.FS + 4, fontweight="semibold", color=F.INK, va="top")
    fig.text(0.07, 0.885, "left: repair the nets that failed the last signoff · right: repair the model's p ≥ 0.5 list",
             fontsize=F.FS - 1, color=F.INK2, va="top")
    fig.text(0.07, 0.005, "Both re-run detailed routing from the same post-GRT checkpoint (not an incremental ECO); the left list has no guard band.",
             fontsize=F.FS - 3, color=F.MUTED, va="bottom")
    F.key_row(fig, [("s", F.GREY, 10, "failed before too", None, True), ("s", F.ROSE, 10, "new (hindsight fix)", None, True),
                    ("s", F.GREEN, 10, "new (model's fix)", None, True)], 0.07, 0.075)
    # right panel: where the new violators sat before the ECO
    ax2 = fig.add_axes([0.72, 0.24, 0.26, 0.38])
    if near:
        ax2.hist(np.clip(near, 0.85, 1.0), bins=np.linspace(0.85, 1.0, 16), color=F.ROSE, zorder=2)
        ax2.axvline(1.0, color=F.INK2, lw=1.0)
        ax2.set_xlim(0.85, 1.005)
        ax2.set_xticks([0.85, 0.9, 0.95, 1.0])
        ax2.set_xticklabels(["0.85×", "0.90×", "0.95×", "1×"])
        ax2.set_xlabel("their signoff slew/cap ÷ limit\nbefore the fix")
        ax2.yaxis.grid(True)
        ax2.set_axisbelow(True)
    msg = f"{len(near)} new violators,\nmedian {np.median(near):.2f}× the limit before" if near else ""
    if flagged_new[1]:
        msg += f"\nthe model had flagged {flagged_new[0]} of {flagged_new[1]}\n({100 * flagged_new[0] / flagged_new[1]:.0f}%) before routing"
    fig.text(0.72, 0.80, msg, fontsize=F.FS - 1, color=F.INK2, va="top", linespacing=1.2)
    nums = dict(rows=rows, near_median=float(np.median(near)) if near else None, n_new=len(near), model_flagged_new=flagged_new)
    F.save(fig, a.out, a.name, nums)
    print(json.dumps(nums, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
