#!/usr/bin/env python3
"""Addendum 22 models: one LightGBM model per correlated-flow base, trained on every *other* correlated-flow base.

Correlated-flow bases are results/<round>cfo-<design>-<n> (ORFS per-layer R and C from placement on, no post-GRT repair)
whose seed reached signoff. Same recipe as br/train.py fit() (400 trees, 31 leaves, lr 0.05, class re-weighting), label =
signoff max-slew or max-cap violation on signal nets with a post-GRT driver. Writes models/model_cfloo_<design>.txt and
prints, for each base, its signal nets, violators, the p >= 0.5 list size and that list's recall on the base's own violators.
Usage: train_cfloo.py [--out-dir models] [--json summary.json]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, HERE)
from residual_cf import frame  # noqa: E402
from train import fit, predict  # noqa: E402

CF = re.compile(r"^(d\d+b?)cfo-([a-z0-9_]+)-(\d{3})$")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out-dir", default=os.path.join(ROOT, "models"))
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    data = {}
    for d in sorted(glob.glob(os.path.join(ROOT, "results", "*cfo-*-[0-9][0-9][0-9]"))):
        m = CF.match(os.path.basename(d))
        if not m:
            continue
        df = frame(d)
        if df is None or df["yv"].sum() == 0:
            continue
        data[os.path.basename(d)] = (m.group(2), df)
    print(f"{len(data)} correlated-flow bases: {', '.join(sorted(data))}")
    out = {}
    for tag, (design, df) in sorted(data.items()):
        tr = pd.concat([d for t, (_, d) in data.items() if t != tag], ignore_index=True)
        tr = tr.assign(y=tr["yv"])
        model = fit(tr)
        path = os.path.join(a.out_dir, f"model_cfloo_{design}.txt")
        model.save_model(path)
        p = predict(model, df)
        y = df["yv"].to_numpy()
        lst = p >= 0.5
        out[tag] = {"model": os.path.relpath(path, ROOT), "train_bases": sorted(t for t in data if t != tag),
                    "signal_nets": int(len(y)), "V": int(y.sum()), "list": int(lst.sum()),
                    "recall": float((lst & (y == 1)).sum() / max(1, y.sum()))}
        r = out[tag]
        print(f"{tag:22s} nets {r['signal_nets']:6d}  V {r['V']:4d}  list {r['list']:5d}  recall {100 * r['recall']:5.1f}%  -> {r['model']}")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
