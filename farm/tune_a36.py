#!/usr/bin/env python3
"""Addendum 36, A36q: Claude's one-time rules at a quarter of the search budget.

For each Addendum 35 race, take the best feasible run among arm g's round-1 runs: 2 runs, each Claude's pins plus TPE's
first pick from the shared start set. Give it the same closure and re-run chain as Amendment 32.2:
  - closure at ceil05(T_eff), with up to 2 refinements after a miss;
  - then re-runs at each passing run's claim;
  - at most 4 runs in all.
Its fixed point is compared with arm b's 8-run fixed point from Addendum 35, with the same 2% margin.
When that round-1 run is already arm g's chained winner, its Addendum 35 chain is reused and no new runs are made.

State: results/tune_xa/a36_state.json. The Addendum 35 state is read only.
Tags: xaqk-<design>-<nnn> (closure), xaqc-<design>-<nnn> (re-runs).
Usage: tune_a36.py --step | --report [--json f]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tune_a35 as X  # noqa: E402

T, A, B = X.T, X.A, X.B
RACE = os.path.join(A.TUNE, "state.json")
STATE36 = os.path.join(A.TUNE, "a36_state.json")
A.STATE = STATE36          # A.save / A.send write this file from here on; the race state is only read


def race_state():
    return json.load(open(RACE))


def load():
    return A.load(STATE36, {"tags": {}})


def r1_best(race, d, s):
    rs = [dict(v, tag=t) for t, v in race["tags"].items()
          if v["design"] == d and v["arm"] == f"g{s}" and v.get("round") == 1]
    ok = [v for v in rs if v.get("feasible") and v.get("teff") is not None]
    return min(ok, key=lambda v: v["teff"]) if ok else None


def chain36(st, root):
    ks = [dict(v, tag=t) for t, v in st["tags"].items() if v["arm"] == "qk" and v.get("source") == root]
    cs = [dict(v, tag=t) for t, v in st["tags"].items() if v["arm"] == "qc" and v.get("root") == root]
    return ks, cs


def reused(race, d, s, b):
    gb, _ = X.arm_best(race, d, s, "g")
    return gb is not None and gb["tag"] == b["tag"]


def step():
    race, st = race_state(), load()
    told = X.tell(st)
    new = []
    for d, s in X.races():
        b = r1_best(race, d, s)
        if b is None or reused(race, d, s, b):
            continue
        ks, cs = chain36(st, b["tag"])
        if any(v["status"] in ("dispatched", "pending") for v in ks + cs):
            continue
        if not any(B.passed(v) for v in ks):
            if len(ks) > B.MAX_REFINE:
                continue
            if not ks:
                clk = B.ceil05(b["teff"])
            else:
                tm = [v["teff"] for v in ks if v.get("teff") is not None]
                last = max(v["overrides"]["CLOCK_PERIOD"] for v in ks)
                clk = max(B.ceil05(max(tm)) if tm else last + 0.05, round(last + 0.05, 2))
            ov = dict(b["overrides"])
            ov["CLOCK_PERIOD"] = clk
            tag = A.next_tag(st, "qk", d)
            A.add(st, tag, d, "qk", ov, source=b["tag"], source_arm=f"g{s}", params=b.get("params"))
            new.append(tag)
            print(f"[a36] {d} s{s}: round-1 best {b['tag']} T_eff {b['teff']:.3f} -> closure {tag} at {clk} ns")
            continue
        nxt = B.chain_next(st, ks + cs, B.MAX_CHAIN)
        if nxt is None:
            continue
        last, clk = nxt
        ov = dict(last["overrides"])
        ov["CLOCK_PERIOD"] = clk
        tag = A.next_tag(st, "qc", d)
        A.add(st, tag, d, "qc", ov, source=last["tag"], root=b["tag"], source_arm=f"g{s}", params=b.get("params"))
        new.append(tag)
        print(f"[a36] {d} s{s}: {last['tag']} passed at {last['overrides']['CLOCK_PERIOD']} -> re-run {tag} at {clk} ns")
    retry = [t for t, v in st["tags"].items() if v["status"] == "pending" and t not in new]
    A.save(st)
    A.send(st, [(retry + new, 20)], f"Addendum 36: quarter-budget closure/re-runs ({len(new)})"
           + (f", {len(retry)} re-sent" if retry else ""))
    inflight = sum(1 for v in st["tags"].values() if v["status"] in ("dispatched", "pending"))
    print(f"[a36] step: told {told}, asked {len(new)}, re-sent {len(retry)}, in flight {inflight}")



# ---------------------------------------------------------------- Amendment 36.2: zero search (z) and its control (y)
Z_FLOOR = 0.45


def start_best(d):
    """The best feasible start-set run on design d (lowest T_eff) and its Optuna params."""
    ok = [(v["teff"], t, p) for t, v, p in B.start_set(d) if T.feasible(v.get("constraints") or [1, 1, 1])
          and v.get("teff") is not None]
    teff, t, p = min(ok, key=lambda r: r[0])
    return t, dict(p)


def zero_params(race, d, s, x):
    """z: the best start setting with Claude's initial pins applied (race d, s); y: the same setting with only the
    hand-coded tight-clock pin (period_frac 0.45), one per design."""
    t, p = start_best(d)
    if x == "z":
        p.update(race["policies"][f"{d}|{s}|init"]["pins"])
    else:
        p["period_frac"] = Z_FLOOR
    return t, p


def roots(st, x, d, s=None):
    return [dict(v, tag=t) for t, v in st["tags"].items() if v["arm"] == x and v["design"] == d
            and (s is None or v.get("seed") == s)]


def chainz(st, x, root):
    ks = [dict(v, tag=t) for t, v in st["tags"].items() if v["arm"] == f"{x}k" and v.get("source") == root]
    cs = [dict(v, tag=t) for t, v in st["tags"].items() if v["arm"] == f"{x}c" and v.get("root") == root]
    return ks, cs


def advance(st, x, b, label, new):
    """Closure + re-run chain of root run b (Amendment 32.2's rules), arms <x>k / <x>c."""
    d = b["design"]
    ks, cs = chainz(st, x, b["tag"])
    if any(v["status"] in ("dispatched", "pending") for v in ks + cs):
        return
    if not (b.get("feasible") and b.get("teff") is not None):
        return
    if not any(B.passed(v) for v in ks):
        if len(ks) > B.MAX_REFINE:
            return
        if not ks:
            clk = B.ceil05(b["teff"])
        else:
            tm = [v["teff"] for v in ks if v.get("teff") is not None]
            last = max(v["overrides"]["CLOCK_PERIOD"] for v in ks)
            clk = max(B.ceil05(max(tm)) if tm else last + 0.05, round(last + 0.05, 2))
        ov = dict(b["overrides"])
        ov["CLOCK_PERIOD"] = clk
        tag = A.next_tag(st, f"{x}k", d)
        A.add(st, tag, d, f"{x}k", ov, source=b["tag"], params=b.get("params"))
        new.append(tag)
        print(f"[a36{x}] {label}: {b['tag']} T_eff {b['teff']:.3f} -> closure {tag} at {clk} ns")
        return
    nxt = B.chain_next(st, ks + cs, B.MAX_CHAIN)
    if nxt is None:
        return
    last, clk = nxt
    ov = dict(last["overrides"])
    ov["CLOCK_PERIOD"] = clk
    tag = A.next_tag(st, f"{x}c", d)
    A.add(st, tag, d, f"{x}c", ov, source=last["tag"], root=b["tag"], params=b.get("params"))
    new.append(tag)
    print(f"[a36{x}] {label}: {last['tag']} passed at {last['overrides']['CLOCK_PERIOD']} -> re-run {tag} at {clk} ns")


def stepz():
    race, st = race_state(), load()
    told = X.tell(st)
    new = []
    for d in X.DES:
        for x, seeds in (("z", X.SEEDS), ("y", [None])):
            for s in seeds:
                rs = roots(st, x, d, s)
                label = f"{d}" + (f" s{s}" if s else "")
                if not rs:
                    src, p = zero_params(race, d, s, x)
                    ov = A.fixed(p, d)
                    tag = A.next_tag(st, x, d)
                    A.add(st, tag, d, x, ov, seed=s, start_source=src, params=p)
                    new.append(tag)
                    print(f"[a36{x}] {label}: one run {tag} at {ov['CLOCK_PERIOD']} ns (start {src} + "
                          f"{'Claude pins' if x == 'z' else 'period_frac 0.45'})")
                    continue
                if rs[0]["status"] in ("dispatched", "pending"):
                    continue
                advance(st, x, rs[0], label, new)
    retry = [t for t, v in st["tags"].items() if v["status"] == "pending" and t not in new]
    A.save(st)
    A.send(st, [(retry + new, 20)], f"Addendum 36: zero-search runs ({len(new)})" + (f", {len(retry)} re-sent" if retry else ""))
    inflight = sum(1 for v in st["tags"].values() if v["status"] in ("dispatched", "pending"))
    print(f"[a36z] step: told {told}, asked {len(new)}, re-sent {len(retry)}, in flight {inflight}")


def fixedz(st, x, d, s=None):
    rs = roots(st, x, d, s)
    if not rs or rs[0]["status"] in ("dispatched", "pending"):
        return ("open", None, None)
    b = rs[0]
    if not (b.get("feasible") and b.get("teff") is not None):
        return ("none", None, b["tag"])
    ks, cs = chainz(st, x, b["tag"])
    landed = [v for v in ks + cs if v["status"] not in ("dispatched", "pending")]
    ok = [v["overrides"]["CLOCK_PERIOD"] for v in landed if B.passed(v)]
    if ok:
        return ("checked", min(ok), b["tag"])
    kl = [v for v in ks if v["status"] not in ("dispatched", "pending")]
    if len(kl) > B.MAX_REFINE:
        return ("lower bound", max(v["overrides"]["CLOCK_PERIOD"] for v in kl), b["tag"])
    return ("single", b["teff"], b["tag"])


def reportz(js):
    race, st = race_state(), load()
    rows, cnt = {}, {k: 0 for k in ("z>b", "b>z", "z>g", "g>z", "z>y", "y>z", "y>b", "b>y")}
    for d, s in X.races():
        z, y = fixedz(st, "z", d, s), fixedz(st, "y", d)
        fb, fg = X.fixed_point(race, d, s, "b"), X.fixed_point(race, d, s, "g")
        r = {"z": z, "y": y, "b": fb, "g": fg}
        for a_, va, b_, vb in (("z", z, "b", fb), ("z", z, "g", fg), ("z", z, "y", y), ("y", y, "b", fb)):
            r[f"{a_}>{b_}"], r[f"{b_}>{a_}"] = B.wins(va, vb), B.wins(vb, va)
            cnt[f"{a_}>{b_}"] += r[f"{a_}>{b_}"]
            cnt[f"{b_}>{a_}"] += r[f"{b_}>{a_}"]
        rows[f"{d}|s{s}"] = r
        print(f"{d} s{s}: z {z[0]} {z[1]} | y {y[0]} {y[1]} | b {fb[1]} | g {fg[1]} | z>b {r['z>b']} b>z {r['b>z']}")
    n = len(rows)
    a36z = cnt["z>b"] >= 5 and cnt["b>z"] <= 2
    print(f"A36z {'PASS' if a36z else 'FAIL'}: z beat b in {cnt['z>b']} of {n}, lost {cnt['b>z']}; vs g "
          f"{cnt['z>g']}/{cnt['g>z']}; vs y {cnt['z>y']}/{cnt['y>z']}; y vs b {cnt['y>b']}/{cnt['b>y']}")
    pend = [t for t, v in st["tags"].items() if v["status"] in ("dispatched", "pending") and v["arm"][0] in "zy"]
    if js:
        json.dump({"races": rows, "counts": cnt, "A36z": a36z, "pending": pend}, open(js, "w"), indent=1, default=str)

def fixed36(race, st, d, s):
    """(kind, clock, root tag) for the quarter-budget winner, as Addendum 35's fixed_point."""
    b = r1_best(race, d, s)
    if b is None:
        return ("none", None, None)
    if reused(race, d, s, b):
        return X.fixed_point(race, d, s, "g")
    ks, cs = chain36(st, b["tag"])
    landed = [v for v in ks + cs if v["status"] not in ("dispatched", "pending")]
    ok = [v["overrides"]["CLOCK_PERIOD"] for v in landed if B.passed(v)]
    if ok:
        return ("checked", min(ok), b["tag"])
    kl = [v for v in ks if v["status"] not in ("dispatched", "pending")]
    if len(kl) > B.MAX_REFINE:
        return ("lower bound", max(v["overrides"]["CLOCK_PERIOD"] for v in kl), b["tag"])
    return ("single", b["teff"], b["tag"])


def report(js):
    race, st = race_state(), load()
    rows, cnt = {}, {"q>b": 0, "b>q": 0, "q>g": 0, "g>q": 0, "q>f": 0, "f>q": 0}
    for d, s in X.races():
        q = fixed36(race, st, d, s)
        fb, fg, ff = (X.fixed_point(race, d, s, x) for x in "bgf")
        r = {"q": q, "b": fb, "g": fg, "f": ff, "reused": bool(r1_best(race, d, s) and reused(race, d, s, r1_best(race, d, s)))}
        for y, fy in (("b", fb), ("g", fg), ("f", ff)):
            r[f"q>{y}"], r[f"{y}>q"] = B.wins(q, fy), B.wins(fy, q)
            cnt[f"q>{y}"] += r[f"q>{y}"]
            cnt[f"{y}>q"] += r[f"{y}>q"]
        rows[f"{d}|s{s}"] = r
        print(f"{d} s{s}: q {q[0]} {q[1]} | b {fb[1]} | g {fg[1]} | f {ff[1]}"
              f"{' (reused A35 chain)' if r['reused'] else ''} | q>b {r['q>b']} b>q {r['b>q']}")
    n = len(rows)
    a36q = cnt["q>b"] >= 5 and cnt["b>q"] <= 2
    print(f"A36q {'PASS' if a36q else 'FAIL'}: q beat b in {cnt['q>b']} of {n}, lost {cnt['b>q']}, "
          f"tied {n - cnt['q>b'] - cnt['b>q']}; vs g {cnt['q>g']}/{cnt['g>q']}; vs f {cnt['q>f']}/{cnt['f>q']}")
    pend = [t for t, v in st["tags"].items() if v["status"] in ("dispatched", "pending")]
    if js:
        json.dump({"races": rows, "counts": cnt, "A36q": a36q, "pending": pend}, open(js, "w"), indent=1, default=str)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--zero", action="store_true", help="Amendment 36.2: zero-search arm z and its control y")
    a = ap.parse_args()
    if a.step:
        stepz() if a.zero else step()
    if a.report:
        reportz(a.json) if a.zero else report(a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
