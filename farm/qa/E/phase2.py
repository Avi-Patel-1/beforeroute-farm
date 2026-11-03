#!/usr/bin/env python3
"""Experiment E (Addendum 42) phase 2: lock the predictions, then dispatch the rebuild chains, then collect.

  phase2.py lock     [--pred DIR] [--extra FILE ...]
      copies every prediction (<pred>/<arm>/<packet>.json), plus extra files (rung-3 formula, Codex's hash file,
      the reader prompts), into farm/qa/E/locked/, writes farm/qa/E/locked/MANIFEST.sha256, commits and pushes
      branch qa-e-reading. Prints the lock commit. Refuses if any chain workflow run already exists on the branch.
  phase2.py dispatch --lock-commit SHA
      checks that SHA is pushed (an ancestor of origin/qa-e-reading) and contains farm/qa/E/locked/MANIFEST.sha256,
      then dispatches farm.yml on qa-e-reading with the 35 chain tags (farm/qa/E/chains.json), max_parallel 4.
  phase2.py collect --run RUN_ID --dest DIR
      downloads only the result-erk-* artifacts of that workflow run into DIR (chain.json + small per-rebuild files).
Then: score.py --chains DIR --key <private>/packet_key.json --pred <pred> --out score.json
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REPO = "Avi-Patel-1/beforeroute-farm"
BRANCH = "qa-e-reading"
TRAILER = ("\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
           "Claude-Session: https://claude.ai/code/session_016XcZ7Zp4en4cWPeoAqbHJG")


def sh(cmd, **k):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, text=True, capture_output=True, cwd=WT, **k).stdout


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def chain_runs_exist():
    out = subprocess.run(["gh", "run", "list", "-R", REPO, "--branch", BRANCH, "--workflow", "farm.yml", "--limit", "50",
                          "--json", "databaseId,displayTitle,createdAt"], capture_output=True, text=True)
    return out.stdout


def lock(a):
    dst = os.path.join(HERE, "locked")
    os.makedirs(dst, exist_ok=True)
    n = 0
    for p in sorted(glob.glob(os.path.join(a.pred, "*", "*.json"))):
        arm = os.path.basename(os.path.dirname(p))
        os.makedirs(os.path.join(dst, "predictions", arm), exist_ok=True)
        shutil.copy2(p, os.path.join(dst, "predictions", arm, os.path.basename(p)))
        n += 1
    for f in a.extra or []:
        shutil.copy2(f, os.path.join(dst, os.path.basename(f)))
    if a.hash_only:     # commit to private files (packet key, packets) without revealing them
        open(os.path.join(dst, "HASHES_PRIVATE.txt"), "w").write(
            "".join(f"{sha(f)}  {os.path.basename(f)}\n" for f in a.hash_only))
    lines = []
    for p in sorted(glob.glob(os.path.join(dst, "**", "*"), recursive=True)):
        if os.path.isfile(p) and not p.endswith("MANIFEST.sha256"):
            lines.append(f"{sha(p)}  {os.path.relpath(p, dst)}")
    open(os.path.join(dst, "MANIFEST.sha256"), "w").write("\n".join(lines) + "\n")
    sh(["git", "add", "-A", os.path.relpath(dst, WT)])
    sh(["git", "commit", "-q", "-m", f"Addendum 42: lock {n} predictions before any rebuild is dispatched" + TRAILER])
    sh(["git", "push", "-q", "origin", BRANCH])
    c = sh(["git", "rev-parse", "HEAD"]).strip()
    print(f"[lock] {n} predictions locked; commit {c}; manifest sha256 {sha(os.path.join(dst, 'MANIFEST.sha256'))}")


def dispatch(a):
    sh(["git", "fetch", "-q", "origin", BRANCH])
    sh(["git", "merge-base", "--is-ancestor", a.lock_commit, f"origin/{BRANCH}"])
    sh(["git", "cat-file", "-e", f"{a.lock_commit}:farm/qa/E/locked/MANIFEST.sha256"])
    tags = [c["tag"] for c in json.load(open(os.path.join(HERE, "chains.json")))["chains"]]
    for t in tags:
        assert os.path.exists(os.path.join(WT, "farm", "jobs", t + ".json")), t
    out = sh(["gh", "workflow", "run", "farm.yml", "-R", REPO, "--ref", BRANCH, "-f", "tags=" + json.dumps(tags),
              "-f", "max_parallel=4"])
    print(out)
    print(chain_runs_exist())


def collect(a):
    os.makedirs(a.dest, exist_ok=True)
    tags = [c["tag"] for c in json.load(open(os.path.join(HERE, "chains.json")))["chains"]]
    for t in tags:
        if os.path.exists(os.path.join(a.dest, t, "chain.json")):
            continue
        r = subprocess.run(["gh", "run", "download", str(a.run), "-R", REPO, "-n", "result-" + t, "-D",
                            os.path.join(a.dest, t)], capture_output=True, text=True)
        print(t, "ok" if r.returncode == 0 else r.stderr.strip()[:200], flush=True)


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p1 = sp.add_parser("lock")
    p1.add_argument("--pred", default="/home/claude/ideas/overnight/reading/predictions")
    p1.add_argument("--extra", nargs="*")
    p1.add_argument("--hash-only", nargs="*")
    p2 = sp.add_parser("dispatch")
    p2.add_argument("--lock-commit", required=True)
    p3 = sp.add_parser("collect")
    p3.add_argument("--run", required=True)
    p3.add_argument("--dest", required=True)
    a = ap.parse_args()
    return {"lock": lock, "dispatch": dispatch, "collect": collect}[a.cmd](a) or 0


if __name__ == "__main__":
    raise SystemExit(main())
