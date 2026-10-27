#!/usr/bin/env python3
"""Ablation ladder: is the learned model doing more than a calibrated estimate?

Usage (one analyze.yml matrix entry per held-out design):
  ablation_ladder.py --data dataset.parquet --out out/ --holdout picorv32 [--rounds 400]
  ablation_ladder.py --data dataset.parquet --out out/ --holdout all   # every eligible design, sequentially

Leave-one-design-out: train on every other design (data runs, standard filter, all nets as in
br/train.py unless --train-sigtype SIGNAL), evaluate on the held-out design's signal nets.
Eligible held-out designs: >= --min-viol violating signal nets.
Rungs:
  0 random                         mean over 5 random scorings
  1 est_slew                       raw estimated worst-load slew ratio (timer's post-GRT estimate)
  2 rule_R8                        max(est load slew ratio, est driver slew ratio, cap_ratio) (br/score.py --rule R8)
  3 logreg_calibrated_estimate     logistic regression (balanced) on standardized log1p of
                                   [worst_load_slew_ratio, driver_slew_ratio, cap_ratio, fanout_ratio, hpwl_um,
                                    guide_len_um, guide_frac_*, fanout, density_mean]
  4 lgbm_estimate_only             LightGBM on the timer-estimate features only (analysis_common.ESTIMATE; no geometry,
                                   no cell identity, no design context)
  4b lgbm_no_geometry              LightGBM on train.FEATURES minus geometry (estimate + cell/netlist + design context)
  5 lgbm_full                      LightGBM on br/train.py FEATURES
LightGBM rungs use br/train.fit's parameters (captured from fit itself); --rounds overrides num_boost_round.
Metrics: recall at 5% flagged, fraction flagged to catch 95%, PR-AUC; pooled over the design's runs and per
run (median / IQR over runs with >= 1 violator); learned rungs also report count calibration per run.
Outputs: <out>/ablation.json, ablation.csv (one row per design x rung), ablation_runs.csv (per run).
"""
from __future__ import annotations

import argparse
import json
import os
import time

import numpy as np
import pandas as pd

import analysis_common as C

RUNGS = [
    ("0", "random"), ("1", "est_slew"), ("2", "rule_R8"), ("3", "logreg_calibrated_estimate"),
    ("4", "lgbm_estimate_only"), ("4b", "lgbm_no_geometry"), ("5", "lgbm_full"),
]


