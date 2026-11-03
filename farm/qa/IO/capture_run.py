#!/usr/bin/env python3
"""IO1: capture the raw record of a finished LibreLane run for the pin test.

Usage: capture_run.py <run_dir> --out <dir> [--pdk-root <dir>]
Runs capture.py (step IOPins.Capture: the signoff view of br/run_dump.py --signoff) and copies the final DEF,
gzipped, to <out>/final.def.gz. Changes nothing in the run.
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "br"))

from librelane.common import Toolbox  # noqa: E402
from librelane.state import State  # noqa: E402
from librelane.steps import Step  # noqa: E402

import steps as brsteps  # noqa: E402
from run_dump import load_step_config  # noqa: E402


@Step.factory.register()
class Capture(brsteps.DumpNetsSignoff):
    id = "IOPins.Capture"
    name = "IO1 capture (signoff view)"

    def get_script_path(self):
        return os.path.join(HERE, "capture.py")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "/work/pdk"))
    a = ap.parse_args()
    run_dir, out = os.path.abspath(a.run_dir), os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    rc = 0
    defs = sorted(glob.glob(os.path.join(run_dir, "final", "def", "*.def")))
    if defs:
        with open(defs[0], "rb") as fi, gzip.open(os.path.join(out, "final.def.gz"), "wb") as fo:
            shutil.copyfileobj(fi, fo)
    else:
        print("[iopins] no final DEF", file=sys.stderr)
        rc = 1
    cands = sorted(glob.glob(os.path.join(run_dir, "*-openroad-stapostpnr", "state_in.json")))
    if not cands:
        print("[iopins] no STAPostPNR state_in.json", file=sys.stderr)
        return 1
    st = json.load(open(cands[-1]))
    spef_map_path = os.path.join(out, "spef_map.json")
    json.dump(st["spef"], open(spef_map_path, "w"))
    config = load_step_config(run_dir, a.pdk_root, extra={"BR_MODE": "signoff", "BR_SPEF_MAP": spef_map_path},
                              cls=Capture)
    state_in = State.loads(open(cands[-1]).read())
    step = Capture(config=config, state_in=state_in, _no_revalidate_conf=True)
    step.start(toolbox=Toolbox(os.path.join(out, "toolbox_tmp")), step_dir=out)
    shutil.rmtree(os.path.join(out, "toolbox_tmp"), ignore_errors=True)
    for f in ("ports.json", "paths.json"):
        p = os.path.join(out, f)
        if not os.path.exists(p):
            print(f"[iopins] capture did not write {f}", file=sys.stderr)
            rc = 1
            continue
        with open(p, "rb") as fi, gzip.open(p + ".gz", "wb") as fo:
            shutil.copyfileobj(fi, fo)
        os.remove(p)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
