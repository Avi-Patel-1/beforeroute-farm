#!/usr/bin/env python3
"""BeforeRoute figure suite v2: dark-surface figures sized for the NVIDIA slide template.

Usage:
  python3 br/figs_v2.py all --out figures/v2/
  python3 br/figs_v2.py NAME [NAME ...] --out figures/v2/
     NAME in: blindspot, blindspot-grid, anatomy, prediction, prediction-summary,
              pareto-hero, pareto, pipeline, iterations

Every number drawn is computed here from results/dataset.parquet, results/<base>/hero_summary.json
and the held-out models in models/. Missing inputs are skipped with a message (Round 3 lands
incrementally), so `all` is safe to rerun at any time. The numbers each figure printed are written
to <out>/figs_v2_numbers.json for cross-checking against the deck text.

Figures are drawn at their final size on the 13.33 x 7.5 in slide, so a 14 pt label in the
figure is 14 pt on the slide. PNG, 200 dpi, black background (#000, same as the template).

Palette (validated with the dataviz skill's validate_palette.js: dark mode, surface #000000,
--pairs all: lightness band, chroma floor, CVD (worst dE 11.8 deutan), normal-vision (26.5) and
contrast all PASS):
  BeforeRoute / model  #6aa800  (NVIDIA #76B900 hue, lightness snapped into the dark band)
  uniform margin       #d55181  (rose)
  rule R8              #3987e5  (blue)
  baseline / estimate  #8c8c8c  (neutral grey)
Marker shape repeats identity: star = model arm, square = rule, circle = uniform / estimate.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys
import time

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, LogNorm  # noqa: E402
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
MUTED = "#9a9a9a"        # footnotes (7.5:1)
GRID = "#262626"         # hairline grid
AXIS = "#4a4a4a"         # axis lines (template accent4)
GREEN = "#6aa800"        # BeforeRoute / model (marks)
BRAND = "#76b900"        # NVIDIA brand green (diagram accents only, not data)
ROSE = "#d55181"         # uniform / blanket margin
BLUE = "#3987e5"         # deterministic rule R8
GREY = "#8c8c8c"         # baseline / raw estimate
CRIT = "#d03b3b"         # status: violation the estimate missed
LOOP = "#cfcfcf"         # signoff-guided loop (conventional practice, neutral)
OTHER = "#5c5c5c"        # other policies tried (context only)
GREY_RAMP = LinearSegmentedColormap.from_list("greys_dark", ["#2e2e2e", "#f2f2f2"])
CRIT_RAMP = LinearSegmentedColormap.from_list("crit_dark", ["#a92f2f", "#ff9a92"])
DPI = 200
FS = 14                  # minimum font size on the slide

NUMBERS: dict = {}       # what each figure printed, for cross-checking


def setup_style():
    names = {f.name for f in font_manager.fontManager.ttflist}
    fam = "Inter" if "Inter" in names else "DejaVu Sans"
    plt.rcParams.update({
        "font.family": fam, "font.size": FS,
        "axes.titlesize": FS + 1, "axes.titleweight": "semibold", "axes.titlelocation": "left",
        "axes.titlecolor": INK, "axes.titlepad": 10,
        "axes.labelsize": FS, "axes.labelcolor": INK2, "axes.edgecolor": AXIS, "axes.linewidth": 1.0,
        "axes.facecolor": SURFACE, "figure.facecolor": SURFACE, "savefig.facecolor": SURFACE,
        "axes.spines.top": False, "axes.spines.right": False,
        "xtick.labelsize": FS, "ytick.labelsize": FS, "xtick.color": AXIS, "ytick.color": AXIS,
        "xtick.labelcolor": INK2, "ytick.labelcolor": INK2, "xtick.major.size": 4, "ytick.major.size": 4,
        "grid.color": GRID, "grid.linewidth": 0.8, "grid.linestyle": "-",
        "text.color": INK, "legend.frameon": False, "legend.fontsize": FS,
        "lines.solid_capstyle": "round", "lines.solid_joinstyle": "round",
        "hatch.color": AXIS,
    })


def save(fig, out_dir, name, numbers=None):
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, name + ".png")
    fig.savefig(path, dpi=DPI, facecolor=SURFACE)
    plt.close(fig)
    NUMBERS[name] = numbers or {}
    print(f"[figs_v2] wrote {os.path.relpath(path, ROOT)}")
    return path


def fmt_int(v):
    return f"{int(round(v)):,}"


def pct(v, nd=0):
    return f"{100 * v:.{nd}f}%"


def footnote(fig, text, y=0.012):
    fig.text(0.012, y, text, fontsize=FS - 2 if False else FS, color=MUTED, ha="left", va="bottom")


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
    except Exception as e:  # half-written file while Round 3 lands
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
    if arm.endswith("hv3") or arm.endswith("hv4") or "-70h" in arm:
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
    "d3-salsa20-000": "salsa20", "d3-des-000": "DES", "d3-y_huff-000": "y_huff (Huffman)",
    "d3-ocs_blitter-000": "ocs_blitter", "d3-bm64-000": "BM64", "d3-md5-000": "MD5",
}
CONFIRMATORY = ["d1-picorv32-006", "d1-picorv32-016", "d1-aes_cipher-000"]
ROUND3 = ["d3-salsa20-000", "d3-des-000", "d3-y_huff-000", "d3-ocs_blitter-000", "d3-bm64-000", "d3-md5-000"]
EXPLORATORY = ["picorv32-base-v1"]


# ================================================================ (a) blind spot
XMAX, YMAX = 2.0, 3.6


def _blind_panel(ax, est, act, gx, small=False):
    est = np.clip(np.asarray(est, float), 0, XMAX - 1e-6)
    act = np.clip(np.asarray(act, float), 0, YMAX - 1e-6)
    ax.add_patch(Rectangle((0, 1), 1, YMAX - 1, facecolor=CRIT, alpha=0.10, lw=0, zorder=0))
    ext = (0, XMAX, 0, YMAX)
    hb = ax.hexbin(est, act, gridsize=gx, extent=ext, bins="log", mincnt=1, cmap=GREY_RAMP,
                   linewidths=0.2, edgecolors=SURFACE, zorder=1)
    blind = (act > 1) & (est <= 1)
    if blind.any():
        ax.hexbin(est[blind], act[blind], gridsize=gx, extent=ext, bins="log", mincnt=1, cmap=CRIT_RAMP,
                  linewidths=0.2, edgecolors=SURFACE, zorder=2)
    ax.plot([0, min(XMAX, YMAX)], [0, min(XMAX, YMAX)], color=GREY, lw=1.0, zorder=3)
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
    n_c = int(((act > 1) & (est > 1)).sum())
    n_fa = int(((est > 1) & (act <= 1)).sum())
    return hb, dict(nets=int(len(est)), signoff_slew_violators=n_v, blind=n_b, caught_by_estimate=n_c,
                    false_alarms=n_fa, blind_frac=(n_b / n_v if n_v else float("nan")))


def fig_blindspot(out_dir, run="d1-picorv32-006", label="PicoRV32", size=(5.95, 3.4), name="blindspot_hero"):
    d = signal_nets(["worst_load_slew_ratio", "act_load_slew_ratio"])
    x = d[(d["run"] == run) & d["act_load_slew_ratio"].notna() & d["worst_load_slew_ratio"].notna()]
    if not len(x):
        print(f"[figs_v2] blindspot: no rows for {run}; skipped")
        return None
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0.105, 0.20, 0.87, 0.74])
    _, nums = _blind_panel(ax, x["worst_load_slew_ratio"].values, x["act_load_slew_ratio"].values, gx=(46, 19))
    ax.set_xlabel("Estimated slew ÷ limit  (pre-route, global-route parasitics)", labelpad=4)
    ax.set_ylabel("Signoff slew ÷ limit", labelpad=4)
    # headline in the blind-spot quadrant
    ax.text(0.04, YMAX - 0.12, f"{nums['blind']:,} of {nums['signoff_slew_violators']:,}", fontsize=FS + 8,
            fontweight="semibold", color=INK, va="top", ha="left", zorder=6)
    ax.text(0.04, YMAX - 0.86, f"signoff slew violators ({pct(nums['blind_frac'])})\nlooked clean to the estimate",
            fontsize=FS, color=INK2, va="top", ha="left", linespacing=1.15, zorder=6)
    ax.text(1.04, YMAX - 0.12, f"flagged by the estimate: {nums['caught_by_estimate']:,}", fontsize=FS, color=INK2,
            va="top", ha="left", zorder=6)
    ax.text(1.04, 0.5, f"false alarms: {nums['false_alarms']:,}", fontsize=FS, color=INK2, va="center", ha="left", zorder=6)
    ax.text(1.62, 1.84, "estimate = signoff", fontsize=FS, color=GREY, rotation=0, ha="left", va="bottom", zorder=6)
    fig.text(0.012, 0.012, f"{label}, {nums['nets']:,} signal nets, worst of 9 corners. Shade: nets per hexagon (log).",
             fontsize=FS - 2.5 if size[0] < 5 else FS - 2, color=MUTED, ha="left", va="bottom")
    nums.update(run=run)
    return save(fig, out_dir, name, nums)


BLIND_GRID_RUNS = [
    ("d1-picorv32-006", "PicoRV32"), ("d1-aes_cipher-000", "AES"), ("d3-salsa20-000", "salsa20"),
    ("d3-des-000", "DES"), ("d3-y_huff-000", "y_huff"), ("d3-ocs_blitter-000", "ocs_blitter"),
    ("d3-bm64-000", "BM64"), ("d3-md5-000", "MD5"),
]


def fig_blindspot_grid(out_dir, size=(12.1, 5.3), name="blindspot_grid"):
    d = signal_nets(["worst_load_slew_ratio", "act_load_slew_ratio"])
    have = [(r, lab) for r, lab in BLIND_GRID_RUNS if (d["run"] == r).any()]
    if not have:
        print("[figs_v2] blindspot-grid: no runs; skipped")
        return None
    ncol = 4 if len(have) > 6 else 3
    nrow = int(math.ceil(len(have) / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=size, squeeze=False, sharex=True, sharey=True)
    fig.subplots_adjust(left=0.07, right=0.99, top=0.9, bottom=0.15, wspace=0.08, hspace=0.42)
    nums = {}
    for ax, (run, lab) in zip(axes.flat, have):
        x = d[(d["run"] == run) & d["act_load_slew_ratio"].notna() & d["worst_load_slew_ratio"].notna()]
        _, n = _blind_panel(ax, x["worst_load_slew_ratio"].values, x["act_load_slew_ratio"].values, gx=(22, 11), small=True)
        ax.set_title(f"{lab}: {n['blind']:,} of {n['signoff_slew_violators']:,} ({pct(n['blind_frac'])})", fontsize=FS)
        nums[run] = n
    for ax in list(axes.flat)[len(have):]:
        ax.set_visible(False)
    fig.text(0.012, 0.965, "Signoff slew violators the estimate called clean (red), per design, one run each",
             fontsize=FS + 1, fontweight="semibold", color=INK, va="top")
    fig.text(0.53, 0.06, "Estimated slew ÷ limit (pre-route)", ha="center", color=INK2, fontsize=FS)
    fig.text(0.012, 0.52, "Signoff slew ÷ limit", rotation=90, va="center", color=INK2, fontsize=FS)
    fracs = [v["blind_frac"] for v in nums.values() if v["signoff_slew_violators"]]
    fig.text(0.012, 0.005, f"Signal nets; worst of 9 corners; 0 false alarms in {sum(v['false_alarms'] == 0 for v in nums.values())} of {len(nums)} designs. "
             f"Blind share {pct(min(fracs))}–{pct(max(fracs))}.", fontsize=FS - 2, color=MUTED, va="bottom")
    return save(fig, out_dir, name, nums)


# ================================================================ (a2) anatomy of the blind spot
GL_BINS = [0, 50, 100, 200, 400, 800, np.inf]
GL_LABELS = ["<50", "50–100", "100–200", "200–400", "400–800", ">800"]


def fig_anatomy(out_dir, size=(5.95, 3.4), name="blindspot_anatomy"):
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
    ax1 = fig.add_axes([0.105, 0.60, 0.87, 0.31])
    ax2 = fig.add_axes([0.105, 0.17, 0.87, 0.31], sharex=ax1)
    xs = np.arange(len(GL_LABELS))
    # top: extracted / estimated net cap (median)
    ax1.axhline(1.0, color=AXIS, lw=1.0)
    ax1.plot(xs, g["cap_med"].values, color=INK, lw=2.0, marker="o", ms=8, mfc=INK, mec=SURFACE, mew=2, zorder=3)
    for i, v in enumerate(g["cap_med"].values):
        ax1.text(i, v + 0.09, f"{v:.2f}×", ha="center", va="bottom", fontsize=FS, color=INK2)
    ax1.set_ylim(0.8, 2.35)
    ax1.set_yticks([1.0, 2.0])
    ax1.set_yticklabels(["1×", "2×"])
    ax1.set_title("Signoff ÷ estimated net capacitance (median)", fontsize=FS, pad=6)
    plt.setp(ax1.get_xticklabels(), visible=False)
    ax1.tick_params(axis="x", length=0)
    # bottom: violation rate (bars, 4 px rounded feel via thin bars; status color = violation)
    vr = g["viol"].values
    ax2.bar(xs, 100 * vr, width=0.5, color=CRIT, zorder=2)
    for i, v in enumerate(vr):
        lab = "0%" if v < 0.0005 else (f"{100 * v:.1f}%")
        ax2.text(i, 100 * v + 2.5, lab, ha="center", va="bottom", fontsize=FS, color=INK2)
    ax2.set_ylim(0, 75)
    ax2.set_yticks([0, 50])
    ax2.set_yticklabels(["0", "50%"])
    ax2.set_title("Nets that violate at signoff", fontsize=FS, pad=6)
    ax2.set_xticks(xs)
    ax2.set_xticklabels(GL_LABELS)
    ax2.set_xlabel("Global-route guide length per net (µm)", labelpad=3)
    ax2.set_xlim(-0.5, len(xs) - 0.5)
    ax2.text(-0.4, 66, f"{pct(dly_share_viol)} of violators are driven by hold-fix delay cells\n"
             f"(clkdlybuf, {pct(dly_share_nets)} of nets)", fontsize=FS, color=INK, va="top", ha="left", linespacing=1.15)
    fig.text(0.012, 0.012, f"All {len(a):,} signal nets, {d['run'].nunique()} runs, {d['design'].nunique()} designs. "
             f"Violators: median {v_est:.2f}× limit estimated, {v_act:.2f}× at signoff.",
             fontsize=FS - 2, color=MUTED, ha="left", va="bottom")
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
    br/train.py's leave-one-design-out evaluation). Cached per (model, dataset) mtime."""
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
            booster = lgb.Booster(model_file=mp)
            p = predict(booster, te)
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


