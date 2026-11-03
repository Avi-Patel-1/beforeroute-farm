#!/usr/bin/env python3
"""Workstream B: write a dispatch batch (farm/qa/B/batches/<batch>.json) from the registered plan (farm/qa/B/plan.json).

  python3 farm/qa/B/make_dispatch.py --batch s01 --kind smoke [--max-parallel 2]
  python3 farm/qa/B/make_dispatch.py --batch c2a1 --kind c2a --max-parallel 4
  python3 farm/qa/B/make_dispatch.py --batch s1 --kind s --max-parallel 4
  python3 farm/qa/B/make_dispatch.py --batch c1a --kind c1 --max-parallel 4

Copy the batch to farm/qa/B/dispatch.json and push to start it (.github/workflows/b_farm.yml).
"""
from __future__ import annotations

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = "/home/claude/eda"            # the landed record (results/<tag>/job.json for flow-time estimates)
BUDGET_S = 15000                      # per job: no new flow starts after this many seconds of the job (timeout 300 min)


def rec_seconds(tag):
    try:
        j = json.load(open(os.path.join(ROOT, "results", tag, "job.json")))
        return float(j.get("flow_seconds") or 0)
    except Exception:
        return 0.0


def chain_entry(w, fb, chain_id, tag_prefix, group, gparams, D=None, stop_first=False):
    f = fb[w["design"]]
    return {"chain_id": chain_id, "design": w["design"], "source": w["source"], "set": w["set"],
            "base_spec": w["spec"], "T0": w["T0"], "claim_orig": w["claim_orig"],
            "D": f["D"] if D is None else D, "io0": f["io0"],
            "F_best": f["F_best"] if D is None else -1.0,       # D overridden (S): no target equals "F_best"
            "drv_ref": w["drv_ref"], "tag_prefix": tag_prefix, "group": group, "group_params": gparams,
            "stop_after_first_pass": stop_first, "frozen": True}


def c2a_groups(plan, chains_only_first=False):
    fb = plan["fbest"]
    groups = []
    order = ["bm64", "md5", "y_huff", "picorv32", "des", "ocs_blitter", "blabla", "aes_cipher"]   # longest first
    bay = sorted([w for w in plan["c2a"] if not w["set"].startswith("A35")], key=lambda w: order.index(w["design"]))
    race = [w for w in plan["c2a"] if w["set"].startswith("A35")]
    for w in bay:                                         # long flows: one job each, stage 1 stops at the first pass
        est = 1.3 * max(rec_seconds(w["source"]), rec_seconds((w["orig_first_rebuild"] or {}).get("tag", ""))) + 300
        gp = {"timeout_s": 16000, "budget_s": BUDGET_S, "est_flow_s": round(est)}
        name = f"bay-{w['design']}"
        cid = f"b2a-{w['design']}-01"
        groups.append(dict(name=name, chains=[chain_entry(w, fb, cid, cid + "-", name, gp, stop_first=True)], **gp))
    by = {}
    for w in race:
        by.setdefault(w["design"], []).append(w)
    for d, ws in by.items():                                # plan order: seed 1 b f g h, seed 2 b f g h -> nn 01..08
        for s in (1, 2):
            name = f"{d}-s{s}"
            gp = {"timeout_s": 16000, "budget_s": BUDGET_S, "est_flow_s": 900}
            chs = []
            for i, w in enumerate(ws):
                if not w["set"].endswith(str(s)):
                    continue
                cid = f"b2a-{d}-{i + 1:02d}"
                chs.append(chain_entry(w, fb, cid, cid + "-", name, gp))
            groups.append(dict(name=name, chains=chs, **gp))
    return groups


def s_groups(plan):
    """S: the 40 race winners with D = 1.0 ns flat; replay + first rebuild only (max_rebuilds 1)."""
    fb = plan["fbest"]
    by = {}
    for w in plan["s"]:
        by.setdefault(w["design"], []).append(w)
    groups = []
    for d, ws in by.items():
        for s in (1, 2):
            name = f"s-{d}-s{s}"
            gp = {"timeout_s": 16000, "budget_s": BUDGET_S, "est_flow_s": 900}
            chs = []
            for i, w in enumerate(ws):
                if not w["set"].endswith(str(s)):
                    continue
                cid = f"bs-{d}-{i + 1:02d}"
                e = chain_entry(w, fb, cid, cid + "-", name, gp, D=1.0)
                e["max_rebuilds"] = 1
                chs.append(e)
            groups.append(dict(name=name, chains=chs, **gp))
    return groups


def c1_runs(plan):
    """All 328 C1 replays with stable tags b1r-<design>-<nnn> (numbered per design in plan order)."""
    fb = plan["fbest"]
    n = {}
    out = []
    for r in plan["c1"]["runs"]:
        d = r["design"]
        n[d] = n.get(d, 0) + 1
        f = fb[d]
        out.append({"tag": f"b1r-{d}-{n[d]:03d}", "kind": "c1r", "setting": r["setting"], "design": d,
                    "base_spec": f"farm/jobs/{r['source']}.json", "source": r["source"], "period": r["T"],
                    "D": f["D"], "io0": f["io0"], "F_best": f["F_best"],
                    "est_s": round(1.2 * rec_seconds(r["source"]) + 300)})
    return out


