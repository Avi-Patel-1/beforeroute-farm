#!/usr/bin/env python3
"""Die plot for one hero base: where signoff fails, what BeforeRoute flagged before routing, and what is
left after its targeted repair. Same dark slide style and palette as br/figs_v2.py.

Usage: python3 br/fig_dieplot.py --base d1-picorv32-006 --arm tgt050-70 --label PicoRV32 --out figures/v2/
Every net is placed at its driver pin's post-GRT location. Signoff violators that only exist after
repair (new buffers) are placed at a load instance that existed at post-GRT; the rest are counted.
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
from matplotlib.lines import Line2D  # noqa: E402


def load_base(results, base):
    nets, by_inst = {}, {}
    for line in open(os.path.join(results, base, "nets.jsonl")):
        n = json.loads(line)
        if n.get("sigtype") != "SIGNAL" or n.get("driver_kind") == "none":
            continue
        if n.get("driver_x_um") is None:
            continue
        nets[n["net"]] = n
        if n.get("driver_inst"):
            by_inst[n["driver_inst"]] = (n["driver_x_um"], n["driver_y_um"])
    return nets, by_inst


def violators_xy(results, tag, nets, by_inst):
    lab = json.load(open(os.path.join(results, tag, "labels.json")))
    fin = json.load(open(os.path.join(results, tag, "final_nets.json")))["nets"]
    pts, names, unplaced = [], [], 0
    for r in lab["nets"]:
        if not r.get("violated") or r.get("sigtype_s") != "SIGNAL":
            continue
        nm = r["net"]
        if nm in nets:
            pts.append((nets[nm]["driver_x_um"], nets[nm]["driver_y_um"]))
            names.append(nm)
            continue
        inst = (r.get("driver_s") or "").split("/")[0]
        xy = by_inst.get(inst)
        if xy is None:
            for p in (fin.get(nm) or {}).get("pins", []):
                xy = by_inst.get(p.split("/")[0])
                if xy:
                    break
        if xy is None:
            unplaced += 1
            continue
        pts.append(xy)
        names.append(nm)
    return np.array(pts).reshape(-1, 2), names, unplaced


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="d1-picorv32-006")
    ap.add_argument("--arm", default="tgt050-70")
    ap.add_argument("--uniform", default="uni70")
    ap.add_argument("--label", default="PicoRV32")
    ap.add_argument("--results", default=F.RESULTS)
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--name", default="dieplot_hero")
    a = ap.parse_args()
    F.setup_style()
    nets, by_inst = load_base(a.results, a.base)
    flagged = set(json.load(open(os.path.join(a.results, a.base, f"flagged_{a.arm}.json"))))
    vxy, vnames, v_unpl = violators_xy(a.results, a.base, nets, by_inst)
    rxy, rnames, r_unpl = violators_xy(a.results, f"{a.base}-{a.arm}", nets, by_inst)
    allxy = np.array([(n["driver_x_um"], n["driver_y_um"]) for n in nets.values()])
    fxy = np.array([(nets[n]["driver_x_um"], nets[n]["driver_y_um"]) for n in flagged if n in nets]).reshape(-1, 2)
    caught = np.array([nm in flagged for nm in vnames])
    timer = np.array([max(nets[nm].get("worst_load_slew_ratio") or 0, nets[nm].get("cap_ratio") or 0) > 1.0 if nm in nets else False for nm in vnames])
    # like-for-like: the timer's own ranking (estimated worst-load slew ratio) at the same budget
    est_rank = sorted(nets, key=lambda k: -(nets[k].get("worst_load_slew_ratio") or 0))[:len(flagged)]
    est_caught = len(set(est_rank) & set(vnames))
    hs = json.load(open(os.path.join(a.results, a.base, "hero_summary.json")))
    rows = {r["tag"]: r for r in hs["arms"]}
    ref = rows.get(f"{a.base}-rerun") or rows.get(a.base)
    arm = rows.get(f"{a.base}-{a.arm}", {})
    uni = rows.get(f"{a.base}-{a.uniform}", {})

    def cells(r):
        return (r.get("resized") or 0) + (r.get("buffers") or 0)

    def hold_kept(r):
        try:
            return r["hold_ws"] / ref["hold_ws"]
        except Exception:
            return float("nan")

    n_v = len(vnames) + v_unpl
    fig = plt.figure(figsize=(12.1, 6.0))
    x0, x1 = allxy[:, 0].min(), allxy[:, 0].max()
    y0, y1 = allxy[:, 1].min(), allxy[:, 1].max()
    pad = 0.02 * max(x1 - x0, y1 - y0)
    axes = [fig.add_axes([0.012, 0.085, 0.47, 0.70]), fig.add_axes([0.512, 0.085, 0.47, 0.70])]
    for ax in axes:
        ax.set_xlim(x0 - pad, x1 + pad)
        ax.set_ylim(y0 - pad, y1 + pad)
        ax.set_aspect("equal")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(True)
            s.set_color(F.AXIS)
        ax.scatter(allxy[:, 0], allxy[:, 1], s=1.2, c="#3a3a3a", lw=0, zorder=1, rasterized=True)
    # panel A: before routing
    ax = axes[0]
    ax.scatter(fxy[:, 0], fxy[:, 1], s=26, facecolors="none", edgecolors=F.GREEN, linewidths=1.2, zorder=3)
    if len(vxy):
        ax.scatter(vxy[caught, 0], vxy[caught, 1], s=9, c=F.CRIT, lw=0, zorder=4)
        ax.scatter(vxy[~caught, 0], vxy[~caught, 1], s=30, c=F.CRIT, marker="x", linewidths=1.6, zorder=5)
    fig.text(0.012, 0.975, f"Before routing: BeforeRoute flags {len(flagged):,} nets ({len(flagged) / len(nets):.0%})",
             fontsize=F.FS + 2, fontweight="semibold", color=F.INK, va="top")
    fig.text(0.012, 0.915, f"{int(caught.sum()):,} of {n_v:,} future signoff violators are inside the flags\n"
             f"(the timer's own top-{len(flagged)} ranking: {est_caught}; its over-limit flag: {int(timer.sum())})", fontsize=F.FS, color=F.INK2, va="top", linespacing=1.25)
    # panel B: after targeted repair
    ax = axes[1]
    if len(rxy):
        ax.scatter(rxy[:, 0], rxy[:, 1], s=30, c=F.CRIT, lw=0, zorder=4)
    n_r = len(rnames) + r_unpl
    fig.text(0.512, 0.975, f"After targeted repair: {n_v:,} → {n_r:,} violators", fontsize=F.FS + 2,
             fontweight="semibold", color=F.INK, va="top")
    fig.text(0.512, 0.915, f"{cells(arm):,} cells changed, {hold_kept(arm):.0%} of hold margin kept\n"
             f"uniform 70% margin: {uni.get('signoff_violating_data_nets', '?')} left, {cells(uni):,} cells, {hold_kept(uni):.0%} kept",
             fontsize=F.FS, color=F.INK2, va="top", linespacing=1.25)
    F.key_row(fig, [("o", F.GREEN, 8, "flagged by the model before routing", None, False),
                    ("o", F.CRIT, 6, "signoff violator", None, True),
                    ("x", F.CRIT, 8, "violator the model missed", None, False)], 0.014, 0.038)
    nums = dict(base=a.base, arm=a.arm, signal_nets=len(nets), flagged=len(flagged), violators=n_v,
                violators_unplaced=v_unpl, caught=int(caught.sum()), timer_flagged_violators=int(timer.sum()), timer_topk_caught=est_caught,
                residual=n_r, residual_unplaced=r_unpl, arm_cells=cells(arm), uni_cells=cells(uni),
                arm_hold_kept=hold_kept(arm), uni_hold_kept=hold_kept(uni),
                uni_residual=uni.get("signoff_violating_data_nets"))
    F.save(fig, a.out, a.name, nums)
    print(json.dumps(nums, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