SERIES = [("model", "BeforeRoute model", GREEN, 2.6), ("r8", "Rule R8 (max estimated ratio)", BLUE, 2.0),
          ("est", "Timer's estimate (load slew)", GREY, 2.0)]


def fig_prediction_grid(out_dir, cache_dir, size=(12.1, 5.5), name="prediction_grid"):
    cur = prediction_curves(cache_dir)
    if not cur:
        print("[figs_v2] prediction: no held-out models; skipped")
        return None
    n = len(cur)
    ncol = 4 if n > 3 else n
    nrow = int(math.ceil(n / ncol))
    fig, axes = plt.subplots(nrow, ncol, figsize=size, squeeze=False, sharex=True, sharey=True)
    fig.subplots_adjust(left=0.065, right=0.99, top=0.80, bottom=0.15, wspace=0.10, hspace=0.45)
    x = 100 * F_GRID
    nums = {}
    for ax, (design, c) in zip(axes.flat, cur.items()):
        ax.axvline(5, color=AXIS, lw=1.0, zorder=1)
        ax.grid(True, axis="y", zorder=0)
        for key, _, col, lw in SERIES[::-1]:
            ax.plot(x, 100 * np.asarray(c["curves"][key]), color=col, lw=lw, zorder=3 if key == "model" else 2)
        m5 = _at(c["curves"]["model"])
        ax.plot([5], [100 * m5], marker="o", ms=8, color=GREEN, mec=SURFACE, mew=2, zorder=4)
        ax.text(6.0, 100 * m5 - 5, f"{pct(m5)}", fontsize=FS, color=INK, va="top", ha="left", zorder=5)
        ax.set_title(f"{c['label']}  ({c['pos']:,} violators)", fontsize=FS)
        ax.set_xlim(0, 20)
        ax.set_ylim(0, 104)
        ax.set_xticks([0, 5, 10, 20])
        ax.set_yticks([0, 50, 100])
        nums[design] = {"model": m5, "r8": _at(c["curves"]["r8"]), "est": _at(c["curves"]["est"]),
                        "n": c["n"], "pos": c["pos"], "runs": c["runs"], "model_file": c["model"]}
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    # legend row (identity by line color + direct label of the 5% point)
    fig.text(0.012, 0.975, "Share of signoff violators caught vs share of nets flagged, on designs the model never saw",
             fontsize=FS + 1, fontweight="semibold", color=INK, va="top")
    lx = 0.012
    for key, lab, col, lw in SERIES:
        fig.add_artist(plt.Line2D([lx, lx + 0.025], [0.885, 0.885], color=col, lw=lw + 0.6, transform=fig.transFigure))
        t = fig.text(lx + 0.031, 0.885, lab, fontsize=FS, color=INK2, va="center")
        lx += 0.031 + 0.0095 * len(lab) + 0.03
    fig.text(0.53, 0.055, "Nets flagged (% of signal nets); vertical line = 5% budget", ha="center", color=INK2, fontsize=FS)
    fig.text(0.012, 0.47, "Violators caught (%)", rotation=90, va="center", color=INK2, fontsize=FS)
    fig.text(0.012, 0.005, "Each design scored by a model trained without it (v3: PicoRV32, AES; v4: others); ranked over all of that design's runs. "
             "Dot = model at 5%.", fontsize=FS - 2, color=MUTED, va="bottom")
    return save(fig, out_dir, name, nums)


