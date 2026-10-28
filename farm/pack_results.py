#!/usr/bin/env python3
"""Pack each completed result directory into results/_pack/<tag>.tar.gz (once), so the
compact evidence can be synced to the Mac after every batch.

Usage: pack_results.py [--results results] [--out /mnt/user-data/outputs/beforeroute]
Prints the list of newly packed archives (absolute paths), one per line.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import tarfile


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
    ap.add_argument("--out", default="/mnt/user-data/outputs/beforeroute/results")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    # tags already copied to the Mac (results/.mac_manifest.txt, whitespace-separated) are not packed again: their local
    # archives are deleted after the sync to keep the session's disk allowance free
    man_p = os.path.join(os.path.abspath(a.results), ".mac_manifest.txt")
    synced = set(open(man_p).read().split()) if os.path.exists(man_p) else set()
    new = []
    for rdir in sorted(glob.glob(os.path.join(os.path.abspath(a.results), "*"))):
        if not os.path.isdir(rdir) or not os.path.exists(os.path.join(rdir, "job.json")):
            continue
        tag = os.path.basename(rdir)
        if tag[:2] in ("x1", "x2", "x3"):
            continue  # tuning runs are summarized in results/tune*/state.json; their raw dumps stay local (compressed)
        dst = os.path.join(a.out, tag + ".tar.gz")
        try:
            status = json.load(open(os.path.join(rdir, "job.json"))).get("status")
        except Exception:
            status = None
        if os.path.exists(dst) or tag in synced or status not in ("completed",):
            continue
        with tarfile.open(dst, "w:gz") as tf:
            tf.add(rdir, arcname=tag)
        new.append(dst)
    for p in new:
        print(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
