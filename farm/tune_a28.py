#!/usr/bin/env python3
"""Addendum 28: AI at two levels - AI-written RTL x AI-tuned flow (route merge #4).

Five versions of the same 16-bit RVV vnclip per-element block (designs/clip16_*: h1 and h0 written by an AI coding agent,
packedclip, stickyround and native conventional; all proven equivalent), each run with: arm d (its own configuration) and
arm e (the expert preset) at 1.0, 0.85, 0.7, 0.6, 0.5 x the 10 ns default clock; arm z = the 8 settings frozen for
Addendum 27 (results/tune_x4/sources.json), applied with no search; arm w = 16 TPE trials warm-started from z (two
batches of 8, each asked once everything before it has been told). Objective and feasibility as Addendum 24 with
Amendment 24.1 (electrical reference: the version's stock run at 10 ns, x5d-<design>-001, with Amendment 27.1's fallback).
Tags x5<arm>-<design>-<nnn>. Usage: tune_a28.py --init | --step | --report [--json f] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tune as T  # noqa: E402
import tune_a27 as A  # noqa: E402  (machinery: suggest with the RC knob, studies, tells, specs, dispatch)

A.PREFIX = "x5"
A.TUNE = os.path.join(T.ROOT, "results", "tune_x5")
A.STATE = os.path.join(A.TUNE, "state.json")
RTL = {"clip16_h1": "ai", "clip16_h0": "ai", "clip16_packedclip": "conv", "clip16_stickyround": "conv",
       "clip16_native": "conv"}
A.NEW = {d: 10.0 for d in RTL}
A.TUNED = {}
A.DESIGNS = {d: {"dir": f"designs/{d}", "config": "config_sky130.json", "period": 10.0} for d in RTL}
N_Z, N_W, BATCH, SEED = 8, 16, 8, 2028
NEED_A, NEED_RTL = 4, 1
SOURCES = os.path.join(T.ROOT, "results", "tune_x4", "sources.json")


def init():
    src = json.load(open(SOURCES))
    st = A.load(A.STATE, {"tags": {}})
    if st["tags"]:
        raise SystemExit("already initialised")
    per = []
    for d in RTL:
        base = {"d": [], "e": []}
        for arm, preset in (("d", {}), ("e", T.EXPERT)):
            for f in T.FRACS:
                tag = A.next_tag(st, arm, d)
                A.add(st, tag, d, arm, {**preset, "CLOCK_PERIOD": round(A.DESIGNS[d]["period"] * f, 2)}, frac=f)
                base[arm].append(tag)
        s = A.study(d, A.seed_for(d, SEED))
        z = []
        for k, sd in enumerate(src["order"]):
            s.enqueue_trial(src["sources"][sd]["params"])
            tr = s.ask()
            tag = A.next_tag(st, "z", d)
            A.add(st, tag, d, "z", A.suggest(tr, d), trial=tr.number, source=src["sources"][sd]["tag"], source_design=sd, rank=k)
            z.append(tag)
        seq = [base["d"][0]]
        for j in range(max(len(z), len(base["e"]))):
            seq += z[j:j + 1] + base["e"][j:j + 1]
        seq += base["d"][1:]
        per.append(seq)
    A.save(st)
    jobs = T.interleave(per)
    A.send(st, [(jobs, 20)], f"Addendum 28: RTL x flow job specs ({len(jobs)})")
    print(f"[a28] init: {len(jobs)} jobs")


def step():
    st = A.load(A.STATE, None)
    if st is None:
        print("[a28] not initialised")
        return
    told = A.tell_finished(st, A.DRY["on"])
    A.save(st)
    retry = [t for t, v in st["tags"].items() if v["status"] == "pending"]
    new = []
    for d in RTL:
        mine = [v for v in st["tags"].values() if v["design"] == d and v["arm"] in ("z", "w")]
        w = [v for v in mine if v["arm"] == "w"]
        if len(w) >= N_W or sum(1 for v in mine if v["arm"] == "z") < N_Z:
            continue
        if any(v["status"] in ("dispatched", "pending") for v in mine):
            continue  # each batch waits for everything before it
        s = A.study(d, A.seed_for(d, SEED + 7 * len(mine)))
        for _ in range(min(BATCH, N_W - len(w))):
            tr = s.ask()
            tag = A.next_tag(st, "w", d)
            A.add(st, tag, d, "w", A.suggest(tr, d), trial=tr.number)
            new.append(tag)
    A.save(st)
    A.send(st, [(retry + new, 20)], f"Addendum 28: warm-start tuner trials ({len(new)})" + (f", {len(retry)} re-sent" if retry else ""))
    print(f"[a28] step: told {told}, asked {len(new)}, re-sent {len(retry)}")


def best(vs):
    ok = [v for v in vs if v.get("feasible") and v.get("teff") is not None]
    return min(ok, key=lambda v: v["teff"]) if ok else None


def done(v):
    return v["status"] not in ("dispatched", "pending")


def report(js):
    st = A.load(A.STATE, {"tags": {}})
    A.tell_finished(st, dry=True)
    rows = st["tags"]
    out = {}
    for d in RTL:
        arm = {a: [dict(v, tag=t) for t, v in rows.items() if v["design"] == d and v["arm"] == a] for a in "dezw"}
        b = {a: best(arm[a]) for a in arm}
        b["zw"] = best(arm["z"] + arm["w"])
        n = {a: (sum(map(done, arm[a])), len(arm[a])) for a in arm}
        out[d] = {"kind": RTL[d], "best": {k: (None if v is None else {"tag": v["tag"], "teff": v["teff"], "area": v.get("area"),
                                                                       "power": v.get("power")}) for k, v in b.items()},
                  "landed": n}
        f = lambda v: "-" if v is None else f"{v['teff']:.2f} ns / {v.get('area') or 0:.0f} um2"
        print(f"== {d} ({RTL[d]}): stock {f(b['d'])} ({n['d'][0]}/{n['d'][1]}), expert {f(b['e'])} ({n['e'][0]}/{n['e'][1]}), "
              f"transfer {f(b['z'])} ({n['z'][0]}/{n['z'][1]}), AI flow {f(b['zw'])} (w {n['w'][0]}/{n['w'][1]})")
    complete = lambda d, arms: all(out[d]["landed"][a][0] == out[d]["landed"][a][1] > 0 for a in arms) and \
        out[d]["landed"]["w"][1] == N_W
    INF = float("inf")
    tv = lambda d, k: (out[d]["best"][k] or {}).get("teff") or INF
    av = lambda d, k: (out[d]["best"][k] or {}).get("area") or INF
    # A28a: AI flow beats the expert preset by > 5% on >= 4 of 5 versions
    a = {d: ((tv(d, "zw") < INF and (tv(d, "e") == INF or (tv(d, "e") - tv(d, "zw")) / tv(d, "e") > 0.05))
             if complete(d, "dezw") else None) for d in RTL}
    pa, fa = sum(1 for x in a.values() if x is True), sum(1 for x in a.values() if x is False)
    va = "PASS" if pa >= NEED_A else ("FAIL" if fa > len(RTL) - NEED_A else "pending")
    allc = all(complete(d, "dezw") for d in RTL)
    ai = [d for d in RTL if RTL[d] == "ai"]
    cv = [d for d in RTL if RTL[d] == "conv"]
    vb = vc = "pending"
    detail = {}
    if allc:
        dai = min(ai, key=lambda d: tv(d, "zw"))
        dcv = min(cv, key=lambda d: tv(d, "zw"))
        # A28b: under the AI flow, the faster AI-written version is no more than 2% slower than the fastest conventional
        # version and its best run is smaller
        okb = tv(dai, "zw") <= 1.02 * tv(dcv, "zw") and av(dai, "zw") < av(dcv, "zw")
        vb = "PASS" if okb else "FAIL"
        # A28c: (AI RTL x AI flow) beats (conventional RTL x expert preset) by > 10% in T_eff
        dce = min(cv, key=lambda d: tv(d, "e"))
        okc = tv(dai, "zw") < INF and (tv(dce, "e") == INF or (tv(dce, "e") - tv(dai, "zw")) / tv(dce, "e") > 0.10)
        vc = "PASS" if okc else "FAIL"
        detail = {"ai_rtl": dai, "conv_rtl_ai_flow": dcv, "conv_rtl_expert": dce,
                  "teff": {"ai_x_ai": tv(dai, "zw"), "conv_x_ai": tv(dcv, "zw"), "conv_x_expert": tv(dce, "e")},
                  "area": {"ai_x_ai": av(dai, "zw"), "conv_x_ai": av(dcv, "zw")}}
    overall = {"A28a": f"{va} ({pa} pass, {fa} fail, {sum(1 for x in a.values() if x is None)} pending)",
               "A28b": vb, "A28c": vc}
    for k, v in overall.items():
        print(f"  {k}: {v}")
    if detail:
        print(f"  detail: {detail}")
    if js:
        json.dump({"designs": out, "per_design": a, "overall": overall, "detail": detail}, open(js, "w"), indent=1, default=str)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    A.DRY["on"] = a.dry_run
    T.DRY["on"] = a.dry_run
    if a.init:
        init()
    if a.step:
        step()
    if a.report:
        report(a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