def fig_prediction_summary(out_dir, cache_dir, size=(5.6, 4.4), name="prediction_summary"):
    """Dot plot: violators caught when 5% of nets are flagged, per held-out design."""
    cur = prediction_curves(cache_dir)
    if not cur:
        print("[figs_v2] prediction-summary: no held-out models; skipped")
        return None
    rows = [(c["label"], _at(c["curves"]["model"]), _at(c["curves"]["r8"]), _at(c["curves"]["est"]), c["pos"]) for c in cur.values()]
    rows.sort(key=lambda r: r[1])
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0.25, 0.20, 0.71, 0.62])
    ys = np.arange(len(rows))
    for i, (lab, m, r8, e, pos) in enumerate(rows):
        ax.plot([min(m, r8, e) * 100, max(m, r8, e) * 100], [i, i], color=AXIS, lw=1.0, zorder=1)
        ax.plot(e * 100, i, "o", ms=9, color=GREY, mec=SURFACE, mew=2, zorder=2)
        ax.plot(r8 * 100, i, "s", ms=9, color=BLUE, mec=SURFACE, mew=2, zorder=3)
        ax.plot(m * 100, i, "*", ms=17, color=GREEN, mec=SURFACE, mew=1.5, zorder=4)
    ax.set_yticks(ys)
    ax.set_yticklabels([r[0] for r in rows])
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(0, 103)
    ax.set_xticks([0, 25, 50, 75, 100])
    ax.set_xticklabels(["0", "25", "50", "75", "100%"])
    ax.grid(True, axis="x", zorder=0)
    ax.spines["left"].set_visible(False)
    ax.set_xlabel("Signoff violators caught when 5% of nets are flagged", labelpad=4)
    ax.set_ylim(-0.6, len(rows) - 0.4)
    # legend (shape + color + label)
    items = [("*", GREEN, 15, "BeforeRoute model"), ("s", BLUE, 9, "Rule R8"), ("o", GREY, 9, "Estimate")]
    lx = 0.02
    for mk, col, ms, lab in items:
        fig.add_artist(plt.Line2D([lx + 0.012], [0.93], marker=mk, ms=ms, color=col, mec=SURFACE, lw=0, transform=fig.transFigure))
        fig.text(lx + 0.035, 0.93, lab, fontsize=FS, color=INK2, va="center")
        lx += 0.035 + 0.0205 * len(lab) + 0.04
    ms_ = [r[1] for r in rows]
    fig.text(0.012, 0.012, f"{len(rows)} held-out designs, each scored by a model that never saw it.",
             fontsize=FS - 2, color=MUTED, va="bottom")
    nums = {r[0]: {"model": r[1], "r8": r[2], "est": r[3], "violators": r[4]} for r in rows}
    nums["_range_model"] = [min(ms_), max(ms_)]
    return save(fig, out_dir, name, nums)


