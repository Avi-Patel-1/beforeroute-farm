#!/usr/bin/env python3
"""Workstream L (docs/qa_week/L_PREREG.md): the finished loop, run hands-off on blocks the project never ran.

Everything runs on a GitHub runner; no step waits for a person or a model.
  prep  --block k            the block's stock reference run (the slew/cap bar) and Addendum 30's 8 start settings, each
                             at its own clock target; record results/prep/<k>.json
  arm   --block k --seed s --arm b|L
        b  plain Bayesian search exactly as Addendum 35's arm b: TPE, warm-started with the 8 start runs, 4 rounds of 2
        L  the loop: the four-line rule (farm/qa/C clib.script_pins: clock target at the floor, plus the best start
           run's synthesis strategy, RC model and utilization) pinned under the same TPE, ONE round of 2 runs
        then, for both: winner = best feasible claim among the arm's own TPE runs (A35 arm_best), rebuilt with the
        registered chain (farm/qa/B blib.chain_next, stock I/O budget, at most 4 rebuilds); for arm L the kept build is
        rebuilt once more with full signoff switched on. Record results/races/<name>.json
  smoke                      a cut-down pass over every code path on the smallest block (not scored)
Flows run through farm/qa/B/run_group.run_flow (br/run_job.py in the pinned LibreLane image), I/O budget untouched.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "farm", "qa", "B"))
sys.path.insert(0, os.path.join(REPO, "farm"))
import blib  # noqa: E402
import run_group as RG  # noqa: E402
import c2b_race as C2  # noqa: E402

SPEC = json.load(open(os.path.join(HERE, "blocks.json")))
PER_ROUND = 2
ROUNDS = {"b": 4, "L": 1}
SIGNOFF = {"RUN_MAGIC_DRC": True, "RUN_KLAYOUT_DRC": True, "RUN_LVS": True, "RUN_KLAYOUT_XOR": True}
SIGNOFF_KEYS = ("magic__drc_error__count", "klayout__drc_error__count", "design__lvs_error__count",
                "route__antenna_violation__count")
SIGNOFF_INFO = ("design__xor_difference__count", "magic__illegal_overlap__count", "antenna__violating__nets")


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def mock_flow(tag, base_spec, period, io_value, image, results, timeout_s):
    """Local dry run only (L_MOCK=1): a made-up flow so the driver's logic can be exercised without Docker."""
    spec_rel = RG.make_spec(tag, base_spec, period, io_value)
    ov = json.load(open(os.path.join(REPO, spec_rel)))["overrides"]
    base = json.load(open(os.path.join(REPO, base_spec)))
    P = json.load(open(os.path.join(REPO, base["design"], base["config"])))["CLOCK_PERIOD"]
    F = 0.5 * P * (1 + 0.004 * (ov.get("FP_CORE_UTIL", 35) - 35))
    claim = F + (0.35 if period < F else 0.6) * (period - F)
    os.makedirs(os.path.join(results, tag), exist_ok=True)
    m = {"timing__setup__ws": period - claim, "timing__setup_r2r__ws": period - claim + 0.03, "timing__hold__ws": 0.1,
         "route__drc_errors": 0, "design__max_slew_violation__count": 0, "design__max_cap_violation__count": 0,
         "design__instance__area__stdcell": 1000.0}
    if ov.get("RUN_MAGIC_DRC"):
        m.update({k: 0 for k in SIGNOFF_KEYS + SIGNOFF_INFO})
    json.dump(m, open(os.path.join(results, tag, "metrics.json"), "w"))
    json.dump({"status": "completed", "flow_completed": True, "flow_seconds": 1.0, "overrides": ov},
              open(os.path.join(results, tag, "job.json"), "w"))
    return {"tag": tag, "docker_rc": 0, "wall_s": 0.0}


if os.environ.get("L_MOCK"):
    RG.run_flow = mock_flow


