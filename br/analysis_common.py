"""Shared helpers for the farm analysis scripts (learning_curve.py, ablation_ladder.py).

- Data: the standard filter (join_how != 'none' & driver_kind != 'none'), data runs only
  (tags d1-/d2-/d3-/d4-/d3b-/d4b-), only the columns the analyses need.
- Model: br/train.py's fit()/predict()/evaluate(). fit_lgb() trains LightGBM with exactly the
  parameters br/train.fit() would use on the same training frame (captured from fit() itself),
  on an arbitrary feature subset and an optional num_boost_round / num_threads override.
- Metrics: pooled over the evaluation runs, and per run (median / IQR over runs with >= 1
  violator), plus calibration of the expected violator count per run.
"""
from __future__ import annotations

import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import train as T  # noqa: E402

FEATURES = list(T.FEATURES)
DATA_PREFIXES = ("d1-", "d2-", "d3-", "d4-", "d3b-", "d4b-")
GEOMETRY = ["hpwl_um", "bbox_w_um", "bbox_h_um", "density_mean", "density_max", "guide_len_um",
            "guide_frac_li1", "guide_frac_met1", "guide_frac_met2", "guide_frac_met3up"]
# the timer's own post-GRT estimate (slews, caps, ratios to the library/SDC limits) + fanout; no geometry, no cell identity
ESTIMATE = ["worst_load_slew_ratio", "worst_load_slew_ns", "driver_slew_ratio", "driver_slew_ns", "cap_ratio",
            "fanout_ratio", "fanout", "net_cap_pf_max", "net_cap_pf_tt", "pin_cap_pf_max",
            "driver_slew_limit_lib_ns", "driver_cap_limit_lib_pf", "driver_slack_ns"]
NO_GEOMETRY = [f for f in FEATURES if f not in GEOMETRY]
LR_FEATURES = ["worst_load_slew_ratio", "driver_slew_ratio", "cap_ratio", "fanout_ratio", "hpwl_um", "guide_len_um",
               "guide_frac_li1", "guide_frac_met1", "guide_frac_met2", "guide_frac_met3up", "fanout", "density_mean"]
R8_COLS = ["worst_load_slew_ratio", "driver_slew_ratio", "cap_ratio"]
KEY_METRICS = ("recall@5%", "frac_to_catch_95", "pr_auc")


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def load(path: str, all_runs: bool = False, float32: bool = False) -> pd.DataFrame:
    """float32=True downcasts float64 feature columns (about half the memory; for small machines)."""
    cols = sorted(set(["run", "design", "sigtype", "join_how", "driver_kind", "y"] + FEATURES + LR_FEATURES))
    df = pd.read_parquet(path, columns=cols)
    if float32:
        f64 = [c for c in df.columns if df[c].dtype == np.float64]
        lim = float(np.finfo(np.float32).max)
        df[f64] = df[f64].clip(-lim, lim).astype(np.float32)
    df = df[(df["join_how"] != "none") & (df["driver_kind"] != "none")]
    if not all_runs:
        df = df[df["run"].str.startswith(DATA_PREFIXES)]
    df = df.drop(columns=["join_how", "driver_kind"]).reset_index(drop=True)
    df["y"] = df["y"].astype(np.int8)
    df["is_signal"] = (df["sigtype"] == "SIGNAL").values
    return df


def run_table(df: pd.DataFrame) -> pd.DataFrame:
    """One row per run: design, rows, positives (all nets), signal nets, signal positives."""
    g = df.groupby("run", sort=True)
    t = g.agg(design=("design", "first"), rows=("y", "size"), pos=("y", "sum"))
    s = df[df["is_signal"]].groupby("run").agg(sig_rows=("y", "size"), sig_pos=("y", "sum"))
    return t.join(s).fillna({"sig_rows": 0, "sig_pos": 0}).reset_index()


# ---------------------------------------------------------------- models
class _Captured(Exception):
    pass


def train_fit_params(df_train: pd.DataFrame):
    """The (params, num_boost_round) br/train.fit() would pass to lightgbm.train for this training frame."""
    import lightgbm as lgb

    box = {}
    orig = lgb.train

    def spy(params, train_set, num_boost_round=100, *args, **kw):
        box["params"], box["rounds"] = dict(params), num_boost_round
        raise _Captured()

    lgb.train = spy
    try:
        T.fit(df_train)
    except _Captured:
        pass
    finally:
        lgb.train = orig
    return box["params"], box["rounds"]


def fit_lgb(df_train: pd.DataFrame, feats=None, rounds: int | None = None, threads: int | None = None):
    """LightGBM with br/train.fit()'s parameters on `feats` (default: train.FEATURES)."""
    import lightgbm as lgb

    feats = list(feats or FEATURES)
    params, rounds0 = train_fit_params(df_train)
    if threads:
        params["num_threads"] = int(threads)
    X = df_train[feats].copy()
    cat = "auto"
    if "driver_class" in feats:
        X["driver_class"] = X["driver_class"].astype("category")
        cat = ["driver_class"]
    y = df_train["y"].astype(int)
    model = lgb.train(params, lgb.Dataset(X, y, categorical_feature=cat), num_boost_round=int(rounds or rounds0))
    model._br_feats = feats
    model._br_spw = float(params.get("scale_pos_weight", 1.0))
    model._br_rounds = int(rounds or rounds0)
    return model


