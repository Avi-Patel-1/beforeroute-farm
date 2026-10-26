#!/usr/bin/env python3
"""Hero experiment: baseline run + scoring + arm sweep from one post-GRT checkpoint.

Usage:
  run_hero.py --job-spec farm/jobs/<tag>.json --model models/model_holdout_picorv32.txt
              [--uniform 10,30,50,70] [--targeted 0.02:70,0.05:70,0.05:90,0.10:70]
              [--results results] [--jobs 2] [--pdk-root ...] [--skip-base-rerun]

Arms (all resume at the same post-GRT state, identical downstream flow):
  base       : the baseline run itself (RUN_POST_GRT_DESIGN_REPAIR off), plus one re-run for noise
  uniform-H  : stock post-GRT repair on every net, slew/cap margins H
  targeted-k-H : post-GRT repair only on the model's top-k fraction of data nets, margins H
Writes results/<tag>/hero_summary.json with per-arm signoff violations, area, instances, runtime.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def run(cmd, log_path):
    with open(log_path, "a") as lf:
        lf.write("\n$ " + " ".join(cmd) + "\n")
        lf.flush()
        r = subprocess.run(cmd, stdout=lf, stderr=subprocess.STDOUT, text=True)
    return r.returncode


def arm_summary(results, tag):
    d = os.path.join(results, tag)
    out = {"tag": tag}
    try:
        job = json.load(open(os.path.join(d, "job.json")))
        out.update({"status": job.get("status"), "flow_seconds": job.get("flow_seconds"), "arm": job.get("arm", "base"),
                    "slew_pct": job.get("slew_pct"), "cap_pct": job.get("cap_pct"), "flagged": job.get("flagged")})
    except Exception as e:
        out["status"] = f"missing job.json ({e})"
        return out
    try:
        m = json.load(open(os.path.join(d, "metrics.json")))
        out.update({
            "stdcell_area": m.get("design__instance__area__stdcell"),
            "instances": m.get("design__instance__count"),
            "max_slew_count": m.get("design__max_slew_violation__count"),
            "max_cap_count": m.get("design__max_cap_violation__count"),
            "max_fanout_count": m.get("design__max_fanout_violation__count"),
            "setup_ws": m.get("timing__setup__ws"), "hold_ws": m.get("timing__hold__ws"),
            "setup_vio": m.get("timing__setup_vio__count"), "hold_vio": m.get("timing__hold_vio__count"),
            "drc": m.get("route__drc_errors"), "lvs_errors": m.get("design__lvs_error__count"),
        })
    except Exception:
        pass
    try:
        lab = json.load(open(os.path.join(d, "labels.json")))["summary"]
        out.update({"signoff_violating_nets": lab["nets_violating"], "nets_total": lab["nets_total"],
                    "corner_counts": lab["corner_counts"]})
    except Exception:
        pass
    ts = os.path.join(d, "targeted_summary.json")
    if os.path.exists(ts):
        out["targeted"] = json.load(open(ts))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-spec", required=True)
    ap.add_argument("--model", required=True)
    ap.add_argument("--uniform", default="10,30,50,70")
    ap.add_argument("--targeted", default="0.02:70,0.05:70,0.05:90,0.10:70")
    ap.add_argument("--results", default=os.path.join(HERE, "..", "results"))
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "/home/claude/eda/pdk"))
    ap.add_argument("--skip-base-rerun", action="store_true")
    ap.add_argument("--design-root", default=os.path.join(HERE, ".."))
    a = ap.parse_args()
    results = os.path.abspath(a.results)
    spec = json.load(open(a.job_spec))
    tag = spec["tag"]
    design_dir = os.path.abspath(os.path.join(a.design_root, spec["design"]))
    log_path = os.path.join(results, f"{tag}.hero.log")
    os.makedirs(results, exist_ok=True)
    t0 = time.time()

    # 1. baseline (kept run dir)
    if not os.path.exists(os.path.join(results, tag, "job.json")) or not os.path.exists(os.path.join(design_dir, "runs", tag)):
        run([sys.executable, os.path.join(HERE, "run_job.py"), "--job-spec", a.job_spec, "--design", design_dir,
             "--jobs", str(a.jobs), "--results", results, "--pdk-root", a.pdk_root, "--keep-run"], log_path)
    base_run = os.path.join(design_dir, "runs", tag)
    if not os.path.exists(os.path.join(results, tag, "nets.jsonl")):
        print("[hero] baseline failed; aborting", file=sys.stderr)
        return 1
    arms = [tag]

    # 2. base re-run (noise control)
    if not a.skip_base_rerun:
        t = f"{tag}-rerun"
        run([sys.executable, os.path.join(HERE, "arms.py"), "--base-run", base_run, "--arm", "base", "--tag", t,
             "--results", results, "--pdk-root", a.pdk_root, "--jobs", str(a.jobs)], log_path)
        arms.append(t)

    # 3. uniform family
    for h in [x for x in a.uniform.split(",") if x]:
        t = f"{tag}-uni{int(float(h))}"
        run([sys.executable, os.path.join(HERE, "arms.py"), "--base-run", base_run, "--arm", "uniform", "--tag", t,
             "--slew-pct", h, "--cap-pct", h, "--results", results, "--pdk-root", a.pdk_root, "--jobs", str(a.jobs)], log_path)
        arms.append(t)

    # 4. targeted family
    for item in [x for x in a.targeted.split(",") if x]:
        k, h = item.split(":")
        flagged = os.path.join(results, tag, f"flagged_k{float(k):.3f}.json")
        run([sys.executable, os.path.join(HERE, "score.py"), "--model", a.model, "--run-results", os.path.join(results, tag),
             "--frac", k, "--out", flagged], log_path)
        t = f"{tag}-tgt{int(round(float(k) * 1000)):03d}-{int(float(h))}"
        run([sys.executable, os.path.join(HERE, "arms.py"), "--base-run", base_run, "--arm", "targeted", "--tag", t,
             "--slew-pct", h, "--cap-pct", h, "--flagged", flagged, "--results", results, "--pdk-root", a.pdk_root,
             "--jobs", str(a.jobs)], log_path)
        arms.append(t)

    summary = {"tag": tag, "design": spec["design"], "model": a.model, "arms": [arm_summary(results, t) for t in arms],
               "seconds": round(time.time() - t0, 1)}
    json.dump(summary, open(os.path.join(results, tag, "hero_summary.json"), "w"), indent=1)
    for s in summary["arms"]:
        print(f"[hero] {s['tag']:34s} {str(s.get('status')):10s} viol_nets={s.get('signoff_violating_nets')} "
              f"slew={s.get('max_slew_count')} area={s.get('stdcell_area')} insts={s.get('instances')} t={s.get('flow_seconds')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
