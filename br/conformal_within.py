#!/usr/bin/env python3
"""Within-design conformal check: calibrate the threshold on k earlier runs of the SAME design (model never
trained on the design), test the miss rate on each remaining run. Also the 'expected-count' auto-budget:
flag the top round(sum p) nets of a run and measure recall.
Usage: conformal_within.py --pairs design=model ... [--alpha 0.10] [--k 1 2 4]
"""
import argparse, json, os, sys
import numpy as np, pandas as pd, lightgbm as lgb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train import FEATURES  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="results/dataset.parquet"); ap.add_argument("--pairs", nargs="+", required=True)
ap.add_argument("--alpha", type=float, default=0.10); ap.add_argument("--k", type=int, nargs="+", default=[1, 2, 4])
ap.add_argument("--seeds", type=int, default=20); ap.add_argument("--out", default="results/conformal_within.json")
a = ap.parse_args()
df = pd.read_parquet(a.data)
df = df[(df.join_how != "none") & (df.driver_kind != "none") & (df.sigtype == "SIGNAL")]
grid = np.linspace(0, 1, 2001)
res = {}
for pair in a.pairs:
    d, mpath = pair.split("=")[:2]
    g = df[df.design == d].copy()
    m = lgb.Booster(model_file=mpath)
    X = g[FEATURES].copy()
    X["driver_class"] = pd.Categorical(X["driver_class"], categories=m.pandas_categorical[0]) if m.pandas_categorical else X["driver_class"].astype("category")
    g["p"] = m.predict(X)
    runs = {r: (x.p.values, x.y.values.astype(int)) for r, x in g.groupby("run") if x.y.sum() >= 5}
    names = sorted(runs)
    miss_curves = {r: np.array([((runs[r][0] < l) & (runs[r][1] == 1)).sum() / runs[r][1].sum() for l in grid]) for r in names}
    # expected-count auto budget
    auto = []
    for r in names:
        p, y = runs[r]; K = max(1, int(round(p.sum())))
        top = np.argsort(-p)[:K]
        auto.append({"run": r, "K": K, "frac": K / len(p), "recall": float(y[top].sum() / y.sum()), "precision": float(y[top].mean())})
    out = {"runs": len(names), "auto_budget_recall_median": float(np.median([x["recall"] for x in auto])) if auto else None,
           "auto_budget_frac_median": float(np.median([x["frac"] for x in auto])) if auto else None, "within": {}}
    rng = np.random.default_rng(0)
    for k in a.k:
        if len(names) < k + 1:
            continue
        misses, fracs, lams = [], [], []
        for s in range(a.seeds):
            perm = list(rng.permutation(names)); cal, test = perm[:k], perm[k:]
            # split conformal at the net level: violators of the calibration runs are the exchangeable units
            sc = np.sort(np.concatenate([runs[r][0][runs[r][1] == 1] for r in cal]))
            n = len(sc)
            j = int(np.floor(a.alpha * (n + 1))) - 1  # largest lambda with (#cal violators below lambda + 1)/(n+1) <= alpha
            lam = float(sc[j]) if j >= 0 else 0.0
            lams.append(lam)
            for r in test:
                p, y = runs[r]
                misses.append(((p < lam) & (y == 1)).sum() / y.sum()); fracs.append((p >= lam).mean())
        out["within"][k] = {"lambda_median": float(np.median(lams)), "miss_mean": float(np.mean(misses)), "miss_p90": float(np.quantile(misses, 0.9)),
                            "flag_frac_mean": float(np.mean(fracs)), "n_test": len(misses)}
    res[d] = out
    print(d, json.dumps(out))
json.dump(res, open(a.out, "w"), indent=1)
