#!/usr/bin/env python3
"""Score a baseline run's post-GRT nets with a trained model and emit the flagged-net list.

Usage: score.py --model results/model/model_holdout_picorv32.txt --run-results results/<tag>
                [--frac 0.05 | --threshold 0.5] [--out flagged.json] [--data-nets-only]
Flags the top fraction of nets (or all nets above a probability threshold); clock
nets are never flagged (the intervention is for data nets).
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_dataset import load_run  # noqa: E402
from train import FEATURES  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--run-results", required=True)
    ap.add_argument("--frac", type=float, default=None)
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--tiers", default=None, help="e.g. 0.02:70,0.05:40 -> top 2%% at 70%%, next 3%% at 40%%; writes a tiers JSON")
    ap.add_argument("--rule-fanout", action="store_true", help="also flag every net whose post-GRT fanout already exceeds MAX_FANOUT (deterministic rule, Round 2 proposal)")
    a = ap.parse_args()
    import lightgbm as lgb

    model = lgb.Booster(model_file=a.model)
    rows, stats = load_run(os.path.abspath(a.run_results))
    df = pd.DataFrame(rows)
    df = df[(df["sigtype"] == "SIGNAL") & (df["driver_kind"] != "none")].copy()
    X = df[FEATURES].copy()
    X["driver_class"] = pd.Categorical(X["driver_class"], categories=model.pandas_categorical[0]) if model.pandas_categorical else X["driver_class"].astype("category")
    df["p"] = model.predict(X)
    if a.rule_fanout:
        df.loc[df["fanout_ratio"].fillna(0) > 1.0, "p"] = 1.0 + df["p"]  # rule nets rank first
    df = df.sort_values("p", ascending=False)
    if a.threshold is not None:
        flagged = df[df["p"] >= a.threshold]
    else:
        k = max(1, int(round((a.frac or 0.05) * len(df))))
        flagged = df.head(k)
    out = a.out or os.path.join(os.path.abspath(a.run_results), "flagged.json")
    if a.tiers:
        tiers, prev = [], 0
        for item in a.tiers.split(","):
            k, h = item.split(":")
            upto = max(prev, int(round(float(k) * len(df))))
            tiers.append({"nets": df.iloc[prev:upto]["net"].tolist(), "slew_pct": float(h), "cap_pct": float(h), "frac_upto": float(k)})
            prev = upto
        json.dump({"tiers": tiers}, open(out, "w"))
        flagged = df.iloc[:prev]
    else:
        json.dump(flagged["net"].tolist(), open(out, "w"))
    summ = {
        "run": stats["run"], "nets_scored": int(len(df)), "flagged": int(len(flagged)), "rule_fanout": bool(a.rule_fanout),
        "rule_fanout_nets": int((df["fanout_ratio"].fillna(0) > 1.0).sum()) if a.rule_fanout else 0,
        "flag_frac": float(len(flagged) / max(1, len(df))), "min_p_flagged": float(flagged["p"].min()) if len(flagged) else None,
        "true_positives_in_flagged": int(flagged["y"].sum()), "positives_total": int(df["y"].sum()),
        "recall_of_flagged": float(flagged["y"].sum() / max(1, df["y"].sum())),
        "out": out,
    }
    df[["net", "net_s", "p", "y", "fanout", "hpwl_um", "worst_load_slew_ratio", "driver_class"]].to_csv(os.path.splitext(out)[0] + ".scores.csv", index=False)
    print(json.dumps(summ, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
