#!/usr/bin/env python3
"""Collect farm artifacts into results/<tag>/.

Usage: collect.py --repo owner/name [--results results] [--limit 50]
Downloads artifacts named result-<tag> from completed workflow runs that are not
yet present locally.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import tempfile


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--results", default="results")
    ap.add_argument("--limit", type=int, default=50)
    a = ap.parse_args()
    os.makedirs(a.results, exist_ok=True)
    r = subprocess.run(
        ["gh", "run", "list", "-R", a.repo, "-w", "farm.yml", "--limit", str(a.limit),
         "--json", "databaseId,status,conclusion,createdAt"],
        capture_output=True, text=True, check=True,
    )
    runs = json.loads(r.stdout)
    n_new = 0
    for run in runs:
        rid = run["databaseId"]
        if run["status"] != "completed":
            continue
        with tempfile.TemporaryDirectory() as td:
            d = subprocess.run(["gh", "run", "download", str(rid), "-R", a.repo, "-D", td],
                               capture_output=True, text=True)
            if d.returncode != 0:
                print(f"[collect] run {rid}: download failed: {d.stderr.strip()[:200]}")
                continue
            for art in glob.glob(os.path.join(td, "result-*")):
                tag = os.path.basename(art)[len("result-"):]
                dst = os.path.join(a.results, tag)
                if os.path.exists(os.path.join(dst, "job.json")):
                    continue
                shutil.copytree(art, dst, dirs_exist_ok=True)
                n_new += 1
                try:
                    st = json.load(open(os.path.join(dst, "job.json"))).get("status")
                except Exception:
                    st = "?"
                print(f"[collect] {tag}: {st}")
    print(f"[collect] {n_new} new results")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
