#!/usr/bin/env python3
"""Evaluate the pre-registered intervention criteria from results/<base>/hero_summary.json files.

Usage: criteria.py [--round R3|R4|A5|R5|all] [--results results] [--json out.json]
Violators = signal nets violating at nine-corner signoff; reference = the base's `rerun` arm
(same rebuilt checkpoint as the arms), falling back to the baseline row. A criterion on a base is
"pending" until every arm it needs has landed; a round's verdict is reported only when no base is pending.
"""
from __future__ import annotations

import argparse
import json
import os

R3 = ["d3-salsa20-000", "d3-des-000", "d3-y_huff-000", "d3-ocs_blitter-000", "d3-bm64-000", "d3-md5-000"]
R4 = ["d3b-sha512-000", "d3b-ldpcenc-000"]
R1 = ["d1-picorv32-006", "d1-picorv32-016", "d1-aes_cipher-000"]
R5 = ["d5-chacha-000", "d5-point_add-000", "d5-blabla-000"]


def load(results, base):
    p = os.path.join(results, base, "hero_summary.json")
    if not os.path.exists(p):
        return None
    hs = json.load(open(p))
    rows = {}
    for r in hs["arms"]:
        arm = "base" if r["tag"] == base else r["tag"][len(base) + 1:]
        rows[arm] = r
    return rows


def V(r):
    return r.get("signoff_violating_data_nets")


def cells(r):
    if r.get("resized") is None and r.get("buffers") is None:
        return None
    return (r.get("resized") or 0) + (r.get("buffers") or 0)


def ref_of(rows):
    return rows.get("rerun") or rows.get("base")


def removed(rows, arm):
    ref, r = ref_of(rows), rows.get(arm)
    if r is None or V(r) is None or not V(ref):
        return None
    return 1 - V(r) / V(ref)


def c_target_vs_uni50(rows, arm):
    """arm removes >= uni50's fraction, with <= 60% of uni50's cells, and hold WS >= uni50's."""
    a, u = rows.get(arm), rows.get("uni50")
    if a is None or u is None:
        return "pending", {}
    fa, fu = removed(rows, arm), removed(rows, "uni50")
    ca, cu = cells(a), cells(u)
    ha, hu = a.get("hold_ws"), u.get("hold_ws")
    ok = fa >= fu and ca is not None and cu and ca <= 0.6 * cu and ha is not None and hu is not None and ha >= hu
    return ("pass" if ok else "fail"), {"removed": round(fa, 3), "uni50_removed": round(fu, 3), "cells": ca, "uni50_cells": cu,
                                         "cells_ratio": round(ca / cu, 2) if ca is not None and cu else None, "hold": round(ha, 4) if ha is not None else None,
                                         "uni50_hold": round(hu, 4) if hu is not None else None}


def c_model_vs_rule(rows, arm, rules):
    a = rows.get(arm)
    have = [rows[r] for r in rules if r in rows]
    if a is None or len(have) < len(rules):
        return "pending", {}
    best = min(V(r) for r in have)
    return ("pass" if V(a) < best else "fail"), {"model_V": V(a), **{f"{r}_V": V(rows[r]) for r in rules}}


def c_removes(rows, arm, frac, cells_vs_uni50=None):
    a = rows.get(arm)
    if a is None or (cells_vs_uni50 is not None and rows.get("uni50") is None):
        return "pending", {}
    f = removed(rows, arm)
    ok = f >= frac
    info = {"removed": round(f, 3), "V": V(a), "ref_V": V(ref_of(rows))}
    if cells_vs_uni50 is not None:
        ca, cu = cells(a), cells(rows["uni50"])
        ok = ok and ca is not None and cu and ca <= cells_vs_uni50 * cu
        info.update(cells=ca, uni50_cells=cu, cells_ratio=round(ca / cu, 2) if ca is not None and cu else None)
    return ("pass" if ok else "fail"), info


def c_fewer_cells(rows, arm, other):
    a, o = rows.get(arm), rows.get(other)
    if a is None or o is None:
        return "pending", {}
    ca, co = cells(a), cells(o)
    return ("pass" if ca is not None and co is not None and ca < co else "fail"), {"cells": ca, f"{other}_cells": co, "V": V(a), f"{other}_V": V(o)}


def c_equiv(results, base, rows, arms):
    out = {}
    for arm in arms:
        if arm not in rows:
            return "pending", out
        p = os.path.join(results, f"{base}-{arm}", "equiv", "result.json")
        out[arm] = json.load(open(p)).get("status") if os.path.exists(p) else "missing"
    ok = all(v == "PROVED" for v in out.values())
    return ("pass" if ok else "fail"), out


def verdict(per_base, need):
    st = [s for s, _ in per_base.values()]
    if "pending" in st or len(st) < need[1]:
        npass, nfail, npend = st.count('pass'), st.count('fail'), st.count('pending') + need[1] - len(st)
        # decided once the pending bases can no longer change the outcome
        if npass >= need[0]:
            return f"PASS, decided early ({npass} pass, {nfail} fail, {npend} pending; needed {need[0]} of {need[1]})"
        if npass + npend < need[0]:
            return f"FAIL, decided early ({npass} pass, {nfail} fail, {npend} pending; needed {need[0]} of {need[1]})"
        return f"pending ({npass} pass, {nfail} fail, {npend} pending)"
    n = st.count("pass")
    return f"{'PASS' if n >= need[0] else 'FAIL'} ({n} of {len(st)}; needed {need[0]})"


