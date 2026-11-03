"""Workstream B (constraint hygiene) shared helpers for the sky130 / LibreLane arms: the frozen I/O override, the judge,
and the registered rebuild chain (docs/qa_week/B_PREREG.md).

Units: ns. Claim C = CLOCK_PERIOD - timing__setup__ws (worst over the nine corners, incl. port paths).
Frozen I/O: IO_DELAY_CONSTRAINT = 100 * D / T, so base.sdc's input/output delay = T * IO/100 = D at every target T;
at T == F_best the value is the design's shipped integer percentage (20; clip16 10), i.e. the stock configuration.
Judge (fail-closed): a completed job with every judged metric present; setup WS >= 0 and hold WS >= 0 (worst over the
nine corners); route__drc_errors == 0; max-slew + max-cap violation count <= the design's stock reference (drv_ref).
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


REQUIRED = ("timing__setup__ws", "timing__hold__ws", "route__drc_errors") + DRV_KEYS
JOB_OK = ("completed", "extract_failed")   # br/run_job.py: the flow completed (extract_failed = post-flow dumps only)


def load_run(results: str, tag: str, period: float, drv_ref) -> dict:
    """Summarize results/<tag>/ as written by br/run_job.py.

    Fail-closed admission (bug fix 2026-11-03, Codex code audit; before it, missing slew/cap counts were read as 0 and
    a missing reference or job record could still PASS): a run is judged only if its job record says the flow
    completed and every judged metric (setup WS, hold WS, route DRC, max-slew and max-cap counts) is present and finite,
    and the slew/cap reference is known. Otherwise it is not admitted and fails the judge (B_PREREG.md: a run without
    metrics fails); "why" says what was missing. The claim needs only a completed job and the setup WS."""
    d = os.path.join(results, tag)
    job = _load(os.path.join(d, "job.json"), {}) or {}
    m = _load(os.path.join(d, "metrics.json"), {}) or {}

    def num(k):
        try:
            v = float(m.get(k))
        except (TypeError, ValueError):
            return None
        return v if math.isfinite(v) else None
    ws, hs, drc = num("timing__setup__ws"), num("timing__hold__ws"), num("route__drc_errors")
    wr = num("timing__setup_r2r__ws")
    slew, cap = num(DRV_KEYS[0]), num(DRV_KEYS[1])
    drv = (slew + cap) if (slew is not None and cap is not None) else None
    job_ok = bool(job) and job.get("status") in JOB_OK and job.get("flow_completed", True) is not False
    why = []
    if not job:
        why.append("no job record")
    elif not job_ok:
        why.append(f"job status {job.get('status')}")
    if not m:
        why.append("no metrics")
    else:
        miss = [k for k in REQUIRED if num(k) is None]
        if miss:
            why.append("missing/non-finite " + ",".join(miss))
    if drv_ref is None:
        why.append("no slew/cap reference")
    admitted = not why
    claim = (float(period) - ws) if (job_ok and ws is not None) else None
    r = {"tag": tag, "period": float(period), "status": job.get("status", "missing"),
         "flow_seconds": job.get("flow_seconds"), "ws": ws, "ws_r2r": wr, "hold_ws": hs, "drc": drc, "drv": drv,
         "drv_ref": drv_ref, "claim": claim,
         "claim_r2r": (float(period) - wr) if (claim is not None and wr is not None) else None,
         "area": m.get("design__instance__area__stdcell"),
         "io_pct": (job.get("overrides") or {}).get("IO_DELAY_CONSTRAINT"),
         "admitted": admitted, "why": "; ".join(why) or None}
    if admitted:
        r["pass_setup"] = ws >= 0
        r["pass_hold"] = hs >= 0
        r["pass_drc"] = drc == 0
        r["pass_drv"] = drv <= drv_ref
        r["pass"] = bool(r["pass_setup"] and r["pass_hold"] and r["pass_drc"] and r["pass_drv"])
    else:
        r.update({"pass_setup": None, "pass_hold": None, "pass_drc": None, "pass_drv": None, "pass": False})
    r["port"] = None if (ws is None or wr is None) else bool(ws < wr - 1e-4)
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


def linfit(xs, ys):                     # agents/analysis/fixedpoint/analyze.py linfit (copied verbatim)
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx < 1e-12:
        return None, None
    a = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return a, my - a * mx


def crossing(pts):                      # agents/analysis/fixedpoint/analyze.py crossing (copied verbatim)
    """pts: [(T, teff)] distinct T, sorted ascending. Returns (F, how)."""
    g = [(T, te - T) for T, te in pts]
    for (t1, g1), (t2, g2) in zip(g, g[1:]):
        if g1 > 0 >= g2:
            return t1 + (t2 - t1) * g1 / (g1 - g2), "interpolated"

    def extra(p1, p2, how):
        a, b = linfit([p1[0], p2[0]], [p1[1], p2[1]])
        if a is None or a >= 0.999:
            return None, how + " (no crossing: slope >= 1)"
        return b / (1 - a), how
    if all(x <= 0 for _, x in g):
        return extra(pts[0], pts[1], "extrapolated below")
    if all(x > 0 for _, x in g):
        return extra(pts[-2], pts[-1], "extrapolated above")
    a, b = linfit([p[0] for p in pts], [p[1] for p in pts])
    if a is None or a >= 0.999:
        return None, "no crossing"
    return b / (1 - a), "fit all"


def topup_target(pts):
    """C1's registered top-up rule (B_PREREG.md): pts [(T, claim)] of one setting, one point per target (median if
    repeated). Returns (target or None if bracketed, reason). Targets rounded to 0.01 ns."""
    pts = sorted(pts)
    if len(pts) < 2:
        return None, "fewer than 2 targets"
    F, how = crossing(pts)
    if how == "interpolated":
        return None, "bracketed"
    tmin, tmax = pts[0][0], pts[-1][0]
    if how.startswith("extrapolated below"):            # met at every target
        Fx = F if F is not None else tmin
        return round(0.95 * min(Fx, tmin), 2), "met at every target: 0.95 x min(F_x, T_min)"
    if how.startswith("extrapolated above"):            # missed at every target
        Fx = F if F is not None else tmax
        return round(1.05 * max(Fx, tmax), 2), "missed at every target: 1.05 x max(F_x, T_max)"
    Fx = F if F is not None else tmin                   # "fit all" / "no crossing"
    return round(0.95 * min(Fx, tmin), 2), "neither: 0.95 x min(F_x, T_min)"