def c1_groups(plan, settings, cap=12000.0):
    rs = [r for r in c1_runs(plan) if r["setting"] in settings]
    bins = []
    for r in sorted(rs, key=lambda r: (-r["est_s"], r["tag"])):      # first-fit decreasing, longest jobs first
        for b in bins:
            if b["t"] + r["est_s"] <= cap:
                b["runs"].append(r)
                b["t"] += r["est_s"]
                break
        else:
            bins.append({"t": r["est_s"], "runs": [r]})
    groups = []
    for i, b in enumerate(bins, 1):
        groups.append({"name": f"c1-{i:02d}", "timeout_s": 16000, "budget_s": BUDGET_S,
                       "est_flow_s": max(r["est_s"] for r in b["runs"]), "est_total_s": round(b["t"]),
                       "runs": sorted(b["runs"], key=lambda r: r["tag"])})
    return groups


def c2b_groups(plan):
    """C2b: the 10 Addendum-35 races (5 designs x 2 seeds), plain TPE as arm b, frozen I/O. Start sets and DRV
    references are read from the landed record with the farm's own functions (farm/tune_a32.py start_set, ref_drv_x8)."""
    import sys as _s
    _s.path.insert(0, os.path.join(ROOT, "farm"))
    import tune_a35 as X                          # ROOT /home/claude/eda: reads results/tune_x6 (start sets)
    fb = plan["fbest"]
    groups = []
    for r in plan["c2b"]["races"]:
        d, s = r["design"], r["seed"]
        f = fb[d]
        start = []
        for t, v, params in X.B.start_set(d):
            start.append({"tag": t, "spec": f"farm/jobs/{t}.json", "params": params,
                          "T": v["overrides"]["CLOCK_PERIOD"]})
        ref = X.B.ref_drv_x8(d)
        name = f"c2b-{d}-s{s}"
        groups.append({"name": name, "timeout_s": 16000, "budget_s": BUDGET_S, "est_flow_s": 900,
                       "race": {"design": d, "seed": s, "seed35": X.seed35(d, s), "D": f["D"], "io0": f["io0"],
                                "F_best": f["F_best"], "drv_ref": ref, "tag_prefix": f"b2b-{d}-s{s}-",
                                "start": start}})
    return groups


def smoke_groups(plan):
    fb = plan["fbest"]
    x = fb["xtea"]
    ctl = {"name": "smoke-ctl", "timeout_s": 7200, "budget_s": 7200, "est_flow_s": 300,
           "runs": [{"tag": "smoke-b-xtea-ctl", "base_spec": "farm/jobs/xac-xtea-024.json", "period": x["F_best"],
                     "D": x["D"], "io0": x["io0"], "F_best": x["F_best"], "drv_ref": 0,
                     "note": "control: replay of xac-xtea-024 at T = F_best with the override (must equal the record)"}]}
    w = next(w for w in plan["c2a"] if w["source"] == "xah1-xtea-007")
    gp = {"timeout_s": 7200, "budget_s": 7200, "est_flow_s": 300}
    ch = chain_entry(w, fb, "smoke-b2a-xtea", "smoke-b2a-xtea-", "smoke-chain", gp, stop_first=True)
    return [ctl, dict(name="smoke-chain", chains=[ch], **gp)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--batch", required=True)
    ap.add_argument("--kind", required=True, choices=["smoke", "c2a", "s", "c1", "c2b"])
    ap.add_argument("--settings", default="", help="C1: setting indices, e.g. 0-9,12,15-20")
    ap.add_argument("--max-parallel", type=int, default=4)
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    plan = json.load(open(os.path.join(HERE, "plan.json")))
    if a.kind == "c1":
        sel = set()
        for part in a.settings.split(","):
            if "-" in part:
                lo, hi = part.split("-")
                sel |= set(range(int(lo), int(hi) + 1))
            elif part:
                sel.add(int(part))
        groups = c1_groups(plan, sel)
    else:
        groups = {"smoke": smoke_groups, "c2a": c2a_groups, "s": s_groups, "c2b": c2b_groups}[a.kind](plan)
    spec = {"batch": a.batch, "kind": a.kind, "max_parallel": a.max_parallel,
            "about": f"workstream B {a.kind} batch {a.batch} (docs/qa_week/B_PREREG.md). {a.note}".strip(),
            "groups": groups}
    os.makedirs(os.path.join(HERE, "batches"), exist_ok=True)
    out = os.path.join(HERE, "batches", a.batch + ".json")
    json.dump(spec, open(out, "w"), indent=1)
    n_ch = sum(len(g.get("chains") or []) for g in groups)
    n_r = sum(len(g.get("runs") or []) for g in groups)
    print(f"{out}: {len(groups)} groups, {n_ch} chains, {n_r} runs, max_parallel {a.max_parallel}")
    for g in groups:
        print(f"  {g['name']:22s} chains {len(g.get('chains') or [])} runs {len(g.get('runs') or [])} "
              f"est_flow_s {g.get('est_flow_s')}")


if __name__ == "__main__":
    main()
