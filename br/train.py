#!/usr/bin/env python3
"""Train / evaluate the BeforeRoute per-net signoff-violation predictor.

Usage: train.py [--data results/dataset.parquet] [--out results/model] [--holdout picorv32]

Evaluation: leave-one-design-out (every design held out once) + the named
hero holdout. Metrics per held-out design: PR-AUC, ROC-AUC, recall at 2% / 5%
of nets flagged, and the fraction of nets that must be flagged to catch 90% of
violating nets. Baselines: rankings by the timer's own estimated slew ratio,
cap ratio, fanout, HPWL and guide length.
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

FEATURES = [
    "is_clock", "fanout", "n_load_ports", "drive_index",
    "driver_slew_ns", "driver_slew_ratio", "worst_load_slew_ns", "worst_load_slew_ratio",
    "driver_slew_limit_lib_ns", "driver_cap_limit_lib_pf", "driver_slack_ns",
    "hpwl_um", "bbox_w_um", "bbox_h_um", "density_mean", "density_max",
    "guide_len_um", "guide_frac_li1", "guide_frac_met1", "guide_frac_met2", "guide_frac_met3up",
    "net_cap_pf_max", "net_cap_pf_tt", "pin_cap_pf_max", "cap_ratio", "fanout_ratio",
    "d_utilization", "d_clock_period_ns", "d_fp_core_util", "d_pl_density_pct", "d_max_tran_ns",
    "driver_class",
]
BASELINES = {
    "est_load_slew_ratio": "worst_load_slew_ratio",
    "est_driver_slew_ratio": "driver_slew_ratio",
    "est_cap_ratio": "cap_ratio",
    "fanout": "fanout",
    "hpwl": "hpwl_um",
    "guide_len": "guide_len_um",
}


def recall_at(y, score, frac):
    n = len(y)
    k = max(1, int(round(frac * n)))
    idx = np.argsort(-score)[:k]
    pos = y.sum()
    return float(y[idx].sum() / pos) if pos else float("nan")


def frac_to_catch(y, score, target=0.9):
    order = np.argsort(-score)
    cum = np.cumsum(y[order])
    pos = y.sum()
    if pos == 0:
        return float("nan")
    k = int(np.searchsorted(cum, target * pos) + 1)
    return k / len(y)


def evaluate(y, score):
    from sklearn.metrics import average_precision_score, roc_auc_score

    y = np.asarray(y).astype(int)
    score = np.asarray(score, dtype=float)
    score = np.nan_to_num(score, nan=0.0, posinf=1e9, neginf=-1e9)
    out = {"n": int(len(y)), "positives": int(y.sum()), "base_rate": float(y.mean()) if len(y) else float("nan")}
    if y.sum() == 0 or y.sum() == len(y):
        return out
    out.update(
        {
            "pr_auc": float(average_precision_score(y, score)),
            "roc_auc": float(roc_auc_score(y, score)),
            "recall@1%": recall_at(y, score, 0.01),
            "recall@2%": recall_at(y, score, 0.02),
            "recall@5%": recall_at(y, score, 0.05),
            "recall@10%": recall_at(y, score, 0.10),
            "frac_to_catch_90": frac_to_catch(y, score, 0.9),
            "frac_to_catch_95": frac_to_catch(y, score, 0.95),
        }
    )
    return out


def fit(df_train):
    import lightgbm as lgb

    X = df_train[FEATURES].copy()
    X["driver_class"] = X["driver_class"].astype("category")
    y = df_train["y"].astype(int)
    pos = max(1, int(y.sum()))
    neg = max(1, int((1 - y).sum()))
    params = dict(
        objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=40,
        feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
        scale_pos_weight=min(50.0, neg / pos), verbose=-1, seed=7, num_threads=2,
    )
    model = lgb.train(params, lgb.Dataset(X, y, categorical_feature=["driver_class"]), num_boost_round=400)
    return model


def predict(model, df):
    X = df[FEATURES].copy()
    X["driver_class"] = pd.Categorical(X["driver_class"], categories=model.pandas_categorical[0]) if model.pandas_categorical else X["driver_class"].astype("category")
    return model.predict(X)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results", "dataset.parquet"))
    ap.add_argument("--out", default=None)
    ap.add_argument("--holdout", default="picorv32")
    ap.add_argument("--data-nets-only", action="store_true", help="evaluate on SIGNAL nets only")
    a = ap.parse_args()
    out = a.out or os.path.join(os.path.dirname(os.path.abspath(a.data)), "model")
    os.makedirs(out, exist_ok=True)

    df = pd.read_parquet(a.data)
    df = df[df["join_how"] != "none"].copy()
    df = df[df["driver_kind"] != "none"].copy()
    designs = sorted(df["design"].unique())
    print(f"[train] rows={len(df)} designs={designs} runs={df['run'].nunique()} positives={int(df['y'].sum())} ({df['y'].mean():.3%})")

    report = {"designs": designs, "rows": int(len(df)), "lodo": {}, "baselines": {}}
    curves = {}
    for held in designs:
        tr, te = df[df["design"] != held], df[df["design"] == held]
        if te["y"].sum() == 0 or tr["y"].sum() == 0 or len(te) == 0:
            report["lodo"][held] = {"skipped": True, "n_test": int(len(te)), "pos_test": int(te["y"].sum()), "pos_train": int(tr["y"].sum())}
            continue
        model = fit(tr)
        p = predict(model, te)
        mask = (te["sigtype"] == "SIGNAL").values if a.data_nets_only else np.ones(len(te), dtype=bool)
        y_te = te["y"].values[mask]
        res = {"model": evaluate(y_te, p[mask]), "train_rows": int(len(tr)), "train_runs": int(tr["run"].nunique()), "test_runs": int(te["run"].nunique())}
        for bname, col in BASELINES.items():
            res[bname] = evaluate(y_te, te[col].fillna(0).values[mask])
        report["lodo"][held] = res
        # recall-vs-flagged curve for the figure
        order = np.argsort(-p[mask])
        cum = np.cumsum(y_te[order]) / max(1, y_te.sum())
        fr = np.arange(1, len(order) + 1) / len(order)
        pts = [(float(fr[i]), float(cum[i])) for i in np.unique(np.linspace(0, len(order) - 1, 400).astype(int))]
        curves[held] = {"model": pts}
        for bname, col in BASELINES.items():
            s = te[col].fillna(0).values[mask]
            o = np.argsort(-s)
            c = np.cumsum(y_te[o]) / max(1, y_te.sum())
            curves[held][bname] = [(float(fr[i]), float(c[i])) for i in np.unique(np.linspace(0, len(o) - 1, 400).astype(int))]
        m = res["model"]
        print(f"[train] holdout={held:11s} n={m['n']:7d} pos={m['positives']:5d} PR-AUC={m.get('pr_auc', float('nan')):.3f} "
              f"R@2%={m.get('recall@2%', float('nan')):.3f} R@5%={m.get('recall@5%', float('nan')):.3f} "
              f"catch90@={m.get('frac_to_catch_90', float('nan')):.3%} | est_slew R@5%={res['est_load_slew_ratio'].get('recall@5%', float('nan')):.3f}")

    # hero model: train on everything except the holdout; also a deploy model on all data
    tr = df[df["design"] != a.holdout]
    if tr["y"].sum() > 0:
        hero = fit(tr)
        hero.save_model(os.path.join(out, f"model_holdout_{a.holdout}.txt"))
        imp = sorted(zip(FEATURES, hero.feature_importance("gain")), key=lambda t: -t[1])
        report["feature_importance_gain"] = [(f, float(g)) for f, g in imp]
    if df["y"].sum() > 0:
        full = fit(df)
        full.save_model(os.path.join(out, "model_all.txt"))
    json.dump(report, open(os.path.join(out, "report.json"), "w"), indent=1)
    json.dump(curves, open(os.path.join(out, "curves.json"), "w"))
    json.dump({"features": FEATURES, "baselines": BASELINES}, open(os.path.join(out, "features.json"), "w"), indent=1)
    print(f"[train] wrote {out}/report.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
