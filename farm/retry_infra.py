#!/usr/bin/env python3
"""Retry tuning jobs lost to runner failures, once; a second loss counts as a flow that did not finish.

A GitHub-hosted runner can die mid-job ("The runner has received a shutdown signal"), leaving no result: the tuner then
waits for a trial that never lands. For tuning tags (x1*/x2*/x3*/x4*) whose every job across recent farm.yml runs ended in
failure / cancelled / timed_out (none queued, running or successful) and that have no results/<tag>/job.json:
first time -> re-dispatch the same committed spec; second time -> write results/<tag>/job.json with status
"runner_failed" and no metrics, so the tuner scores it like any flow that did not finish (registered rule).
State: results/.retried.json. Usage: retry_infra.py [--pages 2] [--dry-run]
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
STATE = os.path.join(ROOT, "results", ".retried.json")


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    try:
        st = json.load(open(STATE))
    except Exception:
        st = {}
    seen = {}  # tag -> list of (status, conclusion)
    for page in range(1, a.pages + 1):
        r = sh(["gh", "api", f"repos/{REPO}/actions/workflows/farm.yml/runs?per_page=100&page={page}", "--jq",
                "[.workflow_runs[] | {id, created_at}]"])
        try:
            runs = json.loads(r.stdout or "[]")
        except Exception:
            runs = []
        if not isinstance(runs, list):
            runs = []
        for run in runs:
            for jp in range(1, 4):
                j = sh(["gh", "api", f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100&page={jp}", "--jq",
                        "[.jobs[] | {name, status, conclusion}]"])
                try:
                    js = json.loads(j.stdout or "[]")
                except Exception:
                    js = []
                if not isinstance(js, list):  # an API error object instead of a job list
                    print(f"[retry] run {run['id']}: job list unavailable ({str(js)[:80]})")
                    js = []
                for x in js:
                    if not isinstance(x, dict):
                        continue
                    if x["name"][:2] in ("x1", "x2", "x3", "x4", "x5", "x6", "x7"):
                        seen.setdefault(x["name"], []).append((x["status"], x["conclusion"]))
                if len(js) < 100:
                    break
        if len(runs) < 100:
            break
    retry, give_up = [], []
    for tag, lst in seen.items():
        if os.path.exists(os.path.join(ROOT, "results", tag, "job.json")):
            continue
        if any(s != "completed" or c == "success" for s, c in lst):
            continue
        if not all(c in ("failure", "cancelled", "timed_out") for _, c in lst):
            continue
        if not any(c in ("failure", "timed_out") for _, c in lst):
            continue  # only cancelled: a deliberate cancel (unstall/park), whose jobs are re-dispatched by that tool
        n = st.get(tag, {}).get("retries", 0)
        if n == 0:
            retry.append(tag)
        elif n >= 1 and sum(1 for _, c in lst if c == "failure" or c == "timed_out") >= 2:
            give_up.append(tag)
    print(f"[retry] lost jobs: retry {retry}, give up {give_up}")
    if a.dry_run:
        return 0
    for i in range(0, len(retry), 8):
        chunk = retry[i:i + 8]
        r = sh(["gh", "workflow", "run", "farm.yml", "-R", REPO, "--ref", "main", "-f", f"tags={json.dumps(chunk)}",
                "-f", "max_parallel=8"])
        print(f"[retry] re-dispatched {chunk}: {'ok' if r.returncode == 0 else 'FAILED ' + r.stderr[-200:]}")
        if r.returncode == 0:
            for t in chunk:
                st[t] = {"retries": st.get(t, {}).get("retries", 0) + 1,
                         "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
        time.sleep(2)
    for t in give_up:
        d = os.path.join(ROOT, "results", t)
        os.makedirs(d, exist_ok=True)
        json.dump({"tag": t, "status": "runner_failed", "note": "runner lost twice; counted as a flow that did not finish"},
                  open(os.path.join(d, "job.json"), "w"), indent=1)
        st.setdefault(t, {})["gave_up"] = True
    json.dump(st, open(STATE, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
