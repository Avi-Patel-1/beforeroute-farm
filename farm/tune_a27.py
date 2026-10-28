#!/usr/bin/env python3
"""Addendum 27: learn once, reuse - transfer of the AI-found flow settings across designs (route merge #3).

Sources: for each of the 8 tuned designs of Addenda 24-26, the feasible configuration with the lowest effective clock
period found by an AI arm (tuner t, or tuner with early stopping p), frozen by --freeze into results/tune_x4/sources.json
together with the pre-registered order (largest gain over the design's own best stock run first).
 1. Unseen designs (never tuned): arms d (stock) and e (expert preset) at 5 clock periods; arm z = the 8 source settings
    (zero-shot transfer: trials 0-7 of a TPE study, enqueued; clock = the source's fraction of this design's default
    period); arm w = 8 more TPE trials, asked once every z trial has been told (warm start). Electrical reference x4d-<d>-001.
 2. Leave-one-out on the 8 tuned designs: arm l = the other 7 designs' source settings (reference: the parent study's
    stock run x1d-/x2d-<design>-001).
 3. Arm c: one confirmation run (clock = T_eff rounded up to 0.05 ns) of each tuned design's pooled best when no earlier
    confirmation run covers that configuration.
Objective and feasibility as Addendum 24 with Amendment 24.1. Tags x4<arm>-<design>-<nnn>.
Usage: tune_a27.py --freeze | --init | --step | --confirm-new | --confirm-transfer | --report [--json f] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime
import json
import math
import os
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tune as T  # noqa: E402  (helpers only; this module keeps its own state and studies)

ROOT = T.ROOT
PREFIX = "x4"
TUNE = os.path.join(ROOT, "results", "tune_x4")
STATE = os.path.join(TUNE, "state.json")
SOURCES = os.path.join(TUNE, "sources.json")
TUNED = {"picorv32": 25.0, "aes_cipher": 40.0, "y_huff": 11.35,
         "des": 20.0, "md5": 37.05, "bm64": 20.0, "ocs_blitter": 18.2, "blabla": 65.0}
PARENT = {d: ("x1" if d in ("picorv32", "aes_cipher", "y_huff") else "x2") for d in TUNED}
PARENT_DIR = {"x1": os.path.join(ROOT, "results", "tune"), "x2": os.path.join(ROOT, "results", "tune_x2")}
A26_DIR = os.path.join(ROOT, "results", "tune_x3")
NEW = {"chacha": 26.01, "ldpcenc": 12.9, "point_add": 10.0, "salsa20": 38.0, "sha512": 39.27}
DESIGNS = {d: {"dir": f"designs/{d}", "config": "config_sky130.json", "period": p} for d, p in {**TUNED, **NEW}.items()}
N_Z, N_W, N_EQ, SEED = 8, 8, 5, 2027
NEED_NEW, NEED_LOO = 3, 5
RC = {"stock": None,
      "cap213": json.load(open(os.path.join(ROOT, "farm", "rc", "sky130_cap213.json"))),
      "orfs": json.load(open(os.path.join(ROOT, "farm", "rc", "sky130_caporfs.json")))}
DRY = {"on": False}
CACHE = {}
LOST_H = 16


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def suggest(trial, d):
    """Addendum 25's extended space on every design (an Addendum-24 source carries RC_MODEL = stock)."""
    T.DESIGNS.setdefault(d, DESIGNS[d])  # T.suggest reads the default period from T.DESIGNS
    ov = T.suggest(trial, d)
    rc = trial.suggest_categorical("RC_MODEL", ["stock", "cap213", "orfs"])
    if RC[rc] is not None:
        ov["LAYERS_RC"] = RC[rc]
    return ov


def fixed(params, d):
    import optuna
    return suggest(optuna.trial.FixedTrial(params), d)


def load(path, default):
    try:
        return json.load(open(path))
    except Exception:
        return default


def save(st):
    if DRY["on"]:
        return
    os.makedirs(TUNE, exist_ok=True)
    json.dump(st, open(STATE + ".tmp", "w"), indent=1)
    os.replace(STATE + ".tmp", STATE)


