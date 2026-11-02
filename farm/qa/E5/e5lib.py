"""E5 (Addendum 41) shared helpers: read one ORFS run's result directory, judge it, and step a rebuild chain.

Units: ASAP7 time is in ps (liberty unit 1 ps; ORFS metrics and SDC periods are in ps).
Claimed clock (AutoTuner's effective_clk_period) = asked period - finish__timing__setup__ws (post-route, OpenRCX).
Judge (7 nm): finish setup WS >= 0 and finish hold WS >= 0 at ORFS's ASAP7 corner (BC), detailed-route DRC count 0,
flow completed.
"""
from __future__ import annotations

import glob
import gzip
import json
import math
import os

GRID = 5.0          # ps: rebuild targets are rounded up to this grid
EPS = 1e-3          # ps: tolerance when rounding up (metrics carry 4 decimals)
MAX_REBUILDS = 4    # new runs per chain


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


def load_run(d: str) -> dict:
    """Summarize results/<tag>/ (as written by orfs_run.sh and run_group.py)."""
    run = _load(os.path.join(d, "run.json"), {}) or {}
    job = _load(os.path.join(d, "job.json"), {}) or {}
    m = {}
    for p in sorted(glob.glob(os.path.join(d, "logs", "*.json"))):
        x = _load(p, {})
        if isinstance(x, dict):
            m.update(x)
    hook = _load(os.path.join(d, "reports", "e5_hook.json"), {}) or {}
    tag = run.get("tag") or job.get("tag") or os.path.basename(d.rstrip("/"))
    period = run.get("period", job.get("period"))
    ws = m.get("finish__timing__setup__ws")
    hs = m.get("finish__timing__hold__ws")
    drc = m.get("detailedroute__route__drc_errors")
    status = run.get("status") or job.get("status") or "missing"
    ok = status == "completed" and ws is not None and hs is not None and drc is not None
    r = {
        "tag": tag, "design": run.get("design", job.get("design")), "period": period,
        "vars": job.get("vars"), "setting": job.get("setting"), "status": status if ok or status != "completed" else "no_metrics",
        "ws": ws, "hold_ws": hs, "tns": m.get("finish__timing__setup__tns"), "drc": drc,
        "claim": (float(period) - float(ws)) if (ok and period is not None) else None,
        "fmax_hz": m.get("finish__timing__fmax"),
        "area_um2": m.get("finish__design__instance__area"),
        "util": m.get("finish__design__instance__utilization"),
        "floorplan_util": m.get("floorplan__design__instance__utilization"),
        "power_w": m.get("finish__power__total"),
        "setup_viol": m.get("finish__timing__drv__setup_violation_count"),
        "hold_viol": m.get("finish__timing__drv__hold_violation_count"),
        "max_slew_viol": m.get("finish__timing__drv__max_slew"),
        "max_cap_viol": m.get("finish__timing__drv__max_cap"),
        "grt_ws": m.get("globalroute__timing__setup__ws"),
        "cts_ws": m.get("cts__timing__setup__ws"),
        "ws_r2r": hook.get("ws_r2r"), "ws_in": hook.get("ws_in"), "ws_out": hook.get("ws_out"),
        "worst_start": hook.get("worst_start"), "worst_end": hook.get("worst_end"),
        "elapsed_s": run.get("elapsed_s"), "cpu": job.get("cpu"),
    }
    if ok:
        r["pass_setup"] = ws >= 0
        r["pass_hold"] = hs >= 0
        r["pass_drc"] = int(drc) == 0
        r["pass"] = r["pass_setup"] and r["pass_hold"] and r["pass_drc"]
        # port-limited: the worst setup path starts at an input or ends at an output and is worse than reg-to-reg
        port = None
        if r["ws_r2r"] is not None or r["ws_in"] is not None or r["ws_out"] is not None:
            port_ws = min([v for v in (r["ws_in"], r["ws_out"]) if v is not None], default=None)
            if port_ws is not None:
                port = r["ws_r2r"] is None or port_ws < r["ws_r2r"] - 1e-4
            else:
                port = False
        r["port"] = port
        r["t_r2r"] = (float(period) - r["ws_r2r"]) if r["ws_r2r"] is not None else None
    else:
        r["pass_setup"] = r["pass_hold"] = r["pass_drc"] = r["pass"] = None
        r["port"] = None
        r["t_r2r"] = None
    return r


def tuner_score(r: dict) -> float:
    """AutoTuner's calculate_score (tools/AutoTuner/src/autotuner/utils.py, step=1): effective_clk_period * 100 +
    (effective_clk_period / 10) * num_drc; runs without metrics get its ERROR_METRIC (9e99)."""
    if r.get("claim") is None or r.get("drc") is None:
        return 9e99
    c = r["claim"]
    return c * 100 + (c / 10) * int(r["drc"])


def chain_next(chain: list[dict], max_rebuilds: int = MAX_REBUILDS):
    """Registered rebuild chain (Addendum 41). chain[0] is the winner run W (target T0, claim C0); chain[1:] are its
    rebuilds in order. Each entry: {"period", "claim", "pass"} (pass = full judge; claim may be None on a flow error).
    Returns (next_target or None, reason).

      1. First rebuild at R1 = ceil5(C0). If W itself passed and R1 == T0, W already sits at its claim: no rebuild.
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
    # last rebuild failed (or had no metrics)
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
