#!/usr/bin/env python3
"""PDK-transfer test: does the sky130-trained per-net signoff-violation predictor work on GF180MCU?

Usage:
  transfer_gf180.py --sky <sky130 dataset.parquet> --gf <gf180 dataset.parquet> --out <dir>
                    [--designs picorv32,aes_cipher_top,ocs_blitter] [--feature-sets base,port]
                    [--arms zs,gfonly,merge,ft] [--ks 1,2,4,all] [--repeats 3] [--neg-frac 0.25]
  transfer_gf180.py --sky <sky130 parquet> --out <dir> --pretrain-only [--feature-sets base,port]

Both datasets get the PDK-neutral driver_class (br/pdk_neutral.py, re-derived from driver_master, so
sky130 rows use the same categories as gf180 rows). Evaluation is per held-out GF180 design (pooled
over that design's runs), on SIGNAL nets only; training uses all joined nets (as train.py does).

Feature sets: base = train.py FEATURES (PDK-neutral driver_class, layer-role guide fractions);
port = node-portable: lengths / standard-cell row height (sky130 hd 2.72 um, gf180 7t 3.92 um),
times / the design's max-transition constraint, caps / the driver's library max-cap limit, clock
period / max transition (no absolute max-transition feature).

Arms, for k gf180 runs drawn at random from the OTHER gf180 designs (k in --ks; --repeats draws for
k < all; the same draws are used by every arm):
  zs      zero-shot (k=0): train.py's LightGBM recipe on ALL sky130 rows
  gfonly  gf180-only: the same recipe on the k gf180 runs only (k=all = leave-one-design-out)
  merge   sky130 (negatives subsampled to --neg-frac, weight 1/neg-frac) + the k gf180 runs
          (k=0 = the subsampled sky130-only model)
  mergew  merge with the gf180 rows re-weighted to --gf-share of the total weight (optional arm)
  ft      fine-tune: the zero-shot sky130 booster + --ft-rounds more rounds on the k gf180 runs
Baselines: the timer's estimated worst load slew ratio; rule R8 = max(est load slew ratio, est
driver slew ratio, est cap ratio). Metrics: fraction of nets flagged to catch 95% of violators,
recall at 5% flagged, PR-AUC (+ROC-AUC), violator rate, blind-spot fraction (violators whose
estimated load slew ratio <= 1). Every result is cached in <out>/cache/<key>.json (resumable).
"""
from __future__ import annotations

import argparse
import itertools
import json
import math
import os
import random
import sys
import time
import zlib

import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from pdk_neutral import NEUTRAL_CLASSES, neutral_class  # noqa: E402
from train import FEATURES, evaluate  # noqa: E402

CAT = pd.CategoricalDtype(NEUTRAL_CLASSES)
PARAMS = dict(  # train.py fit() recipe
    objective="binary", learning_rate=0.05, num_leaves=31, min_data_in_leaf=40,
    feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, lambda_l2=1.0,
    verbose=-1, seed=7, num_threads=2,
)
ROUNDS = 400
ROW_H_UM = {"sky130": 2.72, "gf180mcu": 3.92}  # sky130_fd_sc_hd unithd / gf180mcu_fd_sc_mcu7t5v0 GF018hv5v_mcu_sc7
SDC_MAX_CAP_PF = 0.2  # MAX_CAPACITANCE_CONSTRAINT default of both PDKs
PORT_MAP = {  # base feature -> node-portable replacement
    "driver_slew_ns": "p_driver_slew", "worst_load_slew_ns": "p_worst_load_slew",
    "driver_slew_limit_lib_ns": "p_driver_slew_limit", "driver_cap_limit_lib_pf": "p_driver_cap_limit",
    "driver_slack_ns": "p_driver_slack", "hpwl_um": "p_hpwl", "bbox_w_um": "p_bbox_w", "bbox_h_um": "p_bbox_h",
    "guide_len_um": "p_guide_len", "net_cap_pf_max": "p_net_cap", "net_cap_pf_tt": "p_net_cap_tt",
    "pin_cap_pf_max": "p_pin_cap", "d_clock_period_ns": "p_clock_period", "d_max_tran_ns": None,
}
FEATURES_PORT = [PORT_MAP.get(f, f) for f in FEATURES if PORT_MAP.get(f, f)]
FEATURE_SETS = {"base": FEATURES, "port": FEATURES_PORT}


