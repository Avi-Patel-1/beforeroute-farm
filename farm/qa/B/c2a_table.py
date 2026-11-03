#!/usr/bin/env python3
"""Workstream B, arm C2a: render farm/qa/B/c2a.json (from c2a.py) as markdown tables for the result file (descriptive).

  python3 -I farm/qa/B/c2a_table.py [--in farm/qa/B/c2a.json]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))


def f(x, nd=2):
    return "–" if x is None else f"{x:.{nd}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default=os.path.join(HERE, "c2a.json"))
    a = ap.parse_args()
    d = json.load(open(a.inp))
    rows = [r for r in d["rows"] if r.get("landed")]
    print("| winner (search run) | design | T0 (ns) | claim, stock budget (record) | claim, frozen | first rebuild R1 | "
          "R1 verdict | R1 limiting path | record's first rebuild | kept clock K | T1/K |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        fr = r.get("first_rebuild") or {}
        lim = {True: "port", False: "reg-to-reg", None: "–"}[fr.get("port")]
        ver = "–" if r.get("first_fails") is None else ("**fail**" if r["first_fails"] else "pass")
        why = ""
        if r.get("first_fails"):
            bits = []
            if fr.get("ws") is not None and fr["ws"] < 0:
                bits.append(f"setup {fr['ws']:+.3f}")
            if fr.get("hold_ws") is not None and fr["hold_ws"] < 0:
                bits.append(f"hold {fr['hold_ws']:+.3f}")
            if fr.get("drc"):
                bits.append(f"DRC {fr['drc']}")
            if fr.get("drv") is not None:
                bits.append(f"slew/cap {fr['drv']}")
            why = " (" + ", ".join(bits) + ")" if bits else ""
        orig = {True: "pass", False: "fail", None: "–"}[r.get("orig_first_pass")]
        print(f"| {r['source']} | {r['design']} | {f(r['T0'])} | {f(r['claim_orig'], 3)} | {f(r.get('claim_frozen'), 3)} | "
              f"{f(fr.get('period'))} | {ver}{why} | {lim} | {orig} | {f(r.get('K'))} | "
              f"{f(r.get('g'), 3) if r.get('g') else '–'}{'' if r.get('complete') else ' (chain running)'} |")
    ch = [r for r in rows if r.get("claim_frozen") is not None]
    if ch:
        dif = [(r["claim_frozen"] - r["claim_orig"]) / r["claim_orig"] for r in ch]
        print(f"\nfrozen vs stock-budget claim at the same search target: median {100 * st.median(dif):+.1f}% "
              f"(range {100 * min(dif):+.1f}% to {100 * max(dif):+.1f}%, n {len(dif)})")


if __name__ == "__main__":
    main()
