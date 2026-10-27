#!/usr/bin/env python3
"""BeforeRoute figure suite v2: figures for a dark slide template (black surface, brand green accent).

Usage:
  python3 br/figs_v2.py all --out figures/v2/
  python3 br/figs_v2.py NAME [NAME ...] --out figures/v2/
     NAME in: blindspot, blindspot-grid, anatomy, prediction, prediction-summary,
              pareto-hero, pareto, pipeline, iterations

Every number drawn is computed here from results/dataset.parquet, results/<base>/hero_summary.json
and the held-out models in models/. Missing inputs are skipped with a message (later rounds land
incrementally), so `all` is safe to rerun at any time. The numbers each figure printed are written
to <out>/figs_v2_numbers.json for cross-checking against slide text.

Figures are drawn at their final size on a 13.33 x 7.5 in slide, so a 14 pt label in the figure
is 14 pt on the slide (no text below 14 pt). PNG, 200 dpi, black background.

Palette (validated with a CVD/contrast palette validator: dark mode, surface #000000, all pairs:
lightness band, chroma floor, CVD (worst dE 11.8 deutan), normal-vision (26.5), contrast: PASS):
  BeforeRoute / model  #6aa800  (brand green #76B900, lightness stepped into the dark band)
  uniform margin       #d55181  (rose)
  rule R8              #3987e5  (blue)
  baseline / estimate  #8c8c8c  (neutral grey)
Marker shape repeats identity: star = model arm, square = rule, circle = uniform / estimate.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.patheffects as pe  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mticker  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")
MODELS = os.path.join(ROOT, "models")
DATASET = os.path.join(RESULTS, "dataset.parquet")

# ---------------------------------------------------------------- style tokens
SURFACE = "#000000"
INK = "#ffffff"          # primary text
INK2 = "#bdbdbd"         # secondary text, tick labels (11:1 on black)
MUTED = "#9a9a9a"        # notes (7.5:1)
GRID = "#262626"         # hairline grid
AXIS = "#4a4a4a"         # axis lines
GREEN = "#6aa800"        # BeforeRoute / model (data marks)
BRAND = "#76b900"        # brand green (diagram accents only, not data)
ROSE = "#d55181"         # uniform / blanket margin
BLUE = "#3987e5"         # deterministic rule R8
GREY = "#8c8c8c"         # baseline / raw estimate
CRIT = "#d03b3b"         # status: violation the estimate missed
LOOP = "#cfcfcf"         # signoff-guided loop (conventional practice, neutral)
OTHER = "#6a6a6a"        # other policies tried (context only)
GREY_RAMP = LinearSegmentedColormap.from_list("greys_dark", ["#2e2e2e", "#f2f2f2"])
CRIT_RAMP = LinearSegmentedColormap.from_list("crit_dark", ["#a92f2f", "#ff9a92"])
HALO = [pe.withStroke(linewidth=4, foreground=SURFACE)]
DPI = 200
FS = 14                  # minimum font size on the slide

NUMBERS: dict = {}       # what each figure printed, for cross-checking


def setup_style():
    names = {f.name for f in font_manager.fontManager.ttflist}
    fam = "Inter" if "Inter" in names else "DejaVu Sans"
    plt.rcParams.update({
        "font.family": fam, "font.size": FS,
        "axes.titlesize": FS, "axes.titleweight": "semibold", "axes.titlelocation": "left",
        "axes.titlecolor": INK, "axes.titlepad": 8,
        "axes.labelsize": FS, "axes.labelcolor": INK2, "axes.edgecolor": AXIS, "axes.linewidth": 1.0,
        "axes.facecolor": SURFACE, "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.labelsize": FS, "ytick.labelsize": FS, "xtick.color": AXIS, "ytick.color": AXIS,
        "xtick.labelcolor": INK2, "ytick.labelcolor": INK2, "xtick.major.size": 4, "ytick.major.size": 4,
        "grid.color": GRID, "grid.linewidth": 0.8, "grid.linestyle": "-",
        "text.color": INK, "legend.frameon": False, "legend.fontsize": FS,
        "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
    })


def save(fig, out_dir, name, numbers=None):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name + ".png")
    fig.savefig(path, dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    NUMBERS[name] = numbers or {}
    print(f"[figs_v2] wrote {os.path.relpath(path, ROOT)}")
    return path


def pct(v, nd=0):
    return f"{100 * v:.{nd}f}%"


def key_row(fig, items, x0, y, gap=0.022):
    """A legend drawn as one row in figure coordinates: glyph (+ optional line) then label.
    items: (marker, color, size, label, line_color, filled). Widths measured with the renderer."""
    r = fig.canvas.get_renderer()
    fw = fig.bbox.width
    x = x0
    for mk, col, ms, lab, line, filled in items:
        if line:
            fig.add_artist(Line2D([x, x + 0.026], [y, y], color=line, lw=2.2, transform=fig.transFigure))
        if mk:
            fig.add_artist(Line2D([x + 0.013], [y], marker=mk, ms=ms, lw=0, color=col, mfc=col if filled else SURFACE,
                                  mec=SURFACE if filled else col, mew=1.5 if filled else 1.8, transform=fig.transFigure))
        t = fig.text(x + 0.032, y, lab, fontsize=FS, color=INK2, va="center")
        x += 0.032 + t.get_window_extent(renderer=r).width / fw + gap
    return x


# ---------------------------------------------------------------- data access
_SIG_CACHE: dict = {}


def signal_nets(cols):
    """Signal nets with a joined driver (the filter used throughout the project)."""
    import pandas as pd

    need = sorted(set(cols) | {"run", "design", "join_how", "driver_kind", "sigtype", "y"})
    key = tuple(need)
    if key in _SIG_CACHE:
        return _SIG_CACHE[key]
    if not os.path.exists(DATASET):
        raise FileNotFoundError(DATASET)
    d = pd.read_parquet(DATASET, columns=need)
    d = d[(d["join_how"] != "none") & (d["driver_kind"] != "none") & (d["sigtype"] == "SIGNAL")]
    _SIG_CACHE.clear()
    _SIG_CACHE[key] = d
    return d


def load_hero(base):
    p = os.path.join(RESULTS, base, "hero_summary.json")
    if not os.path.exists(p):
        return None
    try:
        return json.load(open(p))
    except Exception as e:  # half-written file while a round lands
        print(f"[figs_v2] {base}: unreadable hero_summary.json ({e}); skipped")
        return None


def arm_of(tag, base):
    if tag == base:
        return "base"
    return tag[len(base) + 1:] if tag.startswith(base + "-") else tag


def cells_changed(r):
    if r.get("resized") is None and r.get("buffers") is None:
        return None
    return (r.get("resized") or 0) + (r.get("buffers") or 0)


def arms_table(hs):
    """{arm: row} for completed rows; the first row is the baseline itself."""
    base = hs["base"]
    out = {}
    for i, r in enumerate(hs.get("arms", [])):
        if r.get("status") != "completed" or r.get("signoff_violating_data_nets") is None:
            continue
        a = "base" if i == 0 and r.get("tag") == base else arm_of(r.get("tag", ""), base)
        out[a] = r
    return out


def classify(arm):
    if arm == "base":
        return "base"
    if arm.startswith("rerun"):
        return "rerun"
    if arm.startswith("uni"):
        return "uniform"
    if arm.endswith("hv3") or arm.endswith("hv4"):
        return "holdprot"          # hold-fix cells protected: repair disabled (negative result)
    if arm.startswith("lst-"):
        return "loop"
    if arm.startswith("tgt") or arm.startswith("thr"):
        return "model"
    if arm.startswith("det"):
        return "rule"
    if arm.startswith("tier") or arm.startswith("lt"):
        return "tiered"
    return "other"


ROLE_PREF = {
    "top5": ["tgt050-70", "tgt050-70v4", "tgt050-70v3"],
    "thr": ["thr500-70", "thr500-70v4", "thr500-70v3"],
    "rule": ["det050-70"],
}


def pick(arms, role):
    for a in ROLE_PREF[role]:
        if a in arms and cells_changed(arms[a]) is not None:
            return a
    return None


BASE_LABEL = {
    "d1-picorv32-006": "PicoRV32 #006", "d1-picorv32-016": "PicoRV32 #016",
    "d1-aes_cipher-000": "AES", "picorv32-base-v1": "PicoRV32 (exploratory)",
    "d3-salsa20-000": "salsa20", "d3-des-000": "DES", "d3-y_huff-000": "y_huff",
    "d3-ocs_blitter-000": "ocs_blitter", "d3-bm64-000": "BM64", "d3-md5-000": "MD5",
}
CONFIRMATORY = ["d1-picorv32-006", "d1-picorv32-016", "d1-aes_cipher-000"]
ROUND3 = ["d3-salsa20-000", "d3-des-000", "d3-y_huff-000", "d3-ocs_blitter-000", "d3-bm64-000", "d3-md5-000"]
EXPLORATORY = ["picorv32-base-v1"]


# ================================================================ (a) blind spot
XMAX, YMAX = 2.0, 3.6


def _blind_panel(ax, est, act, gx):
    est = np.clip(np.asarray(est, float), 0, XMAX - 1e-6)
    act = np.clip(np.asarray(act, float), 0, YMAX - 1e-6)
    ax.add_patch(Rectangle((0, 1), 1, YMAX - 1, facecolor=CRIT, alpha=0.10, lw=0, zorder=0))
    ext = (0, XMAX, 0, YMAX)
    ax.hexbin(est, act, gridsize=gx, extent=ext, bins="log", mincnt=1, cmap=GREY_RAMP,
              linewidths=0.2, edgecolors=SURFACE, zorder=1)
    blind = (act > 1) & (est <= 1)
    if blind.any():
        ax.hexbin(est[blind], act[blind], gridsize=gx, extent=ext, bins="log", mincnt=1, cmap=CRIT_RAMP,
                  linewidths=0.2, edgecolors=SURFACE, zorder=2)
    ax.plot([0, XMAX], [0, XMAX], color=GREY, lw=1.0, zorder=3)
    ax.axhline(1, color=INK2, lw=1.0, zorder=3)
    ax.axvline(1, color=INK2, lw=1.0, zorder=3)
    ax.set_xlim(0, XMAX)
    ax.set_ylim(0, YMAX)
    ax.set_xticks([0, 1, 2])
    ax.set_yticks([0, 1, 2, 3])
    ax.set_xticklabels(["0", "1×", "2×"])
    ax.set_yticklabels(["0", "1×", "2×", "3×"])
    n_v = int((act > 1).sum())
    n_b = int(blind.sum())
    return dict(nets=int(len(est)), signoff_slew_violators=n_v, blind=n_b,
                caught_by_estimate=int(((act > 1) & (est > 1)).sum()),
                false_alarms=int(((est > 1) & (act <= 1)).sum()),
                blind_frac=(n_b / n_v if n_v else float("nan")))


def fig_blindspot(out_dir, run="d1-picorv32-006", label="PicoRV32", size=(5.95, 3.55), name="blindspot_hero"):
    """Estimated vs signoff worst load-slew ratio per signal net, one run; red = signoff violators
    the estimate called clean."""
    d = signal_nets(["worst_load_slew_ratio", "act_load_slew_ratio"])
    x = d[(d["run"] == run) & d["act_load_slew_ratio"].notna() & d["worst_load_slew_ratio"].notna()]
    if not len(x):
        print(f"[figs_v2] blindspot: no rows for {run}; skipped")
        return None
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0.10, 0.165, 0.875, 0.73])
    nums = _blind_panel(ax, x["worst_load_slew_ratio"].values, x["act_load_slew_ratio"].values, gx=(46, 19))
    ax.set_xlabel("Estimated slew ÷ limit  (pre-route)", labelpad=3)
    ax.set_ylabel("Signoff slew ÷ limit", labelpad=4)
    ax.text(0.04, YMAX - 0.14, f"{nums['blind']:,} of {nums['signoff_slew_violators']:,}", fontsize=FS + 8,
            fontweight="semibold", color=INK, va="top", ha="left", zorder=6, path_effects=HALO)
    ax.text(0.04, YMAX - 0.86, f"signoff slew violators ({pct(nums['blind_frac'])})\nlooked clean to the estimate",
            fontsize=FS, color=INK, va="top", ha="left", linespacing=1.15, zorder=6, path_effects=HALO)
    ax.text(XMAX - 0.03, 1.06, f"caught: {nums['caught_by_estimate']:,}", fontsize=FS, color=INK2, va="bottom", ha="right",
            zorder=6, path_effects=HALO)
    ax.text(XMAX - 0.03, 0.62, f"false alarms: {nums['false_alarms']:,}", fontsize=FS, color=INK2, va="center", ha="right", zorder=6)
    ax.text(XMAX - 0.03, 0.22, "diagonal: estimate = signoff", fontsize=FS, color=GREY, va="center", ha="right", zorder=6)
    fig.text(0.012, 0.975, f"{label}: {nums['nets']:,} signal nets, worst of 9 corners",
             fontsize=FS, color=INK2, va="top", ha="left")
    nums.update(run=run)
    return save(fig, out_dir, name, nums)


BLIND_GRID_RUNS = [
    ("d1-picorv32-006", "PicoRV32"), ("d1-aes_cipher-000", "AES"), ("d3-salsa20-000", "salsa20"),
    ("d3-des-000", "DES"), ("d3-y_huff-000", "y_huff"), ("d3-ocs_blitter-000", "ocs_blitter"),
    ("d3-bm64-000", "BM64"), ("d3-md5-000", "MD5"),
]


def fig_blindspot_grid(out_dir, size=(12.1, 5.6), name="blindspot_grid"):
    d = signal_nets(["worst_load_slew_ratio", "act_load_slew_ratio"])
    have = [(r, lab) for r, lab in BLIND_GRID_RUNS if (d["run"] == r).any()]
    if not have:
        print("[figs_v2] blindspot-grid: no runs; skipped")
        return None
    ncol = 4 if len(have) > 6 else 3
    nrow = int(math.ceil(len(have) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=size, squeeze=False, sharex=True, sharey=True)
    fig.subplots_adjust(left=0.065, right=0.985, top=0.83, bottom=0.16, wspace=0.09, hspace=0.42)
    nums = {}
    for ax, (run, lab) in zip(axes.flat, have):
        x = d[(d["run"] == run) & d["act_load_slew_ratio"].notna() & d["worst_load_slew_ratio"].notna()]
        n = _blind_panel(ax, x["worst_load_slew_ratio"].values, x["act_load_slew_ratio"].values, gx=(22, 11))
        ax.set_title(f"{lab}: {n['blind']:,} of {n['signoff_slew_violators']:,} ({pct(n['blind_frac'])})", fontsize=FS)
        nums[run] = n
    for ax in list(axes.flat)[len(have):]:
        ax.set_visible(False)
    fig.text(0.012, 0.975, "Signoff slew violators the estimate called clean (red), one run per design",
             fontsize=FS + 1, fontweight="semibold", color=INK, va="top")
    fig.text(0.525, 0.075, "Estimated slew ÷ limit (pre-route)", ha="center", color=INK2, fontsize=FS)
    fig.text(0.008, 0.5, "Signoff slew ÷ limit", rotation=90, va="center", color=INK2, fontsize=FS)
    fracs = [v["blind_frac"] for v in nums.values() if v["signoff_slew_violators"]]
    nfa = sum(v["false_alarms"] == 0 for v in nums.values())
    fig.text(0.012, 0.012, f"Signal nets, worst of 9 corners. Blind share {pct(min(fracs))}–{pct(max(fracs))}; "
             f"no false alarms in {nfa} of {len(nums)} designs.", fontsize=FS, color=MUTED, va="bottom")
    return save(fig, out_dir, name, nums)


# ================================================================ (a2) anatomy of the blind spot
GL_BINS = [0, 50, 100, 200, 400, 800, np.inf]
GL_LABELS = ["<50", "50–100", "100–200", "200–400", "400–800", ">800"]


def fig_anatomy(out_dir, size=(5.95, 3.55), name="blindspot_anatomy"):
    """Why the estimate is blind: its net-cap error grows with wire length, and so does the
    violation rate. Two stacked panels on one shared x (no dual axis)."""
    import pandas as pd

    d = signal_nets(["guide_len_um", "net_cap_pf_max", "act_net_cap_pf_max", "driver_class",
                     "worst_load_slew_ratio", "act_load_slew_ratio"])
    a = d[d["act_net_cap_pf_max"].notna() & (d["net_cap_pf_max"] > 0)].copy()
    a["cap_err"] = a["act_net_cap_pf_max"] / a["net_cap_pf_max"]
    a["bin"] = pd.cut(a["guide_len_um"], GL_BINS, right=False, labels=GL_LABELS)
    g = a.groupby("bin", observed=False).agg(n=("y", "size"), viol=("y", "mean"), cap_med=("cap_err", "median"))
    viol = d[d["y"] == 1]
    dly_share_viol = float((viol["driver_class"] == "clkdlybuf").mean())
    dly_share_nets = float((d["driver_class"] == "clkdlybuf").mean())
    v_est = float(viol["worst_load_slew_ratio"].median())
    v_act = float(viol["act_load_slew_ratio"].median())

    fig = plt.figure(figsize=size)
    ax1 = fig.add_axes([0.10, 0.695, 0.875, 0.205])
    ax2 = fig.add_axes([0.10, 0.275, 0.875, 0.30], sharex=ax1)
    xs = np.arange(len(GL_LABELS))
    ax1.axhline(1.0, color=AXIS, lw=1.0)
    ax1.plot(xs, g["cap_med"].values, color=INK, lw=2.0, marker="o", ms=8, mfc=INK, mec=SURFACE, mew=2, zorder=3)
    for i, v in enumerate(g["cap_med"].values):
        ax1.text(i, v + 0.12, f"{v:.2f}×", ha="center", va="bottom", fontsize=FS, color=INK2)
    ax1.set_ylim(0.8, 2.45)
    ax1.set_yticks([1.0, 2.0])
    ax1.set_yticklabels(["1×", "2×"])
    ax1.set_title("Signoff ÷ estimated net capacitance (median)", fontsize=FS, pad=5)
    plt.setp(ax1.get_xticklabels(), visible=False)
    ax1.tick_params(axis="x", length=0)
    vr = g["viol"].values
    ax2.bar(xs, 100 * vr, width=0.5, color=CRIT, zorder=2)
    for i, v in enumerate(vr):
        lab = "0%" if v < 0.0005 else f"{100 * v:.1f}%"
        ax2.text(i, 100 * v + 3, lab, ha="center", va="bottom", fontsize=FS, color=INK2)
    ax2.set_ylim(0, 100)
    ax2.set_yticks([0, 50])
    ax2.set_yticklabels(["0", "50%"])
    ax2.set_title("Nets that violate at signoff", fontsize=FS, pad=5)
    ax2.set_xticks(xs)
    ax2.set_xticklabels(GL_LABELS)
    ax2.set_xlabel("Global-route guide length per net (µm)", labelpad=3)
    ax2.set_xlim(-0.5, len(xs) - 0.5)
    ax2.text(-0.42, 97, f"{pct(dly_share_viol)} of violators: nets driven\nby hold-fix delay cells ({pct(dly_share_nets)} of nets)",
             fontsize=FS, color=INK, va="top", ha="left", linespacing=1.15)
    fig.text(0.012, 0.012, f"{len(a):,} signal nets, {d['run'].nunique()} runs, {d['design'].nunique()} designs",
             fontsize=FS, color=MUTED, ha="left", va="bottom")
    nums = {"bins": GL_LABELS, "n": [int(v) for v in g["n"].values], "violation_rate": [float(v) for v in vr],
            "cap_err_median": [float(v) for v in g["cap_med"].values], "clkdlybuf_share_of_violators": dly_share_viol,
            "clkdlybuf_share_of_nets": dly_share_nets, "violators_median_est_ratio": v_est,
            "violators_median_signoff_ratio": v_act, "rows": int(len(a))}
    return save(fig, out_dir, name, nums)


# ================================================================ (b) prediction
HOLDOUT = [  # (dataset design, label, model file)
    ("picorv32", "PicoRV32", "model_holdout_picorv32_v3.txt"),
    ("aes_cipher_top", "AES", "model_holdout_aes_v3.txt"),
    ("salsa20", "salsa20", "model_holdout_salsa20_v4.txt"),
    ("des", "DES", "model_holdout_des_v4.txt"),
    ("y_huff", "y_huff", "model_holdout_y_huff_v4.txt"),
    ("ocs_blitter", "ocs_blitter", "model_holdout_ocs_blitter_v4.txt"),
    ("BM64", "BM64", "model_holdout_bm64_v4.txt"),
    ("md5", "MD5", "model_holdout_md5_v4.txt"),
]
F_GRID = np.round(np.linspace(0, 0.20, 201), 6)


def _recall_curve(y, s):
    order = np.argsort(-np.nan_to_num(np.asarray(s, float), nan=-1e9), kind="stable")
    cum = np.concatenate([[0], np.cumsum(y[order])])
    pos = max(1, int(y.sum()))
    ks = np.round(F_GRID * len(y)).astype(int)
    return (cum[ks] / pos).tolist()


def prediction_curves(cache_dir):
    """Recall-vs-flagged curves per held-out design, pooled over that design's runs (as in
    br/train.py's leave-one-design-out evaluation), signal nets only. Cached per (model, dataset) mtime."""
    sys.path.insert(0, HERE)
    from train import FEATURES, predict  # noqa: E402  (read-only reuse of the project's scorer)

    os.makedirs(cache_dir, exist_ok=True)
    cpath = os.path.join(cache_dir, "prediction_curves.json")
    cache = json.load(open(cpath)) if os.path.exists(cpath) else {}
    ds_mtime = os.path.getmtime(DATASET)
    todo = []
    for design, lab, mf in HOLDOUT:
        mp = os.path.join(MODELS, mf)
        if not os.path.exists(mp):
            print(f"[figs_v2] prediction: {mf} not present yet; {lab} skipped")
            continue
        key = f"{mf}|{os.path.getmtime(mp):.0f}|{ds_mtime:.0f}"
        if cache.get(design, {}).get("key") == key:
            continue
        todo.append((design, lab, mf, mp, key))
    if todo:
        import lightgbm as lgb

        d = signal_nets(list(FEATURES) + ["worst_load_slew_ratio", "driver_slew_ratio", "cap_ratio"])
        for design, lab, mf, mp, key in todo:
            t0 = time.time()
            te = d[d["design"] == design]
            if not len(te) or te["y"].sum() == 0:
                print(f"[figs_v2] prediction: no rows/violators for {design}; skipped")
                continue
            p = predict(lgb.Booster(model_file=mp), te)
            y = te["y"].values.astype(int)
            r8 = te[["worst_load_slew_ratio", "driver_slew_ratio", "cap_ratio"]].fillna(0).astype(float).max(axis=1).values
            est = te["worst_load_slew_ratio"].fillna(0).values
            cache[design] = {"key": key, "label": lab, "model": mf, "n": int(len(te)), "pos": int(y.sum()),
                             "runs": int(te["run"].nunique()),
                             "curves": {"model": _recall_curve(y, p), "r8": _recall_curve(y, r8), "est": _recall_curve(y, est)}}
            print(f"[figs_v2] scored {design} ({len(te):,} nets, {mf}) in {time.time() - t0:.1f}s")
        json.dump(cache, open(cpath, "w"))
    order = [h[0] for h in HOLDOUT]
    return {k: cache[k] for k in order if k in cache and os.path.exists(os.path.join(MODELS, cache[k]["model"]))}