NEEDED = sorted(set(FEATURES) - {"driver_class"} | {
    "run", "design", "sigtype", "join_how", "driver_kind", "driver_master", "y", "y_slew", "y_cap", "y_fanout",
    "worst_load_slew_ratio", "driver_slew_ratio", "cap_ratio"})


def read(path: str) -> pd.DataFrame:
    """Only the columns this evaluation uses (RAM is shared); dtypes unchanged so pretrained models see the same values."""
    import pyarrow.parquet as pq

    have = set(pq.read_schema(path).names)
    return pd.read_parquet(path, columns=[c for c in NEEDED if c in have])


def prep(df: pd.DataFrame, pdk_family: str) -> pd.DataFrame:
    df = df[(df["join_how"] != "none") & (df["driver_kind"] != "none")].copy()
    df["driver_class"] = df["driver_master"].map(neutral_class)
    num = lambda c: pd.to_numeric(df[c], errors="coerce").astype(float)  # noqa: E731
    rh = ROW_H_UM[pdk_family]
    for src in ("hpwl_um", "bbox_w_um", "bbox_h_um", "guide_len_um"):
        df[PORT_MAP[src]] = num(src) / rh
    mt = num("d_max_tran_ns")
    for src in ("driver_slew_ns", "worst_load_slew_ns", "driver_slew_limit_lib_ns", "driver_slack_ns", "d_clock_period_ns"):
        df[PORT_MAP[src]] = num(src) / mt
    cl = num("driver_cap_limit_lib_pf")
    for src in ("net_cap_pf_max", "net_cap_pf_tt", "pin_cap_pf_max"):
        df[PORT_MAP[src]] = num(src) / cl
    df["p_driver_cap_limit"] = cl / SDC_MAX_CAP_PF
    df["r8"] = df[["worst_load_slew_ratio", "driver_slew_ratio", "cap_ratio"]].apply(pd.to_numeric, errors="coerce").fillna(0).max(axis=1)
    return df


def X_of(df, feats):
    X = df[feats].copy()
    X["driver_class"] = X["driver_class"].astype(CAT)
    for c in X.columns:
        if c != "driver_class":
            X[c] = pd.to_numeric(X[c], errors="coerce").astype(float)
    return X


def _spw(y, w):
    pos = max(1e-9, float(w[y == 1].sum()))
    neg = max(1e-9, float(w[y == 0].sum()))
    return min(50.0, neg / pos)


def fit_w(df, feats, w=None, rounds=ROUNDS, init_model=None):
    import lightgbm as lgb

    y = df["y"].astype(int).values
    w = np.ones(len(df)) if w is None else np.asarray(w, dtype=float)
    p = dict(PARAMS, scale_pos_weight=_spw(y, w))
    ds = lgb.Dataset(X_of(df, feats), y, weight=w, categorical_feature=["driver_class"], free_raw_data=False)
    return lgb.train(p, ds, num_boost_round=rounds, init_model=init_model)


def blind_spot(te):
    v = te[te["y"] == 1]
    if not len(v):
        return float("nan"), float("nan")
    return float((pd.to_numeric(v["worst_load_slew_ratio"], errors="coerce").fillna(0) <= 1.0).mean()), float((v["r8"] <= 1.0).mean())