def study(d, seed):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(multivariate=True, group=True, constant_liar=True, n_startup_trials=N_Z,
                                         seed=seed,
                                         constraints_func=lambda t: t.user_attrs.get("constraints", [1.0, 1.0, 1.0]))
    if DRY["on"]:
        DRY.setdefault("studies", {})
        if d not in DRY["studies"]:
            DRY["studies"][d] = optuna.create_study(study_name=f"{d}-w", sampler=sampler, direction="minimize")
        DRY["studies"][d].sampler = sampler
        return DRY["studies"][d]
    os.makedirs(TUNE, exist_ok=True)
    return optuna.create_study(study_name=f"{d}-w", storage=f"sqlite:///{os.path.join(TUNE, f'{d}-w.db')}",
                               sampler=sampler, direction="minimize", load_if_exists=True)


def seed_for(d, base):
    return base + zlib.crc32((d + "/w").encode()) % 100000


# ---------------------------------------------------------------- sources

def trial_params(db_dir, name, number):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    s = optuna.load_study(study_name=name, storage=f"sqlite:///{os.path.join(db_dir, name + '.db')}")
    for t in s.get_trials(deepcopy=False):
        if t.number == number:
            return dict(t.params)
    raise SystemExit(f"trial {number} not found in {name}")


def strip(ov):
    return {k: v for k, v in ov.items() if k != "CLOCK_PERIOD"}


def pooled_best(d):
    """The feasible AI configuration (tuner t or tuner-with-pruning p) with the lowest T_eff on tuned design d, with its
    Optuna parameters (checked to reproduce the job's overrides)."""
    pre = PARENT[d]
    pst = load(os.path.join(PARENT_DIR[pre], "state.json"), {"tags": {}})["tags"]
    a26 = load(os.path.join(A26_DIR, "state.json"), {"tags": {}})["tags"]
    cands = [(v["teff"], tag, "t", v) for tag, v in pst.items()
             if v["design"] == d and v["arm"] == "t" and v.get("feasible") and v.get("teff") is not None]
    cands += [(v["teff"], tag, "p", v) for tag, v in a26.items()
              if v["design"] == d and v.get("feasible") and v.get("teff") is not None]
    cands.sort(key=lambda x: x[0])
    teff, tag, arm, v = cands[0]
    params = trial_params(PARENT_DIR[pre] if arm == "t" else A26_DIR, f"{d}-{arm}", v["trial"])
    params.setdefault("RC_MODEL", "stock")
    ov = fixed(params, d)
    if strip(ov) != strip(v["overrides"]) or abs(ov["CLOCK_PERIOD"] - v["overrides"]["CLOCK_PERIOD"]) > 1e-9:
        raise SystemExit(f"{tag}: parameters do not reproduce the source overrides")
    return teff, tag, arm, v, params


def parent_confirmed(d, overrides):
    pst = load(os.path.join(PARENT_DIR[PARENT[d]], "state.json"), {"tags": {}})["tags"]
    return any(x["design"] == d and x["arm"] == "c" and strip(x["overrides"]) == strip(overrides) for x in pst.values())


def confirm_new():
    """Addendum 27 procedure: a tuned design whose pooled best changed after the freeze gets one confirmation run of the
    new best (same rule); the transfer sources are not changed."""
    st = load(STATE, None)
    if st is None:
        print("[a27] not initialised")
        return
    covered = {v.get("source") for v in st["tags"].values() if v["arm"] == "c"}
    new = []
    for d in TUNED:
        teff, tag, arm, v, params = pooled_best(d)
        if tag in covered or parent_confirmed(d, v["overrides"]):
            continue
        ov = fixed(params, d)
        ov["CLOCK_PERIOD"] = round(math.ceil(round(teff / 0.05, 6)) * 0.05, 2)
        t = next_tag(st, "c", d)
        add(st, t, d, "c", ov, source=tag)
        new.append(t)
        print(f"[a27] {d}: new pooled best {tag} (T_eff {teff:.3f}) -> confirmation {t} at {ov['CLOCK_PERIOD']} ns")
    save(st)
    send(st, [(new, max(1, len(new)))], f"Addendum 27: confirmation runs of new pooled bests ({len(new)})")


