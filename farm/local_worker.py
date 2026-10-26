#!/usr/bin/env python3
"""Run farm job specs sequentially on this machine (W1), skipping finished ones.

Usage: local_worker.py --tags farm/jobs/d1.tags.json [--only-design spm,crc_pipe] [--jobs 2] [--max 999]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, ".."))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tags", required=True)
    ap.add_argument("--only-design", default=None)
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--max", type=int, default=999)
    ap.add_argument("--results", default=os.path.join(ROOT, "results"))
    a = ap.parse_args()
    tags = json.load(open(a.tags))
    only = set(a.only_design.split(",")) if a.only_design else None
    n = 0
    for tag in tags:
        spec_path = os.path.join(HERE, "jobs", tag + ".json")
        spec = json.load(open(spec_path))
        dname = os.path.basename(spec["design"])
        if only and dname not in only:
            continue
        if os.path.exists(os.path.join(a.results, tag, "job.json")):
            continue
        if n >= a.max:
            break
        n += 1
        t0 = time.time()
        print(f"[w1] {time.strftime('%H:%M:%S')} start {tag}", flush=True)
        r = subprocess.run(
            [sys.executable, os.path.join(ROOT, "br", "run_job.py"), "--job-spec", spec_path,
             "--design", os.path.join(ROOT, spec["design"]), "--jobs", str(a.jobs), "--results", a.results],
            capture_output=True, text=True,
        )
        status = "?"
        try:
            status = json.load(open(os.path.join(a.results, tag, "job.json"))).get("status")
        except Exception:
            pass
        print(f"[w1] {time.strftime('%H:%M:%S')} done  {tag} status={status} rc={r.returncode} {time.time() - t0:.0f}s", flush=True)
    print(f"[w1] finished {n} jobs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
