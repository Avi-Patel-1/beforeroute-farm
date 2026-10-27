#!/usr/bin/env python3
"""Run-level view of held-out predictions: can we predict a run's signoff violator count before routing,
and does the conformal threshold's miss-rate guarantee hold on unseen designs?

Usage: run_level.py [--data results/dataset.parquet] --pairs design=model[=conformal.json] ... [--out results/run_level.json]
"""
import argparse, json, os, sys
import numpy as np, pandas as pd, lightgbm as lgb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train import FEATURES  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="results/dataset.parquet")
ap.add_argument("--pairs", nargs="+", required=True)
ap.add_argument("--out", default="results/run_level.json")
a = ap.parse_args()
df = pd.read_parquet(a.data)
df = df[(df.join_how != "none") & (df.driver_kind != "none") & (df.sigtype == "SIGNAL")]
out = {}
for pair in a.pairs:
    parts = pair.split("=")
    d, mpath = parts[0], parts[1]
    cpath = parts[2] if len(parts) > 2 else None
    g = df[df.design == d].copy()
    if g.empty:
        continue
    m = lgb.Booster(model_file=mpath)
    X = g[FEATURES].copy()
    X["driver_class"] = pd.Categorical(X["driver_class"], categories=m.pandas_categorical[0]) if m.pandas_categorical else X["driver_class"].astype("category")
    g["p"] = m.predict(X)
    lam = json.load(open(cpath))["lambda"] if cpath and os.path.exists(cpath) else None
    rows = []
    for run, r in g.groupby("run"):
        y = r.y.values.astype(int); p = r.p.values; est = r.worst_load_slew_ratio.fillna(0).values
        row = {"run": run, "nets": int(len(r)), "actual": int(y.sum()), "expected_sum_p": float(p.sum()),
               "count_p05": int((p >= 0.5).sum()), "count_est_gt1": int((est > 1).sum()),
               "recall_top5": float(y[np.argsort(-p)[:max(1, int(round(0.05 * len(y))))]].sum() / max(1, y.sum()))}
        if lam is not None:
            row.update({"lambda": lam, "miss_at_lambda": float(((p < lam) & (y == 1)).sum() / max(1, y.sum())),
                        "flag_frac_at_lambda": float((p >= lam).mean())})
        rows.append(row)
    t = pd.DataFrame(rows)
    summ = {"runs": int(len(t)), "violators_total": int(t.actual.sum()),
            "count_mape_sum_p": float((abs(t.expected_sum_p - t.actual) / t.actual.clip(lower=1)).median()),
            "count_mape_est": float((abs(t.count_est_gt1 - t.actual) / t.actual.clip(lower=1)).median()),
            "spearman_runs": float(t[["expected_sum_p", "actual"]].corr(method="spearman").iloc[0, 1]) if len(t) > 2 else None}
    if lam is not None:
        summ.update({"lambda": lam, "miss_at_lambda_median": float(t.miss_at_lambda.median()), "miss_at_lambda_max": float(t.miss_at_lambda.max()),
                     "flag_frac_at_lambda_median": float(t.flag_frac_at_lambda.median())})
    out[d] = {"summary": summ, "runs": rows}
    print(d, json.dumps(summ))
json.dump(out, open(a.out, "w"), indent=1)
