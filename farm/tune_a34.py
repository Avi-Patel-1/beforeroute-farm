#!/usr/bin/env python3
"""Addendum 34: an LLM rewrites RTL from the signoff critical path; original and rewrite are each taken to their
fixed-point clock (Amendment 32.2) under the same flow setting.

--design md5 (default): MD5 under its Addendum-31 ai_ring setting (x4c-md5-003's overrides; farm/agent_a34/md5/baseline.json).
--design zipdiv (the registered second design, run because MD5's loop finished before 12:00 UTC Oct 29): the ZipCPU divider
under x6z-zipdiv-001's overrides (farm/agent_a34/zipdiv/baseline.json), checked clock 8.59 ns (x8a-zipdiv-005), state
results/tune_x9z, tags x9o-zipdiv-<nnn> / x9r-zipdiv-<nnn>; reported, no criterion of its own. MD5's chains:
  orig        designs/md5 (original RTL). Its run at the checked clock already exists (x7k-md5-004, 16.05 ns, same
              overrides and RTL), so the chain starts from it; new runs are tagged x9o-md5-<nnn>.
  <variant>   designs/md5_a34_<variant>/ (a rewrite that passed farm/rtl34/verify.py); runs tagged x9r-md5-<nnn>.
Chain rule (Amendment 32.2): first run at 16.05 ns; then at ceil(T_eff of the last passing run / 0.05) * 0.05 ns while
that is lower than the last passing clock; stop at a miss (setup or feasibility), no decrease, or 4 runs. The chain's
fixed-point clock is the smallest passing clock. A34a: the rewrite's fixed-point clock <= 0.95 x the original's, with
standard-cell area (at those runs) <= 1.15 x; decided 20:30 UTC Oct 29.
Usage: tune_a34.py [--design md5|zipdiv] --variant NAME --src FILE --gate LOG | --step | --report [--json f] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tune as T  # noqa: E402
import tune_a27 as A  # noqa: E402  (load/save/now/send machinery)

# per design: state directory, the original RTL's existing run at the checked clock (seed) and where it is recorded,
# the RTL file name, and the license line for a variant's README
DESIGNS = {
    "md5": {"tune": "tune_x9", "seed_run": "x7k-md5-004", "seed_state": "tune_x7", "src": "md5.v",
            "about": "MD5 (OpenCores, LGPL; see the header of src/md5.v)"},
    "zipdiv": {"tune": "tune_x9z", "seed_run": "x8a-zipdiv-005", "seed_state": "tune_x8", "src": "zipdiv.v",
               "about": "The ZipCPU divider (Gisselquist Technology, GPL-3.0-or-later; a rewrite of designs/zipdiv/src/zipdiv.v "
                        "is a derivative work under the same license, see that file's header)"},
}
MAX_RUNS = 4


def configure(design):
    global DESIGN, CFG, BASE, START_CLOCK, REF, SEED_RUN
    DESIGN, CFG = design, DESIGNS[design]
    A.PREFIX = "x9"
    A.TUNE = os.path.join(T.ROOT, "results", CFG["tune"])
    A.STATE = os.path.join(A.TUNE, "state.json")
    BASE = json.load(open(os.path.join(T.ROOT, "farm", "agent_a34", design, "baseline.json")))
    START_CLOCK = BASE["checked_clock_ns"]             # md5 16.05 ns, zipdiv 8.59 ns
    REF = BASE["electrical_bar_slew_cap_pins"]         # the design's stock reference (Amendment 24.1)
    SEED_RUN = CFG["seed_run"]                         # the original RTL at the checked clock under these overrides


configure("md5")
DECIDE = dt.datetime(2026, 10, 29, 20, 30, tzinfo=dt.timezone.utc)


def ceil05(x):
    return round(math.ceil(round(x / 0.05, 6)) * 0.05, 2)


def state_path():
    return os.path.join(A.TUNE, "dry_state.json") if A.DRY["on"] else A.STATE


def save(st):
    os.makedirs(A.TUNE, exist_ok=True)
    p = state_path()
    json.dump(st, open(p + ".tmp", "w"), indent=1)
    os.replace(p + ".tmp", p)


def state():
    st = A.load(state_path(), None)
    if st is None:
        st = {"tags": {}, "variants": {"orig": {"dir": f"designs/{DESIGN}", "arm": "o"}}}
        rec = A.load(os.path.join(T.ROOT, "results", CFG["seed_state"], "state.json"), {"tags": {}})["tags"].get(SEED_RUN)
        assert rec and abs(rec["overrides"]["CLOCK_PERIOD"] - START_CLOCK) < 1e-9, "seed run missing"
        ov = {k: v for k, v in rec["overrides"].items() if k != "CLOCK_PERIOD"}
        assert ov == BASE["overrides"], "seed run's overrides differ from the baseline setting"
        st["tags"][SEED_RUN] = {"design": DESIGN, "variant": "orig", "arm": "o", "overrides": rec["overrides"],
                                "status": "dispatched", "asked_at": rec.get("asked_at"), "seed": True}
    return st


def write_spec(tag, ddir, ov):
    spec = {"tag": tag, "design": ddir, "config": "config_sky130.json", "overrides": {**T.FIXED, **ov}}
    out = os.path.join(A.TUNE, "dry_jobs") if A.DRY["on"] else os.path.join(T.ROOT, "farm", "jobs")
    os.makedirs(out, exist_ok=True)
    json.dump(spec, open(os.path.join(out, f"{tag}.json"), "w"), indent=1)


def next_tag(st, arm):
    n = sum(1 for t, v in st["tags"].items() if v["arm"] == arm and not v.get("seed")) + 1
    return f"x9{arm}-{DESIGN}-{n:03d}"


def tell(st):
    n = 0
    for tag, v in st["tags"].items():
        if v["status"] != "dispatched":
            continue
        status, teff, cons, m = T.outcome(tag, v["overrides"]["CLOCK_PERIOD"], REF)
        if status is None:
            continue
        v.update({"status": status, "teff": teff, "constraints": cons, "feasible": T.feasible(cons), "landed_at": A.now(),
                  "wns": m.get("timing__setup__ws"), "r2r_wns": m.get("timing__setup_r2r__ws"),
                  "area": m.get("design__instance__area__stdcell"), "hold": m.get("timing__hold__ws"),
                  "drc": m.get("route__drc_errors"), "drv": T.drv_count(m) if m else None, "drv_ref": REF})
        n += 1
    return n


def passed(v):
    return v.get("status") == "done" and v.get("feasible") and (v.get("wns") if v.get("wns") is not None else -1) >= 0


def chain(st, name):
    return sorted(((t, v) for t, v in st["tags"].items() if v.get("variant") == name),
                  key=lambda tv: (tv[1].get("asked_at") or "", tv[0]))


def next_clock(st, name):
    """(clock, done): the chain's next target, or done=True when the chain has finished."""
    runs = chain(st, name)
    if not runs:
        return START_CLOCK, False
    if any(v["status"] in ("pending", "dispatched") for _, v in runs):
        return None, False
    last = runs[-1][1]
    if not passed(last) or len(runs) >= MAX_RUNS:
        return None, True
    good = [v for _, v in runs if passed(v)]
    best_clock = min(v["overrides"]["CLOCK_PERIOD"] for v in good)
    nxt = ceil05(last["teff"])
    if nxt >= best_clock - 1e-9:
        return None, True
    return nxt, False