def evaluate(results, name, bases, crits):
    out = {"round": name, "criteria": {}}
    for cname, fn, need in crits:
        per = {}
        for b in bases:
            rows = load(results, b)
            per[b] = ("pending", {}) if rows is None else fn(b, rows)
        out["criteria"][cname] = {"verdict": verdict(per, need), "per_base": {b: {"status": s, **i} for b, (s, i) in per.items()}}
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--round", default="all")
    ap.add_argument("--results", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    R = a.results
    rounds = {
        "R3": (R3, [
            ("A1.1 tgt050-70 vs uni50 (>= removed, <= 60% cells, hold >=)", lambda b, r: c_target_vs_uni50(r, "tgt050-70"), (5, 6)),
            ("A1.2+A4 tgt050-70 fewer violators than best of det050-70/est050-70", lambda b, r: c_model_vs_rule(r, "tgt050-70", ["det050-70", "est050-70"]), (5, 6)),
            ("A1.3 thr500-70 removes >= 90%", lambda b, r: c_removes(r, "thr500-70", 0.90), (4, 6)),
            # (no equivalence criterion: the Round-3 tgt/thr/det arms were dispatched before the runner kept netlists)
        ]),
        "R4": (R4, [
            ("A3 tgt050-70 vs uni50", lambda b, r: c_target_vs_uni50(r, "tgt050-70"), (2, 2)),
            ("A3+A4 tgt050-70 fewer violators than best of det050-70/est050-70", lambda b, r: c_model_vs_rule(r, "tgt050-70", ["det050-70", "est050-70"]), (2, 2)),
            ("A3 exp100-70 removes >= 85% with <= 60% of uni50 cells", lambda b, r: c_removes(r, "exp100-70", 0.85, 0.6), (2, 2)),
        ]),
        "A5": (R3, [
            ("A5.1 exp100-70 removes >= 85% with <= 60% of uni50 cells (Round-3 bases)", lambda b, r: c_removes(r, "exp100-70", 0.85, 0.6), (5, 6)),
        ]),
        "R5": (R5, [
            ("A6.2 tgt050-70c vs uni50", lambda b, r: c_target_vs_uni50(r, "tgt050-70c"), (2, 3)),
            ("A6.3 tgt050-70c fewer violators than est050-70c", lambda b, r: c_model_vs_rule(r, "tgt050-70c", ["est050-70c"]), (2, 3)),
            ("A6.4 thr500-70c removes >= 90%", lambda b, r: c_removes(r, "thr500-70c", 0.90), (2, 3)),
            ("A6.5 exp100-70c removes >= 85% with <= 60% of uni50 cells", lambda b, r: c_removes(r, "exp100-70c", 0.85, 0.6), (2, 3)),
            ("A6.6 equivalence of the targeted arms", lambda b, r: c_equiv(R, b, r, ["est050-70c", "tgt050-70c", "thr500-70c", "exp100-70c"]), (3, 3)),
        ]),
        "A9": (R3, [
            ("A9a thr500-70 fewer violators than rcal146-0 (wire cap x1.461 = under-calibrated, no margin)", lambda b, r: c_model_vs_rule(r, "thr500-70", ["rcal146-0"]), (4, 6)),
            ("A9b thr500-70 fewer cells than rcal146-20 (wire cap x1.461 = under-calibrated, 20% margin)", lambda b, r: c_fewer_cells(r, "thr500-70", "rcal146-20"), (4, 6)),
        ]),
        "A10": (R3, [
            ("A10a thr500-70 fewer violators than rcal213-10 (wire cap x2.130, stock 10% margin)", lambda b, r: c_model_vs_rule(r, "thr500-70", ["rcal213-10"]), (4, 6)),
            ("A10b thr500-70 fewer cells than rcal213-10", lambda b, r: c_fewer_cells(r, "thr500-70", "rcal213-10"), (4, 6)),
        ]),
        "A11": (R3, [  # withdrawn 06:28Z before any arm ran (lists carried the output-port bug); kept for the record
            ("A11a thr500-70 fewer violators than lst-cal-70 (learned RC calibration, equal budget)", lambda b, r: c_model_vs_rule(r, "thr500-70", ["lst-cal-70"]), (4, 6)),
            ("A11b thr500-70 fewer violators than lst-calt-70 (learned RC calibration, own threshold)", lambda b, r: c_model_vs_rule(r, "thr500-70", ["lst-calt-70"]), (4, 6)),
        ]),
        "NV": (["nv1-nvdla_csc-000"], [
            ("A7 (A6.2) tgt050-70c vs uni50", lambda b, r: c_target_vs_uni50(r, "tgt050-70c"), (1, 1)),
            ("A7 (A6.3) tgt050-70c fewer violators than est050-70c", lambda b, r: c_model_vs_rule(r, "tgt050-70c", ["est050-70c"]), (1, 1)),
            ("A7 (A6.4) thr500-70c removes >= 90%", lambda b, r: c_removes(r, "thr500-70c", 0.90), (1, 1)),
            ("A7 (A6.5) exp100-70c removes >= 85% with <= 60% of uni50 cells", lambda b, r: c_removes(r, "exp100-70c", 0.85, 0.6), (1, 1)),
            ("A7 (A6.6) equivalence of the targeted arms", lambda b, r: c_equiv(R, b, r, ["est050-70c", "tgt050-70c", "thr500-70c", "exp100-70c"]), (1, 1)),
        ]),
    }
    sel = list(rounds) if a.round == "all" else [a.round]
    res = [evaluate(R, k, *rounds[k]) for k in sel]
    for r in res:
        print(f"== {r['round']}")
        for c, v in r["criteria"].items():
            print(f"  {c}: {v['verdict']}")
            for b, info in v["per_base"].items():
                print(f"      {b:20s} {json.dumps(info)}")
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
