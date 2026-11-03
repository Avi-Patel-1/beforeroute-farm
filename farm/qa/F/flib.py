"""F (overnight workstream F): shared helpers. Read one run's result directory (either harness), judge it, step a rebuild chain.

Two harnesses, each the one its publication used:
  orfsagent - ORFS-agent's AutoTuner-integration job script (github.com/ABKGroup/ORFS-Agent @ 730f1fa,
              AutoTuner-integration/AutoTuner/run_or_job.sh) in openroad/orfs:v3.0-1548-gce8d36a7 (ORFS ce8d36a7,
              the commit the ORFS-agent paper names). Metrics: ORFS 6_report.json / 5_2_route.json; claim = asked
              period - finish__timing__setup__ws (exactly ORFS-agent's ECP_final).
  edaenv    - EDA-env's own evaluator (Zenodo doi:10.5281/zenodo.22990248): flow in its pinned image
              (openroad/orfs:26Q3-5-gfb65d5b48 + its patched scripts), then its measure.tcl on the final ODB with the
              task's evaluation SDC. Claim = eval clock - wns (exactly EDA-env's ECP).

Units: ASAP7 ps; sky130hd ns. Grid: 5 ps (ASAP7, E5's rule) or 0.05 ns (sky130hd, the sky130 record's rule).
Judge (pass): flow completed; worst setup slack >= 0 and worst hold slack >= 0 (orfsagent: hold violation count 0,
which is the same test) at the clock asked; routing DRC count 0.
Chain: E5's registered rule (farm/qa/E5/e5lib.py chain_next), with the grid as a parameter.
"""
from __future__ import annotations

import glob
import gzip
import json
import math
import os
import re

MAX_REBUILDS = 4


def grid_for(platform: str) -> float:
    return 0.05 if platform.startswith("sky130") else 5.0


def fmt_period(x: float, grid: float = 5.0) -> str:
    """Period as written into the SDC / environment: the value itself, no float noise, no rounding to the grid
    (a replay uses the published target exactly, e.g. 140.237 ps or 3.634 ns)."""
    return f"{float(x):.6f}".rstrip("0").rstrip(".")


def ceil_grid(x: float, grid: float) -> float:
    eps = grid * 2e-4          # 1e-3 ps on the 5 ps grid (E5), 1e-5 ns on the 0.05 ns grid
    v = math.ceil((x - eps) / grid) * grid
    return int(round(v)) if grid >= 1 else round(v, 2)


def _load(p, default=None):
    try:
        if p.endswith(".gz"):
            with gzip.open(p, "rt") as f:
                return json.load(f)
        with open(p) as f:
            return json.load(f)
    except Exception:
        return default


def _report_text(d: str, name: str):
    for p in (os.path.join(d, "reports", name), os.path.join(d, "reports", name + ".gz")):
        if os.path.exists(p):
            return gzip.open(p, "rt").read() if p.endswith(".gz") else open(p).read()
    return None


def _first_slack_after(txt: str, header: str):
    if not txt:
        return None
    i = txt.find(header)
    if i < 0:
        return None
    m = re.search(r"(-?\d+(?:\.\d+)?)\s+slack \((?:MET|VIOLATED)\)", txt[i:])
    return float(m.group(1)) if m else None


def load_orfsagent(d: str) -> dict:
    run = _load(os.path.join(d, "run.json"), {}) or {}
    m = {}
    for p in sorted(glob.glob(os.path.join(d, "logs", "*.json"))):
        x = _load(p, {})
        if isinstance(x, dict):
            m.update(x)
    rpt = _report_text(d, "6_finish.rpt")
    period = run.get("period")
    ws = m.get("finish__timing__setup__ws")
    hold_n = m.get("finish__timing__drv__hold_violation_count")
    hold_ws = m.get("finish__timing__hold__ws")
    if hold_ws is None:
        hold_ws = _first_slack_after(rpt, "finish report_checks -path_delay min")
    drc = m.get("detailedroute__route__drc_errors")
    status = run.get("status", "missing")
    ok = status == "completed" and ws is not None and drc is not None and (hold_n is not None or hold_ws is not None)
    r = {"harness": "orfsagent", "status": status if ok or status != "completed" else "no_metrics",
         "period": period, "ws": ws, "hold_ws": hold_ws, "hold_viol": hold_n, "drc": drc,
         "tns": m.get("finish__timing__setup__tns"),
         "claim": (float(period) - float(ws)) if (ok and period is not None) else None,
         "area_um2": m.get("finish__design__instance__area"), "power_w": m.get("finish__power__total"),
         "util": m.get("finish__design__instance__utilization"),
         "ws_r2r": _first_slack_after(rpt, "finish report_checks -path_delay max reg to reg"),
         "elapsed_s": run.get("elapsed_s")}
    if ok:
        hold_ok = (int(hold_n) == 0) if hold_n is not None else (hold_ws >= 0)
        r.update(pass_setup=ws >= 0, pass_hold=hold_ok, pass_drc=int(drc) == 0)
        r["pass"] = r["pass_setup"] and r["pass_hold"] and r["pass_drc"]
    else:
        r.update(pass_setup=None, pass_hold=None, pass_drc=None)
        r["pass"] = None
    return r


