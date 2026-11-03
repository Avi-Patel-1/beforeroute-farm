#!/usr/bin/env python3
"""Workstream B: build the resume-stage spec from a workflow run's downloaded artifacts (runner side, no rule change).

  python3 farm/qa/B/resume.py --artifacts <dir with one subdir per artifact> --batch <batch>r --spec-out resume.json

Reads every <artifact>/chains/<chain_id>.json, keeps the latest stage of each chain, and puts each incomplete chain (job
time budget hit, or stage 1 stopped at its first passing rebuild) into a group named after its original group. The
chain's own state carries everything needed to continue it (blib.chain_next on the same entries).
"""
from __future__ import annotations

import argparse
import glob
import json
import os


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--artifacts", required=True)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--spec-out", required=True)
    a = ap.parse_args()
    latest = {}
    for p in sorted(glob.glob(os.path.join(a.artifacts, "**", "chains", "*.json"), recursive=True)):
        try:
            c = json.load(open(p))
        except Exception:
            continue
        cid = c.get("chain_id")
        if cid is None:
            continue
        if cid not in latest or (c.get("stage", 1), len(c.get("state") or [])) > \
                (latest[cid].get("stage", 1), len(latest[cid].get("state") or [])):
            latest[cid] = c
    groups = {}
    for cid, c in sorted(latest.items()):
        if c.get("complete"):
            continue
        g = c.get("group", "g")
        gp = c.get("group_params") or {}
        grp = groups.setdefault(g, {"name": g, "timeout_s": gp.get("timeout_s", 16000),
                                    "budget_s": gp.get("budget_s"), "est_flow_s": gp.get("est_flow_s", 0),
                                    "chains": []})
        c2 = dict(c)
        c2["stage"] = c.get("stage", 1)
        grp["chains"].append(c2)
    spec = {"batch": a.batch, "about": "resume stage: incomplete chains continued with the same rule",
            "groups": list(groups.values())}
    json.dump(spec, open(a.spec_out, "w"), indent=1)
    print(f"[b] {len(latest)} chains seen, {sum(len(g['chains']) for g in spec['groups'])} incomplete, "
          f"groups {[g['name'] for g in spec['groups']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
