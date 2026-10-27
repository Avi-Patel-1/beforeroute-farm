#!/usr/bin/env python3
"""Tables + figures from collected learning-curve / ablation-ladder outputs.

Usage: analysis_report.py [--lc results/analysis/lc] [--ablation results/analysis/ablation] --out <dir> [--label TEXT]

Inputs are directories written by farm/analysis_collect.py (merged CSVs at the top level) or any tree of
per-cell output dirs (CSVs are then concatenated recursively). Writes to <out>:
  lc_summary.csv, ablation_summary.csv          seed-averaged / per-rung summaries
  tables.md                                     per-design tables (pooled; per-run median [IQR])
  learning_curve.png, ablation_ladder.png       figures (light theme)
"""
from __future__ import annotations

import argparse
import glob
import os

import numpy as np
import pandas as pd

INK, INK2, GRID, SURF = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
BLUE = "#2a78d6"
RULE_GRAYS = {"est_slew": "#b9b8b2", "rule_R8": "#7a7973"}
LEARNED_RAMP = {"logreg_calibrated_estimate": "#86b6ef", "lgbm_estimate_only": "#5598e7",
                "lgbm_no_geometry": "#2a78d6", "lgbm_full": "#1c5cab"}
RUNG_LABEL = {"random": "random", "est_slew": "raw slew estimate", "rule_R8": "rule R8",
              "logreg_calibrated_estimate": "logistic calib. (linear)", "lgbm_estimate_only": "GBM, estimate only",
              "lgbm_no_geometry": "GBM, no geometry", "lgbm_full": "GBM, full features"}


def load_csv(d: str | None, name: str) -> pd.DataFrame:
    if not d or not os.path.isdir(d):
        return pd.DataFrame()
    top = os.path.join(d, name)
    if os.path.exists(top):
        return pd.read_csv(top)
    parts = [pd.read_csv(p) for p in sorted(glob.glob(os.path.join(d, "**", name), recursive=True)) if os.path.getsize(p) > 1]
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def n_key(v) -> float:
    return 1e9 if str(v) == "all" else float(v)


def fmt(x, nd=3):
    return "-" if x is None or (isinstance(x, float) and np.isnan(x)) else f"{x:.{nd}f}"


def iqr(r, base):
    return f"{fmt(r[f'{base}_med'])} [{fmt(r[f'{base}_q25'], 2)}-{fmt(r[f'{base}_q75'], 2)}]"


def summarize_lc(lc: pd.DataFrame) -> pd.DataFrame:
    lc = (lc[lc["skipped"].isna()] if "skipped" in lc.columns else lc).copy()
    keys = ["variant", "holdout", "n"]
    lc["n"] = lc["n"].astype(str)
    num = [c for c in lc.columns if c not in keys + ["_index", "train_designs", "in_design_runs", "seed", "skipped"]
           and pd.api.types.is_numeric_dtype(lc[c])]
    g = lc.groupby(keys)
    s = g[num].mean()
    s["seeds"] = g.size()
    for m in ("pooled_recall5", "pooled_catch95", "pooled_prauc"):
        s[m + "_min"] = g[m].min()
        s[m + "_max"] = g[m].max()
    s = s.reset_index()
    s["nk"] = s["n"].map(n_key)
    return s.sort_values(["variant", "holdout", "nk"]).drop(columns="nk")