def confirm_transfer():
    """Amendment 27.2: one confirmation run (clock = T_eff rounded up to 0.05 ns) of (1) a tuned design's best feasible
    leave-one-out result when it beats the design's pooled AI best, (2) an unseen design's best transfer result once all
    its z runs have landed (and the best of z and w once all w runs have landed, if a different setting)."""
    st = load(STATE, None)
    if st is None:
        print("[a27] not initialised")
        return
    covered = {v.get("source") for v in st["tags"].values() if v["arm"] == "c"}
    new = []

    def add_conf(d, tag, v, why):
        ov = dict(v["overrides"])
        ov["CLOCK_PERIOD"] = round(math.ceil(round(v["teff"] / 0.05, 6)) * 0.05, 2)
        t = next_tag(st, "c", d)
        add(st, t, d, "c", ov, source=tag, transfer=True, source_design=v.get("source_design"))
        new.append(t)
        covered.add(tag)
        print(f"[a27] {d}: {why} {tag} (T_eff {v['teff']:.3f}, from {v.get('source_design')}) -> confirmation {t} at {ov['CLOCK_PERIOD']} ns")

    for d in TUNED:
        l = [(t, v) for t, v in st["tags"].items() if v["design"] == d and v["arm"] == "l" and v.get("feasible")
             and v.get("teff") is not None]
        if not l:
            continue
        tag, v = min(l, key=lambda tv: tv[1]["teff"])
        if tag in covered:
            continue
        pooled = pooled_best(d)[0]
        if v["teff"] < pooled:
            add_conf(d, tag, v, f"leave-one-out beats the pooled best ({pooled:.3f}):")
    for d in NEW:
        z = [(t, v) for t, v in st["tags"].items() if v["design"] == d and v["arm"] == "z"]
        w = [(t, v) for t, v in st["tags"].items() if v["design"] == d and v["arm"] == "w"]
        if len(z) < N_Z or any(v["status"] in ("dispatched", "pending") for _, v in z):
            continue
        pool = z + (w if (len(w) == N_W and not any(v["status"] in ("dispatched", "pending") for _, v in w)) else [])
        ok = [(t, v) for t, v in pool if v.get("feasible") and v.get("teff") is not None]
        if not ok:
            continue
        tag, v = min(ok, key=lambda tv: tv[1]["teff"])
        if tag not in covered:
            add_conf(d, tag, v, "best transfer result")
    save(st)
    send(st, [(new, max(1, len(new)))], f"Addendum 27 (Amendment 27.2): confirmation runs of transferred settings ({len(new)})")


def own_confirmed(d, st):
    """Best feasible confirmation of a tuned design's own AI settings (Addenda 24/25 arm c, Addendum 27 arm c without
    transfer), or None."""
    pst = load(os.path.join(PARENT_DIR[PARENT[d]], "state.json"), {"tags": {}})["tags"]
    vals = [x["teff"] for x in pst.values() if x["design"] == d and x["arm"] == "c" and x.get("feasible")
            and x.get("teff") is not None]
    vals += [x["teff"] for x in st["tags"].values() if x["design"] == d and x["arm"] == "c" and not x.get("transfer")
             and x.get("feasible") and x.get("teff") is not None]
    return min(vals) if vals else None


def confirm_loo_own():
    """Amendment 27.3 (Addendum 29): one re-run (clock = T_eff rounded up to 0.05 ns) of a tuned design's best feasible
    leave-one-out run when it is faster than the design's best feasible confirmation of its own AI settings and has not
    been re-run yet. Reported without criterion."""
    st = load(STATE, None)
    if st is None:
        return
    covered = {v.get("source") for v in st["tags"].values() if v["arm"] == "c"}
    new = []
    for d in TUNED:
        l = [(t, v) for t, v in st["tags"].items() if v["design"] == d and v["arm"] == "l" and v.get("feasible")
             and v.get("teff") is not None]
        if not l:
            continue
        tag, v = min(l, key=lambda tv: tv[1]["teff"])
        if tag in covered:
            continue
        own = own_confirmed(d, st)
        if own is not None and v["teff"] >= own:
            continue
        ov = dict(v["overrides"])
        ov["CLOCK_PERIOD"] = round(math.ceil(round(v["teff"] / 0.05, 6)) * 0.05, 2)
        t = next_tag(st, "c", d)
        add(st, t, d, "c", ov, source=tag, transfer=True, source_design=v.get("source_design"), rule="27.3")
        new.append(t)
        covered.add(tag)
        print(f"[a27] {d}: Amendment 27.3: leave-one-out best {tag} (T_eff {v['teff']:.3f}, from {v.get('source_design')}) "
              f"is faster than the own confirmed best ({own}) -> confirmation {t} at {ov['CLOCK_PERIOD']} ns")
    save(st)
    send(st, [(new, max(1, len(new)))], f"Addendum 29 (Amendment 27.3): re-runs of leave-one-out bests ({len(new)})")


