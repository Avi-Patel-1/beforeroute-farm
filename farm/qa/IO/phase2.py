#!/usr/bin/env python3
"""IO1 job specs and collection (docs/qa_week/IO_PREREG.md).

  phase2.py captures              farm/jobs/io-cap-<case>.json (stock source run at T0 + capture) + captures.tags.json
  phase2.py arms                  farm/jobs/io-<case>-<arm>.json for stock/script/claude (source run + chain) +
                                  phase2.tags.json; script/claude need farm/qa/IO/plans/<case>-<arm>.json
  phase2.py collect --run ID --out DIR [--keep-captures]
                                  download every job artifact of workflow run ID into DIR, keeping only chain.json,
                                  each run's metrics/job/pins_applied (and, with --keep-captures, the capture files)
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
GH_REPO = "Avi-Patel-1/beforeroute-farm"


def cases():
    return json.load(open(os.path.join(HERE, "cases.json")))["cases"]


def spec(c, tag, mode, arm, plan, capture):
    return {"tag": tag, "design": c["design_dir"], "config": c["config"], "overrides": c["overrides"],
            "io": {"mode": mode, "case": c["case"], "arm": arm, "plan": plan, "capture": capture,
                   "drv_ref": c["drv_ref"], "max_rebuilds": 4}}


def cmd_captures(a):
    tags = []
    for c in cases():
        t = f"io-cap-{c['case']}"
        json.dump(spec(c, t, "single", "stock", None, True), open(os.path.join(REPO, "farm", "jobs", f"{t}.json"), "w"),
                  indent=1)
        tags.append(t)
    json.dump(tags, open(os.path.join(HERE, "captures.tags.json"), "w"))
    print(json.dumps(tags))


def cmd_arms(a):
    tags = []
    for c in cases():
        for arm in ("stock", "script", "claude"):
            plan = None
            if arm != "stock":
                plan = f"farm/qa/IO/plans/{c['case']}-{arm}.json"
                if not os.path.exists(os.path.join(REPO, plan)):
                    sys.exit(f"missing {plan}")
            t = f"io-{c['case']}-{arm}"
            json.dump(spec(c, t, "chain", arm, plan, False), open(os.path.join(REPO, "farm", "jobs", f"{t}.json"), "w"),
                      indent=1)
            tags.append(t)
    json.dump(tags, open(os.path.join(HERE, "phase2.tags.json"), "w"))
    print(json.dumps(tags))


KEEP_RUN = {"metrics.json", "job.json", "pins_applied.json", "resolved.json"}
KEEP_CAPTURE = {"final.def.gz", "ports.json.gz", "paths.json.gz", "nets.jsonl.gz", "nets_signoff.jsonl.gz"}


def cmd_collect(a):
    os.makedirs(a.out, exist_ok=True)
    jobs = json.loads(subprocess.run(["gh", "run", "view", str(a.run), "-R", GH_REPO, "--json", "jobs"],
                                     capture_output=True, text=True, check=True).stdout)["jobs"]
    for j in jobs:
        tag = j["name"]
        dest = os.path.join(a.out, tag)
        if os.path.exists(os.path.join(dest, "chain.json")):
            continue
        tmp = tempfile.mkdtemp(dir=a.out)
        r = subprocess.run(["gh", "run", "download", str(a.run), "-R", GH_REPO, "-n", f"result-{tag}", "-D", tmp],
                           capture_output=True, text=True)
        if r.returncode != 0:
            print(f"[collect] {tag}: download failed: {r.stderr.strip()[:200]}")
            shutil.rmtree(tmp, ignore_errors=True)
            continue
        os.makedirs(dest, exist_ok=True)
        for root, _, files in os.walk(tmp):
            rel = os.path.relpath(root, tmp)
            for f in files:
                keep = (f == "chain.json" and rel == ".") or f in KEEP_RUN or (a.keep_captures and f in KEEP_CAPTURE)
                if keep:
                    os.makedirs(os.path.join(dest, rel), exist_ok=True)
                    shutil.copy2(os.path.join(root, f), os.path.join(dest, rel, f))
        shutil.rmtree(tmp, ignore_errors=True)
        print(f"[collect] {tag}: kept {sum(len(f) for _, _, f in os.walk(dest))} files")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["captures", "arms", "collect"])
    ap.add_argument("--run")
    ap.add_argument("--out")
    ap.add_argument("--keep-captures", action="store_true")
    a = ap.parse_args()
    {"captures": cmd_captures, "arms": cmd_arms, "collect": cmd_collect}[a.cmd](a)


if __name__ == "__main__":
    main()
