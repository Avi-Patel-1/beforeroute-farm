#!/usr/bin/env python3
"""Would a better RC calibration of the post-global-route estimate close the gap to the learned model?

Post-hoc prediction analysis on the farm dataset (leave-one-design-out, the same held-out designs, signal nets and
catch-95 metric as br/ablation_ladder.py). Each rung multiplies rule R8's score (max of the estimated load slew ratio,
driver slew ratio and cap ratio) by a per-net cap correction k_net = predicted extracted / estimated net cap, fit on
the other designs' at-risk signal nets (R8 > 0.5) by least squares on log(extracted / estimated cap):
  rc_global     one scale (ranking identical to R8; only the threshold moves)
  rc_layer      per routing layer: log k = sum_l b_l * guide_frac_l        (li1, met1, met2, met3+)
  rc_layer_len  + log guide length, log HPWL, log fanout, density           (length/fanout-dependent calibration)
  rc_wire146    the Addendum-9 calibration as applied in the arms: wire cap (net cap - load pin cap) x 1.461
  rc_wire       one wire-cap scale s fit as median((extracted - pin) / (estimated - pin)) on the training nets
  rc_oracle     the true extracted/estimated ratio of each net (upper bound of any cap calibration)
Slew is taken to scale with cap (driver-dominated RC), so k_net * R8 approximates the calibrated estimate's R8.

Usage: python3 br/calib_ladder.py --data results/analysis/farm_dataset/dataset.parquet \
           --ablation agents/analysis/farm/ablation_summary.csv --out agents/analysis/calib_ladder.json
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

COLS = ["run", "design", "sigtype", "join_how", "driver_kind", "y", "worst_load_slew_ratio", "driver_slew_ratio",
        "cap_ratio", "net_cap_pf_max", "act_net_cap_pf_max", "guide_frac_li1", "guide_frac_met1", "guide_frac_met2",
        "guide_frac_met3up", "guide_len_um", "hpwl_um", "fanout", "density_mean", "pin_cap_pf_max"]
LAYERS = ["guide_frac_li1", "guide_frac_met1", "guide_frac_met2", "guide_frac_met3up"]


def design_matrix(df, kind):
    L = df[LAYERS].fillna(0).to_numpy(float)
    if kind == "rc_layer":
        return L
    extra = np.column_stack([np.log1p(df["guide_len_um"].fillna(0).to_numpy(float)),
                             np.log1p(df["hpwl_um"].fillna(0).to_numpy(float)),
                             np.log1p(df["fanout"].fillna(0).to_numpy(float)),
                             df["density_mean"].fillna(0).to_numpy(float)])
    return np.column_stack([L, extra])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="results/analysis/farm_dataset/dataset.parquet")
    ap.add_argument("--ablation", default="agents/analysis/farm/ablation_summary.csv")
    ap.add_argument("--out", default="agents/analysis/calib_ladder.json")
    a = ap.parse_args()
    df = pd.read_parquet(a.data, columns=COLS)
    df = df[(df["join_how"] != "none") & (df["driver_kind"] != "none") & df["run"].str.startswith(C.DATA_PREFIXES)]
    df = df[df["sigtype"] == "SIGNAL"].drop(columns=["join_how", "driver_kind", "sigtype"]).reset_index(drop=True)
    df["y"] = df["y"].astype(np.int8)
    df["r8"] = C.r8(df)
    ok = (df["net_cap_pf_max"] > 0) & (df["act_net_cap_pf_max"] > 0)
    df["logk"] = np.where(ok, np.log(df["act_net_cap_pf_max"].where(ok, 1) / df["net_cap_pf_max"].where(ok, 1)), np.nan)
    ab = pd.read_csv(a.ablation)
    designs = sorted(ab["holdout"].unique())
    piv = ab.pivot_table(index="holdout", columns="rung_name", values="pooled_catch95")
    out = {"note": __doc__.split("\n\n")[1].strip(), "designs": {}}
    for D in designs:
        tr = df[(df["design"] != D) & (df["r8"] > 0.5) & df["logk"].notna()]
        ev = df[df["design"] == D].reset_index(drop=True)
        res = {"n": int(len(ev)), "pos": int(ev["y"].sum()), "floor": 0.95 * float(ev["y"].mean())}
        k0 = float(np.exp(np.median(tr["logk"])))
        res["k_global"] = k0
        res["rc_global"] = C.eval_block(ev, ev["r8"].to_numpy(float) * k0, per_run=False)["pooled"]["frac_to_catch_95"]
        for kind in ("rc_layer", "rc_layer_len"):
            X = design_matrix(tr, kind)
            if kind == "rc_layer_len":
                X = np.column_stack([np.ones(len(X)), X])
            b, *_ = np.linalg.lstsq(X, tr["logk"].to_numpy(float), rcond=None)
            Xe = design_matrix(ev, kind)
            if kind == "rc_layer_len":
                Xe = np.column_stack([np.ones(len(Xe)), Xe])
            pred_tr = X @ b
            resid = tr["logk"].to_numpy(float) - pred_tr
            res[kind + "_r2"] = float(1 - resid.var() / tr["logk"].var())
            k = np.exp(Xe @ b)
            res[kind] = C.eval_block(ev, ev["r8"].to_numpy(float) * k, per_run=False)["pooled"]["frac_to_catch_95"]
            if kind == "rc_layer":
                res["rc_layer_coef"] = dict(zip(["li1", "met1", "met2", "met3+"], [float(np.exp(x)) for x in b]))
        est, pin = ev["net_cap_pf_max"].fillna(0).to_numpy(float), ev["pin_cap_pf_max"].fillna(0).to_numpy(float)
        wire = np.clip(est - pin, 0, None)
        safe_est = np.where(est > 0, est, 1.0)
        t_est, t_pin = tr["net_cap_pf_max"].to_numpy(float), tr["pin_cap_pf_max"].fillna(0).to_numpy(float)
        t_wire = t_est - t_pin
        okw = t_wire > 1e-6
        s_wire = float(np.median((tr["act_net_cap_pf_max"].to_numpy(float)[okw] - t_pin[okw]) / t_wire[okw]))
        res["s_wire"] = s_wire
        for name, sc in (("rc_wire146", 1.461), ("rc_wire", s_wire)):
            k = np.where(est > 0, (pin + sc * wire) / safe_est, 1.0)
            res[name] = C.eval_block(ev, ev["r8"].to_numpy(float) * k, per_run=False)["pooled"]["frac_to_catch_95"]
        ko = np.exp(ev["logk"].fillna(0).to_numpy(float))
        res["rc_oracle"] = C.eval_block(ev, ev["r8"].to_numpy(float) * ko, per_run=False)["pooled"]["frac_to_catch_95"]
        for r in ("est_slew", "rule_R8", "lgbm_full", "lgbm_estimate_only"):
            res[r + "_ablation"] = float(piv.loc[D, r]) if D in piv.index else None
        out["designs"][D] = res
        C.log(f"{D}: R8 {res['rc_global']:.4f} (ablation {res['rule_R8_ablation']:.4f}) layer {res['rc_layer']:.4f} "
              f"layer+len {res['rc_layer_len']:.4f} wire146 {res['rc_wire146']:.4f} wire(s={res['s_wire']:.2f}) {res['rc_wire']:.4f} oracle-cap {res['rc_oracle']:.4f} GBM {res['lgbm_full_ablation']:.4f} "
              f"floor {res['floor']:.4f} | R2 layer {res['rc_layer_r2']:.2f} layer+len {res['rc_layer_len_r2']:.2f}")
    keys = ["est_slew_ablation", "rule_R8_ablation", "rc_global", "rc_wire146", "rc_wire", "rc_layer", "rc_layer_len", "rc_oracle", "lgbm_full_ablation", "floor"]
    out["median"] = {k: float(np.median([v[k] for v in out["designs"].values()])) for k in keys}
    out["median_r2"] = {k: float(np.median([v[k] for v in out["designs"].values()])) for k in ("rc_layer_r2", "rc_layer_len_r2")}
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps({"median": out["median"], "median_r2": out["median_r2"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
