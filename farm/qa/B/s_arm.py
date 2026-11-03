#!/usr/bin/env python3
"""Workstream B, arm S scoring (registered, docs/qa_week/B_PREREG.md): D = 1.0 ns flat for the 40 race winners.

  python3 -I farm/qa/B/s_arm.py --results /home/claude/qa/b/results [--out farm/qa/B/s_arm.json]

S-a (registered): the C2a-ii test applied to the 40 race winners ("at least 2 first rebuilds fail") gives the same verdict
under D = 1.0 ns (chains bs-*) as under C2a's D (chains b2a-*, same 40 winners). S-b (beside, no criterion): the 40
per-winner first-rebuild verdicts all agree.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blib  # noqa: E402


def load(cdir, prefix):
    out = {}
    for f in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
        if f.startswith(prefix) and f.endswith(".json"):
            c = json.load(open(os.path.join(cdir, f)))
            fr = blib.first_rebuild(c["state"]) if c.get("state") else None
            out[c["source"]] = {"chain_id": c["chain_id"], "first_fails": None if fr is None else not fr.get("pass"),
                                "claim0": c["state"][0].get("claim") if c.get("state") else None,
                                "R1": fr and fr.get("period")}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "s_arm.json"))
    a = ap.parse_args()
    plan = json.load(open(os.path.join(HERE, "plan.json")))
    race = [w["source"] for w in plan["s"]]
    cdir = os.path.join(a.results, "chains")
    S, C = load(cdir, "bs-"), load(cdir, "b2a-")
    both = [s for s in race if s in S and s in C and S[s]["first_fails"] is not None and C[s]["first_fails"] is not None]
    kS = sum(1 for s in both if S[s]["first_fails"])
    kC = sum(1 for s in both if C[s]["first_fails"])
    ready = len(both) == len(race)
    agree = [s for s in both if S[s]["first_fails"] == C[s]["first_fails"]]
    res = {"n_both": len(both), "S_fails": kS, "C2a_fails_same_40": kC,
           "S_a": {"S_verdict": kS >= 2, "C2a_verdict": kC >= 2,
                   "verdict": ("PASS" if (kS >= 2) == (kC >= 2) else "FAIL") if ready else "pending"},
           "S_b": {"agree": len(agree), "of": len(both), "disagree": [s for s in both if s not in agree]},
           "rows": {s: {"S": S.get(s), "C2a": C.get(s)} for s in race}}
    json.dump(res, open(a.out, "w"), indent=1)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))


if __name__ == "__main__":
    main()
