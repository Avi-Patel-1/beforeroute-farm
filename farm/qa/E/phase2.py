#!/usr/bin/env python3
"""Experiment E (Addendum 42) phase 2: lock the predictions, then dispatch the rebuild chains, then collect.

  phase2.py preflight [--pred DIR]
      per arm: expected / present / VALID prediction records (35 main packets from the committed
      farm/qa/E/packets_manifest.sha256; two-point 19; renaming and shuffled-view controls 6 + 6), invalid and missing
      ones listed; reader slots not saved, not audit-clean or not answered by the registered model listed (reported,
      never dropped); and whether any label job (a job named erk-*) exists yet on the branch. Exit 1 if a required
      record is missing or a label job exists.
  phase2.py lock     [--pred DIR] [--extra FILE ...] [--hash-only FILE ...] [--allow-incomplete REASON]
      runs the preflight (refuses on a missing record or an existing label job unless --allow-incomplete, whose reason
      is committed), copies every prediction (<pred>/<arm>/<packet>.json), the predictor receipts
      (<pred>/../predictor_runs/<arm>/receipt.json), extra files and PREFLIGHT.json into farm/qa/E/locked/, writes
      farm/qa/E/locked/MANIFEST.sha256, commits and pushes branch qa-e-reading, then reads the server push time of the
      lock commit (GitHub repository activity API). Prints the lock commit and the push time.
  phase2.py freeze --label rung3 --files rung3/formula.py   (or --label codex_det --hash-only FILE ... [--hash H ...])
      commits the predictor (or only its hashes) to farm/qa/E/frozen/ BEFORE it is run on any test packet.
  phase2.py dispatch --lock-commit SHA
      checks that SHA is pushed (an ancestor of origin/qa-e-reading), that every MANIFEST.sha256 line matches the
      file committed in SHA, that the committed PREFLIGHT.json is complete, that no label job and no other active run
      exists on the branch, then dispatches farm.yml on qa-e-reading with the 35 chain tags (farm/qa/E/chains.json),
      max_parallel 4, and records the run's createdAt, which must be later than the lock's server push time.
  phase2.py evidence --lock-commit SHA [--json OUT]
      ordering evidence: the lock's commit time and SERVER push time, every run on the branch with a chain job
      (createdAt, head_sha, contains the lock?, workflow/runner blobs pinned at that head, duplicate or re-dispatched
      tags) and the earliest creation time among runs matching the lock.
  phase2.py collect --run RUN_ID --dest DIR
      downloads only the result-erk-* artifacts of that workflow run into DIR (chain.json + small per-rebuild files).
Then: score.py --chains DIR --key <private>/packet_key.json --pred <pred> --out score.json
"""
from __future__ import annotations

import argparse
import datetime
import glob
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
WT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
REPO = "Avi-Patel-1/beforeroute-farm"
BRANCH = "qa-e-reading"
R = "/home/claude/ideas/overnight/reading"
TRAILER = ("\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
           "Claude-Session: https://claude.ai/code/session_016XcZ7Zp4en4cWPeoAqbHJG")
MAIN_ARMS = ["rung1", "rung2", "rung3", "codex_det", "raw_claim", "law", "io_rule", "handpicked"]
READER_ARMS = ["rung1", "rung2", "rung2_rename", "rung2_shuffle"]
READER_MODEL = "claude-opus-5-5"


def sh(cmd, **k):
    print("+", " ".join(cmd), flush=True)
    return subprocess.run(cmd, check=True, text=True, capture_output=True, cwd=WT, **k).stdout


def sha(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def gh_json(path):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"gh api {path}: {out.stderr.strip()[:300]}")
    return json.loads(out.stdout)


def branch_runs():
    return gh_json(f"repos/{REPO}/actions/runs?branch={BRANCH}&per_page=100")["workflow_runs"]


