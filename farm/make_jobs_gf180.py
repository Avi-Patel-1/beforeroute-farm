#!/usr/bin/env python3
"""Generate GF180MCU data-generation job specs (farm/jobs/<tag>.json) for the PDK-transfer test.

Usage: make_jobs_gf180.py [--prefix g1]

Same knob families as the sky130 d1/d2 sweeps, rescaled to GF180MCU (7-track 5V cells):
  FP_CORE_UTIL 25..35, PL_TARGET_DENSITY_PCT 35..50, CLOCK_PERIOD x{0.8,1.0,1.3} of the
  design's gf180 base period (~2.8x its sky130 period), MAX_TRANSITION_CONSTRAINT
  {2,3,4} ns (the PDK default is 3 ns; sky130 sweeps used {0.5,0.75,1.0} around 0.75 ns).
  RUN_POST_GRT_DESIGN_REPAIR false (training rows describe the baseline flow's blind spot);
  signoff-only checkers off (streamouts and WriteLEF stay on).
Writes <prefix>.tags.json (sweep minus the baseline) and <prefix>-base.tags.json (baseline only),
plus g0-spm-smoke (a tiny pipeline smoke test).
"""
from __future__ import annotations

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.join(HERE, "jobs")

DESIGNS = {  # gf180 base period (ns) in each design's config_gf180.json
    "picorv32": 70.0,
    "aes_cipher": 112.0,
    "ocs_blitter": 51.0,
}
# (util, density, period factor, max transition ns); index 0 = the design's base config
KNOBS = [
    (30, 40, 1.0, 3.0),
    (35, 40, 0.8, 2.0),
    (25, 35, 1.3, 4.0),
    (30, 45, 1.3, 2.0),
    (35, 50, 1.0, 4.0),
]
DATA_OVERRIDES = {
    "RUN_POST_GRT_DESIGN_REPAIR": False,
    "RUN_MAGIC_DRC": False, "RUN_KLAYOUT_DRC": False, "RUN_LVS": False, "RUN_KLAYOUT_XOR": False,
    "RUN_IRDROP_REPORT": False, "RUN_LINTER": False,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prefix", default="g1")
    a = ap.parse_args()
    os.makedirs(JOBS, exist_ok=True)
    per_design = {}
    for dname, period in DESIGNS.items():
        for i, (util, dens, pf, mt) in enumerate(KNOBS):
            tag = f"{a.prefix}-{dname}-{i:03d}"
            ov = {
                "FP_CORE_UTIL": util,
                "PL_TARGET_DENSITY_PCT": dens,
                "CLOCK_PERIOD": round(period * pf, 3),
                "MAX_TRANSITION_CONSTRAINT": mt,
            }
            ov.update(DATA_OVERRIDES)
            spec = {"tag": tag, "design": f"designs/{dname}", "config": "config_gf180.json", "overrides": ov}
            json.dump(spec, open(os.path.join(JOBS, tag + ".json"), "w"), indent=1)
            per_design.setdefault(dname, []).append(tag)
    base = [f"{a.prefix}-picorv32-000"]
    # sweep order (the shared runner queue is FIFO-ish, so order = start order): every design gets
    # runs early; picorv32 variants trail its baseline (dispatched first, in its own run)
    o, s, p = per_design["ocs_blitter"], per_design["aes_cipher"], per_design["picorv32"]
    sweep = [o[0], s[0], o[1], s[1], o[2], s[2], p[1], o[3], s[3], p[2], o[4], s[4], p[3], p[4]]
    json.dump(base, open(os.path.join(JOBS, f"{a.prefix}-base.tags.json"), "w"))
    json.dump(sweep, open(os.path.join(JOBS, f"{a.prefix}.tags.json"), "w"))
    smoke = {"tag": "g0-spm-smoke", "design": "designs/spm", "config": "config_gf180.json", "overrides": dict(DATA_OVERRIDES)}
    json.dump(smoke, open(os.path.join(JOBS, "g0-spm-smoke.json"), "w"), indent=1)
    json.dump(["g0-spm-smoke"] + base, open(os.path.join(JOBS, "g0-smoke-base.tags.json"), "w"))
    print(f"baseline {base}; sweep {len(sweep)} jobs -> farm/jobs/{a.prefix}.tags.json; smoke g0-spm-smoke")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
