#!/usr/bin/env python3
"""Workstream B, arm C2b scoring (registered, docs/qa_week/B_PREREG.md): fresh TPE races with frozen I/O.

  python3 -I farm/qa/B/c2b.py --results /home/claude/qa/b/results [--out farm/qa/B/c2b.json]

Reads results/races/c2b-<design>-s<seed>.json and the winners' chains (results/chains/b2b-<design>-s<seed>-k.json).
  C2b-i:  >= 1 of the 10 winners' first rebuilds fails
  C2b-ii: >= 6 of 10 chains have rebuild-again gain g = T1/K >= 1.02 (slide 5's ">2%"); no passing rebuild = no gain
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import blib  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--out", default=os.path.join(HERE, "c2b.json"))
    a = ap.parse_args()
    races = {}
    for p in sorted(glob.glob(os.path.join(a.results, "races", "c2b-*.json"))):
        r = json.load(open(p))
        races[r["race"]] = r
    rows = []
    for name, r in sorted(races.items()):
        cp = os.path.join(a.results, "chains", f"b2b-{r['design']}-s{r['seed']}-k.json")
        c = json.load(open(cp)) if os.path.exists(cp) else None
        row = {"race": name, "winner": r.get("winner"), "n_trials": len(r.get("trials") or []),
               "chain_complete": bool(c and c.get("complete"))}
        if c:
            s = c["state"]
            fr = blib.first_rebuild(s)
            T1, K = blib.first_pass_clock(s), blib.kept_clock(s)
            row.update({"C0": s[0].get("claim"), "T0": s[0]["period"], "first_fails": None if fr is None else
                        not fr.get("pass"), "T1": T1, "K": K, "g": (T1 / K) if (T1 and K) else None,
                        "chain": [(x["tag"], x["period"], x.get("claim"), x.get("pass")) for x in s]})
        rows.append(row)
    done = [x for x in rows if x.get("chain_complete")]
    fails = sum(1 for x in rows if x.get("first_fails"))
    gains = sum(1 for x in done if x.get("g") is not None and x["g"] >= 1.02)
    ready = len(done) == 10
    res = {"races_landed": len(rows), "chains_complete": len(done),
           "C2b_i": {"first_rebuild_fails": fails, "verdict": "PASS" if fails >= 1 else ("FAIL" if ready else "pending")},
           "C2b_ii": {"gain_ge_1.02": gains, "of": len(done),
                      "verdict": "PASS" if gains >= 6 else ("FAIL" if ready or (gains + 10 - len(done)) < 6 else
                                                            "pending")},
           "rows": rows}
    json.dump(res, open(a.out, "w"), indent=1, default=str)
    print(json.dumps({k: v for k, v in res.items() if k != "rows"}, indent=1))
    for x in rows:
        print(x["race"], x.get("winner"), "C0", x.get("C0"), "first_fails", x.get("first_fails"), "T1", x.get("T1"),
              "K", x.get("K"), "g", x.get("g") and round(x["g"], 4))


if __name__ == "__main__":
    main()
