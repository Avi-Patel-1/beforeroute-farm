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
import sys


def sys_path_blib():
    here = os.path.dirname(os.path.abspath(__file__))
    if here not in sys.path:
        sys.path.insert(0, here)


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
    # C1 (independent replays + registered top-ups): runs deferred by the job time budget are re-queued; settings whose
    # frozen fixed point is not bracketed get their next top-up (blib.topup_target; at most 2 per setting).
    metas = {}
    for p in sorted(glob.glob(os.path.join(a.artifacts, "**", "b_meta.json"), recursive=True)):
        try:
            m = json.load(open(p))
        except Exception:
            continue
        if m.get("kind") not in ("c1r", "c1t"):
            continue
        d = os.path.dirname(p)
        try:
            met = json.load(open(os.path.join(d, "metrics.json")))
        except Exception:
            met = {}
        try:
            fs = float((json.load(open(os.path.join(d, "job.json"))) or {}).get("flow_seconds") or 0)
        except Exception:
            fs = 0.0
        ws = met.get("timing__setup__ws")
        metas[m["tag"]] = dict(m, claim=(float(m["period"]) - float(ws)) if ws is not None else None, flow_s=fs)
    deferred = []
    for p in sorted(glob.glob(os.path.join(a.artifacts, "**", "deferred", "*.json"), recursive=True)):
        try:
            r = json.load(open(p))
        except Exception:
            continue
        if r["tag"] not in metas:
            deferred.append(r)
    topups = []
    if metas:
        bys = {}
        for m in metas.values():
            bys.setdefault(m["setting"], []).append(m)
        pending = {}
        for r in deferred:
            pending.setdefault(r.get("setting"), []).append(r)
        for sid, ms in sorted(bys.items()):
            if pending.get(sid):
                continue                      # wait until the setting's deferred replays have landed
            byT = {}
            for m in ms:
                if m["claim"] is not None:
                    byT.setdefault(round(float(m["period"]), 4), []).append(m["claim"])
            import statistics
            pts = sorted((T, statistics.median(v)) for T, v in byT.items())
            n_top = sum(1 for m in ms if m["kind"] == "c1t")
            sys_path_blib()
            import blib
            tgt, why = blib.topup_target(pts)
            if tgt is None or n_top >= 2 or any(abs(tgt - T) < 1e-9 for T, _ in pts):
                continue
            base = sorted(ms, key=lambda m: m["tag"])[0]
            k = n_top + 1
            topups.append({"tag": f"b1t-{base['design']}-s{int(sid):02d}-{k}", "kind": "c1t", "setting": sid,
                           "design": base["design"], "base_spec": base["base_spec"], "period": tgt,
                           "D": base["D"], "io0": base["io0"], "F_best": base["F_best"],
                           "est_s": max(m["flow_s"] for m in ms) + 300, "why": why})
    extra = deferred + topups
    if extra:
        cap = 12000.0
        bins = []
        for r in sorted(extra, key=lambda r: -float(r.get("est_s") or 600)):
            e = float(r.get("est_s") or 600)
            for b in bins:
                if b["t"] + e <= cap:
                    b["runs"].append(r)
                    b["t"] += e
                    break
            else:
                bins.append({"t": e, "runs": [r]})
        for i, b in enumerate(bins, 1):
            groups[f"c1x{i:02d}"] = {"name": f"c1x{i:02d}", "timeout_s": 16000, "budget_s": 15000,
                                     "est_flow_s": max(float(r.get("est_s") or 600) for r in b["runs"]),
                                     "runs": b["runs"]}
        print(f"[b] C1: {len(deferred)} deferred replays re-queued, {len(topups)} top-ups: "
              + ", ".join(f"{t['tag']}@{t['period']} ({t['why']})" for t in topups))
    spec = {"batch": a.batch, "about": "resume stage: incomplete chains continued with the same rule; C1 deferred "
                                       "replays and registered top-ups", "groups": list(groups.values())}
    json.dump(spec, open(a.spec_out, "w"), indent=1)
    print(f"[b] {len(latest)} chains seen, {sum(len(g.get('chains') or []) for g in spec['groups'])} incomplete, "
          f"groups {[g['name'] for g in spec['groups']]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