def load_edaenv(d: str) -> dict:
    run = _load(os.path.join(d, "run.json"), {}) or {}
    flow = _load(os.path.join(d, "case", "flow.json"), {}) or {}
    meas = _load(os.path.join(d, "case", "measure", "measure.json"), {}) or {}
    met = meas.get("metrics") or {}
    period = run.get("period")
    wns, whs, drc = met.get("wns"), met.get("whs"), met.get("drc_violations")
    status = run.get("status", "missing")
    if status == "completed" and flow.get("status") != "ok":
        status = "flow_" + str(flow.get("status", "missing"))
    ok = status == "completed" and wns is not None and whs is not None and drc is not None
    r = {"harness": "edaenv", "status": status if ok or status != "completed" else "no_metrics",
         "period": period, "ws": wns, "hold_ws": whs, "drc": drc, "tns": met.get("tns"),
         "claim": (float(period) - float(wns)) if (ok and period is not None) else None,
         "ecp_evaluator": met.get("ecp"), "area_um2": met.get("area_um2"), "power_w": met.get("power_total"),
         "util": met.get("utilization"), "instance_count": met.get("instance_count"),
         "drc_source": met.get("drc_source"), "flow_failures": flow.get("failures"),
         "elapsed_s": run.get("elapsed_s")}
    if ok:
        r.update(pass_setup=wns >= 0, pass_hold=whs >= 0, pass_drc=int(drc) == 0)
        r["pass"] = r["pass_setup"] and r["pass_hold"] and r["pass_drc"]
    else:
        r.update(pass_setup=None, pass_hold=None, pass_drc=None)
        r["pass"] = None
    return r


def load_run(d: str) -> dict:
    run = _load(os.path.join(d, "run.json"), {}) or {}
    job = _load(os.path.join(d, "job.json"), {}) or {}
    h = run.get("harness") or job.get("harness")
    r = load_edaenv(d) if h == "edaenv" else load_orfsagent(d)
    r.update(tag=run.get("tag") or job.get("tag") or os.path.basename(d.rstrip("/")),
             config=job.get("config"), kind=job.get("kind"), cpu=job.get("cpu"), wall_s=job.get("wall_s"))
    return r


def chain_next(chain: list[dict], grid: float, max_rebuilds: int = MAX_REBUILDS):
    """E5's registered chain rule (farm/qa/E5/e5lib.py chain_next) with the grid as a parameter.
    chain[0] = the replay W of the published configuration at its published target T0 (claim C0'); chain[1:] = its
    rebuilds in order; entries {"period", "claim", "pass"}. Returns (next_target or None, reason).
      1. First rebuild at R1 = ceil_grid(C0'). If W passed and R1 >= T0, W already sits at its claim: no rebuild.
      2. After a passing rebuild with claim C: next = ceil_grid(C) while below the chain's smallest passing clock and
         above every failed clock of the chain below that smallest passing clock.
      3. If the first rebuild fails: step back once, to max(ceil_grid(C1), R1 + grid), unless that is not below the
         chain's smallest passing clock. A failed rebuild after that ends the chain.
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
            return None, "replay has no claim"
        r1 = ceil_grid(w["claim"], grid)
        if w.get("pass") and r1 >= w["period"]:
            return None, "replay already at its claimed clock"
        return r1, "first rebuild at ceil(claim)"
    last = rebuilds[-1]
    if last.get("pass"):
        nxt = ceil_grid(last["claim"], grid)
        if best is not None and nxt >= best - 1e-9:
            return None, "claim no lower than the smallest passing clock (converged)"
        below = [f for f in fails if best is None or f < best]
        if below and nxt <= max(below) + 1e-9:
            return None, "a failed clock lies at or above the next claim"
        return nxt, "rebuild at ceil(claim of last pass)"
    if len(rebuilds) == 1:
        c1 = last.get("claim")
        r1 = last["period"]
        step = ceil_grid(r1 + grid, grid)
        nxt = max(ceil_grid(c1, grid), step) if c1 is not None else step
        if best is not None and nxt >= best - 1e-9:
            return None, "first rebuild failed; step-back not below the smallest passing clock"
        return nxt, "first rebuild failed: step back once"
    return None, "rebuild failed"


def kept_clock(chain: list[dict]):
    passes = [c["period"] for c in chain if c.get("pass")]
    return min(passes) if passes else None
