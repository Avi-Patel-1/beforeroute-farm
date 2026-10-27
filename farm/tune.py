#!/usr/bin/env python3
"""Addendum 24: AI flow tuning judged at nine-corner signoff, and the prospective early-stopping test.

Per design, four arms (job tags x1<arm>-<design>-<nnn>, farm/jobs/<tag>.json, run by .github/workflows/farm.yml):
  t  tuner: Optuna TPE (multivariate, constant liar for asynchronous trials, 8 random start-up trials), 24 trials
  r  random search over the same space, 24 trials (Optuna RandomSampler, fixed seed)
  d  LibreLane defaults at clock period 1.0/0.85/0.7/0.6/0.5 x the design's default
  e  expert preset (DELAY 0 synthesis, timing-driven placement, post-GRT timing and design repair) at the same periods
Objective: effective clock period T_eff = CLOCK_PERIOD - worst setup slack (ns, nine-corner signoff), minimized.
Feasible: router DRC errors = 0, worst hold slack >= 0, max-slew + max-cap pin violations <= 10.
State: results/tune/state.json and one Optuna SQLite study per design and arm under results/tune/.
Usage:
  tune.py --init [--dry-run]     write the 8 tuner start-up trials and the r/d/e specs; commit, push, dispatch
  tune.py --step [--dry-run]     tell finished trials; ask new tuner trials (<= 8 in flight, <= 24 total); dispatch
  tune.py --report [--json f]    per design and arm: best feasible T_eff, area, power; early-stopping replay (A24a)
  tune.py --confirm [--dry-run]  re-run each design's best tuner configuration at its T_eff (A24d)
"""
from __future__ import annotations

import argparse
import datetime
import gzip
import json
import math
import os
import re
import subprocess
import sys
import time

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
REPO = "Avi-Patel-1/beforeroute-farm"
TUNE = os.path.join(ROOT, "results", "tune")
STATE = os.path.join(TUNE, "state.json")
DESIGNS = {
    "picorv32": {"dir": "designs/picorv32", "config": "config_sky130.json", "period": 25.0},
    "aes_cipher": {"dir": "designs/aes_cipher", "config": "config_sky130.json", "period": 40.0},
    "y_huff": {"dir": "designs/y_huff", "config": "config_sky130.json", "period": 11.35},
}
FIXED = {"RUN_MAGIC_DRC": False, "RUN_KLAYOUT_DRC": False, "RUN_LVS": False, "RUN_KLAYOUT_XOR": False,
         "RUN_IRDROP_REPORT": False, "RUN_LINTER": False}
STRATEGIES = ["AREA 0", "AREA 1", "AREA 2", "AREA 3", "DELAY 0", "DELAY 1", "DELAY 2", "DELAY 3", "DELAY 4"]
FRACS = [1.0, 0.85, 0.7, 0.6, 0.5]
EXPERT = {"SYNTH_STRATEGY": "DELAY 0", "PL_TIMING_DRIVEN": True, "RUN_POST_GRT_RESIZER_TIMING": True,
          "RUN_POST_GRT_DESIGN_REPAIR": True}
N_TRIALS, N_STARTUP, IN_FLIGHT, SEED = 24, 8, 8, 2024
DRV_MAX = 10


