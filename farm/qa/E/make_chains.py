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
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
JOBS = os.path.abspath(os.path.join(HERE, "..", "..", "jobs"))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..", "..", "br")))
from run_job import e_judge  # noqa: E402  (the runner-side chain's own judge: one definition, fail-closed)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--sources", default=os.path.join(HERE, "sources.json"))
    ap.add_argument("--jobs-dir", default=JOBS)
    ap.add_argument("--chains-out", default=os.path.join(HERE, "chains.json"))
    a = ap.parse_args()
    src = json.load(open(a.sources))["sources"]
    # Fail-closed admission (pre-registration clarification 12): every source run must be complete (job record with
    # flow_completed, final metrics with every judge field finite, a numeric electrical bar) before it can define C0/R1
    # or count as a passing clock. All sources are checked first; if any is incomplete NOTHING is written (before this
    # fix a missing DRC or slew/cap count defaulted to a passing 0).
    rows, bad = [], []
    for s in src:
        try:
            job = json.load(open(os.path.join(a.results, s["source"], "job.json")))
            m = json.load(open(os.path.join(a.results, s["source"], "metrics.json")))
        except Exception as e:
            bad.append(f"{s['source']}: {type(e).__name__}: {e}")
            continue
        sp, missing, _ = e_judge(m, s.get("stock_drv_bar"))
        if missing or job.get("flow_completed") is not True:
            bad.append(f"{s['source']}: incomplete source run (missing {missing}, flow_completed {job.get('flow_completed')})")
            continue
        rows.append((s, m, sp))
    if bad:
        for b in bad:
            print("[chains] NOT ADMITTED:", b)
        print(f"[chains] {len(bad)} incomplete source(s): nothing written")
        return 1
    chains = []
    for s, m, sp in rows:
        T0 = float(s["T0"])
        ws = float(m["timing__setup__ws"])
        C0 = T0 - ws
        spec = json.load(open(os.path.join(a.jobs_dir, s["source"] + ".json")))
        tag = s["source"].replace("ers-", "erk-", 1)
        out = {"tag": tag, "design": spec["design"], "config": spec["config"], "overrides": spec["overrides"],
               "chain": {"source_tag": s["source"], "T0": T0, "C0": C0, "source_pass": bool(sp),
                         "drv_bar": s["stock_drv_bar"], "max_rebuilds": 4}}
        json.dump(out, open(os.path.join(a.jobs_dir, tag + ".json"), "w"), indent=1)
        chains.append({"source": s["source"], "tag": tag, "T0": T0, "C0": C0, "R1": None, "source_pass": bool(sp),
                       "replay_ws_equal_record": abs(ws - s["ws0_record"]) < 1e-9})
        chains[-1]["R1"] = round(math.ceil(round(C0 / 0.05, 6)) * 0.05, 2)
    json.dump({"about": "Addendum 42 chain jobs (dispatched only after the lock commit)", "chains": chains},
              open(a.chains_out, "w"), indent=1)
    print(f"[chains] {len(chains)} chain specs; replays equal to record: "
          f"{sum(c['replay_ws_equal_record'] for c in chains)}/{len(chains)}; sources passing: "
          f"{sum(c['source_pass'] for c in chains)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