def label_jobs():
    """Every job on this branch whose name is a registered chain tag (erk-*; smoke-erk-* are training-design smoke).
    Any such job means a label may exist: the lock must come first."""
    found = []
    for r in branch_runs():
        for j in gh_json(f"repos/{REPO}/actions/runs/{r['id']}/jobs?per_page=100&filter=all")["jobs"]:
            if re.match(r"^erk-", j["name"]):
                found.append({"run": r["id"], "job": j["name"], "created_at": r["created_at"]})
    return found


def push_time(commit):
    """Server-side time at which `commit` reached refs/heads/qa-e-reading (GitHub repository activity API)."""
    acts = gh_json(f"repos/{REPO}/activity?ref=refs/heads/{BRANCH}&per_page=100")
    for a in acts:
        if a.get("after") == commit:
            return a["timestamp"]
    for a in sorted(acts, key=lambda x: x["timestamp"]):    # pushed as part of a later push
        r = subprocess.run(["git", "merge-base", "--is-ancestor", commit, a["after"]], cwd=WT)
        if r.returncode == 0:
            return a["timestamp"]
    return None


# ---------------------------------------------------------------- validation (the scorer's rules, strict)
def finite(x):
    return not isinstance(x, bool) and isinstance(x, (int, float)) and math.isfinite(x)


def valid_record(path, pid, arm):
    """Return None if the record is a valid prediction in the registered shape, else the reason. Invalid records are
    registered abstentions (clarification 2); missing ones are reported separately."""
    try:
        p = json.load(open(path))
    except Exception as e:
        return f"unreadable: {type(e).__name__}"
    if not isinstance(p, dict):
        return "not an object"
    if p.get("packet_id") != pid:
        return f"packet_id {p.get('packet_id')!r}"
    if p.get("arm") != arm:
        return f"arm {p.get('arm')!r}"
    if "error" in p:
        return f"predictor error: {str(p['error'])[:80]}"
    if not finite(p.get("p_pass")) or not 0.0 <= p["p_pass"] <= 1.0:
        return f"p_pass {p.get('p_pass')!r}"
    if p.get("call") not in ("pass", "fail", "abstain"):
        return f"call {p.get('call')!r}"
    if not finite(p.get("slope")) and not finite(p.get("claim1_ns")):
        return "slope missing"
    if "kept_clock_ns" not in p:
        return "kept_clock_ns missing"
    k = p["kept_clock_ns"]
    if k is not None and (not finite(k) or k <= 0):
        return f"kept_clock_ns {k!r}"
    return None


def expected_sets():
    main, rungs = [], {}
    for line in open(os.path.join(HERE, "packets_manifest.sha256")):
        s = line.split()
        if len(s) == 2:
            pid, rung, _ = s[1].split("/", 2)
            rungs.setdefault(pid, set()).add(rung)
    main = sorted(p for p, r in rungs.items() if r == {"rung1", "rung2"})
    exp = {arm: main for arm in MAIN_ARMS}
    idx = json.load(open(os.path.join(R, "packets_index.json")))
    for ctl in ("rung2_rename", "rung2_shuffle"):
        exp[ctl] = sorted(idx[ctl])
    key = json.load(open(os.path.join(R, "private", "packet_key.json")))      # read, never printed
    exp["two_point"] = sorted(p for p, v in key["packets"].items() if v.get("kind") == "main" and v.get("has_second_point"))
    assert sorted(idx["main"]) == main, "packets_index.json main != committed packets_manifest.sha256"
    return exp


