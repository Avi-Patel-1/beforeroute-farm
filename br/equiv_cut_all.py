#!/usr/bin/env python3
"""Run br/equiv_cut.py on every collected repaired netlist, one job at a time (idempotent).

For each results/<base>-<arm>/final.nl.v.gz with a gold netlist (results/<base>/final.nl.v.gz, else
results/<base>-rerun/final.nl.v.gz), writes results-equiv-cut/<base>-<arm>/result.json unless it already exists.
Headline arms run first. With --controls, also one negative control per base (the first arm checked for that base;
out dir <tag>-negctrl), which must return COUNTEREXAMPLE.
Usage: equiv_cut_all.py [--yosys BIN] [--only REGEX] [--controls] [--max N] [--min-free-mb 2500] [--dry-run]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
LIB = "pdk/sky130A/libs.ref/sky130_fd_sc_hd/lib/sky130_fd_sc_hd__tt_025C_1v80.lib"
TAG = re.compile(r"^((?:d\d+[a-z0-9]*|nv1)-[a-z0-9_]+-\d{3})-(.+)$")
SKIP_ARMS = {"rerun", "seed", "dmp"}
FIRST = ["thr500-30cr", "rcal213-10", "uni70", "bst500-30-10r", "rcal213-30", "rcal213-20", "rcy213-10y", "rcy213-10",
         "thr500-30cry", "bst500-30-10ry", "uni10", "uni30"]


def mem_free_mb():
    for line in open("/proc/meminfo"):
        if line.startswith("MemAvailable:"):
            return int(line.split()[1]) // 1024
    return 0


def jobs(only):
    out = []
    for g in sorted(glob.glob(os.path.join(ROOT, "results", "*", "final.nl.v.gz"))):
        tag = os.path.basename(os.path.dirname(g))
        m = TAG.match(tag)
        if not m or m.group(2) in SKIP_ARMS:
            continue
        base, arm = m.group(1), m.group(2)
        gold = next((p for p in (os.path.join(ROOT, "results", base, "final.nl.v.gz"),
                                 os.path.join(ROOT, "results", f"{base}-rerun", "final.nl.v.gz")) if os.path.exists(p)), None)
        res = os.path.join(ROOT, "results", base, "resolved.json")
        if not gold or not os.path.exists(res):
            continue
        if only and not re.search(only, tag):
            continue
        prio = FIRST.index(arm) if arm in FIRST else len(FIRST)
        out.append((prio, tag, base, arm, gold, g, json.load(open(res))["DESIGN_NAME"]))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--yosys", default=os.environ.get("YOSYS", "yosys"))
    ap.add_argument("--only", default=None)
    ap.add_argument("--controls", action="store_true")
    ap.add_argument("--max", type=int, default=0)
    ap.add_argument("--min-free-mb", type=int, default=2500)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    outroot = os.path.join(ROOT, "results-equiv-cut")
    os.makedirs(outroot, exist_ok=True)
    done_bases, n = set(), 0
    for prio, tag, base, arm, gold, gate, top in jobs(a.only):
        todo = [(tag, [])]
        if a.controls and base not in done_bases:
            todo.append((f"{tag}-negctrl", ["--negative-control"]))
            done_bases.add(base)
        for name, extra in todo:
            if os.path.exists(os.path.join(outroot, name, "result.json")):
                continue
            if a.max and n >= a.max:
                return 0
            cmd = [sys.executable, os.path.join(ROOT, "br", "equiv_cut.py"), "--gold", gold, "--gate", gate, "--top", top,
                   "--liberty", os.path.join(ROOT, LIB), "--out", os.path.join(outroot, name), "--timeout", str(a.timeout),
                   "--yosys", a.yosys] + extra
            if a.dry_run:
                print(" ".join(cmd))
                n += 1
                continue
            while mem_free_mb() < a.min_free_mb:
                print(f"[cut] waiting for memory ({mem_free_mb()} MB free)", flush=True)
                time.sleep(60)
            t0 = time.time()
            p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
            try:
                r = json.load(open(os.path.join(outroot, name, "result.json")))
                st = r.get("status")
            except Exception:
                st = f"no result (rc {p.returncode})"
            print(f"[cut] {name}: {st} {time.time() - t0:.0f}s", flush=True)
            n += 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
