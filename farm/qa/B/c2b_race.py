#!/usr/bin/env python3
"""Workstream B, arm C2b (registered, docs/qa_week/B_PREREG.md): one fresh TPE race with frozen I/O, on the runner.

A race (design d, seed s) = an Optuna TPE study configured exactly as Addendum 35's plain arm b (farm/tune_a35.py
`study(d, "b", s, {})`: TPESampler(multivariate, group, constant_liar, n_startup_trials 8, seed seed35(d, s),
constraints_func on the trial's "constraints"), the sampler re-created with the same seed before every round, as A35's
code did), warm-started with Addendum 30's 8 start-set settings each re-run at its own target with frozen I/O (enqueued,
told their frozen outcome), then 4 rounds of 2 TPE runs with frozen I/O. Objective = claim T - WNS (failed runs: 2 x the
design's default period, as A35); constraints = [route DRC, -hold WS, slew/cap pins - reference] (farm/tune.py outcome).
Winner = best feasible claim among the 8 TPE runs (A35 arm_best); rebuilt with the registered chain (run_group.run_chain,
W = the winner's own frozen run). Every flow: run_group.run_flow (br/run_job.py in the pinned LibreLane image).
Records: results/<tag>/ per flow, results/races/<race>.json, results/chains/<chain_id>.json.
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(REPO, "farm"))
import blib  # noqa: E402

ROUNDS, PER_ROUND = 4, 2


def outcome(results, tag, period, ref):
    """farm/tune.py outcome(): (teff or None, constraints)."""
    m = {}
    try:
        m = json.load(open(os.path.join(results, tag, "metrics.json")))
    except Exception:
        m = {}
    ws = m.get("timing__setup__ws")
    if ws is None:
        return None, [1e3, 1e3, 1e3], m
    drc = m.get("route__drc_errors") or 0
    hold = m.get("timing__hold__ws")
    drv = sum((m.get(k) or 0) for k in blib.DRV_KEYS)
    cons = [float(drc), float(-(hold if hold is not None else -1.0)), float(drv - ref)]
    return float(period) - ws, cons, m


def write_base(tag, d, ov):
    """farm/tune.py write_spec(): the trial's job spec (T.FIXED + the sampled overrides)."""
    import tune as T
    spec = {"tag": tag, "design": f"designs/{d}", "config": "config_sky130.json", "overrides": {**T.FIXED, **ov}}
    p = os.path.join(REPO, "farm", "qa", "B", "specs", tag + "-base.json")
    os.makedirs(os.path.dirname(p), exist_ok=True)
    json.dump(spec, open(p, "w"), indent=1)
    return os.path.relpath(p, REPO)


