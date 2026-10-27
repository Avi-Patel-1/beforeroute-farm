#!/usr/bin/env python3
"""Prediction-side comparison at the post-GRT checkpoint: the model (GBM on default-RC checkpoint features) vs the
re-timed estimate (rule R8 on checkpoint features dumped with LAYERS_RC = wire cap x K/100) vs the default estimate (R8),
scored against the baseline run's own signoff labels (signal nets).

Usage: retimed_compare.py --base <base_tag> --model <model.txt> [--k 213] [--results results]
       [--ckpt results/<base>-ckpt] [--ckptrc results/<base>-ckptrc<k>] [--json out.json]
Reports catch-95 (fraction of nets flagged, top of each ranking, to catch 95% of violators), recall at 5%, and the list
size and recall of each method's own threshold: model p >= 0.5; re-timed R8 >= 1.0 (its own violators) and >= 0.9
(the stock 10% margin); default R8 >= 1.0.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_dataset import load_run  # noqa: E402
from train import FEATURES  # noqa: E402


def frame(rdir):
    rows, _ = load_run(rdir)
    df = pd.DataFrame(rows)
    return df[(df["sigtype"] == "SIGNAL") & (df["driver_kind"] != "none")].copy()


def r8(df):
    return df[["worst_load_slew_ratio", "driver_slew_ratio", "cap_ratio"]].fillna(0).astype(float).max(axis=1).to_numpy()


def catch(y, s, q=0.95):
    o = np.argsort(-s, kind="stable")
    c = np.cumsum(y[o])
    need = q * y.sum()
    k = int(np.searchsorted(c, need) + 1)
    return k / len(y)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--k", default="213")
    ap.add_argument("--results", default="results")
    ap.add_argument("--ckpt", default=None)
    ap.add_argument("--ckptrc", default=None)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    R = a.results
    ck = a.ckpt or os.path.join(R, f"{a.base}-ckpt")
    rc = a.ckptrc or os.path.join(R, f"{a.base}-ckptrc{a.k}")
    lab = json.load(open(os.path.join(R, a.base, "labels.json")))
    viol = {r["net"] for r in lab["nets"] if r.get("violated") and r.get("sigtype_s") == "SIGNAL"}
    import lightgbm as lgb
    m = lgb.Booster(model_file=a.model)
    d0 = frame(ck)
    X = d0[FEATURES].copy()
    X["driver_class"] = pd.Categorical(X["driver_class"], categories=m.pandas_categorical[0]) if m.pandas_categorical else X["driver_class"].astype("category")
    d0["p"] = m.predict(X)
    d0["r8_default"] = r8(d0)
    d1 = frame(rc)[["net", "worst_load_slew_ratio", "driver_slew_ratio", "cap_ratio"]]
    d1 = d1.assign(r8_cal=r8(d1))[["net", "r8_cal"]]
    df = d0.merge(d1, on="net", how="inner")
    y = df["net"].isin(viol).to_numpy().astype(int)
    n, pos = len(df), int(y.sum())
    out = {"base": a.base, "nets": n, "violators_matched": pos, "violators_signoff": len(viol), "floor": 0.95 * pos / n}
    for name, s in (("model", df["p"].to_numpy()), ("retimed_R8", df["r8_cal"].to_numpy()), ("default_R8", df["r8_default"].to_numpy())):
        k5 = max(1, int(round(0.05 * n)))
        o = np.argsort(-s, kind="stable")
        out[name] = {"catch95": catch(y, s), "recall_at_5pct": float(y[o[:k5]].sum() / max(1, pos))}
    for name, sel in (("model_p>=0.5", df["p"] >= 0.5), ("retimed_R8>=1.0", df["r8_cal"] >= 1.0),
                      ("retimed_R8>=0.9", df["r8_cal"] >= 0.9), ("default_R8>=1.0", df["r8_default"] >= 1.0)):
        sel = sel.to_numpy()
        out[name] = {"flagged": int(sel.sum()), "recall": float(y[sel].sum() / max(1, pos))}
    print(json.dumps(out, indent=1))
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
