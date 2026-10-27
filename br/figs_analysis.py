#!/usr/bin/env python3
"""BeforeRoute analysis figures for the dark slide deck: learning curve and ablation ladder.

Usage:
  python3 br/figs_analysis.py all --out figures/v2/
  python3 br/figs_analysis.py learning_curve ablation --out figures/v2/ [--analysis agents/analysis/farm]

Nothing is retrained: every number drawn is read from the analysis agent's collected farm outputs
(LightGBM at 400 rounds, 3 seeds, on the 214-run farm dataset; the local reduced-round runs under
results/analysis/local are not used):
  <analysis>/answers.json           a.<design>.<variant>.curve.<n>.per_run_median_x_floor (seed mean of the per-run
                                    median of catch-95 / floor), a.<design>._ref_per_run_x_floor (rule R8, same metric,
                                    all runs of the design), b.ALL.paired_vs_*.catch95 (per-run sign tests)
  <analysis>/ablation_summary.csv   pooled catch-95 and violator counts per held-out design x rung
The raw per-run outputs (results/analysis/{lc,self_farmdata}/**/learning_curve_runs.csv and
results/analysis/ablation{,_3b}/ablation_runs.csv) are read only to cross-check answers.json; the result of the
check is printed and stored with the figure's numbers.

catch-95 = fraction of a run's signal nets that must be flagged (top of the ranking) to catch 95% of its signoff
violators; floor = 0.95 x the violator rate (flag only violators), so catch-95 / floor >= 1 and 1 is perfect.

Style, palette and save() come from br/figs_v2.py (imported as F): black surface, model = green star,
rule R8 = blue square, raw estimate = grey circle, >= 14 pt text, drawn at final slide size (5.6 x 4.5 in, the
deck's half-slide picture slot). The numbers each figure drew are merged into <out>/figs_v2_numbers.json.
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
import matplotlib.ticker as mticker  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

ANALYSIS = os.path.join(F.ROOT, "agents", "analysis", "farm")
RAW = os.path.join(F.RESULTS, "analysis")
LC_RAW_DIRS = ["lc", "self_farmdata"]          # farm learning curves + same-design-only variant (400 rounds, farm data)
AB_RAW_DIRS = ["ablation", "ablation_3b"]      # farm ablation + rung 3b (same data); first dir wins on duplicates

SIZE = (5.6, 4.5)                              # half-slide picture slot (slide 3), so 14 pt stays >= 14 pt
SELF = "#b4e06c"                               # same-design-only line: lighter step of the model green (L* 84 vs 63)
LINEAR = F.INK2                                # learned linear calibrations (neither the rule nor the model)
LC_R8 = F.GREY                                 # rule R8 reference in the learning curve (dashed)
FLOOR2 = F.INK2                                # 2x-floor reference (dotted)
DEGENERATE_X = 8.0                             # rule R8 above this x floor: too few violators per run, floor degenerate
LC_SIZES = ["1", "2", "4", "8", "16", "32", "64", "all"]
SELF_DODGE = 2 ** -0.11                        # same-design points drawn slightly left of their x (shared x = 1, 2, 4)
LABEL = {"des": "DES", "aes_cipher_top": "AES", "picorv32": "PicoRV32", "BM64": "BM64"}


def load_answers(analysis):
    p = os.path.join(analysis, "answers.json")
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    return json.load(open(p))


def _agg(vals):
    v = np.asarray(sorted(vals.values()), dtype=float)
    return {"median": float(np.median(v)), "min": float(v.min()), "max": float(v.max()), "n": int(len(v)),
            "by_design": dict(sorted(vals.items()))}


# ================================================================ learning curve
def lc_data(answers, degenerate_x=DEGENERATE_X):
    """Per variant ('runs' = N runs of other designs, 'self' = k runs of the held-out design only) and size:
    per-run median catch-95 / floor per design, aggregated across designs (median, range)."""
    a = answers.get("a") or {}
    ref = {d: (v.get("_ref_per_run_x_floor") or {}) for d, v in a.items()}
    excluded = {d: r["rule_R8"] for d, r in ref.items() if r.get("rule_R8") is not None and r["rule_R8"] > degenerate_x}
    out = {"excluded": excluded, "variants": {}}
    for var in ("runs", "self"):
        pts, pool = {}, {}
        for d, v in a.items():
            if d in excluded or var not in v:
                continue
            for n, c in v[var]["curve"].items():
                if c.get("per_run_median_x_floor") is None:
                    continue
                pts.setdefault(str(n), {})[d] = float(c["per_run_median_x_floor"])
                if str(n) == "all":
                    pool[d] = float(c["train_runs"])
        sizes = [n for n in LC_SIZES if n in pts]
        if sizes:
            out["variants"][var] = {"sizes": sizes, "points": {n: _agg(pts[n]) for n in sizes}, "all_train_runs": pool}
    designs = sorted({d for v in out["variants"].values() for p in v["points"].values() for d in p["by_design"]})
    r8 = {d: float(ref[d]["rule_R8"]) for d in designs if "rule_R8" in ref.get(d, {})}
    out["designs"] = designs
    out["r8"] = _agg(r8) if r8 else None
    return out


def lc_crosscheck(answers):
    """Recompute the per-run median x floor from the raw per-run outputs (as br/analysis_report.py does) and compare
    with answers.json. Returns a summary dict; never raises (the figure is drawn from answers.json either way)."""
    try:
        import analysis_report as R
        dirs = [os.path.join(RAW, d) for d in LC_RAW_DIRS if os.path.isdir(os.path.join(RAW, d))]
        lcr = R.load_lc_runs(dirs)
        if lcr.empty:
            return {"checked": 0, "note": "no raw per-run outputs"}
        r = lcr[lcr["positives"] > 0]
        xf = r["frac_to_catch_95"] / (0.95 * r["positives"] / r["n_nets"])
        per = xf.groupby([r["variant"], r["holdout"], r["n"].astype(str), r["seed"]]).median().groupby(level=[0, 1, 2]).mean()
        a = answers.get("a") or {}
        dev, missing, extra = 0.0, [], []
        for (v, d, n), x in per.items():
            got = ((a.get(d) or {}).get(v) or {}).get("curve", {}).get(n, {}).get("per_run_median_x_floor")
            if got is None:
                extra.append(f"{v}/{d}/{n}")
                continue
            dev = max(dev, abs(round(float(x), 2) - got))
        for d, dv in a.items():
            for v in ("runs", "self"):
                for n in (dv.get(v) or {}).get("curve", {}):
                    if (v, d, str(n)) not in per.index:
                        missing.append(f"{v}/{d}/{n}")
        return {"checked": int(len(per)), "max_abs_diff_2dp": dev, "raw_not_in_answers": extra, "answers_not_in_raw": missing}
    except Exception as e:  # cross-check only
        return {"checked": 0, "note": f"cross-check failed: {type(e).__name__}: {e}"}


def fig_learning_curve(out_dir, analysis=ANALYSIS, size=SIZE, name="learning_curve"):
    """Median across held-out designs of catch-95 / floor (per-run median) vs training runs, for N runs of other
    designs and k runs of the same design only, against rule R8 (no training) and 2x floor."""
    answers = load_answers(analysis)
    D = lc_data(answers)
    V = D["variants"]
    if "runs" not in V and "self" not in V:
        print("[figs_analysis] learning_curve: no learning-curve cells in answers.json; skipped")
        return None
    pool = sorted(V.get("runs", {}).get("all_train_runs", {}).values())
    x_all = float(np.median(pool)) if pool else 200.0

    def xpos(n):
        return x_all if n == "all" else float(n)

    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0.13, 0.30, 0.84, 0.535])
    ax.set_xscale("log", base=2)
    ax.set_yscale("log", base=2)
    nums = {"metric": "catch-95 / floor, per-run median (seed mean), median and range across held-out designs",
            "source": os.path.relpath(os.path.join(analysis, "answers.json"), F.ROOT), "x_all": x_all,
            "all_train_runs": V.get("runs", {}).get("all_train_runs", {}),
            "excluded_degenerate_floor": D["excluded"], "degenerate_rule": f"rule R8 per-run median > {DEGENERATE_X:g}x floor"}
    top = 2.0
    handles = []
    if "runs" in V:   # N runs of other designs: line + shaded range
        v = V["runs"]
        xs = [xpos(n) for n in v["sizes"]]
        med, lo, hi = ([v["points"][n][k] for n in v["sizes"]] for k in ("median", "min", "max"))
        top = max(top, max(hi))
        ax.fill_between(xs, lo, hi, color=F.GREEN, alpha=0.26, lw=0, zorder=2)
        ax.plot(xs, med, color=F.GREEN, lw=2.6, zorder=5, marker="*", ms=15, mfc=F.GREEN, mec=F.SURFACE, mew=1.2)
        nr = sorted({p["n"] for p in v["points"].values()})
        nd = f"{nr[0]}–{nr[-1]}" if nr[0] != nr[-1] else f"{nr[0]}"
        handles.append(Line2D([], [], color=F.GREEN, lw=2.6, marker="*", ms=15, mfc=F.GREEN, mec=F.SURFACE, mew=1.2,
                              label=f"Runs of other designs ({nd} designs)"))
        nums["runs"] = {n: v["points"][n] for n in v["sizes"]}
        for n in ("4", "all"):   # the two numbers the slide quotes: a few runs, and every run
            if n in v["points"]:
                p = v["points"][n]
                ax.annotate(f"{p['median']:.2f}×", (xpos(n), p["max"]), xytext=(0, 5), textcoords="offset points",
                            ha="center" if n != "all" else "right", va="bottom", fontsize=F.FS, color=F.INK,
                            path_effects=F.HALO, zorder=8)
    if "self" in V:   # k runs of the held-out design only: dodged left, range as bars (the two ranges overlap)
        v = V["self"]
        xs = [xpos(n) * SELF_DODGE for n in v["sizes"]]
        med, lo, hi = ([v["points"][n][k] for n in v["sizes"]] for k in ("median", "min", "max"))
        top = max(top, max(hi))
        ax.vlines(xs, lo, hi, color=SELF, lw=1.6, zorder=3)
        ax.plot(xs + xs, lo + hi, "_", ms=9, mew=1.6, color=SELF, zorder=3)
        ax.plot(xs, med, color=SELF, lw=2.0, zorder=6, marker="*", ms=14, mfc=F.SURFACE, mec=SELF, mew=1.7)
        ns = sorted({p["n"] for p in v["points"].values()})
        nd = f"{ns[0]}–{ns[-1]}" if ns[0] != ns[-1] else f"{ns[0]}"
        handles.append(Line2D([], [], color=SELF, lw=2.0, marker="*", ms=14, mfc=F.SURFACE, mec=SELF, mew=1.7,
                              label=f"Same design only ({nd} designs)"))
        nums["self"] = {n: v["points"][n] for n in v["sizes"]}
        if "2" in v["points"]:   # two runs of the same design: value under its range bar
            p = v["points"]["2"]
            ax.annotate(f"{p['median']:.2f}×", (xpos("2") * SELF_DODGE, p["min"]), xytext=(0, -4), textcoords="offset points",
                        ha="center", va="top", fontsize=F.FS, color=SELF, zorder=8,
                        bbox=dict(boxstyle="square,pad=0.08", fc=F.SURFACE, ec="none"))
    r8 = D["r8"]
    if r8:
        ax.axhline(r8["median"], color=LC_R8, lw=2.0, ls=(0, (5, 3)), zorder=4)
        nums["rule_R8"] = r8
    ax.axhline(2.0, color=FLOOR2, lw=1.5, ls=(0, (1, 2.2)), zorder=4)
    ylo, yhi = 0.91, max(4.0, top * 1.06)   # room under 1x (nothing can sit below it) for the value labels
    ax.set_ylim(ylo, yhi)
    ax.set_xlim(0.8, x_all * 1.25)
    yt = [t for t in (1, 1.25, 1.5, 2, 3, 4, 6, 8) if t <= yhi]
    ax.set_yticks(yt)
    ax.set_yticklabels([f"{t:g}×" for t in yt])
    xt = [xpos(n) for n in LC_SIZES]
    ax.set_xticks(xt)
    ax.set_xticklabels([n for n in LC_SIZES])
    ax.xaxis.set_minor_locator(mticker.NullLocator())
    ax.yaxis.set_minor_locator(mticker.NullLocator())
    ax.grid(True, axis="y", zorder=0)
    ax.set_xlabel("Past signoff runs in the training set", labelpad=4)
    ax.legend(handles=handles, loc="upper right", bbox_to_anchor=(1.0, 1.0), fontsize=F.FS, labelcolor=F.INK2,
              handlelength=1.7, handletextpad=0.5, borderaxespad=0.2, labelspacing=0.35)
    # reference-line labels at the right end
    xr = x_all * 1.2
    if r8:
        ax.text(xr, r8["median"] / 1.035, f"Rule R8, no training: {r8['median']:.2f}×", ha="right", va="top", fontsize=F.FS,
                color=F.INK2, path_effects=F.HALO, zorder=7)
    ax.text(xr, 2.0 * 1.035, "2× floor", ha="right", va="bottom", fontsize=F.FS, color=F.INK2, path_effects=F.HALO, zorder=7)
    fig.text(0.012, 0.975, "A few past signoff runs are enough", fontsize=F.FS + 1, fontweight="semibold", color=F.INK, va="top")
    fig.text(0.012, 0.905, "Nets flagged to catch 95% of violators, × floor", fontsize=F.FS, color=F.INK2, va="top")
    notes = ["Floor = flag only violators. Median of unseen designs;", "shading and bars = range across designs."]
    if D["excluded"]:
        ex = ", ".join(LABEL.get(d, d) for d in sorted(D["excluded"]))
        notes[-1] = f"shading, bars = range. {ex} omitted: floor degenerate."
    fig.text(0.012, 0.012, "\n".join(notes), fontsize=F.FS, color=F.MUTED, va="bottom", linespacing=1.25)
    nums["crosscheck_raw_per_run"] = lc_crosscheck(answers)
    return F.save(fig, out_dir, name, nums)


# ================================================================ ablation ladder
RUNGS = [  # (rung_name in ablation_summary.csv, label, marker, color, filled)
    ("est_slew", "Timer's estimate", "o", F.GREY, True),
    ("rule_R8", "Rule R8", "s", F.BLUE, True),
    ("logreg_r8_inputs", "Logistic on R8's inputs", "D", LINEAR, False),
    ("logreg_calibrated_estimate", "Linear calibration (LR)", "D", LINEAR, False),
    ("lgbm_estimate_only", "GBM, estimate only", "*", F.GREEN, True),
    ("lgbm_no_geometry", "GBM, no geometry", "*", F.GREEN, True),
    ("lgbm_full", "GBM, all features", "*", F.GREEN, True),
]


def ablation_data(analysis):
    import pandas as pd

    p = os.path.join(analysis, "ablation_summary.csv")
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    ab = pd.read_csv(p, usecols=["holdout", "rung_name", "n_eval_runs", "eval_n", "eval_pos", "pooled_catch95"])
    designs = sorted(ab["holdout"].unique())
    first = ab.drop_duplicates("holdout").set_index("holdout")
    floor = {d: 0.95 * float(first.loc[d, "eval_pos"]) / float(first.loc[d, "eval_n"]) for d in designs}
    rows = []
    for rn, lab, mk, col, filled in RUNGS:
        x = ab[ab["rung_name"] == rn].set_index("holdout")["pooled_catch95"].dropna()
        if x.empty:
            continue
        vals = {d: float(v) for d, v in x.items()}
        rows.append(dict(rung=rn, label=lab, marker=mk, color=col, filled=filled, **_agg(vals),
                         mean=float(np.mean(list(vals.values())))))
    return {"rows": rows, "floor": dict(_agg(floor), mean=float(np.mean(list(floor.values())))), "designs": designs,
            "runs": {d: int(first.loc[d, "n_eval_runs"]) for d in designs}}


def ab_crosscheck(answers):
    """Recompute the per-run sign tests (GBM full vs R8 / estimate / logistic on R8 inputs) from the raw per-run rows."""
    try:
        import analysis_report as R
        from scipy.stats import binomtest

        dirs = ",".join(os.path.join(RAW, d) for d in AB_RAW_DIRS if os.path.isdir(os.path.join(RAW, d)))
        abr = R.load_multi(dirs, "ablation_runs.csv", key=["holdout", "rung", "run"])
        if abr.empty:
            return {"checked": 0, "note": "no raw per-run outputs"}
        piv = abr[abr["positives"] > 0].pivot_table(index=["holdout", "run"], columns="rung_name", values="frac_to_catch_95",
                                                    aggfunc="first")
        out = {"runs": int(len(piv))}
        b = (answers.get("b") or {}).get("ALL", {})
        for key, base in (("paired_vs_R8", "rule_R8"), ("paired_vs_est", "est_slew"), ("paired_vs_logreg_r8_inputs", "logreg_r8_inputs")):
            if base not in piv or "lgbm_full" not in piv:
                continue
            d = (piv[base] - piv["lgbm_full"]).dropna()
            w, l_ = int((d > 1e-12).sum()), int((d < -1e-12).sum())
            mine = {"W": w, "T": int(len(d) - w - l_), "L": l_, "p": float(binomtest(w, w + l_, 0.5).pvalue)}
            theirs = (b.get(key) or {}).get("catch95") or {}
            out[key] = {"raw": mine, "matches_answers": all(mine[k] == theirs.get(k) for k in ("W", "T", "L"))}
        return out
    except Exception as e:  # cross-check only
        return {"checked": 0, "note": f"cross-check failed: {type(e).__name__}: {e}"}


def fig_ablation(out_dir, analysis=ANALYSIS, size=SIZE, name="ablation"):
    """Median across the held-out designs of the pooled catch-95 per rung of the ablation ladder, with the floor."""
    A = ablation_data(analysis)
    rows = A["rows"]
    if not rows:
        print("[figs_analysis] ablation: no rungs in ablation_summary.csv; skipped")
        return None
    answers = load_answers(analysis)
    st = (((answers.get("b") or {}).get("ALL") or {}).get("paired_vs_R8") or {}).get("catch95")
    fig = plt.figure(figsize=size)
    ax = fig.add_axes([0.415, 0.30, 0.555, 0.455])
    ny = len(rows)
    ys = np.arange(ny)[::-1]
    fl = A["floor"]["median"]
    xmax = max(r["median"] for r in rows)
    ax.axvline(100 * fl, color=F.INK2, lw=1.5, ls=(0, (1, 2.2)), zorder=1)
    for y, r in zip(ys, rows):
        gbm = r["rung"].startswith("lgbm")
        ms = {"*": 19 if r["rung"] == "lgbm_full" else 16, "s": 10, "o": 11, "D": 9}[r["marker"]]
        ax.plot([100 * fl, 100 * r["median"]], [y, y], color=F.AXIS, lw=1.0, zorder=2)   # excess over the floor
        ax.plot(100 * r["median"], y, r["marker"], ms=ms, color=r["color"], mfc=r["color"] if r["filled"] else F.SURFACE,
                mec=F.SURFACE if r["filled"] else r["color"], mew=1.4 if r["filled"] else 1.8, zorder=4)
        ax.text(100 * r["median"] + 0.42, y, f"{100 * r['median']:.1f}%", fontsize=F.FS, color=F.INK if gbm else F.INK2,
                va="center", ha="left", zorder=5)
    ax.set_yticks(ys)
    ax.set_yticklabels([r["label"] for r in rows])
    for t, r in zip(ax.get_yticklabels(), rows):
        t.set_color(F.INK if r["rung"].startswith("lgbm") else F.INK2)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    xt = list(range(0, 2 * int(np.ceil(100 * xmax / 2)) + 1, 2))
    ax.set_xlim(0, max(xt[-1], 100 * xmax + 1.9))
    ax.set_xticks(xt)
    ax.set_xticklabels([f"{t}%" for t in xt])
    ax.set_ylim(-0.6, ny - 0.4)
    ax.grid(True, axis="x", zorder=0)
    ax.text(100 * fl, ny - 0.45, f"floor {100 * fl:.1f}%", fontsize=F.FS, color=F.INK2, ha="center", va="bottom", zorder=5)
    fig.text(0.012, 0.975, "The gain is a nonlinear model\nof the timer's own numbers", fontsize=F.FS + 1, fontweight="semibold",
             color=F.INK, va="top", linespacing=1.15)
    fig.text(0.012, 0.848, "Nets flagged to catch 95% of violators", fontsize=F.FS, color=F.INK2, va="top")
    nd = len(A["designs"])
    lines = [f"Median of {nd} unseen designs, each pooled over its runs."]
    if st:
        tot = st["W"] + st["T"] + st["L"]
        lines.append(f"Per run, the full GBM flags fewer than R8 in {st['W']} of {tot}")
        lines.append(f"runs ({st['L']} worse, {st['T']} tied; sign test p = {st['p']:.0e}).")
    fig.text(0.012, 0.012, "\n".join(lines), fontsize=F.FS, color=F.MUTED, va="bottom", linespacing=1.25)
    nums = {"metric": "pooled catch-95 per held-out design (leave-one-design-out), median across designs",
            "source": os.path.relpath(os.path.join(analysis, "ablation_summary.csv"), F.ROOT),
            "rungs": {r["rung"]: {k: r[k] for k in ("label", "median", "mean", "min", "max", "n", "by_design")} for r in rows},
            "floor": A["floor"], "eval_runs_by_design": A["runs"], "sign_test_vs_R8_catch95": st,
            "crosscheck_raw_per_run": ab_crosscheck(answers)}
    return F.save(fig, out_dir, name, nums)


# ================================================================ CLI
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("names", nargs="+", help="learning_curve, ablation, or all")
    ap.add_argument("--out", default=os.path.join(F.ROOT, "figures", "v2"))
    ap.add_argument("--analysis", default=ANALYSIS, help="dir with answers.json and ablation_summary.csv")
    a = ap.parse_args()
    out = os.path.abspath(a.out)
    F.setup_style()
    jobs = {"learning_curve": lambda: fig_learning_curve(out, a.analysis),
            "ablation": lambda: fig_ablation(out, a.analysis)}
    names = list(jobs) if a.names == ["all"] else [n.replace("-", "_") for n in a.names]
    bad = [n for n in names if n not in jobs]
    if bad:
        ap.error(f"unknown figure(s): {bad}; choose from {list(jobs)} or 'all'")
    failed = []
    for n in names:
        try:
            jobs[n]()
        except FileNotFoundError as e:
            print(f"[figs_analysis] {n}: input missing ({e}); skipped")
        except Exception as e:  # keep going: one broken input must not block the other figure
            failed.append(n)
            print(f"[figs_analysis] {n}: FAILED {type(e).__name__}: {e}")
    os.makedirs(out, exist_ok=True)
    npath = os.path.join(out, "figs_v2_numbers.json")
    prev = json.load(open(npath)) if os.path.exists(npath) else {}
    prev.update(F.NUMBERS)
    json.dump(prev, open(npath, "w"), indent=1, default=float)
    print(f"[figs_analysis] numbers -> {os.path.relpath(npath, F.ROOT)}" + (f"; failed: {failed}" if failed else ""))
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
