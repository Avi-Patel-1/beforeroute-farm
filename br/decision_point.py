#!/usr/bin/env python3
"""Decision-point check: score the features dumped at the post-GRT checkpoint itself (arm `dmp`,
before antenna-diode insertion) and compare with the features the arms were scored on
(the STAMidPNR-3 input of the baseline, after antenna repair).

Usage: decision_point.py --base <base_tag> --model <model.txt> [--results results] [--frac 0.05]
Reads results/<base>/ (baseline view + signoff labels) and results/<base>-dmp/nets.jsonl.gz.
Writes results/<base>-dmp/decision_point.json and prints it.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import sys
import tempfile

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_dataset import load_run  # noqa: E402
from train import FEATURES  # noqa: E402


def frame(rdir):
    rows, _ = load_run(rdir)
    df = pd.DataFrame(rows)
    return df[(df["sigtype"] == "SIGNAL") & (df["driver_kind"] != "none")].copy()


def score(df, model):
    X = df[FEATURES].copy()
    cats = model.pandas_categorical[0] if model.pandas_categorical else None
    X["driver_class"] = pd.Categorical(X["driver_class"], categories=cats) if cats is not None else X["driver_class"].astype("category")
    return df.assign(p=model.predict(X)).sort_values("p", ascending=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--results", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
    ap.add_argument("--frac", type=float, default=0.05)
    a = ap.parse_args()
    import lightgbm as lgb

    model = lgb.Booster(model_file=a.model)
    base_dir = os.path.join(a.results, a.base)
    dmp_dir = os.path.join(a.results, a.base + "-dmp")
    src = os.path.join(dmp_dir, "nets.jsonl.gz")
    if not os.path.exists(src):
        src = os.path.join(dmp_dir, "nets.jsonl")
    if not os.path.exists(src):
        raise SystemExit(f"no decision-point dump in {dmp_dir}")
    with tempfile.TemporaryDirectory() as td:
        for fn in ("job.json", "labels.json", "final_nets.json", "resolved.json", "metrics.json"):
            shutil.copy2(os.path.join(base_dir, fn), os.path.join(td, fn))
        shutil.copy2(os.path.join(dmp_dir, "dump_summary.json"), os.path.join(td, "dump_summary.json"))
        opener = gzip.open if src.endswith(".gz") else open
        with opener(src, "rt") as fi, open(os.path.join(td, "nets.jsonl"), "w") as fo:
            shutil.copyfileobj(fi, fo)
        ck = frame(td)
    mid = frame(base_dir)
    ck, mid = score(ck, model), score(mid, model)
    out = {"base": a.base, "model": os.path.basename(a.model), "signal_nets_checkpoint": int(len(ck)),
           "signal_nets_stamidpnr3": int(len(mid)), "violators": int(mid["y"].sum())}
    for name, sel in (("top%g%%" % (a.frac * 100), "frac"), ("p>=0.5", "thr"), ("auto(sum p)", "exp")):
        sets, rec = {}, {}
        for tag, df in (("checkpoint", ck), ("stamidpnr3", mid)):
            if sel == "frac":
                f = df.head(max(1, int(round(a.frac * len(df)))))
            elif sel == "thr":
                f = df[df["p"] >= 0.5]
            else:
                f = df.head(max(1, int(round(float(df["p"].clip(upper=1).sum())))))
            sets[tag] = set(f["net"])
            rec[tag] = float(f["y"].sum() / max(1, df["y"].sum()))
        inter = len(sets["checkpoint"] & sets["stamidpnr3"])
        union = len(sets["checkpoint"] | sets["stamidpnr3"])
        out[name] = {"n_checkpoint": len(sets["checkpoint"]), "n_stamidpnr3": len(sets["stamidpnr3"]),
                     "jaccard": inter / max(1, union), "recall_checkpoint": rec["checkpoint"], "recall_stamidpnr3": rec["stamidpnr3"]}
    # per-net feature drift between the two views (nets matched by name)
    m = ck[["net", "worst_load_slew_ratio", "net_cap_pf_max", "fanout", "p"]].merge(
        mid[["net", "worst_load_slew_ratio", "net_cap_pf_max", "fanout", "p"]], on="net", suffixes=("_ck", "_mid"))
    rel = lambda c: (m[c + "_ck"].astype(float) - m[c + "_mid"].astype(float)).abs() / m[c + "_mid"].astype(float).abs().clip(lower=1e-9)
    out["matched_nets"] = int(len(m))
    out["drift"] = {
        "slew_ratio_rel_median": float(np.nanmedian(rel("worst_load_slew_ratio"))),
        "slew_ratio_rel_p99": float(np.nanpercentile(rel("worst_load_slew_ratio"), 99)),
        "net_cap_rel_median": float(np.nanmedian(rel("net_cap_pf_max"))),
        "fanout_changed_nets": int((m["fanout_ck"] != m["fanout_mid"]).sum()),
        "p_abs_diff_p99": float(np.nanpercentile((m["p_ck"] - m["p_mid"]).abs(), 99)),
    }
    path = os.path.join(dmp_dir, "decision_point.json")
    json.dump(out, open(path, "w"), indent=1)
    print(json.dumps(out, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