def lc_tables(s: pd.DataFrame) -> str:
    out = []
    for variant, title in (("runs", "Learning curve - N random runs from other designs (3 seeds; mean, [min-max] over seeds)"),
                           ("designs", "Learning curve - all runs of K random other designs (3 seeds)"),
                           ("within", "Within-project flywheel - all other designs + k runs of the held-out design; test = its remaining runs (paired across k)")):
        v = s[s["variant"] == variant]
        if v.empty:
            continue
        out.append(f"\n### {title}\n")
        cal = variant == "within"
        hdr = ("| design | N | train runs | train designs | R@5% pooled | catch-95 pooled | PR-AUC pooled | R@5% per-run med [IQR] | catch-95 per-run med [IQR]"
               + (" | count calib. err med [IQR] | sum p / actual med |" if cal else " |") + " R8 R@5% / catch-95 (same runs) |")
        out.append(hdr)
        out.append("|" + "---|" * (hdr.count("|") - 1))
        for _, r in v.iterrows():
            line = (f"| {r['holdout']} | {r['n']} | {r['n_train_runs']:.0f} | {r['n_train_designs']:.1f} | "
                    f"{fmt(r['pooled_recall5'])} [{fmt(r['pooled_recall5_min'], 2)}-{fmt(r['pooled_recall5_max'], 2)}] | "
                    f"{fmt(r['pooled_catch95'])} [{fmt(r['pooled_catch95_min'], 2)}-{fmt(r['pooled_catch95_max'], 2)}] | "
                    f"{fmt(r['pooled_prauc'])} | {iqr(r, 'run_recall5')} | {iqr(r, 'run_catch95')} |")
            if cal:
                line += f" {iqr(r, 'run_calerr')} | {fmt(r.get('run_sumratio_med'), 2)} |"
            line += f" {fmt(r.get('r8_pooled_recall5'))} / {fmt(r.get('r8_pooled_catch95'))} |"
            out.append(line)
    return "\n".join(out)


def ablation_tables(ab: pd.DataFrame) -> str:
    out = ["\n### Ablation ladder - leave-one-design-out, signal nets (pooled over the design's runs; per-run median [IQR])\n"]
    hdr = "| design | viol. rate (catch-95 floor = 0.95x) | rung | R@5% pooled | catch-95 pooled | PR-AUC pooled | R@5% per-run med [IQR] | catch-95 per-run med [IQR] | count calib. err med |"
    out += [hdr, "|" + "---|" * (hdr.count("|") - 1)]
    nc, pc = ("eval_n", "eval_pos") if "eval_n" in ab.columns else ("n", "pos")
    for _, r in ab.iterrows():
        out.append(f"| {r['holdout']} ({r['n_eval_runs']:.0f} runs) | {r[pc] / r[nc]:.2%} | {r['rung']} {RUNG_LABEL.get(r['rung_name'], r['rung_name'])} | "
                   f"{fmt(r['pooled_recall5'])} | {fmt(r['pooled_catch95'])} | {fmt(r['pooled_prauc'])} | "
                   f"{iqr(r, 'run_recall5')} | {iqr(r, 'run_catch95')} | {fmt(r.get('run_calerr_med'), 2)} |")
    # compact cross-design views
    for metric, name, better in (("pooled_recall5", "R@5% pooled (higher is better)", max),
                                 ("pooled_catch95", "fraction flagged to catch 95% pooled (lower is better)", min),
                                 ("pooled_prauc", "PR-AUC pooled", max)):
        p = ab.pivot_table(index="holdout", columns="rung", values=metric, aggfunc="first")
        p.loc["MEAN"] = p.mean()
        out.append(f"\n#### {name}\n")
        cols = list(p.columns)
        out.append("| design | " + " | ".join(f"{c} {RUNG_LABEL.get(ab[ab['rung'] == c]['rung_name'].iloc[0], '')}" for c in cols) + " |")
        out.append("|" + "---|" * (len(cols) + 1))
        for idx, row in p.iterrows():
            out.append(f"| {idx} | " + " | ".join(fmt(row[c]) for c in cols) + " |")
    return "\n".join(out)