def step():
    st = state()
    told = tell(st)
    new = []
    for name, info in st["variants"].items():
        clk, done = next_clock(st, name)
        if clk is None:
            continue
        ov = dict(BASE["overrides"])
        ov["CLOCK_PERIOD"] = clk
        tag = next_tag(st, info["arm"])
        write_spec(tag, info["dir"], ov)
        st["tags"][tag] = {"design": DESIGN, "variant": name, "arm": info["arm"], "overrides": ov, "status": "pending",
                           "asked_at": A.now()}
        new.append(tag)
        print(f"[a34] {name}: run {tag} at {clk} ns")
    retry = [t for t, v in st["tags"].items() if v["status"] == "pending" and t not in new]
    save(st)
    A.send(st, [(retry + new, 4)], f"Addendum 34: fixed-point runs ({len(new)})" + (f", {len(retry)} re-sent" if retry else ""))
    if A.DRY["on"]:                                        # A.send marks dispatched but does not save in a dry run
        save(st)
    else:
        save(st)
    print(f"[a34] step: told {told}, asked {len(new)}, re-sent {len(retry)}")


def sh(cmd):
    return subprocess.run(cmd, cwd=T.ROOT, capture_output=True, text=True)


def variant(name, src, gate):
    if not re.fullmatch(r"r\d+", name):
        raise SystemExit("variant names are r1, r2, ...")
    st = state()
    if name in st["variants"]:
        raise SystemExit(f"variant {name} exists")
    body = open(src, "rb").read()
    sha = hashlib.sha256(body).hexdigest()
    g = open(gate).read()
    if "VERDICT: PASS" not in g or f"cand sha256 {sha}" not in g:
        raise SystemExit("the gate log does not show a PASS for this exact file; Addendum 34 runs only gated rewrites")
    ddir = f"designs/{DESIGN}_a34_{name}"
    root = os.path.join(A.TUNE, "dry_designs") if A.DRY["on"] else T.ROOT
    full = os.path.join(root, ddir)
    os.makedirs(os.path.join(full, "src"), exist_ok=True)
    shutil.copy(os.path.join(T.ROOT, "designs", DESIGN, "config_sky130.json"), os.path.join(full, "config_sky130.json"))
    open(os.path.join(full, "src", CFG["src"]), "wb").write(body)
    gate_py = "farm/rtl34/verify.py" if DESIGN == "md5" else f"farm/rtl34/verify_{DESIGN}.py"
    open(os.path.join(full, "README.md"), "w").write(
        f"{CFG['about']} rewritten by an LLM for Addendum 34 ({name}).\n"
        f"Gate ({gate_py}) log: farm/agent_a34/{DESIGN}/{os.path.basename(gate)}; source sha256 {sha}.\n")
    st["variants"][name] = {"dir": ddir, "arm": "r", "src_sha256": sha, "gate_log": gate, "added_at": A.now()}
    save(st)
    if A.DRY["on"]:
        print(f"[a34] dry run: variant {name} written under {full}")
        return
    r = sh(["git", "add", ddir, "farm/agent_a34"])
    if r.returncode:
        raise SystemExit(r.stderr)
    r = sh(["git", "commit", "-q", "-m", f"Addendum 34 ({DESIGN}): RTL variant {name} (gate PASS) with its prompt, reply and gate log, "
                                         f"committed before its runs\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
                                         f"Claude-Session: https://claude.ai/code/session_016XcZ7Zp4en4cWPeoAqbHJG"])
    print(r.stdout + r.stderr)
    sh(["git", "pull", "-q", "--rebase", "origin", "main"])
    print(sh(["git", "push", "-q", "origin", "HEAD:main"]).stderr or f"[a34] variant {name} committed and pushed")


