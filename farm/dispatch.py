#!/usr/bin/env python3
"""Dispatch farm jobs to GitHub Actions in batches.

Usage: dispatch.py --repo owner/name --tags farm/jobs/d1.tags.json [--batch 40] [--max-parallel 20] [--ref main]
                   [--workflow farm.yml]
Each batch becomes one workflow run (matrix of up to --batch jobs).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--tags", required=True)
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--max-parallel", type=int, default=20)
    ap.add_argument("--ref", default="main")
    ap.add_argument("--workflow", default="farm.yml", help="workflow file (e.g. farm_gf180.yml)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    tags = json.load(open(a.tags))
    for i in range(0, len(tags), a.batch):
        chunk = tags[i : i + a.batch]
        cmd = [
            "gh", "workflow", "run", a.workflow, "-R", a.repo, "--ref", a.ref,
            "-f", f"tags={json.dumps(chunk)}", "-f", f"max_parallel={a.max_parallel}",
        ]
        print(f"[dispatch] batch {i // a.batch + 1}: {len(chunk)} jobs")
        if a.dry_run:
            print(" ".join(cmd))
            continue
        r = subprocess.run(cmd, capture_output=True, text=True)
        print(r.stdout.strip(), r.stderr.strip())
        if r.returncode != 0:
            return r.returncode
        time.sleep(3)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
