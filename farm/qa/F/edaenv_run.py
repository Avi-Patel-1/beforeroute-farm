#!/usr/bin/env python3
"""F (overnight workstream F): one EDA-env flow + measurement on the runner, with EDA-env's own evaluator code.

Replay  (period == the task's evaluation clock): the task package exactly as published; the evaluator's worker.py
        runs the flow phase (applies the published submission.diff, sanitizes config.mk, runs ORFS `finish` with
        NUM_CORES=8) and the measure phase (its measure.tcl on 6_final.odb with the task's eval.sdc, OpenRCX).
Rebuild (any other period X): a copy of the task package in which the working SDC the flow reads and the evaluation
        SDC both say `set clk_period X` (targets.json eval_clk_ps = X). Nothing else changes: the same submission diff,
        the same config.mk knobs (absolute-ps knobs such as SETUP_SLACK_MARGIN or ABC_CLOCK_PERIOD_IN_PS stay as
        published), the same image. Where the task's config.mk reads the SDC from the image
        ($(DESIGN_HOME)/...), the edited copy is bind-mounted over that path; where it reads $(WS)/constraint.sdc,
        the task copy's project/constraint.sdc is edited.
Differences from evaluate.py, all outside the measurement: no `--cpus 8 --memory 16g` (Docker refuses --cpus above
the runner's 4 vCPUs; NUM_CORES=8 is still passed to the flow, as the evaluator does); no starter ("noop") replay and
no functional (LEC/testbench) phase, because the TrueClock judge does not use them (every registered submission
edits only config.mk / flow scripts, never RTL). Bulky flow outputs (ODB, DEF, SPEF) are deleted after measuring.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time

SDC_RX = re.compile(r"^set clk_period .*$", re.M)


def sh256(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def set_period(text: str, x: str) -> str:
    n = len(SDC_RX.findall(text))
    if n != 1:
        raise SystemExit(f"expected one 'set clk_period' line, found {n}")
    return SDC_RX.sub(f"set clk_period {x}", text)


def sdc_mode(cfg_text: str):
    """The SDC the flow reads: last `export SDC_FILE` line outside a pos_slack variant."""
    nick = re.search(r"^export DESIGN_NICKNAME\s*=\s*(\S+)", cfg_text, re.M).group(1)
    lines = [ln for ln in re.findall(r"^\s*export SDC_FILE\s*=\s*(\S+)", cfg_text, re.M) if "pos_slack" not in ln]
    v = lines[-1]
    if v.startswith("$(WS)/"):
        return "ws", v[len("$(WS)/"):]
    m = re.match(r"\$\(DESIGN_HOME\)/\$\(PLATFORM\)/\$\(DESIGN_NICKNAME\)/(\S+)$", v)
    if m:
        return "image", f"/OpenROAD-flow-scripts/flow/designs/asap7/{nick}/{m.group(1)}"
    raise SystemExit(f"unrecognized SDC_FILE {v}")


def docker(image, task, case, phase, submission=None, mounts=()):
    cmd = ["docker", "run", "--rm", "--platform", "linux/amd64", "--network", "none", "--pids-limit", "4096",
           "--mount", f"type=bind,src={task},dst=/task,readonly",
           "--mount", f"type=bind,src={EVAL},dst=/evaluator,readonly",
           "--mount", f"type=bind,src={case},dst=/work" + (",readonly" if phase != "flow" else "")]
    if phase != "flow":
        dest = os.path.join(case, phase)
        os.makedirs(dest)
        cmd += ["--mount", f"type=bind,src={dest},dst=/result"]
    if submission is not None:
        cmd += ["--mount", f"type=bind,src={submission},dst=/submission,readonly"]
    for src, dst in mounts:
        cmd += ["--mount", f"type=bind,src={src},dst={dst},readonly"]
    cmd += ["--entrypoint", "python3", image, "/evaluator/worker.py", phase, "--kind", "patch"]
    with open(os.path.join(case, phase + "-container.log"), "w") as log:
        p = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT)
    rec = os.path.join(case, "flow.json") if phase == "flow" else os.path.join(case, phase, phase + ".json")
    out = json.load(open(rec)) if os.path.isfile(rec) else {"status": "error", "error": f"no {phase} receipt"}
    out["_docker_rc"] = p.returncode
    return out


def main():
    global EVAL
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True, help="extracted EDA-env artifact root")
    ap.add_argument("--task", required=True)
    ap.add_argument("--submission", required=True)
    ap.add_argument("--period", required=True, help="clock (ps) asked and judged; the eval clock = replay")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--image", default="eda-env-evaluator:iccad26")
    a = ap.parse_args()
    src = os.path.abspath(a.src)
    EVAL = os.path.join(src, "evaluator")
    task0 = os.path.join(src, "tasks", a.task)
    sub = os.path.join(src, a.submission)
    out = os.path.join(os.path.abspath(a.results), a.tag)
    os.makedirs(out, exist_ok=True)
    work = os.path.join(os.path.abspath(a.results), ".work", a.tag)
    shutil.rmtree(work, ignore_errors=True)
    os.makedirs(work)
    targets0 = json.load(open(os.path.join(task0, "targets.json")))
    t_eval = float(targets0["eval_clk_ps"])
    x = float(a.period)
    mode = "replay" if abs(x - t_eval) < 1e-9 else "rebuild"
    info = {"tag": a.tag, "harness": "edaenv", "task": a.task, "period": x, "mode": mode, "eval_clk_published": t_eval,
            "submission_sha256": sh256(sub)}
    mounts = []
    if mode == "replay":
        task = task0
    else:
        task = os.path.join(work, "task")
        shutil.copytree(task0, task)
        xs = a.period
        for rel in ("project/constraint.sdc", "eval/eval.sdc"):
            p = os.path.join(task, rel)
            txt = open(p).read()          # read first: open(p, "w") would truncate it
            open(p, "w").write(set_period(txt, xs))
        tj = dict(targets0, eval_clk_ps=x)
        json.dump(tj, open(os.path.join(task, "targets.json"), "w"), indent=2)
        kind, where = sdc_mode(open(os.path.join(task, "project", "config.mk")).read())
        info["sdc_mode"] = kind
        if kind == "image":
            stock = subprocess.run(["docker", "run", "--rm", "--entrypoint", "cat", a.image, where],
                                   capture_output=True, text=True, check=True).stdout
            info["image_sdc_sha256"] = hashlib.sha256(stock.encode()).hexdigest()
            info["task_sdc_sha256"] = sh256(os.path.join(task0, "project", "constraint.sdc"))
            mod = os.path.join(work, "image_sdc_" + os.path.basename(where))
            open(mod, "w").write(set_period(stock, xs))
            mounts.append((mod, where))
            info["mounted_sdc"] = where
    case = os.path.join(work, "case")
    os.makedirs(case)
    t0 = time.time()
    flow = docker(a.image, task, case, "flow", submission=sub, mounts=mounts)
    t1 = time.time()
    meas = None
    if flow.get("status") == "ok":
        meas = docker(a.image, task, case, "measure", mounts=mounts)
    t2 = time.time()
    subprocess.run(["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}", work])
    # keep the receipts, measurement, stage metrics, reports and gzipped logs; drop layouts
    dst = os.path.join(out, "case")
    os.makedirs(dst, exist_ok=True)
    for f in ("flow.json", "flow.log", "flow-container.log", "measure-container.log", "submitted.diff"):
        p = os.path.join(case, f)
        if os.path.isfile(p):
            shutil.copy2(p, dst)
    if os.path.isdir(os.path.join(case, "measure")):
        shutil.copytree(os.path.join(case, "measure"), os.path.join(dst, "measure"), dirs_exist_ok=True,
                        ignore=shutil.ignore_patterns("*.spef"))
    plat = open(os.path.join(task0, "eval", "platform.txt")).read().strip()
    des = open(os.path.join(task0, "eval", "design.txt")).read().strip()
    for sub_dir, pats in (("logs", (".json", ".log")), ("reports", (".rpt", ".log", ".txt", ".json"))):
        d = os.path.join(case, "out", sub_dir, plat, des, "base")
        if not os.path.isdir(d):
            continue
        os.makedirs(os.path.join(out, sub_dir), exist_ok=True)
        for f in sorted(os.listdir(d)):
            p = os.path.join(d, f)
            if not os.path.isfile(p) or not f.endswith(pats):
                continue
            if f.endswith(".json"):
                shutil.copy2(p, os.path.join(out, sub_dir, f))
            else:
                subprocess.run(["gzip", "-c", p], stdout=open(os.path.join(out, sub_dir, f + ".gz"), "wb"))
    for f in ("flow.log",):
        p = os.path.join(dst, f)
        if os.path.isfile(p):
            subprocess.run(["gzip", "-f", p])
    sanitized = os.path.join(case, "ws", "sanitized.mk")
    if os.path.isfile(sanitized):
        shutil.copy2(sanitized, os.path.join(out, "sanitized.mk"))
    for rel in ("project/constraint.sdc", "eval/eval.sdc", "targets.json"):
        shutil.copy2(os.path.join(task, rel), os.path.join(out, rel.replace("/", "_")))
    status = "completed" if (flow.get("status") == "ok" and meas and meas.get("status") == "ok") else (
        "flow_" + str(flow.get("status")) if flow.get("status") != "ok" else "measure_" + str((meas or {}).get("status")))
    info.update(status=status, elapsed_s=round(t1 - t0), measure_s=round(t2 - t1), flow_status=flow.get("status"),
                flow_failures=flow.get("failures"), flow_error=flow.get("error"),
                measure_error=(meas or {}).get("error"))
    json.dump(info, open(os.path.join(out, "run.json"), "w"), indent=1)
    subprocess.run(["sudo", "rm", "-rf", work])
    print(json.dumps(info))
    return 0


EVAL = None
if __name__ == "__main__":
    sys.exit(main())
