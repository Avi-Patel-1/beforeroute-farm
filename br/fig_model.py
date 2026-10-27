#!/usr/bin/env python3
"""The ML component on one figure: what the model reads, what it is, what it outputs, and what it learned.

Left: schematic (feature families -> 400 boosted trees -> per-net probability -> threshold -> repair list).
Top right: share of the model's split gain by feature family (model_all_v5).
Bottom right: what the trees learned, out of fold: for nets of 8 Round-3/4 designs, each scored by the model
that never saw its design, the signoff violation rate and the mean predicted probability against the timer's own
estimated worst-load slew ratio, split by wire length (HPWL tertiles). The estimate's own threshold is 1.0.
Usage: fig_model.py [--out figures/v2] [--name model_card]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import figs_v2 as F  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

FAMILIES = {
    "Timer's own estimate": ["worst_load_slew_ratio", "cap_ratio", "driver_slew_ratio", "fanout_ratio", "driver_slack_ns",
                             "driver_slew_ns", "worst_load_slew_ns", "net_cap_pf_max", "net_cap_pf_tt"],
    "Wire geometry and route guides": ["hpwl_um", "bbox_w_um", "bbox_h_um", "guide_len_um", "guide_frac_li1", "guide_frac_met1",
                                       "guide_frac_met2", "guide_frac_met3up", "density_mean", "density_max"],
    "Connectivity and drive": ["fanout", "n_load_ports", "drive_index", "driver_class", "pin_cap_pf_max", "is_clock",
                               "driver_slew_limit_lib_ns", "driver_cap_limit_lib_pf"],
    "Design knobs": ["d_utilization", "d_clock_period_ns", "d_fp_core_util", "d_pl_density_pct", "d_max_tran_ns"],
}
HOLDOUT = {"BM64": "bm64", "des": "des", "md5": "md5", "ocs_blitter": "ocs_blitter", "salsa20": "salsa20",
           "y_huff": "y_huff", "ldpcenc": "ldpcenc", "sha512": "sha512"}


def gain_by_family(model_path):
    import lightgbm as lgb
    m = lgb.Booster(model_file=model_path)
    g = dict(zip(m.feature_name(), m.feature_importance("gain")))
    tot = sum(g.values())
    out = {fam: 100.0 * sum(g.get(f, 0.0) for f in fs) / tot for fam, fs in FAMILIES.items()}
    covered = {f for fs in FAMILIES.values() for f in fs}
    missing = [f for f in g if f not in covered]
    if missing:
        raise SystemExit(f"features not in a family: {missing}")
    return out, m.num_trees(), len(g)


def oof_curve():
    import lightgbm as lgb
    from train import FEATURES
    cols = list(dict.fromkeys(FEATURES + ["design", "y", "sigtype", "join_how", "driver_kind"]))
    df = pd.read_parquet(F.DATASET, columns=cols)
    df = df[(df.join_how != "none") & (df.driver_kind != "none") & (df.sigtype == "SIGNAL") & df.design.isin(HOLDOUT)].copy()
    df["p"] = np.nan
    for d, tag in HOLDOUT.items():
        m = lgb.Booster(model_file=os.path.join(F.MODELS, f"model_holdout_{tag}_v4.txt"))
        idx = df.design == d
        X = df.loc[idx, FEATURES].copy()
        X["driver_class"] = X["driver_class"].astype("category")
        df.loc[idx, "p"] = m.predict(X)
    return df


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--name", default="model_card")
    ap.add_argument("--model", default=os.path.join(F.MODELS, "model_all_v5.txt"))
    a = ap.parse_args()
    F.setup_style()
    fam, ntrees, nfeat = gain_by_family(a.model)
    df = oof_curve()

    fig = plt.figure(figsize=(16, 7.6))
    # ---------------- left: schematic ----------------
    ax = fig.add_axes([0.0, 0.0, 0.5, 1.0])
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 10)
    ax.axis("off")

    def box(x, y, w, h, title, lines, edge, title_col=F.INK, fs=F.FS - 1):
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02,rounding_size=0.15", fc="#0f0f0f", ec=edge, lw=1.4))
        ax.text(x + 0.18, y + h - 0.22, title, color=title_col, fontsize=fs, fontweight="bold", va="top", ha="left")
        for i, ln in enumerate(lines):
            ax.text(x + 0.18, y + h - 0.72 - i * 0.43, ln, color=F.INK2, fontsize=fs - 2, va="top", ha="left")

    def arrow(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0), arrowprops=dict(arrowstyle="-|>", color=F.INK2, lw=1.4, mutation_scale=16))

    ax.text(0.15, 9.75, "One signal net at the post-global-route checkpoint", color=F.INK, fontsize=F.FS, va="top")
    order = list(FAMILIES)
    y = 8.95
    heights = [1.2, 1.2, 1.2, 1.2]
    examples = ["est. slew ÷ limit, est. cap ÷ limit",
                "HPWL, guide length, layer shares",
                "fanout, driver class, pin cap",
                "utilisation, clock period"]
    centers = []
    for fname, h, ex in zip(order, heights, examples):
        y -= h
        n = len(FAMILIES[fname])
        box(0.15, y, 4.3, h - 0.12, f"{fname}  ({n})", [ex], F.AXIS, fs=F.FS - 1)
        centers.append(y + (h - 0.12) / 2)
        y -= 0.08
    ax.text(0.15, y - 0.1, f"{nfeat} numbers per net from the timer and router;\nno signoff data at inference",
            color=F.MUTED, fontsize=F.FS - 3, va="top")
    # trees
    tx, ty, tw, th = 5.0, 3.75, 2.3, 4.6
    ax.add_patch(FancyBboxPatch((tx, ty), tw, th, boxstyle="round,pad=0.02,rounding_size=0.15", fc="#0f0f0f", ec=F.GREEN, lw=1.8))
    ax.text(tx + tw / 2, ty + th - 0.2, "Gradient-boosted\ntrees (LightGBM)", color=F.INK, fontsize=F.FS - 1, fontweight="bold", ha="center", va="top")
    rng = np.random.default_rng(3)
    for k, (cx, cy) in enumerate([(tx + 0.55, ty + 2.35), (tx + 1.6, ty + 2.35), (tx + 0.55, ty + 0.95), (tx + 1.6, ty + 0.95)]):
        pts = [(cx, cy + 0.55), (cx - 0.3, cy + 0.05), (cx + 0.3, cy + 0.05), (cx - 0.45, cy - 0.45), (cx - 0.15, cy - 0.45), (cx + 0.15, cy - 0.45), (cx + 0.45, cy - 0.45)]
        for (i, j) in [(0, 1), (0, 2), (1, 3), (1, 4), (2, 5), (2, 6)]:
            ax.plot([pts[i][0], pts[j][0]], [pts[i][1], pts[j][1]], color=F.AXIS, lw=1.0, zorder=2)
        for i, (px, py) in enumerate(pts):
            ax.scatter([px], [py], s=26 if i < 3 else 18, c=F.GREEN if i >= 3 and rng.random() > 0.5 else F.INK2, zorder=3, lw=0)
    ax.text(tx + tw / 2, ty + 1.72, "+", color=F.INK, fontsize=F.FS + 2, ha="center", va="center")
    ax.text(tx + tw / 2, ty + 0.25, f"{ntrees} trees, ≤31 leaves", color=F.INK2, fontsize=F.FS - 3, ha="center", va="center")
    for c in centers:
        arrow(4.5, c, tx - 0.05, min(max(c, ty + 0.4), ty + th - 0.4))
    # output
    ox = 7.75
    box(ox, 5.55, 2.15, 2.75, "Output", ["P(violates at", "9-corner signoff)", "≥ 0.5 → on the", "repair list"], F.GREEN, fs=F.FS - 1)
    arrow(tx + tw + 0.02, 6.9, ox - 0.05, 6.9)
    box(ox, 2.25, 2.15, 2.85, "Actuator", ["stock repair_design", "on listed nets only,", "wire cap ×2.13,", "30% margin"], F.AXIS, fs=F.FS - 1)
    arrow(ox + 1.05, 5.5, ox + 1.05, 5.15)
    ax.text(5.0, 3.35, "Trained on 999,919 nets\nfrom 128 runs of 12\nopen designs (4.3%\nviolate at signoff)\n\nRetrains on all 1.6M\nnets in 5.5 min on 2\nCPU cores; scores\n100k nets in 1.3 s",
            color=F.INK2, fontsize=F.FS - 3, va="top", ha="left")

    # ---------------- top right: gain by family ----------------
    ax2 = fig.add_axes([0.56, 0.6, 0.42, 0.31])
    names = order[::-1]
    vals = [fam[n] for n in names]
    ax2.barh([i * 1.6 for i in range(len(names))], vals, color=[F.GREEN if v == max(vals) else F.GREY for v in vals], height=0.55)
    ax2.set_yticks([])
    for i, (n, v) in enumerate(zip(names, vals)):
        ax2.text(0, i * 1.6 + 0.42, n, va="bottom", ha="left", color=F.INK2, fontsize=F.FS - 2)
        ax2.text(max(v, 0) + 1.0, i * 1.6, f"{v:.0f}%" if v >= 1 else "<1%", va="center", color=F.INK, fontsize=F.FS - 2)
    ax2.set_xlim(0, 100)
    ax2.set_ylim(-0.5, (len(names) - 1) * 1.6 + 1.2)
    ax2.set_xticks([])
    for sp in ("top", "right", "bottom", "left"):
        ax2.spines[sp].set_visible(False)
    ax2.set_title("Where the trees split (share of split gain)", loc="left", color=F.INK, fontsize=F.FS - 1, pad=8)

    # ---------------- bottom right: learned response ----------------
    ax3 = fig.add_axes([0.6, 0.1, 0.38, 0.37])
    r = df["worst_load_slew_ratio"].clip(0, 2.0)
    bins = np.linspace(0, 1.6, 17)
    cls = df["driver_class"].astype(str)
    dly = cls == "clkdlybuf"
    groups = [("hold-fix delay buffers", dly, F.GREEN), ("all other drivers", ~dly, F.INK2)]
    nums = {"gain_by_family_pct": {k: round(v, 1) for k, v in fam.items()}, "n_nets": int(len(df)), "n_pos": int(df.y.sum()),
            "delay_buffer_nets": int(dly.sum()), "delay_buffer_violators": int(df[dly].y.sum()),
            "violators_below_limit_frac": round(float((df[df.y == 1].worst_load_slew_ratio < 1).mean()), 3), "curves": {}}
    for lab, msk, col in groups:
        sub = df[msk]
        b = np.digitize(r[msk], bins) - 1
        xs, obs, pred, ns = [], [], [], []
        for k in range(len(bins) - 1):
            s = sub[b == k]
            if len(s) < 60:
                continue
            xs.append((bins[k] + bins[k + 1]) / 2)
            obs.append(100 * s.y.mean())
            pred.append(100 * s.p.mean())
            ns.append(len(s))
        ax3.plot(xs, pred, color=col, lw=2.2, label=lab, zorder=3)
        ax3.scatter(xs, obs, color=col, s=22, zorder=4, lw=0)
        nums["curves"][lab] = {"x": [round(v, 2) for v in xs], "observed_pct": [round(v, 1) for v in obs],
                               "predicted_pct": [round(v, 1) for v in pred], "n": ns}
    ax3.axvline(1.0, color=F.INK2, lw=1, ls=(0, (3, 3)))
    ax3.text(1.02, 96, "timer's own limit", color=F.INK2, fontsize=F.FS - 3, va="top")
    ax3.axvspan(0, 1.0, color=F.CRIT, alpha=0.07, lw=0)
    ax3.text(0.03, 96, f"estimate says safe: {100 * nums['violators_below_limit_frac']:.0f}% of violators", color=F.CRIT, fontsize=F.FS - 3, va="top")
    ax3.set_xlim(0, 1.6)
    ax3.set_ylim(0, 100)
    ax3.set_xlabel("Timer's estimated worst load slew ÷ limit (pre-route)", fontsize=F.FS - 2, color=F.INK2)
    ax3.set_ylabel("Nets violating at signoff (%)", fontsize=F.FS - 2, color=F.INK2)
    ax3.grid(color=F.GRID, lw=0.8)
    for s in ("top", "right"):
        ax3.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax3.spines[s].set_color(F.AXIS)
    ax3.tick_params(colors=F.INK2, labelsize=F.FS - 3)
    leg = ax3.legend(loc="center right", frameon=False, fontsize=F.FS - 3, labelcolor=F.INK2, title="line = model, dots = actual", title_fontsize=F.FS - 4)
    leg.get_title().set_color(F.MUTED)
    ax3.set_title("What it learned: nets start failing at ~0.5 of the timer's limit\n(8 designs, each scored by the model that never saw it)", loc="left", color=F.INK, fontsize=F.FS - 1, pad=8)
    F.save(fig, a.out, a.name, nums)
    print(json.dumps(nums, indent=1)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
