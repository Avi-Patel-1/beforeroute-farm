#!/usr/bin/env python3
"""Experiment E shared definitions (Addendum 42, docs/qa_week/E_PREREG.md): ceil05, the registered chain simulated on a
deterministic claim-response C(T), and the scripted baselines (raw claim, the law, the I/O-aware scalar rule, the
two-point line, the hand-picked feature)."""
from __future__ import annotations

import gzip
import json
import math

S_MINUS, S_PLUS = 0.59, 0.29          # mechanism-law.md section 2 (sky130/LibreLane, 328 audit runs)
IO_FRAC = 0.20


def ceil05(x):
    return round(math.ceil(round(x / 0.05, 6)) * 0.05, 2)


def simulate_chain(C, T0, C0, source_pass, cap=4):
    """The registered chain on a deterministic response C(T) (pass = C(T) <= T, setup only).
    Returns (first_pass, C1, kept_clock or None, clocks tried)."""
    tried, order = {}, []

    def run(t):
        k = round(t, 4)
        if k not in tried:
            c = C(t)
            tried[k] = (c, c <= t + 1e-9)
            order.append(t)
        return tried[k]

    smallest = T0 if source_pass else None
    failed = []
    R1 = ceil05(C0)
    c1, p1 = run(R1)
    last = None
    if p1:
        smallest = R1 if smallest is None else min(smallest, R1)
        last = c1
    else:
        failed.append(R1)
        step = max(ceil05(c1), round(R1 + 0.05, 2))
        if (smallest is None or step < smallest - 1e-9) and len(order) < cap:
            c2, p2 = run(step)
            if p2:
                smallest = step if smallest is None else min(smallest, step)
                last = c2
            else:
                failed.append(step)
    while last is not None and len(order) < cap:
        nxt = ceil05(last)
        if smallest is not None and nxt >= smallest - 1e-9:
            break
        if any(f >= nxt - 1e-9 and (smallest is None or f < smallest) for f in failed):
            break
        n0 = len(order)
        c, p = run(nxt)
        if p:
            smallest = nxt if smallest is None else min(smallest, nxt)
            last = c
        else:
            failed.append(nxt)
            break
        if len(order) == n0:
            break
    return p1, c1, smallest, order


def predict_from_response(C, T0, C0, source_pass):
    R1 = ceil05(C0)
    p1, c1, kept, _ = simulate_chain(C, T0, C0, source_pass)
    return {"p_pass": 1.0 if p1 else 0.0, "call": "pass" if p1 else "fail",
            "slope": (c1 - C0) / (R1 - T0), "claim1_ns": c1, "kept_clock_ns": kept}


def law_response(T0, ws0):
    s0 = S_MINUS if ws0 < 0 else S_PLUS
    F = T0 - ws0 / (1.0 - s0)                    # k = 1/(1 - s): 2.44 failing, 1.41 passing

    def C(T):
        s = S_MINUS if T < F else S_PLUS
        return F + s * (T - F)
    return C, F


def io_response(T0, ws0, wr0):
    C0 = T0 - ws0
    port = wr0 is not None and ws0 < wr0 - 1e-4
    if not port:
        return lambda T: C0
    c_r2r = T0 - wr0
    return lambda T: max(c_r2r, C0 + IO_FRAC * (T - T0))


def line_response(T0, C0, slope):
    return lambda T: C0 + slope * (T - T0)


def handpicked_feature(postgrt_path):
    """f = (# signal nets whose driver_slack_ns is within 5% of the worst such slack) / (# such nets);
    constrained slacks only (< 1e6 ns)."""
    sl = []
    op = gzip.open if postgrt_path.endswith(".gz") else open
    with op(postgrt_path, "rt") as fh:
        for line in fh:
            if not line.strip():
                continue
            r = json.loads(line)
            if r.get("sigtype") != "SIGNAL":
                continue
            s = r.get("driver_slack_ns")
            if s is None or not isinstance(s, (int, float)) or math.isnan(s) or s >= 1e6:
                continue
            sl.append(float(s))
    if not sl:
        return None
    w = min(sl)
    thr = w + 0.05 * abs(w)
    return sum(1 for s in sl if s <= thr) / len(sl)


def ols(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx > 0 else 0.0
    return my - b * mx, b