def paired_table(runs: pd.DataFrame) -> str:
    """Per-run paired comparison of rungs on the same runs (runs with >= 1 violator)."""
    if runs.empty:
        return ""
    runs = runs[runs["positives"] > 0]
    pairs = [("lgbm_full", "logreg_calibrated_estimate"), ("lgbm_full", "est_slew"), ("lgbm_full", "rule_R8"),
             ("lgbm_estimate_only", "logreg_calibrated_estimate"), ("lgbm_full", "lgbm_estimate_only")]
    out = ["\n### Paired per-run comparison (same runs): median per-run difference in catch-95 (B - A; > 0 means A flags less) "
           "and share of runs where A needs fewer flags (ties excluded)\n"]
    hdr = "| design | runs | " + " | ".join(f"{RUNG_LABEL[a]} vs {RUNG_LABEL[b]}" for a, b in pairs) + " |"
    out += [hdr, "|" + "---|" * (len(pairs) + 2)]
    piv = runs.pivot_table(index=["holdout", "run"], columns="rung_name", values="frac_to_catch_95", aggfunc="first")
    tot = {p: [] for p in pairs}
    for d, g in piv.groupby(level=0):
        cells = []
        for a, b in pairs:
            if a not in g or b not in g:
                cells.append("-")
                continue
            diff = (g[b] - g[a]).dropna()
            if diff.empty:
                cells.append("-")
                continue
            tot[(a, b)].append(diff)
            nz = diff[diff != 0]
            win = (nz > 0).mean() if len(nz) else float("nan")
            cells.append(f"{diff.median():+.4f} ({win:.0%})")
        out.append(f"| {d} | {len(g)} | " + " | ".join(cells) + " |")
    cells = []
    for p in pairs:
        if tot[p]:
            allv = pd.concat(tot[p])
            nz = allv[allv != 0]
            cells.append(f"{allv.median():+.4f} ({(nz > 0).mean():.0%})")
        else:
            cells.append("-")
    out.append(f"| ALL runs | {len(piv)} | " + " | ".join(cells) + " |")
    return "\n".join(out)

VARIANT_TEXT = {"runs": "other-design runs", "designs": "other designs (all their runs)",
                "within": "same-design runs on top of all other designs", "self": "same-design runs only"}


def load_lc_runs(dirs) -> pd.DataFrame:
    """Per-run learning-curve rows with the training size in 'n' and the run's net count in 'n_nets'. Outputs written
    before the n/n_nets fix carry the net count in 'n'; their sizes are rebuilt from the record order in learning_curve.json."""
    import json

    parts = []
    for d in dirs:
        for jp in sorted(glob.glob(os.path.join(d, "**", "learning_curve.json"), recursive=True)):
            cp = os.path.join(os.path.dirname(jp), "learning_curve_runs.csv")
            if not os.path.exists(cp) or os.path.getsize(cp) < 2:
                continue
            runs = pd.read_csv(cp)
            if "n_nets" not in runs.columns:
                recs = [r for r in json.load(open(jp)).get("records", []) if "model" in r and "skipped" not in r]
                sizes = [str(r["n"]) for r in recs for _ in range(int(r["model"]["n_runs"]))]
                if len(sizes) != len(runs):
                    print(f"[report] cannot rebuild sizes for {cp} ({len(sizes)} vs {len(runs)} rows); skipped")
                    continue
                runs = runs.rename(columns={"n": "n_nets"})
                runs["n"] = sizes
            runs["n"] = runs["n"].astype(str)
            parts.append(runs)
    return pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()


