#!/usr/bin/env python3
"""Addendum 31: operating-point closure, checking every quoted clock at that clock (reported without criterion).

A quoted point is a run whose effective period T_eff = clock period - worst setup slack is quoted on the slides:
  - per tuned design (Addenda 24-27): the stock flow's best run, the expert preset's best, the expert + RC best (Addendum 25
    arm f), the AI ring (best feasible re-run of the design's own AI settings), and the best feasible re-run of a borrowed
    setting;
  - per clip16 version (Addenda 28/29): the AI-flow re-run and the expert re-run;
  - Salsa20: the borrowed setting's re-run.
A point is already closed at its own clock when it was run at ceil(T_eff / 0.05) * 0.05 ns and met setup (slack >= 0)
while feasible. Every other point gets one run with the same configuration at ceil(T_eff / 0.05) * 0.05 ns
(tags x7k-<design>-<nnn>). Reported per point: its closed clock, the smallest clock among its checked runs at which the
run is feasible (Amendment 24.1, the design's own stock reference) and meets setup; area at that run.
Usage: closure_a31.py --freeze | --init | --step | --report [--json f] [--dry-run]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tune as T  # noqa: E402
import tune_a27 as A  # noqa: E402  (specs, dispatch, tells)

A.PREFIX = "x7"
A.TUNE = os.path.join(T.ROOT, "results", "tune_x7")
A.STATE = os.path.join(A.TUNE, "state.json")
POINTS = os.path.join(A.TUNE, "points.json")
CLIP = ("clip16_h1", "clip16_h0", "clip16_packedclip", "clip16_stickyround", "clip16_native")
A.DESIGNS = {**A.DESIGNS, **{d: {"dir": f"designs/{d}", "config": "config_sky130.json", "period": 10.0} for d in CLIP}}
PARENT = {"picorv32": "x1", "aes_cipher": "x1", "y_huff": "x1",
          "des": "x2", "md5": "x2", "bm64": "x2", "ocs_blitter": "x2", "blabla": "x2"}


def ref_tag(d):
    if d in PARENT:
        return f"{PARENT[d]}d-{d}-001"
    if d in CLIP:
        return f"x5d-{d}-001"
    return None


def ref_drv_a31(d):
    """The design's own electrical reference (its stock run at the default clock; Amendment 27.1's fallback for Salsa20)."""
    if d == "salsa20":
        for k in range(1, 6):
            m = A.load(os.path.join(T.ROOT, "results", f"x4d-{d}-{k:03d}", "metrics.json"), {})
            if m.get("timing__setup__ws") is not None:
                return T.drv_count(m)
        return None
    m = A.load(os.path.join(T.ROOT, "results", ref_tag(d), "metrics.json"), {})
    return T.drv_count(m) if m.get("timing__setup__ws") is not None else None


A.ref_drv = ref_drv_a31


def records():
    out = {}
    for p in glob.glob(os.path.join(T.ROOT, "results", "tune*", "state.json")):
        if os.path.abspath(p) == os.path.abspath(A.STATE):
            continue
        out.update(A.load(p, {"tags": {}}).get("tags", {}))
    return out


def own_clock(v):
    return round(math.ceil(round(v["teff"] / 0.05, 6)) * 0.05, 2)


def best(vs):
    ok = [v for v in vs if v.get("feasible") and v.get("teff") is not None]
    return min(ok, key=lambda v: v["teff"]) if ok else None


def freeze():
    """Fix the list of quoted points (written once, before any closure run)."""
    if os.path.exists(POINTS):
        raise SystemExit("points already frozen")
    R = records()
    tagged = lambda pred: [dict(v, tag=t) for t, v in R.items() if pred(t, v)]
    pts = []
    for d, pre in PARENT.items():
        arm = lambda a: tagged(lambda t, v: t.startswith(f"{pre}{a}-{d}-"))
        for name, a in (("stock", "d"), ("expert", "e"), ("expert_rc", "f")):
            b = best(arm(a))
            if b:
                pts.append({"design": d, "point": name, "tag": b["tag"]})
        own = tagged(lambda t, v: v.get("design") == d and v.get("arm") == "c" and not v.get("transfer")
                     and t[:2] in ("x1", "x2", "x4"))
        b = best(own)
        if b:
            pts.append({"design": d, "point": "ai_ring", "tag": b["tag"]})
        bor = tagged(lambda t, v: v.get("design") == d and v.get("arm") == "c" and v.get("transfer") and t.startswith("x4"))
        b = best(bor)
        if b:
            pts.append({"design": d, "point": "borrowed", "tag": b["tag"]})
    for d in CLIP:
        for c in tagged(lambda t, v: t.startswith(f"x5c-{d}-")):
            pts.append({"design": d, "point": "ai_flow" if c.get("of") == "AI flow" else "expert", "tag": c["tag"]})
    b = best(tagged(lambda t, v: v.get("design") == "salsa20" and v.get("arm") == "c" and v.get("transfer")))
    if b:
        pts.append({"design": "salsa20", "point": "borrowed", "tag": b["tag"]})
    for p in pts:
        v = R[p["tag"]]
        p.update({"clock": v["overrides"]["CLOCK_PERIOD"], "teff": v["teff"], "wns": v.get("wns"), "feasible": v.get("feasible"),
                  "area": v.get("area"), "own_clock": own_clock(v)})
        p["needs_run"] = not (p["feasible"] and p["wns"] is not None and p["wns"] >= 0 and abs(p["clock"] - p["own_clock"]) < 1e-6)
    os.makedirs(A.TUNE, exist_ok=True)
    if not A.DRY["on"]:
        json.dump({"frozen_at": A.now(), "points": pts}, open(POINTS, "w"), indent=1)
    print(f"[a31] {len(pts)} quoted points, {sum(p['needs_run'] for p in pts)} need a closure run")
    for p in pts:
        print(f"  {p['design']:20s} {p['point']:10s} {p['tag']:28s} clock {p['clock']:7.2f} T_eff {p['teff']:7.3f} "
              f"wns {p['wns'] if p['wns'] is None else round(p['wns'], 3)} -> {'run at ' + str(p['own_clock']) if p['needs_run'] else 'closed at its clock'}")
    return pts


def amend311():
    """Amendment 31.1: add the budget-matched pair per tuned design, the 24-run AI tuner's best (arm t) and random search's
    best (arm r), as quoted points; closure runs as for the others."""
    data = json.load(open(POINTS))
    if any(p.get("amendment") == "31.1" for p in data["points"]):
        raise SystemExit("already amended")
    R = records()
    st = A.load(A.STATE, None)
    new_pts, jobs = [], []
    for d, pre in PARENT.items():
        for name, a in (("tuner24", "t"), ("random24", "r")):
            b = best([dict(v, tag=t) for t, v in R.items() if t.startswith(f"{pre}{a}-{d}-")])
            if not b:
                continue
            p = {"design": d, "point": name, "tag": b["tag"], "amendment": "31.1", "clock": b["overrides"]["CLOCK_PERIOD"],
                 "teff": b["teff"], "wns": b.get("wns"), "feasible": b.get("feasible"), "area": b.get("area"), "own_clock": own_clock(b)}
            p["needs_run"] = not (p["feasible"] and p["wns"] is not None and p["wns"] >= 0 and abs(p["clock"] - p["own_clock"]) < 1e-6)
            if p["needs_run"]:
                # an earlier run of the same configuration at this clock (e.g. the Addendum 24/25 confirmation of the tuner's
                # best) is that closure run already: the flow is deterministic, so it is not run twice
                same = [t for t, v in R.items() if v.get("design") == d and v.get("overrides")
                        and A.strip(v["overrides"]) == A.strip(b["overrides"])
                        and abs(v["overrides"].get("CLOCK_PERIOD", -1) - p["own_clock"]) < 1e-6 and v.get("teff") is not None]
                if same:
                    p["needs_run"] = False
                    p["closure_existing"] = same[0]
            new_pts.append(p)
            if p["needs_run"]:
                ov = dict(b["overrides"])
                ov["CLOCK_PERIOD"] = p["own_clock"]
                t = A.next_tag(st, "k", d)
                A.add(st, t, d, "k", ov, source=b["tag"], point=name)
                jobs.append(t)
            print(f"  {d:12s} {name:9s} {b['tag']:24s} clock {p['clock']:7.2f} T_eff {p['teff']:7.3f} -> "
                  f"{'run at ' + str(p['own_clock']) if p['needs_run'] else ('existing run ' + p['closure_existing'] if p.get('closure_existing') else 'closed at its clock')}")
    if not A.DRY["on"]:
        data["points"] += new_pts
        data["amended_31_1_at"] = A.now()
        json.dump(data, open(POINTS, "w"), indent=1)
    A.save(st)
    A.send(st, [(jobs, 20)], f"Addendum 31 (Amendment 31.1): closure runs of the 24-run tuner's and random search's bests ({len(jobs)})")
    print(f"[a31] amendment 31.1: {len(new_pts)} points, {len(jobs)} jobs")


def init():
    pts = json.load(open(POINTS))["points"] if os.path.exists(POINTS) else freeze()
    R = records()
    st = A.load(A.STATE, {"tags": {}})
    if st["tags"]:
        raise SystemExit("already initialised")
    jobs = []
    for p in pts:
        if not p["needs_run"]:
            continue
        ov = dict(R[p["tag"]]["overrides"])
        ov["CLOCK_PERIOD"] = p["own_clock"]
        t = A.next_tag(st, "k", p["design"])
        A.add(st, t, p["design"], "k", ov, source=p["tag"], point=p["point"])
        jobs.append(t)
    A.save(st)
    A.send(st, [(jobs, 20)], f"Addendum 31: closure runs at each quoted point's own clock ({len(jobs)})")
    print(f"[a31] init: {len(jobs)} jobs")


def step():
    st = A.load(A.STATE, None)
    if st is None:
        print("[a31] not initialised")
        return
    told = A.tell_finished(st, A.DRY["on"])
    A.save(st)
    retry = [t for t, v in st["tags"].items() if v["status"] == "pending"]
    A.send(st, [(retry, 20)], f"Addendum 31: re-sent specs ({len(retry)})")
    print(f"[a31] step: told {told}, re-sent {len(retry)}")


def report(js):
    """Per point: the closed clock of its configuration = the smallest clock at which any run of exactly that configuration
    (same design, same overrides apart from the clock; the flow is deterministic) met setup and the feasibility rule.
    Status: closed at (or below) the quoted point's own clock; closed only at a looser clock; or not closed / pending."""
    pts = json.load(open(POINTS))["points"] if os.path.exists(POINTS) else []
    st = A.load(A.STATE, {"tags": {}})
    A.tell_finished(st, dry=True)
    R = records()
    R.update(st["tags"])
    by_cfg = {}
    for t, v in R.items():
        if v.get("overrides") and v.get("design") and v.get("teff") is not None and v.get("status") not in ("dispatched", "pending", "superseded"):
            key = (v["design"], json.dumps(A.strip(v["overrides"]), sort_keys=True, default=str))
            by_cfg.setdefault(key, []).append(dict(v, tag=t))
    pend_src = {v.get("source") for t, v in st["tags"].items() if v["status"] in ("dispatched", "pending")}
    out = []
    for p in pts:
        src = R.get(p["tag"], {})
        key = (p["design"], json.dumps(A.strip(src.get("overrides") or {}), sort_keys=True, default=str))
        runs = by_cfg.get(key, [])
        ok = sorted((r["overrides"]["CLOCK_PERIOD"], r.get("area"), r["tag"], r.get("wns")) for r in runs
                    if r.get("feasible") and r.get("wns") is not None and r["wns"] >= 0)
        cc = ok[0] if ok else None
        if cc is not None and cc[0] <= p["own_clock"] + 1e-6:
            status = "closed at its own clock"
        elif p["tag"] in pend_src:
            status = "pending"
        elif cc is not None:
            status = "closed only at a looser clock"
        else:
            status = "not closed"
        out.append({**p, "status": status, "runs_checked": len(runs), "closed_clock": None if cc is None else cc[0],
                    "closed_area": None if cc is None else cc[1], "closed_tag": None if cc is None else cc[2],
                    "closed_wns": None if cc is None else cc[3]})
        f = lambda x: "-" if x is None else f"{x:.2f}"
        print(f"{p['design']:20s} {p['point']:10s} quoted {p['teff']:7.3f} (own clock {p['own_clock']:6.2f}) -> {status:30s} "
              f"closed clock {f(out[-1]['closed_clock'])}  ({len(runs)} runs of this setting)")
    if js:
        json.dump({"points": out}, open(js, "w"), indent=1, default=str)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--amend311", action="store_true")
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    A.DRY["on"] = a.dry_run
    T.DRY["on"] = a.dry_run
    if a.freeze:
        freeze()
    if a.init:
        init()
    if a.amend311:
        amend311()
    if a.step:
        step()
    if a.report:
        report(a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