def freeze():
    if os.path.exists(SOURCES) and not DRY["on"]:
        raise SystemExit(f"{SOURCES} exists (sources are frozen once)")
    out = {"frozen_at": now(), "sources": {}}
    for d in TUNED:
        pre = PARENT[d]
        pst = load(os.path.join(PARENT_DIR[pre], "state.json"), {"tags": {}})["tags"]
        teff, tag, arm, v, params = pooled_best(d)
        stock = [x["teff"] for x in pst.values() if x["design"] == d and x["arm"] == "d" and x.get("feasible")]
        confirmed = parent_confirmed(d, v["overrides"])
        out["sources"][d] = {"tag": tag, "arm": arm, "trial": v["trial"], "teff": teff, "params": params,
                             "period_frac": params["period_frac"], "stock_best": min(stock) if stock else None,
                             "gain_vs_stock": (min(stock) - teff) / min(stock) if stock else None,
                             "already_confirmed": bool(confirmed)}
    order = sorted(out["sources"], key=lambda d: -(out["sources"][d]["gain_vs_stock"] or -1e9))
    out["order"] = order
    CACHE["src"] = out
    if not DRY["on"]:
        os.makedirs(TUNE, exist_ok=True)
        json.dump(out, open(SOURCES, "w"), indent=1)
    for d in order:
        s = out["sources"][d]
        print(f"{d:12s} {s['tag']:22s} T_eff {s['teff']:.3f} frac {s['period_frac']:.3f} gain vs stock "
              f"{100 * s['gain_vs_stock']:.1f}%  confirmed earlier: {s['already_confirmed']}")
    print("order:", ", ".join(order))
    return out


# ---------------------------------------------------------------- jobs

def next_tag(st, arm, d):
    n = sum(1 for v in st["tags"].values() if v["arm"] == arm and v["design"] == d) + 1
    return f"{PREFIX}{arm}-{d}-{n:03d}"


def write_spec(tag, d, ov):
    spec = {"tag": tag, "design": DESIGNS[d]["dir"], "config": DESIGNS[d]["config"], "overrides": {**T.FIXED, **ov}}
    out = os.path.join(TUNE, "dry_jobs") if DRY["on"] else os.path.join(ROOT, "farm", "jobs")
    os.makedirs(out, exist_ok=True)
    json.dump(spec, open(os.path.join(out, f"{tag}.json"), "w"), indent=1)


def add(st, tag, d, arm, ov, **kw):
    write_spec(tag, d, ov)
    st["tags"][tag] = {"design": d, "arm": arm, "overrides": ov, "status": "pending", "asked_at": now(), **kw}


def send(st, groups, msg):
    alltags = [t for g, _ in groups for t in g]
    if not alltags:
        return
    if not T.commit_specs(alltags, msg, DRY["on"]):
        return
    for tags, mp in groups:
        for t in T.dispatch(tags, DRY["on"], mp):
            st["tags"][t]["status"] = "dispatched"
            st["tags"][t]["asked_at"] = now()
    save(st)


