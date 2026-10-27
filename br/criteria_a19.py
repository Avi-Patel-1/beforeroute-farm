#!/usr/bin/env python3
"""Addenda 19, 20 and 22 criteria, exactly as registered (hashes in farm/prereg_hashes.txt).

V = signal nets violating max slew or max capacitance at any of the nine signoff corners (labels.json; fanout-only
violators are not counted, unlike Addenda 1–18 which used every DRV type on data nets).
ΔA = std-cell area minus the base re-run's. Noise band: counts differ only if |a−b| > 0.45·√max(a, b, 1).
Calibrated frontier F(ΔA): piecewise-linear V over ΔA through rcal213-0/10/20/30 (nearest end point outside the range).
Hold: worst hold slack over the nine corners (metrics timing__hold__ws); a difference counts only if > 25 ps.
A criterion on a base is pending until every arm it needs has landed (job status completed or flow_failed with a
signoff label file present); a verdict is printed as PASS/FAIL once decided or as running counts otherwise.
Usage: criteria_a19.py [--results results] [--json out.json]
"""
from __future__ import annotations

import argparse
import json
import math
import os

BASES = ["d3-bm64-000", "d3-des-000", "d3-md5-000", "d3-ocs_blitter-000", "d3-salsa20-000", "d3-y_huff-000",
         "d3b-ldpcenc-000", "d3b-sha512-000", "d5-blabla-000", "d5-chacha-000", "d5-point_add-000",
         "d1-picorv32-006", "d1-picorv32-016", "d1-aes_cipher-000"]
R1 = ["d1-picorv32-006", "d1-picorv32-016", "d1-aes_cipher-000"]
# Addendum 22: correlated-flow bases whose seed reached signoff (pico-006 and LDPC did not route under ORFS RC)
CF_BASES = ["d3cfo-bm64-000", "d3cfo-des-000", "d3cfo-md5-000", "d3cfo-ocs_blitter-000", "d3cfo-salsa20-000",
            "d3cfo-y_huff-000", "d3bcfo-sha512-000", "d5cfo-blabla-000", "d5cfo-chacha-000", "d5cfo-point_add-000",
            "d1cfo-picorv32-016", "d1cfo-aes_cipher-000"]
# the correlated bases whose unrepaired seed has >= 30% of its signoff violators under the limit at the post-GRT estimate
# (fixed in Addendum 22 from the seeds, before any arm ran): where a learned list has something left to find
CF_RESIDUAL = ["d3cfo-salsa20-000", "d3bcfo-sha512-000", "d5cfo-blabla-000", "d5cfo-chacha-000", "d5cfo-point_add-000",
               "d1cfo-picorv32-016"]
RESULTS = "results"


def base_area(base):
    m = os.path.join(RESULTS, base, "metrics.json")
    return json.load(open(m)).get("design__instance__area__stdcell") if os.path.exists(m) else None


def cells(base, a):
    p = os.path.join(RESULTS, base, "hero_summary.json")
    if not os.path.exists(p):
        return None
    r = {x["tag"]: x for x in json.load(open(p))["arms"]}.get(f"{base}-{a}")
    if not r or r.get("buffers") is None:
        return None
    return (r.get("buffers") or 0) + (r.get("resized") or 0)


def arm(base, a):
    d = os.path.join(RESULTS, f"{base}-{a}")
    lab = os.path.join(d, "labels.json")
    if not os.path.exists(lab):
        return None
    L = json.load(open(lab))
    V = sum(1 for r in L["nets"] if r.get("violated") and r.get("sigtype_s") == "SIGNAL" and (r.get("viol_slew") or r.get("viol_cap")))
    m = json.load(open(os.path.join(d, "metrics.json"))) if os.path.exists(os.path.join(d, "metrics.json")) else {}
    hv = None
    for k in ("timing__hold_vio__count",):
        hv = m.get(k)
    return {"V": V, "area": m.get("design__instance__area__stdcell"), "hold": m.get("timing__hold__ws"), "hold_vio": hv,
            "setup": m.get("timing__setup__ws")}


def band(a, b):
    return 0.45 * math.sqrt(max(a, b, 1))


def cmp_counts(a, b):
    """-1 if a fewer than b beyond the band, +1 if more, 0 tie."""
    if abs(a - b) <= band(a, b):
        return 0
    return -1 if a < b else 1


def frontier(base, arms=("rcal213-0", "rcal213-10", "rcal213-20", "rcal213-30"), ref="rerun"):
    base_area = (arm(base, ref) or {}).get("area") if ref else globals()["base_area"](base)
    pts = []
    for a in arms:
        r = arm(base, a)
        if r is None or r["area"] is None or base_area is None:
            return None, base_area
        pts.append((r["area"] - base_area, r["V"]))
    pts.sort()
    return pts, base_area


