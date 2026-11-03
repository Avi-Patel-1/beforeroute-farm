"""Workstream B (constraint hygiene) shared helpers for the sky130 / LibreLane arms: the frozen I/O override, the judge,
and the registered rebuild chain (docs/qa_week/B_PREREG.md).

Units: ns. Claim C = CLOCK_PERIOD - timing__setup__ws (worst over the nine corners, incl. port paths).
Frozen I/O: IO_DELAY_CONSTRAINT = 100 * D / T, so base.sdc's input/output delay = T * IO/100 = D at every target T;
at T == F_best the value is the design's shipped integer percentage (20; clip16 10), i.e. the stock configuration.
Judge: metrics landed; setup WS >= 0 and hold WS >= 0 (worst over the nine corners); route__drc_errors == 0;
max-slew + max-cap violation count <= the design's stock reference (drv_ref).
Chain: E5's rule (qa-e5-asap7 farm/qa/E5/e5lib.chain_next) on the 0.05 ns grid (farm/tune_a32.py ceil05).
"""
from __future__ import annotations

import json
import math
import os

GRID = 0.05          # ns
MAX_REBUILDS = 4
DRV_KEYS = ("design__max_slew_violation__count", "design__max_cap_violation__count")


def ceil05(x: float) -> float:
    """farm/tune_a32.py ceil05: round up to the 0.05 ns grid (1e-6 tolerance in grid units)."""
    return round(math.ceil(round(x / GRID, 6)) * GRID, 2)


def io_pct(D: float, T: float, io0: float, F_best: float):
    """The frozen-I/O override value (percent of T). Exactly the shipped integer percentage at T == F_best."""
    if abs(float(T) - float(F_best)) < 1e-9:
        return int(round(100 * io0))
    return round(100.0 * float(D) / float(T), 6)


def _load(p, default=None):
    try:
        with open(p) as f:
            return json.load(f)
    except Exception:
        return default


def load_run(results: str, tag: str, period: float, drv_ref) -> dict:
    """Summarize results/<tag>/ as written by br/run_job.py."""
    d = os.path.join(results, tag)
    job = _load(os.path.join(d, "job.json"), {}) or {}
    m = _load(os.path.join(d, "metrics.json"), {}) or {}
    ws, hs = m.get("timing__setup__ws"), m.get("timing__hold__ws")
    wr = m.get("timing__setup_r2r__ws")
    drc = m.get("route__drc_errors")
    drv = sum((m.get(k) or 0) for k in DRV_KEYS) if m else None
    ok = bool(m) and ws is not None and hs is not None
    r = {"tag": tag, "period": float(period), "status": job.get("status", "missing"),
         "flow_seconds": job.get("flow_seconds"), "ws": ws, "ws_r2r": wr, "hold_ws": hs, "drc": drc, "drv": drv,
         "drv_ref": drv_ref, "claim": (float(period) - float(ws)) if ok else None,
         "claim_r2r": (float(period) - float(wr)) if (ok and wr is not None and math.isfinite(wr)) else None,
         "area": m.get("design__instance__area__stdcell"), "io_pct": (job.get("overrides") or {}).get(
             "IO_DELAY_CONSTRAINT")}
    if ok:
        r["pass_setup"] = ws >= 0
        r["pass_hold"] = hs >= 0
        r["pass_drc"] = drc == 0
        r["pass_drv"] = drv_ref is None or drv <= drv_ref
        r["pass"] = bool(r["pass_setup"] and r["pass_hold"] and r["pass_drc"] and r["pass_drv"])
        r["port"] = None if wr is None else bool(ws < wr - 1e-4)
    else:
        r.update({"pass_setup": None, "pass_hold": None, "pass_drc": None, "pass_drv": None, "pass": False,
                  "port": None})
    return r


def chain_next(chain: list, max_rebuilds: int = MAX_REBUILDS):
    """E5's registered chain rule on the 0.05 ns grid. chain[0] = the winner run W (here: W replayed with frozen I/O
    at its search target T0); chain[1:] = rebuilds in order. Entries: {"period", "claim", "pass"}.
    Returns (next target or None, reason)."""
    w = chain[0]
    rebuilds = chain[1:]
    if len(rebuilds) >= max_rebuilds:
        return None, "rebuild cap reached"
    passes = [c["period"] for c in chain if c.get("pass")]
    fails = [c["period"] for c in chain if not c.get("pass")]
    best = min(passes) if passes else None
    if not rebuilds:
        if w.get("claim") is None:
            return None, "winner has no claim"
        r1 = ceil05(w["claim"])
        if w.get("pass") and r1 >= w["period"] - 1e-9:
            return None, "winner already at its claimed clock"
        return r1, "first rebuild at ceil05(claim)"
    last = rebuilds[-1]
    if last.get("pass"):
        nxt = ceil05(last["claim"])
        if best is not None and nxt >= best - 1e-9:
            return None, "claim no lower than the smallest passing clock (converged)"
        below = [f for f in fails if best is None or f < best]
        if below and nxt <= max(below) + 1e-9:
            return None, "a failed clock lies at or above the next claim"
        return nxt, "rebuild at ceil05(claim of last pass)"
    if len(rebuilds) == 1:
        c1 = last.get("claim")
        r1 = last["period"]
        nxt = max(ceil05(c1), round(r1 + GRID, 2)) if c1 is not None else round(r1 + GRID, 2)
        if best is not None and nxt >= best - 1e-9:
            return None, "first rebuild failed; step-back not below the smallest passing clock"
        return nxt, "first rebuild failed: step back once"
    return None, "rebuild failed"


def kept_clock(chain: list):
    passes = [c["period"] for c in chain if c.get("pass")]
    return min(passes) if passes else None


def first_rebuild(chain: list):
    """The first rebuild entry (W itself when W sits at its claimed clock), or None."""
    if len(chain) > 1:
        return chain[1]
    if chain and chain[0].get("pass") and chain[0].get("claim") is not None and \
            ceil05(chain[0]["claim"]) >= chain[0]["period"] - 1e-9:
        return chain[0]
    return None


def first_pass_clock(chain: list):
    """T1: the clock of the chain's first passing rebuild (W itself when W sits at its claimed clock)."""
    fr = first_rebuild(chain)
    if fr is not None and fr is chain[0]:
        return chain[0]["period"]
    for c in chain[1:]:
        if c.get("pass"):
            return c["period"]
    return None
