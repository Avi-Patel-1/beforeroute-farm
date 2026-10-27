#!/usr/bin/env python3
"""Park queued hero runs so a newer experiment queues first, then re-queue them unchanged (Addendum 24, farm order).

The runner pool serves queued jobs roughly first come, first served, so a sequential experiment dispatched behind a long
queue waits for all of it. `--park` cancels every hero.yml run that is still queued (none of its jobs started) and records
it; `--release` re-runs the parked runs (same run, same inputs, oldest first), which puts them at the back of the queue.
State: results/.parked_runs.json. Re-run runs are also made visible again to the hero collectors (their run ids are
removed from results/.collected_runs.json and marked live in results/.hero_runs_cache.json).

Usage: park.py --park | --release [--max N] | --release-when-ready [--deadline 2026-10-28T08:00:00Z] | --status
--release-when-ready releases everything once every design of the tuner (results/tune/state.json) has its confirmation
run dispatched, or at the deadline, whichever comes first.
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
STATE = os.path.join(ROOT, "results", ".parked_runs.json")
TUNE_STATE = os.path.join(ROOT, "results", "tune", "state.json")


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load():
    try:
        return json.load(open(STATE))
    except Exception:
        return {"runs": []}


def save(st):
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE + ".tmp", "w"), indent=1)
    os.replace(STATE + ".tmp", STATE)


def queued_hero_runs():
    out = []
    for page in range(1, 6):
        r = sh(["gh", "api", f"repos/{REPO}/actions/workflows/hero.yml/runs?status=queued&per_page=100&page={page}",
                "--jq", "[.workflow_runs[] | {id, head_branch, created_at}]"])
        try:
            got = json.loads(r.stdout or "[]")
        except Exception:
            got = []
        out += got
        if len(got) < 100:
            break
    return out


def park():
    st = load()
    have = {r["id"] for r in st["runs"]}
    runs = queued_hero_runs()
    n = 0
    for run in runs:
        if run["id"] in have:
            continue
        # never touch a run any of whose jobs already started
        j = sh(["gh", "api", f"repos/{REPO}/actions/runs/{run['id']}/jobs?per_page=100", "--jq", "[.jobs[].status]"])
        try:
            statuses = json.loads(j.stdout or "[]")
        except Exception:
            statuses = None
        if statuses is None or any(s not in ("queued", "waiting", "pending") for s in statuses):
            print(f"[park] {run['id']} ({run['head_branch']}): has started jobs or unreadable, left alone")
            continue
        c = sh(["gh", "run", "cancel", str(run["id"]), "-R", REPO])
        if c.returncode != 0:
            print(f"[park] {run['id']}: cancel failed {c.stderr.strip()[:150]}")
            continue
        st["runs"].append({"id": run["id"], "branch": run["head_branch"], "created_at": run["created_at"],
                           "parked_at": now(), "released_at": None})
        n += 1
        save(st)
    print(f"[park] parked {n} queued hero runs ({len(runs)} were queued)")


def unmark_collected(rid):
    p = os.path.join(ROOT, "results", ".collected_runs.json")
    try:
        done = json.load(open(p))
        if rid in done:
            done.remove(rid)
            json.dump(done, open(p, "w"))
    except Exception:
        pass
    p = os.path.join(ROOT, "results", ".hero_runs_cache.json")
    try:
        cache = json.load(open(p))
        cache[str(rid)] = {"done": False, "jobs": [], "t": 0}
        json.dump(cache, open(p, "w"))
    except Exception:
        pass


def release(max_n=None):
    st = load()
    todo = sorted((r for r in st["runs"] if not r.get("released_at")), key=lambda r: r["created_at"])
    if max_n is not None:
        todo = todo[:max_n]
    n = 0
    for r in todo:
        v = sh(["gh", "run", "view", str(r["id"]), "-R", REPO, "--json", "status,conclusion"])
        try:
            info = json.loads(v.stdout or "{}")
        except Exception:
            info = {}
        if info.get("status") != "completed":
            print(f"[park] {r['id']}: still {info.get('status')} (cancellation pending?), not re-run yet")
            continue
        x = sh(["gh", "run", "rerun", str(r["id"]), "-R", REPO])
        if x.returncode != 0:
            print(f"[park] {r['id']}: rerun failed {x.stderr.strip()[:200]}")
            continue
        r["released_at"] = now()
        unmark_collected(r["id"])
        save(st)
        n += 1
        time.sleep(1)
    left = sum(1 for r in st["runs"] if not r.get("released_at"))
    print(f"[park] re-queued {n} runs; {left} still parked")


def ready(deadline):
    if now() >= deadline:
        return True, f"deadline {deadline} reached"
    try:
        tags = json.load(open(TUNE_STATE))["tags"].values()
    except Exception:
        return False, "no tuner state"
    designs = {v["design"] for v in tags}
    confirmed = {v["design"] for v in tags if v["arm"] == "c" and v["status"] != "pending"}
    if designs and designs <= confirmed:
        return True, "every design's confirmation run is dispatched"
    return False, f"confirmation dispatched for {len(confirmed)} of {len(designs)} designs; deadline {deadline}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--park", action="store_true")
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--release-when-ready", action="store_true")
    ap.add_argument("--deadline", default="2026-10-28T08:00:00Z")
    ap.add_argument("--max", type=int, default=None)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.park:
        park()
    if a.release:
        release(a.max)
    if a.release_when_ready:
        ok, why = ready(a.deadline)
        print(f"[park] release {'now' if ok else 'not yet'}: {why}")
        if ok:
            release(a.max)
    if a.status or not (a.park or a.release or a.release_when_ready):
        st = load()
        rel = sum(1 for r in st["runs"] if r.get("released_at"))
        print(f"[park] {len(st['runs'])} parked in total, {rel} re-queued, {len(st['runs']) - rel} waiting")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
