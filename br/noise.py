#!/usr/bin/env python3
"""Noise across re-placed copies (Addendum 19, descriptive): for each design with re-placed bases
<round>j1-<d>-<n> and <round>j2-<d>-<n> (placement density -1 / +1 point), signal violators V of the base itself and of
each arm on the original and both copies; the spread of V across the three checkpoints; and the paired difference
(policy - reference) on each checkpoint, against the 0.45*sqrt(max) band used by every criterion.
Usage: noise.py [--arms rcal213-10 thr500-30cr bst500-30-10r] [--ref rcal213-10] [--json out]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paper_table as PT  # noqa: E402

DESIGNS = ["d3b-ldpcenc-000", "d3b-sha512-000", "d5-blabla-000", "d5-chacha-000", "d5-point_add-000",
           "d1-picorv32-006", "d1-picorv32-016", "d1-aes_cipher-000"]


def copies(base):
    fam, rest = base.split("-", 1)
    return [base, f"{fam}j1-{rest}", f"{fam}j2-{rest}"]


def V(tag):
    return PT.violators(tag)


def identical(a, b):
    """A copy whose std-cell area and routed wirelength equal the original's is the same placement (the placer replaces
    a density target below its minimum with that minimum, so a +-1 point change can be a no-op)."""
    try:
        ma = json.load(open(os.path.join(PT.RESULTS, a, "metrics.json")))
        mb = json.load(open(os.path.join(PT.RESULTS, b, "metrics.json")))
    except Exception:
        return False
    keys = ("design__instance__area__stdcell", "route__wirelength")
    return all(ma.get(k) is not None and ma.get(k) == mb.get(k) for k in keys)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="*", default=["rcal213-10", "thr500-30cr", "bst500-30-10r"])
    ap.add_argument("--ref", default="rcal213-10")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    out = {}
    for base in DESIGNS:
        cs = copies(base)
        same = [c for c in cs[1:] if identical(base, c)]
        cs = [c for c in cs if c not in same]
        row = {"base": [V(c) for c in cs], "identical_copies": same}
        for arm in a.arms:
            row[arm] = [V(f"{c}-{arm}") if c != base or arm != "rerun" else V(f"{base}-rerun") for c in cs]
        out[base] = row
        name = PT.NAMES.get(base, base)
        parts = [f"no repair {row['base']}" + (f" (identical copies dropped: {same})" if same else "")]
        for arm in a.arms:
            vs = row[arm]
            got = [v for v in vs if v is not None]
            spread = (max(got) - min(got)) if len(got) > 1 else None
            band = 0.45 * math.sqrt(max(got + [1])) if got else None
            parts.append(f"{arm} {vs} spread {spread} (band {band:.1f})" if band is not None else f"{arm} {vs}")
        for arm in a.arms:
            if arm == a.ref:
                continue
            d = [(x - y) if (x is not None and y is not None) else None for x, y in zip(row[arm], row[a.ref])]
            parts.append(f"{arm}-{a.ref} {d}")
        print(f"{name:13s} " + " | ".join(parts))
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
