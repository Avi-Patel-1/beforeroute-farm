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
Usage: closure_a31.py --freeze | --init | --amend311 | --amend312 | --step | --refine | --report [--json f] [--dry-run]
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


HELD30 = {"xtea": 26.03, "zipdiv": 19.09, "usb_cdc_core": 15.6, "wbqspiflash": 18.86, "cic_decimator": 10.0, "APU": 17.0,
          "PPU": 18.0}
NEVER27 = ("chacha", "ldpcenc", "point_add", "salsa20", "sha512")
A.DESIGNS = {**A.DESIGNS, **{d: {"dir": f"designs/{d}", "config": "config_sky130.json", "period": p} for d, p in HELD30.items()}}
X6STATE = os.path.join(T.ROOT, "results", "tune_x6", "state.json")
X4STATE = os.path.join(T.ROOT, "results", "tune_x4", "state.json")


def ref_drv_x6(d):
    """Addendum 30's reference (Amendments 24.1 / 27.1 / 30.1): the design's first live stock run in registered clock order
    that reached signoff."""
    st = A.load(X6STATE, {"tags": {}})["tags"]
    ds = sorted(((v.get("frac", 1.0), t) for t, v in st.items() if v["design"] == d and v["arm"] == "d"
                 and v.get("status") != "superseded"), key=lambda x: -x[0])
    for _, t in ds:
        r = os.path.join(T.ROOT, "results", t)
        if not os.path.exists(os.path.join(r, "job.json")):
            return None
        m = A.load(os.path.join(r, "metrics.json"), {})
        if m.get("timing__setup__ws") is not None:
            return T.drv_count(m)
    return None


def ref_drv_a31(d):
    """The design's own electrical reference (its stock run at the default clock; Amendment 27.1's fallback for the
    never-tuned designs; Addendum 30's reference for the held-out designs)."""
    if d in HELD30:
        return ref_drv_x6(d)
    if d in NEVER27:
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


