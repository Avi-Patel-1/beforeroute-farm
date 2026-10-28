#!/usr/bin/env python3
"""Keep the workspace under its fixed disk allowance during long unattended runs.

When free space is below --min-gb: gzip nets.jsonl / nets_signoff.jsonl / final_nets.json in tuning runs (x1*/x2*/x3*;
tune*.py read the .gz forms), then nets_signoff.jsonl in hero-arm results (tags with an arm suffix, e.g.
d3-des-000-thr500-30cr; the criteria read labels.json/metrics.json, not this file), oldest first, until --target-gb is
free; then, if still short, removes tuning runs' nets_signoff.jsonl.gz (oldest first; the farm keeps every run's artifact
for 30 days; logged in results/.removed_files.txt). Prints what it did.
Usage: disk_guard.py [--min-gb 3] [--target-gb 6] [--results results]
"""
from __future__ import annotations

import argparse
import glob
import gzip
import os
import shutil


def free_gb(path):
    s = os.statvfs(path)
    return s.f_bavail * s.f_frsize / 1e9


def gz(p):
    with open(p, "rb") as fi, gzip.open(p + ".gz", "wb", compresslevel=6) as fo:
        shutil.copyfileobj(fi, fo)
    os.remove(p)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-gb", type=float, default=3.0)
    ap.add_argument("--target-gb", type=float, default=6.0)
    ap.add_argument("--results", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
    a = ap.parse_args()
    f0 = free_gb(a.results)
    print(f"[disk] free {f0:.1f} GB")
    if f0 >= a.min_gb:
        return 0
    cands = []
    for d in glob.glob(os.path.join(a.results, "x[12345]*")):
        for fn in ("nets.jsonl", "nets_signoff.jsonl", "final_nets.json"):
            p = os.path.join(d, fn)
            if os.path.exists(p):
                cands.append((0, os.path.getmtime(p), p))
    for d in glob.glob(os.path.join(a.results, "*-*-*-*")):
        p = os.path.join(d, "nets_signoff.jsonl")
        if os.path.exists(p):
            cands.append((1, os.path.getmtime(p), p))
    # final_nets.json (per-net signoff detail of every hero arm, ~3 MB each): the check-in criteria read labels.json and
    # metrics.json only; the farm-side tools that read final_nets.json run on the farm's own copies
    for p in glob.glob(os.path.join(a.results, "*", "final_nets.json")):
        cands.append((2, os.path.getmtime(p), p))
    cands.sort()
    n = 0
    for _, _, p in cands:
        if free_gb(a.results) >= a.target_gb:
            break
        try:
            gz(p)
            n += 1
        except OSError as e:
            print(f"[disk] {p}: {e}")
            break
    print(f"[disk] gzipped {n} files; free {free_gb(a.results):.1f} GB")
    # last tier: tuning runs' per-net signoff dumps (no tuning report reads them; the farm keeps every run's artifact for
    # 30 days, so collect.py can fetch them again). Logged in results/.removed_files.txt.
    if free_gb(a.results) < a.target_gb:
        drop = sorted((os.path.getmtime(p), p) for d in glob.glob(os.path.join(a.results, "x[12345]*"))
                      for p in [os.path.join(d, "nets_signoff.jsonl.gz")] if os.path.exists(p))
        k = 0
        with open(os.path.join(a.results, ".removed_files.txt"), "a") as log:
            for _, p in drop:
                if free_gb(a.results) >= a.target_gb:
                    break
                os.remove(p)
                log.write(p + "\n")
                k += 1
        print(f"[disk] removed {k} tuning-run signoff dumps (re-fetchable from the farm for 30 days); free {free_gb(a.results):.1f} GB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
