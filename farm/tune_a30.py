#!/usr/bin/env python3
"""Addendum 30: one AI-found setting as a fixed default on held-out designs (route merge #5).

Seven open designs no study had run (designs/{xtea,zipdiv,usb_cdc_core,wbqspiflash,cic_decimator,APU,PPU}, from the
same OpenLane v0.21 commit as the other designs) each get: arm d (stock configuration) and arm e (Addendum 24's expert
preset) at 1.0, 0.85, 0.7, 0.6, 0.5 x the default clock; arm z = the 8 settings frozen for Addendum 27
(results/tune_x4/sources.json), applied unchanged with the clock = the source's fraction x the default. The primary
setting under test is the one the tuner found on MD5 (frozen source of Addendum 27). Objective and feasibility as
Addendum 24 with Amendment 24.1 (electrical reference: the design's stock run at its default clock, x6d-<design>-001,
with Amendment 27.1's fallback). Confirmation (Addendum 29 rule): MD5's run and the best z run, once all z runs of the
design have landed, are re-run once at T_eff rounded up to 0.05 ns. Tags x6<arm>-<design>-<nnn>.
Usage: tune_a30.py --init | --step | --confirm | --report [--json f] [--dry-run]
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

A.PREFIX = "x6"
A.TUNE = os.path.join(T.ROOT, "results", "tune_x6")
A.STATE = os.path.join(A.TUNE, "state.json")
HELD = {"xtea": 26.03, "zipdiv": 19.09, "usb_cdc_core": 15.6, "wbqspiflash": 18.86, "cic_decimator": 10.0, "APU": 17.0,
        "PPU": 18.0}
A.NEW = dict(HELD)
A.TUNED = {}
A.DESIGNS = {d: {"dir": f"designs/{d}", "config": "config_sky130.json", "period": p} for d, p in HELD.items()}
SOURCES = os.path.join(T.ROOT, "results", "tune_x4", "sources.json")
PRIMARY = "md5"
SEED = 2030
MIN_SCORABLE = 4


def init():
    src = json.load(open(SOURCES))
    st = A.load(A.STATE, {"tags": {}})
    if st["tags"]:
        raise SystemExit("already initialised")
    per = []
    for d in HELD:
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
        # the stock reference first, then MD5's setting, then the rest interleaved
        zp = [t for t in z if st["tags"][t]["source_design"] == PRIMARY]
        zr = [t for t in z if t not in zp]
        seq = [base["d"][0]] + zp
        for j in range(max(len(zr), len(base["e"]))):
            seq += zr[j:j + 1] + base["e"][j:j + 1]
        seq += base["d"][1:]
        per.append(seq)
    A.save(st)
    jobs = T.interleave(per)
    A.send(st, [(jobs, 20)], f"Addendum 30: held-out designs, stock / expert / 8 frozen AI settings ({len(jobs)})")
    print(f"[a30] init: {len(jobs)} jobs")


def step():
    st = A.load(A.STATE, None)
    if st is None:
        print("[a30] not initialised")
        return
    told = A.tell_finished(st, A.DRY["on"])
    A.save(st)
    retry = [t for t, v in st["tags"].items() if v["status"] == "pending"]
    A.send(st, [(retry, 20)], f"Addendum 30: re-sent specs ({len(retry)})")
    print(f"[a30] step: told {told}, re-sent {len(retry)}")


def confirm():
    """Addendum 30 (Addendum 29 rule): once all z runs of a design have landed, one re-run of MD5's run (if feasible) and of
    the best feasible z run (if different), at T_eff rounded up to 0.05 ns."""
    st = A.load(A.STATE, None)
    if st is None:
        return
    covered = {v.get("source") for v in st["tags"].values() if v["arm"] == "c"}
    new = []
    for d in HELD:
        z = [(t, v) for t, v in st["tags"].items() if v["design"] == d and v["arm"] == "z"]
        if not z or any(v["status"] in ("dispatched", "pending") for _, v in z):
            continue
        ok = [(t, v) for t, v in z if v.get("feasible") and v.get("teff") is not None]
        picks = [tv for tv in ok if tv[1].get("source_design") == PRIMARY]
        if ok:
            picks.append(min(ok, key=lambda tv: tv[1]["teff"]))
        for tag, v in picks:
            if tag in covered:
                continue
            ov = dict(v["overrides"])
            ov["CLOCK_PERIOD"] = round(math.ceil(round(v["teff"] / 0.05, 6)) * 0.05, 2)
            t = A.next_tag(st, "c", d)
            A.add(st, t, d, "c", ov, source=tag, source_design=v.get("source_design"))
            new.append(t)
            covered.add(tag)
            print(f"[a30] {d}: {v.get('source_design')}'s setting {tag} (T_eff {v['teff']:.3f}) -> confirmation {t} at {ov['CLOCK_PERIOD']} ns")
    A.save(st)
    A.send(st, [(new, 10)], f"Addendum 30: confirmation re-runs ({len(new)})")


def best(vs):
    ok = [v for v in vs if v.get("feasible") and v.get("teff") is not None]
    return min(ok, key=lambda v: v["teff"]) if ok else None


def done(v):
    return v["status"] not in ("dispatched", "pending")


def report(js):
    st = A.load(A.STATE, {"tags": {}})
    A.tell_finished(st, dry=True)
    rows = st["tags"]
    out, per = {}, {}
    for d in HELD:
        arm = {a: [dict(v, tag=t) for t, v in rows.items() if v["design"] == d and v["arm"] == a] for a in "dezc"}
        n = {a: (sum(map(done, arm[a])), len(arm[a])) for a in arm}
        md5 = next((v for v in arm["z"] if v.get("source_design") == PRIMARY), None)
        b = {"d": best(arm["d"]), "e": best(arm["e"]), "z": best(arm["z"])}
        ea = min((v for v in arm["e"] if v.get("teff") is not None), key=lambda v: v["teff"], default=None)
        ref_ok = any(v["tag"].endswith("-001") and v.get("teff") is not None for v in arm["d"]) or \
            any(v.get("teff") is not None for v in arm["d"])
        complete = lambda a: n[a][0] == n[a][1] > 0
        tv = lambda v: None if v is None else v["teff"]
        res = {"A30a": None, "A30b": None, "A30c": None}
        m_ok = md5 is not None and done(md5) and md5.get("feasible") and md5.get("teff") is not None
        if complete("e") and md5 is not None and done(md5) and b["e"] is not None:
            res["A30a"] = bool(m_ok and md5["teff"] < 0.95 * b["e"]["teff"])
        if complete("d") and md5 is not None and done(md5) and b["d"] is not None:
            res["A30b"] = bool(m_ok and md5["teff"] < 0.90 * b["d"]["teff"])
        if complete("e") and complete("z") and b["e"] is not None:
            res["A30c"] = bool(b["z"] is not None and b["z"]["teff"] < 0.95 * b["e"]["teff"])
        per[d] = res
        conf = {v["tag"]: {"source": v.get("source"), "source_design": v.get("source_design"), "status": v["status"],
                           "clock": v["overrides"].get("CLOCK_PERIOD"), "teff": v.get("teff"), "wns": v.get("wns"),
                           "feasible": v.get("feasible"), "area": v.get("area")} for v in arm["c"]}
        wins = {}
        if complete("z"):
            okz = [v for v in arm["z"] if v.get("feasible") and v.get("teff") is not None]
            if okz:
                wins = {"best_source": min(okz, key=lambda v: v["teff"]).get("source_design")}
        out[d] = {"default": HELD[d], "landed": n, "scorable": ref_ok,
                  "best": {k: (None if v is None else {"tag": v["tag"], "teff": v["teff"], "area": v.get("area")}) for k, v in b.items()},
                  "md5": None if md5 is None else {"tag": md5["tag"], "status": md5["status"], "teff": md5.get("teff"),
                                                   "feasible": md5.get("feasible"), "area": md5.get("area"), "hold": md5.get("hold"),
                                                   "drv": md5.get("drv"), "drv_ref": md5.get("drv_ref")},
                  "e_any": None if ea is None else {"teff": ea["teff"], "drv": ea.get("drv"), "drv_ref": ea.get("drv_ref"),
                                                    "hold": ea.get("hold")},
                  "confirm": conf, **wins, **res}
        f = lambda x: "-" if x is None else f"{x:.2f}"
        print(f"== {d} (default {HELD[d]} ns): stock {f(tv(b['d']))} ({n['d'][0]}/{n['d'][1]}), expert {f(tv(b['e']))} "
              f"({n['e'][0]}/{n['e'][1]}), MD5's setting {f(tv(md5) if m_ok else None)}, best of 8 {f(tv(b['z']))} "
              f"({n['z'][0]}/{n['z'][1]}; from {wins.get('best_source')})  {res}")
    overall = {}
    for key, pool in (("A30a", lambda d: out[d]["best"]["e"] is not None), ("A30b", lambda d: True),
                      ("A30c", lambda d: out[d]["best"]["e"] is not None)):
        ds = [d for d in HELD if out[d]["scorable"] and pool(d)]
        dec = [d for d in ds if per[d][key] is not None]
        p = sum(1 for d in dec if per[d][key])
        pend = len(ds) - len(dec)
        need = math.ceil(2 * len(ds) / 3)
        allin = all(out[d]["landed"]["d"][0] == out[d]["landed"]["d"][1] and out[d]["landed"]["e"][0] == out[d]["landed"]["e"][1]
                    for d in HELD)
        if allin and len(ds) < MIN_SCORABLE:
            v = "not scorable"
        elif p >= need and pend == 0:
            v = "PASS"
        elif p + pend < need:
            v = "FAIL"
        else:
            v = "pending"
        overall[key] = f"{v} ({p} pass, {len(dec) - p} fail, {pend} pending; {need} of {len(ds)} needed)"
        print(f"  {key}: {overall[key]}")
    if js:
        json.dump({"designs": out, "per_design": per, "overall": overall}, open(js, "w"), indent=1, default=str)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--confirm", action="store_true")
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
    if a.confirm:
        confirm()
    if a.report:
        report(a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
