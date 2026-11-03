#!/usr/bin/env python3
"""Workstream B, arm C3: E5's run_group.py (farm/qa/E5/run_group.py) with the I/O budget frozen: every run and every
chain carries "io_p0" (the design's ORFS default period, ps), passed to farm/qa/B3/orfs_run.sh as IO_P0. The judge and the
chain rule are E5's own (farm/qa/E5/e5lib.py, imported unchanged).
Original E5 docstring follows.
E5 (Addendum 41): run one group of farm/qa/E5/dispatch.json on a GitHub runner, in the pinned ORFS image.

A group holds either
  "runs":   independent flow runs, {"tag", "design", "period", "vars", "setting", "kind"}; or
  "chains": registered rebuild chains, {"chain_id", "design", "setting", "vars", "tag_prefix",
            "winner": {"tag", "period", "claim", "pass"}}; each chain is stepped here with e5lib.chain_next, one flow
            at a time, so a chain needs no round trip through the dispatcher.
plus "num_cores", "timeout_s" and "parallel" (flows run at once; default 1). Every flow: farm/qa/E5/orfs_run.sh in a
fresh container; results/<tag>/ gets run.json (from the container) and job.json (from here).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "E5"))
import e5lib  # noqa: E402  (E5's judge and chain rule, unchanged)

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def cpu_model() -> str:
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "?"


def run_one(run: dict, image: str, results: str, num_cores: int, timeout_s: int) -> dict:
    tag = run["tag"]
    out = os.path.join(results, tag)
    os.makedirs(out, exist_ok=True)
    mv = " ".join(f"{k}={v}" for k, v in sorted((run.get("vars") or {}).items()))
    env = {"TAG": tag, "DESIGN": run["design"], "PERIOD": str(run["period"]), "NUM_CORES": str(num_cores),
           "MAKE_VARS": mv, "RUN_TIMEOUT": str(timeout_s), "IO_P0": str(run.get("io_p0") or "")}
    cmd = ["docker", "run", "--rm", "--name", tag, "-v", f"{REPO}:/work"]
    for k, v in env.items():
        cmd += ["-e", f"{k}={v}"]
    cmd += [image, "bash", "/work/farm/qa/B3/orfs_run.sh"]
    t0 = time.time()
    print(f"[b3] start {tag}: {run['design']} {run['period']} ps {mv} io_p0={run.get('io_p0')}", flush=True)
    with open(os.path.join(out, "docker.log"), "w") as lf:
        try:
            rc = subprocess.call(cmd, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout_s + 600)
        except subprocess.TimeoutExpired:
            subprocess.call(["docker", "kill", tag])
            rc = -9
    subprocess.call(["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}", out])
    runj = {}
    try:
        runj = json.load(open(os.path.join(out, "run.json")))
    except Exception:
        pass
    job = {"tag": tag, "design": run["design"], "period": run["period"], "vars": run.get("vars") or {},
           "setting": run.get("setting"), "kind": run.get("kind"), "chain_id": run.get("chain_id"),
           "io_p0": run.get("io_p0"),
           "num_cores": num_cores, "status": runj.get("status", "no_run_json"), "docker_rc": rc,
           "wall_s": round(time.time() - t0, 1), "cpu": cpu_model(), "nproc": os.cpu_count(), "image": image,
           "runner": os.environ.get("RUNNER_NAME"), "gh_run_id": os.environ.get("GITHUB_RUN_ID"),
           "gh_sha": os.environ.get("GITHUB_SHA")}
    json.dump(job, open(os.path.join(out, "job.json"), "w"), indent=1)
    r = e5lib.load_run(out)
    print(f"[e5] done  {tag}: status={r['status']} ws={r['ws']} hold={r['hold_ws']} drc={r['drc']} "
          f"claim={r['claim']} pass={r['pass']} ({job['wall_s']:.0f} s)", flush=True)
    return r


def run_chain(ch: dict, image: str, results: str, num_cores: int, timeout_s: int) -> dict:
    w = dict(ch["winner"])
    state = [{"tag": w["tag"], "period": w["period"], "claim": w["claim"], "pass": w["pass"]}]
    log = []
    k = 0
    while True:
        nxt, why = e5lib.chain_next(state)
        log.append({"after": state[-1]["tag"], "next": nxt, "why": why})
        print(f"[e5] chain {ch['chain_id']}: next={nxt} ({why})", flush=True)
        if nxt is None:
            break
        k += 1
        reuse = next((s for s in state if s["period"] == nxt), None)
        if reuse is not None:   # same configuration at the same clock: the flow is deterministic, reuse the result
            state.append(dict(reuse, reused=True))
            continue
        run = {"tag": f"{ch['tag_prefix']}{k}", "design": ch["design"], "period": nxt, "vars": ch.get("vars") or {},
               "setting": ch.get("setting"), "kind": "rebuild", "chain_id": ch["chain_id"], "io_p0": ch.get("io_p0")}
        r = run_one(run, image, results, num_cores, timeout_s)
        state.append({"tag": r["tag"], "period": nxt, "claim": r["claim"], "pass": r["pass"]})
    res = {"chain_id": ch["chain_id"], "design": ch["design"], "setting": ch.get("setting"), "winner": w,
           "io_p0": ch.get("io_p0"),
           "chain": state, "steps": log, "kept_clock": e5lib.kept_clock(state)}
    os.makedirs(os.path.join(results, "chains"), exist_ok=True)
    json.dump(res, open(os.path.join(results, "chains", ch["chain_id"] + ".json"), "w"), indent=1)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--group", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--results", default="results")
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    grp = next(g for g in spec["groups"] if g["name"] == a.group)
    results = os.path.abspath(a.results)
    os.makedirs(results, exist_ok=True)
    nc = int(grp.get("num_cores", 4))
    to = int(grp.get("timeout_s", 3 * 3600))
    par = int(grp.get("parallel", 1))
    print(f"[e5] batch {spec['batch']} group {a.group}: cpu={cpu_model()} nproc={os.cpu_count()} num_cores={nc}",
          flush=True)
    with ThreadPoolExecutor(max_workers=par) as ex:
        if grp.get("runs"):
            list(ex.map(lambda r: run_one(r, a.image, results, nc, to), grp["runs"]))
        if grp.get("chains"):
            list(ex.map(lambda c: run_chain(c, a.image, results, nc, to), grp["chains"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
