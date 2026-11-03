"""Rung-3 frozen forecasting formula (registered chain, sky130A / LibreLane 3.0.16, packet format E1.0).

predict(run_dir) reads ONLY run_dir/contract.json (source block, judge.drv_bar, chain.R1_ns) and, if present,
run_dir/metrics.json (fallback for missing contract fields). Per-net dumps, layout/ and sta/ are not needed.
Deterministic, standard library only. Constants were fitted on the training families (rung3_train) and are
hard-coded; see NOTES.md.
"""
import json
import math
import os

GRID = 0.05
IO_FRAC = 0.20          # io_delay_pct_of_period / 100 (read from the contract when present)

# slope location: s = B0 + B1*relax + B2*r + B3*relax*r, r = min(|R1-T0|/C0, R_CLIP)  (L1 fit, family-weighted)
B0, B1, B2, B3 = 0.713, -0.255, -2.147, 2.013
R_CLIP = 0.30
# pass model: claim change dC = (s + OFF)*dT + logistic noise, scale = A_C0*C0 + B_DT*|dT|
OFF_RELAX, OFF_TIGHT = -0.10, 0.10
A_C0, B_DT = 0.013, 0.05
# non-setup checks: DRV count vs bar, hold, DRC
DRV_R0, DRV_K = 0.97, 25.0
P_CLEAN = 0.995
HOLD_BAD = 0.88
DRC_BAD = 0.5
# call thresholds
CALL_PASS, CALL_FAIL = 0.60, 0.40


def _ceil05(x):
    return round(math.ceil(x / GRID - 1e-6) * GRID, 4)


def _load(run_dir):
    with open(os.path.join(run_dir, 'contract.json')) as fh:
        c = json.load(fh)
    m = {}
    p = os.path.join(run_dir, 'metrics.json')
    if os.path.exists(p):
        try:
            with open(p) as fh:
                m = json.load(fh)
        except Exception:
            m = {}
    return c, m


def _f(x, default=None):
    try:
        if x is None:
            return default
        v = float(x)
        return v if math.isfinite(v) else default
    except Exception:
        return default


class _Src:
    pass


def _source(c, m):
    s = c.get('source', {})
    o = _Src()
    o.T0 = _f(s.get('target_ns'))
    o.WS0 = _f(s.get('worst_setup_slack_ns'), _f(m.get('timing__setup__ws')))
    o.C0 = _f(s.get('claim_ns'))
    if o.C0 is None and o.T0 is not None and o.WS0 is not None:
        o.C0 = o.T0 - o.WS0
    if o.WS0 is None and o.C0 is not None:
        o.WS0 = o.T0 - o.C0
    o.r2r = _f(s.get('r2r_worst_setup_slack_ns'), _f(m.get('timing__setup_r2r__ws'), o.WS0))
    o.port = bool(s.get('port_limited', False))
    o.hold = _f(s.get('worst_hold_slack_ns'), _f(m.get('timing__hold__ws'), 0.0))
    o.drc = _f(s.get('route_drc'), _f(m.get('route__drc_errors'), 0.0))
    drv = _f(s.get('drv_count'))
    if drv is None:
        drv = (_f(m.get('design__max_slew_violation__count'), 0.0) or 0.0) + \
              (_f(m.get('design__max_cap_violation__count'), 0.0) or 0.0)
    o.drv = drv
    o.bar = _f(c.get('judge', {}).get('drv_bar'))
    sp = s.get('passes_judge')
    if sp is None:
        sp = (o.WS0 >= 0 and o.hold >= 0 and o.drc == 0 and (o.bar is None or o.drv <= o.bar))
    o.spass = bool(sp)
    ch = c.get('chain', {})
    o.R1 = _f(ch.get('R1_ns'), _ceil05(o.C0))
    o.max_rebuilds = int(_f(ch.get('max_rebuilds'), 4))
    io = _f(c.get('constraints', {}).get('io_delay_pct_of_period'))
    o.io = IO_FRAC if io is None else io / 100.0
    return o


