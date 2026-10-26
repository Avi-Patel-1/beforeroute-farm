#!/usr/bin/env python3
"""Run one experimental arm from a finished baseline run's post-GRT checkpoint.

Usage:
  arms.py --base-run <design/runs/<basetag>> --arm base|uniform|targeted --tag <armtag>
          [--slew-pct 50 --cap-pct 50] [--flagged flagged.json] [--results results]
          [--override KEY=JSON ...] [--pdk-root ...]

All arms resume at the post-global-route repair point (the state after
OpenROAD.CheckAntennas of the baseline run) with an identical downstream flow:
  base     : RUN_POST_GRT_DESIGN_REPAIR=false (re-runs the baseline suffix; control for noise)
  uniform  : stock OpenROAD.RepairDesignPostGRT on every net with the given margins
  targeted : BeforeRoute.TargetedRepairPostGRT, margins applied only to the flagged nets
Outputs: results/<armtag>/{metrics.json, resolved.json, labels.json, final_nets.json, job.json, checks/}
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
sys.path.insert(0, HERE)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-run", required=True)
    ap.add_argument("--arm", required=True, choices=["base", "uniform", "targeted", "tiered"])
    ap.add_argument("--tag", required=True)
    ap.add_argument("--slew-pct", type=float, default=50)
    ap.add_argument("--cap-pct", type=float, default=50)
    ap.add_argument("--flagged", default=None)
    ap.add_argument("--tiers", default=None, help="tiers JSON for the tiered arm")
    ap.add_argument("--results", default=os.path.join(HERE, "..", "results"))
    ap.add_argument("--override", action="append", default=[])
    ap.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "/home/claude/eda/pdk"))
    ap.add_argument("--jobs", type=int, default=2)
    a = ap.parse_args()

    base_run = os.path.abspath(a.base_run)
    design_dir = os.path.dirname(os.path.dirname(base_run))
    base_tag = os.path.basename(base_run)
    overlay = os.path.join(design_dir, f"config.{base_tag}.json")
    if not os.path.exists(overlay):
        raise SystemExit(f"baseline overlay config not found: {overlay}")
    states = sorted(glob.glob(os.path.join(base_run, "*-openroad-checkantennas", "state_out.json")))
    if not states:
        raise SystemExit("no post-GRT CheckAntennas state in baseline run")
    state_path = states[0]

    cfg = json.load(open(overlay))
    for ov in a.override:
        k, v = ov.split("=", 1)
        try:
            cfg[k] = json.loads(v)
        except json.JSONDecodeError:
            cfg[k] = v
    if a.arm == "base":
        cfg["RUN_POST_GRT_DESIGN_REPAIR"] = False
    else:
        cfg["RUN_POST_GRT_DESIGN_REPAIR"] = True
        cfg["GRT_DESIGN_REPAIR_MAX_SLEW_PCT"] = a.slew_pct
        cfg["GRT_DESIGN_REPAIR_MAX_CAP_PCT"] = a.cap_pct
    flagged_abs = None
    if a.arm == "targeted":
        if not a.flagged:
            raise SystemExit("--flagged is required for the targeted arm")
        flagged_abs = os.path.abspath(a.flagged)
        cfg["BR_FLAGGED_NETS_FILE"] = flagged_abs
    if a.arm == "tiered":
        if not a.tiers:
            raise SystemExit("--tiers is required for the tiered arm")
        flagged_abs = os.path.abspath(a.tiers)
        cfg["BR_FLAGGED_TIERS_FILE"] = flagged_abs
    arm_overlay = os.path.join(design_dir, f"config.{a.tag}.json")
    json.dump(cfg, open(arm_overlay, "w"), indent=1)

    from librelane.flows import Flow
    from librelane.state import State
    import steps  # noqa: F401  (registers BeforeRoute steps)

    Classic = Flow.factory.get("Classic")
    if a.arm in ("targeted", "tiered"):
        FlowCls = Classic.Substitute({"OpenROAD.RepairDesignPostGRT": steps.TargetedRepairPostGRT})
        frm = "BeforeRoute.TargetedRepairPostGRT"
    else:
        FlowCls = Classic
        frm = "OpenROAD.RepairDesignPostGRT" if a.arm == "uniform" else "Odb.DiodesOnPorts"

    results = os.path.abspath(os.path.join(a.results, a.tag))
    os.makedirs(results, exist_ok=True)
    manifest = {
        "tag": a.tag, "arm": a.arm, "base_run": base_run, "state_in": state_path,
        "slew_pct": a.slew_pct if a.arm != "base" else None, "cap_pct": a.cap_pct if a.arm != "base" else None,
        "flagged": flagged_abs, "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    run_dir = os.path.join(design_dir, "runs", a.tag)
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    t0 = time.time()
    status = "completed"
    try:
        flow = FlowCls(arm_overlay, design_dir=design_dir, pdk_root=a.pdk_root, pdk="sky130A", scl="sky130_fd_sc_hd")
        flow.start(tag=a.tag, frm=frm, with_initial_state=State.loads(open(state_path).read()))
    except Exception as e:  # keep the evidence, report the failure
        status = f"flow_failed: {type(e).__name__}: {str(e)[:300]}"
    manifest["flow_seconds"] = round(time.time() - t0, 1)

    def copy_if(src, dst):
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(results, dst))
            return True
        return False

    done = copy_if(os.path.join(run_dir, "final", "metrics.json"), "metrics.json")
    copy_if(os.path.join(run_dir, "resolved.json"), "resolved.json")
    for ts in glob.glob(os.path.join(run_dir, "*targetedrepair*", "targeted_summary.json")):
        copy_if(ts, "targeted_summary.json")
    for lg in glob.glob(os.path.join(run_dir, "*repair*postgrt*", "openroad-*.log")):
        copy_if(lg, "repair_step.log")
    if done:
        lab = subprocess.run([sys.executable, os.path.join(HERE, "labels.py"), run_dir], capture_output=True, text=True)
        open(os.path.join(results, "labels.log"), "w").write(lab.stdout[-20000:] + "\n--- stderr ---\n" + lab.stderr[-20000:])
        copy_if(os.path.join(run_dir, "br-labels", "labels.json"), "labels.json")
        copy_if(os.path.join(run_dir, "br-labels", "final_nets.json"), "final_nets.json")
        os.makedirs(os.path.join(results, "checks"), exist_ok=True)
        for rpt in glob.glob(os.path.join(run_dir, "*-openroad-stapostpnr", "*", "checks.rpt")):
            shutil.copy2(rpt, os.path.join(results, "checks", os.path.basename(os.path.dirname(rpt)) + ".checks.rpt"))
    else:
        status = status if status != "completed" else "flow_incomplete"
    manifest["status"] = status
    manifest["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(manifest, open(os.path.join(results, "job.json"), "w"), indent=1)
    print(json.dumps(manifest, indent=1))
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
