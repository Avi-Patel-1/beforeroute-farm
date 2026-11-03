"""AD (TrueClock overnight, experiments A and D) shared helpers: read one ORFS run's result directory, judge it, and
step a rebuild chain. Derived from farm/qa/E5/e5lib.py (Addendum 41, frozen); the judge, the AutoTuner score and the
chain rule are E5's, unchanged. The one addition: three platforms with different time units. Every number this
module returns is in ps (sky130hd metrics are in ns and are multiplied by 1000).

Claimed clock (AutoTuner's effective_clk_period) = asked period - finish__timing__setup__ws (post-route).
Judge: finish setup WS >= 0 and finish hold WS >= 0 at the platform's ORFS corner, detailed-route DRC count 0, flow
completed.
"""
from __future__ import annotations

import glob
import gzip
import json
import math
import os

GRID = 5.0          # ps: rebuild targets are rounded up to this grid (E5's rule, all platforms)
EPS = 1e-3          # ps: tolerance when rounding up (metrics carry 4 decimals)
MAX_REBUILDS = 4    # new runs per chain
UNIT_PS = {"asap7": 1.0, "gt2n": 1.0, "sky130hd": 1000.0}


def ceil_grid(x: float, g: float = GRID) -> int:
    return int(math.ceil((x - EPS) / g) * g)


def _load(p, default=None):
    try:
        if p.endswith(".gz"):
            with gzip.open(p, "rt") as f:
                return json.load(f)
        with open(p) as f:
            return json.load(f)
    except Exception:
        return default


def r2r_slack_from_report(d: str):
    """Fallback when the hook gave no number: the first slack in the finish report's 'reg to reg' max section."""
    import re
    for p in (os.path.join(d, "reports", "6_finish.rpt"), os.path.join(d, "reports", "6_finish.rpt.gz")):
        if not os.path.exists(p):
            continue
        txt = gzip.open(p, "rt").read() if p.endswith(".gz") else open(p).read()
        i = txt.find("finish report_checks -path_delay max reg to reg")
        if i < 0:
            return None
        m = re.search(r"(-?\d+(?:\.\d+)?)\s+slack \((?:MET|VIOLATED)\)", txt[i:])
        return float(m.group(1)) if m else None
    return None


def _mul(x, u):
    return None if x is None else float(x) * u


def load_run(d: str) -> dict:
    """Summarize results/<tag>/ (as written by orfs_run.sh and run_group.py). Times in ps."""
    run = _load(os.path.join(d, "run.json"), {}) or {}
    job = _load(os.path.join(d, "job.json"), {}) or {}
    platform = run.get("platform") or job.get("platform") or "asap7"
    u = float(run.get("time_unit_ps") or UNIT_PS.get(platform, 1.0))
    m = {}
    for p in sorted(glob.glob(os.path.join(d, "logs", "*.json"))):
        x = _load(p, {})
        if isinstance(x, dict):
            m.update(x)
    hook = _load(os.path.join(d, "reports", "e5_hook.json"), {}) or {}
    if hook.get("ws_r2r") is None:
        v = r2r_slack_from_report(d)
        if v is not None:
            hook = dict(hook, ws_r2r=v, r2r_source="6_finish.rpt")
    tag = run.get("tag") or job.get("tag") or os.path.basename(d.rstrip("/"))
    period = run.get("period_ps", job.get("period_ps", run.get("period", job.get("period"))))
    ws = _mul(m.get("finish__timing__setup__ws"), u)
    hs = _mul(m.get("finish__timing__hold__ws"), u)
    drc = m.get("detailedroute__route__drc_errors")
    status = run.get("status") or job.get("status") or "missing"
    ok = status == "completed" and ws is not None and hs is not None and drc is not None
    r = {
        "tag": tag, "design": run.get("design", job.get("design")), "platform": platform, "period": period,
        "vars": job.get("vars"), "setting": job.get("setting"), "kind": job.get("kind"), "arm": job.get("arm"),
        "status": status if ok or status != "completed" else "no_metrics",
        "ws": ws, "hold_ws": hs, "tns": _mul(m.get("finish__timing__setup__tns"), u), "drc": drc,
        "claim": (float(period) - float(ws)) if (ok and period is not None) else None,
        "area_um2": m.get("finish__design__instance__area"),
        "util": m.get("finish__design__instance__utilization"),
        "synth_area_um2": m.get("synth__design__instance__area__stdcell"),
        "synth_cells": m.get("synth__design__instance__count__stdcell"),
        "synth_sha1": run.get("synth_netlist_sha1"), "abc_d": run.get("ad_abc_d"),
        "abc_d_log_hits": run.get("abc_d_log_hits"),
        "max_slew_viol": m.get("finish__timing__drv__max_slew"),
        "max_cap_viol": m.get("finish__timing__drv__max_cap"),
        "ws_r2r": _mul(hook.get("ws_r2r"), u), "ws_in": _mul(hook.get("ws_in"), u),
        "ws_out": _mul(hook.get("ws_out"), u),
        "worst_start": hook.get("worst_start"), "worst_end": hook.get("worst_end"),
        "elapsed_s": run.get("elapsed_s"), "cpu": job.get("cpu"),
    }
    if ok:
        r["pass_setup"] = ws >= 0
        r["pass_hold"] = hs >= 0
        r["pass_drc"] = int(drc) == 0
        r["pass"] = r["pass_setup"] and r["pass_hold"] and r["pass_drc"]
        r["port"] = None if r["ws_r2r"] is None else bool(ws < r["ws_r2r"] - 0.006 * u)
        r["t_r2r"] = (float(period) - r["ws_r2r"]) if r["ws_r2r"] is not None else None
    else:
        r["pass_setup"] = r["pass_hold"] = r["pass_drc"] = r["pass"] = None
        r["port"] = None
        r["t_r2r"] = None
    rt = _load(os.path.join(d, "reports", "ad_retime.json"))
    if rt is not None:
        r["retime"] = rt
    return r


