#!/usr/bin/env python3
"""Experiment E: run a frozen predict(run_dir) module (rung 3's formula, Codex's deterministic baseline) on every main
rung-2 packet and write <pred>/<arm>/<packet_id>.json in the PACKET_FORMAT.md schema.

  run_predictor.py --module /path/formula.py --arm rung3 --packets /home/claude/ideas/overnight/reading/packets \
      --pred /home/claude/ideas/overnight/reading/predictions [--sha256 EXPECTED]
Main packets are the directories <packets>/<pid>/ that have both rung1/ and rung2/ (controls have only rung2/).
The module's SHA-256 is printed (and checked against --sha256 when given) before anything runs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import sys
import traceback


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--module", required=True)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--packets", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--sha256", default=None)
    ap.add_argument("--func", default="predict")
    a = ap.parse_args()
    h = hashlib.sha256(open(a.module, "rb").read()).hexdigest()
    print(f"[run] {a.module} sha256 {h}")
    if a.sha256 and h != a.sha256:
        print("[run] SHA-256 mismatch: refusing")
        return 2
    sys.path.insert(0, os.path.dirname(os.path.abspath(a.module)))
    spec = importlib.util.spec_from_file_location("frozen_predictor", a.module)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    fn = getattr(mod, a.func)
    out = os.path.join(a.pred, a.arm)
    os.makedirs(out, exist_ok=True)
    n = bad = 0
    for pid in sorted(os.listdir(a.packets)):
        d = os.path.join(a.packets, pid)
        if not (os.path.isdir(os.path.join(d, "rung1")) and os.path.isdir(os.path.join(d, "rung2"))):
            continue
        try:
            r = dict(fn(os.path.join(d, "rung2")))
            rec = {"packet_id": pid, "arm": a.arm, "p_pass": float(r["p_pass"]), "call": r["call"],
                   "slope": float(r["slope"]),
                   "kept_clock_ns": None if r.get("kept_clock_ns") is None else float(r["kept_clock_ns"]),
                   "module_sha256": h}
            assert 0.0 <= rec["p_pass"] <= 1.0 and rec["call"] in ("pass", "fail", "abstain")
        except Exception as e:
            bad += 1
            rec = {"packet_id": pid, "arm": a.arm, "error": f"{type(e).__name__}: {e}", "module_sha256": h}
            traceback.print_exc()
        json.dump(rec, open(os.path.join(out, pid + ".json"), "w"), indent=1)
        n += 1
    print(f"[run] {a.arm}: {n} packets, {bad} errors -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
