#!/usr/bin/env python3
"""Per-base, per-arm outcome table for the paper, the site and the frontier analysis.

For each base and arm: signal violators V (max-slew or max-cap at any of the nine signoff corners, signal nets; the same
definition as br/criteria.py), cells changed (buffers inserted + cells resized, from the arm's summary), std-cell area and
its change against the base re-run, worst hold / setup slack, hold / setup violating endpoints, and runtime.
Usage: paper_table.py [--bases ...] [--arms ...] [--json out.json] [--csv out.csv]
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS = os.path.join(ROOT, "results")

BASES = {
    "Round 3": ["d3-bm64-000", "d3-des-000", "d3-md5-000", "d3-ocs_blitter-000", "d3-salsa20-000", "d3-y_huff-000"],
    "Round 4-5 (Addendum 15)": ["d3b-ldpcenc-000", "d3b-sha512-000", "d5-blabla-000", "d5-chacha-000", "d5-point_add-000"],
    "Round 1 (Addendum 17)": ["d1-picorv32-006", "d1-picorv32-016", "d1-aes_cipher-000"],
}
NAMES = {"d3-bm64-000": "BM64", "d3-des-000": "DES", "d3-md5-000": "MD5", "d3-ocs_blitter-000": "ocs_blitter",
         "d3-salsa20-000": "salsa20", "d3-y_huff-000": "y_huff", "d3b-ldpcenc-000": "LDPC", "d3b-sha512-000": "SHA-512",
         "d5-blabla-000": "BlaBla", "d5-chacha-000": "ChaCha", "d5-point_add-000": "point_add",
         "d1-picorv32-006": "PicoRV32-006", "d1-picorv32-016": "PicoRV32-016", "d1-aes_cipher-000": "AES"}
DEFAULT_ARMS = ["rerun", "uni70", "rcal213-0", "rcal213-10", "rcal213-20", "rcal213-30", "thr500-30cr", "bst500-30-10r",
                "rqn-30r", "rqt900-30r", "rnd1-30r", "rcalorfs-10", "rcalorfs-30", "thr500-30co"]


def violators(tag):
    p = os.path.join(RESULTS, tag, "labels.json")
    if not os.path.exists(p):
        return None
    lab = json.load(open(p))
    return sum(1 for r in lab["nets"] if r.get("violated") and r.get("sigtype_s") == "SIGNAL" and (r.get("viol_slew") or r.get("viol_cap")))


def summary_rows(base):
    p = os.path.join(RESULTS, base, "hero_summary.json")
    if not os.path.exists(p):
        return {}
    return {r["tag"]: r for r in json.load(open(p))["arms"]}


def table(bases, arms):
    out = []
    for group, bs in BASES.items():
        for b in bs:
            if bases and b not in bases:
                continue
            rows = summary_rows(b)
            base_area = (rows.get(f"{b}-rerun") or rows.get(b) or {}).get("stdcell_area")
            for arm in arms:
                tag = f"{b}-{arm}"
                r = rows.get(tag)
                job = os.path.join(RESULTS, tag, "job.json")
                status = json.load(open(job)).get("status") if os.path.exists(job) else None
                V = violators(tag)
                if r is None and V is None:
                    continue
                r = r or {}
                cells = None if r.get("buffers") is None else (r.get("buffers") or 0) + (r.get("resized") or 0)
                area = r.get("stdcell_area")
                out.append({"group": group, "base": b, "design": NAMES[b], "arm": arm, "status": status, "V": V,
                            "cells": cells, "buffers": r.get("buffers"), "resized": r.get("resized"),
                            "area": area, "dA_pct": (100.0 * (area - base_area) / base_area) if (area and base_area) else None,
                            "hold_ws": r.get("hold_ws"), "hold_vio": r.get("hold_vio"), "setup_ws": r.get("setup_ws"),
                            "setup_vio": r.get("setup_vio"), "flow_seconds": r.get("flow_seconds")})
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", nargs="*", default=None)
    ap.add_argument("--arms", nargs="*", default=DEFAULT_ARMS)
    ap.add_argument("--json", default=None)
    ap.add_argument("--csv", default=None)
    a = ap.parse_args()
    rows = table(a.bases, a.arms)
    if a.json:
        json.dump(rows, open(a.json, "w"), indent=1)
    if a.csv and rows:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    for r in rows:
        dA = f"{r['dA_pct']:+.2f}%" if r["dA_pct"] is not None else "  -  "
        hw = f"{r['hold_ws']:+.3f}" if r["hold_ws"] is not None else "-"
        print(f"{r['design']:13s} {r['arm']:14s} V={str(r['V']):>5s} cells={str(r['cells']):>6s} dA={dA:>8s} hold={hw:>7s} {r['status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