def setup(block):
    import tune_a35 as X                       # tune_a32 (B), tune_a27 (A), tune (T): knob space and seeds
    b = SPEC["blocks"][block]
    d, P = b["design"], float(b["period"])
    X.B.HELD[d] = P
    X.A.DESIGNS[d] = {"dir": f"designs/{d}", "config": "config_sky130.json", "period": P}
    return X, d, P


def write_base(tag, d, ov):
    p = os.path.join(HERE, "specs", tag + "-base.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump({"tag": tag, "design": f"designs/{d}", "config": "config_sky130.json", "overrides": ov},
              open(p, "w"), indent=1)
    return os.path.relpath(p, REPO)


def flow(a, tag, base_rel, period, ref):
    RG.run_flow(tag, base_rel, period, None, a.image, a.results, a.timeout)
    teff, cons, m = C2.outcome(a.results, tag, period, ref if ref is not None else 0)
    if teff is None:                           # one retry with the same tag, as in workstream B
        RG.run_flow(tag, base_rel, period, None, a.image, a.results, a.timeout)
        teff, cons, m = C2.outcome(a.results, tag, period, ref if ref is not None else 0)
    return teff, cons, m


def prep(a, block, n_start=8, prefix="l"):
    X, d, P = setup(block)
    import tune as T
    pfx = f"{prefix}{block}-"
    out = {"block": block, "design": d, "period": P, "started_utc": now(), "start": []}
    path = os.path.join(a.results, "prep", f"{block}.json")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    base = write_base(pfx + "ref", d, dict(T.FIXED))
    teff, cons, m = flow(a, pfx + "ref", base, P, None)
    ref = None
    if m.get("timing__setup__ws") is not None and all(m.get(k) is not None for k in blib.DRV_KEYS):
        ref = int(sum(m.get(k) or 0 for k in blib.DRV_KEYS))
    out.update({"ref_tag": pfx + "ref", "ref_claim": teff, "drv_ref": ref})
    json.dump(out, open(path, "w"), indent=1)
    if ref is None:
        print(f"[l] {block}: the stock reference run has no metrics; stopping", flush=True)
        return 1
    for i, src in enumerate(SPEC["sources"][:n_start], 1):
        tag = f"{pfx}z{i}"
        ov = X.A.fixed(src["params"], d)
        base = write_base(tag, d, {**T.FIXED, **ov})
        teff, cons, m = flow(a, tag, base, float(ov["CLOCK_PERIOD"]), ref)
        out["start"].append({"tag": tag, "source": src["tag"], "params": src["params"], "T": ov["CLOCK_PERIOD"],
                             "base_spec": base, "teff": teff, "constraints": cons,
                             "feasible": all(c <= 0 for c in cons)})
        json.dump(out, open(path, "w"), indent=1)
        print(f"[l] start {tag}: T {ov['CLOCK_PERIOD']} claim {teff} feasible {out['start'][-1]['feasible']}", flush=True)
    out["ended_utc"] = now()
    json.dump(out, open(path, "w"), indent=1)
    return 0


def script_pins(start):
    """farm/qa/C/clib.script_pins on this block's start runs. Fallback (registered): if no start run is feasible, the
    lowest-claim start run of any kind."""
    ok = [(s["teff"], i) for i, s in enumerate(start) if s["teff"] is not None and s["feasible"]]
    if not ok:
        ok = [(s["teff"], i) for i, s in enumerate(start) if s["teff"] is not None]
    best = start[min(ok)[1]]["params"]
    return {"period_frac": 0.45, "SYNTH_STRATEGY": best["SYNTH_STRATEGY"], "RC_MODEL": best["RC_MODEL"],
            "FP_CORE_UTIL": best["FP_CORE_UTIL"]}


