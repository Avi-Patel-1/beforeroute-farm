#!/usr/bin/env python3
"""IO1 runner-side job: one source run at the winner's settings and search target, optionally with a pin plan and a
capture of the raw record, and optionally its registered rebuild chain, all inside one GitHub Actions job.

Usage (farm.yml, inside the LibreLane image): io_run.py --job-spec farm/jobs/<tag>.json [--results results]
       [--pdk-root /work/pdk] [--jobs 4]
Job spec: {"tag", "design", "config", "overrides" (winner's settings; CLOCK_PERIOD = the search target T0),
           "io": {"mode": "single"|"chain", "case", "arm", "plan": repo-relative plan JSON or null,
                  "capture": bool, "drv_ref": int, "max_rebuilds": 4}}
Every run goes through br/run_job.py unchanged. With a plan, the run's config also gets IOPINS_PLAN and
meta.substituting_steps {"+OpenROAD.IOPlacement": "IOPins.ApplyPinPlan"}, and PYTHONPATH carries the plugin; without
one, the run is byte-for-byte the record's job. Output: results/<tag>/{<tag>-r<k>/..., chain.json}.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, HERE)
import iolib  # noqa: E402

PLUGIN_DIR = os.path.join(HERE, "plugin")
META = {"version": 1, "flow": "Classic", "substituting_steps": {"+OpenROAD.IOPlacement": "IOPins.ApplyPinPlan"}}


def one_run(spec, rtag, clock, a, plan_abs, capture, t_end):
    ov = dict(spec["overrides"])
    ov["CLOCK_PERIOD"] = clock
    env = dict(os.environ)
    if plan_abs:
        ov["IOPINS_PLAN"] = plan_abs
        ov["meta"] = META
        env["PYTHONPATH"] = ":".join(x for x in (PLUGIN_DIR, env.get("PYTHONPATH", "")) if x)
    run_spec = {"tag": rtag, "design": spec["design"], "config": spec["config"], "overrides": ov}
    sp = os.path.join(a.results, spec["tag"], f"{rtag}.spec.json")
    json.dump(run_spec, open(sp, "w"), indent=1)
    timeout = int(max(600, min(16000, t_end - time.time())))
    cmd = [sys.executable, os.path.join(ROOT, "br", "run_job.py"), "--job-spec", sp, "--jobs", str(a.jobs),
           "--results", os.path.join(a.results, spec["tag"]), "--pdk-root", a.pdk_root, "--timeout", str(timeout),
           "--keep-run"]
    t0 = time.time()
    r = subprocess.run(cmd, cwd=ROOT, env=env, capture_output=True, text=True)
    rdir = os.path.join(a.results, spec["tag"], rtag)
    os.makedirs(rdir, exist_ok=True)
    open(os.path.join(rdir, "io_run.log"), "w").write(r.stdout[-20000:] + "\n--- stderr ---\n" + r.stderr[-20000:])
    run_dir = os.path.join(ROOT, spec["design"], "runs", rtag)
    for f in glob.glob(os.path.join(run_dir, "*-iopins-applypinplan", "pins_applied.json")):
        shutil.copy2(f, os.path.join(rdir, "pins_applied.json"))
    for f in glob.glob(os.path.join(run_dir, "*-iopins-applypinplan", "*.log")):
        shutil.copy2(f, os.path.join(rdir, "applypinplan.log"))
    if capture and os.path.exists(os.path.join(rdir, "metrics.json")):
        c = subprocess.run([sys.executable, os.path.join(HERE, "capture_run.py"), run_dir, "--out",
                            os.path.join(rdir, "capture"), "--pdk-root", a.pdk_root],
                           cwd=ROOT, env=env, capture_output=True, text=True)
        open(os.path.join(rdir, "capture.log"), "w").write(c.stdout[-20000:] + "\n--- stderr ---\n" + c.stderr[-20000:])
    elif os.path.exists(os.path.join(rdir, "metrics.json")):
        defs = sorted(glob.glob(os.path.join(run_dir, "final", "def", "*.def")))
        if defs:                                   # keep every run's final DEF (pins, placement, routing) for audit
            with open(defs[0], "rb") as fi, gzip.open(os.path.join(rdir, "final.def.gz"), "wb") as fo:
                shutil.copyfileobj(fi, fo)
    for f in ("nets.jsonl", "nets_signoff.jsonl", "final_nets.json"):
        p = os.path.join(rdir, f)
        if os.path.exists(p):
            with open(p, "rb") as fi, gzip.open(p + ".gz", "wb") as fo:
                shutil.copyfileobj(fi, fo)
            os.remove(p)
    shutil.rmtree(run_dir, ignore_errors=True)
    m = {}
    if os.path.exists(os.path.join(rdir, "metrics.json")):
        m = json.load(open(os.path.join(rdir, "metrics.json")))
    job = {}
    if os.path.exists(os.path.join(rdir, "job.json")):
        job = json.load(open(os.path.join(rdir, "job.json")))
    return {"tag": rtag, "clock": clock, "passed": iolib.judge(m, spec["io"]["drv_ref"]), "claim": iolib.claim(m, clock),
            "ws": m.get("timing__setup__ws"), "ws_r2r": m.get("timing__setup_r2r__ws"),
            "hold": m.get("timing__hold__ws"), "drc": m.get("route__drc_errors"), "drv": iolib.drv_count(m) if m else None,
            "flow_completed": bool(m), "status": job.get("status"), "wall_s": round(time.time() - t0, 1),
            "has_job": bool(job)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-spec", required=True)
    ap.add_argument("--results", default=os.path.join(ROOT, "results"))
    ap.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "/work/pdk"))
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--budget-min", type=float, default=280.0, help="wall budget of the whole job (GitHub limit 300)")
    a = ap.parse_args()
    a.results = os.path.abspath(a.results)
    t_end = time.time() + a.budget_min * 60
    spec = json.load(open(a.job_spec))
    io = spec["io"]
    os.makedirs(os.path.join(a.results, spec["tag"]), exist_ok=True)
    plan_abs = os.path.join(ROOT, io["plan"]) if io.get("plan") else None
    plan_sha = hashlib.sha256(open(plan_abs, "rb").read()).hexdigest() if plan_abs else None
    T0 = float(spec["overrides"]["CLOCK_PERIOD"])
    out = {"tag": spec["tag"], "case": io.get("case"), "arm": io.get("arm"), "mode": io["mode"], "T0": T0,
           "drv_ref": io["drv_ref"], "plan": io.get("plan"), "plan_sha256": plan_sha, "runs": [],
           "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    path = os.path.join(a.results, spec["tag"], "chain.json")

    def run(clock, k, capture=False):
        rtag = f"{spec['tag']}-r{k}"
        r = one_run(spec, rtag, clock, a, plan_abs, capture, t_end)
        if not r["has_job"]:                        # infrastructure failure: the same run once more
            r = one_run(spec, rtag, clock, a, plan_abs, capture, t_end)
            r["retried"] = True
        r["kind"] = "source" if k == 0 else "rebuild"
        out["runs"].append(r)
        json.dump(out, open(path, "w"), indent=1)
        print(f"[io] {rtag} at {clock} ns: passed={r['passed']} claim={r['claim']} ws={r['ws']} hold={r['hold']} "
              f"drc={r['drc']} drv={r['drv']} ({r['wall_s']} s)", flush=True)
        return r

    run(T0, 0, capture=bool(io.get("capture")))
    if io["mode"] == "chain":
        k = 1
        while True:
            nxt = iolib.chain_next(T0, out["runs"], io.get("max_rebuilds", 4))
            if nxt is None:
                break
            if time.time() > t_end - 30 * 60:
                out["truncated"] = "job wall budget"
                break
            run(nxt, k)
            k += 1
    out["kept"] = iolib.kept_clock(out["runs"])
    out["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(out, open(path, "w"), indent=1)
    print(json.dumps({k: out[k] for k in ("tag", "T0", "kept")}), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
