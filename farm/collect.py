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
        # explicit pages on the repos/{owner}/{repo} endpoint: `gh run view --json jobs` pages a run with > 100 jobs
        # through a numeric-ID URL that the network proxy rejects (the 102-job tuning run was silently skipped)
        lines, ok = [], True
        for page in range(1, 4):
            j = sh(["gh", "api", f"repos/{a.repo}/actions/runs/{rid}/jobs?per_page=100&page={page}", "--jq",
                    ".jobs[] | \"\\(.name)\\t\\(.status)\\t\\(.conclusion // \"-\")\""])
            if j.returncode != 0:
                ok = False
                break
            got = [l for l in j.stdout.strip().splitlines() if l.strip()]
            lines += got
            if len(got) < 100:
                break
        if not ok and not lines:
            print(f"[collect] run {rid}: job list failed")
            continue
        for line in lines:
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
            if tag[:2] in ("x1", "x2", "x3"):
                # tuning runs: keep the per-net dumps compressed (~40 MB -> ~6 MB per run; the disk allowance is fixed)
                import gzip as _gz
                for fn in ("nets.jsonl", "nets_signoff.jsonl", "final_nets.json"):
                    p = os.path.join(dst, fn)
                    if os.path.exists(p):
                        with open(p, "rb") as fi, _gz.open(p + ".gz", "wb", compresslevel=6) as fo:
                            shutil.copyfileobj(fi, fo)
                        os.remove(p)
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
