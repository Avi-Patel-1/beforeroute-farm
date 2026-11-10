#!/usr/bin/env python3
"""Workstream L scorer (registered with docs/qa_week/L_PREREG.md). Reads results/races/l<block><seed><arm>.json from the
downloaded artifacts and prints the registered verdicts.
  match-or-beat: the loop's kept clock is no more than 2% slower than plain Bayesian search's (or Bayesian kept none
                 and the loop kept one). beat: more than 2% faster. No kept clock for the loop = a loss.
  P1: the loop matches or beats in at least 4 of the 6 races.   P2: every loop kept build is signoff-clean.
"""
import glob
import json
import os
import sys

root = sys.argv[1] if len(sys.argv) > 1 else "results"
R = {}
for p in glob.glob(os.path.join(root, "**", "races", "l*.json"), recursive=True):
    r = json.load(open(p))
    R[(r["block"], r["seed"], r["arm"])] = r
blocks = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "blocks.json")))["blocks"]
rows, mb, beat, clean, kept_l = [], 0, 0, 0, 0
for k in blocks:
    for s in (1, 2):
        b, l = R.get((k, s, "b")), R.get((k, s, "L"))
        if b is None or l is None:
            rows.append({"block": blocks[k]["design"], "seed": s, "missing": [x for x, v in (("b", b), ("L", l)) if v is None]})
            continue
        kb, kl = b.get("kept_clock"), l.get("kept_clock")
        if kl is None:
            v = "loss"
        elif kb is None:
            v = "beat"
        else:
            v = "beat" if kl < kb / 1.02 else ("match" if kl <= kb * 1.02 else "loss")
        mb += v in ("beat", "match")
        beat += v == "beat"
        so = l.get("signoff") or {}
        kept_l += kl is not None
        clean += bool(so.get("clean"))
        nflow = lambda r: len(r["trials"]) + max(len((r.get("chain") or {}).get("state", [])) - 1, 0)
        rows.append({"block": blocks[k]["design"], "seed": s, "bayes_kept_ns": kb, "loop_kept_ns": kl,
                     "loop_vs_bayes": round(kb / kl, 4) if kb and kl else None, "verdict": v,
                     "bayes_search_runs": len(b["trials"]), "loop_search_runs": len(l["trials"]),
                     "bayes_flows": nflow(b), "loop_flows": nflow(l), "loop_pins": l.get("pins"),
                     "signoff_clean": so.get("clean"), "signoff": so.get("metrics"), "signoff_clock": so.get("clock")})
n = sum(1 for r in rows if "verdict" in r)
out = {"races_scored": n, "match_or_beat": mb, "beat": beat, "P1 (>= 4 of 6 match or beat)": (mb >= 4) if n == 6 else None,
       "loop_kept": kept_l, "signoff_clean": clean, "P2 (every loop kept build signoff-clean)": (clean == kept_l and kept_l > 0) if n == 6 else None,
       "rows": rows}
print(json.dumps(out, indent=1))
