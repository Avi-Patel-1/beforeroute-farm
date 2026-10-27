#!/usr/bin/env python3
"""Where the hold goes: count hold-fix delay cells that a repair turned into plain buffers, per base and arm.

Compares instance masters between the base's final netlist (no post-GRT repair) and each arm's final netlist by
instance name (the resizer keeps names when it resizes). Reports, per arm: delay cells (clkdlybuf4s*, dlygate*,
dlymetal*) in the base; how many were resized into buffers (buf_*/clkbuf_*), into other delay cells, or left alone;
and the arm's worst hold slack change against the re-run. Usage: hold_swaps.py [--arms ...] [--json out]
"""
from __future__ import annotations

import argparse
import collections
import gzip
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import paper_table as PT  # noqa: E402

INST_RE = re.compile(r"^\s*(sky130_fd_sc_hd__\w+)\s+(\S+)\s*\(", re.M)
DELAY = re.compile(r"sky130_fd_sc_hd__(clkdlybuf4s\d+|dlygate4sd\d|dlymetal6s\ds)_\d+$")
BUF = re.compile(r"sky130_fd_sc_hd__(buf|clkbuf)_\d+$")


def masters(path):
    if not os.path.exists(path):
        return None
    txt = (gzip.open if path.endswith(".gz") else open)(path, "rt").read()
    return {m.group(2).lstrip("\\"): m.group(1) for m in INST_RE.finditer(txt)}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--arms", nargs="*", default=["uni70", "rcal213-10", "thr500-30cr"])
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    out = {}
    for g, bases in PT.BASES.items():
        for b in bases:
            base = masters(os.path.join(PT.RESULTS, b, "final.nl.v.gz")) or masters(os.path.join(PT.RESULTS, f"{b}-rerun", "final.nl.v.gz"))
            if base is None:
                continue
            dly = {k: v for k, v in base.items() if DELAY.match(v)}
            rows = {r["arm"]: r for r in PT.table([b], ["rerun"] + a.arms)}
            h0 = (rows.get("rerun") or {}).get("hold_ws")
            out[b] = {"delay_cells": len(dly), "arms": {}}
            for arm in a.arms:
                m = masters(os.path.join(PT.RESULTS, f"{b}-{arm}", "final.nl.v.gz"))
                if m is None:
                    continue
                c = collections.Counter()
                for k, v in dly.items():
                    w = m.get(k)
                    if w is None:
                        c["removed"] += 1
                    elif w == v:
                        c["kept"] += 1
                    elif BUF.match(w):
                        c["to_buffer"] += 1
                    elif DELAY.match(w):
                        c["to_delay"] += 1
                    else:
                        c["to_other"] += 1
                h = (rows.get(arm) or {}).get("hold_ws")
                out[b]["arms"][arm] = dict(c, hold_ws=h, d_hold_ps=(None if h is None or h0 is None else round(1000 * (h - h0), 1)))
            s = " | ".join(f"{arm}: →buf {v.get('to_buffer', 0)}, Δhold {v.get('d_hold_ps')} ps" for arm, v in out[b]["arms"].items())
            print(f"{PT.NAMES[b]:13s} delay cells {len(dly):5d} | {s}")
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
