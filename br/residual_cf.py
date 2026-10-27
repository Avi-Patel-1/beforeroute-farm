#!/usr/bin/env python3
"""What is left for a learned list once the flow's wire RC is correlated (descriptive; no farm runs).

For each design with both a default-RC base (results/<fam>-<d>-<n>) and a whole-flow correlated base
(results/<fam>cfo-<d>-<n>, ORFS per-layer R and C from placement on, no post-GRT repair), on signal nets with a
post-GRT driver, label = signoff max-slew or max-cap violation:
  blind      share of violators whose post-GRT estimate R8 = max(load-slew, driver-slew, cap ratio) is below 1
  N90        nets with R8 >= 0.9 (what a stock repair at 10% margin would touch)
  rec_est    share of violators in that list
  rec_gbm    share of violators in the held-out model's top N90 (same list size)
  gbm_only   violators in the model's top N90 but not in the estimate's list
  c95_est / c95_gbm   share of signal nets that must be flagged to catch 95% of violators, ranking by R8 / by the model
The model is the base's held-out model from farm/dispatch_a19.py (trained on default-RC runs only).
Usage: residual_cf.py [--json out]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(ROOT, "farm"))
from build_dataset import load_run  # noqa: E402
from train import FEATURES  # noqa: E402
import dispatch_a19 as D  # noqa: E402


def frame(rdir):
    if not all(os.path.exists(os.path.join(rdir, f)) for f in ("job.json", "nets.jsonl", "labels.json")):
        return None
    rows, _ = _load_forced(rdir)  # a flow that ended in deferred hold errors still reached signoff
    if rows is None:
        return None
    df = pd.DataFrame(rows)
    df = df[(df["sigtype"] == "SIGNAL") & (df["driver_kind"] != "none")].copy()
    df["yv"] = ((df["y_slew"] == 1) | (df["y_cap"] == 1)).astype(int)
    df["r8"] = df[["worst_load_slew_ratio", "driver_slew_ratio", "cap_ratio"]].fillna(0).astype(float).max(axis=1)
    return df


def _load_forced(rdir):
    import build_dataset as B
    orig = B.json.load

    def patched(f, *a, **k):
        d = orig(f, *a, **k)
        if getattr(f, "name", "").endswith("job.json"):
            d["status"] = "completed"
        return d
    B.json.load = patched
    try:
        return B.load_run(rdir)
    finally:
        B.json.load = orig


def catch(scores, y, q=0.95):
    order = np.argsort(-scores, kind="stable")
    cum = np.cumsum(y[order])
    need = int(np.ceil(q * y.sum()))
    if need == 0:
        return float("nan")
    k = int(np.searchsorted(cum, need) + 1)
    return k / len(y)


def metrics(df, model):
    import lightgbm as lgb
    y = df["yv"].to_numpy()
    X = df[FEATURES].copy()
    X["driver_class"] = pd.Categorical(X["driver_class"], categories=model.pandas_categorical[0]) if model.pandas_categorical else X["driver_class"].astype("category")
    p = model.predict(X)
    r8 = df["r8"].to_numpy()
    V = int(y.sum())
    est90 = r8 >= 0.9
    n90 = int(est90.sum())
    top = np.zeros(len(y), bool)
    if n90:
        top[np.argsort(-p, kind="stable")[:n90]] = True
    return {"signal_nets": int(len(y)), "V": V, "blind": float(((r8 < 1.0) & (y == 1)).sum() / max(1, V)),
            "N90": n90, "rec_est": float((est90 & (y == 1)).sum() / max(1, V)),
            "rec_gbm": float((top & (y == 1)).sum() / max(1, V)), "gbm_only": int((top & ~est90 & (y == 1)).sum()),
            "c95_est": catch(r8, y), "c95_gbm": catch(p, y),
            "n_p05": int((p >= 0.5).sum()), "rec_p05": float(((p >= 0.5) & (y == 1)).sum() / max(1, V)),
            "delay_driven": float(df.loc[df["yv"] == 1, "driver_master"].fillna("").str.contains("clkdlybuf|dlygate|dlymetal").mean()) if V else float("nan"),
            "missed_r8_median": float(np.median(r8[(y == 1) & ~est90])) if ((y == 1) & ~est90).any() else float("nan")}


def summarize(path=None):
    """Headline numbers from residual_cf.json (shared by paper/gen_numbers.py and site/build_site.py)."""
    path = path or os.path.join(ROOT, "agents", "analysis", "residual_cf.json")
    if not os.path.exists(path):
        return {}
    R = {b: v for b, v in json.load(open(path)).items() if v.get("default") and v.get("ORFS RC")}
    if not R:
        return {}

    def med(xs):
        xs = sorted(xs)
        n = len(xs)
        return xs[n // 2] if n % 2 else 0.5 * (xs[n // 2 - 1] + xs[n // 2])
    areas = []
    for b in R:
        fam, rest = b.split("-", 1)
        try:
            a0 = json.load(open(os.path.join(ROOT, "results", b, "metrics.json")))["design__instance__area__stdcell"]
            a1 = json.load(open(os.path.join(ROOT, "results", f"{fam}cfo-{rest}", "metrics.json")))["design__instance__area__stdcell"]
            areas.append(100 * (a1 / a0 - 1))
        except Exception:
            pass
    L = {b: v for b, v in R.items() if v.get("ORFS RC, CF-trained LOO")}
    cut = [1 - v["ORFS RC"]["V"] / v["default"]["V"] for v in R.values()]
    lst = [v["ORFS RC"]["rec_est"] for v in R.values()]
    return {"n": len(R), "blind_def_med": med([v["default"]["blind"] for v in R.values()]),
            "blind_cor_med": med([v["ORFS RC"]["blind"] for v in R.values()]),
            "list_min": min(lst), "list_med": med(lst), "vcut_min": min(cut), "vcut_max": max(cut),
            "est_beats_gbm": sum(1 for v in R.values() if v["ORFS RC"]["c95_est"] < v["ORFS RC"]["c95_gbm"]),
            "loo_n": len(L), "loo_beats_est": sum(1 for v in L.values() if v["ORFS RC, CF-trained LOO"]["c95_gbm"] < v["ORFS RC"]["c95_est"]),
            "area_min": min(areas) if areas else None, "area_max": max(areas) if areas else None,
            "delay_med": med([v["ORFS RC"].get("delay_driven", float("nan")) for v in R.values() if v["ORFS RC"].get("delay_driven") == v["ORFS RC"].get("delay_driven")] or [float("nan")]),
            "missed_r8_med": med([v["ORFS RC"]["missed_r8_median"] for v in R.values() if v["ORFS RC"].get("missed_r8_median") == v["ORFS RC"].get("missed_r8_median") and v["ORFS RC"].get("missed_r8_median") is not None] or [float("nan")]),
            "blind_cor_min": min(v["ORFS RC"]["blind"] for v in R.values()), "blind_cor_max": max(v["ORFS RC"]["blind"] for v in R.values()),
            "n_blind_half": sum(1 for v in R.values() if v["ORFS RC"]["blind"] >= 0.5),
            "loo_better_10": sum(1 for v in L.values() if v["ORFS RC, CF-trained LOO"]["c95_gbm"] < 0.9 * v["ORFS RC"]["c95_est"]),
            "loo_worse_10": sum(1 for v in L.values() if v["ORFS RC, CF-trained LOO"]["c95_gbm"] > 1.1 * v["ORFS RC"]["c95_est"]),
            "designs": sorted(R)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--loo", action="store_true", help="also train leave-one-design-out models on the correlated-flow bases")
    a = ap.parse_args()
    import lightgbm as lgb
    out = {}
    print(f"{'design':18s} {'flow':8s} {'nets':>6s} {'V':>5s} {'blind':>6s} {'N90':>5s} {'rec_est':>7s} {'rec_gbm':>7s} {'gbm_only':>8s} {'c95_est':>7s} {'c95_gbm':>7s}")
    for base, mpath in D.MODEL.items():
        fam, rest = base.split("-", 1)
        model = lgb.Booster(model_file=os.path.join(ROOT, mpath))
        for flow, tag in (("default", base), ("ORFS RC", f"{fam}cfo-{rest}")):
            df = frame(os.path.join(ROOT, "results", tag))
            if df is None or df["yv"].sum() == 0:
                continue
            m = metrics(df, model)
            out.setdefault(base, {})[flow] = m
            print(f"{base:18s} {flow:8s} {m['signal_nets']:6d} {m['V']:5d} {m['blind']:6.0%} {m['N90']:5d} {m['rec_est']:7.0%} "
                  f"{m['rec_gbm']:7.0%} {m['gbm_only']:8d} {m['c95_est']:7.1%} {m['c95_gbm']:7.1%}")
    if a.loo:
        # a learned residual: models trained on correlated-flow runs only (label = slew or cap), each design held out
        from train import fit as _fit  # noqa: F401  (same recipe, label swapped below)
        cf = {}
        for base in D.MODEL:
            fam, rest = base.split("-", 1)
            df = frame(os.path.join(ROOT, "results", f"{fam}cfo-{rest}"))
            if df is not None and df["yv"].sum() > 0:
                cf[base] = df
        print(f"\nleave-one-design-out on {len(cf)} correlated-flow bases (models trained on correlated runs only)")
        for base, df in cf.items():
            saved = os.path.join(ROOT, "models", f"model_cfloo_{base.split('-', 1)[1].rsplit('-', 1)[0]}.txt")
            if os.path.exists(saved):  # the Addendum-22 model (br/train_cfloo.py: same recipe, trained on the other bases)
                model = lgb.Booster(model_file=saved)
            else:
                tr = pd.concat([d for b, d in cf.items() if b != base], ignore_index=True)
                tr = tr.assign(y=tr["yv"])
                model = _fit(tr)
            m = metrics(df, model)
            out.setdefault(base, {})["ORFS RC, CF-trained LOO"] = m
            print(f"{base:18s} {'CF-LOO':8s} {m['signal_nets']:6d} {m['V']:5d} {m['blind']:6.0%} {m['N90']:5d} {m['rec_est']:7.0%} "
                  f"{m['rec_gbm']:7.0%} {m['gbm_only']:8d} {m['c95_est']:7.1%} {m['c95_gbm']:7.1%}")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