def tuner_score(r: dict) -> float:
    """AutoTuner's calculate_score (tools/AutoTuner/src/autotuner/utils.py, step=1): effective_clk_period * 100 +
    (effective_clk_period / 10) * num_drc; runs without metrics get its ERROR_METRIC (9e99). (In ps; the ranking is
    the same in any time unit.)"""
    if r.get("claim") is None or r.get("drc") is None:
        return 9e99
    c = r["claim"]
    return c * 100 + (c / 10) * int(r["drc"])


def chain_next(chain: list[dict], max_rebuilds: int = MAX_REBUILDS):
    """E5's registered rebuild chain (Addendum 41), unchanged. chain[0] is the winner run W (target T0, claim C0);
    chain[1:] are its rebuilds in order. Each entry: {"period", "claim", "pass"} (ps). Returns (next or None, why).

      1. First rebuild at R1 = ceil5(C0). If W itself passed and R1 >= T0, W already sits at its claim: no rebuild.
      2. After a passing rebuild with claim C: next = ceil5(C) while it is below the chain's smallest passing clock
         and above every failed clock of the chain that lies below that smallest passing clock.
      3. If the first rebuild fails: step back once, to max(ceil5(C1), R1 + 5), unless that is not below the chain's
         smallest passing clock (W's own target if W passed). A rebuild that fails after that ends the chain.
      4. At most max_rebuilds new runs. The kept clock is the chain's smallest passing clock.
    """
    w = chain[0]
    rebuilds = chain[1:]
    if len(rebuilds) >= max_rebuilds:
        return None, "rebuild cap reached"
    passes = [c["period"] for c in chain if c.get("pass")]
    fails = [c["period"] for c in chain if c.get("pass") is False or c.get("pass") is None]
    best = min(passes) if passes else None
    if not rebuilds:
        if w.get("claim") is None:
            return None, "winner has no claim"
        r1 = ceil_grid(w["claim"])
        if w.get("pass") and r1 >= w["period"]:
            return None, "winner already at its claimed clock"
        return r1, "first rebuild at ceil5(claim)"
    last = rebuilds[-1]
    if last.get("pass"):
        nxt = ceil_grid(last["claim"])
        if best is not None and nxt >= best:
            return None, "claim no lower than the smallest passing clock (converged)"
        below = [f for f in fails if best is None or f < best]
        if below and nxt <= max(below):
            return None, "a failed clock lies at or above the next claim"
        return nxt, "rebuild at ceil5(claim of last pass)"
    if len(rebuilds) == 1:
        c1 = last.get("claim")
        r1 = last["period"]
        nxt = max(ceil_grid(c1), r1 + int(GRID)) if c1 is not None else r1 + int(GRID)
        if best is not None and nxt >= best:
            return None, "first rebuild failed; step-back not below the smallest passing clock"
        return nxt, "first rebuild failed: step back once"
    return None, "rebuild failed"


def kept_clock(chain: list[dict]):
    passes = [c["period"] for c in chain if c.get("pass")]
    return min(passes) if passes else None


def top3(runs: list[dict], k: int = 3) -> list[dict]:
    """The tuner's picks (E5's rule): lowest AutoTuner score among the design's grid runs; ties by tag."""
    rs = [r for r in runs if tuner_score(r) < 9e99]
    rs.sort(key=lambda r: (tuner_score(r), r["tag"]))
    return rs[:k]
