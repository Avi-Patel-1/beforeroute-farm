#!/usr/bin/env python3
"""Experiment E (Addendum 42): write the 35 rebuild-chain job specs (farm/jobs/erk-<design>-<nn>.json) and
farm/qa/E/chains.json from the captured source runs. Writing them dispatches nothing; phase2.py dispatch does, after
the predictions are locked.

Each chain spec = the source's spec (same design, config, overrides) with tag erk-..., no capture, and
"chain": {source_tag, T0, C0 (the capture run's own claim), source_pass (judge on the capture run), drv_bar,
max_rebuilds 4}. br/run_job.py runs the registered chain on the runner (run_chain).
"""
from __future__ import annotations

import argparse
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.abspath(os.path.join(HERE, "..", "..", "jobs"))


def drv(m):
    return (m.get("design__max_slew_violation__count") or 0) + (m.get("design__max_cap_violation__count") or 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    a = ap.parse_args()
    src = json.load(open(os.path.join(HERE, "sources.json")))["sources"]
    chains = []
    for s in src:
        m = json.load(open(os.path.join(a.results, s["source"], "metrics.json")))
        T0 = float(s["T0"])
        ws, hold = m["timing__setup__ws"], m.get("timing__hold__ws")
        C0 = T0 - ws
        sp = ws >= 0 and hold is not None and hold >= 0 and (m.get("route__drc_errors") or 0) == 0 \
            and drv(m) <= s["stock_drv_bar"]
        spec = json.load(open(os.path.join(JOBS, s["source"] + ".json")))
        tag = s["source"].replace("ers-", "erk-", 1)
        out = {"tag": tag, "design": spec["design"], "config": spec["config"], "overrides": spec["overrides"],
               "chain": {"source_tag": s["source"], "T0": T0, "C0": C0, "source_pass": bool(sp),
                         "drv_bar": s["stock_drv_bar"], "max_rebuilds": 4}}
        json.dump(out, open(os.path.join(JOBS, tag + ".json"), "w"), indent=1)
        chains.append({"source": s["source"], "tag": tag, "T0": T0, "C0": C0, "R1": None, "source_pass": bool(sp),
                       "replay_ws_equal_record": abs(ws - s["ws0_record"]) < 1e-9})
        import math
        chains[-1]["R1"] = round(math.ceil(round(C0 / 0.05, 6)) * 0.05, 2)
    json.dump({"about": "Addendum 42 chain jobs (dispatched only after the lock commit)", "chains": chains},
              open(os.path.join(HERE, "chains.json"), "w"), indent=1)
    print(f"[chains] {len(chains)} chain specs; replays equal to record: "
          f"{sum(c['replay_ws_equal_record'] for c in chains)}/{len(chains)}; sources passing: "
          f"{sum(c['source_pass'] for c in chains)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
