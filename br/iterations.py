#!/usr/bin/env python3
"""Iterations-to-closure table (Addendum 2): signoff-guided loop vs BeforeRoute + cleanup, per base.

Usage: iterations.py [--bases b1,b2,...] [--results results] [--json out.json]
Loop:        pass 0 = baseline signoff (rerun arm as reference), pass k = lst-sgl<k>-70.
BeforeRoute: pass 1 = seed arm (tgt050-70, or tgt050-70c on Round-5 bases), pass k+1 = lst-cln<k>-70.
Signal slew/cap violators only (fanout residuals are antenna-diode loads, reported separately and not
counted, per Addendum 2). A chain is "stalled" when advance.py found no new net to add (the next pass would
repeat the previous one exactly) and "closed" at 0. Cells = cells changed by that pass's repair (each pass
repairs its whole cumulative list from the same checkpoint, so cells are per pass, not summed).
"""
from __future__ import annotations

import argparse
import json
import os

DEFAULT = ("d3-salsa20-000,d3-des-000,d3-y_huff-000,d3-ocs_blitter-000,d3-bm64-000,d3-md5-000,d3b-sha512-000,"
           "d3b-ldpcenc-000,d1-picorv32-006,d1-picorv32-016,d1-aes_cipher-000,d5-chacha-000,d5-point_add-000,d5-blabla-000")


def sv(results, tag):
    """signal slew/cap violators (fanout-only excluded), cells changed, hold ws; None if not landed."""
    p = os.path.join(results, tag, "labels.json")
    if not os.path.exists(p):
        return None
    lab = json.load(open(p))
    n = sum(1 for r in lab["nets"] if r.get("violated") and r.get("sigtype_s") == "SIGNAL" and (r.get("viol_slew") or r.get("viol_cap")))
    cells = None
    hs = os.path.join(results, tag, "repair_step.log")
    try:
        from run_hero import arm_summary  # noqa: E402
        s = arm_summary(results, tag)
        if s.get("resized") is not None or s.get("buffers") is not None:
            cells = (s.get("resized") or 0) + (s.get("buffers") or 0)
        hold = s.get("hold_ws")
    except Exception:
        hold = None
    return {"V": n, "cells": cells, "hold": hold}


def main() -> int:
    import sys
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", default=DEFAULT)
    ap.add_argument("--results", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    R = a.results
    state = open(os.path.join(R, ".advance_dispatched")).read() if os.path.exists(os.path.join(R, ".advance_dispatched")) else ""
    out = []
    for b in a.bases.split(","):
        ref = sv(R, f"{b}-rerun") or sv(R, b)
        if ref is None:
            continue
        loop = [dict(pass_=0, arm="baseline", **ref)]
        for k in range(1, 6):
            r = sv(R, f"{b}-lst-sgl{k}-70")
            if r is None:
                st = "stalled" if f"{b} lst-sgl{k}-70 STALLED" in state else ("pending" if f"{b} lst-sgl{k}-70" in state or k == 1 else "not dispatched")
                if st == "stalled":  # Addendum 8: one escalation pass
                    e = sv(R, f"{b}-lsx-sgl{k}x")
                    loop.append(dict(pass_=k, arm=f"esc{k}", **e) if e else dict(pass_=k, arm=f"esc{k}", status="pending" if f"{b} lsx-sgl{k}x" in state else "stalled"))
                else:
                    loop.append(dict(pass_=k, arm=f"sgl{k}", status=st))
                break
            loop.append(dict(pass_=k, arm=f"sgl{k}", **r))
            if r["V"] == 0:
                break
        seed = "tgt050-70c" if b.startswith("d5-") else "tgt050-70"
        br = []
        r = sv(R, f"{b}-{seed}")
        if r is None:
            br.append(dict(pass_=1, arm=seed, status="pending"))
        else:
            br.append(dict(pass_=1, arm=seed, **r))
            if r["V"] > 0:
                for k in range(1, 5):
                    r2 = sv(R, f"{b}-lst-cln{k}-70")
                    if r2 is None:
                        st = "stalled" if f"{b} lst-cln{k}-70 STALLED" in state else ("pending" if f"{b} lst-cln{k}-70" in state else "not dispatched")
                        if st == "stalled":  # Addendum 8: one escalation pass
                            e = sv(R, f"{b}-lsx-cln{k}x")
                            br.append(dict(pass_=k + 1, arm=f"esc{k}", **e) if e else dict(pass_=k + 1, arm=f"esc{k}", status="pending" if f"{b} lsx-cln{k}x" in state else "stalled"))
                        else:
                            br.append(dict(pass_=k + 1, arm=f"cln{k}", status=st))
                        break
                    br.append(dict(pass_=k + 1, arm=f"cln{k}", **r2))
                    if r2["V"] == 0:
                        break
        out.append({"base": b, "loop": loop, "beforeroute": br})

    def fmt(seq):
        parts = []
        for p in seq:
            if "V" in p:
                parts.append(f"{p['arm']}:{p['V']}" + (f"({p['cells']}c)" if p.get("cells") is not None else ""))
            else:
                parts.append(f"{p['arm']}:{p['status']}")
        return " → ".join(parts)

    for o in out:
        print(f"{o['base']}")
        print(f"   loop        (passes incl. baseline signoff): {fmt(o['loop'])}")
        print(f"   BeforeRoute (passes)                       : {fmt(o['beforeroute'])}")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
