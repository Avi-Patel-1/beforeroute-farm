#!/usr/bin/env python3
"""Smoke test / sanity summary for analyze.yml: per-design and per-run counts of the rebuilt dataset.

Usage: analysis_smoke.py --data dataset.parquet --out out/ [--designs a,b]
Writes <out>/dataset_runs.csv (one row per run: design, nets, signal nets, violating signal nets)
and <out>/dataset_summary.json.
"""
from __future__ import annotations

import argparse
import json
import os

import pandas as pd


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--designs", default="")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    df = pd.read_parquet(a.data, columns=["run", "design", "sigtype", "join_how", "driver_kind", "y"])
    if a.designs:
        df = df[df["design"].isin(a.designs.split(","))]
    f = df[(df["join_how"] != "none") & (df["driver_kind"] != "none")]
    sig = f[f["sigtype"] == "SIGNAL"]
    runs = (f.groupby("run").agg(design=("design", "first"), nets=("y", "size"))
            .join(sig.groupby("run").agg(signal_nets=("y", "size"), signal_viol=("y", "sum"))).reset_index())
    runs.to_csv(os.path.join(a.out, "dataset_runs.csv"), index=False)
    per = runs.groupby("design").agg(runs=("run", "size"), signal_nets=("signal_nets", "sum"),
                                     signal_viol=("signal_viol", "sum"),
                                     runs_with_viol=("signal_viol", lambda s: int((s > 0).sum())))
    summ = {"rows": int(len(df)), "rows_filtered": int(len(f)), "runs": int(df["run"].nunique()),
            "signal_viol": int(sig["y"].sum()), "per_design": per.reset_index().to_dict(orient="records")}
    json.dump(summ, open(os.path.join(a.out, "dataset_summary.json"), "w"), indent=1)
    print(per.to_string())
    print(f"rows={summ['rows']} runs={summ['runs']} signal violators={summ['signal_viol']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