def lc_answer(lc: pd.DataFrame, lcr: pd.DataFrame | None = None, abr: pd.DataFrame | None = None, thr: float = 2.0) -> tuple:
    """(a) smallest training size reaching catch-95 <= 2 x floor (floor = 0.95 x violator rate), two ways:
    pooled = catch-95 pooled over the evaluation runs vs the pooled floor (one global ranking across runs);
    per-run = median over evaluation runs of catch-95 / that run's own floor (flagging the top of each run: the operating mode).
    Seed means; 'all seeds' variants in answers.json. abr (ablation per-run rows) gives per-run references for R8 / raw estimate."""
    if lc.empty:
        return "", {}
    per_run = {}
    if lcr is not None and not lcr.empty:
        r = lcr[lcr["positives"] > 0].copy()
        r["xf"] = r["frac_to_catch_95"] / (0.95 * r["positives"] / r["n_nets"])
        per_run = r.groupby(["variant", "holdout", "n", "seed"])["xf"].median().groupby(level=[0, 1, 2]).agg(["mean", "max"]).to_dict("index")
    ref_run = {}
    if abr is not None and not abr.empty:
        q = abr[abr["positives"] > 0].copy()
        q["xf"] = q["frac_to_catch_95"] / (0.95 * q["positives"] / q["n"])
        ref_run = q.groupby(["holdout", "rung_name"])["xf"].median().to_dict()
    lc = (lc[lc["skipped"].isna()] if "skipped" in lc.columns else lc).copy()
    lc["n"] = lc["n"].astype(str)
    lc["ratio"] = lc["pooled_catch95"] / (0.95 * lc["eval_pos"] / lc["eval_n"])
    lc["r8_ratio"] = lc["r8_pooled_catch95"] / (0.95 * lc["eval_pos"] / lc["eval_n"])
    lc["est_ratio"] = lc["est_slew_pooled_catch95"] / (0.95 * lc["eval_pos"] / lc["eval_n"])
    g = lc.groupby(["variant", "holdout", "n"]).agg(c95=("pooled_catch95", "mean"), ratio=("ratio", "mean"), ratio_max=("ratio", "max"),
                                                     train_runs=("n_train_runs", "mean"), r8=("r8_ratio", "mean"),
                                                     est=("est_ratio", "mean")).reset_index()
    g["nk"] = g["n"].map(n_key)
    g = g.sort_values(["variant", "holdout", "nk"])
    ans = {}

    def first(x, col):
        hit = x[x[col] <= thr]
        return None if hit.empty else str(hit.iloc[0]["n"])

    for (v, d), x in g.groupby(["variant", "holdout"]):
        x = x.copy()
        x["run_x"] = [per_run.get((v, d, n), {}).get("mean", np.nan) for n in x["n"]]
        x["run_x_max"] = [per_run.get((v, d, n), {}).get("max", np.nan) for n in x["n"]]
        ans.setdefault(d, {})[v] = {
            "pooled_n_star": first(x, "ratio"), "pooled_n_star_all_seeds": first(x, "ratio_max"),
            "per_run_n_star": first(x, "run_x"), "per_run_n_star_all_seeds": first(x, "run_x_max"),
            "curve": {r["n"]: {"catch95_pooled": round(r["c95"], 4), "pooled_x_floor": round(r["ratio"], 2),
                               "per_run_median_x_floor": None if r["run_x"] != r["run_x"] else round(r["run_x"], 2),
                               "train_runs": round(r["train_runs"], 1)} for _, r in x.iterrows()},
            "r8_pooled_x_floor": round(float(x["r8"].mean()), 2), "est_pooled_x_floor": round(float(x["est"].mean()), 2),
        }
    for d in ans:
        ans[d]["_ref_per_run_x_floor"] = {k: round(float(ref_run[(d, k)]), 2) for k in ("rule_R8", "est_slew", "lgbm_full") if (d, k) in ref_run}
    out = [f"\n### (a) Training data needed to reach catch-95 <= {thr:g}x floor (floor = 0.95 x violator rate of the evaluation runs)\n",
           "Each cell: pooled / per-run. pooled = catch-95 over all evaluation runs ranked together (one global score scale); "
           "per-run = median over runs of catch-95 / that run's floor (top-k flagging within each run, the operating mode). "
           "Smallest training size whose seed mean meets the bar; '>m' = not reached up to m; '-' = not run. "
           "x-floor columns: catch-95 / floor (pooled / per-run median).\n"]
    hdr = ("| design | rule R8 x-floor | raw estimate x-floor | GBM LODO x-floor | " +
           " | ".join(VARIANT_TEXT[v] for v in ("runs", "designs", "within", "self")) + " |")
    out += [hdr, "|" + "---|" * (hdr.count("|") - 1)]
    for d in sorted(ans):
        a = ans[d]
        cells = []
        for v in ("runs", "designs", "within", "self"):
            if v not in a:
                cells.append("-")
                continue
            mx = list(a[v]["curve"])[-1]
            cells.append(f"{a[v]['pooled_n_star'] or '>' + mx} / {a[v]['per_run_n_star'] or '>' + mx}")
        ref = next(a[v] for v in ("runs", "within", "designs", "self") if v in a)
        rr = a.get("_ref_per_run_x_floor", {})
        lodo = (a.get("runs", {}).get("curve", {}).get("all") or {}).get("pooled_x_floor")
        fmt2 = lambda v: "-" if v is None else f"{v:.2f}"
        out.append(f"| {d} | {ref['r8_pooled_x_floor']:.2f} / {fmt2(rr.get('rule_R8'))} | {ref['est_pooled_x_floor']:.2f} / {fmt2(rr.get('est_slew'))} | "
                   f"{fmt2(lodo)} / {fmt2(rr.get('lgbm_full'))} | " + " | ".join(cells) + " |")
    return "\n".join(out), ans