def preflight(a, quiet=False):
    exp = expected_sets()
    res = {"when_utc": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"),
           "arms": {}, "readers": {}, "blocking": []}
    for arm, pids in exp.items():
        d = os.path.join(a.pred, arm)
        present = sorted(os.path.splitext(f)[0] for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []
        invalid = {}
        for pid in present:
            if pid in pids:
                why = valid_record(os.path.join(d, pid + ".json"), pid, arm)
                if why:
                    invalid[pid] = why
        missing = sorted(set(pids) - set(present))
        extra = sorted(set(present) - set(pids))
        res["arms"][arm] = {"expected": len(pids), "present": len(set(present) & set(pids)),
                            "valid": len(set(present) & set(pids)) - len(invalid), "invalid": invalid,
                            "missing": missing, "extra": extra}
        if missing or extra:
            res["blocking"].append(f"{arm}: {len(missing)} missing, {len(extra)} unexpected")
        if invalid and arm not in READER_ARMS:
            res["blocking"].append(f"{arm}: {len(invalid)} invalid predictor records")
    for d in sorted(glob.glob(os.path.join(a.pred, "*"))):
        if os.path.isdir(d) and os.path.basename(d) not in exp:
            res["blocking"].append(f"unregistered arm folder {os.path.basename(d)}")
    tok = json.load(open(os.path.join(R, "private", "reader_tokens.json")))
    slots = {}
    for t, e in tok.items():
        slots.setdefault(e["arm"], []).append(e)
    for arm in READER_ARMS:
        es = slots.get(arm, [])
        rep = {"slots": len(es), "saved": sum(1 for e in es if e.get("saved")),
               "audit_clean": sum(1 for e in es if e.get("audit_clean") is True),
               "not_clean": [{"pid": e["pid"], "outside": e.get("outside", [])[:4]} for e in es
                             if e.get("saved") and e.get("audit_clean") is not True],
               "not_saved": sorted(e["pid"] for e in es if not e.get("saved")),
               "status_not_ok": {e["pid"]: e.get("status") for e in es if e.get("saved") and e.get("status") != "ok"},
               "other_model": {e["pid"]: e.get("models") for e in es if e.get("saved")
                               and any(m != READER_MODEL for m in (e.get("models") or [READER_MODEL]))}}
        res["readers"][arm] = rep
        if rep["slots"] != len(exp[arm]):
            res["blocking"].append(f"{arm}: {rep['slots']} reader slots for {len(exp[arm])} packets")
    try:
        res["label_jobs"] = label_jobs()
    except Exception as e:
        res["label_jobs"] = None
        res["blocking"].append(f"label-job check failed: {e}")
    if res["label_jobs"]:
        res["blocking"].append(f"{len(res['label_jobs'])} label job(s) already exist")
    res["complete"] = not res["blocking"]
    if not quiet:
        print(f"{'arm':14s} {'exp':>4s} {'have':>4s} {'valid':>5s}  missing / invalid")
        for arm, v in res["arms"].items():
            print(f"{arm:14s} {v['expected']:4d} {v['present']:4d} {v['valid']:5d}  {len(v['missing'])} / "
                  f"{len(v['invalid'])}" + (f"  invalid: {v['invalid']}" if v["invalid"] else ""))
        for arm, v in res["readers"].items():
            print(f"readers {arm:14s} slots {v['slots']} saved {v['saved']} audit-clean {v['audit_clean']}"
                  + (f" | NOT CLEAN {v['not_clean']}" if v["not_clean"] else "")
                  + (f" | status {v['status_not_ok']}" if v["status_not_ok"] else "")
                  + (f" | other model {v['other_model']}" if v["other_model"] else ""))
        print(f"label jobs on {BRANCH}: {res['label_jobs']}")
        print("PREFLIGHT", "COMPLETE" if res["complete"] else "INCOMPLETE: " + "; ".join(res["blocking"]))
    return res


def cmd_preflight(a):
    res = preflight(a)
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    return 0 if res["complete"] else 1


def lock(a):
    res = preflight(a)
    if not res["complete"] and not a.allow_incomplete:
        print("[lock] refusing: preflight incomplete (use --allow-incomplete REASON to lock what exists, on record)")
        return 1
    if res["label_jobs"]:
        print("[lock] refusing: a label job already exists; the lock must precede every label")
        return 1
    res["allow_incomplete_reason"] = a.allow_incomplete
    dst = os.path.join(HERE, "locked")
    if os.path.exists(dst) and os.listdir(dst):
        print(f"[lock] refusing: {dst} already exists (one lock)")
        return 1
    os.makedirs(dst, exist_ok=True)
    n = 0
    for p in sorted(glob.glob(os.path.join(a.pred, "*", "*.json"))):
        arm = os.path.basename(os.path.dirname(p))
        os.makedirs(os.path.join(dst, "predictions", arm), exist_ok=True)
        shutil.copy2(p, os.path.join(dst, "predictions", arm, os.path.basename(p)))
        n += 1
    for rc in sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(a.pred)), "predictor_runs", "*", "receipt.json"))):
        arm = os.path.basename(os.path.dirname(rc))
        os.makedirs(os.path.join(dst, "predictor_runs", arm), exist_ok=True)
        shutil.copy2(rc, os.path.join(dst, "predictor_runs", arm, "receipt.json"))
    names = [os.path.basename(f) for f in a.extra or []]
    if len(set(names)) != len(names):
        print(f"[lock] refusing: duplicate basenames in --extra {names}")
        return 1
    for f in a.extra or []:
        shutil.copy2(f, os.path.join(dst, os.path.basename(f)))
    if a.hash_only:     # commit to private files (packet key, packets) without revealing them
        open(os.path.join(dst, "HASHES_PRIVATE.txt"), "w").write(
            "".join(f"{sha(f)}  {os.path.basename(f)}\n" for f in a.hash_only))
    json.dump(res, open(os.path.join(dst, "PREFLIGHT.json"), "w"), indent=1)
    lines = []
    for p in sorted(glob.glob(os.path.join(dst, "**", "*"), recursive=True)):
        if os.path.isfile(p) and not p.endswith("MANIFEST.sha256"):
            lines.append(f"{sha(p)}  {os.path.relpath(p, dst)}")
    open(os.path.join(dst, "MANIFEST.sha256"), "w").write("\n".join(lines) + "\n")
    counts = ", ".join(f"{k} {v['valid']}/{v['expected']}" for k, v in res["arms"].items())
    sh(["git", "add", "-A", os.path.relpath(dst, WT)])
    sh(["git", "commit", "-q", "-m", f"Addendum 42: lock {n} predictions before any rebuild is dispatched\n\n"
        f"Valid/expected per arm: {counts}." + TRAILER])
    sh(["git", "push", "-q", "origin", BRANCH])
    c = sh(["git", "rev-parse", "HEAD"]).strip()
    ct = sh(["git", "show", "-s", "--format=%cI", c]).strip()
    pt = None
    for _ in range(12):
        pt = push_time(c)
        if pt:
            break
        time.sleep(5)
    print(f"[lock] {n} predictions locked; commit {c} (commit time {ct}); server push time {pt}; "
          f"manifest sha256 {sha(os.path.join(dst, 'MANIFEST.sha256'))}")
    log = os.environ.get("E_PHASE2_LOG", os.path.join(R, "private", "phase2_log.txt"))
    with open(log, "a") as f:
        f.write(json.dumps({"lock_commit": c, "lock_commit_time": ct, "lock_push_time": pt, "predictions": n}) + "\n")
    return 0


