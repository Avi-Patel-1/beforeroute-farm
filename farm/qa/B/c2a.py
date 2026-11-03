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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--prefix", default="b2a-")
    ap.add_argument("--out", default=os.path.join(HERE, "c2a.json"))
    ap.add_argument("--final", action="store_true")
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
    for w in W:
        c = chains.get(w["source"])
        row = {"design": w["design"], "set": w["set"], "source": w["source"], "T0": w["T0"],
               "claim_orig": w["claim_orig"], "orig_first_pass": (w.get("orig_first_rebuild") or {}).get("pass"),
               "D": w["D"], "landed": c is not None}
        if c is None:
            rows.append(row)
            continue
        s = c["state"]
        wr = s[0] if s else None
        fr = blib.first_rebuild(s) if s else None
        row.update({"chain_id": c["chain_id"], "complete": bool(c.get("complete")), "stage": c.get("stage"),
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
    # C2a-ii is decided as soon as 2 failures have landed (more landings cannot undo ">= 2")
    json.dump(res, open(a.out, "w"), indent=1, default=str)
    print(f"chains landed {res['landed_chains']}/48, complete {res['complete_chains']}; first rebuilds landed "
          f"{len(fr_landed)}/{n_expected}")
    print("C2a-i  :", res["C2a_i"]["still_fail"], "of", len(of), "original failures still fail ->", res["C2a_i"]["verdict"],
          res["C2a_i"]["which"])
    print("C2a-ii :", n_fail, "of", len(fr_landed), "first rebuilds fail ->", res["C2a_ii"]["verdict"], res["C2a_ii"]["which"])
    print("C2a-iii: median g", None if not gs else round(st.median(gs), 4), f"(n {len(gs)}) ->", res["C2a_iii"]["verdict"])
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
