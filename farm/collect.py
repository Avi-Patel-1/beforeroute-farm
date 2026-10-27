#!/usr/bin/env python3
"""Collect farm artifacts into results/<tag>/ as individual jobs complete.

Usage: collect.py --repo owner/name [--results results] [--limit 20] [--workflow farm.yml]
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
    ap.add_argument("--workflow", default="farm.yml", help="workflow file whose runs to collect (e.g. farm_gf180.yml)")
    a = ap.parse_args()
    os.makedirs(a.results, exist_ok=True)
    r = sh(["gh", "run", "list", "-R", a.repo, "-w", a.workflow, "--limit", str(a.limit), "--json", "databaseId,status"])
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
            parts = line.split("\t")
            tag, status = parts[0], parts[1]
            concl = parts[2] if len(parts) > 2 else "-"
            dst = os.path.join(a.results, tag)
            if os.path.exists(os.path.join(dst, "job.json")):
                continue
            if status != "completed":
                pending += 1
                continue
            if concl in ("cancelled", "skipped"):
                continue  # a cancelled job uploads only a partial dir; its tag is re-dispatched later
            with tempfile.TemporaryDirectory() as td:
                d = sh(["gh", "run", "download", str(rid), "-R", a.repo, "-n", f"result-{tag}", "-D", td])
                if d.returncode != 0:
                    print(f"[collect] {tag}: no artifact ({d.stderr.strip()[:120]})")
                    continue
                if not os.path.exists(os.path.join(td, "job.json")):
                    print(f"[collect] {tag}: artifact has no job.json (partial run) - skipped")
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