def score_design(te, p, thresholds=(0.5, 0.9)):
    """Metrics on SIGNAL nets of one held-out design (pooled over its runs) + per-run values of the main ones.
    Also the operating point at fixed score thresholds (fraction flagged, recall): does a threshold set on
    sky130 transfer? (models: probability 0.5 / 0.9; baselines: ratio 1.0)."""
    m = (te["sigtype"] == "SIGNAL").values
    p = np.asarray(p)
    out = evaluate(te["y"].values[m], p[m])
    ys, ps = te["y"].values[m].astype(int), np.nan_to_num(p[m].astype(float))
    for t in thresholds:
        f = ps >= t
        out[f"flagged@{t:g}"] = float(f.mean()) if len(f) else None
        out[f"recall@{t:g}"] = float(ys[f].sum() / ys.sum()) if ys.sum() else None
    per = []
    sig = te[m]
    ps = p[m]
    for run in sorted(sig["run"].unique()):
        sel = (sig["run"] == run).values
        r = evaluate(sig["y"].values[sel], ps[sel])
        per.append({"run": run, **{k: r.get(k) for k in ("frac_to_catch_95", "recall@5%", "pr_auc", "positives", "n")}})
    out["per_run"] = per
    return out


def sub_neg(sky, frac, seed=11):
    if frac >= 1.0:
        return sky, np.ones(len(sky))
    rng = np.random.default_rng(seed)
    keep = (sky["y"].values == 1) | (rng.random(len(sky)) < frac)
    s = sky[keep]
    return s, np.where(s["y"].values == 1, 1.0, 1.0 / frac)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sky", required=True)
    ap.add_argument("--gf", default=None, help="gf180 dataset (omit with --pretrain-only)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pretrain-only", action="store_true", help="only train/save the sky130-only models")
    ap.add_argument("--designs", default=None, help="comma list of gf180 design (top) names, e.g. picorv32,aes_cipher_top,ocs_blitter")
    ap.add_argument("--feature-sets", default="base,port")
    ap.add_argument("--arms", default="zs,gfonly,merge,ft")
    ap.add_argument("--ks", default="1,2,4,all")
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--arm-repeats", default="merge=1,mergew=1", help="per-arm cap on draws for k < all, e.g. merge=1 (merge fits are the slow ones)")
    ap.add_argument("--arm-fsets", default="merge=base,mergew=base", help="per-arm feature sets, e.g. merge=base")
    ap.add_argument("--neg-frac", type=float, default=0.25)
    ap.add_argument("--gf-share", type=float, default=0.2)
    ap.add_argument("--ft-rounds", type=int, default=100)
    ap.add_argument("--strict", action="store_true",
                    help="exclude the held-out design's own sky130 runs from every sky130-trained arm (new PDK AND new design)")
    ap.add_argument("--sky-lodo", action="store_true", help="reference: sky130 leave-one-design-out on the same designs (base features, full recipe)")
    a = ap.parse_args()
    arms = a.arms.split(",")
    fsets = a.feature_sets.split(",")
    arm_rep = {kv.split("=")[0]: int(kv.split("=")[1]) for kv in a.arm_repeats.split(",") if kv}
    arm_fs = {}
    for kv in (x for x in a.arm_fsets.split(",") if x):
        arm, fsl = kv.split("=")
        arm_fs[arm] = set(fsl.split("+"))
    os.makedirs(os.path.join(a.out, "cache"), exist_ok=True)
    os.makedirs(os.path.join(a.out, "models"), exist_ok=True)
    import lightgbm as lgb

    def cached(key, fn):
        path = os.path.join(a.out, "cache", key + ".json")
        if os.path.exists(path):
            return json.load(open(path))
        t0 = time.time()
        res = fn()
        res["_seconds"] = round(time.time() - t0, 1)
        json.dump(res, open(path + ".tmp", "w"), indent=1)
        os.replace(path + ".tmp", path)
        print(f"[transfer] {key}: {res['_seconds']}s", flush=True)
        return res

    sky = prep(read(a.sky), "sky130")
    sky_s, w_s = sub_neg(sky, a.neg_frac)

    def sky_model(name, df, feats, w=None):
        mp = os.path.join(a.out, "models", name)
        if os.path.exists(mp):
            return lgb.Booster(model_file=mp)
        t0 = time.time()
        m = fit_w(df, feats, w)
        m.save_model(mp + ".tmp")
        os.replace(mp + ".tmp", mp)
        print(f"[transfer] trained {name} on {len(df)} rows in {time.time() - t0:.0f}s", flush=True)
        return m

    def full_name(fs, minus=None):
        n = "sky130_all_neutral" if fs == "base" else f"sky130_all_neutral_{fs}"
        return n + (f"_minus_{minus}" if minus else "") + ".txt"

    def sub_name(fs, minus=None):
        n = f"sky130_sub{a.neg_frac:g}_neutral" if fs == "base" else f"sky130_sub{a.neg_frac:g}_neutral_{fs}"
        return n + (f"_minus_{minus}" if minus else "") + ".txt"

    def sky_for(d):
        """sky130 training rows (full, subsampled + weights) for held-out design d under the chosen protocol."""
        if not a.strict:
            return sky, sky_s, w_s
        keep = (sky_s["design"] != d).values
        return sky[sky["design"] != d], sky_s[keep], w_s[keep]

    if a.pretrain_only:
        for fs in fsets:
            if a.strict:
                for d in (a.designs or "").split(","):
                    full_d, sub_d, wsub_d = sky_for(d)
                    sky_model(full_name(fs, d), full_d, FEATURE_SETS[fs])
                    sky_model(sub_name(fs, d), sub_d, FEATURE_SETS[fs], wsub_d)
            else:
                sky_model(full_name(fs), sky, FEATURE_SETS[fs])
                sky_model(sub_name(fs), sky_s, FEATURE_SETS[fs], w_s)
        return 0

    gf = prep(read(a.gf), "gf180mcu")
    if a.designs:
        gf = gf[gf["design"].isin(a.designs.split(","))]
    designs = sorted(gf["design"].unique())
    runs_of = {d: sorted(gf.loc[gf["design"] == d, "run"].unique()) for d in designs}
    print(f"[transfer] sky130 rows={len(sky)} runs={sky['run'].nunique()} pos={int(sky['y'].sum())}; "
          f"gf180 rows={len(gf)} runs={gf['run'].nunique()} designs={ {d: len(r) for d, r in runs_of.items()} }", flush=True)
    S = {"designs": designs, "runs": runs_of, "args": vars(a), "describe": {}, "baselines": {}, "arms": {}}

    for d in designs:
        te = gf[gf["design"] == d]
        s = te[te["sigtype"] == "SIGNAL"]
        b_load, b_r8 = blind_spot(s)
        S["describe"][d] = {
            "runs": len(runs_of[d]), "signal_nets": int(len(s)), "violators": int(s["y"].sum()),
            "violator_rate": float(s["y"].mean()) if len(s) else None,
            "violator_rate_per_run": {r: float(g["y"].mean()) for r, g in s.groupby("run")},
            "blind_spot_load": b_load, "blind_spot_r8": b_r8,
            "y_slew": int(s["y_slew"].sum()), "y_cap": int(s["y_cap"].sum()), "y_fanout": int(s["y_fanout"].sum()),
        }
        S["baselines"][d] = {
            "est_load_slew_ratio": score_design(te, pd.to_numeric(te["worst_load_slew_ratio"], errors="coerce").fillna(0).values, thresholds=(1.0,)),
            "R8": score_design(te, te["r8"].values, thresholds=(1.0,)),
        }
    s_sig = sky[sky["sigtype"] == "SIGNAL"]
    S["describe_sky130"] = {
        dd: {"runs": int(g["run"].nunique()), "signal_nets": int(len(g)), "violator_rate": float(g["y"].mean()),
             "blind_spot_load": blind_spot(g)[0], "blind_spot_r8": blind_spot(g)[1]}
        for dd, g in s_sig.groupby("design")
    }

    if a.sky_lodo:  # within-sky130 reference for the same designs: what a held-out design looks like without a PDK change
        for d in designs:
            if d not in set(sky["design"]):
                continue

            def lodo(d=d):
                model = fit_w(sky[sky["design"] != d], FEATURES)
                te = sky[sky["design"] == d]
                res = score_design(te, model.predict(X_of(te, FEATURES)))
                res["baseline_est_load_slew_ratio"] = {k: v for k, v in score_design(te, pd.to_numeric(te["worst_load_slew_ratio"], errors="coerce").fillna(0).values, thresholds=(1.0,)).items() if k != "per_run"}
                res["baseline_R8"] = {k: v for k, v in score_design(te, te["r8"].values, thresholds=(1.0,)).items() if k != "per_run"}
                res.pop("per_run", None)
                return res
            S.setdefault("sky130_lodo", {})[d] = cached(f"sky130_lodo_{d}", lodo)

    ks = [k if k == "all" else int(k) for k in a.ks.split(",")]
    proto = "strict_" if a.strict else ""
    S["protocol"] = "strict: held-out design excluded from sky130 training" if a.strict else "all sky130 designs in training"
    for fs in fsets:
        feats = FEATURE_SETS[fs]
        for d in designs:
            sky_d, sky_s_d, w_s_d = sky_for(d)
            need_full = "zs" in arms or "ft" in arms
            full = sky_model(full_name(fs, d if a.strict else None), sky_d, feats) if need_full else None
            te = gf[gf["design"] == d]
            Xte = X_of(te, feats)
            A = S["arms"].setdefault(fs, {}).setdefault(d, {})
            tsig = f"{zlib.crc32('|'.join(runs_of[d]).encode()):08x}"  # cache keys change when the test runs change
            if "zs" in arms:
                A.setdefault("zs", {})["0"] = [cached(f"{proto}{fs}_zs_{d}_{tsig}", lambda: score_design(te, full.predict(Xte)))]
            if "merge" in arms and fs in arm_fs.get("merge", {fs}):
                def m0():
                    return score_design(te, sky_model(sub_name(fs, d if a.strict else None), sky_s_d, feats, w_s_d).predict(Xte))
                A.setdefault("merge", {})["0"] = [cached(f"{proto}{fs}_merge_{d}_k0_{tsig}", m0)]
            pool = [r for dd in designs if dd != d for r in runs_of[dd]]
            for k in ks:
                if k == "all":
                    draws = [pool]
                elif k > len(pool):
                    continue
                elif k == len(pool):
                    if "all" in ks:
                        continue  # same subset as k=all
                    draws = [pool]
                elif math.comb(len(pool), k) <= a.repeats:  # few distinct subsets: use all of them
                    draws = [list(c) for c in itertools.combinations(pool, k)]
                else:  # distinct random subsets, deterministic per (design, k, draw)
                    draws, seen, r = [], set(), 0
                    while len(draws) < a.repeats:
                        c = tuple(sorted(random.Random(zlib.crc32(f"{d}|{k}|{r}".encode())).sample(pool, k)))
                        r += 1
                        if c not in seen:
                            seen.add(c)
                            draws.append(list(c))
                for r, picked in enumerate(draws):
                    g = gf[gf["run"].isin(picked)]
                    if g["y"].sum() == 0:
                        continue
                    meta = {"picked": list(picked), "gf_rows": int(len(g))}

                    def run_arm(arm, g=g, te=te, Xte=Xte, meta=meta, sky_s_d=sky_s_d, w_s_d=w_s_d, full=full):
                        if arm == "gfonly":
                            model = fit_w(g, feats)
                        elif arm in ("merge", "mergew"):
                            tr = pd.concat([sky_s_d, g], ignore_index=True)
                            wg = np.ones(len(g))
                            if arm == "mergew":
                                wg[:] = a.gf_share / (1 - a.gf_share) * w_s_d.sum() / len(g)
                            model = fit_w(tr, feats, np.concatenate([w_s_d, wg]))
                            meta = dict(meta, gf_row_weight=float(wg[0]))
                        elif arm == "ft":
                            model = fit_w(g, feats, rounds=a.ft_rounds, init_model=full)
                        else:
                            raise ValueError(arm)
                        res = score_design(te, model.predict(Xte))
                        res.update(meta)
                        return res

                    for arm in arms:
                        if arm == "zs":
                            continue
                        if k != "all" and r >= arm_rep.get(arm, a.repeats):
                            continue
                        if arm in arm_fs and fs not in arm_fs[arm]:
                            continue
                        psig = f"{zlib.crc32('|'.join(sorted(picked)).encode()):08x}"
                        key = f"{proto if arm != 'gfonly' else ''}{fs}_{arm}_{d}_k{k}_r{r}_{tsig}_{psig}"
                        A.setdefault(arm, {}).setdefault(str(k), []).append(cached(key, lambda arm=arm: run_arm(arm)))
            json.dump(S, open(os.path.join(a.out, "summary.json"), "w"), indent=1)
            write_tables(S, os.path.join(a.out, "tables.md"))

    json.dump(S, open(os.path.join(a.out, "summary.json"), "w"), indent=1)
    write_tables(S, os.path.join(a.out, "tables.md"))
    print(open(os.path.join(a.out, "tables.md")).read())
    return 0