def predict_lgb(model, df: pd.DataFrame) -> np.ndarray:
    feats = getattr(model, "_br_feats", FEATURES)
    X = df[feats].copy()
    if "driver_class" in feats:
        X["driver_class"] = (pd.Categorical(X["driver_class"], categories=model.pandas_categorical[0])
                             if model.pandas_categorical else X["driver_class"].astype("category"))
    return model.predict(X)


def lr_matrix(df: pd.DataFrame) -> np.ndarray:
    X = df[LR_FEATURES].astype(float).fillna(0.0).clip(lower=0.0).values
    return np.log1p(X)


def fit_lr(df_train: pd.DataFrame):
    """Learned linear calibration of the estimate: standardized log1p features, balanced logistic regression."""
    from sklearn.linear_model import LogisticRegression
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    y = df_train["y"].astype(int).values
    m = make_pipeline(StandardScaler(), LogisticRegression(C=1.0, class_weight="balanced", max_iter=3000))
    m.fit(lr_matrix(df_train), y)
    m._br_spw = float((1 - y).sum() / max(1, y.sum()))  # balanced weights = this positive up-weighting
    return m


def predict_lr(model, df: pd.DataFrame) -> np.ndarray:
    return model.predict_proba(lr_matrix(df))[:, 1]


def r8(df: pd.DataFrame) -> np.ndarray:
    return df[R8_COLS].astype(float).fillna(0.0).max(axis=1).values


def prior_correct(p: np.ndarray, spw: float) -> np.ndarray:
    """Undo positive up-weighting (scale_pos_weight / balanced class weights): odds_true = odds_weighted / spw."""
    p = np.clip(np.asarray(p, dtype=float), 1e-12, 1 - 1e-12)
    return p / (p + (1.0 - p) * spw)


# ---------------------------------------------------------------- metrics
def _q(v, q):
    v = [x for x in v if x == x]
    return float(np.quantile(v, q)) if v else float("nan")


def eval_block(ev: pd.DataFrame, score: np.ndarray, prob: np.ndarray | None = None, per_run: bool = True) -> dict:
    """ev: evaluation rows (signal nets) with 'run' and 'y'; score aligned with ev.
    Returns pooled metrics, per-run median/IQR of the key metrics, and (if prob) calibration of
    the expected violator count per run: |sum p - actual| / actual (runs with >= 1 violator)."""
    y = ev["y"].values.astype(int)
    score = np.asarray(score, dtype=float)
    out = {"pooled": T.evaluate(y, score), "n_runs": int(ev["run"].nunique())}
    if per_run:
        runs = ev["run"].values
        order = np.argsort(runs, kind="stable")
        r_sorted = runs[order]
        bounds = np.flatnonzero(np.r_[True, r_sorted[1:] != r_sorted[:-1], True])
        per = []
        for i in range(len(bounds) - 1):
            idx = order[bounds[i]:bounds[i + 1]]
            yy = y[idx]
            rec = {"run": str(r_sorted[bounds[i]]), "n": int(len(idx)), "positives": int(yy.sum())}
            if yy.sum() > 0:
                m = T.evaluate(yy, score[idx])
                rec.update({k: m.get(k) for k in KEY_METRICS})
            if prob is not None and yy.sum() > 0:
                rec["sum_p"] = float(np.sum(prob[idx]))
                rec["cal_err"] = abs(rec["sum_p"] - yy.sum()) / yy.sum()
                rec["sum_ratio"] = rec["sum_p"] / yy.sum()
            per.append(rec)
        pos_runs = [r for r in per if r["positives"] > 0]
        summ = {"n_runs_with_pos": len(pos_runs)}
        for k in KEY_METRICS:
            v = [r[k] for r in pos_runs if r.get(k) is not None]
            summ[k] = {"median": _q(v, 0.5), "q25": _q(v, 0.25), "q75": _q(v, 0.75)}
        if prob is not None:
            for k in ("cal_err", "sum_ratio"):
                v = [r[k] for r in pos_runs if k in r]
                summ[k] = {"median": _q(v, 0.5), "q25": _q(v, 0.25), "q75": _q(v, 0.75)}
        out["per_run"] = summ
        out["runs"] = per
    return out


def flat(block: dict, prefix: str = "") -> dict:
    """Flatten an eval_block into CSV columns."""
    p = block["pooled"]
    row = {f"{prefix}eval_n": p.get("n"), f"{prefix}eval_pos": p.get("positives"),
           f"{prefix}pooled_recall5": p.get("recall@5%"), f"{prefix}pooled_catch95": p.get("frac_to_catch_95"),
           f"{prefix}pooled_prauc": p.get("pr_auc"), f"{prefix}pooled_recall2": p.get("recall@2%"),
           f"{prefix}pooled_catch90": p.get("frac_to_catch_90"), f"{prefix}pooled_rocauc": p.get("roc_auc")}
    pr = block.get("per_run")
    if pr:
        row[f"{prefix}n_runs_pos"] = pr["n_runs_with_pos"]
        for k, short in (("recall@5%", "recall5"), ("frac_to_catch_95", "catch95"), ("pr_auc", "prauc"),
                         ("cal_err", "calerr"), ("sum_ratio", "sumratio")):
            if k in pr:
                for s in ("median", "q25", "q75"):
                    row[f"{prefix}run_{short}_{s[:3] if s == 'median' else s}"] = pr[k][s]
    return row