def arm(a, block, seed, x, rounds=None, max_rebuilds=blib.MAX_REBUILDS, prefix="l", smoke=False):
    import optuna
    import tune as T
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    X, d, P = setup(block)
    pr = json.load(open(os.path.join(a.results, "prep", f"{block}.json")))
    ref, start = pr["drv_ref"], pr["start"]
    assert ref is not None and start, "prep is incomplete"
    rounds = ROUNDS[x] if rounds is None else rounds
    name = f"{prefix}{block}{seed}{x.lower()}"
    pfx = name + "-"
    s35 = X.seed35(d, seed)
    pins = script_pins(start) if x == "L" else None

    def sampler(with_pins):
        sm = optuna.samplers.TPESampler(multivariate=True, group=True, constant_liar=True, n_startup_trials=X.A.N_Z,
                                        seed=s35, constraints_func=lambda t: t.user_attrs.get("constraints",
                                                                                              [1.0, 1.0, 1.0]))
        if with_pins and pins:
            sm = optuna.samplers.PartialFixedSampler(fixed_params=pins, base_sampler=sm)
        return sm
    study = optuna.create_study(study_name=name, sampler=sampler(False), direction="minimize")
    trials = []
    rec = {"race": name, "block": block, "design": d, "seed": seed, "arm": x, "seed35": s35, "pins": pins,
           "drv_ref": ref, "period": P, "rounds": rounds, "max_rebuilds": max_rebuilds, "optuna": optuna.__version__,
           "trials": trials, "started_utc": now(), "gh_run_id": os.environ.get("GITHUB_RUN_ID"),
           "gh_sha": os.environ.get("GITHUB_SHA")}
    path = os.path.join(a.results, "races", name + ".json")
    os.makedirs(os.path.dirname(path), exist_ok=True)

    def save():
        json.dump(rec, open(path, "w"), indent=1, default=str)
    for st0 in start:                          # warm start (A35 warm): enqueue, ask, tell the recorded outcome
        study.enqueue_trial(st0["params"])
        tr = study.ask()
        ov = X.A.suggest(tr, d)
        assert abs(ov["CLOCK_PERIOD"] - st0["T"]) < 1e-6, (st0["tag"], ov["CLOCK_PERIOD"], st0["T"])
        tr.set_user_attr("constraints", st0["constraints"])
        tr.set_user_attr("start_tag", st0["tag"])
        study.tell(tr, st0["teff"] if st0["teff"] is not None else 2.0 * P)
    n = 0
    for k in range(1, rounds + 1):
        study.sampler = sampler(True)
        asked = []
        for _ in range(PER_ROUND):
            tr = study.ask()
            ov = X.A.suggest(tr, d)
            n += 1
            asked.append((tr, ov, f"{pfx}t{n}"))
        for tr, ov, tag in asked:
            if pins:
                assert abs(tr.params["period_frac"] - 0.45) < 1e-12, tr.params
            base = write_base(tag, d, {**T.FIXED, **ov})
            teff, cons, m = flow(a, tag, base, float(ov["CLOCK_PERIOD"]), ref)
            tr.set_user_attr("constraints", cons)
            study.tell(tr, teff if teff is not None else 2.0 * P)
            trials.append({"tag": tag, "kind": "tpe", "round": k, "params": dict(tr.params), "T": ov["CLOCK_PERIOD"],
                           "base_spec": base, "teff": teff, "constraints": cons,
                           "feasible": all(c <= 0 for c in cons)})
            save()
            print(f"[l] {tag}: T {ov['CLOCK_PERIOD']} claim {teff} feasible {trials[-1]['feasible']}", flush=True)
    ok = [t for t in trials if t["feasible"] and t["teff"] is not None]
    if not ok:
        rec.update({"winner": None, "kept_clock": None, "note": "no feasible search run: no winner to rebuild",
                    "ended_utc": now()})
        save()
        return rec
    w = min(ok, key=lambda t: (t["teff"], t["tag"]))
    rec["winner"] = w["tag"]
    W = blib.load_run(a.results, w["tag"], w["T"], ref)
    ch = {"chain_id": pfx + "k", "design": d, "source": w["tag"], "set": f"L {name}", "base_spec": w["base_spec"],
          "T0": w["T"], "D": None, "io0": None, "F_best": None, "drv_ref": ref, "tag_prefix": pfx + "k",
          "group": name, "frozen": False, "max_rebuilds": max_rebuilds,
          "state": [{"tag": w["tag"], "period": w["T"], "claim": W["claim"], "pass": W["pass"], "ws": W["ws"],
                     "ws_r2r": W["ws_r2r"], "hold_ws": W["hold_ws"], "drc": W["drc"], "drv": W["drv"],
                     "port": W["port"], "io_pct": None, "status": W["status"]}]}
    save()
    res = RG.run_chain(ch, a.image, a.results, a.timeout, a.budget, a.est, 1)
    rec["chain"] = res
    rec["kept_clock"] = res["kept_clock"]
    rec["first_rebuild"] = res["first_rebuild"]
    save()
    target = res["kept_clock"] if res["kept_clock"] is not None else (w["T"] if smoke else None)
    if x == "L" and target is not None and not a.no_signoff:
        ov = dict(json.load(open(os.path.join(REPO, w["base_spec"])))["overrides"])
        ov.update(SIGNOFF)
        tag = pfx + "so"
        base = write_base(tag, d, ov)
        RG.run_flow(tag, base, float(target), None, a.image, a.results, a.timeout)
        r = blib.load_run(a.results, tag, float(target), ref)
        m = {}
        try:
            m = json.load(open(os.path.join(a.results, tag, "metrics.json")))
        except Exception:
            pass
        so = {k: m.get(k) for k in SIGNOFF_KEYS + SIGNOFF_INFO}
        rec["signoff"] = {"tag": tag, "clock": target, "judge_pass": r["pass"], "ws": r["ws"], "hold_ws": r["hold_ws"],
                          "drc": r["drc"], "drv": r["drv"], "status": r["status"], "metrics": so,
                          "clean": bool(r["pass"] and all(so[k] == 0 for k in SIGNOFF_KEYS))}
        print(f"[l] signoff {tag} at {target}: {rec['signoff']}", flush=True)
    rec["ended_utc"] = now()
    save()
    return rec


