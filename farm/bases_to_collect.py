#!/usr/bin/env python3
"""Print the hero bases that have finished runs not yet collected (one per line), so cycle.sh only re-collects those.

A completed run counts as collected once its id is in results/.collected_runs.json; this script writes the ids it
found to results/.collect_pending_runs.json, and `--mark` (run after the bases were collected) moves them into the
collected set. Job names are <base>-<arm>; the base is the longest farm/jobs/<base>.json name prefixing the job name.
Also prints every base with arms on disk but no hero_summary.json yet.
Usage: bases_to_collect.py [--repo owner/name] [--results results] [--pages 2] | bases_to_collect.py --mark
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default="Avi-Patel-1/beforeroute-farm")
    ap.add_argument("--results", default=os.path.join(ROOT, "results"))
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--mark", action="store_true")
    a = ap.parse_args()
    done_p = os.path.join(a.results, ".collected_runs.json")
    pend_p = os.path.join(a.results, ".collect_pending_runs.json")
    try:
        done = set(json.load(open(done_p)))
    except Exception:
        done = set()
    if a.mark:
        try:
            done |= set(json.load(open(pend_p)))
        except Exception:
            pass
        json.dump(sorted(done), open(done_p, "w"))
        return 0
    bases = sorted((os.path.basename(p)[:-5] for p in glob.glob(os.path.join(ROOT, "farm", "jobs", "*.json"))), key=len, reverse=True)
    out, pending = set(), []
    for page in range(1, a.pages + 1):
        r = subprocess.run(["gh", "api", f"repos/{a.repo}/actions/workflows/hero.yml/runs?status=completed&per_page=100&page={page}",
                            "--jq", "[.workflow_runs[].id]"], capture_output=True, text=True)
        try:
            ids = json.loads(r.stdout or "[]")
        except Exception:
            ids = []
        new = [i for i in ids if i not in done]
        pending += new
        for rid in new:
            j = subprocess.run(["gh", "api", f"repos/{a.repo}/actions/runs/{rid}/jobs?per_page=100", "--jq", "[.jobs[].name]"],
                               capture_output=True, text=True)
            try:
                names = json.loads(j.stdout or "[]")
            except Exception:
                names = []
            for n in names:
                b = next((b for b in bases if n.startswith(b + "-")), None)
                if b:
                    out.add(b)
        if len(ids) < 100:
            break
    for b in bases:
        if not os.path.exists(os.path.join(a.results, b, "hero_summary.json")) and glob.glob(os.path.join(a.results, b + "-*", "labels.json")):
            out.add(b)
    json.dump(pending, open(pend_p, "w"))
    print("\n".join(sorted(out)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
