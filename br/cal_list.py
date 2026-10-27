#!/usr/bin/env python3
"""Equal-budget repair list from a learned RC calibration (no GBM): for each Round-3 base, rank the base run's signal
nets by rule R8 x k_net, where k_net = exp(per-layer + length/fanout/density log-linear fit of extracted/estimated net cap)
fit on every other design's at-risk signal nets (R8 > 0.5; the 'rc_layer_len' rung of br/calib_ladder.py), and keep the
top N nets, N = the size of the model's p >= 0.5 list for that base (results/<base>/flagged_thr500-70.json).
Writes farm/lists/<base>/cal.json (arm lst-cal-70) and farm/lists/<base>/calt.json (arm lst-calt-70: every net whose
calibrated R8 >= 1.0, the calibration's own threshold), and prints overlap and baseline-run recall of the lists.

Usage: python3 br/cal_list.py [--data results/analysis/farm_dataset/dataset.parquet] [--write]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import analysis_common as C  # noqa: E402
from calib_ladder import COLS, design_matrix  # noqa: E402

BASES = {"d3-salsa20-000": "salsa20", "d3-des-000": "des", "d3-y_huff-000": "y_huff",
         "d3-ocs_blitter-000": "ocs_blitter", "d3-bm64-000": "BM64", "d3-md5-000": "md5"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="results/analysis/farm_dataset/dataset.parquet")
    ap.add_argument("--results", default="results")
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    df = pd.read_parquet(a.data, columns=COLS + ["net"])
    df = df[(df["join_how"] != "none") & (df["driver_kind"] != "none") & df["run"].str.startswith(C.DATA_PREFIXES)]
    df = df[df["sigtype"] == "SIGNAL"].reset_index(drop=True)
    df["r8"] = C.r8(df)
    ok = (df["net_cap_pf_max"] > 0) & (df["act_net_cap_pf_max"] > 0)
    df["logk"] = np.where(ok, np.log(df["act_net_cap_pf_max"].where(ok, 1) / df["net_cap_pf_max"].where(ok, 1)), np.nan)
    out = {}
    for base, D in BASES.items():
        tr = df[(df["design"] != D) & (df["r8"] > 0.5) & df["logk"].notna()]
        X = np.column_stack([np.ones(len(tr)), design_matrix(tr, "rc_layer_len")])
        b, *_ = np.linalg.lstsq(X, tr["logk"].to_numpy(float), rcond=None)
        ev = df[df["run"] == base].reset_index(drop=True)
        if ev.empty:
            print(f"{base}: base run not in the dataset")
            continue
        k = np.exp(np.column_stack([np.ones(len(ev)), design_matrix(ev, "rc_layer_len")]) @ b)
        score = ev["r8"].to_numpy(float) * k
        model = json.load(open(os.path.join(a.results, base, "flagged_thr500-70.json")))
        N = len(model)
        order = np.argsort(-score, kind="stable")
        cal = [str(n) for n in ev["net"].to_numpy()[order[:N]]]
        calt = [str(n) for n in ev["net"].to_numpy()[score >= 1.0]]
        viol = set(ev.loc[ev["y"] == 1, "net"])
        ms, cs = set(model), set(cal)
        rec = {"N": N, "jaccard": round(len(ms & cs) / len(ms | cs), 3),
               "model_recall_base": round(len(ms & viol) / max(1, len(viol)), 3),
               "cal_recall_base": round(len(cs & viol) / max(1, len(viol)), 3), "violators_base": len(viol),
               "cal_threshold_score": round(float(score[order[N - 1]]), 3),
               "model_names_found": round(len(ms & set(ev["net"])) / max(1, N), 3),
               "calt_N": len(calt), "calt_recall_base": round(len(set(calt) & viol) / max(1, len(viol)), 3)}
        out[base] = rec
        print(base, json.dumps(rec))
        if a.write:
            d = os.path.join("farm", "lists", base)
            os.makedirs(d, exist_ok=True)
            json.dump(cal, open(os.path.join(d, "cal.json"), "w"))
            json.dump(calt, open(os.path.join(d, "calt.json"), "w"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
