#!/usr/bin/env python3
"""Conformal risk control for the flagging threshold.

Usage: conformal.py --model models/model_holdout_<d>_v4.txt --exclude-design <d>
                    [--alpha 0.10] [--data results/dataset.parquet] [--out models/conformal/<d>.json]

Calibration units are *runs* (one flow run = one exchangeable unit), taken from every design
except the held-out one. For a threshold lambda, the per-run risk is the miss rate: the fraction
of that run's violating signal nets with score < lambda. Conformal risk control (Angelopoulos,
Bates et al., 2022) picks the largest lambda such that
    (n/(n+1)) * mean_i R_i(lambda) + 1/(n+1) <= alpha,
which guarantees E[miss rate on a new exchangeable run] <= alpha. Designs are not truly
exchangeable, so the guarantee is checked prospectively on unseen design families.
"""
import argparse, json, os
import numpy as np, pandas as pd, lightgbm as lgb
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train import FEATURES  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--model", required=True); ap.add_argument("--exclude-design", required=True)
ap.add_argument("--alpha", type=float, default=0.10)
ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "dataset.parquet"))
ap.add_argument("--out", default=None)
ap.add_argument("--balance-designs", action="store_true", help="one calibration unit per design (mean risk over its runs) instead of per run")
a = ap.parse_args()
df = pd.read_parquet(a.data)
df = df[(df.join_how != "none") & (df.driver_kind != "none") & (df.sigtype == "SIGNAL") & (df.design != a.exclude_design)]
model = lgb.Booster(model_file=a.model)
X = df[FEATURES].copy()
X["driver_class"] = pd.Categorical(X["driver_class"], categories=model.pandas_categorical[0]) if model.pandas_categorical else X["driver_class"].astype("category")
df = df.assign(p=model.predict(X))
grid = np.linspace(0.0, 1.0, 1001)
runs = []
unit = "design" if a.balance_designs else "run"
for key, g in df.groupby(unit):
    if a.balance_designs:
        per_run = []
        for run, gr in g.groupby("run"):
            pos = gr[gr.y == 1].p.values
            if len(pos) >= 5:
                per_run.append(np.array([(pos < lam).mean() for lam in grid]))
        if not per_run:
            continue
        runs.append(np.vstack(per_run).mean(axis=0))
    else:
        pos = g[g.y == 1].p.values
        if len(pos) < 5:
            continue  # runs with almost no violators carry no information about misses
        runs.append(np.array([(pos < lam).mean() for lam in grid]))
R = np.vstack(runs); n = len(runs)
bound = (n / (n + 1)) * R.mean(axis=0) + 1.0 / (n + 1)
ok = np.where(bound <= a.alpha)[0]
lam = float(grid[ok.max()]) if len(ok) else 0.0
# what fraction of nets that threshold flags on calibration runs (cost side)
flag_frac = float((df.p >= lam).mean())
per_design = {d: float(((g[g.y == 1].p < lam).mean())) for d, g in df.groupby("design") if (g.y == 1).sum() >= 5}
res = {"model": a.model, "exclude_design": a.exclude_design, "alpha": a.alpha, "lambda": lam, "calibration_unit": unit,
       "calibration_units": int(n), "bound_at_lambda": float(bound[ok.max()]) if len(ok) else None,
       "calibration_flag_fraction": flag_frac, "calibration_miss_rate_by_design": per_design}
out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.model)), "conformal", f"{a.exclude_design}_alpha{int(a.alpha*100):02d}.json")
os.makedirs(os.path.dirname(out), exist_ok=True)
json.dump(res, open(out, "w"), indent=1)
print(json.dumps(res, indent=1))