def _sfix(o, T):
    """Fixed-netlist structural slope: port paths scale with io fraction, reg-to-reg paths do not."""
    dT = T - o.T0
    if abs(dT) < 1e-9 or not o.port:
        return 0.0
    c_r2r = o.T0 - o.r2r
    c1 = max(c_r2r, o.C0 + o.io * dT)
    return (c1 - o.C0) / dT


def _slope(o, T):
    dT = T - o.T0
    if abs(dT) < 1e-9:
        return 0.0
    relax = 1.0 if dT > 0 else 0.0
    r = min(abs(dT) / max(o.C0, 1e-6), R_CLIP)
    s = B0 + B1 * relax + B2 * r + B3 * relax * r
    if not relax:
        s = max(s, _sfix(o, T))      # a tightening never loses the structural port-path slope
    return s


def _p_other(o):
    ratio = (o.drv / o.bar) if (o.bar and o.bar > 0) else 0.0
    z = max(-50.0, min(50.0, DRV_K * (ratio - DRV_R0)))
    p = P_CLEAN / (1.0 + math.exp(z))
    if o.hold < 0:
        p *= HOLD_BAD
    if o.drc and o.drc > 0:
        p *= DRC_BAD
    return p


def _claim(o, T):
    """Median predicted claimed clock of a rebuild at T (pass-model location)."""
    dT = T - o.T0
    if abs(dT) < 1e-9:
        return o.C0
    m = _slope(o, T) + (OFF_RELAX if dT > 0 else OFF_TIGHT)
    return o.C0 + m * dT


def _p_pass(o, T):
    dT = T - o.T0
    if abs(dT) < 1e-9:          # identical settings and clock: bit-identical rebuild
        return 0.995 if o.spass else 0.005
    sig = A_C0 * o.C0 + B_DT * abs(dT)
    z = (T - _claim(o, T)) / max(sig, 1e-6)
    p_setup = 1.0 / (1.0 + math.exp(-max(-50.0, min(50.0, z))))
    return p_setup * _p_other(o)


def _kept(o):
    """Most-likely path of the registered chain under the model (pass iff p >= 0.5)."""
    smallest = o.T0 if o.spass else None
    fails = []
    n = 0

    def run(T):
        return _p_pass(o, T) >= 0.5, _claim(o, T)

    def refine(C, n):
        nonlocal smallest
        while n < o.max_rebuilds:
            Tn = _ceil05(C)
            if smallest is not None and not (Tn < smallest - 1e-9):
                break
            if any(f < (smallest if smallest is not None else 1e18) - 1e-9 and Tn <= f + 1e-9 for f in fails):
                break
            ok, Cn = run(Tn)
            n += 1
            if ok:
                smallest = Tn
                C = Cn
            else:
                fails.append(Tn)
                break
        return n

    ok, C1 = run(o.R1)
    n = 1
    if ok:
        smallest = o.R1 if smallest is None else min(smallest, o.R1)
        refine(C1, n)
    else:
        fails.append(o.R1)
        T2 = max(_ceil05(C1), round(o.R1 + GRID, 4))
        if (smallest is None or T2 < smallest - 1e-9) and n < o.max_rebuilds:
            ok2, C2 = run(T2)
            n += 1
            if ok2:
                smallest = T2
                refine(C2, n)
    return None if smallest is None else round(smallest, 4)


def predict(run_dir: str) -> dict:
    c, m = _load(run_dir)
    o = _source(c, m)
    p = _p_pass(o, o.R1)
    p = min(max(p, 0.01), 0.99)
    call = 'pass' if p >= CALL_PASS else ('fail' if p <= CALL_FAIL else 'abstain')
    slope = _slope(o, o.R1)
    return {'p_pass': round(p, 4), 'call': call, 'slope': round(slope, 4), 'kept_clock_ns': _kept(o)}


if __name__ == '__main__':
    import sys
    for d in sys.argv[1:]:
        print(d, predict(d))
