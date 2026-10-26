#!/usr/bin/env python3
"""BeforeRoute worker: run one LibreLane job, extract features + labels, keep a compact result.

Usage:
  run_job.py --design <design_dir> --config <config.json|yaml> --tag <run_tag>
             [--override KEY=JSONVALUE ...] [--overrides-json <file>]
             [--results <dir>] [--jobs 2] [--keep-run] [--pdk-root <dir>]

Steps: (1) write an overlay config (base config + overrides) into the design
dir, (2) run `librelane` to completion, (3) DumpNetsPostGRT on the run,
(4) labels from the nine-corner signoff reports, (5) copy the compact outputs
(nets.jsonl, labels.json, final_nets.json, metrics.json, resolved.json, the
flow log gzipped, a job.json manifest) into <results>/<tag>/ and, unless
--keep-run, delete the run directory.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def load_config(path):
    if path.endswith(".json"):
        return json.load(open(path))
    import yaml

    return yaml.safe_load(open(path))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-spec", default=None, help="JSON file with design, config, tag, overrides (overrides CLI values)")
    ap.add_argument("--design", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--override", action="append", default=[])
    ap.add_argument("--overrides-json", default=None)
    ap.add_argument("--results", default=os.path.join(HERE, "..", "results"))
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--keep-run", action="store_true")
    ap.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "/home/claude/eda/pdk"))
    ap.add_argument("--timeout", type=int, default=7200)
    a = ap.parse_args()
    spec = {}
    if a.job_spec:
        spec = json.load(open(a.job_spec))
        a.design = a.design or spec["design"]
        a.config = a.config or spec["config"]
        a.tag = a.tag or spec["tag"]
    if not (a.design and a.config and a.tag):
        ap.error("--design, --config and --tag are required (or --job-spec)")

    design = os.path.abspath(a.design)
    cfg_path = os.path.abspath(a.config) if os.path.isabs(a.config) or os.path.exists(a.config) else os.path.join(design, a.config)
    base = load_config(cfg_path)
    overrides = dict(spec.get("overrides") or {})
    if a.overrides_json:
        overrides.update(json.load(open(a.overrides_json)))
    for ov in a.override:
        k, v = ov.split("=", 1)
        try:
            overrides[k] = json.loads(v)
        except json.JSONDecodeError:
            overrides[k] = v
    cfg = dict(base)
    cfg.update(overrides)
    # keep pdk-specific sub-dicts of YAML configs intact; overrides are top-level
    overlay = os.path.join(design, f"config.{a.tag}.json")
    json.dump(cfg, open(overlay, "w"), indent=1)

    results = os.path.abspath(os.path.join(a.results, a.tag))
    os.makedirs(results, exist_ok=True)
    manifest = {
        "tag": a.tag,
        "design_dir": design,
        "base_config": cfg_path,
        "overrides": overrides,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": os.uname().nodename,
        "jobs": a.jobs,
    }
    run_dir = os.path.join(design, "runs", a.tag)
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    t0 = time.time()
    flow_log = os.path.join(results, "flow.log")
    cmd = ["librelane", "--pdk-root", a.pdk_root, "--manual-pdk", "--run-tag", a.tag, "-j", str(a.jobs), overlay]
    with open(flow_log, "w") as lf:
        try:
            r = subprocess.run(cmd, cwd=design, stdout=lf, stderr=subprocess.STDOUT, timeout=a.timeout)
            rc = r.returncode
        except subprocess.TimeoutExpired:
            rc = -9
            lf.write("\n[br] TIMEOUT\n")
    manifest["flow_exit"] = rc
    manifest["flow_seconds"] = round(time.time() - t0, 1)

    def copy_if(src, dst_name):
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(results, dst_name))
            return True
        return False

    final_metrics = os.path.join(run_dir, "final", "metrics.json")
    manifest["flow_completed"] = copy_if(final_metrics, "metrics.json")
    copy_if(os.path.join(run_dir, "resolved.json"), "resolved.json")
    copy_if(os.path.join(run_dir, "error.log"), "error.log")

    status = "flow_failed"
    if manifest["flow_completed"]:
        status = "completed"
        t1 = time.time()
        d = subprocess.run([sys.executable, os.path.join(HERE, "run_dump.py"), run_dir, "--pdk-root", a.pdk_root],
                           capture_output=True, text=True)
        manifest["dump_exit"] = d.returncode
        manifest["dump_seconds"] = round(time.time() - t1, 1)
        open(os.path.join(results, "dump.log"), "w").write(d.stdout[-20000:] + "\n--- stderr ---\n" + d.stderr[-20000:])
        ok1 = copy_if(os.path.join(run_dir, "br-dump-postgrt", "nets.jsonl"), "nets.jsonl")
        copy_if(os.path.join(run_dir, "br-dump-postgrt", "dump_summary.json"), "dump_summary.json")
        # signoff view (final ODB + RCX parasitics): actual per-net slews/caps for all nets
        t1b = time.time()
        d2 = subprocess.run([sys.executable, os.path.join(HERE, "run_dump.py"), run_dir, "--signoff", "--pdk-root", a.pdk_root],
                            capture_output=True, text=True)
        manifest["dump_signoff_exit"] = d2.returncode
        manifest["dump_signoff_seconds"] = round(time.time() - t1b, 1)
        open(os.path.join(results, "dump_signoff.log"), "w").write(d2.stdout[-20000:] + "\n--- stderr ---\n" + d2.stderr[-20000:])
        copy_if(os.path.join(run_dir, "br-dump-signoff", "nets_signoff.jsonl"), "nets_signoff.jsonl")
        t2 = time.time()
        lab = subprocess.run([sys.executable, os.path.join(HERE, "labels.py"), run_dir], capture_output=True, text=True)
        manifest["labels_exit"] = lab.returncode
        manifest["labels_seconds"] = round(time.time() - t2, 1)
        open(os.path.join(results, "labels.log"), "w").write(lab.stdout[-20000:] + "\n--- stderr ---\n" + lab.stderr[-20000:])
        ok2 = copy_if(os.path.join(run_dir, "br-labels", "labels.json"), "labels.json")
        copy_if(os.path.join(run_dir, "br-labels", "final_nets.json"), "final_nets.json")
        if not (ok1 and ok2):
            status = "extract_failed"
        # signoff reports (small) for audit
        import glob

        for rpt in glob.glob(os.path.join(run_dir, "*-openroad-stapostpnr", "*", "checks.rpt")):
            corner = os.path.basename(os.path.dirname(rpt))
            os.makedirs(os.path.join(results, "checks"), exist_ok=True)
            shutil.copy2(rpt, os.path.join(results, "checks", f"{corner}.checks.rpt"))
    # gzip the flow log
    with open(flow_log, "rb") as fi, gzip.open(flow_log + ".gz", "wb") as fo:
        shutil.copyfileobj(fi, fo)
    os.remove(flow_log)
    manifest["status"] = status
    manifest["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(manifest, open(os.path.join(results, "job.json"), "w"), indent=1)
    if not a.keep_run and os.path.exists(run_dir):
        shutil.rmtree(run_dir, ignore_errors=True)
    print(json.dumps(manifest, indent=1))
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
