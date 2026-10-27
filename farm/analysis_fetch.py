#!/usr/bin/env python3
"""Reconstruct the per-net dataset inputs from farm.yml artifacts (build job of analyze.yml).

  list:     analysis_fetch.py list --repo owner/name --out manifest.json
            Lists farm.yml runs (newest first) and their completed jobs whose tag is a data tag
            (d1-/d2-/d3-/d4-/d3b-/d4b-), with the run's result-<tag> artifact. Writes the candidate
            manifest and prints a cache key (hash of the sorted tag@artifact list).
  download: analysis_fetch.py download --manifest manifest.json --dest data/results [--workers 8]
            Downloads, per tag, the newest candidate artifact whose job.json says "completed"
            (falls back to older candidates of the same tag), keeps only the files
            br/build_dataset.py reads, and writes <dest>/../fetched.json.
  wait:     analysis_fetch.py wait --repo owner/name --run-id N --dest dir [--timeout-min 120]
            Reuse the dataset built by another analyze.yml run: waits for its build job, then
            downloads its "dataset" artifact into dir. Exit 3 if that build failed or timed out.

Uses the gh CLI (GH_TOKEN with actions:read).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

DATA_PREFIXES = ("d1-", "d2-", "d3-", "d4-", "d3b-", "d4b-")
KEEP = {"job.json", "nets.jsonl", "nets_signoff.jsonl", "labels.json", "final_nets.json",
        "resolved.json", "dump_summary.json", "metrics.json"}


def gh_lines(path: str, jq: str) -> list:
    """GET a paginated REST endpoint; one compact JSON value per jq output line."""
    for attempt in range(4):
        r = subprocess.run(["gh", "api", "--paginate", path, "--jq", jq], capture_output=True, text=True)
        if r.returncode == 0:
            return [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
        print(f"[fetch] gh api {path}: {r.stderr.strip()[:200]} (attempt {attempt + 1})", flush=True)
        time.sleep(5 * (attempt + 1))
    raise SystemExit(f"gh api failed: {path}")


def is_data_tag(tag: str) -> bool:
    return tag.startswith(DATA_PREFIXES)


def cmd_list(a) -> int:
    runs = gh_lines(f"repos/{a.repo}/actions/workflows/farm.yml/runs?per_page=100",
                    ".workflow_runs[] | {id, status, conclusion, created_at}")
    runs.sort(key=lambda r: r["created_at"], reverse=True)
    cands: dict[str, list] = {}
    n_jobs = 0
    for run in runs:
        rid = run["id"]
        jobs = gh_lines(f"repos/{a.repo}/actions/runs/{rid}/jobs?per_page=100&filter=latest",
                        ".jobs[] | {name, status, conclusion}")
        good = {j["name"] for j in jobs
                if is_data_tag(j["name"]) and j["status"] == "completed"
                and (j["conclusion"] or "") not in ("cancelled", "skipped")}
        if not good:
            continue
        arts = gh_lines(f"repos/{a.repo}/actions/runs/{rid}/artifacts?per_page=100",
                        ".artifacts[] | {id, name, size_in_bytes, expired}")
        by_name = {x["name"]: x for x in arts if not x["expired"]}
        for tag in sorted(good):
            art = by_name.get(f"result-{tag}")
            if not art:
                continue
            n_jobs += 1
            cands.setdefault(tag, []).append({"run_id": rid, "run_status": run["status"], "artifact_id": art["id"],
                                              "bytes": art["size_in_bytes"], "created_at": run["created_at"]})
    key_src = "\n".join(f"{t}@{','.join(str(c['artifact_id']) for c in cands[t])}" for t in sorted(cands))
    key = hashlib.sha256(key_src.encode()).hexdigest()[:20]
    man = {"repo": a.repo, "farm_runs": len(runs), "tags": len(cands), "candidates": n_jobs, "key": key,
           "total_mb_newest": round(sum(c[0]["bytes"] for c in cands.values()) / 1e6, 1),
           "by_tag": {t: cands[t] for t in sorted(cands)}}
    json.dump(man, open(a.out, "w"), indent=1)
    print(f"[fetch] {len(runs)} farm runs, {len(cands)} data tags ({n_jobs} candidate artifacts, "
          f"{man['total_mb_newest']} MB newest), key={key}", flush=True)
    if a.github_output and os.environ.get("GITHUB_OUTPUT"):
        with open(os.environ["GITHUB_OUTPUT"], "a") as f:
            f.write(f"key={key}\ntags={len(cands)}\n")
    return 0


def _fetch_one(repo: str, tag: str, cands: list, dest: str) -> dict:
    tried = []
    for c in cands:  # newest first
        with tempfile.TemporaryDirectory(dir=os.path.dirname(dest)) as td:
            ok = False
            for attempt in range(3):
                r = subprocess.run(["gh", "run", "download", str(c["run_id"]), "-R", repo, "-n", f"result-{tag}", "-D", td],
                                   capture_output=True, text=True)
                if r.returncode == 0:
                    ok = True
                    break
                time.sleep(3 * (attempt + 1))
            if not ok:
                tried.append({"run_id": c["run_id"], "status": "download_failed", "err": r.stderr.strip()[:160]})
                continue
            try:
                st = json.load(open(os.path.join(td, "job.json"))).get("status")
            except Exception:
                st = "no_job_json"
            if st != "completed" or not os.path.exists(os.path.join(td, "nets.jsonl")):
                tried.append({"run_id": c["run_id"], "status": st if st != "completed" else "no_nets_jsonl"})
                continue
            out = os.path.join(dest, tag)
            os.makedirs(out, exist_ok=True)
            for fn in os.listdir(td):
                if fn in KEEP:
                    shutil.move(os.path.join(td, fn), os.path.join(out, fn))
            return {"tag": tag, "status": "completed", "run_id": c["run_id"], "artifact_id": c["artifact_id"], "tried": tried}
    return {"tag": tag, "status": tried[0]["status"] if tried else "none", "tried": tried}


def cmd_download(a) -> int:
    man = json.load(open(a.manifest))
    os.makedirs(a.dest, exist_ok=True)
    t0 = time.time()
    res = []
    with ThreadPoolExecutor(a.workers) as ex:
        futs = [ex.submit(_fetch_one, man["repo"], t, c, a.dest) for t, c in man["by_tag"].items()]
        for i, f in enumerate(futs):
            r = f.result()
            res.append(r)
            if (i + 1) % 25 == 0:
                print(f"[fetch] {i + 1}/{len(futs)} tags ({time.time() - t0:.0f}s)", flush=True)
    ok = [r for r in res if r["status"] == "completed"]
    summ = {"key": man["key"], "tags_listed": len(res), "completed": len(ok),
            "not_completed": {r["tag"]: r["status"] for r in res if r["status"] != "completed"},
            "used": {r["tag"]: {"run_id": r["run_id"], "artifact_id": r["artifact_id"]} for r in ok},
            "seconds": round(time.time() - t0, 1)}
    json.dump(summ, open(os.path.join(os.path.dirname(os.path.abspath(a.dest)), "fetched.json"), "w"), indent=1)
    print(f"[fetch] {len(ok)}/{len(res)} tags completed and fetched in {time.time() - t0:.0f}s; "
          f"{len(res) - len(ok)} not usable", flush=True)
    return 0 if ok else 1


def cmd_wait(a) -> int:
    end = time.time() + 60 * a.timeout_min
    while time.time() < end:
        jobs = gh_lines(f"repos/{a.repo}/actions/runs/{a.run_id}/jobs?per_page=100&filter=latest",
                        '.jobs[] | select(.name == "build") | {status, conclusion}')
        if jobs and jobs[0]["status"] == "completed":
            if jobs[0]["conclusion"] != "success":
                print(f"[fetch] build job of run {a.run_id} concluded {jobs[0]['conclusion']}", flush=True)
                return 3
            os.makedirs(a.dest, exist_ok=True)
            r = subprocess.run(["gh", "run", "download", str(a.run_id), "-R", a.repo, "-n", "dataset", "-D", a.dest],
                               capture_output=True, text=True)
            if r.returncode == 0 and os.path.exists(os.path.join(a.dest, "dataset.parquet")):
                print(f"[fetch] reused dataset of analyze run {a.run_id}", flush=True)
                return 0
            print(f"[fetch] download failed: {r.stderr.strip()[:200]}", flush=True)
            return 3
        print(f"[fetch] waiting for build job of run {a.run_id} ({jobs[0]['status'] if jobs else 'not started'})", flush=True)
        time.sleep(60)
    return 3


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("list")
    p.add_argument("--repo", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--github-output", action="store_true", help="write key=/tags= to $GITHUB_OUTPUT")
    p = sub.add_parser("download")
    p.add_argument("--manifest", required=True)
    p.add_argument("--dest", required=True)
    p.add_argument("--workers", type=int, default=8)
    p = sub.add_parser("wait")
    p.add_argument("--repo", required=True)
    p.add_argument("--run-id", required=True)
    p.add_argument("--dest", required=True)
    p.add_argument("--timeout-min", type=float, default=120)
    a = ap.parse_args()
    return {"list": cmd_list, "download": cmd_download, "wait": cmd_wait}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