def freeze(a):
    """Commit a predictor (rung 3's formula) or only its hashes (Codex's) BEFORE it is run on any test packet."""
    dst = os.path.join(HERE, "frozen")
    os.makedirs(dst, exist_ok=True)
    lines = []
    for f in a.files or []:
        shutil.copy2(f, os.path.join(dst, os.path.basename(f)))
        lines.append(f"{sha(f)}  {os.path.basename(f)}  (file committed)")
    for f in a.hash_only or []:
        lines.append(f"{sha(f)}  {os.path.basename(f)}  (hash only)")
    for h in a.hash or []:
        lines.append(f"{h}  (hash given: {a.label})")
    if a.note:
        lines.append(f"# {a.note}")
    open(os.path.join(dst, f"FROZEN_{a.label}.txt"), "w").write("\n".join(lines) + "\n")
    sh(["git", "add", "-A", os.path.relpath(dst, WT)])
    sh(["git", "commit", "-q", "-m", f"Addendum 42: freeze {a.label} before it sees any test packet" + TRAILER])
    sh(["git", "push", "-q", "origin", BRANCH])
    c = sh(["git", "rev-parse", "HEAD"]).strip()
    print(f"[freeze] {a.label}: commit {c}\n" + "\n".join(lines))


def dispatch(a):
    sh(["git", "fetch", "-q", "origin", BRANCH])
    a.lock_commit = sh(["git", "rev-parse", "--verify", a.lock_commit + "^{commit}"]).strip()
    sh(["git", "merge-base", "--is-ancestor", a.lock_commit, f"origin/{BRANCH}"])
    man = sh(["git", "show", f"{a.lock_commit}:farm/qa/E/locked/MANIFEST.sha256"])
    bad = 0
    for line in man.splitlines():
        h, rel = line.split(None, 1)
        blob = subprocess.run(["git", "show", f"{a.lock_commit}:farm/qa/E/locked/{rel}"], cwd=WT, capture_output=True).stdout
        if hashlib.sha256(blob).hexdigest() != h:
            bad += 1
            print("[dispatch] manifest mismatch:", rel)
    if bad:
        print("[dispatch] refusing: the lock commit's files do not match its manifest")
        return 1
    pre = json.loads(sh(["git", "show", f"{a.lock_commit}:farm/qa/E/locked/PREFLIGHT.json"]))
    if not pre.get("complete") and not pre.get("allow_incomplete_reason"):
        print("[dispatch] refusing: the locked preflight is incomplete")
        return 1
    lj = label_jobs()
    if lj:
        print(f"[dispatch] refusing: label jobs already exist: {lj}")
        return 1
    active = [r["id"] for r in branch_runs() if r["status"] != "completed"]
    if active:
        print(f"[dispatch] refusing: active run(s) on {BRANCH}: {active} (one active run per workstream)")
        return 1
    chains = json.load(open(os.path.join(HERE, "chains.json")))["chains"]
    tags = [c["tag"] for c in chains]
    for t in tags:
        assert os.path.exists(os.path.join(WT, "farm", "jobs", t + ".json")), t
    # Scheduling only (the jobs are independent and deterministic): longest first, by each source's own capture-flow
    # time, so the long picorv32 chains do not start last behind the 4-job limit. Registered order if unavailable.
    src_dir = os.path.join(R, "private", "sources")
    try:
        secs = {c["tag"]: float(json.load(open(os.path.join(src_dir, c["source"], "job.json")))["flow_seconds"])
                for c in chains}
        tags = sorted(tags, key=lambda t: (-secs[t], tags.index(t)))
        order_note = "longest first by source capture-flow seconds"
    except Exception as e:
        order_note = f"registered order ({type(e).__name__})"
    print(f"[dispatch] job order ({order_note}): {tags}")
    lock_time = sh(["git", "show", "-s", "--format=%cI", a.lock_commit]).strip()
    pt = push_time(a.lock_commit)
    if not pt:
        print("[dispatch] refusing: no server push time found for the lock commit")
        return 1
    head = sh(["git", "rev-parse", f"origin/{BRANCH}"]).strip()
    if subprocess.run(["git", "diff", "--quiet", head, "--", ".github/workflows/farm.yml", "br/run_job.py",
                       "farm/jobs", "farm/qa/E/chains.json"], cwd=WT).returncode != 0:
        print("[dispatch] refusing: the local workflow / runner / chain specs differ from origin")
        return 1
    pins = pinned_files(head)
    print(f"[dispatch] dispatching at origin/{BRANCH} = {head}; pinned {json.dumps(pins)}")
    before = {r["id"] for r in branch_runs()}
    out = sh(["gh", "workflow", "run", "farm.yml", "-R", REPO, "--ref", BRANCH, "-f", "tags=" + json.dumps(tags),
              "-f", "max_parallel=4"])
    print(out)
    run = None
    for _ in range(24):
        new = [r for r in branch_runs() if r["id"] not in before]
        if new:
            run = sorted(new, key=lambda r: r["created_at"])[0]
            break
        time.sleep(5)
    created = run["created_at"] if run else None
    run_head = run["head_sha"] if run else None
    head_ok = run_head == head
    order_ok = bool(created and created > pt) and head_ok
    log = os.environ.get("E_PHASE2_LOG", os.path.join(R, "private", "phase2_log.txt"))
    with open(log, "a") as f:
        f.write(json.dumps({"lock_commit": a.lock_commit, "lock_commit_time": lock_time, "lock_push_time": pt,
                            "chain_run": run["id"] if run else None, "chain_run_created_at": created,
                            "chain_run_head_sha": run_head, "chain_run_workflow_path": run.get("path") if run else None,
                            "pinned_at_head": pins, "created_after_push": order_ok, "job_order": tags,
                            "job_order_rule": order_note, "dispatch_output": out.strip()}) + "\n")
    print(f"[dispatch] lock commit {a.lock_commit} (commit time {lock_time}, pushed {pt}); chain run "
          f"{run['id'] if run else '?'} created {created} at head {run_head} (= dispatched head: {head_ok}); "
          f"created after the lock push: {order_ok}")
    return 0 if order_ok else 1