def ablation_verdict(ab: pd.DataFrame, runs: pd.DataFrame) -> tuple:
    """(b) GBM (full) vs raw estimate and rule R8 at the operating budget, pooled and paired per run (sign test)."""
    from scipy.stats import binomtest

    if ab.empty or runs.empty:
        return "", {}
    runs = runs[runs["positives"] > 0]
    piv = {m: runs.pivot_table(index=["holdout", "run"], columns="rung_name", values=m, aggfunc="first")
           for m in ("recall@5%", "frac_to_catch_95")}

    def paired(sub_r, sub_c, base):
        res = {}
        for m, sub, sign in (("recall5", sub_r, 1), ("catch95", sub_c, -1)):
            if base not in sub or "lgbm_full" not in sub:
                continue
            dlt = (sign * (sub["lgbm_full"] - sub[base])).dropna()
            w, l_ = int((dlt > 1e-12).sum()), int((dlt < -1e-12).sum())
            t = int(len(dlt) - w - l_)
            p = binomtest(w, w + l_, 0.5).pvalue if w + l_ else float("nan")
            res[m] = {"W": w, "T": t, "L": l_, "p": p, "median_delta": float(dlt.median()) if len(dlt) else float("nan")}
        return res

    nc, pc = ("eval_n", "eval_pos") if "eval_n" in ab.columns else ("n", "pos")
    ver = {}
    out = ["\n### (b) Ablation verdict: GBM (full features) vs raw slew estimate and rule R8 at the operating budget\n",
           "Pooled over the held-out design's runs; paired = per run (runs with >= 1 violator), W-T-L = GBM better / tie / worse, "
           "p = two-sided sign test.\n"]
    hdr = ("| design | runs | viol. rate | R@5% GBM / est / R8 | catch-95 GBM / est / R8 (floor) | paired R@5% vs est | vs R8 | "
           "paired catch-95 vs est | vs R8 |")
    out += [hdr, "|" + "---|" * (hdr.count("|") - 1)]

    def cell(r):
        return f"{r['W']}-{r['T']}-{r['L']} (p={r['p']:.2g})" if r else "-"

    designs = sorted(ab["holdout"].unique())
    for d in designs + ["ALL"]:
        if d == "ALL":
            sr, sc = piv["recall@5%"], piv["frac_to_catch_95"]
            row = "| ALL designs | " + str(len(sc)) + " | | | |"
        else:
            x = ab[ab["holdout"] == d].set_index("rung_name")
            if "lgbm_full" not in x.index:
                continue
            sr = piv["recall@5%"].xs(d, level=0) if d in piv["recall@5%"].index.get_level_values(0) else pd.DataFrame()
            sc = piv["frac_to_catch_95"].xs(d, level=0) if d in piv["frac_to_catch_95"].index.get_level_values(0) else pd.DataFrame()
            rate = float(x[pc].iloc[0] / x[nc].iloc[0])
            g = lambda r, m: x.loc[r, m] if r in x.index else float("nan")
            row = (f"| {d} | {int(x['n_eval_runs'].iloc[0])} | {rate:.2%} | "
                   f"{g('lgbm_full', 'pooled_recall5'):.3f} / {g('est_slew', 'pooled_recall5'):.3f} / {g('rule_R8', 'pooled_recall5'):.3f} | "
                   f"{g('lgbm_full', 'pooled_catch95'):.3f} / {g('est_slew', 'pooled_catch95'):.3f} / {g('rule_R8', 'pooled_catch95'):.3f} ({0.95 * rate:.3f}) |")
            ver[d] = {"rate": rate, **{f"{r}_{m}": float(g(r, f"pooled_{m}")) for r in ("lgbm_full", "est_slew", "rule_R8", "logreg_calibrated_estimate")
                                      for m in ("recall5", "catch95")}}
        pe, pr = paired(sr, sc, "est_slew"), paired(sr, sc, "rule_R8")
        ver.setdefault(d, {}).update({"paired_vs_est": pe, "paired_vs_R8": pr})
        out.append(row + f" {cell(pe.get('recall5'))} | {cell(pr.get('recall5'))} | {cell(pe.get('catch95'))} | {cell(pr.get('catch95'))} |")
    return "\n".join(out), ver