def F_at(pts, x):
    if x <= pts[0][0]:
        return pts[0][1]
    if x >= pts[-1][0]:
        return pts[-1][1]
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        if x0 <= x <= x1:
            return y0 if x1 == x0 else y0 + (y1 - y0) * (x - x0) / (x1 - x0)
    return pts[-1][1]


def below_frontier(base, a, arms=("rcal213-0", "rcal213-10", "rcal213-20", "rcal213-30"), ref="rerun"):
    pts, base_area = frontier(base, arms, ref)
    r = arm(base, a)
    if pts is None or r is None or r["area"] is None:
        return None
    dA = r["area"] - base_area
    f = F_at(pts, dA)
    if r["V"] < f - band(r["V"], f):
        s = "below"
    elif r["V"] > f + band(r["V"], f):
        s = "above"
    else:
        s = "on"
    return {"status": s, "V": r["V"], "F": round(f, 1), "dA_um2": round(dA, 1), "frontier": [(round(x, 1), y) for x, y in pts]}


def tally(per, need_pass, max_fail=None, n_total=None):
    vals = [v for v in per.values() if v is not None]
    n_total = n_total or len(per)
    ok = sum(1 for v in vals if v == "pass")
    bad = sum(1 for v in vals if v == "fail")
    pend = n_total - len(vals)
    if max_fail is None:  # pass = ok >= need_pass
        if ok >= need_pass:
            return "PASS"
        if ok + pend < need_pass:
            return "FAIL"
        return "pending"
    if ok >= need_pass and bad + pend <= max_fail:
        return "PASS"
    if bad > max_fail or ok + pend < need_pass:
        return "FAIL"
    return "pending"