def _f(x, pct=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    return f"{100 * x:.1f}%" if pct else f"{x:.3f}"


ARM_LABEL = {"zs": "zero-shot (sky130 model)", "gfonly": "GF180-only", "merge": "merge sky130 + GF180",
             "mergew": "merge, GF180 re-weighted", "ft": "fine-tune sky130 model on GF180"}
METRICS = [("frac_to_catch_95", "nets flagged to catch 95% of violators (lower is better)", True),
           ("recall@5%", "recall at 5% of nets flagged (higher is better)", True),
           ("pr_auc", "PR-AUC (higher is better)", False)]


def write_tables(S, path):
    L = []
    designs = S["designs"]
    L.append("## GF180 designs (signal nets, pooled over runs) vs the same designs in sky130\n")
    L.append("| design | GF180 runs | signal nets | violators | violator rate (per-run range) | blind spot: est load slew <= 1 | blind spot: R8 <= 1 | sky130 violator rate | sky130 blind spot (est load slew <= 1) |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for d in designs:
        x = S["describe"][d]
        pr = list(x["violator_rate_per_run"].values())
        sk = S["describe_sky130"].get(d, {})
        L.append(f"| {d} | {x['runs']} | {x['signal_nets']} | {x['violators']} | {_f(x['violator_rate'], True)} ({_f(min(pr), True)}-{_f(max(pr), True)}) | "
                 f"{_f(x['blind_spot_load'], True)} | {_f(x['blind_spot_r8'], True)} | {_f(sk.get('violator_rate'), True)} | {_f(sk.get('blind_spot_load'), True)} |")
    L.append("")
    if S.get("sky130_lodo"):
        L.append("## Reference: the same designs held out within sky130 (model trained on the other 11 sky130 designs)\n")
        L.append("| sky130 held-out design | flagged to catch 95% | recall @ 5% | PR-AUC | est-slew baseline: catch 95% / recall @ 5% / PR-AUC | R8: catch 95% / recall @ 5% / PR-AUC |")
        L.append("|---|---|---|---|---|---|")
        for d, m in S["sky130_lodo"].items():
            b, r = m["baseline_est_load_slew_ratio"], m["baseline_R8"]
            L.append(f"| {d} | {_f(m.get('frac_to_catch_95'), True)} | {_f(m.get('recall@5%'), True)} | {_f(m.get('pr_auc'))} | "
                     f"{_f(b.get('frac_to_catch_95'), True)} / {_f(b.get('recall@5%'), True)} / {_f(b.get('pr_auc'))} | "
                     f"{_f(r.get('frac_to_catch_95'), True)} / {_f(r.get('recall@5%'), True)} / {_f(r.get('pr_auc'))} |")
        L.append("")
    L.append("## Does a score threshold transfer? (fraction of signal nets flagged / recall at a fixed threshold)\n")
    L.append("| held-out | est. load slew ratio > 1 | R8 > 1 | " + " | ".join(f"zero-shot [{fs}] p >= 0.5 | zero-shot [{fs}] p >= 0.9" for fs in S["arms"]) + " |")
    L.append("|---|---|---|" + "---|---|" * len(S["arms"]))

    def op(m, t):
        return f"{_f(m.get(f'flagged@{t:g}'), True)} / {_f(m.get(f'recall@{t:g}'), True)}"
    for d in designs:
        b = S["baselines"][d]
        cells = [op(b["est_load_slew_ratio"], 1.0), op(b["R8"], 1.0)]
        for fs, byd in S["arms"].items():
            zs = (byd.get(d, {}).get("zs") or {}).get("0")
            cells += [op(zs[0], 0.5), op(zs[0], 0.9)] if zs else ["", ""]
        L.append(f"| GF180 {d} | " + " | ".join(cells) + " |")
    for d, m in (S.get("sky130_lodo") or {}).items():
        cells = [op(m["baseline_est_load_slew_ratio"], 1.0), op(m["baseline_R8"], 1.0), op(m, 0.5), op(m, 0.9)]
        L.append(f"| sky130 {d} (LODO, base) | " + " | ".join(cells) + " |")
    L.append("")
    for d in designs:
        rate = S["describe"][d]["violator_rate"] or float("nan")
        L.append(f"## Held-out GF180 design: {d}\n")
        L.append(f"Bounds for a perfect ranker: catch 95% at {_f(0.95 * rate, True)} flagged; recall @ 5% <= {_f(min(1.0, 0.05 / rate) if rate else float('nan'), True)}.\n")
        L.append("| ranker | flagged to catch 95% (per-run min-max) | recall @ 5% (per-run min-max) | PR-AUC | ROC-AUC |")
        L.append("|---|---|---|---|---|")

        def rr(m, k):
            v = [x.get(k) for x in m.get("per_run", []) if x.get(k) is not None]
            return f" ({_f(min(v), True)}-{_f(max(v), True)})" if len(v) > 1 else ""

        def line(name, m):
            return (f"| {name} | {_f(m.get('frac_to_catch_95'), True)}{rr(m, 'frac_to_catch_95')} | "
                    f"{_f(m.get('recall@5%'), True)}{rr(m, 'recall@5%')} | {_f(m.get('pr_auc'))} | {_f(m.get('roc_auc'))} |")
        for name, key in (("baseline: est. load slew ratio", "est_load_slew_ratio"), ("baseline: rule R8", "R8")):
            L.append(line(name, S["baselines"][d][key]))
        for fs, byd in S["arms"].items():
            zs = (byd.get(d, {}).get("zs") or {}).get("0")
            if zs:
                L.append(line(f"zero-shot sky130 model [{fs} features]", zs[0]))
        L.append("")
        for fs, byd in S["arms"].items():
            A = byd.get(d, {})
            kset = sorted({k for arm in A.values() for k in arm}, key=lambda k: (k == "all", int(k) if k != "all" else 0))
            for mkey, mlabel, pct in METRICS:
                L.append(f"{d} [{fs} features] - {mlabel}; mean over draws (min-max), k = GF180 runs from the other designs\n")
                L.append("| arm | " + " | ".join(f"k={k}" for k in kset) + " |")
                L.append("|---|" + "---|" * len(kset))
                for arm in ("zs", "gfonly", "merge", "mergew", "ft"):
                    if arm not in A:
                        continue
                    cells = []
                    for k in kset:
                        lst = [x.get(mkey) for x in A[arm].get(k, []) if x.get(mkey) is not None]
                        if not lst:
                            cells.append("")
                        elif len(lst) == 1:
                            cells.append(_f(lst[0], pct))
                        else:
                            cells.append(f"{_f(float(np.mean(lst)), pct)} ({_f(min(lst), pct)}-{_f(max(lst), pct)})")
                    L.append(f"| {ARM_LABEL[arm]} | " + " | ".join(cells) + " |")
                L.append("")
    open(path, "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    raise SystemExit(main())