def run_race(race: dict, image: str, results: str, timeout_s: int, run_flow, run_chain, budget_s, est_s):
    import optuna
    import tune_a35 as X                       # imports tune_a32 (B), tune_a27 (A), tune (T): knob space, seeds
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    d, s = race["design"], int(race["seed"])
    D, io0, Fb, ref = race["D"], race["io0"], race["F_best"], race["drv_ref"]
    held = X.B.HELD[d]
    seed = X.seed35(d, s)
    assert seed == race["seed35"], (seed, race["seed35"])

    def sampler():
        return optuna.samplers.TPESampler(multivariate=True, group=True, constant_liar=True,
                                          n_startup_trials=X.A.N_Z, seed=seed,
                                          constraints_func=lambda t: t.user_attrs.get("constraints", [1.0, 1.0, 1.0]))
    study = optuna.create_study(study_name=f"{d}-b{s}-frozen", sampler=sampler(), direction="minimize")
    trials = []
    rec = {"race": race["name"], "design": d, "seed": s, "seed35": seed, "D": D, "drv_ref": ref, "held": held,
           "optuna": optuna.__version__, "trials": trials, "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ",
                                                                                     time.gmtime())}

    def save():
        os.makedirs(os.path.join(results, "races"), exist_ok=True)
        json.dump(rec, open(os.path.join(results, "races", race["name"] + ".json"), "w"), indent=1, default=str)

    def flow(tag, base_rel, period):
        io_value = blib.io_pct(D, period, io0, Fb)
        run_flow(tag, base_rel, period, io_value, image, results, timeout_s)
        teff, cons, m = outcome(results, tag, period, ref)
        if teff is None:                       # registered: one retry with the same tag
            run_flow(tag, base_rel, period, io_value, image, results, timeout_s)
            teff, cons, m = outcome(results, tag, period, ref)
        return teff, cons, io_value
    # warm start: Addendum 30's 8 start settings, re-run at their own targets with frozen I/O, then enqueued + told
    for i, st0 in enumerate(race["start"], 1):
        tag = f"{race['tag_prefix']}z{i}"
        base_rel = st0["spec"]
        T0 = float(json.load(open(os.path.join(REPO, base_rel)))["overrides"]["CLOCK_PERIOD"])
        teff, cons, iov = flow(tag, base_rel, T0)
        study.enqueue_trial(st0["params"])
        tr = study.ask()
        ov = X.A.suggest(tr, d)
        assert abs(ov["CLOCK_PERIOD"] - T0) < 1e-6, (d, st0["tag"], ov["CLOCK_PERIOD"], T0)
        tr.set_user_attr("constraints", cons)
        tr.set_user_attr("start_tag", st0["tag"])
        study.tell(tr, teff if teff is not None else 2.0 * held)
        trials.append({"tag": tag, "kind": "start", "source": st0["tag"], "T": T0, "teff": teff, "constraints": cons,
                       "feasible": all(c <= 0 for c in cons), "io_pct": iov, "number": tr.number})
        save()
    # 4 rounds of 2 TPE runs (both asked before either runs: constant liar, as A35 asked a round at once)
    n = 0
    for k in range(1, ROUNDS + 1):
        study.sampler = sampler()
        asked = []
        for j in range(PER_ROUND):
            tr = study.ask()
            ov = X.A.suggest(tr, d)
            n += 1
            tag = f"{race['tag_prefix']}t{n}"
            asked.append((tr, ov, tag))
        for tr, ov, tag in asked:
            base_rel = write_base(tag, d, ov)
            teff, cons, iov = flow(tag, base_rel, float(ov["CLOCK_PERIOD"]))
            tr.set_user_attr("constraints", cons)
            study.tell(tr, teff if teff is not None else 2.0 * held)
            trials.append({"tag": tag, "kind": "tpe", "round": k, "params": dict(tr.params), "T": ov["CLOCK_PERIOD"],
                           "base_spec": base_rel, "teff": teff, "constraints": cons,
                           "feasible": all(c <= 0 for c in cons), "io_pct": iov, "number": tr.number})
            save()
    ok = [t for t in trials if t["kind"] == "tpe" and t["feasible"] and t["teff"] is not None]
    if not ok:
        rec["winner"] = None
        rec["note"] = "no feasible TPE run: no winner to rebuild"
        save()
        return rec
    w = min(ok, key=lambda t: (t["teff"], t["tag"]))
    rec["winner"] = w["tag"]
    W = blib.load_run(results, w["tag"], w["T"], ref)
    ch = {"chain_id": f"{race['tag_prefix']}k", "design": d, "source": w["tag"], "set": f"C2b race {race['name']}",
          "base_spec": w["base_spec"], "T0": w["T"], "D": D, "io0": io0, "F_best": Fb, "drv_ref": ref,
          "tag_prefix": f"{race['tag_prefix']}k", "group": race["name"], "group_params": race.get("group_params"),
          "frozen": True,
          "state": [{"tag": w["tag"], "period": w["T"], "claim": W["claim"], "pass": W["pass"], "ws": W["ws"],
                     "ws_r2r": W["ws_r2r"], "hold_ws": W["hold_ws"], "drc": W["drc"], "drv": W["drv"],
                     "port": W["port"], "io_pct": w["io_pct"], "status": W["status"]}]}
    save()
    rec["chain"] = run_chain(ch, image, results, timeout_s, budget_s, est_s, 1)
    rec["ended_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    save()
    return rec