def pinned_files(commit):
    """Git blob id and SHA-256 of the files that define a chain job at `commit` (the workflow, the runner, the
    chain index); the run executes the workflow file of its head_sha."""
    out = {}
    for f in (".github/workflows/farm.yml", "br/run_job.py", "farm/qa/E/chains.json"):
        blob = sh(["git", "rev-parse", f"{commit}:{f}"]).strip()
        data = subprocess.run(["git", "cat-file", "blob", blob], cwd=WT, capture_output=True).stdout
        out[f] = {"blob": blob, "sha256": hashlib.sha256(data).hexdigest()}
    return out


def evidence(a):
    """Ordering evidence for the lock receipt and E_RESULT.md: the lock commit's commit time and SERVER push time,
    every workflow run on the branch that contains a chain job (erk-*), with createdAt, head_sha, whether its head
    contains the lock commit, run attempts, its workflow / runner blobs, per-tag job counts (duplicates and
    re-dispatches listed), and the earliest creation time among the runs that match the lock."""
    sh(["git", "fetch", "-q", "origin", BRANCH])
    a.lock_commit = sh(["git", "rev-parse", "--verify", a.lock_commit + "^{commit}"]).strip()
    ct = sh(["git", "show", "-s", "--format=%cI", a.lock_commit]).strip()
    pt = push_time(a.lock_commit)
    runs, seen = [], {}
    for r in sorted(branch_runs(), key=lambda r: r["created_at"]):
        jobs = gh_json(f"repos/{REPO}/actions/runs/{r['id']}/jobs?per_page=100&filter=all")["jobs"]
        erk = [j for j in jobs if re.match(r"^erk-", j["name"])]
        if not erk:
            continue
        contains = subprocess.run(["git", "merge-base", "--is-ancestor", a.lock_commit, r["head_sha"]],
                                  cwd=WT).returncode == 0
        starts = sorted(j["started_at"] for j in erk if j.get("started_at"))
        for j in erk:
            seen.setdefault(j["name"], []).append({"run": r["id"], "attempt": j.get("run_attempt"),
                                                    "conclusion": j.get("conclusion"), "status": j.get("status")})
        runs.append({"run": r["id"], "created_at": r["created_at"], "run_started_at": r.get("run_started_at"),
                     "head_sha": r["head_sha"], "run_attempt": r.get("run_attempt"), "event": r.get("event"),
                     "workflow_path": r.get("path"), "contains_lock_commit": contains, "erk_jobs": len(erk),
                     "first_job_started_at": starts[0] if starts else None,
                     "pinned_at_head": pinned_files(r["head_sha"])})
    match = [r for r in runs if r["contains_lock_commit"]]
    dup = {t: v for t, v in seen.items() if len(v) > 1}
    out = {"lock_commit": a.lock_commit, "lock_commit_time": ct, "lock_push_time_server": pt, "chain_runs": runs,
           "earliest_matching_chain_run_created_at": min((r["created_at"] for r in match), default=None),
           "all_chain_runs_created_after_lock_push": bool(pt) and all(r["created_at"] > pt for r in runs),
           "chain_runs_not_containing_lock": [r["run"] for r in runs if not r["contains_lock_commit"]],
           "tags_with_more_than_one_job": dup, "distinct_erk_tags": len(seen)}
    print(json.dumps(out, indent=1))
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    return 0 if out["all_chain_runs_created_after_lock_push"] and not out["chain_runs_not_containing_lock"] else 1


