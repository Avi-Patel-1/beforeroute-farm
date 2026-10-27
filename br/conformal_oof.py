#!/usr/bin/env python3
"""Cross-design conformal risk control with OUT-OF-FOLD calibration scores (fixes br/conformal.py, whose
calibration scores were in-sample: the held-out model of the target design had been trained on the
calibration designs).

Every design's rows are scored by that design's own held-out model (never trained on it). For target
design d, the calibration units are the OTHER designs (design-level: mean per-run miss curve of the design)
or their runs (run-level), and lambda is chosen by conformal risk control:
    (n/(n+1)) * mean_i R_i(lambda) + 1/(n+1) <= alpha.
Also evaluates the deterministic rule R8 = max(est load slew, est driver slew, est cap ratio), which needs no
training (its calibration is clean by construction), at the same alpha: fraction of nets flagged and realized
miss on d. Usage: conformal_oof.py --pairs design=model ... [--alpha 0.1 0.2] [--out results/conformal_oof.json]
"""
import argparse, json, os, sys
import numpy as np, pandas as pd, lightgbm as lgb
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train import FEATURES  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--data", default="results/dataset.parquet")
ap.add_argument("--pairs", nargs="+", required=True)
ap.add_argument("--alpha", type=float, nargs="+", default=[0.10, 0.20])
ap.add_argument("--targets", nargs="*", default=None, help="designs to evaluate as unseen (default: all paired)")
ap.add_argument("--min-pos", type=int, default=5)
ap.add_argument("--out", default="results/conformal_oof.json")
a = ap.parse_args()

cols = list(dict.fromkeys(FEATURES + ["design", "run", "y", "sigtype", "join_how", "driver_kind"]))
df = pd.read_parquet(a.data, columns=cols)
df = df[(df.join_how != "none") & (df.driver_kind != "none") & (df.sigtype == "SIGNAL")].copy()
models = dict(p.split("=", 1) for p in a.pairs)
df = df[df.design.isin(models)].copy()
df["p"] = np.nan
for d, mpath in models.items():
    m = lgb.Booster(model_file=mpath)
    idx = df.design == d
    X = df.loc[idx, FEATURES].copy()
    X["driver_class"] = pd.Categorical(X["driver_class"], categories=m.pandas_categorical[0]) if m.pandas_categorical else X["driver_class"].astype("category")
    df.loc[idx, "p"] = m.predict(X)
df["r8"] = df[["worst_load_slew_ratio", "driver_slew_ratio", "cap_ratio"]].fillna(0).astype(float).max(axis=1)


def curves(score, grid):
    """per (design, run): miss-rate curve over the threshold grid (runs with >= min_pos violators)."""
    out = {}
    for (d, r), g in df.groupby(["design", "run"]):
        pos = np.sort(g.loc[g.y == 1, score].values)
        if len(pos) < a.min_pos:
            continue
        out[(d, r)] = np.searchsorted(pos, grid, side="left") / len(pos)  # fraction of violators with score < lambda
    return out


res = {"alpha": a.alpha, "targets": {}}
for score, grid in (("p", np.linspace(0, 1, 2001)), ("r8", np.quantile(df["r8"].values, np.linspace(0, 1, 2001)))):
    C = curves(score, grid)
    for d in (a.targets or sorted(models)):
        tgt = [(k, v) for k, v in C.items() if k[0] == d]
        if not tgt:
            continue
        for unit in ("design", "run"):
            if unit == "design":
                byd = {}
                for (dd, r), v in C.items():
                    if dd != d:
                        byd.setdefault(dd, []).append(v)
                U = [np.mean(v, axis=0) for v in byd.values()]
            else:
                U = [v for (dd, r), v in C.items() if dd != d]
            R = np.vstack(U); n = len(U)
            bound = (n / (n + 1)) * R.mean(axis=0) + 1.0 / (n + 1)
            for alpha in a.alpha:
                ok = np.where(bound <= alpha)[0]
                lam = float(grid[ok.max()]) if len(ok) else float(grid[0])
                g = df[df.design == d]
                miss_runs = [float(((x[score] < lam) & (x.y == 1)).sum() / x.y.sum()) for _, x in g.groupby("run") if x.y.sum() >= a.min_pos]
                flag_runs = [float((x[score] >= lam).mean()) for _, x in g.groupby("run") if x.y.sum() >= a.min_pos]
                res["targets"].setdefault(d, {}).setdefault(score, {}).setdefault(unit, {})[str(alpha)] = {
                    "lambda": lam, "units": n, "feasible": bool(len(ok)),
                    "miss_median": float(np.median(miss_runs)), "miss_max": float(np.max(miss_runs)),
                    "flag_frac_median": float(np.median(flag_runs)), "runs": len(miss_runs)}
json.dump(res, open(a.out, "w"), indent=1)
print(f"{'design':15s} {'score':5s} {'unit':6s} {'alpha':>5s} {'lambda':>8s} {'miss(med)':>9s} {'miss(max)':>9s} {'flagged':>8s}")
for d, v in res["targets"].items():
    for score, u in v.items():
        for unit, al in u.items():
            for alpha, r in al.items():
                print(f"{d:15s} {score:5s} {unit:6s} {alpha:>5s} {r['lambda']:8.3f} {r['miss_median']:9.1%} {r['miss_max']:9.1%} {r['flag_frac_median']:8.1%}" + ("" if r["feasible"] else "  (infeasible: lambda=min)"))
