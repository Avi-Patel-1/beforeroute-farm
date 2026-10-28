#!/usr/bin/env python3
"""Addendum 25: the Addendum-24 protocol on five more designs, with the per-net project's parasitic correction merged
into the tuner's search space (RC model: stock / wire cap x2.13 / ORFS per-layer R and C for the estimate-based steps).

Same objective, feasibility (Amendment 24.1: no more slew+cap pins than the design's stock run at its default clock,
here x2d-<design>-001), tuner (Optuna TPE, 8 start-ups, <= 8 in flight, 24 trials), random arm (24), defaults and expert
arms (5 clock periods), plus arm f = the expert preset with ORFS per-layer RC (the correction without the search).
Seeds differ per design. Usage mirrors farm/tune.py: --init / --step / --confirm / --report [--json f] [--dry-run].
"""
from __future__ import annotations

import json
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tune as T  # noqa: E402

T.PREFIX = "x2"
T.ADDENDUM = "Addendum 25"
T.TUNE = os.path.join(T.ROOT, "results", "tune_x2")
T.STATE = os.path.join(T.TUNE, "state.json")
T.DESIGNS = {
    "des": {"dir": "designs/des", "config": "config_sky130.json", "period": 20.0},
    "md5": {"dir": "designs/md5", "config": "config_sky130.json", "period": 37.05},
    "bm64": {"dir": "designs/bm64", "config": "config_sky130.json", "period": 20.0},
    "ocs_blitter": {"dir": "designs/ocs_blitter", "config": "config_sky130.json", "period": 18.2},
    "blabla": {"dir": "designs/blabla", "config": "config_sky130.json", "period": 65.0},
}
T.INIT_CAPS = (12, 8)
T.NEED = 3
RC = {"stock": None,
      "cap213": json.load(open(os.path.join(T.ROOT, "farm", "rc", "sky130_cap213.json"))),
      "orfs": json.load(open(os.path.join(T.ROOT, "farm", "rc", "sky130_caporfs.json")))}
T.FIXED_ARMS = [("d", {}), ("e", T.EXPERT), ("f", {**T.EXPERT, "LAYERS_RC": RC["orfs"]})]
T.REPORT_ARMS = ("t", "r", "d", "e", "f", "c")


def seed_for(d, base):
    return base + zlib.crc32(d.encode()) % 100000


T.seed_for = seed_for
_base_suggest = T.suggest


def suggest(trial, d):
    ov = _base_suggest(trial, d)
    rc = trial.suggest_categorical("RC_MODEL", ["stock", "cap213", "orfs"])
    if RC[rc] is not None:
        ov["LAYERS_RC"] = RC[rc]
    return ov


T.suggest = suggest


def rc_model(ov):
    lr = ov.get("LAYERS_RC")
    if lr is None:
        return "stock"
    return "orfs" if lr == RC["orfs"] else ("cap213" if lr == RC["cap213"] else "other")


def report_a25(js):
    out = T.report(None)
    res, overall = T.verdicts(out)
    INF = float("inf")
    e_res = {}
    for d, row in out.items():
        t, f = row["t"], row["f"]
        v = None
        if t["landed"] == t["n"] == T.N_TRIALS and f["landed"] == f["n"] == len(T.FRACS):
            tb = t["best_teff"] if t["best_teff"] is not None else INF
            fb = f["best_teff"] if f["best_teff"] is not None else INF
            v = tb < INF and (fb == INF or (fb - tb) / fb > 0.05)
        e_res[d] = v
        best = t.get("best_overrides")
        row["t"]["best_rc_model"] = rc_model(best) if best else None
    p = sum(1 for v in e_res.values() if v is True)
    f_ = sum(1 for v in e_res.values() if v is False)
    overall["A25e"] = ("PASS" if p >= T.NEED else ("FAIL" if f_ > len(e_res) - T.NEED else "pending")) + \
        f" ({p} pass, {f_} fail, {len(e_res) - p - f_} pending)"
    print(f"  A25e (tuner vs expert+ORFS RC, > 5%): {overall['A25e']}  " + ", ".join(f"{d}={v}" for d, v in e_res.items()))
    print("  (A24a-d above are this study's A25a-d)")
    if js:
        json.dump({"designs": out, "per_design": res, "per_design_e": e_res, "overall": overall}, open(js, "w"), indent=1,
                  default=str)
    return out


def main() -> int:
    if "--report" in sys.argv:
        js = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
        report_a25(js)
        argv = [a for a in sys.argv[1:] if a not in ("--report",)]
        if "--json" in argv:
            i = argv.index("--json")
            del argv[i:i + 2]
        if not argv:
            return 0
        sys.argv = [sys.argv[0]] + argv
    return T.main()


if __name__ == "__main__":
    raise SystemExit(main())