def _at(curve, f=0.05):
    return float(np.interp(f, F_GRID, curve))


SERIES = [("model", "BeforeRoute model", GREEN, 2.6), ("r8", "Rule R8 (max of estimated ratios)", BLUE, 2.0),
          ("est", "Timer's estimate (load slew)", GREY, 2.0)]


def fig_prediction_grid(out_dir, cache_dir, size=(12.1, 5.7), name="prediction_grid"):
    cur = prediction_curves(cache_dir)
    if not cur:
        print("[figs_v2] prediction: no held-out models; skipped")
        return None
    n = len(cur)
    ncol = 4 if n > 3 else n
    nrow = int(math.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=size, squeeze=False, sharex=True, sharey=True)
    fig.subplots_adjust(left=0.075, right=0.99, top=0.76, bottom=0.165, wspace=0.10, hspace=0.48)
    x = 100 * F_GRID
    nums = {}
    for ax, (design, c) in zip(axes.flat, cur.items()):
        ax.axvline(5, color=AXIS, lw=1.0, zorder=1)
        ax.grid(True, axis="y", zorder=0)
        for key, _, col, lw in SERIES[::-1]:
            ax.plot(x, 100 * np.asarray(c["curves"][key]), color=col, lw=lw, zorder=3 if key == "model" else 2)
        m5 = _at(c["curves"]["model"])
        ax.plot([5], [100 * m5], marker="o", ms=8, color=GREEN, mec=SURFACE, mew=2, zorder=4)
        ax.text(6.2, 100 * m5 - 6, pct(m5), fontsize=FS, color=INK, va="top", ha="left", zorder=5, path_effects=HALO)
        ax.set_title(f"{c['label']} ({c['pos']:,} violators)", fontsize=FS)
        ax.set_xlim(0, 20)
        ax.set_ylim(0, 104)
        ax.set_xticks([0, 5, 10, 15])
        ax.set_yticks([0, 50, 100])
        nums[design] = {"model": m5, "r8": _at(c["curves"]["r8"]), "est": _at(c["curves"]["est"]),
                        "n": c["n"], "pos": c["pos"], "runs": c["runs"], "model_file": c["model"]}
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    fig.text(0.012, 0.975, "Violators caught vs nets flagged, on designs each model never saw",
             fontsize=FS + 1, fontweight="semibold", color=INK, va="top")
    key_row(fig, [(None, c_, 0, lab, c_, True) for _, lab, c_, _ in SERIES], 0.012, 0.885)
    fig.text(0.53, 0.07, "Nets flagged (% of signal nets); vertical line = 5% budget", ha="center", color=INK2, fontsize=FS)
    fig.text(0.006, 0.46, "Violators caught (%)", rotation=90, va="center", color=INK2, fontsize=FS)
    fig.text(0.012, 0.008, "Ranked over all runs of the held-out design. Dot and number: model at the 5% budget.",
             fontsize=FS, color=MUTED, va="bottom")
    return save(fig, out_dir, name, nums)


