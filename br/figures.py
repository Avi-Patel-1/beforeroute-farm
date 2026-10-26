#!/usr/bin/env python3
"""Figures for BeforeRoute.

Usage: figures.py recall --model-dir results/model [--design picorv32] [--out fig.png]
       figures.py arms --arms results/arms_summary.json [--out fig.png]
"""
from __future__ import annotations

import argparse
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

LABELS = {
    "model": "BeforeRoute model",
    "est_load_slew_ratio": "Timer's own estimate (load slew / limit)",
    "est_driver_slew_ratio": "Timer's own estimate (driver slew / limit)",
    "est_cap_ratio": "Timer's own estimate (cap / limit)",
    "fanout": "Fanout",
    "hpwl": "HPWL",
    "guide_len": "Global-route length",
}


def recall_fig(model_dir, design, out):
    curves = json.load(open(os.path.join(model_dir, "curves.json")))
    report = json.load(open(os.path.join(model_dir, "report.json")))
    designs = [design] if design else list(curves.keys())
    fig, axes = plt.subplots(1, len(designs), figsize=(5.2 * len(designs), 4.2), squeeze=False)
    for ax, d in zip(axes[0], designs):
        c = curves[d]
        for key in ("model", "est_load_slew_ratio", "est_cap_ratio", "fanout", "hpwl"):
            if key not in c:
                continue
            xs = [p[0] * 100 for p in c[key]]
            ys = [p[1] * 100 for p in c[key]]
            ax.plot(xs, ys, label=LABELS[key], lw=2.4 if key == "model" else 1.4, alpha=1.0 if key == "model" else 0.8)
        ax.set_xscale("log")
        ax.set_xlim(0.1, 100)
        ax.set_ylim(0, 101)
        ax.set_xlabel("Nets flagged for extra repair (% of nets, log scale)")
        ax.set_ylabel("Signoff-violating nets caught (%)")
        r = report["lodo"].get(d, {}).get("model", {})
        ax.set_title(f"Held-out design: {d}  (n={r.get('n', '?')} nets, {r.get('positives', '?')} violating)")
        ax.axvline(5, color="gray", ls=":", lw=1)
        ax.grid(True, which="both", alpha=0.25)
        ax.legend(fontsize=8, loc="lower right")
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    print(f"wrote {out}")


def arms_fig(arms_path, out):
    arms = json.load(open(arms_path))
    names = [a["label"] for a in arms]
    viol = [a["signoff_violating_nets"] for a in arms]
    area = [a["stdcell_area"] for a in arms]
    base_area = area[0]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10, 4))
    a1.bar(names, viol, color=["#888", "#c66", "#e9a", "#59c"][: len(names)])
    a1.set_ylabel("Nets violating at nine-corner signoff")
    a1.set_title("Signoff violations")
    for i, v in enumerate(viol):
        a1.text(i, v, str(v), ha="center", va="bottom")
    delta = [(x - base_area) / base_area * 100 for x in area]
    a2.bar(names, delta, color=["#888", "#c66", "#e9a", "#59c"][: len(names)])
    a2.set_ylabel("Standard-cell area vs baseline (%)")
    a2.set_title("Area cost")
    for i, v in enumerate(delta):
        a2.text(i, v, f"{v:+.2f}%", ha="center", va="bottom" if v >= 0 else "top")
    for ax in (a1, a2):
        ax.tick_params(axis="x", labelrotation=15)
        ax.grid(True, axis="y", alpha=0.25)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    print(f"wrote {out}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("recall")
    r.add_argument("--model-dir", required=True)
    r.add_argument("--design", default=None)
    r.add_argument("--out", default="recall.png")
    m = sub.add_parser("arms")
    m.add_argument("--arms", required=True)
    m.add_argument("--out", default="arms.png")
    a = ap.parse_args()
    if a.cmd == "recall":
        recall_fig(a.model_dir, a.design, a.out)
    else:
        arms_fig(a.arms, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
