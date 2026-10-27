#!/usr/bin/env python3
"""Run the BeforeRoute.DumpNetsPostGRT step standalone on a finished LibreLane run.

Usage: run_dump.py <run_dir> [--out <dir>] [--pdk-root <dir>]

The post-GRT state is taken from the state_in.json of the flow's `STAMidPNR-3`
step (the last pre-route STA), so features describe exactly what the flow's
own post-GRT timing report saw.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from librelane.common import Toolbox  # noqa: E402
from librelane.config import Config  # noqa: E402
from librelane.state import State  # noqa: E402

from steps import DumpNetsPostGRT, DumpNetsSignoff  # noqa: E402


def find_state_in(run_dir: str) -> str:
    cands = sorted(glob.glob(os.path.join(run_dir, "*-openroad-stamidpnr-3", "state_in.json")))
    if not cands:
        # fall back: last openroad step before detailed routing
        cands = sorted(glob.glob(os.path.join(run_dir, "*-openroad-detailedrouting", "state_in.json")))
    if not cands:
        raise SystemExit(f"no post-GRT state_in.json found under {run_dir}")
    return cands[-1]


def load_step_config(run_dir: str, pdk_root: str, extra: dict | None = None, cls=DumpNetsPostGRT) -> Config:
    """Base the step config on the run's own post-GPL resizer step config (a
    ResizerStep, so it carries every GRT/RSZ/SDC variable this step needs), and
    fill anything missing from resolved.json."""
    base_cands = sorted(glob.glob(os.path.join(run_dir, "*-openroad-repairdesignpostgpl", "config.json")))
    resolved = json.loads(open(os.path.join(run_dir, "resolved.json")).read(), parse_float=Decimal)
    all_vars = cls.get_all_config_variables()  # includes the universal flow variables
    wanted = {v.name for v in all_vars}
    merged = {k: v for k, v in resolved.items() if k in wanted or k == "meta"}
    if base_cands:
        for k, v in json.loads(open(base_cands[-1]).read(), parse_float=Decimal).items():
            if k in wanted and k not in merged:
                merged[k] = v
    if extra:
        merged.update(extra)
    for probe in ("MAX_TRANSITION_CONSTRAINT", "MAX_CAPACITANCE_CONSTRAINT", "MAX_FANOUT_CONSTRAINT", "CLOCK_PERIOD"):
        print(f"[br] config {probe} = {merged.get(probe)!r} (in wanted: {probe in wanted})")
    try:
        config, _ = Config.load(
            config_in=merged,
            flow_config_vars=all_vars,
            design_dir=".",
            pdk_root=pdk_root,
            _load_pdk_configs=False,
        )
    except Exception as e:  # unrelated variables rejected: fall back to a strict filter
        print(f"[br] full config rejected ({type(e).__name__}: {str(e)[:200]}); filtering")
        filtered = {k: v for k, v in merged.items() if k in wanted or k == "meta"}
        config, _ = Config.load(
            config_in=filtered,
            flow_config_vars=all_vars,
            design_dir=".",
            pdk_root=pdk_root,
            _load_pdk_configs=False,
        )
    return config


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--out", default=None)
    ap.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "/home/claude/eda/pdk"))
    ap.add_argument("--signoff", action="store_true", help="dump the signoff view (final ODB + RCX SPEF per corner)")
    ap.add_argument("--state", default=None,
                    help="explicit post-GRT state json to dump instead of STAMidPNR-3's state_in, e.g. "
                         "<run>/*-openroad-checkantennas/state_out.json = the decision point the arms resume from "
                         "(before antenna repair)")
    ap.add_argument("--layers-rc", default=None,
                    help="JSON file with a LAYERS_RC override (per-corner, per-layer wire res/cap) for the post-GRT dump, "
                         "e.g. farm/rc/sky130_cap213.json: re-times the estimate with the wire cap scaled to extraction")
    a = ap.parse_args()
    run_dir = os.path.abspath(a.run_dir)
    out = a.out or os.path.join(run_dir, "br-dump-signoff" if a.signoff else "br-dump-postgrt")
    os.makedirs(out, exist_ok=True)
    if a.signoff:
        cands = sorted(glob.glob(os.path.join(run_dir, "*-openroad-stapostpnr", "state_in.json")))
        if not cands:
            raise SystemExit("no STAPostPNR state_in.json")
        state_in_path = cands[-1]
        st = json.load(open(state_in_path))
        spef_map_path = os.path.join(out, "spef_map.json")
        json.dump(st["spef"], open(spef_map_path, "w"))
        config = load_step_config(run_dir, a.pdk_root, extra={"BR_MODE": "signoff", "BR_SPEF_MAP": spef_map_path}, cls=DumpNetsSignoff)
        state_in = State.loads(open(state_in_path).read())
        step = DumpNetsSignoff(config=config, state_in=state_in, _no_revalidate_conf=True)
    else:
        state_in_path = os.path.abspath(a.state) if a.state else find_state_in(run_dir)
        extra = None
        if a.layers_rc:
            from decimal import Decimal
            extra = {"LAYERS_RC": json.loads(open(a.layers_rc).read(), parse_float=Decimal)}
            print(f"[br] LAYERS_RC override from {a.layers_rc}")
        config = load_step_config(run_dir, a.pdk_root, extra=extra)
        state_in = State.loads(open(state_in_path).read())
        step = DumpNetsPostGRT(config=config, state_in=state_in, _no_revalidate_conf=True)
    print(f"[br] state_in: {state_in_path}")
    print(f"[br] odb: {state_in['odb']}")
    step.start(toolbox=Toolbox(os.path.join(out, "toolbox_tmp")), step_dir=out)
    summ = os.path.join(out, "dump_summary.json")
    if os.path.exists(summ):
        print(open(summ).read())
        return 0
    print("[br] dump_summary.json missing; step failed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