def fig_prediction_summary(out_dir, cache_dir, size=(5.6, 4.5), name="prediction_summary"):
    """Dot plot: violators caught when 5% of nets are flagged, per held-out design."""
    cur = prediction_curves(cache_dir)
    if not cur:
        print("[figs_v2] prediction-summary: no held-out models; skipped")
        return None
    rows = [(c["label"], _at(c["curves"]["model"]), _at(c["curves"]["r8"]), _at(c["curves"]["est"]), c["pos"]) for c in cur.values()]
    rows.sort(key=lambda r: r[1])
    lo = max(0, 10 * math.floor(min(min(r[1:4]) for r in rows) * 10))
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0.235, 0.14, 0.62, 0.69])
    dy = 0.16
    for i, (lab, m, r8, e, pos) in enumerate(rows):
        ax.plot([min(m, r8, e) * 100, max(m, r8, e) * 100], [i, i], color=AXIS, lw=1.0, zorder=1)
        ax.plot(e * 100, i - dy, "o", ms=9, color=GREY, mec=SURFACE, mew=2, zorder=2)
        ax.plot(r8 * 100, i + dy, "s", ms=9, color=BLUE, mec=SURFACE, mew=2, zorder=3)
        ax.plot(m * 100, i, "*", ms=18, color=GREEN, mec=SURFACE, mew=1.5, zorder=4)
        ax.text(101.5, i, pct(m), fontsize=FS, color=INK, va="center", ha="left")
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r[0] for r in rows])
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(lo, 100.5)
    ticks = [t for t in range(int(lo), 101, 10)]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{t}%" if t == 100 else str(t) for t in ticks])
    ax.grid(True, axis="x", zorder=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Violators caught at a 5% budget (unseen designs)", labelpad=4)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    key_row(fig, [("*", GREEN, 16, "BeforeRoute model", None, True), ("s", BLUE, 9, "Rule R8", None, True),
                  ("o", GREY, 9, "Estimate", None, True)], 0.012, 0.935)
    ms_ = [r[1] for r in rows]
    nums = {r[0]: {"model": r[1], "r8": r[2], "est": r[3], "violators": r[4]} for r in rows}
    nums["_range_model"] = [min(ms_), max(ms_)]
    return save(fig, out_dir, name, nums)


