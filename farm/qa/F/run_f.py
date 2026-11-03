#!/usr/bin/env python3
"""F (overnight workstream F): run one group of farm/qa/F/dispatch.json on a GitHub runner.

A group holds "items", each {"config": <id in configs.json>, "tag_prefix": ..., "mode": "chain" | "single",
"periods": [...] (single mode only)}. Chain mode = the registered protocol, stepped here with flib.chain_next so
nothing waits on a dispatcher: the replay of the published configuration at its published target T0 (tag
<prefix>0), then its rebuild chain (tags <prefix>1, <prefix>2, ...). Single mode (smoke only) runs the listed periods.
"budget_s" (default 16200 s = 270 min): no new flow is started once the job has used this much wall time; the chain
file then records "truncated by job budget".
Results: results/<tag>/ (run.json, job.json, metrics, reports, gzipped logs) and results/chains/<config>.json.
"""
from __future__ import annotations

import argparse
import json
import os
import platform as pyplatform
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import flib  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
IMAGES = {
    "orfsagent": "openroad/orfs@sha256:6fe655d0d5f33e2f344ec4ce1641b613b7bb90ec4cda279d2407386ed78ff6b3",
    "edaenv": "eda-env-evaluator:iccad26",
}
T_START = time.time()


def cpu_model() -> str:
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return pyplatform.processor() or "?"


def run_one(cfg: dict, tag: str, period: float, kind: str, src: str, results: str, timeout_s: int) -> dict:
    out = os.path.join(results, tag)
    os.makedirs(out, exist_ok=True)
    ps = flib.fmt_period(period, cfg["grid"])
    t0 = time.time()
    print(f"[F] start {tag}: {cfg['id']} {cfg['design']}/{cfg['platform']} period {ps} ({kind})", flush=True)
    if cfg["harness"] == "orfsagent":
        k = cfg["knobs"]
        env = {"TAG": tag, "DESIGN": cfg["design"], "TECH": cfg["platform"], "PERIOD": ps,
               "UTIL": k["UTIL"], "LB_ADDON": k["LB_ADDON"], "TNS": k["TNS_End_Percent"], "HIER": k["HIER_SYNTH"],
               "GP_PAD": k["GP_PAD"], "DP_PAD": k["DP_PAD"], "DPO": k["DPO"], "CTS_CSIZE": k["CTS_CSIZE"],
               "CTS_CDIA": k["CTS_CDIA"], "PIN_ADJ": k["PIN_ADJ"], "UP_ADJ": k["UP_ADJ"], "AR": k["AR"],
               "POWER_EFFORT": k["POWER_EFFORT"], "RD": k["RD"], "TD": k["TD"], "RUN_TIMEOUT": timeout_s,
               "CFG_DIR": "/src/orfsagent/autotune_configs"}
        cmd = ["docker", "run", "--rm", "--name", tag, "-v", f"{REPO}:/work", "-v", f"{src}:/src:ro"]
        for kk, v in env.items():
            cmd += ["-e", f"{kk}={v}"]
        cmd += [IMAGES["orfsagent"], "bash", "/work/farm/qa/F/orfsagent_run.sh"]
        with open(os.path.join(out, "docker.log"), "w") as lf:
            try:
                rc = subprocess.call(cmd, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout_s + 600)
            except subprocess.TimeoutExpired:
                subprocess.call(["docker", "kill", tag])
                rc = -9
        subprocess.call(["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}", out])
    else:
        cmd = [sys.executable, os.path.join(HERE, "edaenv_run.py"), "--src", os.path.join(src, "EDA-env"),
               "--task", cfg["task"], "--submission", cfg["submission"], "--period", ps, "--tag", tag,
               "--results", results, "--image", IMAGES["edaenv"]]
        with open(os.path.join(out, "driver.log"), "w") as lf:
            try:
                rc = subprocess.call(cmd, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout_s + 1800)
            except subprocess.TimeoutExpired:
                rc = -9
    job = {"tag": tag, "config": cfg["id"], "harness": cfg["harness"], "period": float(ps), "kind": kind,
           "docker_rc": rc, "wall_s": round(time.time() - t0, 1), "cpu": cpu_model(), "nproc": os.cpu_count(),
           "image": IMAGES[cfg["harness"]], "runner": os.environ.get("RUNNER_NAME"),
           "gh_run_id": os.environ.get("GITHUB_RUN_ID"), "gh_sha": os.environ.get("GITHUB_SHA")}
    json.dump(job, open(os.path.join(out, "job.json"), "w"), indent=1)
    r = flib.load_run(out)
    print(f"[F] done  {tag}: status={r['status']} ws={r['ws']} hold={r['hold_ws']} drc={r['drc']} "
          f"claim={r['claim']} pass={r['pass']} ({job['wall_s']:.0f} s)", flush=True)
    return r