def amend312():
    """Amendment 31.2: the new-design points the slides quote, frozen per design (by rule) once every stock, expert, expert + RC
    and borrowed run of that design and its re-runs have landed, then closed like the others.
      held-out designs (Addendum 30): the stock flow's best, the expert preset's best, the expert + RC best, MD5's setting
        (its feasible re-run, else its feasible run) and the best borrowed setting (best feasible re-run, else best run) when
        that is a different setting;
      never-tuned designs (Addendum 27): the stock flow's best and the best borrowed setting (as above; Salsa20's is already
        a point).
    A point already run at ceil(T_eff/0.05)*0.05 ns with setup met and feasible is closed; an existing run of the same
    configuration at that clock is its closure run; every other point gets one run there (tags x7k-<design>-<nnn>).
    Idempotent: designs already frozen are skipped; designs still running wait for a later call."""
    data = json.load(open(POINTS))
    have = {(p["design"], p["point"]) for p in data["points"]}
    done_d = {p["design"] for p in data["points"] if p.get("amendment") == "31.2"}
    R = records()
    st = A.load(A.STATE, None)
    tv = lambda v: v["teff"]
    new_pts, jobs = [], []
    for d, path, arms_needed in [(d, X6STATE, "defz") for d in HELD30] + [(d, X4STATE, "dz") for d in NEVER27]:
        if d in done_d:
            continue
        live = {t: v for t, v in A.load(path, {"tags": {}})["tags"].items() if v["design"] == d and v.get("status") != "superseded"}
        arms = {a: [dict(v, tag=t) for t, v in live.items() if v["arm"] == a] for a in "defzc"}
        if not all(arms[a] for a in arms_needed) or any(v["status"] in ("dispatched", "pending")
                                                         for a in arms_needed + "c" for v in arms[a]):
            continue
        okz = [v for v in arms["z"] if v.get("feasible") and v.get("teff") is not None]
        md5z = next((v for v in okz if v.get("source_design") == "md5"), None) if d in HELD30 else None
        bz = min(okz, key=tv) if okz else None
        asked = {v.get("source") for v in arms["c"]}
        # the design's own re-runs (Addendum 30 --confirm / Addendum 27 --confirm-new) must have been asked and landed first
        if (md5z and md5z["tag"] not in asked) or (bz and bz["tag"] not in asked and d in HELD30):
            continue
        if d in NEVER27 and bz and not arms["c"]:
            continue
        cok = [v for v in arms["c"] if v.get("feasible") and v.get("teff") is not None]
        md5 = min((v for v in cok if md5z and v.get("source") == md5z["tag"]), key=tv, default=None) or md5z
        bor = min(cok, key=tv, default=None) or bz
        picks = [("stock", best(arms["d"]))]
        if d in HELD30:
            picks += [("expert", best(arms["e"])), ("expert_rc", best(arms["f"])), ("md5", md5)]
        if bor and not (md5 and A.strip(bor["overrides"]) == A.strip(md5["overrides"])):
            picks.append(("borrowed", bor))
        for name, b in picks:
            if not b or (d, name) in have:
                continue
            p = {"design": d, "point": name, "tag": b["tag"], "amendment": "31.2", "clock": b["overrides"]["CLOCK_PERIOD"],
                 "teff": b["teff"], "wns": b.get("wns"), "feasible": b.get("feasible"), "area": b.get("area"), "own_clock": own_clock(b)}
            p["needs_run"] = not (p["feasible"] and p["wns"] is not None and p["wns"] >= 0 and abs(p["clock"] - p["own_clock"]) < 1e-6)
            if p["needs_run"]:
                same = [t for t, v in R.items() if v.get("design") == d and v.get("overrides") and v.get("status") != "superseded"
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
            print(f"  {d:14s} {name:9s} {b['tag']:24s} clock {p['clock']:7.2f} T_eff {p['teff']:7.3f} -> "
                  f"{'run at ' + str(p['own_clock']) if p['needs_run'] else ('existing run ' + p['closure_existing'] if p.get('closure_existing') else 'closed at its clock')}")
    if not new_pts:
        print("[a31] amendment 31.2: no design ready")
        return
    if not A.DRY["on"]:
        data["points"] += new_pts
        data.setdefault("amended_31_2_at", []).append(A.now())
        json.dump(data, open(POINTS, "w"), indent=1)
    A.save(st)
    A.send(st, [(jobs, 20)], f"Addendum 31 (Amendment 31.2): closure runs of new-design points ({len(jobs)})")
    print(f"[a31] amendment 31.2: {len(new_pts)} points, {len(jobs)} jobs")


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


MAX_REFINE = 2


def cfg_key(d, ov):
    return (d, json.dumps(A.strip(ov or {}), sort_keys=True, default=str))


def refine():
    """Amendment 31.3 (all arms alike): a point not closed at its own clock gets up to two more runs of its configuration,
    one at a time, at c = max(ceil(T*/0.05)*0.05, f + 0.05), where T* is the largest T_eff among the configuration's runs that
    missed (setup or feasibility) at clocks below its current closed clock and f the largest such clock; only if c is below
    the current closed clock (or none closed yet). A configuration shared by several points is refined once."""
    pts = json.load(open(POINTS))["points"] if os.path.exists(POINTS) else []
    st = A.load(A.STATE, None)
    if st is None:
        return
    R = records()
    R.update(st["tags"])
    by_cfg = {}
    for t, v in R.items():
        if v.get("overrides") and v.get("design") and v.get("status") != "superseded":
            by_cfg.setdefault(cfg_key(v["design"], v["overrides"]), []).append(dict(v, tag=t))
    jobs, seen = [], set()
    for p in pts:
        src = R.get(p["tag"], {})
        key = cfg_key(p["design"], src.get("overrides"))
        if key in seen:
            continue
        seen.add(key)
        runs = by_cfg.get(key, [])
        if any(r.get("status") in ("dispatched", "pending") for r in runs):
            continue
        clk = lambda r: r["overrides"]["CLOCK_PERIOD"]
        ran = [r for r in runs if r.get("teff") is not None]
        if p.get("needs_run") and not p.get("closure_existing") and not any(
                r["tag"].startswith("x7k-") and abs(clk(r) - p["own_clock"]) < 1e-6 for r in runs):
            continue  # its first closure run has not been asked yet
        good = [r for r in ran if r.get("feasible") and r.get("wns") is not None and r["wns"] >= 0]
        cc = min((clk(r) for r in good), default=math.inf)
        if cc <= p["own_clock"] + 1e-6:
            continue
        nref = sum(1 for r in runs if r.get("refine"))
        if nref >= MAX_REFINE:
            continue
        gtags = {r["tag"] for r in good}
        missed = [r for r in ran if r["tag"] not in gtags and clk(r) < cc - 1e-6]
        if not missed:
            continue
        c = max(round(math.ceil(round(max(r["teff"] for r in missed) / 0.05, 6)) * 0.05, 2),
                round(max(clk(r) for r in missed) + 0.05, 2))
        if c >= cc - 1e-6 or any(abs(clk(r) - c) < 1e-6 for r in runs):
            continue
        ov = dict(src["overrides"])
        ov["CLOCK_PERIOD"] = c
        t = A.next_tag(st, "k", p["design"])
        A.add(st, t, p["design"], "k", ov, source=p["tag"], point=p["point"], refine=nref + 1)
        jobs.append(t)
        print(f"  {p['design']:14s} {p['point']:9s} refine {nref + 1}: closed clock {cc if cc < math.inf else '-'}, "
              f"largest missed T_eff {max(r['teff'] for r in missed):.3f} -> run at {c}")
    A.save(st)
    A.send(st, [(jobs, 20)], f"Addendum 31 (Amendment 31.3): closure refinement runs ({len(jobs)})")
    print(f"[a31] amendment 31.3: {len(jobs)} refinement runs")


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
    # a closure run still in flight for the same configuration (e.g. the ring and the 24-run tuner's best share a setting)
    pend_cfg = {(v["design"], json.dumps(A.strip(v.get("overrides") or {}), sort_keys=True, default=str))
                for t, v in st["tags"].items() if v["status"] in ("dispatched", "pending")}
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
        elif p["tag"] in pend_src or key in pend_cfg:
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
    ap.add_argument("--amend312", action="store_true")
    ap.add_argument("--refine", action="store_true")
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
    if a.amend312:
        amend312()
    if a.step:
        step()
    if a.refine:
        refine()
    if a.report:
        report(a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