# ================================================================ (c) intervention Pareto
def _pareto_axes(ax, hs, big=False, annotate=True):
    base = hs["base"]
    arms = arms_table(hs)
    b = arms.get("base")
    if b is None:
        ax.text(0.5, 0.5, f"{base}: no baseline yet", transform=ax.transAxes, ha="center", color=MUTED)
        return {}
    yb, hb = b["signoff_violating_data_nets"], b.get("hold_ws")

    def hold_kept(r):
        return (r.get("hold_ws") / hb) if (hb and r.get("hold_ws") is not None) else None

    uni = sorted([(int(a[3:]), cells_changed(r), r["signoff_violating_data_nets"], hold_kept(r))
                  for a, r in arms.items() if classify(a) == "uniform" and cells_changed(r) is not None and a[3:].isdigit()])
    top5, thr, rule = pick(arms, "top5"), pick(arms, "thr"), pick(arms, "rule")
    named = {x for x in (top5, thr, rule) if x}
    others = [(a, r) for a, r in arms.items() if classify(a) in ("model", "tiered", "rule") and a not in named and cells_changed(r) is not None]
    ms_big = 22 if big else 17
    # other policies tried (context, unlabeled)
    for a, r in others:
        mk = {"model": "*", "rule": "s", "tiered": "D"}[classify(a)]
        ax.plot(cells_changed(r), r["signoff_violating_data_nets"], mk, ms=(11 if mk == "*" else 7), mfc="none",
                mec=OTHER, mew=1.2, zorder=2)
    # uniform family: baseline -> H=30/50/70 (rose)
    ux = [0] + [u[1] for u in uni]
    uy = [yb] + [u[2] for u in uni]
    ax.plot(ux, uy, color=ROSE, lw=2.4 if big else 2.0, zorder=3)
    ax.plot([u[1] for u in uni], [u[2] for u in uni], "o", ms=9, color=ROSE, mec=SURFACE, mew=2, zorder=4)
    ax.plot([0], [yb], "o", ms=10, color=GREY, mec=SURFACE, mew=2, zorder=5)
    nums = {"baseline_violators": yb, "baseline_hold_ns": hb,
            "uniform": {f"uni{h}": {"cells": c, "violators": v, "hold_kept": k} for h, c, v, k in uni}}
    for h, c, v, k in uni:
        if h == max(u[0] for u in uni) and annotate:
            continue
        ax.annotate(f"{h}%", (c, v), xytext=(8, 6), textcoords="offset points", fontsize=FS, color=INK2, zorder=6)
    for role, a, mk, col in (("top5", top5, "*", GREEN), ("thr", thr, "*", GREEN), ("rule", rule, "s", BLUE)):
        if not a:
            continue
        r = arms[a]
        big_mk = role == "top5"
        ax.plot(cells_changed(r), r["signoff_violating_data_nets"], mk,
                ms=(ms_big if mk == "*" else 12) if big_mk or mk == "s" else ms_big - 5,
                color=col, mec=SURFACE, mew=1.5, zorder=7, mfc=col if (big_mk or mk == "s") else SURFACE)
        nums[role] = {"arm": a, "cells": cells_changed(r), "violators": r["signoff_violating_data_nets"],
                      "hold_kept": hold_kept(r), "area_delta": (r["stdcell_area"] / b["stdcell_area"] - 1) if b.get("stdcell_area") else None}
    if uni:
        h, c, v, k = uni[-1]
        nums["uniform_max"] = {"arm": f"uni{h}", "cells": c, "violators": v, "hold_kept": k}
    ax.set_xlim(left=-0.03 * max(ux + [1]))
    ax.set_ylim(-0.04 * yb, yb * 1.13)
    ax.grid(True, axis="y", zorder=0)
    ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
    return nums


