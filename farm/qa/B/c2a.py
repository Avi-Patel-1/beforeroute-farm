#!/usr/bin/env python3
"""Workstream B, arm C2a scoring (registered tests, docs/qa_week/B_PREREG.md).

  python3 -I farm/qa/B/c2a.py --results /home/claude/qa/b/results [--prefix b2a-] [--out farm/qa/B/c2a.json]

Reads results/chains/<chain_id>.json (runner-side chain states collected by farm/qa/B/collect.py) and farm/qa/B/plan.json.
Per winner: W = the winner's job spec replayed at its search target T0 with frozen I/O (claim C0); first rebuild at
ceil05(C0) (blib.first_rebuild); kept clock K; T1 = first passing rebuild; g = T1/K.
  C2a-i:   >= 2 of the 3 original failures (x1t-picorv32-014, x1t-y_huff-005, x2t-bm64-007) fail their first rebuild
  C2a-ii:  >= 2 of the 48 first rebuilds fail
  C2a-iii: median g over chains with a passing rebuild >= 1.05
A winner whose replay has no claim leaves the denominators. Verdicts are "pending" until every first rebuild (i, ii) or
every chain (iii) has landed, unless --final (the registered latest decision time) is given.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blib  # noqa: E402

ORIG_FAIL = ["x1t-picorv32-014", "x1t-y_huff-005", "x2t-bm64-007"]
# Logical configurations already run in smoke (Amendment B.1; audit request: flag by configuration, not by tag):
# the XTEA race winner xah1-xtea-007 with D = 0.84 ns at these targets (smoke run 41566723780, tags smoke-b2a-xtea-*).
SMOKE_SEEN = {("xah1-xtea-007", 11.71), ("xah1-xtea-007", 4.55), ("xah1-xtea-007", 4.15), ("xah1-xtea-007", 4.10)}


def status_class(x):
    """Audit request: keep failed completed builds distinct from flow errors and from runs that never landed."""
    if x is None:
        return "not landed"
    if x.get("claim") is None:
        return "flow error (no metrics after the retry)"
    if x.get("pass"):
        return "completed, pass"
    why = []
    if x.get("ws") is not None and x["ws"] < 0:
        why.append("setup")
    if x.get("hold_ws") is not None and x["hold_ws"] < 0:
        why.append("hold")
    if x.get("drc"):
        why.append("DRC")
    if x.get("drv") is not None and x.get("drv_ref") is not None and x["drv"] > x["drv_ref"]:
        why.append("slew/cap")
    return "completed, fail (" + "+".join(why or ["judge"]) + ")"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--prefix", default="b2a-")
    ap.add_argument("--out", default=os.path.join(HERE, "c2a.json"))
    ap.add_argument("--final", action="store_true")
    ap.add_argument("--judge", choices=["failclosed", "runner"], default="failclosed",
                    help="failclosed (default, fix 2026-11-03): re-judge every chain entry from the collected run "
                         "directory with blib.load_run; runner: the pass flags the runner recorded (before the fix)")
    a = ap.parse_args()
    plan = json.load(open(os.path.join(HERE, "plan.json")))
    W = plan["c2a"]
    chains = {}
    cdir = os.path.join(a.results, "chains")
    for f in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
        if f.startswith(a.prefix) and f.endswith(".json"):
            c = json.load(open(os.path.join(cdir, f)))
            chains[c["source"]] = c
    rows = []
    rejudge_diff = []
    for w in W:
        c = chains.get(w["source"])
        row = {"design": w["design"], "set": w["set"], "source": w["source"], "T0": w["T0"], "drv_ref": w["drv_ref"],
               "claim_orig": w["claim_orig"], "orig_first_pass": (w.get("orig_first_rebuild") or {}).get("pass"),
               "D": w["D"], "landed": c is not None}
        if c is None:
            rows.append(row)
            continue
        s = c["state"]
        for x in s:                                   # fail-closed re-judge of every entry from its own run directory
            x["pass_runner"] = x.get("pass")
            if a.judge == "runner":
                continue
            if os.path.isdir(os.path.join(a.results, x["tag"])):
                j = blib.load_run(a.results, x["tag"], x["period"], w["drv_ref"])
                x.update({"pass": j["pass"], "claim": j["claim"], "admitted": j["admitted"], "why": j["why"],
                          "ws": j["ws"], "ws_r2r": j["ws_r2r"], "hold_ws": j["hold_ws"], "drc": j["drc"],
                          "drv": j["drv"], "port": j["port"]})
            else:
                x.update({"pass": False, "admitted": False, "why": "run directory not collected"})
            if bool(x["pass"]) != bool(x["pass_runner"]):
                rejudge_diff.append({"tag": x["tag"], "runner": x["pass_runner"], "failclosed": x["pass"],
                                     "why": x.get("why")})
        wr = s[0] if s else None
        fr = blib.first_rebuild(s) if s else None
        for x in s:
            x.setdefault("drv_ref", w["drv_ref"])
        row.update({"chain_id": c["chain_id"], "complete": bool(c.get("complete")), "stage": c.get("stage"),
                    "W_status": status_class(wr), "R1_status": status_class(fr) if s else "not landed",
                    "smoke_seen": sorted(x["period"] for x in s if (w["source"], round(x["period"], 2)) in SMOKE_SEEN),
                    "W": wr and {k: wr.get(k) for k in ("tag", "period", "claim", "pass", "port", "ws", "ws_r2r",
                                                        "io_pct")},
                    "claim_frozen": wr and wr.get("claim"),
                    "first_rebuild": fr and {k: fr.get(k) for k in ("tag", "period", "claim", "pass", "port", "ws",
                                                                    "ws_r2r", "hold_ws", "drc", "drv")},
                    "first_fails": None if fr is None else (not fr.get("pass")),
                    "K": blib.kept_clock(s), "T1": blib.first_pass_clock(s),
                    "chain": [(x["tag"], x["period"], x.get("claim"), x.get("pass")) for x in s]})
        if row["T1"] and row["K"]:
            row["g"] = row["T1"] / row["K"]
        if wr is not None and wr.get("claim") is None:
            row["no_claim"] = True
        rows.append(row)
    have_claim = [r for r in rows if r.get("landed") and not r.get("no_claim")]
    fr_landed = [r for r in have_claim if r.get("first_fails") is not None]
    n_expected = len([r for r in rows if not r.get("no_claim")])
    all_first = len(fr_landed) == n_expected
    all_chains = all(r.get("landed") and r.get("complete") for r in rows if not r.get("no_claim"))
    of = [r for r in fr_landed if r["source"] in ORIG_FAIL]
    n_of_fail = sum(1 for r in of if r["first_fails"])
    n_fail = sum(1 for r in fr_landed if r["first_fails"])
    gs = [r["g"] for r in rows if r.get("g") is not None and r.get("complete")]

    def verdict(ok, ready):
        return ("PASS" if ok else "FAIL") if (ready or a.final) else "pending"
    res = {
        "judge": a.judge, "rejudge_discrepancies": rejudge_diff,
        "landed_chains": sum(1 for r in rows if r.get("landed")), "complete_chains": sum(1 for r in rows if r.get("complete")),
        "first_rebuilds_landed": len(fr_landed), "expected": n_expected, "no_claim": [r["source"] for r in rows if r.get("no_claim")],
        "C2a_i": {"original_failures_landed": len(of), "still_fail": n_of_fail,
                  "which": [(r["source"], r["first_fails"]) for r in of],
                  "verdict": ("PASS" if n_of_fail >= 2 else "FAIL" if (len(of) - n_of_fail) >= 2
                              else verdict(False, len(of) == 3))},
        "C2a_ii": {"fails": n_fail, "of": len(fr_landed), "which": [r["source"] for r in fr_landed if r["first_fails"]],
                   "verdict": verdict(n_fail >= 2, all_first) if not (n_fail >= 2) else "PASS"},
        "C2a_iii": {"n": len(gs), "median_g": st.median(gs) if gs else None,
                    "over_1.02": sum(1 for g in gs if g >= 1.02),
                    "verdict": verdict(bool(gs) and st.median(gs) >= 1.05, all_chains)},
        "rows": rows,
    }
    # per-design counts beside the pooled ones (audit request)
    per = {}
    for r in rows:
        p = per.setdefault(r["design"], {"winners": 0, "landed": 0, "first_fail": 0, "first_pass": 0, "no_claim": 0,
                                         "gains": []})
        p["winners"] += 1
        if r.get("landed"):
            p["landed"] += 1
        if r.get("no_claim"):
            p["no_claim"] += 1
        if r.get("first_fails") is True:
            p["first_fail"] += 1
        if r.get("first_fails") is False:
            p["first_pass"] += 1
        if r.get("g") is not None and r.get("complete"):
            p["gains"].append(round(r["g"], 4))
    for p in per.values():
        p["median_g"] = st.median(p["gains"]) if p["gains"] else None
    res["per_design"] = per
    res["status_counts"] = {}
    for r in rows:
        for k in ("W_status", "R1_status"):
            if r.get(k):
                res["status_counts"].setdefault(k, {}).setdefault(r[k], 0)
                res["status_counts"][k][r[k]] += 1
    res["smoke_overlap"] = {r["source"]: r["smoke_seen"] for r in rows if r.get("smoke_seen")}
    # beside (descriptive, not registered): the same counts with a setup-only judge, and fails by reason
    so = [r for r in fr_landed if (r.get("first_rebuild") or {}).get("ws") is not None]
    res["beside_setup_only"] = {
        "first_rebuild_setup_fails": sum(1 for r in so if r["first_rebuild"]["ws"] < 0), "of": len(so),
        "original_failures_setup_fail": [(r["source"], r["first_rebuild"]["ws"] < 0) for r in so
                                         if r["source"] in ORIG_FAIL],
        "fails_by_reason": {k: v for k, v in res["status_counts"].get("R1_status", {}).items() if "fail" in k}}
    # C2a-ii is decided as soon as 2 failures have landed (more landings cannot undo ">= 2")
    json.dump(res, open(a.out, "w"), indent=1, default=str)
    print(f"judge: {a.judge}; entries where the fail-closed re-judge differs from the runner's flag: "
          f"{len(rejudge_diff)} {rejudge_diff[:5]}")
    print(f"chains landed {res['landed_chains']}/48, complete {res['complete_chains']}; first rebuilds landed "
          f"{len(fr_landed)}/{n_expected}")
    print("C2a-i  :", res["C2a_i"]["still_fail"], "of", len(of), "original failures still fail ->", res["C2a_i"]["verdict"],
          res["C2a_i"]["which"])
    print("C2a-ii :", n_fail, "of", len(fr_landed), "first rebuilds fail ->", res["C2a_ii"]["verdict"], res["C2a_ii"]["which"])
    print("C2a-iii: median g", None if not gs else round(st.median(gs), 4), f"(n {len(gs)}) ->", res["C2a_iii"]["verdict"])
    print("per design:", {d: (p["first_fail"], p["landed"], p["winners"], p["median_g"]) for d, p in per.items()})
    print("status:", res["status_counts"])
    print("beside, setup-only judge:", res["beside_setup_only"])
    if res["smoke_overlap"]:
        print("already observed in smoke (same logical configuration):", res["smoke_overlap"])
    for r in rows:
        if not r.get("landed"):
            continue
        fr = r.get("first_rebuild") or {}
        print(f"  {r['source']:24s} T0 {r['T0']:6.2f} claim orig {r['claim_orig']:7.3f} frozen "
              f"{(r.get('claim_frozen') or float('nan')):7.3f} | R1 {fr.get('period')} pass {fr.get('pass')} "
              f"port {fr.get('port')} | K {r.get('K')} T1 {r.get('T1')} g {r.get('g') and round(r['g'], 3)} "
              f"{'' if r.get('complete') else '(chain incomplete)'}")


if __name__ == "__main__":
    main()
