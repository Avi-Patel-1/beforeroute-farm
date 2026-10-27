#!/usr/bin/env python3
"""Data-flywheel learning curve for the per-net signoff-violation predictor.

Usage (one analyze.yml matrix entry per held-out design x size):
  learning_curve.py --data dataset.parquet --out out/ --holdout picorv32 --variant runs --n 8
  learning_curve.py ... --variant runs --n 1,2,4,8,16,32,64,all   # several sizes in one job
  learning_curve.py ... --variant designs --n 2      # all runs of n random other designs
  learning_curve.py ... --variant within --n 2       # all other designs + n runs of the held-out design

Variants (3 seeds each; a size that covers the whole pool is fitted once):
  runs     train on N runs drawn from all *other* designs. Each seed is a random arrival order of
           the pool's runs, conditioned on the first run having >= --min-pos violators; size N
           takes the first N runs of that order (nested across N: one flywheel trajectory per seed).
  designs  train on all runs of K distinct other designs; random design order per seed, first
           design must have >= --min-pos violators; nested across K.
  within   "within-project flywheel": train on all other designs plus k runs of the held-out
           design D; per seed a random order of D's runs: the first k are added to training and the
           test set is D's runs after the first min(4, n_runs-1) (identical for every k of a seed,
           so k = 0/1/2/4 are paired).
  self     train on k runs of the held-out design only (no other designs), same paired test runs as within.
Evaluation: signal nets of the held-out design's evaluation runs; recall at 5% flagged, fraction
flagged to catch 95%, PR-AUC, pooled over runs and per run (median / IQR); calibration of the
expected violator count per run, |sum p - actual| / actual, with p prior-corrected for the
positive up-weighting (raw p also reported). Rule R8 and the raw slew estimate on the same
evaluation runs are reported alongside as reference lines.
Model: br/train.py's LightGBM parameters (captured from train.fit), --rounds overrides num_boost_round.
Outputs: <out>/learning_curve.json, learning_curve.csv, learning_curve_runs.csv
"""
from __future__ import annotations

import argparse
import json
import os
import time
import zlib

import numpy as np
import pandas as pd

import analysis_common as C


def order_runs(pool: pd.DataFrame, rng, min_pos: int) -> list:
    """Random order of pool runs whose first run has >= min_pos violators (all nets)."""
    perm = list(pool["run"].values[rng.permutation(len(pool))])
    pos = dict(zip(pool["run"], pool["pos"]))
    for i, r in enumerate(perm):
        if pos[r] >= min_pos:
            return [r] + perm[:i] + perm[i + 1:]
    return perm


