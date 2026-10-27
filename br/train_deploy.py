#!/usr/bin/env python3
"""Fit the deployment model: one classifier (and the signoff-ratio regressor) on every run of every
design in a dataset, with the same features and hyper-parameters as br/train.py. Memory-lean: loads
only the columns it needs.

Usage: train_deploy.py --data dataset.parquet --out models/model_all_v5.txt [--exclude-design d ...]
Writes <out>, reg_<basename of out> next to it, and <out>.json (designs, runs, rows, positives).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train import FEATURES, fit, fit_reg  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--exclude-design", action="append", default=[])
    ap.add_argument("--no-reg", action="store_true")
    a = ap.parse_args()
    cols = sorted(set(FEATURES + ["y", "design", "run", "join_how", "driver_kind", "sigtype", "act_load_slew_ratio"]))
    df = pd.read_parquet(a.data, columns=cols)  # float64 kept: driver_slack_ns uses 1e39 for "unconstrained"
    df = df[(df["join_how"] != "none") & (df["driver_kind"] != "none")]
    if a.exclude_design:
        df = df[~df["design"].isin(a.exclude_design)]
    t0 = time.time()
    model = fit(df)
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    model.save_model(a.out)
    reg_path = os.path.join(os.path.dirname(os.path.abspath(a.out)), "reg_" + os.path.basename(a.out).replace("model_", ""))
    if not a.no_reg and df["act_load_slew_ratio"].notna().sum() > 200:
        fit_reg(df).save_model(reg_path)
    man = {"data": os.path.abspath(a.data), "designs": sorted(df["design"].unique().tolist()),
           "runs": int(df["run"].nunique()), "rows": int(len(df)), "positives": int(df["y"].sum()),
           "runs_per_design": {d: int(n) for d, n in df.groupby("design")["run"].nunique().items()},
           "excluded": a.exclude_design, "seconds": round(time.time() - t0, 1),
           "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    json.dump(man, open(a.out + ".json", "w"), indent=1)
    print(json.dumps(man, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
