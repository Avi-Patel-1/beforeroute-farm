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


def _arm_kind(tag, base):
    a = tag[len(base) + 1:] if tag.startswith(base + "-") else "base"
    if a in ("", "base"):
        return "base", a
    if a.startswith("rerun"):
        return "rerun", a
    if a.startswith("uni"):
        return "uniform", a
    if a.startswith("tgt") or a.startswith("thr") or a.startswith("exp"):
        return "targeted", a
    if a.startswith("det") or a.startswith("est"):
        return "rule", a
    if a.startswith("lst-"):
        return "list", a
    if a.startswith("tier") or a.startswith("lt"):
        return "tiered", a
    return "other", a


def _cost(r):
    """Cells changed by the repair step: resizes + inserted buffers (from the log);
    falls back to the standard-cell instance delta when the log is missing."""
    if r.get("resized") is not None or r.get("buffers") is not None:
        return (r.get("resized") or 0) + (r.get("buffers") or 0), "cells changed by repair (resized + buffered)"
    return None, None


def _arm_label(a):
    if a.startswith("tgt"):
        k, h = a[3:].split("-")
        return f"k={int(k)/10:g}% H={h}"
    if a.startswith("thr"):
        k, h = a[3:].split("-")
        return f"p≥{int(k)/1000:g} H={h}"
    if a.startswith("det"):
        k, h = a[3:].split("-")
        return f"rule R8 top {int(k)/10:g}% H={h}"
    if a.startswith("lt"):
        return "learned margins " + a[2:]
    if a.startswith("tier"):
        parts = a[4:].split("_")
        return "tiers " + " / ".join(f"{int(x.split('-')[0])/10:g}%@{x.split('-')[1]}" for x in parts)
    if a.startswith("uni"):
        return f"H={a[3:]}"
    return a


def pareto_fig(summary_paths, out, title=None):
    """One panel per base: signal-net signoff violations vs repair cost, uniform family as a
    curve, targeted/tiered arms as markers; lower panel = hold worst slack per arm."""
    bases = [json.load(open(p)) for p in summary_paths]
    n = len(bases)
    fig, axes = plt.subplots(2, n, figsize=(4.8 * n, 7.4), squeeze=False, gridspec_kw={"height_ratios": [3, 1.6]})
    for col, hs in enumerate(bases):
        base = hs["base"]
        rows = {r["tag"]: r for r in hs["arms"] if r.get("status") == "completed"}
        b = rows.get(base)
        ax, ax2 = axes[0][col], axes[1][col]
        if b is None:
            ax.set_title(f"{base}: no baseline"); continue
        yb = b.get("signoff_violating_data_nets")
        hold_b = b.get("hold_ws")
        arms = []
        for tag, r in rows.items():
            kind, a = _arm_kind(tag, base)
            if kind in ("uniform", "targeted", "tiered", "rule") and r.get("signoff_violating_data_nets") is not None:
                arms.append((kind, a, r))
        have_logs = all(r.get("resized") is not None or r.get("buffers") is not None for _, _, r in arms)
        if have_logs:
            cost = lambda r: (r.get("resized") or 0) + (r.get("buffers") or 0)
            xlabel = "cells changed by the repair step (resized + inserted buffers)"
        else:
            cost = lambda r: (r.get("instances_stdcell") or 0) - (b.get("instances_stdcell") or 0)
            xlabel = "net change in standard-cell instances after repair"
        pts = {"uniform": [], "targeted": [], "tiered": [], "rule": []}
        for kind, a, r in arms:
            pts[kind].append((cost(r), r["signoff_violating_data_nets"], r.get("hold_ws"), a, r))
        uni = sorted(pts["uniform"], key=lambda t: int(t[3][3:]))
        ax.axhline(yb, color="#888", lw=1, ls=":", label=f"baseline: {yb} violating signal nets")
        if uni:
            ax.plot([t[0] for t in uni], [t[1] for t in uni], "-o", color="#b04a3a", lw=1.5, ms=6, label="uniform margin H on every net")
            for x, y, h, a, _ in uni:
                ax.annotate(f"{a[3:]}%", (x, y), textcoords="offset points", xytext=(5, 5), fontsize=8, color="#b04a3a")
        for kind, marker, color, lab in (("targeted", "*", "#2a6f97", "targeted: top-k% nets by model, margin H"), ("tiered", "D", "#5c8f3a", "tiered margins"), ("rule", "s", "#8a6d3b", "same k, deterministic rule instead of the model")):
            p_ = sorted(pts[kind], key=lambda t: t[0])
            if p_:
                ax.scatter([t[0] for t in p_], [t[1] for t in p_], marker=marker, s=170 if marker == "*" else 60, color=color, zorder=5, label=lab)
                for i, (x, y, h, a, _) in enumerate(p_):
                    ax.annotate(_arm_label(a), (x, y), textcoords="offset points", xytext=(8, 10 + 11 * i), fontsize=7.5, color=color,
                                arrowprops=dict(arrowstyle="-", color=color, lw=0.5, alpha=0.6))
        ax.set_xlabel(xlabel, fontsize=9)
        ax.set_ylabel("signal nets violating at nine-corner signoff")
        ax.set_title(base, fontsize=10)
        ax.grid(True, alpha=0.25)
        ax.set_ylim(bottom=-max(1, yb * 0.03), top=yb * 1.12)
        if col == 0:
            ax.legend(fontsize=7.5, loc="center right")
        labels, vals, cols = ["base"], [hold_b], ["#888"]
        for kind, color in (("uniform", "#b04a3a"), ("targeted", "#2a6f97"), ("tiered", "#5c8f3a"), ("rule", "#8a6d3b")):
            for x, y, h, a, _ in sorted(pts[kind], key=lambda t: t[3]):
                labels.append(a); vals.append(h); cols.append(color)
        ax2.bar(range(len(vals)), [v if v is not None else 0 for v in vals], color=cols)
        ax2.set_xticks(range(len(vals))); ax2.set_xticklabels(labels, rotation=35, ha="right", fontsize=7.5)
        ax2.set_ylabel("hold worst slack (ns)")
        ax2.grid(True, axis="y", alpha=0.25)
        ax2.set_title("collateral: hold margin left after repair", fontsize=9)
    fig.suptitle(title or "Targeted vs uniform post-GRT repair", fontsize=11)
    fig.tight_layout()
    fig.savefig(out, dpi=160)
    print(f"wrote {out}")


