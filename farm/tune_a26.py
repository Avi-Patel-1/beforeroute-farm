#!/usr/bin/env python3
"""Addendum 26: the AI tuner with early stopping at global route inside its loop (route merge #2).

Arm p on each of the 8 designs of Addenda 24 and 25, with that design's own search space: Optuna TPE as in Addendum 24
(8 random start-ups, <= 8 in flight, constraints), up to 48 trials. Every p job records its global-route proxy
(CLOCK_PERIOD - setup WS of the mid-PnR STA after global routing, br/run_job.py "prune"); once >= 8 of the arm's trials on a
design have a proxy, each new trial carries prune.above = the 30th percentile of those proxies (lower is better) and the
flow stops before detailed routing when its proxy is above it. Pruned trials are told to TPE as PRUNED (proxy as their
intermediate value). Compared with the design's full-fidelity tuner arm (x1t / x2t) at equal compute (flow seconds summed
in trial order). Usage: tune_a26.py --init | --step | --report [--json f] [--dry-run]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tune as T  # noqa: E402  (helpers only; this module keeps its own state and studies)

ROOT = T.ROOT
PREFIX = "x3"
TUNE = os.path.join(ROOT, "results", "tune_x3")
STATE = os.path.join(TUNE, "state.json")
A24 = {"picorv32": {"dir": "designs/picorv32", "config": "config_sky130.json", "period": 25.0},
       "aes_cipher": {"dir": "designs/aes_cipher", "config": "config_sky130.json", "period": 40.0},
       "y_huff": {"dir": "designs/y_huff", "config": "config_sky130.json", "period": 11.35}}
A25 = {"des": {"dir": "designs/des", "config": "config_sky130.json", "period": 20.0},
       "md5": {"dir": "designs/md5", "config": "config_sky130.json", "period": 37.05},
       "bm64": {"dir": "designs/bm64", "config": "config_sky130.json", "period": 20.0},
       "ocs_blitter": {"dir": "designs/ocs_blitter", "config": "config_sky130.json", "period": 18.2},
       "blabla": {"dir": "designs/blabla", "config": "config_sky130.json", "period": 65.0}}
DESIGNS = {**A24, **A25}
PARENT = {d: ("x1", os.path.join(ROOT, "results", "tune", "state.json")) for d in A24}
PARENT.update({d: ("x2", os.path.join(ROOT, "results", "tune_x2", "state.json")) for d in A25})
N_TRIALS, N_STARTUP, IN_FLIGHT, KEEP_Q, MIN_PROXIES, SEED = 48, 8, 8, 0.30, 8, 2026
NEED = 5
RC = {"stock": None,
      "cap213": json.load(open(os.path.join(ROOT, "farm", "rc", "sky130_cap213.json"))),
      "orfs": json.load(open(os.path.join(ROOT, "farm", "rc", "sky130_caporfs.json")))}
DRY = {"on": False}


def suggest(trial, d):
    T.DESIGNS.setdefault(d, DESIGNS[d])  # T.suggest reads the default period from T.DESIGNS
    ov = T.suggest(trial, d)
    if d in A25:  # Addendum 25's extended space
        rc = trial.suggest_categorical("RC_MODEL", ["stock", "cap213", "orfs"])
        if RC[rc] is not None:
            ov["LAYERS_RC"] = RC[rc]
    return ov


def load():
    return json.load(open(STATE)) if os.path.exists(STATE) else {"tags": {}}


def save(st):
    if DRY["on"]:
        return
    os.makedirs(TUNE, exist_ok=True)
    json.dump(st, open(STATE + ".tmp", "w"), indent=1)
    os.replace(STATE + ".tmp", STATE)


def study(d, seed):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(multivariate=True, group=True, constant_liar=True, n_startup_trials=N_STARTUP,
                                         seed=seed,
                                         constraints_func=lambda t: t.user_attrs.get("constraints", [1.0, 1.0, 1.0]))
    os.makedirs(TUNE, exist_ok=True)
    if DRY["on"]:
        DRY.setdefault("studies", {})
        if d not in DRY["studies"]:
            DRY["studies"][d] = optuna.create_study(study_name=f"{d}-p", sampler=sampler, direction="minimize")
        DRY["studies"][d].sampler = sampler
        return DRY["studies"][d]
    return optuna.create_study(study_name=f"{d}-p", storage=f"sqlite:///{os.path.join(TUNE, f'{d}-p.db')}",
                               sampler=sampler, direction="minimize", load_if_exists=True)


def seed_for(d, base):
    return base + zlib.crc32((d + "/p").encode()) % 100000


def next_tag(st, d):
    n = sum(1 for v in st["tags"].values() if v["design"] == d) + 1
    return f"{PREFIX}p-{d}-{n:03d}"


def write_spec(tag, d, ov, prune):
    spec = {"tag": tag, "design": DESIGNS[d]["dir"], "config": DESIGNS[d]["config"], "overrides": {**T.FIXED, **ov},
            "prune": {"above": prune}}
    out = os.path.join(TUNE, "dry_jobs") if DRY["on"] else os.path.join(ROOT, "farm", "jobs")
    os.makedirs(out, exist_ok=True)
    json.dump(spec, open(os.path.join(out, f"{tag}.json"), "w"), indent=1)


def job(tag):
    try:
        return json.load(open(os.path.join(ROOT, "results", tag, "job.json")))
    except Exception:
        return None


def ref_drv(d):
    pre, _ = PARENT[d]
    try:
        m = json.load(open(os.path.join(ROOT, "results", f"{pre}d-{d}-001", "metrics.json")))
    except Exception:
        return None
    return T.drv_count(m) if m.get("timing__setup__ws") is not None else None


def proxies(st, d):
    return sorted(v["gr_proxy"] for v in st["tags"].values()
                  if v["design"] == d and v.get("gr_proxy") is not None and v["status"] not in ("dispatched", "pending"))


def threshold(st, d):
    px = proxies(st, d)
    if len(px) < MIN_PROXIES:
        return None
    k = max(0, math.ceil(KEEP_Q * len(px)) - 1)
    return round(px[k], 4)


def tell_finished(st, dry):
    import optuna
    told = 0
    for tag, v in st["tags"].items():
        if v["status"] != "dispatched":
            continue
        j = job(tag)
        if j is None:
            continue
        d = v["design"]
        period = v["overrides"]["CLOCK_PERIOD"]
        v["gr_proxy"] = j.get("gr_proxy")
        v["flow_seconds"] = j.get("flow_seconds")
        if j.get("status") == "pruned":
            v.update({"status": "pruned", "teff": None, "constraints": None, "feasible": False, "landed_at": T.now()})
            outcome = ("pruned", None, None)
        else:
            ref = ref_drv(d)
            status, teff, cons, m = T.outcome(tag, period, ref)
            if status == "done" and ref is None:
                continue
            v.update({"status": status, "teff": teff, "constraints": cons, "feasible": T.feasible(cons),
                      "landed_at": T.now(), "area": m.get("design__instance__area__stdcell"),
                      "power": m.get("power__total"), "hold": m.get("timing__hold__ws"), "wns": m.get("timing__setup__ws"),
                      "drv": T.drv_count(m) if m else None, "drv_ref": ref})
            outcome = (status, teff, cons)
        if not dry:
            s = study(d, SEED)
            tid = s._storage.get_trial_id_from_study_id_trial_number(s._study_id, v["trial"])
            try:
                if v.get("gr_proxy") is not None:
                    s._storage.set_trial_intermediate_value(tid, 1, float(v["gr_proxy"]))
                if outcome[0] == "pruned":
                    s.tell(v["trial"], state=optuna.trial.TrialState.PRUNED)
                else:
                    s._storage.set_trial_user_attr(tid, "constraints", outcome[2])
                    s.tell(v["trial"], outcome[1] if outcome[1] is not None else 2.0 * DESIGNS[d]["period"])
            except Exception as e:  # already told
                print(f"[a26] tell {tag}: {e}")
        told += 1
    return told


def send(st, tags, msg, dry):
    if not tags:
        return
    if not T.commit_specs(tags, msg, dry):
        return
    for t in T.dispatch(tags, dry, 24):
        st["tags"][t]["status"] = "dispatched"
        st["tags"][t]["asked_at"] = T.now()
    save(st)


def ask(st, dry, init=False):
    new = []
    for d in DESIGNS:
        mine = [v for v in st["tags"].values() if v["design"] == d]
        inflight = sum(1 for v in mine if v["status"] in ("dispatched", "pending"))
        room = min((N_STARTUP if init else IN_FLIGHT) - inflight, N_TRIALS - len(mine))
        if room <= 0:
            continue
        thr = threshold(st, d)
        s = study(d, seed_for(d, SEED + 7 * len(mine)))
        for _ in range(room):
            tr = s.ask()
            ov = suggest(tr, d)
            tag = next_tag(st, d)
            write_spec(tag, d, ov, thr)
            st["tags"][tag] = {"design": d, "arm": "p", "trial": tr.number, "overrides": ov, "prune_above": thr,
                               "status": "pending", "asked_at": T.now()}
            new.append(tag)
    save(st)
    return new


def init(dry):
    st = load()
    new = ask(st, dry, init=True)
    send(st, new, f"Addendum 26: tuner-with-pruning start-up trials ({len(new)})", dry)
    print(f"[a26] init: {len(new)} jobs")


def step(dry):
    st = load()
    told = tell_finished(st, dry)
    save(st)
    retry = [t for t, v in st["tags"].items() if v["status"] == "pending"]
    new = ask(st, dry)
    send(st, retry + new, f"Addendum 26: tuner-with-pruning trials ({len(new)})", dry)
    print(f"[a26] step: told {told}, asked {len(new)}, re-sent {len(retry)}")


def parent_arm(d):
    pre, path = PARENT[d]
    try:
        tags = json.load(open(path))["tags"]
    except Exception:
        return []
    out = []
    for tag, v in tags.items():
        if v["arm"] == "t" and v["design"] == d:
            j = job(tag)
            out.append({**v, "tag": tag, "flow_seconds": (j or {}).get("flow_seconds")})
    return sorted(out, key=lambda v: v.get("trial") if v.get("trial") is not None else 1e9)


def report(js):
    st = load()
    tell_finished(st, dry=True)
    out, per = {}, {}
    for d in DESIGNS:
        t = parent_arm(d)
        t_done = [v for v in t if v["status"] not in ("dispatched", "pending")]
        t_complete = len(t) >= T.N_TRIALS and len(t_done) == len(t)
        t_ok = [v["teff"] for v in t if v.get("feasible")]
        t_best = min(t_ok) if t_ok else None
        t_budget = sum(v.get("flow_seconds") or 0 for v in t_done)
        p = sorted((v for v in st["tags"].values() if v["design"] == d), key=lambda v: v["trial"])
        cum, p_best_at, reached_at, best = 0.0, None, None, None
        for v in p:
            if v["status"] in ("dispatched", "pending"):
                break  # equal-compute accounting stops at the first trial still running (trial order)
            cum += v.get("flow_seconds") or 0
            if v.get("feasible") and (best is None or v["teff"] < best):
                best = v["teff"]
            if cum <= t_budget:
                p_best_at = best
            if reached_at is None and best is not None and t_best is not None and best <= t_best:
                reached_at = cum
        p_landed = sum(1 for v in p if v["status"] not in ("dispatched", "pending"))
        p_pruned = sum(1 for v in p if v["status"] == "pruned")
        enough = t_complete and (cum >= t_budget or p_landed >= N_TRIALS)
        a = b = None
        if enough:
            a = p_best_at is not None and (t_best is None or p_best_at < 0.99 * t_best)
            b = reached_at is not None and t_budget > 0 and reached_at <= 0.7 * t_budget
        per[d] = {"A26a": a, "A26b": b}
        out[d] = {"t_best": t_best, "t_budget_s": t_budget, "t_landed": len(t_done), "p_landed": p_landed,
                  "p_pruned": p_pruned, "p_compute_s": cum, "p_best_at_budget": p_best_at, "p_best": best,
                  "p_reached_t_best_at_s": reached_at}
        print(f"== {d}: tuner best {t_best} ({len(t_done)}/24, {t_budget / 3600:.1f} h); pruned-tuner {p_landed} landed "
              f"({p_pruned} pruned, {cum / 3600:.1f} h), best at equal compute {p_best_at}, overall best {best}")
    overall = {}
    for k in ("A26a", "A26b"):
        vals = [per[d][k] for d in per]
        pp, ff = sum(1 for x in vals if x is True), sum(1 for x in vals if x is False)
        overall[k] = ("PASS" if pp >= NEED else ("FAIL" if ff > len(vals) - NEED else "pending")) + \
            f" ({pp} pass, {ff} fail, {len(vals) - pp - ff} pending)"
        print(f"  {k}: {overall[k]}  " + ", ".join(f"{d}={per[d][k]}" for d in per))
    if js:
        json.dump({"designs": out, "per_design": per, "overall": overall}, open(js, "w"), indent=1, default=str)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    DRY["on"] = a.dry_run
    T.DRY["on"] = a.dry_run
    if a.init:
        init(a.dry_run)
    if a.step:
        step(a.dry_run)
    if a.report:
        report(a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