def suggest(trial, d):
    """The search space shared by the tuner and the random arm. Returns LibreLane overrides."""
    frac = trial.suggest_float("period_frac", 0.45, 1.0)
    util = trial.suggest_int("FP_CORE_UTIL", 20, 50)
    dd = trial.suggest_int("density_delta", 5, 30)
    ov = {
        "CLOCK_PERIOD": round(DESIGNS[d]["period"] * frac, 2),
        "SYNTH_STRATEGY": trial.suggest_categorical("SYNTH_STRATEGY", STRATEGIES),
        "SYNTH_ABC_BUFFERING": trial.suggest_categorical("SYNTH_ABC_BUFFERING", [False, True]),
        "SYNTH_SIZING": trial.suggest_categorical("SYNTH_SIZING", [False, True]),
        "FP_CORE_UTIL": util,
        "PL_TARGET_DENSITY_PCT": min(util + dd, 80),
        "PL_TIMING_DRIVEN": trial.suggest_categorical("PL_TIMING_DRIVEN", [False, True]),
        "PL_ROUTABILITY_DRIVEN": trial.suggest_categorical("PL_ROUTABILITY_DRIVEN", [False, True]),
        "RUN_POST_GRT_RESIZER_TIMING": trial.suggest_categorical("RUN_POST_GRT_RESIZER_TIMING", [False, True]),
        "RUN_POST_GRT_DESIGN_REPAIR": trial.suggest_categorical("RUN_POST_GRT_DESIGN_REPAIR", [False, True]),
        "PL_RESIZER_SETUP_SLACK_MARGIN": round(trial.suggest_float("PL_RESIZER_SETUP_SLACK_MARGIN", 0.0, 0.4), 3),
        "GRT_RESIZER_SETUP_SLACK_MARGIN": round(trial.suggest_float("GRT_RESIZER_SETUP_SLACK_MARGIN", 0.0, 0.4), 3),
        "DESIGN_REPAIR_MAX_SLEW_PCT": trial.suggest_int("DESIGN_REPAIR_MAX_SLEW_PCT", 10, 40),
        "DESIGN_REPAIR_MAX_CAP_PCT": trial.suggest_int("DESIGN_REPAIR_MAX_CAP_PCT", 10, 40),
    }
    return ov


def sh(cmd, check=False):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
    if check and r.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(cmd)}\n{r.stderr[-2000:]}")
    return r


def load_state():
    return json.load(open(STATE)) if os.path.exists(STATE) else {"tags": {}}


def save_state(st):
    os.makedirs(TUNE, exist_ok=True)
    json.dump(st, open(STATE + ".tmp", "w"), indent=1)
    os.replace(STATE + ".tmp", STATE)


def next_tag(st, arm, d):
    n = sum(1 for v in st["tags"].values() if v["arm"] == arm and v["design"] == d) + 1
    return f"x1{arm}-{d}-{n:03d}"


DRY = {"on": False}


def write_spec(tag, d, ov):
    spec = {"tag": tag, "design": DESIGNS[d]["dir"], "config": DESIGNS[d]["config"], "overrides": {**FIXED, **ov}}
    out = os.path.join(TUNE, "dry_jobs") if DRY["on"] else os.path.join(ROOT, "farm", "jobs")
    os.makedirs(out, exist_ok=True)
    json.dump(spec, open(os.path.join(out, f"{tag}.json"), "w"), indent=1)


def study(d, arm, seed):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    if arm == "t":
        sampler = optuna.samplers.TPESampler(multivariate=True, group=True, constant_liar=True,
                                             n_startup_trials=N_STARTUP, seed=seed,
                                             constraints_func=lambda t: t.user_attrs.get("constraints", [1.0, 1.0, 1.0]))
    else:
        sampler = optuna.samplers.RandomSampler(seed=seed)
    os.makedirs(TUNE, exist_ok=True)
    if DRY["on"]:  # a dry run must not leave asked-but-never-told trials in the real studies
        key = f"{d}-{arm}"
        DRY.setdefault("studies", {})
        if key not in DRY["studies"]:
            DRY["studies"][key] = optuna.create_study(study_name=key, sampler=sampler, direction="minimize")
        DRY["studies"][key].sampler = sampler
        return DRY["studies"][key]
    return optuna.create_study(study_name=f"{d}-{arm}", storage=f"sqlite:///{os.path.join(TUNE, f'{d}-{arm}.db')}",
                               sampler=sampler, direction="minimize", load_if_exists=True)


