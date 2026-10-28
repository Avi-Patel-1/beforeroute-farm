#!/usr/bin/env python3
"""Re-dispatch tuning jobs stuck in a starved farm.yml run.

GitHub does not schedule queued jobs first come, first served across runs: a large run capped by max-parallel can sit
with every remaining job queued and none running while newer runs take all slots (Addendum 24's comparison run started
nothing for 3 h). For each farm.yml run with queued jobs, none running, and no job started in the last --stall-min minutes
(or created that long ago without any start): cancel it, wait until it is cancelled, then re-dispatch its queued tags whose
results are not on disk as runs of <= --chunk jobs. Specs are unchanged (farm/jobs/<tag>.json, already committed).
Only runs whose jobs are all tuning tags (x1*/x2*/x3*) are touched.
Usage: unstall.py [--stall-min 60] [--chunk 8] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import subprocess
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO = "Avi-Patel-1/beforeroute-farm"


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def ts(s):
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc)


def jobs(rid):
    out = []
    for page in range(1, 4):
        r = sh(["gh", "api", f"repos/{REPO}/actions/runs/{rid}/jobs?per_page=100&page={page}", "--jq",
                "[.jobs[] | {name, status, conclusion, started_at}]"])
        try:
            got = json.loads(r.stdout or "[]")
        except Exception:
            got = []
        out += got
        if len(got) < 100:
            break
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stall-min", type=float, default=60)
    ap.add_argument("--chunk", type=int, default=8)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    now = datetime.datetime.now(datetime.timezone.utc)
    runs = []
    for status in ("queued", "in_progress"):
        r = sh(["gh", "api", f"repos/{REPO}/actions/workflows/farm.yml/runs?status={status}&per_page=100", "--jq",
                "[.workflow_runs[] | {id, created_at}]"])
        try:
            runs += json.loads(r.stdout or "[]")
        except Exception:
            pass
    n_fixed = 0
    for run in runs:
        js = jobs(run["id"])
        if not js or not all(j["name"][:2] in ("x1", "x2", "x3") for j in js):
            continue
        queued = [j for j in js if j["status"] in ("queued", "waiting", "pending")]
        running = [j for j in js if j["status"] == "in_progress"]
        if not queued or running:
            continue
        starts = [ts(j["started_at"]) for j in js if j.get("started_at") and j["status"] == "completed"]
        last = max(starts) if starts else ts(run["created_at"])
        idle = (now - last).total_seconds() / 60
        if idle < a.stall_min:
            continue
        tags = [j["name"] for j in queued if not os.path.exists(os.path.join(ROOT, "results", j["name"], "job.json"))]
        print(f"[unstall] run {run['id']}: {len(queued)} queued, none running, idle {idle:.0f} min -> re-dispatch {len(tags)}")
        if a.dry_run:
            continue
        c = sh(["gh", "run", "cancel", str(run["id"]), "-R", REPO])
        if c.returncode != 0:
            print(f"[unstall] cancel failed: {c.stderr.strip()[:200]}")
            continue
        for _ in range(24):
            v = sh(["gh", "run", "view", str(run["id"]), "-R", REPO, "--json", "status", "-q", ".status"])
            if v.stdout.strip() == "completed":
                break
            time.sleep(5)
        # a job that slipped into running before the cancel landed is now cancelled; re-dispatch everything not on disk
        tags = [j["name"] for j in jobs(run["id"]) if j.get("conclusion") == "cancelled"
                and not os.path.exists(os.path.join(ROOT, "results", j["name"], "job.json"))]
        for i in range(0, len(tags), a.chunk):
            chunk = tags[i:i + a.chunk]
            r = sh(["gh", "workflow", "run", "farm.yml", "-R", REPO, "--ref", "main", "-f", f"tags={json.dumps(chunk)}",
                    "-f", f"max_parallel={a.chunk}"])
            print(f"[unstall]   {len(chunk)} jobs: {'ok' if r.returncode == 0 else 'FAILED ' + r.stderr[-200:]}")
            time.sleep(2)
        n_fixed += 1
    print(f"[unstall] {n_fixed} stalled runs re-dispatched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