# ================================================================ (c) intervention Pareto
def _pareto_data(hs):
    arms = arms_table(hs)
    b = arms.get("base")
    if b is None:
        return None
    yb, hb = b["signoff_violating_data_nets"], b.get("hold_ws")

    def info(a):
        r = arms[a]
        return {"arm": a, "cells": cells_changed(r), "violators": r["signoff_violating_data_nets"],
                "hold_kept": (r["hold_ws"] / hb) if (hb and r.get("hold_ws") is not None) else None,
                "area_delta": (r["stdcell_area"] / b["stdcell_area"] - 1) if (b.get("stdcell_area") and r.get("stdcell_area")) else None}

    uni = sorted([(int(a[3:]), info(a)) for a in arms if classify(a) == "uniform" and a[3:].isdigit() and cells_changed(arms[a]) is not None])
    out = {"base": hs["base"], "baseline_violators": yb, "baseline_hold_ns": hb, "uniform": [u[1] for u in uni],
           "uniform_pct": [u[0] for u in uni],
           "tiered": [info(a) for a in arms if classify(a) == "tiered" and cells_changed(arms[a]) is not None]}
    for role in ("top5", "thr", "rule"):
        a = pick(arms, role)
        out[role] = info(a) if a else None
    return out


def _pareto_draw(ax, P, big=False):
    yb = P["baseline_violators"]
    for t in P["tiered"]:
        ax.plot(t["cells"], t["violators"], "D", ms=7, mfc=SURFACE, mec=OTHER, mew=1.4, zorder=2)
    ux = [0] + [u["cells"] for u in P["uniform"]]
    uy = [yb] + [u["violators"] for u in P["uniform"]]
    if P["uniform"]:
        ax.plot(ux, uy, color=ROSE, lw=2.4 if big else 2.0, zorder=3)
        ax.plot(ux[1:], uy[1:], "o", ms=9, color=ROSE, mec=SURFACE, mew=2, zorder=4)
    ax.plot([0], [yb], "o", ms=10, color=GREY, mec=SURFACE, mew=2, zorder=5)
    if P["thr"] and P["thr"] != P["top5"]:
        ax.plot(P["thr"]["cells"], P["thr"]["violators"], "*", ms=(19 if big else 16), mfc=SURFACE, mec=GREEN, mew=1.8, zorder=6)
    if P["rule"]:
        ax.plot(P["rule"]["cells"], P["rule"]["violators"], "s", ms=11, color=BLUE, mec=SURFACE, mew=2, zorder=6)
    if P["top5"]:
        ax.plot(P["top5"]["cells"], P["top5"]["violators"], "*", ms=(24 if big else 19), color=GREEN, mec=SURFACE, mew=1.5, zorder=7)
    ax.grid(True, axis="y", zorder=0)
    ax.xaxis.set_major_formatter(mticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    xmax = max(ux + [c["cells"] for c in (P["top5"], P["thr"], P["rule"]) if c] + [t["cells"] for t in P["tiered"]] + [1])
    ax.set_xlim(-0.04 * xmax, 1.06 * xmax)
    return xmax


def fig_pareto_hero(out_dir, base="d1-picorv32-006", size=(5.95, 4.55), name="pareto_hero"):
    """One base, big and simple: baseline, uniform 30/50/70% curve, BeforeRoute top-5% arm."""
    hs = load_hero(base)
    P = _pareto_data(hs) if hs else None
    if not P or not P["uniform"]:
        print(f"[figs_v2] pareto-hero: {base} missing or has no uniform arms; skipped")
        return None
    P = dict(P, tiered=[], thr=None, rule=None)   # hero: headline comparison only
    yb = P["baseline_violators"]
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0.125, 0.135, 0.845, 0.745])
    xmax = _pareto_draw(ax, P, big=True)
    ax.set_ylim(-0.04 * yb, yb * 1.12)
    ax.set_xlabel("Cells changed by the repair step (resized + buffers)", labelpad=4)
    ax.set_ylabel("Signal nets violating at signoff", labelpad=4)
    ax.annotate(f"Baseline: {yb:,}", (0, yb), xytext=(10, 9), textcoords="offset points", fontsize=FS, color=INK2, va="bottom")
    for h, u in zip(P["uniform_pct"][:-1], P["uniform"][:-1]):
        ax.annotate(f"{h}%", (u["cells"], u["violators"]), xytext=(9, 3), textcoords="offset points", fontsize=FS, color=INK2,
                    va="bottom", path_effects=HALO)
    um, hpct = P["uniform"][-1], P["uniform_pct"][-1]
    ax.annotate(f"Uniform {hpct}%, every net\n{um['violators']:,} left · {um['cells']:,} cells\nhold margin kept {pct(um['hold_kept'])}",
                (um["cells"], um["violators"]), xytext=(1.035 * xmax, 0.60 * yb), textcoords="data", ha="right", va="bottom",
                fontsize=FS, color=INK2, linespacing=1.2,
                arrowprops=dict(arrowstyle="-", color=AXIS, lw=1.0, shrinkA=2, shrinkB=8, relpos=(1.0, 0.0)))
    t5 = P["top5"]
    if t5:
        ax.annotate(f"BeforeRoute top 5% @ 70%\n{t5['violators']:,} left · {t5['cells']:,} cells\nhold margin kept {pct(t5['hold_kept'])}",
                    (t5["cells"], t5["violators"]), xytext=(0.015 * xmax, 0.22 * yb), textcoords="data", ha="left", va="bottom",
                    fontsize=FS, color=INK, linespacing=1.2,
                    arrowprops=dict(arrowstyle="-", color=AXIS, lw=1.0, shrinkA=2, shrinkB=10, relpos=(0.55, 0.0)))
    fig.text(0.012, 0.975, f"{BASE_LABEL.get(base, base)}, unseen by the model; 9-corner signoff",
             fontsize=FS, color=INK, va="top", fontweight="semibold")
    nums = {k: P[k] for k in ("baseline_violators", "baseline_hold_ns", "uniform", "uniform_pct", "top5")}
    nums["base"] = base
    return save(fig, out_dir, name, nums)


