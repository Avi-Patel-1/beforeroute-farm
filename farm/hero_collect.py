#!/usr/bin/env python3
"""Collect hero-arm artifacts (hero-<base>-<arm>) into results/ and summarize the arms.

Usage: hero_collect.py --repo owner/name --base <base_tag> [--results results] [--run-id N]
Writes results/<base>/hero_summary.json (one row per arm) and prints a table.
Each artifact carries its own copy of the baseline results (rebuilt on that runner); the
first copy is kept as results/<base>/ if absent, later ones are checked for identity.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "br"))
from run_hero import arm_summary  # noqa: E402


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--base", required=True)
    ap.add_argument("--results", default="results")
    ap.add_argument("--run-id", default=None)
    a = ap.parse_args()
    runs = [a.run_id] if a.run_id else json.loads(sh(["gh", "run", "list", "-R", a.repo, "-w", "hero.yml", "--limit", "300", "--json", "databaseId", "--jq", "[.[].databaseId]"]).stdout)
    # cache of finished runs' job lists (they never change), so each call only queries live runs
    cache_path = os.path.join(a.results, ".hero_runs_cache.json")
    try:
        cache = json.load(open(cache_path))
    except Exception:
        cache = {}
    arms = []
    base_metrics = None
    for rid in runs:
        ent = cache.get(str(rid))
        if ent is None or not ent.get("done"):
            j = sh(["gh", "run", "view", str(rid), "-R", a.repo, "--json", "status,jobs", "--jq", '"\\(.status)\\n" + ([.jobs[] | "\\(.name)\\t\\(.status)"] | join("\\n"))'])
            lines = j.stdout.strip().splitlines()
            if not lines:
                continue
            ent = {"done": lines[0] == "completed", "jobs": lines[1:]}
            cache[str(rid)] = ent
        if not any(l.startswith(a.base + "-") for l in ent["jobs"]):
            continue
        for line in ent["jobs"]:
            name, status = line.split("\t")[:2]
            if not name.startswith(a.base + "-") or status != "completed":
                continue
            arm = name[len(a.base) + 1:]
            arm_tag = f"{a.base}-{arm}"
            dst = os.path.join(a.results, arm_tag)
            if not os.path.exists(os.path.join(dst, "job.json")):
                with tempfile.TemporaryDirectory() as td:
                    d = sh(["gh", "run", "download", str(rid), "-R", a.repo, "-n", f"hero-{name}", "-D", td])
                    if d.returncode != 0:
                        print(f"[hero] {name}: no artifact")
                        continue
                    src_arm = os.path.join(td, arm_tag)
                    src_base = os.path.join(td, a.base)
                    if os.path.exists(src_arm):
                        shutil.copytree(src_arm, dst, dirs_exist_ok=True)
                    if os.path.exists(src_base):
                        # always keep the lists the runner scored/used for this arm (flagged_*.json, tiers_*.json, *.scores.csv)
                        os.makedirs(os.path.join(a.results, a.base), exist_ok=True)
                        for fn in os.listdir(src_base):
                            if fn.startswith(("flagged_", "tiers_")):
                                shutil.copy2(os.path.join(src_base, fn), os.path.join(a.results, a.base, fn))
                        bm = json.load(open(os.path.join(src_base, "metrics.json"))) if os.path.exists(os.path.join(src_base, "metrics.json")) else None
                        if base_metrics is None:
                            base_metrics = bm
                        if not os.path.exists(os.path.join(a.results, a.base, "job.json")):
                            shutil.copytree(src_base, os.path.join(a.results, a.base), dirs_exist_ok=True)
                        elif bm is not None:
                            local = json.load(open(os.path.join(a.results, a.base, "metrics.json")))
                            same = all(local.get(k) == bm.get(k) for k in ("design__instance__area__stdcell", "design__instance__count", "design__max_slew_violation__count"))
                            if not same:
                                print(f"[hero] WARNING: baseline rebuilt on runner for {name} differs from local baseline")
            if os.path.exists(os.path.join(dst, "job.json")):
                arms.append(arm_tag)
    try:
        json.dump(cache, open(cache_path, "w"))
    except Exception:
        pass
    rows = [arm_summary(a.results, a.base)] + [arm_summary(a.results, t) for t in sorted(set(arms))]
    out = os.path.join(a.results, a.base, "hero_summary.json")
    json.dump({"base": a.base, "arms": rows}, open(out, "w"), indent=1)
    base_area = rows[0].get("stdcell_area")
    print(f"{'arm':30s} {'status':10s} {'viol_nets':>9s} {'slew':>6s} {'cap':>4s} {'fan':>4s} {'area':>8s} {'dArea%':>7s} {'insts':>6s} {'setup_ws':>8s} {'hold_ws':>7s} {'secs':>6s}")
    for r in rows:
        da = (r.get("stdcell_area", 0) - base_area) / base_area * 100 if base_area and r.get("stdcell_area") else float("nan")
        print(f"{r['tag']:30s} {str(r.get('status')):10s} {str(r.get('signoff_violating_nets')):>9s} {str(r.get('max_slew_count')):>6s} {str(r.get('max_cap_count')):>4s} {str(r.get('max_fanout_count')):>4s} {str(r.get('stdcell_area')):>8s} {da:7.2f} {str(r.get('instances')):>6s} {str(round(r.get('setup_ws') or 0, 3)):>8s} {str(round(r.get('hold_ws') or 0, 3)):>7s} {str(r.get('flow_seconds')):>6s}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