def collect(a):
    """Download each result-erk-* artifact of the run, keep ONLY the chain record (chain.json, or chain_partial.json
    for an infrastructure loss), the job record and each rebuild's job.json + metrics.json (gzipped); delete the rest."""
    import gzip as _gz
    import tempfile
    os.makedirs(a.dest, exist_ok=True)
    tags = a.tags or [c["tag"] for c in json.load(open(os.path.join(HERE, "chains.json")))["chains"]]
    got = 0
    for t in tags:
        if os.path.exists(os.path.join(a.dest, t, "chain.json")):
            got += 1
            continue
        tmp = tempfile.mkdtemp(prefix="e_collect_", dir=a.dest)
        r = subprocess.run(["gh", "run", "download", str(a.run), "-R", REPO, "-n", "result-" + t, "-D", tmp],
                           capture_output=True, text=True)
        if r.returncode == 0:
            dst = os.path.join(a.dest, t)
            os.makedirs(dst, exist_ok=True)
            for f in ("chain.json", "chain_partial.json", "job.json"):
                if os.path.exists(os.path.join(tmp, f)):
                    shutil.copy2(os.path.join(tmp, f), os.path.join(dst, f))
            for sub in sorted(glob.glob(os.path.join(tmp, "rebuilds", "*", ""))):
                k = os.path.basename(os.path.dirname(sub))
                for f in ("job.json", "metrics.json"):
                    if os.path.exists(os.path.join(sub, f)):
                        os.makedirs(os.path.join(dst, "rebuilds", k), exist_ok=True)
                        with open(os.path.join(sub, f), "rb") as fi, _gz.open(os.path.join(dst, "rebuilds", k, f + ".gz"), "wb") as fo:
                            shutil.copyfileobj(fi, fo)
            got += os.path.exists(os.path.join(dst, "chain.json"))
            state = "chain.json" if os.path.exists(os.path.join(dst, "chain.json")) else \
                ("INFRA LOSS (chain_partial.json)" if os.path.exists(os.path.join(dst, "chain_partial.json")) else "no chain record")
        else:
            state = "not downloadable: " + r.stderr.strip()[:160]
        shutil.rmtree(tmp, ignore_errors=True)
        print(t, state, flush=True)
    print(f"[collect] {got}/{len(tags)} chain records in {a.dest}")


