#!/usr/bin/env python3
"""Collect farm artifacts into results/<tag>/ as individual jobs complete.

Usage: collect.py --repo owner/name [--results results] [--limit 20]
For every farm workflow run (completed or still in progress), downloads the
result-<tag> artifact of each completed job that is not yet present locally.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--results", default="results")
    ap.add_argument("--limit", type=int, default=20)
    a = ap.parse_args()
    os.makedirs(a.results, exist_ok=True)
    r = sh(["gh", "run", "list", "-R", a.repo, "-w", "farm.yml", "--limit", str(a.limit), "--json", "databaseId,status"])
    if r.returncode != 0:
        print(r.stderr.strip()[:300])
        return 1
    n_new = n_fail = 0
    pending = 0
    for run in json.loads(r.stdout):
        rid = run["databaseId"]
        j = sh(["gh", "run", "view", str(rid), "-R", a.repo, "--json", "jobs", "--jq", ".jobs[] | \"\\(.name)\\t\\(.status)\\t\\(.conclusion // \"-\")\""])
        if j.returncode != 0:
            continue
        for line in j.stdout.strip().splitlines():
            if not line.strip():
                continue
            tag, status, concl = line.split("\t")
            dst = os.path.join(a.results, tag)
            if os.path.exists(os.path.join(dst, "job.json")):
                continue
            if status != "completed":
                pending += 1
                continue
            with tempfile.TemporaryDirectory() as td:
                d = sh(["gh", "run", "download", str(rid), "-R", a.repo, "-n", f"result-{tag}", "-D", td])
                if d.returncode != 0:
                    print(f"[collect] {tag}: no artifact ({d.stderr.strip()[:120]})")
                    continue
                shutil.copytree(td, dst, dirs_exist_ok=True)
            try:
                st = json.load(open(os.path.join(dst, "job.json"))).get("status")
            except Exception:
                st = "?"
            n_new += 1
            if st != "completed":
                n_fail += 1
            print(f"[collect] {tag}: {st}")
    print(f"[collect] {n_new} new ({n_fail} failed), {pending} still running/queued")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