def _label_block(ax, xy, head, body, xytext, ha="left", va="bottom", head_color=INK):
    t = ax.annotate(head + "\n" + body, xy, xytext=xytext, textcoords="offset points", fontsize=FS, color=INK2,
                    ha=ha, va=va, linespacing=1.2, zorder=8,
                    arrowprops=dict(arrowstyle="-", color=AXIS, lw=1.0, shrinkA=0, shrinkB=9))
    return t


def fig_pareto_hero(out_dir, base="d1-picorv32-006", size=(5.95, 4.55), name="pareto_hero"):
    hs = load_hero(base)
    if hs is None:
        print(f"[figs_v2] pareto-hero: {base} missing; skipped")
        return None
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0.13, 0.15, 0.84, 0.72])
    nums = _pareto_axes(ax, hs, big=True)
    if not nums:
        plt.close(fig)
        return None
    yb = nums["baseline_violators"]
    ax.set_xlabel("Cells changed by the repair step (resized + buffers)", labelpad=4)
    ax.set_ylabel("Signal nets violating at signoff", labelpad=4)
    ax.annotate(f"Baseline: {yb:,}", (0, yb), xytext=(12, -4), textcoords="offset points", fontsize=FS, color=INK2, va="top")
    um = nums.get("uniform_max")
    if um:
        _label_block(ax, (um["cells"], um["violators"]), f"Uniform {um['arm'][3:]}% margin, every net",
                     f"{um['violators']:,} left · {um['cells']:,} cells\nhold margin kept {pct(um['hold_kept'])}",
                     xytext=(0, 62), ha="right", va="bottom")
    t5 = nums.get("top5")
    if t5:
        _label_block(ax, (t5["cells"], t5["violators"]), "BeforeRoute: top 5% of nets at 70%",
                     f"{t5['violators']:,} left · {t5['cells']:,} cells\nhold margin kept {pct(t5['hold_kept'])}",
                     xytext=(-14, 70), ha="left", va="bottom")
    fig.text(0.012, 0.965, f"{BASE_LABEL.get(base, base)}: one post-global-route checkpoint, nine-corner signoff",
             fontsize=FS, color=INK, va="top", fontweight="semibold")
    fig.text(0.012, 0.012, "Lower-left is better. Uniform curve: 30 / 50 / 70% margin on every net. Model never saw PicoRV32.",
             fontsize=FS - 2, color=MUTED, va="bottom")
    nums["base"] = base
    return save(fig, out_dir, name, nums)