def style(ax):
    ax.set_facecolor(SURF)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color(GRID)
    ax.tick_params(colors=INK2, labelsize=8, length=0)
    ax.grid(True, axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)


def fig_learning_curve(lcr: pd.DataFrame, abr: pd.DataFrame, path: str, label: str) -> None:
    """Per held-out design: per-run median recall@5% and catch-95 / floor vs number of training runs, for
    'N runs of other designs' (runs variant) and 'k runs of the same design only' (self variant)."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D

    if lcr is None or lcr.empty:
        return
    r = lcr[(lcr["positives"] > 0) & lcr["variant"].isin(["runs", "self"])].copy()
    if r.empty:
        return
    r["xf"] = r["frac_to_catch_95"] / (0.95 * r["positives"] / r["n_nets"])
    per = r.groupby(["variant", "holdout", "n", "seed"]).agg(rec=("recall@5%", "median"), rec25=("recall@5%", lambda v: v.quantile(0.25)),
                                                            rec75=("recall@5%", lambda v: v.quantile(0.75)), xf=("xf", "median"),
                                                            xf25=("xf", lambda v: v.quantile(0.25)), xf75=("xf", lambda v: v.quantile(0.75)))
    per = per.groupby(level=[0, 1, 2]).mean().reset_index()
    # x position = number of training runs (runs: N, or the pool size for 'all'; self: k)
    if "n_train_runs" in lcr.columns:
        pass
    ref = {}
    if abr is not None and not abr.empty:
        q = abr[abr["positives"] > 0].copy()
        q["xf"] = q["frac_to_catch_95"] / (0.95 * q["positives"] / q["n"])
        ref = q.groupby(["holdout", "rung_name"]).agg(rec=("recall@5%", "median"), xf=("xf", "median")).to_dict("index")
    designs = [d for d in ["picorv32", "aes_cipher_top", "salsa20", "sha512", "y_huff", "des"] if d in set(per["holdout"])]
    if not designs:
        return
    colors = {"runs": BLUE, "self": "#eb6834"}
    fig, axes = plt.subplots(2, len(designs), figsize=(2.25 * len(designs) + 0.7, 5.2), sharex=True, facecolor=SURF)
    axes = np.atleast_2d(axes).reshape(2, len(designs))
    xmax = 2
    for j, d in enumerate(designs):
        for v in ("runs", "self"):
            g = per[(per["holdout"] == d) & (per["variant"] == v)].copy()
            if g.empty:
                continue
            pool = lcr[(lcr["variant"] == v) & (lcr["holdout"] == d)]
            allx = float(pool["_pool_runs"].iloc[0]) if "_pool_runs" in pool.columns and len(pool) else 256.0
            g["x"] = [allx if n == "all" else float(n) for n in g["n"]]
            g = g.sort_values("x")
            xmax = max(xmax, g["x"].max())
            for i, (m, lo, hi) in enumerate((("rec", "rec25", "rec75"), ("xf", "xf25", "xf75"))):
                ax = axes[i, j]
                ax.fill_between(g["x"], g[lo], g[hi], color=colors[v], alpha=0.13, linewidth=0)
                ax.plot(g["x"], g[m], color=colors[v], linewidth=1.6, marker="o", markersize=4, markeredgecolor=SURF, markeredgewidth=1)
        for i in range(2):
            ax = axes[i, j]
            style(ax)
            ax.set_xscale("log", base=2)
            rr = ref.get((d, "rule_R8"))
            if rr:
                ax.axhline(rr["rec" if i == 0 else "xf"], color=RULE_GRAYS["rule_R8"], linewidth=1.2, linestyle=(0, (4, 3)))
            if i == 1:
                ax.axhline(2.0, color=INK, linewidth=1.0, linestyle=(0, (1, 1.5)))
                ax.set_ylim(0.8, max(3.2, min(8.0, ax.get_ylim()[1])))
                ax.set_xlabel("training runs", fontsize=8, color=INK2)
            else:
                ax.set_ylim(min(0.6, ax.get_ylim()[0]), 1.01)
                ax.set_title(d, fontsize=9.5, color=INK, pad=6)
            if j == 0:
                ax.set_ylabel("recall at 5% flagged\n(per-run median)" if i == 0 else "catch-95 / floor\n(per-run median)", fontsize=8.5, color=INK2)
    xt = [t for t in (1, 4, 16, 64, 256) if t <= xmax * 1.01]
    for ax in axes[1]:
        ax.set_xticks(xt)
        ax.set_xticklabels([str(t) for t in xt])
    handles = [Line2D([], [], color=BLUE, linewidth=1.6, marker="o", markersize=4, label="GBM on N runs of OTHER designs (last point = all)"),
               Line2D([], [], color=colors["self"], linewidth=1.6, marker="o", markersize=4, label="GBM on k runs of the SAME design only"),
               Line2D([], [], color=RULE_GRAYS["rule_R8"], linewidth=1.2, linestyle=(0, (4, 3)), label="rule R8 (no training)"),
               Line2D([], [], color=INK, linewidth=1.0, linestyle=(0, (1, 1.5)), label="2x floor")]
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False, fontsize=8, bbox_to_anchor=(0.5, 0.995))
    fig.text(0.5, 0.004, "Held-out design per column; lines = seed mean of the per-run median, bands = per-run IQR; "
             f"floor = 0.95 x the run's violator rate.\n{label}", ha="center", va="bottom", fontsize=7.2, color=INK2)
    fig.tight_layout(rect=(0, 0.05, 1, 0.93))
    fig.savefig(path, dpi=170, facecolor=SURF)
    plt.close(fig)


def fig_ablation(ab: pd.DataFrame, path: str, label: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    from matplotlib.patches import Patch

    rungs = [r for r in ["est_slew", "rule_R8", "logreg_calibrated_estimate", "lgbm_estimate_only", "lgbm_no_geometry", "lgbm_full"]
             if r in set(ab["rung_name"])]
    colors = {**RULE_GRAYS, **LEARNED_RAMP}
    nc, pc = ("eval_n", "eval_pos") if "eval_n" in ab.columns else ("n", "pos")
    full = ab[ab["rung_name"] == "lgbm_full"]
    order = full.sort_values(pc, ascending=False)["holdout"].tolist() or sorted(ab["holdout"].unique())
    rate = {d: float(ab[ab["holdout"] == d][pc].iloc[0] / ab[ab["holdout"] == d][nc].iloc[0]) for d in order}
    fig, axes = plt.subplots(2, 1, figsize=(11.5, 6.4), sharex=True, facecolor=SURF)
    w = 0.8 / len(rungs)
    xs = np.arange(len(order))
    vals_c = ab[ab["rung_name"].isin(rungs)]["pooled_catch95"].dropna()
    med = float(vals_c.median()) if len(vals_c) else 0.1
    cap = float(max(0.12, 1.25 * vals_c[vals_c <= 3 * med].max())) if len(vals_c) else 1.0
    for i, (m, ylab) in enumerate((("pooled_recall5", "recall at 5% flagged"), ("pooled_catch95", "fraction flagged to catch 95%"))):
        ax = axes[i]
        style(ax)
        for k, r in enumerate(rungs):
            vals = np.array([ab[(ab["holdout"] == d) & (ab["rung_name"] == r)][m].mean() for d in order])
            xk = xs - 0.4 + w * (k + 0.5)
            shown = np.minimum(vals, cap) if i == 1 else vals
            ax.bar(xk, shown, width=w * 0.86, color=colors[r], linewidth=0)
            if i == 1:
                for x_, v in zip(xk, vals):
                    if v > cap:
                        ax.text(x_, cap * 1.01, f"{v:.2f}", rotation=90, ha="center", va="bottom", fontsize=6.5, color=INK, clip_on=False)
        if i == 0:
            ax.set_ylim(0, 1.0)
        else:
            ax.set_ylim(0, cap)
            for x_, d in zip(xs, order):
                ax.hlines(0.95 * rate[d], x_ - 0.42, x_ + 0.42, colors=INK, linewidth=1.0, linestyles=(0, (1, 1.5)))
        ax.set_ylabel(ylab, fontsize=8.5, color=INK2)
    rnd = ab[ab["rung_name"] == "random"]
    note = f" Random ranking: recall@5% ~{rnd['pooled_recall5'].mean():.2f}, catch-95 ~{rnd['pooled_catch95'].mean():.2f}." if len(rnd) else ""
    axes[1].set_xticks(xs)
    labs = []
    for d in order:
        n_runs = int(ab[ab["holdout"] == d]["n_eval_runs"].iloc[0])
        labs.append(f"{d}\n{n_runs} run{'s' if n_runs != 1 else ''}\n{rate[d]:.1%} viol.")
    axes[1].set_xticklabels(labs, fontsize=7.5, color=INK2)
    handles = [Patch(color=colors[r], label=RUNG_LABEL[r]) for r in rungs]
    handles.append(Line2D([], [], color=INK, linewidth=1.0, linestyle=(0, (1, 1.5)), label="floor (0.95 x violator rate)"))
    fig.legend(handles=handles, loc="upper center", ncol=len(handles), frameon=False, fontsize=7.5, bbox_to_anchor=(0.5, 0.995))
    fig.text(0.5, 0.004, f"Leave-one-design-out, signal nets, pooled over each held-out design's runs; bars above the catch-95 axis "
             f"are clipped and labeled.{note}\n{label}", ha="center", va="bottom", fontsize=7, color=INK2)
    fig.tight_layout(rect=(0, 0.045, 1, 0.94))
    fig.savefig(path, dpi=170, facecolor=SURF)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lc", default=None, help="comma list of learning-curve output dirs (merged)")
    ap.add_argument("--ablation", default=None)
    ap.add_argument("--out", required=True)
    ap.add_argument("--label", default="")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    md = [f"# Analysis tables {a.label}\n"]
    answers = {}
    lc_parts = [load_csv(d, "learning_curve.csv") for d in (a.lc or "").split(",") if d]
    lc = pd.concat([x for x in lc_parts if not x.empty], ignore_index=True) if any(not x.empty for x in lc_parts) else pd.DataFrame()
    if not lc.empty:
        lcr = load_lc_runs([d for d in (a.lc or "").split(",") if d])
        abr = load_csv(a.ablation, "ablation_runs.csv")
        txt, answers["a"] = lc_answer(lc, lcr, abr, thr=2.0)
        md.append(txt)
        txt, answers["a_strict_1.25x"] = lc_answer(lc, lcr, abr, thr=1.25)
        md.append(txt.replace("### (a)", "### (a, stricter bar)"))
    if not lc.empty:
        s = summarize_lc(lc)
        s.to_csv(os.path.join(a.out, "lc_summary.csv"), index=False)
        md.append(lc_tables(s))
        pool_runs = lc[lc["n"].astype(str) == "all"].groupby(["variant", "holdout"])["n_train_runs"].max().to_dict()
        lcr["_pool_runs"] = [pool_runs.get((v, d), 256) for v, d in zip(lcr["variant"], lcr["holdout"])]
        fig_learning_curve(lcr, load_csv(a.ablation, "ablation_runs.csv"), os.path.join(a.out, "learning_curve.png"), a.label)
    ab = load_csv(a.ablation, "ablation.csv")
    if not ab.empty:
        ab["rung"] = ab["rung"].astype(str)
        ab = ab.drop_duplicates(subset=["holdout", "rung"], keep="last")
        ab = ab.sort_values(["holdout", "rung"])
        ab.to_csv(os.path.join(a.out, "ablation_summary.csv"), index=False)
        txt, answers["b"] = ablation_verdict(ab, load_csv(a.ablation, "ablation_runs.csv"))
        md.insert(1, txt)
        md.append(ablation_tables(ab))
        md.append(paired_table(load_csv(a.ablation, "ablation_runs.csv")))
        fig_ablation(ab, os.path.join(a.out, "ablation_ladder.png"), a.label)
    open(os.path.join(a.out, "tables.md"), "w").write("\n".join(md) + "\n")
    import json
    json.dump(answers, open(os.path.join(a.out, "answers.json"), "w"), indent=1, default=str)
    print(f"wrote {a.out}/tables.md" + (" + learning_curve.png" if not lc.empty else "") + (" + ablation_ladder.png" if not ab.empty else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
