#!/usr/bin/env python3
"""BeforeRoute as one command: RTL -> post-GRT checkpoint -> predict -> targeted repair -> signoff.

  python3 br/beforeroute.py --design designs/des --config config_sky130.json --tag des-br \\
      --model models/model_all_v5.txt --budget thr:0.5 --margin 70

Steps (each one is the same code the farm arms run):
  1. checkpoint  LibreLane Classic flow up to OpenROAD.CheckAntennas with the stock post-GRT repair off
  2. features    BeforeRoute.DumpNetsPostGRT on the checkpoint state itself (br/run_dump.py --state)
  3. predict     score every signal net with the model (br/score.py) from a directory that holds only the
                 checkpoint features and the flow config -- nothing from signoff exists yet
  4. repair      resume at the checkpoint with BeforeRoute.TargetedRepairPostGRT on the flagged nets only,
                 then the stock flow to nine-corner signoff (br/arms.py --arm targeted)
  5. report      signal nets violating at signoff, cells changed, hold/setup slack, area
Budget: frac:0.05 (top 5% of signal nets) | thr:0.5 (p >= 0.5) | auto:1.0 (top round(sum p) nets).
LibreLane steps run in the tool environment (`source env.sh`, or --docker IMAGE); scoring runs on the host
python (lightgbm, pandas).
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def run(cmd, log, cwd=ROOT):
    t0 = time.time()
    with open(log, "w") as f:
        r = subprocess.run(cmd, cwd=cwd, stdout=f, stderr=subprocess.STDOUT)
    return r.returncode, round(time.time() - t0, 1)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--design", required=True, help="design dir (relative to the repo root)")
    ap.add_argument("--config", required=True, help="LibreLane config inside the design dir")
    ap.add_argument("--tag", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--budget", default="thr:0.5")
    ap.add_argument("--margin", type=float, default=70.0, help="slew/cap repair margin %% on flagged nets")
    ap.add_argument("--override", action="append", default=[], help="extra flow variables KEY=JSON")
    ap.add_argument("--results", default="results")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--pdk-root", default="pdk")
    ap.add_argument("--docker", default=None, help="run LibreLane steps in this image (repo mounted at /work)")
    a = ap.parse_args()

    design = os.path.relpath(os.path.abspath(a.design), ROOT)
    out = os.path.join(ROOT, a.results, a.tag + "-beforeroute")
    os.makedirs(out, exist_ok=True)
    if a.docker:
        pre = ["docker", "run", "--rm", "-v", f"{ROOT}:/work", "-w", "/work", "-e", "PDK_ROOT=/work/pdk", a.docker]
        rootp = "/work"
    else:
        pre = ["bash", "-c", 'source "$0/env.sh" && shift && exec "$@"', ROOT, "_"]
        rootp = ROOT
    P = lambda *p: os.path.join(rootp, *p)  # noqa: E731  (path as seen by the LibreLane steps)
    report = {"tag": a.tag, "design": design, "model": a.model, "budget": a.budget, "margin": a.margin, "steps": {}}

    # 1. checkpoint (overlay = config + overrides, written like run_job.py does)
    cfg_path = os.path.join(ROOT, design, a.config)
    cfg = json.load(open(cfg_path))
    cfg.update({"RUN_POST_GRT_DESIGN_REPAIR": False, "RUN_MAGIC_DRC": False, "RUN_KLAYOUT_DRC": False, "RUN_LVS": False,
                "RUN_KLAYOUT_XOR": False, "RUN_IRDROP_REPORT": False, "RUN_LINTER": False})
    for ov in a.override:
        k, v = ov.split("=", 1)
        try:
            cfg[k] = json.loads(v)
        except json.JSONDecodeError:
            cfg[k] = v
    json.dump(cfg, open(os.path.join(ROOT, design, f"config.{a.tag}.json"), "w"), indent=1)
    run_dir = os.path.join(ROOT, design, "runs", a.tag)
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    rc, sec = run(pre + ["bash", "-c", f'cd "{P(design)}" && librelane --pdk-root "{P(a.pdk_root)}" --manual-pdk --run-tag {a.tag} '
                         f'-j {a.jobs} --to OpenROAD.CheckAntennas config.{a.tag}.json'], os.path.join(out, "1_checkpoint.log"))
    states = sorted(glob.glob(os.path.join(run_dir, "*-openroad-checkantennas", "state_out.json")))
    report["steps"]["checkpoint"] = {"exit": rc, "seconds": sec}
    if not states:
        report["status"] = "checkpoint_failed"
        json.dump(report, open(os.path.join(out, "report.json"), "w"), indent=1)
        print(json.dumps(report, indent=1))
        return 1
    # the arms read resolved.json of the base run (written by the flow at start)
    st_rel = os.path.relpath(states[0], ROOT)

    # 2. features at the checkpoint
    feat = os.path.join(out, "features")
    os.makedirs(feat, exist_ok=True)
    rc, sec = run(pre + ["python3", P("br", "run_dump.py"), P(design, "runs", a.tag), "--state", P(st_rel),
                         "--out", P(os.path.relpath(feat, ROOT), "dump"), "--pdk-root", P(a.pdk_root)], os.path.join(out, "2_features.log"))
    report["steps"]["features"] = {"exit": rc, "seconds": sec}
    if not os.path.exists(os.path.join(feat, "dump", "nets.jsonl")):
        report["status"] = "feature_dump_failed"
        json.dump(report, open(os.path.join(out, "report.json"), "w"), indent=1)
        print(json.dumps(report, indent=1))
        return 1
    for fn in ("nets.jsonl", "dump_summary.json"):
        shutil.copy2(os.path.join(feat, "dump", fn), os.path.join(feat, fn))
    shutil.copy2(os.path.join(run_dir, "resolved.json"), os.path.join(feat, "resolved.json"))
    json.dump({"tag": a.tag + "-ckpt", "status": "completed", "kind": "checkpoint features only, no signoff data"}, open(os.path.join(feat, "job.json"), "w"))
    json.dump({"nets": [], "summary": {"nets_violating": 0, "corner_counts": {}}}, open(os.path.join(feat, "labels.json"), "w"))
    json.dump({"nets": {}}, open(os.path.join(feat, "final_nets.json"), "w"))
    json.dump({}, open(os.path.join(feat, "metrics.json"), "w"))

    # 3. predict
    kind, val = (a.budget.split(":") + ["0.05"])[:2]
    sel = {"frac": ["--frac", val], "thr": ["--threshold", val], "auto": ["--expected-count", val]}[kind]
    flagged = os.path.join(out, "flagged.json")
    t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(HERE, "score.py"), "--model", os.path.join(ROOT, a.model), "--run-results", feat,
                        *sel, "--out", flagged], capture_output=True, text=True, cwd=ROOT)
    open(os.path.join(out, "3_predict.log"), "w").write(r.stdout + r.stderr)
    try:
        summ = json.loads(r.stdout[r.stdout.index("{"):])
    except Exception:
        summ = {}
    report["steps"]["predict"] = {"exit": r.returncode, "seconds": round(time.time() - t0, 1), "nets_scored": summ.get("nets_scored"),
                                  "flagged": summ.get("flagged"), "flag_frac": summ.get("flag_frac")}
    if r.returncode != 0:
        report["status"] = "predict_failed"
        json.dump(report, open(os.path.join(out, "report.json"), "w"), indent=1)
        print(json.dumps(report, indent=1))
        return 1

    # 4. targeted repair + rest of the flow to signoff
    arm_tag = a.tag + "-br"
    rc, sec = run(pre + ["python3", P("br", "arms.py"), "--base-run", P(design, "runs", a.tag), "--arm", "targeted", "--tag", arm_tag,
                         "--slew-pct", str(a.margin), "--cap-pct", str(a.margin), "--flagged", P(os.path.relpath(flagged, ROOT)),
                         "--results", P(a.results), "--pdk-root", P(a.pdk_root), "--jobs", str(a.jobs)], os.path.join(out, "4_repair_signoff.log"))
    report["steps"]["repair_signoff"] = {"exit": rc, "seconds": sec}

    # 5. report
    sys.path.insert(0, HERE)
    from run_hero import arm_summary  # noqa: E402

    try:
        s = arm_summary(os.path.join(ROOT, a.results), arm_tag)
        report["signoff"] = {k: s.get(k) for k in ("status", "signoff_violating_data_nets", "data_slew", "data_cap", "data_fanout",
                                                  "resized", "buffers", "hold_ws", "setup_ws", "stdcell_area", "flow_seconds")}
        report["status"] = "completed"
    except Exception as e:
        report["status"] = f"report_failed: {type(e).__name__}: {e}"
    json.dump(report, open(os.path.join(out, "report.json"), "w"), indent=1)
    print(json.dumps(report, indent=1))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