def run_chain(cfg: dict, item: dict, src: str, results: str, timeout_s: int, budget_s: int, phase: str) -> dict:
    """phase "primary": the replay and the first rebuild only; "continue": resume from results/chains/<id>.json
    (downloaded from the primary job) and finish the chain; "all": both in one go."""
    pre = item["tag_prefix"]
    pub = cfg["published"]
    grid = cfg["grid"]
    cpath = os.path.join(results, "chains", pre.rstrip("-") + ".json")
    if phase == "continue":
        if not os.path.exists(cpath):
            print(f"[F] chain {cfg['id']}: no primary chain file; nothing to continue", flush=True)
            return {}
        prev = json.load(open(cpath))
        if prev.get("complete"):
            print(f"[F] chain {cfg['id']}: already complete in the primary phase", flush=True)
            return prev
        state, log = prev["chain"], prev["steps"]
        log = [s for s in log if s.get("why") not in ("primary phase ends here", "truncated by job budget")]
        k = len(state) - 1
    else:
        w = run_one(cfg, pre + "0", float(pub["T0"]), "replay", src, results, timeout_s)
        state = [{"tag": w["tag"], "period": float(pub["T0"]), "claim": w["claim"], "pass": w["pass"]}]
        log, k = [], 0
    truncated = False
    while True:
        nxt, why = flib.chain_next(state, grid)
        if nxt is None:
            log.append({"after": state[-1]["tag"], "next": None, "why": why})
            print(f"[F] chain {cfg['id']}: ends ({why})", flush=True)
            break
        if phase == "primary" and len(state) >= 2:
            log.append({"after": state[-1]["tag"], "next": nxt, "why": "primary phase ends here"})
            print(f"[F] chain {cfg['id']}: primary phase done; next would be {nxt} ({why})", flush=True)
            break
        if time.time() - T_START > budget_s:
            truncated = True
            log.append({"after": state[-1]["tag"], "next": nxt, "why": "truncated by job budget"})
            break
        log.append({"after": state[-1]["tag"], "next": nxt, "why": why})
        print(f"[F] chain {cfg['id']}: next={nxt} ({why})", flush=True)
        k += 1
        reuse = next((s for s in state if abs(s["period"] - nxt) < 1e-9), None)
        if reuse is not None:   # same configuration, same clock: deterministic flow, reuse the result
            state.append(dict(reuse, reused=True))
            continue
        r = run_one(cfg, f"{pre}{k}", nxt, "rebuild", src, results, timeout_s)
        state.append({"tag": r["tag"], "period": float(nxt), "claim": r["claim"], "pass": r["pass"]})
    done = not truncated and not (log and log[-1]["why"] == "primary phase ends here")
    res = {"config": cfg["id"], "source": cfg["source"], "design": cfg["design"], "platform": cfg["platform"],
           "grid": grid, "published": pub, "replay": state[0], "chain": state, "steps": log,
           "kept_clock": flib.kept_clock(state), "complete": done, "truncated": truncated, "phase": phase}
    os.makedirs(os.path.join(results, "chains"), exist_ok=True)
    json.dump(res, open(cpath, "w"), indent=1)
    return res


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--group", required=True)
    ap.add_argument("--src", required=True, help="fetched sources (fetch_sources.sh)")
    ap.add_argument("--results", default="results")
    ap.add_argument("--phase", default="all", choices=["all", "primary", "continue"])
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    cfgs = {c["id"]: c for c in json.load(open(os.path.join(HERE, "configs.json")))["configs"]}
    if os.path.exists(os.path.join(HERE, "configs_smoke.json")):
        cfgs.update({c["id"]: c for c in json.load(open(os.path.join(HERE, "configs_smoke.json")))["configs"]})
    grp = next(g for g in spec["groups"] if g["name"] == a.group)
    results = os.path.abspath(a.results)
    os.makedirs(results, exist_ok=True)
    to = int(grp.get("timeout_s", 14400))
    budget = int(grp.get("budget_s", 16200))
    print(f"[F] batch {spec['batch']} group {a.group}: cpu={cpu_model()} nproc={os.cpu_count()}", flush=True)
    for it in grp["items"]:
        cfg = cfgs[it["config"]]
        if it.get("mode", "chain") == "chain":
            run_chain(cfg, it, os.path.abspath(a.src), results, to, budget, a.phase)
        elif a.phase == "continue":
            continue
        else:
            for i, p in enumerate(it["periods"]):
                if time.time() - T_START > budget:
                    print("[F] job budget reached; stopping", flush=True)
                    break
                run_one(cfg, f"{it['tag_prefix']}{i}", float(p), "smoke", os.path.abspath(a.src), results, to)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
