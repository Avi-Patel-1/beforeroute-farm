#!/usr/bin/env python3
"""Collect farm artifacts into results/<tag>/ as individual jobs complete.

Usage: collect.py --repo owner/name [--results results] [--hours 48] [--limit 20]
For every farm workflow run of the last --hours hours (completed or still in progress), downloads the result-<tag>
artifact of each completed job that is not yet present locally. Runs whose jobs are all collected are remembered in
results/.farm_runs_done.json and skipped.
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


def download_artifact(repo, rid, name, dest, cache):
    """Download one artifact of a run into dest. `gh run download` pages a run's artifact list through a numeric-ID URL that
    the network proxy rejects, so artifacts beyond the first 100 of a large run were never collected (Oct 28: 24 of the
    126-job Addendum-30 run). This lists the artifacts with explicit repos/{owner}/{repo} pages and fetches the zip by id.
    Returns True or an error string."""
    import zipfile
    if rid not in cache:
        arts = {}
        for page in range(1, 6):
            r = sh(["gh", "api", f"repos/{repo}/actions/runs/{rid}/artifacts?per_page=100&page={page}", "--jq",
                    ".artifacts[] | \"\\(.name)\\t\\(.id)\\t\\(.expired)\""])
            if r.returncode != 0:
                return f"artifact list failed: {r.stderr.strip()[:100]}"
            got = [l.split("\t") for l in r.stdout.strip().splitlines() if l.strip()]
            for n, i, exp in got:
                arts[n] = (i, exp == "true")
            if len(got) < 100:
                break
        cache[rid] = arts
    hit = cache[rid].get(name)
    if not hit:
        return "no such artifact"
    if hit[1]:
        return "artifact expired"
    zp = os.path.join(dest, "_a.zip")
    with open(zp, "wb") as fo:
        r = subprocess.run(["gh", "api", f"repos/{repo}/actions/artifacts/{hit[0]}/zip"], stdout=fo, stderr=subprocess.PIPE)
    if r.returncode != 0:
        return f"zip download failed: {r.stderr.decode(errors='replace').strip()[:100]}"
    try:
        with zipfile.ZipFile(zp) as z:
            z.extractall(dest)
    except Exception as e:
        return f"bad zip: {e}"
    finally:
        os.remove(zp)
    return True


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--results", default="results")
    ap.add_argument("--limit", type=int, default=20, help="fallback only: newest runs if the paged listing fails")
    ap.add_argument("--hours", type=float, default=48.0, help="look at every farm.yml run created in the last N hours")
    a = ap.parse_args()
    os.makedirs(a.results, exist_ok=True)
    # every farm.yml run of the last --hours hours (explicit repos/{owner}/{repo} pages: the proxy rejects the numeric-ID
    # URLs `gh run list` uses beyond 100), minus runs already known to be fully collected. A fixed window of the newest
    # --limit runs silently dropped older runs once many small runs were dispatched (Oct 28: Addendum 27's runs).
    done_path = os.path.join(a.results, ".farm_runs_done.json")
    try:
        done = set(json.load(open(done_path)))
    except Exception:
        done = set()
    import datetime as _dt
    since = _dt.datetime.now(_dt.timezone.utc) - _dt.timedelta(hours=a.hours)
    runs = []
    for page in range(1, 11):
        r = sh(["gh", "api", f"repos/{a.repo}/actions/workflows/farm.yml/runs?per_page=100&page={page}", "--jq",
                "[.workflow_runs[] | {databaseId: .id, status, created_at}]"])
        if r.returncode != 0:
            print(r.stderr.strip()[:300])
            break
        got = json.loads(r.stdout or "[]")
        if not isinstance(got, list):
            break
        old = False
        for x in got:
            t = _dt.datetime.strptime(x["created_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=_dt.timezone.utc)
            if t < since:
                old = True
                continue
            runs.append(x)
        if old or len(got) < 100:
            break
    if not runs and a.limit:
        r = sh(["gh", "run", "list", "-R", a.repo, "-w", "farm.yml", "--limit", str(a.limit), "--json", "databaseId,status"])
        runs = json.loads(r.stdout or "[]") if r.returncode == 0 else []
    n_new = n_fail = 0
    pending = 0
    art_cache = {}
    for run in runs:
        rid = run["databaseId"]
        if rid in done:
            continue
        run_open = run.get("status") != "completed"
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
        all_done = ok and not run_open
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
                all_done = False
                continue
            if concl in ("cancelled", "skipped"):
                continue  # a cancelled job uploads only a partial dir; its tag is re-dispatched later
            all_done = False  # re-checked next time once this job's artifact is in
            with tempfile.TemporaryDirectory() as td:
                d = download_artifact(a.repo, rid, f"result-{tag}", td, art_cache)
                if d is not True:
                    print(f"[collect] {tag}: no artifact ({str(d)[:120]})")
                    continue
                if not os.path.exists(os.path.join(td, "job.json")):
                    print(f"[collect] {tag}: artifact has no job.json (partial run) - skipped")
                    continue
                shutil.copytree(td, dst, dirs_exist_ok=True)
            if tag[:2] in ("x1", "x2", "x3", "x4", "x5", "x6", "x7", "x8"):
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
        if all_done:
            done.add(rid)
    json.dump(sorted(done), open(done_path + ".tmp", "w"))
    os.replace(done_path + ".tmp", done_path)
    print(f"[collect] {n_new} new ({n_fail} failed), {pending} still running/queued; {len(runs)} runs in the last {a.hours:g} h")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
