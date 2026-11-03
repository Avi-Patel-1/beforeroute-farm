#!/usr/bin/env python3
"""Workstream B (constraint hygiene): run one group of a farm/qa/B dispatch spec on a GitHub runner, every flow in the
pinned LibreLane image via br/run_job.py (exactly as farm.yml runs one job).

A group holds
  "runs":   independent flows {"tag", "base_spec", "period", "D", "io0", "F_best", ["io_override"]}; or
  "chains": registered rebuild chains {"chain_id", "design", "base_spec", "D", "io0", "F_best", "drv_ref",
            "tag_prefix", "stop_after_first_pass", "state": [...] (resume only)}; step 0 replays the winner's job spec at
            its own search target (base_spec's CLOCK_PERIOD) with frozen I/O, then blib.chain_next steps the chain.
plus "timeout_s" (per flow), "budget_s" (wall budget for this job: no new flow starts once elapsed + the expected flow
time exceeds it; the chain is then left incomplete for the resume stage), "est_flow_s".
Every flow's job spec = base_spec's design/config/overrides, CLOCK_PERIOD = target, IO_DELAY_CONSTRAINT = the frozen
value (blib.io_pct), skip_dumps. Results: results/<tag>/ (br/run_job.py) and results/chains/<chain_id>.json (state).
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blib  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
T_START = time.time()


def cpu_model() -> str:
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return platform.processor() or "?"


def make_spec(tag: str, base_spec: str, period: float, io_value) -> str:
    base = json.load(open(os.path.join(REPO, base_spec)))
    ov = dict(base.get("overrides") or {})
    ov["CLOCK_PERIOD"] = period
    if io_value is not None:
        ov["IO_DELAY_CONSTRAINT"] = io_value
    spec = {"tag": tag, "design": base["design"], "config": base["config"], "overrides": ov, "skip_dumps": True,
            "b_base_spec": base_spec}
    p = os.path.join(REPO, "farm", "qa", "B", "specs", tag + ".json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(spec, open(p, "w"), indent=1)
    return os.path.relpath(p, REPO)


def run_flow(tag: str, base_spec: str, period: float, io_value, image: str, results: str, timeout_s: int) -> dict:
    spec_rel = make_spec(tag, base_spec, period, io_value)
    cmd = ["docker", "run", "--rm", "--name", tag, "-v", f"{REPO}:/work", "-w", "/work", "-e", "PDK_ROOT=/work/pdk",
           image, "python3", "br/run_job.py", "--job-spec", spec_rel, "--jobs", "4", "--results",
           os.path.relpath(results, REPO), "--pdk-root", "/work/pdk", "--timeout", str(timeout_s)]
    t0 = time.time()
    print(f"[b] start {tag}: {base_spec} at {period} ns, IO_DELAY_CONSTRAINT {io_value}", flush=True)
    os.makedirs(os.path.join(results, tag), exist_ok=True)
    with open(os.path.join(results, tag, "docker.log"), "w") as lf:
        try:
            rc = subprocess.call(cmd, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout_s + 900)
        except subprocess.TimeoutExpired:
            subprocess.call(["docker", "kill", tag])
            rc = -9
    subprocess.call(["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}", results])
    host = {"tag": tag, "docker_rc": rc, "wall_s": round(time.time() - t0, 1), "cpu": cpu_model(),
            "runner": os.environ.get("RUNNER_NAME"), "gh_run_id": os.environ.get("GITHUB_RUN_ID"),
            "gh_sha": os.environ.get("GITHUB_SHA"), "image": image, "spec": spec_rel}
    json.dump(host, open(os.path.join(results, tag, "host.json"), "w"), indent=1)
    return host


def within_budget(budget_s, est_s) -> bool:
    if not budget_s:
        return True
    return (time.time() - T_START) + float(est_s or 0) <= float(budget_s)


def run_chain(ch: dict, image: str, results: str, timeout_s: int, budget_s, est_s, stage: int) -> dict:
    D, io0, Fb, ref = ch["D"], ch["io0"], ch["F_best"], ch.get("drv_ref")
    state = list(ch.get("state") or [])
    steps = list(ch.get("steps") or [])
    est = est_s
    incomplete_reason = None
    stopped_first_pass = False
    while True:
        if not state:                       # step 0: the winner replayed at its own search target with frozen I/O
            T0 = float(json.load(open(os.path.join(REPO, ch["base_spec"])))["overrides"]["CLOCK_PERIOD"])
            nxt, why = T0, "winner replayed at its search target (frozen I/O)"
        else:
            nxt, why = blib.chain_next(state, int(ch.get("max_rebuilds", blib.MAX_REBUILDS)))
            if nxt is not None and ch.get("stop_after_first_pass") and stage == 1 and \
                    blib.first_pass_clock(state) is not None:
                stopped_first_pass = True
                incomplete_reason = "stage 1 ends at the first passing rebuild"
                steps.append({"after": state[-1]["tag"], "next": nxt, "why": why + " [deferred to the resume stage]",
                              "stage": stage})
                break
        steps.append({"after": state[-1]["tag"] if state else None, "next": nxt, "why": why, "stage": stage})
        print(f"[b] chain {ch['chain_id']}: next={nxt} ({why})", flush=True)
        if nxt is None:
            break
        reuse = next((s for s in state if abs(s["period"] - nxt) < 1e-9), None)
        if reuse is not None:               # same setting at the same clock: deterministic flow, reuse the result
            state.append(dict(reuse, reused=True))
            continue
        if not within_budget(budget_s, est):
            incomplete_reason = "job time budget"
            steps[-1]["deferred"] = True
            break
        k = len(state)
        tag = f"{ch['tag_prefix']}{k}"
        io_value = blib.io_pct(D, nxt, io0, Fb) if ch.get("frozen", True) else None
        host = run_flow(tag, ch["base_spec"], nxt, io_value, image, results, timeout_s)
        r = blib.load_run(results, tag, nxt, ref)
        if r.get("flow_seconds"):
            est = max(float(est or 0), float(r["flow_seconds"]) + 120)
        retried = False
        if r["claim"] is None:
            # registered handling: one retry with the same tag; a flow error the retry reproduces is a result
            if within_budget(budget_s, est):
                retried = True
                print(f"[b] {tag}: no metrics (docker rc {host['docker_rc']}, status {r['status']}): one retry",
                      flush=True)
                host = run_flow(tag, ch["base_spec"], nxt, io_value, image, results, timeout_s)
                r = blib.load_run(results, tag, nxt, ref)
            else:
                print(f"[b] {tag}: no metrics; retry skipped (job time budget)", flush=True)
        print(f"[b] done {tag}: ws={r['ws']} r2r={r['ws_r2r']} hold={r['hold_ws']} drc={r['drc']} drv={r['drv']}/{ref}"
              f" claim={r['claim']} pass={r['pass']} ({host['wall_s']:.0f} s)", flush=True)
        state.append({"tag": tag, "period": nxt, "claim": r["claim"], "pass": r["pass"], "ws": r["ws"],
                      "ws_r2r": r["ws_r2r"], "hold_ws": r["hold_ws"], "drc": r["drc"], "drv": r["drv"],
                      "port": r["port"], "io_pct": io_value, "status": r["status"], "retried": retried,
                      "flow_seconds": r.get("flow_seconds")})
        if len(state) == 1 and r["claim"] is None:
            steps.append({"after": tag, "next": None, "why": "winner replay has no claim", "stage": stage})
            break
    complete = incomplete_reason is None
    res = {k: v for k, v in ch.items() if k not in ("state", "steps")}
    res.update({"state": state, "steps": steps, "stage": stage, "complete": complete,
                "incomplete_reason": incomplete_reason, "stopped_at_first_pass": stopped_first_pass,
                "kept_clock": blib.kept_clock(state), "first_pass_clock": blib.first_pass_clock(state),
                "first_rebuild": blib.first_rebuild(state), "updated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                                         time.gmtime())})
    os.makedirs(os.path.join(results, "chains"), exist_ok=True)
    json.dump(res, open(os.path.join(results, "chains", ch["chain_id"] + ".json"), "w"), indent=1)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--group", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--results", default="results")
    ap.add_argument("--stage", type=int, default=1)
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    grp = next(g for g in spec["groups"] if g["name"] == a.group)
    results = os.path.abspath(a.results)
    os.makedirs(results, exist_ok=True)
    to = int(grp.get("timeout_s", 16000))
    budget = grp.get("budget_s")
    est = grp.get("est_flow_s", 0)
    print(f"[b] batch {spec['batch']} group {a.group} stage {a.stage}: cpu={cpu_model()} nproc={os.cpu_count()} "
          f"budget={budget}", flush=True)
    for r in grp.get("runs") or []:
        if not within_budget(budget, est):
            print(f"[b] {r['tag']}: deferred (job time budget)", flush=True)
            os.makedirs(os.path.join(results, "deferred"), exist_ok=True)
            json.dump(r, open(os.path.join(results, "deferred", r["tag"] + ".json"), "w"), indent=1)
            continue
        io_value = r.get("io_override", blib.io_pct(r["D"], r["period"], r["io0"], r["F_best"]))
        run_flow(r["tag"], r["base_spec"], r["period"], io_value, a.image, results, to)
        x = blib.load_run(results, r["tag"], r["period"], r.get("drv_ref"))
        if x["claim"] is None and within_budget(budget, est):      # registered: one retry with the same tag
            print(f"[b] {r['tag']}: no metrics (status {x['status']}): one retry", flush=True)
            run_flow(r["tag"], r["base_spec"], r["period"], io_value, a.image, results, to)
            x = blib.load_run(results, r["tag"], r["period"], r.get("drv_ref"))
        if x.get("flow_seconds"):
            est = max(float(est or 0), float(x["flow_seconds"]) + 120)
        meta = {k: v for k, v in r.items() if k not in ("io_override",)}
        meta.update({"io_value": io_value, "stage": a.stage})
        json.dump(meta, open(os.path.join(results, r["tag"], "b_meta.json"), "w"), indent=1)
        print(f"[b] done {r['tag']}: ws={x['ws']} r2r={x['ws_r2r']} hold={x['hold_ws']} claim={x['claim']}", flush=True)
    for ch in grp.get("chains") or []:
        run_chain(ch, a.image, results, to, budget, est, a.stage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