def init():
    src = load(SOURCES, None) or CACHE.get("src")
    if src is None:
        raise SystemExit("run --freeze first")
    st = load(STATE, {"tags": {}})
    if st["tags"]:
        raise SystemExit("already initialised")
    order = src["order"]
    # 3. confirmations of pooled bests not covered by an earlier confirmation run
    conf = []
    for d in order:
        s = src["sources"][d]
        if s["already_confirmed"]:
            continue
        ov = fixed(s["params"], d)
        ov["CLOCK_PERIOD"] = round(math.ceil(round(s["teff"] / 0.05, 6)) * 0.05, 2)
        tag = next_tag(st, "c", d)
        add(st, tag, d, "c", ov, source=s["tag"])
        conf.append(tag)
    # 1. unseen designs: stock and expert at five clocks, zero-shot transfer as the first 8 trials of a TPE study
    per_new = []
    for d in NEW:
        base = {"d": [], "e": []}
        for arm, preset in (("d", {}), ("e", T.EXPERT)):
            for f in T.FRACS:
                tag = next_tag(st, arm, d)
                add(st, tag, d, arm, {**preset, "CLOCK_PERIOD": round(DESIGNS[d]["period"] * f, 2)}, frac=f)
                base[arm].append(tag)
        s = study(d, seed_for(d, SEED))
        z = []
        for k, sd in enumerate(order):
            s.enqueue_trial(src["sources"][sd]["params"])
            tr = s.ask()
            ov = suggest(tr, d)
            tag = next_tag(st, "z", d)
            add(st, tag, d, "z", ov, trial=tr.number, source=src["sources"][sd]["tag"], source_design=sd, rank=k)
            z.append(tag)
        # the stock reference first, then transfer and expert runs alternating, then the other stock runs
        seq = [base["d"][0]]
        for j in range(max(len(z), len(base["e"]))):
            seq += z[j:j + 1] + base["e"][j:j + 1]
        seq += base["d"][1:]
        per_new.append(seq)
    # 2. leave-one-out on the tuned designs
    per_loo = []
    for d in order:
        seq = []
        for k, sd in enumerate(x for x in order if x != d):
            ov = fixed(src["sources"][sd]["params"], d)
            tag = next_tag(st, "l", d)
            add(st, tag, d, "l", ov, source=src["sources"][sd]["tag"], source_design=sd, rank=k)
            seq.append(tag)
        per_loo.append(seq)
    save(st)
    new_jobs, loo_jobs = T.interleave(per_new), T.interleave(per_loo)
    send(st, [(conf, max(1, len(conf))), (new_jobs, 20), (loo_jobs, 12)],
         f"Addendum 27: transfer study job specs ({len(conf) + len(new_jobs) + len(loo_jobs)})")
    print(f"[a27] init: {len(conf)} confirmations, {len(new_jobs)} unseen-design jobs, {len(loo_jobs)} leave-one-out jobs")


def ref_drv(d):
    """Amendment 24.1 reference; Amendment 27.1 (1): for an unseen design whose stock run at the default clock did not
    reach signoff, the first stock run in the registered order (1.0, 0.85, 0.7, 0.6, 0.5 x default) that did."""
    if d in PARENT:
        try:
            m = json.load(open(os.path.join(ROOT, "results", f"{PARENT[d]}d-{d}-001", "metrics.json")))
        except Exception:
            return None
        return T.drv_count(m) if m.get("timing__setup__ws") is not None else None
    for k in range(1, len(T.FRACS) + 1):
        r = os.path.join(ROOT, "results", f"{PREFIX}d-{d}-{k:03d}")
        if not os.path.exists(os.path.join(r, "job.json")):
            return None  # this one has not landed yet: wait for it
        try:
            m = json.load(open(os.path.join(r, "metrics.json")))
        except Exception:
            m = {}
        if m.get("timing__setup__ws") is not None:
            return T.drv_count(m)
    return None  # no stock run reached signoff: not scorable