def gap_fig(csv_path, out, design="PicoRV32"):
    import pandas as pd

    d = pd.read_csv(csv_path)
    d = d[d["sig"] == "SIGNAL"]
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    clk = d["cls"].str.startswith("clkdlybuf")
    ax.scatter(d[~clk]["est"], d[~clk]["act"], s=6, alpha=0.35, color="#4a7fb5", label="data nets")
    ax.scatter(d[clk]["est"], d[clk]["act"], s=8, alpha=0.6, color="#d9603b", label="nets driven by hold-fix delay cells (clkdlybuf4s25)")
    lim = max(1.6, float(d["act"].quantile(0.999)))
    ax.plot([0, lim], [0, lim], color="gray", lw=1, ls="--", label="estimate = signoff")
    ax.axhline(1.0, color="k", lw=1); ax.axvline(1.0, color="k", lw=1)
    ax.fill_between([0, 1.0], 1.0, lim, color="#d9603b", alpha=0.08)
    n_v = int((d["act"] > 1).sum()); n_e = int((d["est"] > 1).sum()); n_blind = int(((d["act"] > 1) & (d["est"] <= 1)).sum())
    ax.text(0.03, lim * 0.93, f"blind spot: {n_blind} of {n_v} signoff violators\nlooked clean to the pre-route estimate", fontsize=9, color="#a0391c", va="top")
    ax.set_xlim(0, lim); ax.set_ylim(0, lim)
    ax.set_xlabel("Worst load slew / limit, pre-route estimate (post-GRT, nine corners)")
    ax.set_ylabel("Worst load slew / limit, signoff (extracted RCX, nine corners)")
    ax.set_title(f"{design}: the flow's own estimate vs signoff, per net (n={len(d)})", fontsize=11)
    ax.legend(fontsize=8, loc="lower right")
    ax.grid(True, alpha=0.25)
    fig.tight_layout()
    fig.savefig(out, dpi=170)
    print(f"wrote {out}  violators={n_v} est_flagged={n_e} blind={n_blind}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gap")
    g.add_argument("--csv", required=True)
    g.add_argument("--design", default="PicoRV32")
    g.add_argument("--out", default="gap.png")
    r = sub.add_parser("recall")
    r.add_argument("--model-dir", required=True)
    r.add_argument("--design", default=None)
    r.add_argument("--out", default="recall.png")
    m = sub.add_parser("arms")
    m.add_argument("--arms", required=True)
    m.add_argument("--out", default="arms.png")
    pq = sub.add_parser("pareto")
    pq.add_argument("--summary", action="append", required=True, help="results/<base>/hero_summary.json (repeatable)")
    pq.add_argument("--out", default="pareto.png")
    pq.add_argument("--title", default=None)
    a = ap.parse_args()
    if a.cmd == "recall":
        recall_fig(a.model_dir, a.design, a.out)
    elif a.cmd == "gap":
        gap_fig(a.csv, a.out, a.design)
    elif a.cmd == "pareto":
        pareto_fig(a.summary, a.out, a.title)
    else:
        arms_fig(a.arms, a.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