def commit_specs(tags, msg, dry):
    """Commit and push the job specs (retrying on a concurrent push). True when origin/main has them."""
    if not tags:
        return True
    paths = [os.path.join("farm", "jobs", f"{t}.json") for t in tags]
    if dry:
        print(f"[tune] dry run: would commit {len(paths)} specs")
        return True
    sh(["git", "add"] + paths, check=True)
    r = sh(["git", "commit", "-q", "-m", msg + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_016XcZ7Zp4en4cWPeoAqbHJG"])
    if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
        print(f"[tune] commit failed: {r.stderr[-300:]}")
        return False
    for _ in range(5):
        sh(["git", "pull", "-q", "--rebase", "origin", "main"])
        if sh(["git", "push", "-q", "origin", "HEAD:main"]).returncode == 0:
            return True
        time.sleep(3)
    print("[tune] push failed 5 times; specs stay pending")
    return False


def dispatch(tags, dry, max_parallel):
    """One farm.yml run per <= 250 tags (GitHub's matrix limit is 256). Returns the tags dispatched."""
    done = []
    for i in range(0, len(tags), 250):
        chunk = tags[i:i + 250]
        if dry:
            print(f"[tune] dry run: would dispatch {len(chunk)} jobs (max_parallel {max_parallel}): {chunk[:6]}...")
            done += chunk
            continue
        r = sh(["gh", "workflow", "run", "farm.yml", "-R", REPO, "--ref", "main", "-f", f"tags={json.dumps(chunk)}",
                "-f", f"max_parallel={max_parallel}"])
        print(f"[tune] dispatched {len(chunk)} jobs (max_parallel {max_parallel}): {'ok' if r.returncode == 0 else 'FAILED ' + r.stderr[-300:]}")
        if r.returncode == 0:
            done += chunk
        time.sleep(2)
    return done


BACKEND = {"name": os.environ.get("BR_BACKEND", "farm")}  # "farm" (GitHub Actions) or "modal" (farm/modal_backend.py)


def send(st, groups, msg, dry):
    """groups: [(tags, max_parallel)], in queue order. Specs were written and the tags are in st as 'pending'.
    Commit once, dispatch each group, mark what went out as dispatched (asked_at = dispatch time)."""
    alltags = [t for g, _ in groups for t in g]
    if not alltags:
        return
    if not commit_specs(alltags, msg, dry):
        return
    for tags, mp in groups:
        if BACKEND["name"] == "modal" and not dry:
            sys.path.insert(0, os.path.join(ROOT, "farm"))
            import modal_backend  # noqa: E402
            sent = modal_backend.spawn(tags, jobs=4)
        else:
            sent = dispatch(tags, dry, mp)
        for t in sent:
            st["tags"][t]["status"] = "dispatched"
            st["tags"][t]["asked_at"] = now()
    if not dry:
        save_state(st)


def outcome(tag, period):
    """(status, T_eff, constraints, metrics) from results/<tag>; status None while not landed."""
    d = os.path.join(ROOT, "results", tag)
    if not os.path.exists(os.path.join(d, "job.json")):
        return None, None, None, {}
    m = {}
    if os.path.exists(os.path.join(d, "metrics.json")):
        try:
            m = json.load(open(os.path.join(d, "metrics.json")))
        except Exception:
            m = {}
    ws = m.get("timing__setup__ws")
    if ws is None:
        return "failed", None, [1e3, 1e3, 1e3], m
    teff = period - ws
    drc = m.get("route__drc_errors") or 0
    hold = m.get("timing__hold__ws")
    drv = (m.get("design__max_slew_violation__count") or 0) + (m.get("design__max_cap_violation__count") or 0)
    cons = [float(drc), float(-(hold if hold is not None else -1.0)), float(drv - DRV_MAX)]
    return "done", teff, cons, m


def feasible(cons):
    return cons is not None and all(c <= 0 for c in cons)


def interleave(lists):
    """Round-robin over lists (keeps each list's order)."""
    out, i = [], 0
    while any(i < len(l) for l in lists):
        for l in lists:
            if i < len(l):
                out.append(l[i])
        i += 1
    return out


def add(st, tag, d, arm, trial, ov):
    write_spec(tag, d, ov)
    st["tags"][tag] = {"design": d, "arm": arm, "trial": trial, "overrides": ov, "status": "pending", "asked_at": now()}


def init(dry):
    st = load_state()
    tuner, rest = [], []
    for d in DESIGNS:
        if not any(v["arm"] == "t" and v["design"] == d for v in st["tags"].values()):
            s = study(d, "t", SEED)
            for _ in range(N_STARTUP):
                tr = s.ask()
                tag = next_tag(st, "t", d)
                add(st, tag, d, "t", tr.number, suggest(tr, d))
                tuner.append(tag)
    per_design = []
    for d in DESIGNS:
        r_tags, base = [], {"d": [], "e": []}
        if not any(v["arm"] == "r" and v["design"] == d for v in st["tags"].values()):
            s = study(d, "r", SEED + 1)
            for _ in range(N_TRIALS):
                tr = s.ask()
                tag = next_tag(st, "r", d)
                add(st, tag, d, "r", tr.number, suggest(tr, d))
                r_tags.append(tag)
        for arm, preset in (("d", {}), ("e", EXPERT)):
            if any(v["arm"] == arm and v["design"] == d for v in st["tags"].values()):
                continue
            for f in FRACS:
                tag = next_tag(st, arm, d)
                add(st, tag, d, arm, None, {**preset, "CLOCK_PERIOD": round(DESIGNS[d]["period"] * f, 2)})
                base[arm].append(tag)
        # per design: a defaults and an expert run, then five random trials, and so on
        seq = []
        for j in range(max(len(base["d"]), len(base["e"]), math.ceil(len(r_tags) / 5))):
            seq += base["d"][j:j + 1] + base["e"][j:j + 1] + r_tags[5 * j:5 * j + 5]
        per_design.append(seq)
    rest = interleave(per_design)
    if not dry:
        save_state(st)
    # tuner start-up trials go first, in their own run, so they queue ahead; the rest run at most 10 at a time so
    # that later tuner trials (sequential by design) always find free runners
    send(st, [(tuner, 24), (rest, 10)], f"Addendum 24: tuning and early-stopping job specs ({len(tuner) + len(rest)})", dry)
    print(f"[tune] init: {len(tuner)} tuner start-up + {len(rest)} random/defaults/expert jobs")


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


LOST_H = {"t": 16, "c": 16}  # hours after dispatch before a job that never produced a result counts as lost; others 36


def tell_finished(st, dry):
    told = 0
    for tag, v in st["tags"].items():
        if v["status"] != "dispatched":
            continue
        status, teff, cons, m = outcome(tag, v["overrides"]["CLOCK_PERIOD"])
        if status is None:
            # runner lost or artifact missing: the trial is dropped (told FAIL, which TPE ignores), not scored
            age = (datetime.datetime.now(datetime.timezone.utc)
                   - datetime.datetime.strptime(v["asked_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=datetime.timezone.utc))
            if age.total_seconds() < LOST_H.get(v["arm"], 36) * 3600:
                continue
            status, teff, cons, m = "lost", None, None, {}
        v.update({"status": status, "teff": teff, "constraints": cons, "feasible": feasible(cons), "landed_at": now(),
                  "area": m.get("design__instance__area__stdcell"), "power": m.get("power__total"),
                  "hold": m.get("timing__hold__ws"), "wns": m.get("timing__setup__ws"),
                  "drc": m.get("route__drc_errors"),
                  "drv": (m.get("design__max_slew_violation__count") or 0) + (m.get("design__max_cap_violation__count") or 0)
                  if m else None})
        if v["arm"] in ("t", "r") and v.get("trial") is not None and not dry:
            import optuna
            s = study(v["design"], v["arm"], SEED)
            try:
                if status == "lost":
                    s.tell(v["trial"], state=optuna.trial.TrialState.FAIL)
                else:
                    tid = s._storage.get_trial_id_from_study_id_trial_number(s._study_id, v["trial"])
                    s._storage.set_trial_user_attr(tid, "constraints", cons)
                    s.tell(v["trial"], teff if teff is not None else 2.0 * DESIGNS[v["design"]]["period"])
            except Exception as e:  # already told
                print(f"[tune] tell {tag}: {e}")
        told += 1
    return told


def step(dry):
    st = load_state()
    told = tell_finished(st, dry)
    if not dry:
        save_state(st)
    retry = [t for t, v in st["tags"].items() if v["status"] == "pending"]  # specs whose commit or dispatch failed
    new = []
    for d in DESIGNS:
        mine = [v for v in st["tags"].values() if v["arm"] == "t" and v["design"] == d]
        inflight = sum(1 for v in mine if v["status"] in ("dispatched", "pending"))
        room = min(IN_FLIGHT - inflight, N_TRIALS - len(mine))
        if room <= 0:
            continue
        s = study(d, "t", SEED + 7 * len(mine))  # a fresh RNG stream per call (TPE keeps no other state)
        for _ in range(room):
            tr = s.ask()
            tag = next_tag(st, "t", d)
            add(st, tag, d, "t", tr.number, suggest(tr, d))
            new.append(tag)
    if not dry:
        save_state(st)
    send(st, [(retry + new, 24)], f"Addendum 24: tuner trials ({len(new)})" + (f", {len(retry)} re-sent" if retry else ""), dry)
    print(f"[tune] step: told {told}, asked {len(new)}, re-sent {len(retry)}")


def post_grt_wns(tag):
    """Worst driver slack over signal nets in the post-GRT dump (the global-route view the flow itself sees)."""
    p = os.path.join(ROOT, "results", tag, "nets.jsonl")
    op = (lambda: open(p)) if os.path.exists(p) else ((lambda: gzip.open(p + ".gz", "rt")) if os.path.exists(p + ".gz") else None)
    if op is None:
        return None
    w = None
    with op() as f:
        for line in f:
            n = json.loads(line)
            if n.get("sigtype") != "SIGNAL":
                continue
            s = n.get("driver_slack_ns")
            if s is not None and (w is None or s < w):
                w = s
    return w


STEP_RE = re.compile(r"^\[(\d\d:\d\d:\d\d)\]\s+VERBOSE\s+Running '([^']+)'")


def share_after_drt(tag):
    p = os.path.join(ROOT, "results", tag, "flow.log.gz")
    if not os.path.exists(p):
        return None
    ts, names = [], []
    for line in gzip.open(p, "rt", errors="ignore"):
        m = STEP_RE.match(line)
        if m:
            h, mi, s = map(int, m.group(1).split(":"))
            ts.append(h * 3600 + mi * 60 + s)
            names.append(m.group(2))
    for i in range(1, len(ts)):
        while ts[i] < ts[i - 1]:
            ts[i] += 86400
    if "OpenROAD.DetailedRouting" not in names or len(ts) < 2 or ts[-1] <= ts[0]:
        return None
    i = names.index("OpenROAD.DetailedRouting")
    return (ts[-1] - ts[i]) / (ts[-1] - ts[0])


def report(js):
    st = load_state()
    tell_finished(st, dry=True)
    out = {}
    for d in DESIGNS:
        row = {}
        for arm in ("t", "r", "d", "e", "c"):
            vs = [v for v in st["tags"].values() if v["arm"] == arm and v["design"] == d]
            ok = [v for v in vs if v.get("feasible")]
            best = min(ok, key=lambda v: v["teff"]) if ok else None
            row[arm] = {"n": len(vs), "landed": sum(1 for v in vs if v["status"] not in ("dispatched", "pending")), "feasible": len(ok),
                        "best_teff": best["teff"] if best else None, "best_area": best.get("area") if best else None,
                        "best_power": best.get("power") if best else None,
                        "best_overrides": best["overrides"] if best else None,
                        "confirm_ok": (arm == "c" and len(vs) > 0 and all(v.get("feasible") and v.get("wns") is not None and v["wns"] >= 0 for v in vs))}
        # A24a: early stopping on the random sweep, keep the best 30% by the global-route proxy
        rs = [(tag, v) for tag, v in st["tags"].items() if v["arm"] == "r" and v["design"] == d and v["status"] not in ("dispatched", "pending")]
        prox = []
        for tag, v in rs:
            w = post_grt_wns(tag)
            if w is not None:
                prox.append((v["overrides"]["CLOCK_PERIOD"] - w, tag, v))
        prox.sort(key=lambda x: x[0])
        k = max(1, math.ceil(0.3 * len(prox)))
        kept = prox[:k]
        allf = [v["teff"] for _, _, v in prox if v.get("feasible")]
        keptf = [v["teff"] for _, _, v in kept if v.get("feasible")]
        shares = [s for s in (share_after_drt(tag) for _, tag, _ in prox) if s is not None]
        row["early_stop"] = {"ranked": len(prox), "kept": k, "best_all": min(allf) if allf else None,
                             "best_kept": min(keptf) if keptf else None,
                             "retained_within_2pct": (min(keptf) <= 1.02 * min(allf)) if (allf and keptf) else None,
                             "median_share_after_drt": (sorted(shares)[len(shares) // 2] if shares else None),
                             "skipped_share": ((1 - k / len(prox)) * sorted(shares)[len(shares) // 2]) if (shares and prox) else None}
        out[d] = row
        print(f"== {d} (default period {DESIGNS[d]['period']} ns)")
        for arm, name in (("t", "tuner"), ("r", "random"), ("d", "defaults"), ("e", "expert")):
            x = row[arm]
            print(f"  {name:8s} {x['landed']:2d}/{x['n']:2d} landed, {x['feasible']:2d} feasible, best T_eff "
                  f"{x['best_teff']:.2f} ns" if x["best_teff"] is not None else f"  {name:8s} {x['landed']:2d}/{x['n']:2d} landed, {x['feasible']:2d} feasible, best T_eff -")
        print(f"  early stop: {row['early_stop']}")
    res, overall = verdicts(out)
    for k, v in overall.items():
        print(f"  {k}: {v}  " + ", ".join(f"{d}={res[d][k]}" for d in res))
    if js:
        json.dump({"designs": out, "per_design": res, "overall": overall}, open(js, "w"), indent=1, default=str)
    return out


def confirm(dry):
    st = load_state()
    tell_finished(st, dry=True)
    new = []
    for d in DESIGNS:
        if any(v["arm"] == "c" and v["design"] == d for v in st["tags"].values()):
            continue
        mine = [v for v in st["tags"].values() if v["arm"] == "t" and v["design"] == d]
        if len(mine) < N_TRIALS or any(v["status"] in ("dispatched", "pending") for v in mine):
            print(f"[tune] {d}: tuner not finished ({sum(1 for v in mine if v['status'] not in ('dispatched', 'pending'))}/{N_TRIALS} landed)")
            continue
        ok = [v for v in mine if v.get("feasible")]
        if not ok:
            print(f"[tune] {d}: no feasible tuner trial to confirm")
            continue
        best = min(ok, key=lambda v: v["teff"])
        ov = dict(best["overrides"])
        ov["CLOCK_PERIOD"] = round(math.ceil(round(best["teff"] / 0.05, 6)) * 0.05, 2)
        tag = next_tag(st, "c", d)
        add(st, tag, d, "c", None, ov)
        new.append(tag)
    if not dry:
        save_state(st)
    send(st, [(new, 3)], f"Addendum 24: confirmation runs ({len(new)})", dry)


def verdicts(out):
    """A24a-d per design and overall (pass on >= 2 of 3; FAIL once 2 designs fail; else pending)."""
    INF = float("inf")
    res = {}
    for d, row in out.items():
        r, t, e = row["r"], row["t"], row["e"]
        es = row["early_stop"]
        a = None
        if r["landed"] == r["n"] == N_TRIALS:
            a = bool(es["retained_within_2pct"]) and (es["skipped_share"] or 0) >= 0.4
        b = c = None
        tb = t["best_teff"] if t["best_teff"] is not None else INF
        if t["landed"] == t["n"] == N_TRIALS and r["landed"] == r["n"] == N_TRIALS:
            rb = r["best_teff"] if r["best_teff"] is not None else INF
            b = tb < INF and (rb == INF or (rb - tb) / rb > 0.02)
        if t["landed"] == t["n"] == N_TRIALS and e["landed"] == e["n"] == len(FRACS):
            eb = e["best_teff"] if e["best_teff"] is not None else INF
            c = tb < INF and (eb == INF or (eb - tb) / eb > 0.05)
        cf = row.get("c", {})
        dd = None
        if cf.get("n") and cf.get("landed") == cf.get("n"):
            dd = bool(cf.get("confirm_ok"))
        res[d] = {"A24a": a, "A24b": b, "A24c": c, "A24d": dd}
    overall = {}
    for k in ("A24a", "A24b", "A24c", "A24d"):
        vals = [res[d][k] for d in res]
        p, f = sum(1 for v in vals if v is True), sum(1 for v in vals if v is False)
        overall[k] = "PASS" if p >= 2 else ("FAIL" if f >= 2 else "pending")
        overall[k] += f" ({p} pass, {f} fail, {len(vals) - p - f} pending)"
    return res, overall


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--confirm", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    DRY["on"] = a.dry_run
    if a.init:
        init(a.dry_run)
    if a.step:
        step(a.dry_run)
    if a.confirm:
        confirm(a.dry_run)
    if a.report:
        report(a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