def fig_pareto_grid(out_dir, bases, name, title, size=None):
    have = [(b, load_hero(b)) for b in bases]
    have = [(b, h) for b, h in have if h is not None and "base" in arms_table(h)]
    if not have:
        print(f"[figs_v2] {name}: none of {bases} landed yet; skipped")
        return None
    n = len(have)
    ncol = min(3, n)
    nrow = int(math.ceil(n / ncol))
    size = size or (12.1, 4.5 if nrow == 1 else 7.6)
    fig, axes = plt.subplots(nrow, ncol, figsize=size, squeeze=False)
    fig.subplots_adjust(left=0.07, right=0.985, top=0.80 if nrow == 1 else 0.87, bottom=0.17 if nrow == 1 else 0.10,
                        wspace=0.22, hspace=0.50)
    nums = {}
    for ax, (b, hs) in zip(axes.flat, have):
        nb = _pareto_axes(ax, hs, big=False)
        ax.set_title(f"{BASE_LABEL.get(b, b)} · baseline {nb.get('baseline_violators', 0):,}", fontsize=FS)
        um, t5, th, ru = nb.get("uniform_max"), nb.get("top5"), nb.get("thr"), nb.get("rule")
        if um:
            ax.annotate(f"{um['violators']:,} · hold {pct(um['hold_kept'])}", (um["cells"], um["violators"]),
                        xytext=(0, 18), textcoords="offset points", ha="right", fontsize=FS, color=INK2, zorder=8)
        if t5:
            ax.annotate(f"{t5['violators']:,} · hold {pct(t5['hold_kept'])}", (t5["cells"], t5["violators"]),
                        xytext=(10, 22), textcoords="offset points", ha="left", fontsize=FS, color=INK, zorder=8,
                        arrowprops=dict(arrowstyle="-", color=AXIS, lw=1.0, shrinkB=8))
        if th and (not t5 or abs(th["cells"] - t5["cells"]) > 0 or th["violators"] != t5["violators"]):
            ax.annotate(f"p≥0.5: {th['violators']:,} · hold {pct(th['hold_kept'])}", (th["cells"], th["violators"]),
                        xytext=(10, 58), textcoords="offset points", ha="left", fontsize=FS, color=INK2, zorder=8,
                        arrowprops=dict(arrowstyle="-", color=AXIS, lw=1.0, shrinkB=8))
        if ru:
            ax.annotate(f"R8: {ru['violators']:,} · hold {pct(ru['hold_kept'])}", (ru["cells"], ru["violators"]),
                        xytext=(10, -26), textcoords="offset points", ha="left", fontsize=FS, color=INK2, zorder=8,
                        arrowprops=dict(arrowstyle="-", color=AXIS, lw=1.0, shrinkB=8))
        nums[b] = nb
    for ax in list(axes.flat)[n:]:
        ax.set_visible(False)
    fig.text(0.012, 0.975, title, fontsize=FS + 1, fontweight="semibold", color=INK, va="top")
    # legend row: shape + color + label
    items = [("o", GREY, 10, "baseline", None), ("o", ROSE, 9, "uniform margin 30/50/70%", ROSE),
             ("*", GREEN, 16, "BeforeRoute top 5% @70% (filled), p≥0.5 (open)", None),
             ("s", BLUE, 10, "rule R8 top 5%", None), ("*", OTHER, 11, "other policies tried", None)]
    lx, ly = 0.012, (0.895 if nrow == 1 else 0.925)
    for mk, col, ms, lab, line in items:
        if line:
            fig.add_artist(plt.Line2D([lx, lx + 0.024], [ly, ly], color=line, lw=2, transform=fig.transFigure))
        fig.add_artist(plt.Line2D([lx + 0.012], [ly], marker=mk, ms=ms, color=col, mec=SURFACE if col != OTHER else OTHER,
                                  mfc=col if col != OTHER else "none", lw=0, transform=fig.transFigure))
        fig.text(lx + 0.03, ly, lab, fontsize=FS, color=INK2, va="center")
        lx += 0.03 + 0.0093 * len(lab) + 0.022
    fig.text(0.5, 0.012 if nrow > 1 else 0.035, "Cells changed by the repair step (resized + buffers)", ha="center",
             color=INK2, fontsize=FS)
    fig.text(0.008, 0.5, "Signal nets violating at signoff", rotation=90, va="center", color=INK2, fontsize=FS)
    return save(fig, out_dir, name, nums)