def tell_finished(st, dry):
    import optuna
    told = 0
    for tag, v in st["tags"].items():
        if v["status"] != "dispatched":
            continue
        ref = ref_drv(v["design"])
        status, teff, cons, m = T.outcome(tag, v["overrides"]["CLOCK_PERIOD"], ref)
        if status == "done" and ref is None:
            continue
        if status is None:
            age = (datetime.datetime.now(datetime.timezone.utc)
                   - datetime.datetime.strptime(v["asked_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc))
            if age.total_seconds() < (LOST_H if v["arm"] in ("z", "w", "c") else 36) * 3600:
                continue
            status, teff, cons, m = "lost", None, None, {}
        j = load(os.path.join(ROOT, "results", tag, "job.json"), {})
        v.update({"status": status, "teff": teff, "constraints": cons, "feasible": T.feasible(cons), "landed_at": now(),
                  "area": m.get("design__instance__area__stdcell"), "power": m.get("power__total"),
                  "hold": m.get("timing__hold__ws"), "wns": m.get("timing__setup__ws"), "drc": m.get("route__drc_errors"),
                  "drv": T.drv_count(m) if m else None, "drv_ref": ref, "flow_seconds": j.get("flow_seconds")})
        if v["arm"] in ("z", "w") and not dry:
            s = study(v["design"], SEED)
            try:
                if status == "lost":
                    s.tell(v["trial"], state=optuna.trial.TrialState.FAIL)
                else:
                    tid = s._storage.get_trial_id_from_study_id_trial_number(s._study_id, v["trial"])
                    s._storage.set_trial_user_attr(tid, "constraints", cons)
                    s.tell(v["trial"], teff if teff is not None else 2.0 * DESIGNS[v["design"]]["period"])
            except Exception as e:  # already told
                print(f"[a27] tell {tag}: {e}")
        told += 1
    return told


def step():
    st = load(STATE, None)
    if st is None:
        print("[a27] not initialised")
        return
    told = tell_finished(st, DRY["on"])
    save(st)
    retry = [t for t, v in st["tags"].items() if v["status"] == "pending"]
    new = []
    # Amendment 27.1 (2): a confirmation run stopped by a tool error before signoff is re-run once (same spec, new tag)
    for tag, v in list(st["tags"].items()):
        if v["arm"] != "c" or v["status"] != "failed" or v.get("rerun_of") or v.get("rerun_tag"):
            continue
        t2 = next_tag(st, "c", v["design"])
        add(st, t2, v["design"], "c", dict(v["overrides"]), source=v.get("source"), rerun_of=tag)
        v["rerun_tag"] = t2
        new.append(t2)
        print(f"[a27] {tag} stopped before signoff -> re-run once as {t2} (Amendment 27.1)")
    for d in NEW:
        z = [v for v in st["tags"].values() if v["design"] == d and v["arm"] == "z"]
        w = [v for v in st["tags"].values() if v["design"] == d and v["arm"] == "w"]
        if w or len(z) < N_Z or any(v["status"] in ("dispatched", "pending") for v in z):
            continue
        s = study(d, seed_for(d, SEED + 7 * len(z)))
        for _ in range(N_W):  # asked together: constant liar spreads them
            tr = s.ask()
            tag = next_tag(st, "w", d)
            add(st, tag, d, "w", suggest(tr, d), trial=tr.number)
            new.append(tag)
    save(st)
    send(st, [(retry + new, 16)], f"Addendum 27: warm-start tuner trials ({len(new)})" + (f", {len(retry)} re-sent" if retry else ""))
    print(f"[a27] step: told {told}, asked {len(new)}, re-sent {len(retry)}")


# ---------------------------------------------------------------- report

def parent_rows(d):
    pre = PARENT[d]
    return load(os.path.join(PARENT_DIR[pre], "state.json"), {"tags": {}})["tags"]


def best(vs):
    ok = [v["teff"] for v in vs if v.get("feasible") and v.get("teff") is not None]
    return min(ok) if ok else None


def landed(vs):
    return sum(1 for v in vs if v["status"] not in ("dispatched", "pending"))


def beats(a, b, margin):
    """a (lower is better) beats b by more than margin; None = no feasible configuration (infinite)."""
    if a is None:
        return False
    return b is None or (b - a) / b > margin


def report(js):
    st = load(STATE, {"tags": {}})
    src = load(SOURCES, {"order": [], "sources": {}})
    tell_finished(st, dry=True)
    rows = st["tags"]
    out = {"unseen": {}, "loo": {}, "confirm": {}}
    per = {}
    for d in NEW:
        arm = {a: [v for v in rows.values() if v["design"] == d and v["arm"] == a] for a in ("d", "e", "z", "w")}
        z5 = [v for v in arm["z"] if v.get("rank", 99) < N_EQ]
        b = {a: best(arm[a]) for a in arm}
        b["z5"] = best(z5)
        b["zw"] = best(arm["z"] + arm["w"])
        n = {a: (landed(arm[a]), len(arm[a])) for a in arm}
        e_done = n["e"][0] == n["e"][1] == len(T.FRACS)
        z_done = n["z"][0] == n["z"][1] == N_Z
        w_done = n["w"][0] == n["w"][1] == N_W
        z5_done = all(v["status"] not in ("dispatched", "pending") for v in z5) and len(z5) == N_EQ
        res = {"A27a": beats(b["z"], b["e"], 0.05) if (e_done and z_done) else None,
               "A27b": beats(b["z5"], b["e"], 0.05) if (e_done and z5_done) else None,
               "A27c": beats(b["zw"], b["e"], 0.10) if (e_done and z_done and w_done) else None}
        per[d] = res
        win = min((v for v in arm["z"] if v.get("feasible")), key=lambda v: v["teff"], default=None)
        # reported without criterion: the expert arm's fastest run whatever its feasibility (for arms with no feasible run)
        ea = min((v for v in arm["e"] if v.get("teff") is not None), key=lambda v: v["teff"], default=None)
        e_any = None if ea is None else {"teff": ea["teff"], "drv": ea.get("drv"), "drv_ref": ea.get("drv_ref"),
                                         "hold": ea.get("hold"), "feasible": bool(ea.get("feasible"))}
        out["unseen"][d] = {"best": b, "landed": n, "best_z_source": win.get("source_design") if win else None,
                            "e_any": e_any, **res}
        f = lambda x: f"{x:.2f}" if x is not None else "-"
        print(f"== {d} (default {DESIGNS[d]['period']} ns): stock {f(b['d'])} ({n['d'][0]}/{n['d'][1]}), expert {f(b['e'])} "
              f"({n['e'][0]}/{n['e'][1]}), transfer {f(b['z'])} ({n['z'][0]}/{n['z'][1]}; first 5: {f(b['z5'])}; best from "
              f"{out['unseen'][d]['best_z_source']}), +warm start {f(b['zw'])} ({n['w'][0]}/{n['w'][1]})  {res}")
    loo = {}
    for d in TUNED:
        pr = parent_rows(d)
        e = [v for v in pr.values() if v["design"] == d and v["arm"] == "e"]
        dd = [v for v in pr.values() if v["design"] == d and v["arm"] == "d"]
        l = [v for v in rows.values() if v["design"] == d and v["arm"] == "l"]
        bl, be, bd = best(l), best(e), best(dd)
        tb = src["sources"].get(d, {}).get("teff")
        l_done = landed(l) == len(l) == len(TUNED) - 1
        v = beats(bl, be, 0.05) if l_done else None
        loo[d] = {"A27d": v}
        win = min((x for x in l if x.get("feasible")), key=lambda x: x["teff"], default=None)
        rec = ((bd - bl) / (bd - tb)) if (bd is not None and bl is not None and tb is not None and bd > tb) else None
        out["loo"][d] = {"best_transfer": bl, "expert_best": be, "stock_best": bd, "tuned_best": tb, "landed": (landed(l), len(l)),
                         "best_source": win.get("source_design") if win else None, "share_of_tuning_gain": rec, "A27d": v}
        f = lambda x: f"{x:.2f}" if x is not None else "-"
        print(f"== LOO {d}: transfer {f(bl)} ({landed(l)}/{len(l)}, best from {out['loo'][d]['best_source']}) vs expert {f(be)}, "
              f"stock {f(bd)}, own tuned best {f(tb)}; share of tuning gain {f(rec)}  A27d={v}")
    for tag, v in rows.items():
        if v["arm"] == "c":
            out["confirm"][tag] = {"design": v["design"], "source": v.get("source"), "status": v["status"],
                                   "clock": v["overrides"]["CLOCK_PERIOD"], "wns": v.get("wns"), "teff": v.get("teff"),
                                   "feasible": v.get("feasible"), "rerun_of": v.get("rerun_of")}
            print(f"== confirm {v['design']}: {tag} ({v.get('source')}{', re-run of ' + v['rerun_of'] if v.get('rerun_of') else ''}) "
                  f"clock {v['overrides']['CLOCK_PERIOD']} status {v['status']} WS {v.get('wns')} T_eff {v.get('teff')} feasible {v.get('feasible')}")
    overall = {}
    for k in ("A27a", "A27b", "A27c"):
        vals = [per[d][k] for d in per]
        p, fl = sum(1 for x in vals if x is True), sum(1 for x in vals if x is False)
        overall[k] = ("PASS" if p >= NEED_NEW else ("FAIL" if fl > len(vals) - NEED_NEW else "pending")) + f" ({p} pass, {fl} fail, {len(vals) - p - fl} pending)"
    vals = [loo[d]["A27d"] for d in loo]
    p, fl = sum(1 for x in vals if x is True), sum(1 for x in vals if x is False)
    overall["A27d"] = ("PASS" if p >= NEED_LOO else ("FAIL" if fl > len(vals) - NEED_LOO else "pending")) + f" ({p} pass, {fl} fail, {len(vals) - p - fl} pending)"
    for k, v in overall.items():
        print(f"  {k}: {v}")
    if js:
        json.dump({**out, "overall": overall, "order": src.get("order")}, open(js, "w"), indent=1, default=str)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--freeze", action="store_true")
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--confirm-new", action="store_true")
    ap.add_argument("--confirm-transfer", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    DRY["on"] = a.dry_run
    T.DRY["on"] = a.dry_run
    if a.freeze:
        freeze()
    if a.init:
        init()
    if a.step:
        step()
    if a.confirm_new:
        confirm_new()
    if a.confirm_transfer:
        confirm_transfer()
        confirm_loo_own()
    if a.report:
        report(a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
