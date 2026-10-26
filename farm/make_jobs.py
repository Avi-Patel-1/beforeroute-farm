#!/usr/bin/env python3
"""Generate BeforeRoute data-generation job specs (farm/jobs/<tag>.json).

Usage: make_jobs.py [--per-design 35] [--seed 7] [--prefix d1]

Knobs (sampled, base config always included):
  FP_CORE_UTIL 35..65, PL_TARGET_DENSITY_PCT = util+5 (+/-10), CLOCK_PERIOD x{0.8,1.0,1.3},
  MAX_TRANSITION_CONSTRAINT {0.5,0.75,1.0} ns, EXTRA_EXCLUDED_CELLS {none, clkdlybuf},
  RUN_POST_GRT_DESIGN_REPAIR false (training rows describe the baseline flow's blind spot).
"""
from __future__ import annotations

import argparse
import itertools
import json
import os
import random

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.join(HERE, "jobs")

DESIGNS = {
    "picorv32": {"config": "config_sky130.json", "period": 25.0, "util": 35, "density": 45},
    "aes_cipher": {"config": "config_sky130.json", "period": 40.0, "util": 35, "density": 45},
    "crc_pipe": {"config": "config.yaml", "period": 10.0, "util": 45, "density": None},
    "spm": {"config": "config.yaml", "period": 10.0, "util": 45, "density": None},
}
CLKDLY = ["sky130_fd_sc_hd__clkdlybuf4s25_1"]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-design", type=int, default=35)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--prefix", default="d1")
    ap.add_argument("--designs", default=None, help="comma list of design dirs to use instead of DESIGNS (config_sky130.json, period from config)")
    ap.add_argument("--utils", default="35,40,45,50,55")
    ap.add_argument("--skip-base", action="store_true", help="do not include the base/base-noclkdly picks (already run as another sweep)")
    a = ap.parse_args()
    designs = DESIGNS
    if a.designs:
        designs = {}
        for dname in a.designs.split(","):
            cfg = json.load(open(os.path.join(HERE, "..", "designs", dname, "config_sky130.json")))
            designs[dname] = {"config": "config_sky130.json", "period": float(cfg["CLOCK_PERIOD"]), "util": int(cfg.get("FP_CORE_UTIL", 35)), "density": cfg.get("PL_TARGET_DENSITY_PCT")}
    utils = [int(u) for u in a.utils.split(",")]
    rng = random.Random(a.seed)
    os.makedirs(JOBS, exist_ok=True)
    tags = []
    for dname, d in designs.items():
        space = list(
            itertools.product(
                utils,  # util (65 does not route on the big designs)
                [-10, 0, 10, 20],  # density delta (capped at 70 below)
                [0.8, 1.0, 1.3],  # period factor
                [0.5, 0.75, 1.0],  # max transition ns
                [0, 1],  # exclude clkdlybuf
            )
        )
        rng.shuffle(space)
        picks = [] if a.skip_base else [(d["util"], 0, 1.0, 0.75, 0), (d["util"], 0, 1.0, 0.75, 1)]  # base + base-noclkdly
        base_like = {(d["util"], 0, 1.0, 0.75, 0)}
        picks += [p for p in space if p not in picks and p not in base_like][: max(0, a.per_design - len(picks))]
        for i, (util, dd, pf, mt, ex) in enumerate(picks):
            tag = f"{a.prefix}-{dname}-{i:03d}"
            ov = {
                "FP_CORE_UTIL": util,
                "PL_TARGET_DENSITY_PCT": max(20, min(70, util + 5 + dd)),
                "CLOCK_PERIOD": round(d["period"] * pf, 3),
                "MAX_TRANSITION_CONSTRAINT": mt,
                "RUN_POST_GRT_DESIGN_REPAIR": False,
                # signoff-only steps are not needed for slew/cap/fanout labels (21% of runtime)
                # (streamouts and WriteLEF stay on: ungated later steps need their GDS/LEF)
                "RUN_MAGIC_DRC": False, "RUN_KLAYOUT_DRC": False, "RUN_LVS": False, "RUN_KLAYOUT_XOR": False,
                "RUN_IRDROP_REPORT": False, "RUN_LINTER": False,
            }
            if ex:
                ov["EXTRA_EXCLUDED_CELLS"] = CLKDLY
            spec = {"tag": tag, "design": f"designs/{dname}", "config": d["config"], "overrides": ov}
            json.dump(spec, open(os.path.join(JOBS, tag + ".json"), "w"), indent=1)
            tags.append(tag)
    json.dump(tags, open(os.path.join(JOBS, f"{a.prefix}.tags.json"), "w"))
    print(f"wrote {len(tags)} job specs; tag list: farm/jobs/{a.prefix}.tags.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