def smoke(a):
    """Every code path on the smallest block with a cut-down budget. Not scored; tags start with q."""
    if prep(a, "u", n_start=2, prefix="q"):
        return 1
    rl = arm(a, "u", 1, "L", rounds=1, max_rebuilds=1, prefix="q", smoke=True)
    rb = arm(a, "u", 1, "b", rounds=1, max_rebuilds=1, prefix="q", smoke=True)
    bad = []
    for r in (rl, rb):
        if not any(t["teff"] is not None for t in r["trials"]):
            bad.append(f"{r['race']}: no search run produced metrics")
        if r.get("winner") and "chain" not in r:
            bad.append(f"{r['race']}: no chain record")
    if rl.get("winner") and any((rl.get("signoff") or {}).get("metrics", {}).get(k) is None for k in SIGNOFF_KEYS):
        bad.append(f"signoff metrics missing: {rl.get('signoff')}")
    print("[l] smoke:", "OK" if not bad else bad, flush=True)
    return 1 if bad else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["prep", "arm", "smoke"])
    ap.add_argument("--block")
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--arm", choices=["b", "L"])
    ap.add_argument("--image", default="mock")
    ap.add_argument("--results", default="results")
    ap.add_argument("--timeout", type=int, default=9000)
    ap.add_argument("--budget", type=float, default=19000)
    ap.add_argument("--est", type=float, default=0)
    ap.add_argument("--no-signoff", action="store_true")
    a = ap.parse_args()
    a.results = os.path.abspath(a.results)
    os.makedirs(a.results, exist_ok=True)
    if a.cmd == "prep":
        return prep(a, a.block)
    if a.cmd == "arm":
        arm(a, a.block, a.seed, a.arm)
        return 0
    return smoke(a)


if __name__ == "__main__":
    raise SystemExit(main())