def fixed_point(st, name):
    runs = chain(st, name)
    good = [v for _, v in runs if passed(v)]
    _, done = next_clock(st, name)
    if good:
        b = min(good, key=lambda v: v["overrides"]["CLOCK_PERIOD"])
        return {"kind": "checked", "clock": b["overrides"]["CLOCK_PERIOD"], "area": b.get("area"), "done": done}
    # a run that missed timing bounds the clock from below; a run the flow stopped (status "failed", no timing) does not
    miss = [v["overrides"]["CLOCK_PERIOD"] for _, v in runs if v.get("status") == "done"]
    stopped = [v["overrides"]["CLOCK_PERIOD"] for _, v in runs if v.get("status") == "failed"]
    if miss:
        return {"kind": "lower bound", "clock": max(miss), "area": None, "done": done}
    if stopped:
        return {"kind": "flow stopped", "clock": max(stopped), "area": None, "done": done}
    return {"kind": "open", "clock": None, "area": None, "done": done}


def report(js):
    st = state()
    tell(st)
    out = {"variants": {}, "runs": {}}
    for name in st["variants"]:
        out["variants"][name] = fixed_point(st, name)
        out["runs"][name] = [{"tag": t, "clock": v["overrides"]["CLOCK_PERIOD"], "status": v["status"], "teff": v.get("teff"),
                              "wns": v.get("wns"), "r2r_wns": v.get("r2r_wns"), "feasible": v.get("feasible"),
                              "area": v.get("area")} for t, v in chain(st, name)]
    o = out["variants"]["orig"]
    best = None
    for name, r in out["variants"].items():
        if name == "orig" or r["kind"] != "checked" or o["kind"] != "checked":
            continue
        win = r["clock"] <= 0.95 * o["clock"] + 1e-9 and (r["area"] or 1e18) <= 1.15 * (o["area"] or 0) + 1e-6
        r["A34a_win"] = win
        r["vs_orig_freq"] = round(o["clock"] / r["clock"], 4)
        if best is None or r["clock"] < best[1]["clock"]:
            best = (name, r)
    decided = dt.datetime.now(dt.timezone.utc) >= DECIDE
    w = bool(best and best[1].get("A34a_win"))
    out["A34a"] = (("PASS" if w else "FAIL") if decided else ("pending" if not w else "PASS")) + \
        (f" (best {best[0]}: {best[1]['clock']} vs {o['clock']} ns)" if best else " (no rewrite checked yet)")
    if DESIGN != "md5":                                # A34a is MD5's criterion; the second design is reported only
        out["A34a"] = None
        out["summary"] = (f"{DESIGN}, reported (no criterion): best {best[0]} {best[1]['clock']} vs {o['clock']} ns "
                          f"({best[1]['vs_orig_freq']}x), area {best[1]['area']} vs {o['area']}") if best else \
            f"{DESIGN}, reported (no criterion): no rewrite checked yet"
    for name, r in out["variants"].items():
        print(f"== {name}: {r}")
        for x in out["runs"][name]:
            print(f"     {x['tag']}: {x['clock']} ns {x['status']} T_eff {x['teff']} wns {x['wns']} feasible {x['feasible']} area {x['area']}")
    print("A34a:", out["A34a"]) if DESIGN == "md5" else print("A34 " + out["summary"])
    if js:
        json.dump(out, open(js, "w"), indent=1, default=str)
    save(st)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--design", default="md5", choices=sorted(DESIGNS))
    ap.add_argument("--variant")
    ap.add_argument("--src")
    ap.add_argument("--gate")
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    configure(a.design)
    A.DRY["on"] = a.dry_run
    T.DRY["on"] = a.dry_run
    if a.variant:
        variant(a.variant, a.src, a.gate)
    if a.step:
        step()
    if a.report:
        report(a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