def order_designs(pool: pd.DataFrame, rng, min_pos: int) -> list:
    per = pool.groupby("design")["pos"].sum()
    designs = list(per.index.values[rng.permutation(len(per))])
    for i, d in enumerate(designs):
        if per[d] >= min_pos:
            return [d] + designs[:i] + designs[i + 1:]
    return designs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--holdout", required=True)
    ap.add_argument("--variant", choices=["runs", "designs", "within", "self"], default="runs")
    ap.add_argument("--n", default="all", help="comma list of training sizes: runs (runs), designs (designs) or in-design runs k (within); all = whole pool")
    ap.add_argument("--seeds", type=int, default=3)
    ap.add_argument("--min-pos", type=int, default=20, help="violators required in the first run/design of an order")
    ap.add_argument("--rounds", type=int, default=0, help="num_boost_round override (0 = br/train.fit's)")
    ap.add_argument("--threads", type=int, default=0, help="LightGBM threads (0 = all cores)")
    ap.add_argument("--train-sigtype", choices=["all", "SIGNAL"], default="all", help="training nets (br/train.py trains on all)")
    ap.add_argument("--float32", action="store_true", help="downcast features to float32 at load (lower peak memory)")
    ap.add_argument("--all-runs", action="store_true", help="keep non-data runs (default: d1-/d2-/d3-/d4-/d3b-/d4b- only)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    threads = a.threads or os.cpu_count()
    t_start = time.time()

    df = C.load(a.data, all_runs=a.all_runs, float32=a.float32)
    rt = C.run_table(df if a.train_sigtype == "all" else df[df["is_signal"]])
    D = a.holdout
    d_runs = sorted(rt.loc[rt["design"] == D, "run"])
    pool = rt[rt["design"] != D].reset_index(drop=True)
    C.log(f"holdout={D} variant={a.variant} n={a.n}: D runs={len(d_runs)}, pool runs={len(pool)} "
          f"designs={pool['design'].nunique()} rows={len(df)}")
    if not d_runs:
        raise SystemExit(f"no runs for design {D}")
    train_df = df if a.train_sigtype == "all" else df[df["is_signal"]]
    ev_all = df[(df["design"] == D) & df["is_signal"]].reset_index(drop=True)
    by_run_train = {r: g.index.values for r, g in train_df.groupby("run")}

    records, run_rows, csv_rows = [], [], []
    cache = {}  # frozenset(train runs) -> (p_raw on ev_all, spw, rounds, fit_s)
    rule_scores = {"r8": C.r8(ev_all), "est_slew": ev_all["worst_load_slew_ratio"].astype(float).fillna(0).values}
    kmax = min(4, len(d_runs) - 1)
    d_set = set(d_runs)

    def dump():
        json.dump({"args": vars(a), "seconds": round(time.time() - t_start, 1), "records": records},
                  open(os.path.join(a.out, "learning_curve.json"), "w"), indent=1)
        pd.DataFrame(csv_rows).to_csv(os.path.join(a.out, "learning_curve.csv"), index=False)
        pd.DataFrame(run_rows).to_csv(os.path.join(a.out, "learning_curve_runs.csv"), index=False)

    for n_str in [x.strip() for x in str(a.n).split(",") if x.strip()]:
        if a.variant in ("within", "self"):
            k = int(n_str)
            if kmax < 1 or k > kmax:
                records.append({"variant": a.variant, "holdout": D, "n": k, "skipped": f"k={k} > kmax={kmax} ({len(d_runs)} runs of {D})"})
                C.log(f"skip k={k}: kmax={kmax}")
                continue
            seeds = range(a.seeds)
        else:
            size_pool = len(pool) if a.variant == "runs" else pool["design"].nunique()
            size = size_pool if n_str == "all" else min(int(n_str), size_pool)
            seeds = range(1) if size >= size_pool else range(a.seeds)
        n_val = n_str if n_str == "all" else int(n_str)
        for seed in seeds:
            rng = np.random.default_rng([seed, zlib.crc32(D.encode())])
            if a.variant == "runs":
                train_runs = order_runs(pool, rng, a.min_pos)[:size]
                eval_runs, size_val = d_runs, len(train_runs)
            elif a.variant == "designs":
                chosen = order_designs(pool, rng, a.min_pos)[:size]
                train_runs = list(pool.loc[pool["design"].isin(chosen), "run"])
                eval_runs, size_val = d_runs, len(chosen)
            else:  # within: other designs + k runs of D; self: k runs of D only (same paired test runs)
                perm = [d_runs[i] for i in rng.permutation(len(d_runs))]
                train_runs = (list(pool["run"]) if a.variant == "within" else []) + perm[:k]
                eval_runs, size_val = perm[kmax:], k
            if not train_runs:
                records.append({"variant": a.variant, "holdout": D, "n": n_val, "seed": seed, "skipped": "empty training set"})
                continue
            key = frozenset(train_runs)
            tr = train_df.loc[np.concatenate([by_run_train[r] for r in train_runs])]
            n_pos = int(tr["y"].sum())
            rec = {"variant": a.variant, "holdout": D, "n": n_val, "size": size_val, "seed": seed,
                   "n_train_runs": len(train_runs), "n_train_designs": int(tr["design"].nunique()),
                   "train_designs": ";".join(sorted(tr["design"].unique())), "n_train_rows": int(len(tr)), "n_train_pos": n_pos,
                   "in_design_runs": ";".join(sorted(r for r in train_runs if r in d_set)),
                   "eval_runs": len(eval_runs), "threads": threads}
            if n_pos == 0 or n_pos == len(tr):
                rec["skipped"] = "degenerate training labels"
                records.append(rec)
                continue
            if key not in cache:
                t0 = time.time()
                model = C.fit_lgb(tr, rounds=a.rounds or None, threads=threads)
                cache[key] = (C.predict_lgb(model, ev_all), model._br_spw, model._br_rounds, time.time() - t0)
                del model
            p, spw, rounds, fit_s = cache[key]
            rec.update({"rounds": rounds, "scale_pos_weight": spw, "fit_seconds": round(fit_s, 1)})
            m = ev_all["run"].isin(set(eval_runs)).values
            ev = ev_all[m]
            blk = C.eval_block(ev, p[m], prob=C.prior_correct(p[m], spw))
            raw = C.eval_block(ev, p[m], prob=p[m])
            rec["model"] = {kk: blk[kk] for kk in ("pooled", "per_run", "n_runs")}
            rec["calibration_raw_p"] = raw["per_run"].get("cal_err")
            row = {kk: v for kk, v in rec.items() if not isinstance(v, dict)}
            row.update(C.flat(blk))
            row["run_calerr_raw_med"] = raw["per_run"]["cal_err"]["median"]
            for rname, sc in rule_scores.items():
                rb = C.eval_block(ev, sc[m])
                rec[rname] = {kk: rb[kk] for kk in ("pooled", "per_run")}
                row.update(C.flat(rb, prefix=f"{rname}_"))
            records.append(rec)
            csv_rows.append(row)
            for r in blk["runs"]:
                run_rows.append({"variant": a.variant, "holdout": D, "n": n_val, "seed": seed,
                                 **{("n_nets" if kk == "n" else kk): v for kk, v in r.items()}})
            C.log(f"n={n_val} seed={seed} train runs={len(train_runs)} designs={rec['n_train_designs']} pos={n_pos} fit={fit_s:.0f}s | "
                  f"pooled R@5%={blk['pooled'].get('recall@5%', float('nan')):.3f} catch95={blk['pooled'].get('frac_to_catch_95', float('nan')):.3f} "
                  f"PR-AUC={blk['pooled'].get('pr_auc', float('nan')):.3f} | run-med R@5%={blk['per_run']['recall@5%']['median']:.3f} "
                  f"cal_err={blk['per_run']['cal_err']['median']:.2f} | R8 R@5%={rec['r8']['pooled'].get('recall@5%', float('nan')):.3f}")
            dump()
        if len(cache) > 4:  # keep memory bounded across sizes
            cache.clear()
    dump()
    C.log(f"done in {time.time() - t_start:.0f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