# ================================================================ (d) pipeline diagram
def fig_pipeline(out_dir, size=(12.1, 2.55), name="pipeline"):
    W, H = size
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, W)
    ax.set_ylim(0, H)
    ax.axis("off")
    y0, h = 1.62, 0.78          # main row
    stages = ["Synthesis", "Floorplan\n+ place", "CTS", "Global\nroute", "BR", "Detailed\nroute", "RC\nextraction", "9-corner\nsignoff"]
    widths = [1.18, 1.18, 0.82, 1.08, 1.55, 1.12, 1.18, 1.18]
    gap = (W - 0.06 - sum(widths)) / (len(stages) - 1)
    x = 0.03
    boxes = {}
    for s, w in zip(stages, widths):
        if s == "BR":
            ax.add_patch(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0,rounding_size=0.10", fc="#14240a", ec=BRAND, lw=2.2, zorder=3))
            ax.text(x + w / 2, y0 + h / 2, "BeforeRoute", ha="center", va="center", fontsize=FS + 1, fontweight="semibold", color=INK, zorder=4)
        else:
            ax.add_patch(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0,rounding_size=0.10", fc="#121212", ec="#5a5a5a", lw=1.2, zorder=3))
            ax.text(x + w / 2, y0 + h / 2, s, ha="center", va="center", fontsize=FS, color="#e6e6e6", linespacing=1.1, zorder=4)
        boxes[s] = (x, w)
        x += w + gap
    names = list(boxes)
    for a, b in zip(names[:-1], names[1:]):
        xa = boxes[a][0] + boxes[a][1]
        xb = boxes[b][0]
        ax.add_patch(FancyArrowPatch((xa + 0.03, y0 + h / 2), (xb - 0.03, y0 + h / 2), arrowstyle="-|>", mutation_scale=14,
                                     color="#7a7a7a", lw=1.4, zorder=2))
    # expanded BeforeRoute panel (zoom-in)
    bx, bw = boxes["BR"]
    px0, px1, py0, py1 = 2.35, 9.65, 0.12, 0.98
    ax.add_patch(FancyBboxPatch((px0, py0), px1 - px0, py1 - py0, boxstyle="round,pad=0,rounding_size=0.12", fc="#0b1406", ec=BRAND, lw=1.4, zorder=1))
    for xa, xb in ((bx + 0.05, px0 + 0.4), (bx + bw - 0.05, px1 - 0.4)):
        ax.plot([xa, xb], [y0, py1], color=BRAND, lw=1.0, alpha=0.8, zorder=1)
    steps = [("1", "Score every net", "LightGBM on post-GRT features"),
             ("2", "Mask the rest", "do-not-touch on ~95% of nets"),
             ("3", "Stock repair_design", "70% margin, flagged nets only")]
    sw = (px1 - px0 - 0.5) / 3
    for i, (num, head, sub) in enumerate(steps):
        sx = px0 + 0.25 + i * sw
        ax.text(sx + 0.05, py1 - 0.17, num, ha="left", va="top", fontsize=FS + 4, fontweight="semibold", color=BRAND, zorder=4)
        ax.text(sx + 0.38, py1 - 0.17, head, ha="left", va="top", fontsize=FS, fontweight="semibold", color=INK, zorder=4)
        ax.text(sx + 0.38, py1 - 0.47, sub, ha="left", va="top", fontsize=FS, color=INK2, zorder=4)
        if i < 2:
            ax.add_patch(FancyArrowPatch((sx + sw - 0.17, py0 + 0.43), (sx + sw + 0.02, py0 + 0.43), arrowstyle="-|>", mutation_scale=12,
                                         color=BRAND, lw=1.2, zorder=4))
    # feedback loop: signoff reports -> labels -> retrain (back into step 1)
    sx_, sw_ = boxes["9-corner\nsignoff"]
    loop = FancyArrowPatch((sx_ + sw_ / 2, y0 - 0.02), (px1 + 0.02, (py0 + py1) / 2), connectionstyle="angle,angleA=-90,angleB=0,rad=12",
                           arrowstyle="-|>", mutation_scale=15, color=BRAND, lw=1.8, zorder=2)
    ax.add_patch(loop)
    ax.text(px1 + 0.15, (py0 + py1) / 2 - 0.07, "signoff reports become\ntraining labels", ha="left", va="top",
            fontsize=FS, color=INK2, linespacing=1.1, zorder=4)
    return save(fig, out_dir, name, {"stages": [s.replace("\n", " ") for s in stages]})


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
    ax = fig.add_axes([0.13, 0.17, 0.84, 0.68])
    ax.set_xlabel("Route + extract + signoff passes", labelpad=4)
    ax.set_ylabel("Signal nets violating at signoff", labelpad=4)
    ax.grid(True, axis="y", zorder=0)
    if not found:
        ax.set_xlim(-0.2, 3.4)
        ax.set_ylim(0, 1)
        ax.set_xticks([0, 1, 2, 3])
        ax.set_yticks([])
        ax.text(0.5, 0.55, "TBD-R3", transform=ax.transAxes, ha="center", va="center", fontsize=FS + 14, fontweight="semibold", color="#5a5a5a")
        ax.text(0.5, 0.36, "signoff-guided loop arms (lst-sgl*, lst-cln1)\nnot yet in any hero_summary.json", transform=ax.transAxes,
                ha="center", va="center", fontsize=FS, color=MUTED, linespacing=1.2)
        fig.text(0.012, 0.965, "Iterations to closure: placeholder", fontsize=FS, fontweight="semibold", color=INK, va="top")
        return save(fig, out_dir, name, {"placeholder": True})
    b, arms, loop = found[0]
    base = arms["base"]
    yb = base["signoff_violating_data_nets"]
    nums = {"base": b, "baseline": yb}
    lx = [0] + [k for k, _ in loop]
    ly = [yb] + [r["signoff_violating_data_nets"] for _, r in loop]
    ax.plot(lx, ly, color=LOOP, lw=2.0, marker="o", ms=9, mfc=SURFACE, mec=LOOP, mew=2, zorder=3)
    ax.annotate("signoff-guided loop", (lx[-1], ly[-1]), xytext=(8, 4), textcoords="offset points", fontsize=FS, color=INK2)
    nums["loop"] = list(zip(lx, ly))
    t5 = pick(arms, "top5")
    if t5:
        bx_, by_ = [0, 1], [yb, arms[t5]["signoff_violating_data_nets"]]
        if "lst-cln1-70" in arms:
            bx_.append(2)
            by_.append(arms["lst-cln1-70"]["signoff_violating_data_nets"])
        ax.plot(bx_, by_, color=GREEN, lw=2.6, zorder=4)
        ax.plot(bx_[1:], by_[1:], "*", ms=17, color=GREEN, mec=SURFACE, mew=1.5, zorder=5)
        ax.annotate("BeforeRoute" + (" + cleanup" if len(bx_) > 2 else ""), (bx_[-1], by_[-1]), xytext=(8, -14),
                    textcoords="offset points", fontsize=FS, color=INK2)
        nums["beforeroute"] = list(zip(bx_, by_))
    if "uni70" in arms:
        ux_, uy_ = [0, 1], [yb, arms["uni70"]["signoff_violating_data_nets"]]
        ax.plot(ux_, uy_, color=ROSE, lw=2.0, marker="o", ms=9, mec=SURFACE, mew=2, zorder=3)
        ax.annotate("uniform 70%", (1, uy_[-1]), xytext=(8, 10), textcoords="offset points", fontsize=FS, color=INK2)
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
    out = a.out if os.path.isabs(a.out) else os.path.join(os.getcwd(), a.out)
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
                           fig_pareto_grid(out, ROUND3, "pareto_round3", "Round 3: six new design families (model never saw them)"),
                           fig_pareto_grid(out, EXPLORATORY, "pareto_exploratory", "Exploratory base (Round 0)", size=(5.95, 4.6))],
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