def main() -> int:
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    pp = sp.add_parser("preflight")
    pp.add_argument("--pred", default=os.path.join(R, "predictions"))
    pp.add_argument("--json", default=None)
    p1 = sp.add_parser("lock")
    p1.add_argument("--pred", default=os.path.join(R, "predictions"))
    p1.add_argument("--extra", nargs="*")
    p1.add_argument("--hash-only", nargs="*")
    p1.add_argument("--allow-incomplete", default=None)
    p0 = sp.add_parser("freeze")
    p0.add_argument("--label", required=True)
    p0.add_argument("--files", nargs="*")
    p0.add_argument("--hash-only", nargs="*")
    p0.add_argument("--hash", nargs="*")
    p0.add_argument("--note", default=None)
    p2 = sp.add_parser("dispatch")
    p2.add_argument("--lock-commit", required=True)
    p4 = sp.add_parser("evidence")
    p4.add_argument("--lock-commit", required=True)
    p4.add_argument("--json", default=None)
    p3 = sp.add_parser("collect")
    p3.add_argument("--run", required=True)
    p3.add_argument("--dest", required=True)
    p3.add_argument("--tags", nargs="*", help="override the 35 registered chain tags (smoke only)")
    a = ap.parse_args()
    return {"preflight": cmd_preflight, "lock": lock, "freeze": freeze, "dispatch": dispatch,
            "collect": collect, "evidence": evidence}[a.cmd](a) or 0


if __name__ == "__main__":
    raise SystemExit(main())