def fig_pareto_grid(out_dir, bases, name, title, size=None):
    have = []
    for b in bases:
        hs = load_hero(b)
        P = _pareto_data(hs) if hs else None
        if P:
            have.append((b, P))
    if not have:
        print(f"[figs_v2] {name}: none of {bases} landed yet; skipped")
        return None
    n = len(have)
    ncol = min(3, n)
    nrow = int(math.ceil(n / ncol))
    size = size or (12.1, 4.7 if nrow == 1 else 7.9)
    fig, axes = plt.subplots(nrow, ncol, figsize=size, squeeze=False)
    top = 1 - 1.05 / size[1]
    fig.subplots_adjust(left=0.075 if ncol > 1 else 0.15, right=0.985, top=top, bottom=0.75 / size[1] + 0.02,
                        wspace=0.22, hspace=0.42)
    nums = {}
    present = set()
    for ax, (b, P) in zip(axes.flat, have):
        yb = P["baseline_violators"]
        ax.set_title(f"{BASE_LABEL.get(b, b)} · baseline {yb:,}", fontsize=FS)
        nums[b] = P
        if not (P["uniform"] or P["top5"] or P["thr"] or P["rule"]):
            ax.plot([0], [yb], "o", ms=10, color=GREY, mec=SURFACE, mew=2)
            ax.set_xlim(-0.5, 10)
            ax.set_ylim(0, yb * 1.42)
            ax.set_xticks([])
            ax.text(5, yb * 0.55, "arms pending\nTBD-R3", ha="center", va="center", fontsize=FS, color=MUTED, linespacing=1.3)
            ax.yaxis.set_major_locator(mticker.MaxNLocator(nbins=3, integer=True))
            present.add("base")
            continue
        _pareto_draw(ax, P)
        present |= {"base"} | ({"uni"} if P["uniform"] else set()) | {k for k in ("top5", "thr", "rule") if P[k]} \
            | ({"tiered"} if P["tiered"] else set())
        ax.set_ylim(-0.04 * yb, yb * 1.45)
        ticks = mticker.MaxNLocator(nbins=4, integer=True).tick_values(0, yb)
        ax.set_yticks([t for t in ticks if 0 <= t <= yb])
        for k, (h, u) in enumerate(zip(P["uniform_pct"], P["uniform"])):
            last = k == len(P["uniform"]) - 1
            ax.annotate(f"{h}%", (u["cells"], u["violators"]), xytext=((-8, 8) if last else (8, 4)), textcoords="offset points",
                        fontsize=FS, color=INK2, va="bottom", ha="right" if last else "left", path_effects=HALO)
        # scoreboard in the free top band: glyph + "violators left · hold kept"
        board = [(P["top5"], "*", GREEN, True), (P["thr"] if P["thr"] != P["top5"] else None, "*", GREEN, False),
                 (P["rule"], "s", BLUE, True), (P["uniform"][-1] if P["uniform"] else None, "o", ROSE, True)]
        board = [x for x in board if x[0]]
        for k, (info, mk, col, filled) in enumerate(board):
            cx, cy = (0.05 + 0.50 * (k % 2), 0.955 - 0.105 * (k // 2))
            ax.plot([cx], [cy], marker=mk, ms=(15 if mk == "*" else 9), color=col, mfc=col if filled else SURFACE,
                    mec=SURFACE if filled else col, mew=1.5 if filled else 1.8, transform=ax.transAxes, clip_on=False, lw=0)
            hk = "–" if info["hold_kept"] is None else pct(info["hold_kept"])
            ax.text(cx + 0.045, cy, f"{info['violators']:,} · {hk}", transform=ax.transAxes, fontsize=FS, color=INK,
                    va="center", ha="left")
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    suffix = "   (labels: violators left · hold margin kept)" if ncol > 1 else ""
    fig.text(0.012, 1 - 0.08 / size[1], title + suffix, fontsize=FS + 1, fontweight="semibold", color=INK, va="top")
    items = [("o", GREY, 10, "baseline", None, True, "base"), ("o", ROSE, 9, "uniform 30/50/70%", ROSE, True, "uni"),
             ("*", GREEN, 16, "top 5% @70%", None, True, "top5"), ("*", GREEN, 15, "p ≥ 0.5 @70%", None, False, "thr"),
             ("s", BLUE, 10, "rule R8 top 5%", None, True, "rule"), ("D", OTHER, 7, "tiered / learned margins", None, False, "tiered")]
    key_row(fig, [i[:6] for i in items if i[6] in present], 0.012, 1 - 0.55 / size[1], gap=0.022 * 12.1 / size[0])
    fig.text(0.5, 0.012, "Cells changed by the repair step (resized + buffers)", ha="center", color=INK2, fontsize=FS, va="bottom")
    fig.text(0.006, 0.5, "Signal nets violating at signoff", rotation=90, va="center", color=INK2, fontsize=FS)
    return save(fig, out_dir, name, nums)


# ================================================================ (d) pipeline diagram
def fig_pipeline(out_dir, size=(12.1, 2.6), name="pipeline"):
    """Flow row with the BeforeRoute step highlighted, its three sub-steps in a zoom-in panel,
    and the feedback loop (signoff reports become training labels). Text widths are measured,
    so the layout holds if wording changes."""
    W, H = size
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    rend = fig.canvas.get_renderer()

    def width_in(t):
        return t.get_window_extent(renderer=rend).width / fig.dpi

    y0, h = 1.72, 0.80          # main row
    stages = ["Synthesis", "Floorplan\n+ place", "CTS", "Global\nroute", "BR", "Detailed\nroute", "RC\nextraction", "9-corner\nsignoff"]
    widths = [1.18, 1.18, 0.82, 1.08, 1.55, 1.12, 1.18, 1.18]
    gap = (W - 0.06 - sum(widths)) / (len(stages) - 1)
    x = 0.03
    boxes = {}
    for s_, w in zip(stages, widths):
        if s_ == "BR":
            ax.add_patch(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0,rounding_size=0.10", fc="#14240a", ec=BRAND, lw=2.2, zorder=3))
            ax.text(x + w / 2, y0 + h / 2, "BeforeRoute", ha="center", va="center", fontsize=FS + 1, fontweight="semibold", color=INK, zorder=4)
        else:
            ax.add_patch(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0,rounding_size=0.10", fc="#121212", ec="#5a5a5a", lw=1.2, zorder=3))
            ax.text(x + w / 2, y0 + h / 2, s_, ha="center", va="center", fontsize=FS, color="#e6e6e6", linespacing=1.1, zorder=4)
        boxes[s_] = (x, w)
        x += w + gap
    names = list(boxes)
    for a_, b_ in zip(names[:-1], names[1:]):
        xa = boxes[a_][0] + boxes[a_][1]
        xb = boxes[b_][0]
        ax.add_patch(FancyArrowPatch((xa + 0.03, y0 + h / 2), (xb - 0.03, y0 + h / 2), arrowstyle="-|>", mutation_scale=14,
                                     color="#7a7a7a", lw=1.4, zorder=2))
    # zoom-in panel with the three sub-steps, laid out from measured text widths
    steps = [("1", "Score every net", "LightGBM, post-GRT features"),
             ("2", "Mask the rest", "do-not-touch on all others"),
             ("3", "Stock repair_design", "70% margin, flagged only")]
    py0, py1 = 0.10, 1.05
    num_w, pad, arrow_w = 0.36, 0.20, 0.55
    blocks = []
    for num, head, sub in steps:
        tn = ax.text(0, 0, num, fontsize=FS + 6, fontweight="semibold", color=BRAND, ha="left", va="top", zorder=4)
        th = ax.text(0, 0, head, fontsize=FS, fontweight="semibold", color=INK, ha="left", va="top", zorder=4)
        ts = ax.text(0, 0, sub, fontsize=FS, color=INK2, ha="left", va="top", zorder=4)
        blocks.append((tn, th, ts, num_w + max(width_in(th), width_in(ts))))
    px0 = 0.03
    px1 = px0 + pad + sum(bw for *_, bw in blocks) + arrow_w * (len(blocks) - 1) + pad
    ax.add_patch(FancyBboxPatch((px0, py0), px1 - px0, py1 - py0, boxstyle="round,pad=0,rounding_size=0.12", fc="#0b1406",
                                ec=BRAND, lw=1.4, zorder=1))
    sx = px0 + pad
    for i, (tn, th, ts, bw) in enumerate(blocks):
        tn.set_position((sx, py1 - 0.12))
        th.set_position((sx + num_w, py1 - 0.15))
        ts.set_position((sx + num_w, py1 - 0.50))
        sx += bw
        if i < len(blocks) - 1:
            ax.add_patch(FancyArrowPatch((sx + 0.12, (py0 + py1) / 2 - 0.05), (sx + arrow_w - 0.12, (py0 + py1) / 2 - 0.05),
                                         arrowstyle="-|>", mutation_scale=13, color=BRAND, lw=1.3, zorder=4))
            sx += arrow_w
    bx, bw_ = boxes["BR"]
    ax.plot([bx + 0.06, max(px0 + 0.3, bx - 1.2)], [y0, py1], color=BRAND, lw=1.0, alpha=0.8, zorder=1)
    ax.plot([bx + bw_ - 0.06, min(px1 - 0.3, bx + bw_ + 1.2)], [y0, py1], color=BRAND, lw=1.0, alpha=0.8, zorder=1)
    # feedback loop: signoff reports -> training labels -> the model in step 1
    sx_, sw_ = boxes["9-corner\nsignoff"]
    xl = sx_ + sw_ / 2
    ax.add_patch(FancyArrowPatch((xl, y0 - 0.03), (px1 + 0.03, 0.48), connectionstyle="angle,angleA=-90,angleB=0,rad=10",
                                 arrowstyle="-|>", mutation_scale=15, color=BRAND, lw=1.8, zorder=2))
    ax.text(xl - 0.12, (py1 + y0) / 2 - 0.02, "signoff reports become\ntraining labels", ha="right", va="center", fontsize=FS,
            color=INK2, linespacing=1.1, zorder=4)
    return save(fig, out_dir, name, {"stages": [s_.replace("\n", " ") for s_ in stages], "panel_right_in": round(px1, 2)})


# ================================================================ (e) iterations to closure
def fig_iterations(out_dir, bases=None, size=(5.95, 4.0), name="iterations"):
    bases = bases or (CONFIRMATORY + ROUND3 + EXPLORATORY)
    found = []
    for b in bases:
        hs = load_hero(b)
        if hs is None:
            continue
        arms = arms_table(hs)
        loop = sorted([(int(a[len("lst-sgl"):].split("-")[0]), r) for a, r in arms.items()
                       if a.startswith("lst-sgl") and a[len("lst-sgl"):].split("-")[0].isdigit()])
        if loop:
            found.append((b, arms, loop))
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0.13, 0.17, 0.82, 0.68])
    ax.set_xlabel("Route + extract + signoff passes", labelpad=4)
    ax.set_ylabel("Signal nets violating at signoff", labelpad=4)
    ax.grid(True, axis="y", zorder=0)
    if not found:
        ax.set_xlim(-0.2, 3.4)
        ax.set_ylim(0, 1)
        ax.set_xticks([0, 1, 2, 3])
        ax.set_yticks([])
        ax.text(0.5, 0.58, "TBD-R3", transform=ax.transAxes, ha="center", va="center", fontsize=FS + 14, fontweight="semibold", color="#5a5a5a")
        ax.text(0.5, 0.36, "signoff-guided loop arms (lst-sgl*, lst-cln1)\nnot yet in any hero_summary.json", transform=ax.transAxes,
                ha="center", va="center", fontsize=FS, color=MUTED, linespacing=1.2)
        fig.text(0.012, 0.965, "Iterations to closure (placeholder)", fontsize=FS, fontweight="semibold", color=INK, va="top")
        return save(fig, out_dir, name, {"placeholder": True})
    b, arms, loop = found[0]
    yb = arms["base"]["signoff_violating_data_nets"]
    nums = {"base": b, "baseline": yb}
    lx = [0] + [k for k, _ in loop]
    ly = [yb] + [r["signoff_violating_data_nets"] for _, r in loop]
    ax.plot(lx, ly, color=LOOP, lw=2.0, marker="o", ms=9, mfc=SURFACE, mec=LOOP, mew=2, zorder=3)
    ax.annotate("signoff-guided loop", (lx[-1], ly[-1]), xytext=(8, 6), textcoords="offset points", fontsize=FS, color=INK2,
                path_effects=HALO)
    nums["loop"] = list(zip(lx, ly))
    t5 = pick(arms, "top5")
    if t5:
        bx_, by_ = [0, 1], [yb, arms[t5]["signoff_violating_data_nets"]]
        if "lst-cln1-70" in arms:
            bx_.append(2)
            by_.append(arms["lst-cln1-70"]["signoff_violating_data_nets"])
        ax.plot(bx_, by_, color=GREEN, lw=2.6, zorder=4)
        ax.plot(bx_[1:], by_[1:], "*", ms=18, color=GREEN, mec=SURFACE, mew=1.5, zorder=5)
        ax.annotate("BeforeRoute" + (" + cleanup" if len(bx_) > 2 else ""), (bx_[-1], by_[-1]), xytext=(8, -16),
                    textcoords="offset points", fontsize=FS, color=INK2, path_effects=HALO)
        nums["beforeroute"] = list(zip(bx_, by_))
    if "uni70" in arms:
        ux_, uy_ = [0, 1], [yb, arms["uni70"]["signoff_violating_data_nets"]]
        ax.plot(ux_, uy_, color=ROSE, lw=2.0, marker="o", ms=9, mec=SURFACE, mew=2, zorder=3)
        ax.annotate("uniform 70%", (1, uy_[-1]), xytext=(8, 10), textcoords="offset points", fontsize=FS, color=INK2, path_effects=HALO)
        nums["uniform70"] = list(zip(ux_, uy_))
    ax.plot([0], [yb], "o", ms=10, color=GREY, mec=SURFACE, mew=2, zorder=6)
    ax.set_xticks(sorted(set(lx + [0, 1, 2])))
    ax.set_ylim(-0.04 * yb, yb * 1.1)
    fig.text(0.012, 0.965, f"{BASE_LABEL.get(b, b)}: violators left after each pass", fontsize=FS, fontweight="semibold", color=INK, va="top")
    return save(fig, out_dir, name, nums)


# ================================================================ CLI
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="+")
    ap.add_argument("--out", default=os.path.join(ROOT, "figures", "v2"))
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    cache = os.path.join(out, "cache")
    setup_style()
    jobs = {
        "blindspot": lambda: fig_blindspot(out),
        "blindspot-grid": lambda: fig_blindspot_grid(out),
        "anatomy": lambda: fig_anatomy(out),
        "prediction": lambda: fig_prediction_grid(out, cache),
        "prediction-summary": lambda: fig_prediction_summary(out, cache),
        "pareto-hero": lambda: fig_pareto_hero(out),
        "pareto": lambda: [fig_pareto_grid(out, CONFIRMATORY, "pareto_confirmatory",
                                           "Targeted vs uniform repair on three held-out bases (confirmatory)"),
                           fig_pareto_grid(out, ROUND3, "pareto_round3", "Round 3: six new design families, unseen by the model"),
                           fig_pareto_grid(out, EXPLORATORY, "pareto_exploratory", "Round 0 (labels: violators · hold kept)", size=(5.95, 4.9))],
        "pipeline": lambda: fig_pipeline(out),
        "iterations": lambda: fig_iterations(out),
    }
    names = list(jobs) if a.names == ["all"] else a.names
    bad = [n for n in names if n not in jobs]
    if bad:
        ap.error(f"unknown figure(s): {bad}; choose from {list(jobs)} or 'all'")
    failed = []
    for n in names:
        try:
            jobs[n]()
        except FileNotFoundError as e:
            print(f"[figs_v2] {n}: input missing ({e}); skipped")
        except Exception as e:  # keep going: one broken input must not block the rest
            failed.append(n)
            print(f"[figs_v2] {n}: FAILED {type(e).__name__}: {e}")
    os.makedirs(out, exist_ok=True)
    npath = os.path.join(out, "figs_v2_numbers.json")
    prev = json.load(open(npath)) if os.path.exists(npath) else {}
    prev.update(NUMBERS)
    json.dump(prev, open(npath, "w"), indent=1, default=float)
    print(f"[figs_v2] numbers -> {os.path.relpath(npath, ROOT)}" + (f"; failed: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
