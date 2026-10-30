#!/usr/bin/env python3
"""Addendum 35, design-level tracks: A35m (MD5 rewrite r2's chain continued past its cap), A35r (a second rewrite r3 from
r2's own signoff report, chained from r2's best passing clock) and A35x (RTL x flow cross on clip16, 4 runs).
State: results/tune_xa/md5_state.json. Tags xam-md5-<nnn>, xar-md5-<nnn>, xax-<design>-<nnn>.
Usage: tune_a35_md5.py --step | --variant-r3 --src FILE --gate LOG | --cross | --report [--json f] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tune as T  # noqa: E402
import tune_a27 as A  # noqa: E402
import tune_a34 as R  # noqa: E402  (MD5 baseline setting, electrical bar, ceil05, passed)

R.configure("md5")
STATE = os.path.join(T.ROOT, "results", "tune_xa", "md5_state.json")
X9 = os.path.join(T.ROOT, "results", "tune_x9", "state.json")
SEED_R2 = "x9r-md5-005"          # r2 at 10.60 ns, passing, the last run of Addendum 34's capped chain
CAP = 4
CROSS = [("clip16_h0", "x5c-clip16_h0-001"), ("clip16_h0", "x5c-clip16_stickyround-001"),
         ("clip16_stickyround", "x5c-clip16_stickyround-001"), ("clip16_stickyround", "x5c-clip16_h0-001")]
DRY = {"on": False}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load():
    st = A.load(STATE, None)
    if st is None:
        x9 = A.load(X9, {"tags": {}})["tags"]
        seed = dict(x9[SEED_R2])
        assert R.passed(seed) and abs(seed["overrides"]["CLOCK_PERIOD"] - 10.6) < 1e-9, "r2 seed run"
        st = {"tags": {SEED_R2: dict(seed, chain="r2", seed=True)},
              "variants": {"r2": {"dir": "designs/md5_a34_r2", "arm": "m"}}}
    if "orig" not in st["variants"]:          # Amendment 35.2: the original gets the same allowance, from its own chain
        x9 = A.load(X9, {"tags": {}})["tags"]
        for t in ("x7k-md5-004", "x9o-md5-001"):
            rec = x9[t]
            st["tags"][t] = {**rec, "design": "md5", "chain": "orig", "seed": True}
        st["variants"]["orig"] = {"dir": "designs/md5", "arm": "o"}
    return st


def save(st):
    if DRY["on"]:
        return
    os.makedirs(os.path.dirname(STATE), exist_ok=True)
    json.dump(st, open(STATE + ".tmp", "w"), indent=1)
    os.replace(STATE + ".tmp", STATE)


def spec(tag, ddir, ov):
    s = {"tag": tag, "design": ddir, "config": "config_sky130.json", "overrides": {**T.FIXED, **ov}}
    out = os.path.join(T.ROOT, "results", "tune_xa", "dry_jobs") if DRY["on"] else os.path.join(T.ROOT, "farm", "jobs")
    os.makedirs(out, exist_ok=True)
    json.dump(s, open(os.path.join(out, f"{tag}.json"), "w"), indent=1)


def next_tag(st, arm, d):
    n = sum(1 for v in st["tags"].values() if v.get("arm") == arm and v.get("design") == d and not v.get("seed")) + 1
    return f"xa{arm}-{d}-{n:03d}"


def tell(st):
    n = 0
    for tag, v in st["tags"].items():
        if v.get("status") != "dispatched":
            continue
        ref = R.REF if v["design"] == "md5" else None
        status, teff, cons, m = T.outcome(tag, v["overrides"]["CLOCK_PERIOD"], ref if ref is not None else 10 ** 6)
        if status is None:
            continue
        v.update({"status": status, "teff": teff, "constraints": cons, "feasible": T.feasible(cons), "landed_at": now(),
                  "wns": m.get("timing__setup__ws"), "r2r_wns": m.get("timing__setup_r2r__ws"),
                  "area": m.get("design__instance__area__stdcell"), "hold": m.get("timing__hold__ws"),
                  "drc": m.get("route__drc_errors"), "drv": T.drv_count(m) if m else None, "power": m.get("power__total")})
        n += 1
    return n


def chain(st, name):
    return sorted(((t, v) for t, v in st["tags"].items() if v.get("chain") == name),
                  key=lambda tv: (tv[1].get("asked_at") or "", tv[0]))


def r2_best(st):
    """r2's smallest passing clock over Addendum 34's chain and A35m."""
    x9 = A.load(X9, {"tags": {}})["tags"]
    ok = [v["overrides"]["CLOCK_PERIOD"] for v in x9.values() if v.get("variant") == "r2" and R.passed(v)]
    ok += [v["overrides"]["CLOCK_PERIOD"] for _, v in chain(st, "r2") if R.passed(v)]
    return min(ok)


def next_clock(st, name):
    """Amendment 35.2 rule (all A35 MD5 chains alike): after a passing run, re-run at ceil(T_eff/0.05)*0.05 while that is
    below the smallest passing clock and no failed clock lies in between; after a miss, re-run at max(ceil05(the miss's
    T_eff), missed clock + 0.05) while below the smallest passing clock, at most 2 such refinements; at most CAP new runs."""
    runs = chain(st, name)
    new = [v for _, v in runs if not v.get("seed")]
    if any(v.get("status") in ("pending", "dispatched") for _, v in runs):
        return None
    if not runs:
        return st["variants"][name]["start_clock"]
    if len(new) >= CAP:
        return None
    last = runs[-1][1]
    good = [v["overrides"]["CLOCK_PERIOD"] for _, v in runs if R.passed(v)]
    best = min(good) if good else float("inf")
    failed = [v["overrides"]["CLOCK_PERIOD"] for _, v in runs if v.get("status") == "done" and not R.passed(v)]
    if R.passed(last):
        nxt = R.ceil05(last["teff"])
        if nxt >= best - 1e-9 or any(f >= nxt - 1e-9 and f < best for f in failed):
            return None
        return nxt
    if last.get("teff") is None:
        return None
    refines = sum(1 for v in new if v.get("refine"))
    if refines >= 2:
        return None
    nxt = max(R.ceil05(last["teff"]), round(last["overrides"]["CLOCK_PERIOD"] + 0.05, 2))
    return nxt if nxt < best - 1e-9 else None


def send(st, tags, msg):
    if not tags:
        return
    if not T.commit_specs(tags, msg, DRY["on"]):
        return
    for t in T.dispatch(tags, DRY["on"], 8):
        st["tags"][t]["status"] = "dispatched"
        st["tags"][t]["asked_at"] = now()
    save(st)


def step():
    st = load()
    told = tell(st)
    new = []
    for name, info in st["variants"].items():
        clk = next_clock(st, name)
        if clk is None:
            continue
        ov = dict(R.BASE["overrides"])
        ov["CLOCK_PERIOD"] = clk
        tag = next_tag(st, info["arm"], "md5")
        spec(tag, info["dir"], ov)
        last = chain(st, name)[-1][1] if chain(st, name) else None
        st["tags"][tag] = {"design": "md5", "chain": name, "arm": info["arm"], "overrides": ov, "status": "pending",
                           "asked_at": now(), "refine": bool(last is not None and not R.passed(last))}
        new.append(tag)
        print(f"[a35md5] {name}: run {tag} at {clk} ns")
    retry = [t for t, v in st["tags"].items() if v.get("status") == "pending" and t not in new]
    save(st)
    send(st, retry + new, f"Addendum 35: MD5 chain runs ({len(new)})" + (f", {len(retry)} re-sent" if retry else ""))
    print(f"[a35md5] step: told {told}, asked {len(new)}, re-sent {len(retry)}")


def variant_r3(src, gate):
    """Register r3 (gate passed): designs/md5_a35_r3 = r2's directory with the new RTL; chain starts at r2's best clock."""
    st = load()
    if "r3" in st["variants"]:
        raise SystemExit("r3 exists")
    full = os.path.join(T.ROOT, "designs", "md5_a35_r3")
    if not DRY["on"]:
        if os.path.exists(full):
            shutil.rmtree(full)
        shutil.copytree(os.path.join(T.ROOT, "designs", "md5_a34_r2"), full, ignore=shutil.ignore_patterns("runs"))
        shutil.copy(src, os.path.join(full, "src", "md5.v"))
    sha = hashlib.sha256(open(src, "rb").read()).hexdigest()
    st["variants"]["r3"] = {"dir": "designs/md5_a35_r3", "arm": "r", "src_sha256": sha, "gate_log": gate,
                            "start_clock": r2_best(st), "added_at": now()}
    save(st)
    print(f"[a35md5] r3 registered, chain starts at {st['variants']['r3']['start_clock']} ns")


def cross():
    st = load()
    new = []
    for d, rec in CROSS:
        if any(v.get("cross") == [d, rec] for v in st["tags"].values()):
            continue
        ov = {k: v for k, v in json.load(open(os.path.join(T.ROOT, "farm", "jobs", f"{rec}.json")))["overrides"].items()
              if k not in T.FIXED}
        assert abs(ov["CLOCK_PERIOD"] - 4.25) < 1e-9
        tag = next_tag(st, "x", d)
        spec(tag, f"designs/{d}", ov)
        st["tags"][tag] = {"design": d, "cross": [d, rec], "arm": "x", "overrides": ov, "status": "pending", "asked_at": now()}
        new.append(tag)
        print(f"[a35x] {tag}: {d} with {rec}'s recipe at 4.25 ns")
    save(st)
    send(st, new, f"Addendum 35: RTL x flow cross on clip16 ({len(new)} runs)")


def report(js):
    st = load()
    out = {"r2_best_before": 10.6, "chains": {}, "cross": []}
    for name in st["variants"]:
        rows = [(t, v["overrides"]["CLOCK_PERIOD"], v.get("status"), v.get("wns"), v.get("feasible"), v.get("area"))
                for t, v in chain(st, name)]
        ok = [c for t, c, s, w, f, a in rows if s == "done" and f and w is not None and w >= 0]
        out["chains"][name] = {"runs": rows, "best": min(ok) if ok else None}
        print(f"== {name}: " + "; ".join(f"{t} {c} {s} wns {w} area {a}" for t, c, s, w, f, a in rows))
    for t, v in sorted(st["tags"].items()):
        if v.get("cross"):
            out["cross"].append({"tag": t, "rtl": v["cross"][0], "recipe": v["cross"][1], "status": v.get("status"),
                                 "wns": v.get("wns"), "hold": v.get("hold"), "drc": v.get("drc"), "drv": v.get("drv"),
                                 "area": v.get("area")})
            print(f"== cross {t}: {v['cross']} {v.get('status')} wns {v.get('wns')} area {v.get('area')}")
    if js:
        json.dump(out, open(js, "w"), indent=1, default=str)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--variant-r3", action="store_true")
    ap.add_argument("--src")
    ap.add_argument("--gate")
    ap.add_argument("--cross", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json")
    a = ap.parse_args()
    DRY["on"] = a.dry_run
    A.DRY["on"] = a.dry_run
    T.DRY["on"] = a.dry_run
    if a.variant_r3:
        variant_r3(a.src, a.gate)
    if a.cross:
        cross()
    if a.step:
        step()
    if a.report:
        report(a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