def main() -> int:
    global RESULTS
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    RESULTS = a.results
    out = {}

    def frontier_crit(name, armname, bases=BASES, need=9, max_above=2,
                      farms=("rcal213-0", "rcal213-10", "rcal213-20", "rcal213-30"), ref="rerun", what="calibrated"):
        per, detail = {}, {}
        for b in bases:
            r = below_frontier(b, armname, farms, ref)
            detail[b] = r
            per[b] = None if r is None else ("pass" if r["status"] == "below" else ("fail" if r["status"] == "above" else "tie"))
        below = sum(1 for v in per.values() if v == "pass")
        above = sum(1 for v in per.values() if v == "fail")
        pend = sum(1 for v in per.values() if v is None)
        if below >= need and above + pend <= max_above:
            verdict = "PASS"
        elif above > max_above or below + pend < need:
            verdict = "FAIL"
        else:
            verdict = "pending"
        out[name] = {"verdict": verdict, "below": below, "above": above, "pending": pend, "per_base": detail}
        print(f"  {name} {armname} below the {what} frontier (need >= {need} below, <= {max_above} above): {verdict} ({below} below, {above} above, {pend} pending)")

    def pair_crit(name, x, y, need, n_bases=BASES, sense="fewer", strict=True):
        per, detail = {}, {}
        for b in n_bases:
            rx, ry = arm(b, x), arm(b, y)
            if rx is None or ry is None:
                per[b] = None; detail[b] = None; continue
            c = cmp_counts(rx["V"], ry["V"])
            if sense == "fewer":
                per[b] = "pass" if c < 0 else "fail"
            else:  # "no more"
                per[b] = "pass" if c <= 0 else "fail"
            detail[b] = {x: rx["V"], y: ry["V"], "cmp": c}
        verdict = tally(per, need, n_total=len(n_bases))
        ok = sum(1 for v in per.values() if v == "pass")
        pend = sum(1 for v in per.values() if v is None)
        out[name] = {"verdict": verdict, "pass": ok, "pending": pend, "per_base": detail}
        print(f"  {name} {x} {sense} violators than {y} (need {need} of {len(n_bases)}): {verdict} ({ok} pass, {pend} pending)")

    def hold_crit(name, x, y, need_higher, max_lower):
        detail, higher, lower, pend = {}, 0, 0, 0
        for b in BASES:
            rx, ry = arm(b, x), arm(b, y)
            if rx is None or ry is None or rx["hold"] is None or ry["hold"] is None:
                pend += 1; detail[b] = None; continue
            d = rx["hold"] - ry["hold"]
            s = "higher" if d > 0.025 else ("lower" if d < -0.025 else "tie")
            higher += s == "higher"; lower += s == "lower"
            detail[b] = {x: round(rx["hold"], 4), y: round(ry["hold"], 4), "status": s}
        if higher >= need_higher and lower + pend <= max_lower:
            verdict = "PASS"
        elif lower > max_lower or higher + pend < need_higher:
            verdict = "FAIL"
        else:
            verdict = "pending"
        out[name] = {"verdict": verdict, "higher": higher, "lower": lower, "pending": pend, "per_base": detail}
        print(f"  {name} {x} worst hold slack vs {y} (need >= {need_higher} higher by > 25 ps, <= {max_lower} lower): {verdict} ({higher} higher, {lower} lower, {pend} pending)")

    def cells_frontier_crit(name, armname, bases, farms, need, max_above, label):
        """Frontier over cells changed (buffers inserted + cells resized) through the stock arms `farms`."""
        per, det = {}, {}
        for b in bases:
            pts = []
            for fa in farms:
                r, c = arm(b, fa), cells(b, fa)
                if r is None or c is None:
                    pts = None
                    break
                pts.append((c, r["V"]))
            r, c = arm(b, armname), cells(b, armname)
            if pts is None or r is None or c is None:
                per[b] = None; det[b] = None; continue
            pts.sort()
            f = F_at(pts, c)
            st = "below" if r["V"] < f - band(r["V"], f) else ("above" if r["V"] > f + band(r["V"], f) else "on")
            per[b] = st
            det[b] = {"status": st, "V": r["V"], "cells": c, "F": round(f, 1), "frontier": pts}
        below = sum(1 for v in per.values() if v == "below"); above = sum(1 for v in per.values() if v == "above")
        pend = sum(1 for v in per.values() if v is None)
        v = "PASS" if (below >= need and above + pend <= max_above) else ("FAIL" if (above > max_above or below + pend < need) else "pending")
        out[name] = {"verdict": v, "below": below, "above": above, "pending": pend, "per_base": det}
        print(f"  {name} {armname} below the {label} frontier over cells changed (need >= {need} below, <= {max_above} above): {v} ({below} below, {above} above, {pend} pending)")

    print("== A19")
    frontier_crit("A19a", "bst500-30-10r")
    frontier_crit("A19b", "thr500-30cr")
    pair_crit("A19c", "thr500-30cr", "rqn-30r", 9)
    pair_crit("A19d", "thr500-30cr", "rnd1-30r", 12)
    # A19e: hold-violating endpoints no more than rcal213-10t on >= 9, and violators no more (band) on >= 9
    per_h, per_v, det = {}, {}, {}
    for b in BASES:
        rx, ry = arm(b, "bst500-30-10rt"), arm(b, "rcal213-10t")
        if rx is None or ry is None:
            per_h[b] = per_v[b] = None; det[b] = None; continue
        hx, hy = rx.get("hold_vio"), ry.get("hold_vio")
        per_h[b] = None if (hx is None or hy is None) else ("pass" if hx <= hy else "fail")
        per_v[b] = "pass" if cmp_counts(rx["V"], ry["V"]) <= 0 else "fail"
        det[b] = {"hold_vio": (hx, hy), "V": (rx["V"], ry["V"])}
    vh, vv = tally(per_h, 9), tally(per_v, 9)
    ve = "PASS" if vh == vv == "PASS" else ("FAIL" if "FAIL" in (vh, vv) else "pending")
    out["A19e"] = {"verdict": ve, "hold_part": vh, "violator_part": vv, "per_base": det}
    print(f"  A19e bst500-30-10rt vs rcal213-10t: hold-violating endpoints no more on >= 9 ({vh}) and violators no more on >= 9 ({vv}): {ve}")
    pair_crit("A19f", "thr500-30crv4", "rcal213-10", 2, n_bases=R1, sense="no more")
    print("  -- exploratory, NOT registered: the A19a/b frontier over cells changed instead of std-cell area")
    cells_frontier_crit("A19a-cells (exploratory)", "bst500-30-10r", BASES, ("rcal213-0", "rcal213-10", "rcal213-20", "rcal213-30"), 9, 2, "calibrated")
    cells_frontier_crit("A19b-cells (exploratory)", "thr500-30cr", BASES, ("rcal213-0", "rcal213-10", "rcal213-20", "rcal213-30"), 9, 2, "calibrated")
    print("== A20")
    hold_crit("A20a", "rcy213-10y", "rcal213-10", 5, 1)
    pair_crit("A20b", "rcy213-10y", "rcal213-10", 12, sense="no more")
    # A20c: control, rcy213-10 equals rcal213-10 (same V, area, hold) on >= 13
    per, det = {}, {}
    for b in BASES:
        rx, ry = arm(b, "rcy213-10"), arm(b, "rcal213-10")
        if rx is None or ry is None:
            per[b] = None; det[b] = None; continue
        same = rx["V"] == ry["V"] and rx["area"] == ry["area"] and rx["hold"] == ry["hold"]
        per[b] = "pass" if same else "fail"; det[b] = {"rcy": rx, "rcal": ry}
    v = tally(per, 13)
    out["A20c"] = {"verdict": v, "per_base": det}
    print(f"  A20c rcy213-10 identical to rcal213-10 (need 13 of 14): {v} ({sum(1 for x in per.values() if x == 'pass')} identical, {sum(1 for x in per.values() if x is None)} pending)")
    print("== A22 (correlated flow; models trained on the other correlated bases)")
    # A22a: frontier over CELLS CHANGED (not area: resizing a delay cell into buf_2 lowers area, so area is not monotone in
    # repair effort), through uni0/10/20/30; below/above with the noise band; >= 7 below and <= 2 above of 12
    cells_frontier_crit("A22a", "bst500-30-10", CF_RESIDUAL, ("uni0", "uni10", "uni20", "uni30"), 4, 1,
                        "correlated stock (6 large-residual bases)")
    cells_frontier_crit("A22a-all", "bst500-30-10", CF_BASES, ("uni0", "uni10", "uni20", "uni30"), 0, 2,
                        "correlated stock (all 12; no-harm part: above on <= 2)")
    va = out["A22a"]["verdict"]; vb = out["A22a-all"]["verdict"]
    out["A22a"]["verdict_combined"] = "PASS" if va == vb == "PASS" else ("FAIL" if "FAIL" in (va, vb) else "pending")
    print(f"  A22a combined (large-residual part AND no-harm part): {out['A22a']['verdict_combined']}")
    # reported without criterion: the same over std-cell area
    frontier_crit("A22a-area (no criterion)", "bst500-30-10", bases=CF_BASES, need=7, max_above=2,
                  farms=("uni0", "uni10", "uni20", "uni30"), ref=None, what="correlated stock (area)")
    pair_crit("A22b", "thr500-30c", "rqc-30", 4, n_bases=CF_RESIDUAL)
    # A22c: thr500-30c changes fewer cells than uni30 on >= 10 AND leaves no more violators (band) on >= 7
    per_c, per_v, det = {}, {}, {}
    for b in CF_BASES:
        rx, ry = arm(b, "thr500-30c"), arm(b, "uni30")
        cx, cy = cells(b, "thr500-30c"), cells(b, "uni30")
        if rx is None or ry is None or cx is None or cy is None:
            per_c[b] = per_v[b] = None; det[b] = None; continue
        per_c[b] = "pass" if cx < cy else "fail"
        per_v[b] = "pass" if cmp_counts(rx["V"], ry["V"]) <= 0 else "fail"
        det[b] = {"cells": (cx, cy), "V": (rx["V"], ry["V"])}
    vc, vv = tally(per_c, 10, n_total=len(CF_BASES)), tally(per_v, 7, n_total=len(CF_BASES))
    vcc = "PASS" if vc == vv == "PASS" else ("FAIL" if "FAIL" in (vc, vv) else "pending")
    out["A22c"] = {"verdict": vcc, "cells_part": vc, "violator_part": vv, "per_base": det}
    print(f"  A22c thr500-30c vs uni30: fewer cells on >= 10 of 12 ({vc}) and violators no more on >= 7 of 12 ({vv}): {vcc}")
    print("== A23 (conventional-boost controls: the estimate's own list boosted, same two-tier step)")
    pair_crit("A23a", "bst500-30-10rt", "bqn-30-10rt", 9)
    # A23b: A19e's rule applied to the control bqn-30-10rt vs rcal213-10t
    per_h, per_v, det = {}, {}, {}
    for b in BASES:
        rx, ry = arm(b, "bqn-30-10rt"), arm(b, "rcal213-10t")
        if rx is None or ry is None:
            per_h[b] = per_v[b] = None; det[b] = None; continue
        hx, hy = rx.get("hold_vio"), ry.get("hold_vio")
        per_h[b] = None if (hx is None or hy is None) else ("pass" if hx <= hy else "fail")
        per_v[b] = "pass" if cmp_counts(rx["V"], ry["V"]) <= 0 else "fail"
        det[b] = {"hold_vio": (hx, hy), "V": (rx["V"], ry["V"])}
    vh, vv = tally(per_h, 9), tally(per_v, 9)
    vb = "PASS" if vh == vv == "PASS" else ("FAIL" if "FAIL" in (vh, vv) else "pending")
    out["A23b"] = {"verdict": vb, "hold_part": vh, "violator_part": vv, "per_base": det}
    print(f"  A23b bqn-30-10rt vs rcal213-10t: hold-violating endpoints no more on >= 9 ({vh}) and violators no more on >= 9 ({vv}): {vb}")
    pair_crit("A23c", "bst500-30-10", "bqc-30-10", 4, n_bases=CF_RESIDUAL)
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1, default=str)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
