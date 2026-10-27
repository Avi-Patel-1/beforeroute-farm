#!/usr/bin/env python3
"""Collect the outputs of one analyze.yml run into a local directory.

Usage: analysis_collect.py --run-id N --out results/analysis/<name>/ [--repo owner/name] [--with-dataset]

Downloads every analysis-<name>-<index> artifact of the run into <out>/<index>/ (skipping
indices already present, so it can be re-run while the run is in progress), then merges:
  - every CSV with the same file name across indices -> <out>/<file>.csv (+ an `_index` column)
  - every JSON with the same file name across indices -> <out>/<file>.all.json ({index: content})
and writes <out>/run.json (run status, per-job conclusions, the dataset manifest summary).
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import os
import re
import shutil
import subprocess
import tempfile


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True)


def gh_lines(path, jq):
    r = sh(["gh", "api", "--paginate", path, "--jq", jq])
    if r.returncode != 0:
        raise SystemExit(f"gh api {path}: {r.stderr.strip()[:300]}")
    return [json.loads(l) for l in r.stdout.splitlines() if l.strip()]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--repo", default="Avi-Patel-1/beforeroute-farm")
    ap.add_argument("--with-dataset", action="store_true", help="also download the run's dataset artifact (large)")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    run = json.loads(sh(["gh", "api", f"repos/{a.repo}/actions/runs/{a.run_id}"]).stdout or "{}")
    jobs = gh_lines(f"repos/{a.repo}/actions/runs/{a.run_id}/jobs?per_page=100&filter=latest",
                    ".jobs[] | {name, status, conclusion, started_at, completed_at}")
    arts = gh_lines(f"repos/{a.repo}/actions/runs/{a.run_id}/artifacts?per_page=100",
                    ".artifacts[] | {id, name, size_in_bytes, expired}")
    pat = re.compile(r"^analysis-(.+)-(\d+)$")
    got = skipped = failed = 0
    for art in sorted(arts, key=lambda x: x["name"]):
        m = pat.match(art["name"])
        if not m or art["expired"]:
            continue
        idx = int(m.group(2))
        dst = os.path.join(a.out, f"{idx:03d}")
        if os.path.exists(os.path.join(dst, "_meta.json")):
            skipped += 1
            continue
        with tempfile.TemporaryDirectory() as td:
            r = sh(["gh", "run", "download", str(a.run_id), "-R", a.repo, "-n", art["name"], "-D", td])
            if r.returncode != 0:
                print(f"[collect] {art['name']}: download failed: {r.stderr.strip()[:200]}")
                failed += 1
                continue
            shutil.copytree(td, dst, dirs_exist_ok=True)
        got += 1
    if a.with_dataset and any(x["name"] == "dataset" for x in arts):
        dd = os.path.join(a.out, "dataset")
        if not os.path.exists(os.path.join(dd, "dataset.parquet")):
            r = sh(["gh", "run", "download", str(a.run_id), "-R", a.repo, "-n", "dataset", "-D", dd])
            print(f"[collect] dataset: {'ok' if r.returncode == 0 else r.stderr.strip()[:200]}")

    # merge per-index outputs
    idx_dirs = sorted(d for d in glob.glob(os.path.join(a.out, "[0-9][0-9][0-9]")) if os.path.isdir(d))
    csv_names = sorted({os.path.basename(p) for d in idx_dirs for p in glob.glob(os.path.join(d, "*.csv"))})
    for name in csv_names:
        rows, fields = [], ["_index"]
        for d in idx_dirs:
            p = os.path.join(d, name)
            if not os.path.exists(p):
                continue
            with open(p, newline="") as f:
                for r in csv.DictReader(f):
                    r["_index"] = os.path.basename(d)
                    rows.append(r)
                    for k in r:
                        if k not in fields:
                            fields.append(k)
        with open(os.path.join(a.out, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    json_names = sorted({os.path.basename(p) for d in idx_dirs for p in glob.glob(os.path.join(d, "*.json"))})
    for name in json_names:
        merged = {}
        for d in idx_dirs:
            p = os.path.join(d, name)
            if os.path.exists(p):
                try:
                    merged[os.path.basename(d)] = json.load(open(p))
                except Exception as e:
                    merged[os.path.basename(d)] = {"_error": str(e)}
        json.dump(merged, open(os.path.join(a.out, os.path.splitext(name)[0] + ".all.json"), "w"), indent=1)

    info = {"run_id": a.run_id, "status": run.get("status"), "conclusion": run.get("conclusion"),
            "created_at": run.get("created_at"), "head_sha": run.get("head_sha"),
            "jobs": {j["name"]: f"{j['status']}/{j['conclusion']}" for j in jobs},
            "artifacts_downloaded": got, "already_present": skipped, "download_failed": failed,
            "indices": [os.path.basename(d) for d in idx_dirs], "merged_csv": csv_names}
    json.dump(info, open(os.path.join(a.out, "run.json"), "w"), indent=1)
    done = sum(1 for j in jobs if j["status"] == "completed")
    print(f"[collect] run {a.run_id} {run.get('status')}/{run.get('conclusion')}: jobs {done}/{len(jobs)} completed; "
          f"{got} new, {skipped} present, {failed} failed; merged {len(csv_names)} CSV(s) -> {a.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