def run_design(df: pd.DataFrame, D: str, a, threads: int, out_rows: list, run_rows: list, report: dict) -> None:
    train_df = df if a.train_sigtype == "all" else df[df["is_signal"]]
    tr = train_df[train_df["design"] != D]
    ev = df[(df["design"] == D) & df["is_signal"]].reset_index(drop=True)
    res = {"n_eval_runs": int(ev["run"].nunique()), "eval_pos": int(ev["y"].sum()), "eval_n": int(len(ev)),
           "n_train_runs": int(tr["run"].nunique()), "n_train_rows": int(len(tr)), "n_train_pos": int(tr["y"].sum()),
           "rungs": {}}
    C.log(f"holdout={D}: eval runs={res['n_eval_runs']} signal nets={len(ev)} violators={res['eval_pos']} | "
          f"train runs={res['n_train_runs']} rows={len(tr)} pos={res['n_train_pos']}")
    want = set(a.rungs.split(",")) if a.rungs else None
    for rid, rname in RUNGS:
        if want and rid not in want:
            continue
        t0 = time.time()
        prob = None
        extra = {}
        if rname == "random":
            blks = []
            for s in range(5):
                blks.append(C.eval_block(ev, np.random.default_rng(100 + s).random(len(ev))))
            blk = blks[0]
            for k in ("recall@5%", "frac_to_catch_95", "pr_auc", "recall@2%", "frac_to_catch_90", "roc_auc"):
                blk["pooled"][k] = float(np.mean([b["pooled"][k] for b in blks]))
            for k in C.KEY_METRICS:
                for q in ("median", "q25", "q75"):
                    blk["per_run"][k][q] = float(np.mean([b["per_run"][k][q] for b in blks]))
        elif rname == "est_slew":
            blk = C.eval_block(ev, ev["worst_load_slew_ratio"].astype(float).fillna(0).values)
        elif rname == "rule_R8":
            blk = C.eval_block(ev, C.r8(ev))
        elif rname == "logreg_calibrated_estimate":
            m = C.fit_lr(tr)
            p = C.predict_lr(m, ev)
            prob = C.prior_correct(p, m._br_spw)
            blk = C.eval_block(ev, p, prob=prob)
            lr = m[-1]
            extra["coef"] = dict(zip(C.LR_FEATURES, [float(c) for c in lr.coef_[0]]))
            extra["intercept"] = float(lr.intercept_[0])
        else:
            feats = {"lgbm_estimate_only": C.ESTIMATE, "lgbm_no_geometry": C.NO_GEOMETRY, "lgbm_full": C.FEATURES}[rname]
            m = C.fit_lgb(tr, feats, rounds=a.rounds or None, threads=threads)
            p = C.predict_lgb(m, ev)
            prob = C.prior_correct(p, m._br_spw)
            blk = C.eval_block(ev, p, prob=prob)
            extra["features"] = feats
            extra["rounds"] = m._br_rounds
            imp = sorted(zip(feats, m.feature_importance("gain")), key=lambda t: -t[1])
            tot = sum(g for _, g in imp) or 1.0
            extra["importance_gain_frac"] = [(f, round(float(g) / tot, 4)) for f, g in imp[:12]]
        secs = time.time() - t0
        res["rungs"][rid] = {"name": rname, "pooled": blk["pooled"], "per_run": blk["per_run"], "seconds": round(secs, 1), **extra}
        row = {"holdout": D, "rung": rid, "rung_name": rname, "n_eval_runs": res["n_eval_runs"], "n_train_runs": res["n_train_runs"],
               "rounds": extra.get("rounds"), "seconds": round(secs, 1)}
        row.update(C.flat(blk))
        out_rows.append(row)
        for r in blk["runs"]:
            run_rows.append({"holdout": D, "rung": rid, "rung_name": rname, **r})
        pr = blk["pooled"]
        C.log(f"  {rid:>2} {rname:28s} pooled R@5%={pr.get('recall@5%', float('nan')):.3f} catch95={pr.get('frac_to_catch_95', float('nan')):.3f} "
              f"PR-AUC={pr.get('pr_auc', float('nan')):.3f} | run-med R@5%={blk['per_run']['recall@5%']['median']:.3f} "
              f"catch95={blk['per_run']['frac_to_catch_95']['median']:.3f} ({secs:.0f}s)")
        # write as we go (restart-safe partial output)
        pd.DataFrame(out_rows).to_csv(os.path.join(a.out, "ablation.csv"), index=False)
        pd.DataFrame(run_rows).to_csv(os.path.join(a.out, "ablation_runs.csv"), index=False)
    report[D] = res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--holdout", default="all", help="design, comma list, or 'all' (every design with >= --min-viol)")
    ap.add_argument("--min-viol", type=int, default=50)
    ap.add_argument("--rounds", type=int, default=0, help="num_boost_round override (0 = br/train.fit's)")
    ap.add_argument("--threads", type=int, default=0)
    ap.add_argument("--rungs", default="", help="comma list of rung ids to run (default all)")
    ap.add_argument("--train-sigtype", choices=["all", "SIGNAL"], default="all")
    ap.add_argument("--all-runs", action="store_true")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    threads = a.threads or os.cpu_count()
    t_start = time.time()
    df = C.load(a.data, all_runs=a.all_runs)
    viol = df[df["is_signal"]].groupby("design")["y"].sum()
    eligible = sorted(viol[viol >= a.min_viol].index)
    designs = eligible if a.holdout == "all" else a.holdout.split(",")
    C.log(f"rows={len(df)} runs={df['run'].nunique()} eligible={eligible} -> {designs}")
    out_rows, run_rows, report = [], [], {}
    skipped = {}
    for D in designs:
        if D not in eligible:
            skipped[D] = f"{int(viol.get(D, 0))} violating signal nets < {a.min_viol}"
            C.log(f"skip {D}: {skipped[D]}")
            continue
        run_design(df, D, a, threads, out_rows, run_rows, report)
        json.dump({"args": vars(a), "threads": threads, "eligible": eligible, "skipped": skipped,
                   "features": {"estimate": C.ESTIMATE, "no_geometry": C.NO_GEOMETRY, "full": C.FEATURES, "logreg": C.LR_FEATURES},
                   "seconds": round(time.time() - t_start, 1), "designs": report},
                  open(os.path.join(a.out, "ablation.json"), "w"), indent=1)
    if not report:
        json.dump({"args": vars(a), "eligible": eligible, "skipped": skipped}, open(os.path.join(a.out, "ablation.json"), "w"), indent=1)
    C.log(f"done in {time.time() - t_start:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
