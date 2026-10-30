#!/usr/bin/env python3
"""Addendum 35: does feedback from physical results improve the next search? One-time vs repeated LLM guidance of TPE.

Races: 5 designs of Addendum 32 (xtea, cic_decimator, zipdiv, usb_cdc_core, wbqspiflash) x 2 new TPE seeds = 10 races.
Every race has four arms with the same start set (the 8 live borrowed runs of Addendum 30, already landed, told to every
arm's study as its first 8 trials), the same TPE (Addenda 24-33's sampler: multivariate, grouped, constant liar,
constraint-aware, seeded per race), the same budget (8 new runs: 4 rounds of 2) and the same closure + re-run chain.
  b  plain TPE (no policy)
  f  TPE with the tight-clock rule pinned by hand (period_frac = 0.45; Addendum 33's arm f)
  g  frozen LLM policy: before round 1 a fresh LLM instance reads the start set's signoff summaries and writes a POLICY
     (pins: up to 8 knobs fixed to values; TPE chooses the rest); g keeps it for all 4 rounds
  h  adaptive LLM policy: the same initial policy as g (the same reply), then before rounds 2, 3 and 4 a fresh LLM
     instance reads h's own landed runs (signoff summaries) and the policy history, and revises the policy
Policies may pin any of the 15 knobs within the space (period_frac included) and nothing else: no scores, constraints,
budgets, clock rules or RTL. Prompts and unedited replies are saved under farm/agent_a35/<design>/s<seed>/ and committed
with the job specs that use them, before dispatch. Out-of-range values are clamped and logged; pins beyond 8 are dropped.
Closure + chain as Addendum 32 (Amendment 32.2): each arm's best new run is re-run at ceil(T_eff/0.05)*0.05 ns (up to two
refinements after a miss), then re-run at the clock each passing run claims while it decreases, at most 4 re-runs in all.
Tags xa<arm><seed>-<design>-<nnn> (closure xak-, chain xac-).
Usage: tune_a35.py --policy-prompt | --policy-ingest | --init | --step | --report [--json f] [--dry-run]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tune as T  # noqa: E402
import tune_a27 as A  # noqa: E402
import tune_a32 as B  # noqa: E402  (start set, diagnostics, knob space, clamp, chain rules; sets A.* for x8 on import)

A.PREFIX = "xa"
A.TUNE = os.path.join(T.ROOT, "results", "tune_xa")
A.STATE = os.path.join(A.TUNE, "state.json")
AGENT_DIR = os.path.join(T.ROOT, "farm", "agent_a35")
DES = ["xtea", "cic_decimator", "zipdiv", "usb_cdc_core", "wbqspiflash"]
SEEDS = [1, 2]
ARMS = ["b", "f", "g", "h"]
ROUNDS, PER_ROUND, MAX_PINS, FLOOR = 4, 2, 8, 0.45
A.N_Z = 8
KN = {name: (kind, rng) for name, kind, rng, _ in B.KNOBS}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def seed35(d, s):
    return 3500 + 1000 * s + zlib.crc32(d.encode()) % 100000


def races():
    return [(d, s) for d in DES for s in SEEDS]


def aid(x, s):
    return f"{x}{s}"


def load():
    return A.load(A.STATE, {"tags": {}, "policies": {}})


def pkey(d, s, x):
    return f"{d}|{s}|{x}"


def pins_for(st, d, s, x, k):
    """The pins arm x uses in round k of race (d, s); None if its policy for that round is not decided yet."""
    if x == "b":
        return {}
    if x == "f":
        return {"period_frac": FLOOR}
    pol = st["policies"].get(pkey(d, s, "init"))
    if pol is None:
        return None
    if x == "g" or k == 1:
        return dict(pol["pins"])
    ups = {p["round"]: p for p in st["policies"].get(pkey(d, s, "h"), [])}
    return dict(ups[k]["pins"]) if k in ups else None


def study(d, x, s, pins):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(multivariate=True, group=True, constant_liar=True, n_startup_trials=A.N_Z,
                                         seed=seed35(d, s),
                                         constraints_func=lambda t: t.user_attrs.get("constraints", [1.0, 1.0, 1.0]))
    if pins:
        sampler = optuna.samplers.PartialFixedSampler(fixed_params=pins, base_sampler=sampler)
    path = os.path.join(A.TUNE, "dry" if A.DRY["on"] else "", f"{d}-{aid(x, s)}.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return optuna.create_study(study_name=f"{d}-{aid(x, s)}", storage=f"sqlite:///{path}", sampler=sampler,
                               direction="minimize", load_if_exists=True)


def warm(d, x, s):
    """Tell the start set to arm x's study once (first 8 trials, enqueued, as Addendum 32's init_b)."""
    sd = study(d, x, s, None)
    if len(sd.trials) >= 8:
        return
    for t, v, p in B.start_set(d):
        sd.enqueue_trial(p)
        tr = sd.ask()
        ov = A.suggest(tr, d)
        assert abs(ov["CLOCK_PERIOD"] - v["overrides"]["CLOCK_PERIOD"]) < 1e-6, (d, t)
        tr.set_user_attr("constraints", v.get("constraints") or [1e3, 1e3, 1e3])
        tr.set_user_attr("start_tag", t)
        sd.tell(tr, v["teff"] if v.get("teff") is not None else 2.0 * B.HELD[d])


def mine(st, d, s, x):
    return [dict(v, tag=t) for t, v in sorted(st["tags"].items()) if v["design"] == d and v["arm"] == aid(x, s)]


def next_round(st, d, s, x):
    rs = mine(st, d, s, x)
    if any(v["status"] in ("dispatched", "pending") for v in rs):
        return None
    k = max([v.get("round", 0) for v in rs] or [0]) + 1
    return k if k <= ROUNDS else None


def ask_round(st, d, s, x, k, pins):
    sd = study(d, x, s, pins)
    new = []
    for i in range(PER_ROUND):
        tr = sd.ask()
        ov = A.suggest(tr, d)
        for name, val in pins.items():
            assert tr.params[name] == val, (d, x, name, tr.params[name], val)
        tag = A.next_tag(st, aid(x, s), d)
        A.add(st, tag, d, aid(x, s), ov, params=dict(tr.params), trial=tr.number, round=k, slot=i, pins=dict(pins))
        new.append(tag)
    return new


# ---------------------------------------------------------------- policies (what the LLM reads and writes)

PROMPT = """You are guiding a Bayesian optimizer (Optuna's TPE sampler) that tunes the settings of an open-source chip design
flow (LibreLane/OpenROAD on the SkyWater sky130 130 nm process) for one design. Use ONLY the information in this message:
do not read files, run commands, search, or use anything you may know about other runs or designs. Reply with the JSON
described at the end and nothing else.

GOAL. Find settings that let this design pass signoff at the shortest clock period. Each run is scored by its effective
clock T_eff = (clock target it was given) - (worst setup slack over 9 signoff corners); lower is better. A run counts
only if it is FEASIBLE: hold slack >= 0 at every corner, zero router DRC errors, and no more slew/capacitance violation
pins (summed over the 9 corners) than the bar, which is set by the stock flow's run on this design. T_eff from a run
aimed at a much looser or tighter target can be optimistic: the best run will later be re-run at its T_eff, and then
again at the clock each passing re-run claims, and the result is the shortest clock that actually passes.

HOW THE SEARCH WORKS. The optimizer proposes {k} settings per round, for {rounds} rounds ({budget} runs), and learns from
every run's score and feasibility (including the start runs below). You do not propose settings. You write a POLICY:
you may PIN up to {maxpins} knobs to fixed values. For every new proposal the optimizer uses your pinned values and
chooses all other knobs itself from the history. An empty policy {{}} leaves the optimizer unchanged.{update_note}

DESIGN. {design}: {function}. Default clock period {default} ns. Stock flow: about {cells} standard cells. Bar: {bar}
slew/cap pins.

KNOBS (pin only these, within these ranges):
{knobs}

HISTORY on this design ({n} runs so far: 8 'start' runs are settings found on other designs and applied unchanged{hist_note}).
Each run shows its setting and a signoff summary.
{history}
{policy_history}
TASK. Write the policy for round {round} of {rounds}, using what the signoff summaries tell you (for example which
corner limits setup, whether the worst path touches a port, hold-buffer counts, slew/cap pins against the bar,
congestion, wire length against the pre-route estimate). Reply with JSON only, in this form:
{{"rationale": "<at most 120 words: what the reports suggest and why these pins>",
 "pins": {{"<knob>": <value>, ...}}}}
"""

UPDATE_NOTE = """ This is a revision: you see the
results of the rounds run under the earlier policies, and you may keep the policy, change pinned values, add pins or
remove pins."""


def policy_history_text(st, d, s, k):
    rows = [("round 1", st["policies"][pkey(d, s, "init")])]
    rows += [(f"round {p['round']}", p) for p in st["policies"].get(pkey(d, s, "h"), []) if p["round"] < k]
    out = ["POLICIES SO FAR (yours, with your rationale then):"]
    for lab, p in rows:
        out.append(f"- {lab}: pins {json.dumps(p['pins'], separators=(', ', ': '))}; rationale: {p.get('rationale', '')}")
    return "\n".join(out) + "\n"


def prompt_text(st, d, s, k):
    ref = B.ref_drv_x8(d)
    hist = []
    rows = B.start_set(d)
    for t, v, p in rows:
        hist.append(B.run_line(f"start {v['source_design']}", t, p, v, ref))
    n = len(rows)
    if k > 1:
        for v in mine(st, d, s, "h"):
            line = B.run_line(f"round {v['round']}", v["tag"], v.get("params"), v, ref)
            line = line.replace("\n  setting ", f"\n  pinned by the policy then: {json.dumps(v.get('pins', {}), separators=(', ', ': '))}\n  setting ", 1)
            hist.append(line)
            n += 1
    fn, cells = B.FUNCTION.get(d, ("", ""))
    return PROMPT.format(design=d, function=fn or "open-source design", default=B.HELD[d], cells=cells or "?", bar=ref,
                         knobs=B.knob_text(), n=n, history="\n".join(hist), round=k, rounds=ROUNDS, k=PER_ROUND,
                         budget=ROUNDS * PER_ROUND, maxpins=MAX_PINS, update_note=UPDATE_NOTE if k > 1 else "",
                         hist_note="; 'round' runs were proposed by the optimizer under your policies" if k > 1 else "",
                         policy_history=("\n" + policy_history_text(st, d, s, k)) if k > 1 else "")


def due_policies(st):
    """(design, seed, round) for every policy that is due now: the initial one, and h's revision before round k once
    h's round k-1 has landed."""
    out = []
    for d, s in races():
        if pkey(d, s, "init") not in st["policies"]:
            out.append((d, s, 1))
            continue
        k = next_round(st, d, s, "h")
        if k is not None and k > 1 and pins_for(st, d, s, "h", k) is None:
            out.append((d, s, k))
    return out


def ppath(d, s, k, what):
    return os.path.join(AGENT_DIR, d, f"s{s}", f"round{k}_{what}")


def policy_prompt():
    st = load()
    out, new = [], []
    for d, s, k in due_policies(st):
        p = ppath(d, s, k, "prompt.md")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        text = prompt_text(st, d, s, k)
        if os.path.exists(p):
            print(f"[a35] {d} s{s} round {k}: prompt already written ({'unchanged' if open(p).read() == text else 'kept'}) -> {p}")
        else:
            open(p, "w").write(text)
            print(f"[a35] {d} s{s} round {k}: prompt -> {p} ({len(text)} chars)")
            new.append(os.path.relpath(p, T.ROOT))
        out.append(p)
    if new and not A.DRY["on"]:          # bookkeeping: each prompt is committed as soon as it is written (before its reply)
        T.sh(["git", "add"] + new, check=True)
        if T.sh(["git", "commit", "-q", "-m", f"Addendum 35: policy prompts ({len(new)}), written before their replies"]).returncode == 0:
            for _ in range(5):
                T.sh(["git", "pull", "-q", "--rebase", "origin", "main"])
                if T.sh(["git", "push", "-q", "origin", "HEAD:main"]).returncode == 0:
                    break
    return out


def parse_policy(raw):
    m = re.search(r"\{.*\}", raw, re.S)
    rep = json.loads(m.group(0))
    pins_in = rep.get("pins") or {}
    log, pins = [], {}
    for name, val in pins_in.items():
        if name not in KN:
            log.append(f"{name}: not a knob -> dropped")
            continue
        if len(pins) >= MAX_PINS:
            log.append(f"{name}: beyond {MAX_PINS} pins -> dropped")
            continue
        kind, rng = KN[name]
        pins[name] = B.clamp(name, kind, rng, val, log)
    return {"rationale": str(rep.get("rationale", ""))[:1500], "pins": pins, "log": log}


def policy_ingest():
    """Read every due reply, validate, store; then ask and dispatch what the new policies unblock (via step)."""
    st = load()
    got = []
    for d, s, k in due_policies(st):
        f = ppath(d, s, k, "reply.json")
        if not os.path.exists(f):
            continue
        pol = parse_policy(open(f).read())
        pol.update({"round": k, "decided_at": now(), "prompt": os.path.relpath(ppath(d, s, k, "prompt.md"), T.ROOT),
                    "reply": os.path.relpath(f, T.ROOT)})
        if k == 1:
            st["policies"][pkey(d, s, "init")] = pol
        else:
            st["policies"].setdefault(pkey(d, s, "h"), []).append(pol)
        got.append((d, s, k))
        print(f"[a35] {d} s{s} round {k}: pins {json.dumps(pol['pins'])}" + (f"  (adjusted: {pol['log']})" if pol["log"] else ""))
    A.save(st)
    if got and not A.DRY["on"]:
        files = []
        for d, s, k in got:
            files += [os.path.relpath(ppath(d, s, k, w), T.ROOT) for w in ("prompt.md", "reply.json")]
        T.sh(["git", "add"] + files, check=True)   # committed together with the job specs by A.send in step()
    return got


# ---------------------------------------------------------------- tell / step / closure

def tell(st):
    told = 0
    for tag, v in st["tags"].items():
        if v["status"] != "dispatched":
            continue
        ref = B.ref_drv_x8(v["design"])
        status, teff, cons, m = T.outcome(tag, v["overrides"]["CLOCK_PERIOD"], ref)
        if status is None:
            continue
        j = A.load(os.path.join(T.ROOT, "results", tag, "job.json"), {})
        v.update({"status": status, "teff": teff, "constraints": cons, "feasible": T.feasible(cons), "landed_at": now(),
                  "area": m.get("design__instance__area__stdcell"), "hold": m.get("timing__hold__ws"),
                  "wns": m.get("timing__setup__ws"), "r2r_wns": m.get("timing__setup_r2r__ws"),
                  "drc": m.get("route__drc_errors"), "drv": T.drv_count(m) if m else None, "drv_ref": ref,
                  "power": m.get("power__total"), "flow_seconds": j.get("flow_seconds")})
        arm = v["arm"]
        if arm[0] in ARMS and v.get("trial") is not None and not A.DRY["on"]:
            x, s = arm[0], int(arm[1:])
            sd = study(v["design"], x, s, None)
            try:
                tid = sd._storage.get_trial_id_from_study_id_trial_number(sd._study_id, v["trial"])
                sd._storage.set_trial_user_attr(tid, "constraints", cons)
                sd.tell(v["trial"], teff if teff is not None else 2.0 * B.HELD[v["design"]])
            except Exception as e:
                print(f"[a35] tell {tag}: {e}")
        told += 1
    return told


def arm_best(st, d, s, x):
    rs = mine(st, d, s, x)
    ok = [v for v in rs if v.get("feasible") and v.get("teff") is not None]
    done = len(rs) == ROUNDS * PER_ROUND and all(v["status"] not in ("dispatched", "pending") for v in rs)
    return (min(ok, key=lambda v: v["teff"]) if ok else None), done


def chain_of(st, best_tag):
    ks = [dict(v, tag=t) for t, v in st["tags"].items() if v["arm"] == "k" and v.get("source") == best_tag]
    cs = [dict(v, tag=t) for t, v in st["tags"].items() if v["arm"] == "c" and v.get("root") == best_tag]
    return ks, cs


def closure_jobs(st):
    new = []
    for d, s in races():
        for x in ARMS:
            b, done = arm_best(st, d, s, x)
            if not done or b is None:
                continue
            ks, cs = chain_of(st, b["tag"])
            if any(v["status"] in ("dispatched", "pending") for v in ks + cs):
                continue
            if not any(B.passed(v) for v in ks):
                if len(ks) > B.MAX_REFINE:
                    continue
                if not ks:
                    clk = B.ceil05(b["teff"])
                else:
                    tm = [v["teff"] for v in ks if v.get("teff") is not None]
                    last = max(v["overrides"]["CLOCK_PERIOD"] for v in ks)
                    clk = max(B.ceil05(max(tm)) if tm else last + 0.05, round(last + 0.05, 2))
                ov = dict(b["overrides"])
                ov["CLOCK_PERIOD"] = clk
                tag = A.next_tag(st, "k", d)
                A.add(st, tag, d, "k", ov, source=b["tag"], source_arm=aid(x, s), params=b.get("params"))
                new.append(tag)
                print(f"[a35] {d} {aid(x, s)}: best {b['tag']} T_eff {b['teff']:.3f} -> closure {tag} at {clk} ns")
                continue
            nxt = B.chain_next(st, ks + cs, B.MAX_CHAIN)
            if nxt is None:
                continue
            last, clk = nxt
            ov = dict(last["overrides"])
            ov["CLOCK_PERIOD"] = clk
            tag = A.next_tag(st, "c", d)
            A.add(st, tag, d, "c", ov, source=last["tag"], root=b["tag"], source_arm=aid(x, s), params=b.get("params"))
            new.append(tag)
            print(f"[a35] {d} {aid(x, s)}: {last['tag']} passed at {last['overrides']['CLOCK_PERIOD']} -> re-run {tag} at {clk} ns")
    return new


def init():
    """Warm-start every race-arm study with the start set (no runs)."""
    for d, s in races():
        for x in ARMS:
            warm(d, x, s)
    st = load()
    st.setdefault("registered", "Addendum 35 (docs/BEFOREROUTE_PREREG.md)")
    st.setdefault("init_at", now())
    A.save(st)
    print("[a35] studies warm-started: " + ", ".join(f"{d}-{aid(x, s)}" for d, s in races() for x in ARMS))


def step():
    st = load()
    told = tell(st)
    A.save(st)
    new = []
    for d, s in races():
        for x in ARMS:
            k = next_round(st, d, s, x)
            if k is None:
                continue
            pins = pins_for(st, d, s, x, k)
            if pins is None:
                continue
            new += ask_round(st, d, s, x, k, pins)
    new += closure_jobs(st)
    retry = [t for t, v in st["tags"].items() if v["status"] == "pending" and t not in new]
    A.save(st)
    A.send(st, [(retry + new, 20)], f"Addendum 35: runs ({len(new)})" + (f", {len(retry)} re-sent" if retry else ""))
    due = due_policies(st)
    print(f"[a35] step: told {told}, asked {len(new)}, re-sent {len(retry)}; policies due: {due}")
    return new, due


# ---------------------------------------------------------------- report

def fixed_point(st, d, s, x):
    """(kind, value, best tag): checked = smallest clock passed in the chain of the arm's best (closure + re-runs);
    lower bound = largest closure clock failed when none passed; single = best run's T_eff while unchecked."""
    b, done = arm_best(st, d, s, x)
    if b is None:
        return ("none", None, None) if done else ("open", None, None)
    ks, cs = chain_of(st, b["tag"])
    landed = [v for v in ks + cs if v["status"] not in ("dispatched", "pending")]
    ok = [v["overrides"]["CLOCK_PERIOD"] for v in landed if B.passed(v)]
    if ok:
        return ("checked", min(ok), b["tag"])
    kl = [v for v in ks if v["status"] not in ("dispatched", "pending")]
    if len(kl) > B.MAX_REFINE:
        return ("lower bound", max(v["overrides"]["CLOCK_PERIOD"] for v in kl), b["tag"])
    return ("single", b["teff"], b["tag"])


def report(js):
    st = load()
    per, out = {}, {}
    for d, s in races():
        fp = {x: fixed_point(st, d, s, x) for x in ARMS}
        r = f"{d}|s{s}"
        per[r] = {"h>g": B.wins(fp["h"], fp["g"]), "g>h": B.wins(fp["g"], fp["h"]),
                  "h>f": B.wins(fp["h"], fp["f"]), "f>h": B.wins(fp["f"], fp["h"]),
                  "g>f": B.wins(fp["g"], fp["f"]), "f>g": B.wins(fp["f"], fp["g"]),
                  "f>b": B.wins(fp["f"], fp["b"]), "b>f": B.wins(fp["b"], fp["f"]),
                  "h>b": B.wins(fp["h"], fp["b"]), "b>h": B.wins(fp["b"], fp["h"]),
                  "g>b": B.wins(fp["g"], fp["b"]), "b>g": B.wins(fp["b"], fp["g"])}
        n = {x: (sum(1 for v in mine(st, d, s, x) if v["status"] not in ("dispatched", "pending")), len(mine(st, d, s, x)))
             for x in ARMS}
        out[r] = {"fixed_point": fp, "landed": n, "init_pins": (st["policies"].get(pkey(d, s, "init")) or {}).get("pins"),
                  "h_pins": [p["pins"] for p in st["policies"].get(pkey(d, s, "h"), [])], **per[r]}
        f = lambda z: f"{z[0]} {z[1]:.2f}" if z[1] is not None else z[0]
        print(f"== {r}: b {f(fp['b'])} | f {f(fp['f'])} | g {f(fp['g'])} | h {f(fp['h'])} | runs "
              + " ".join(f"{x} {n[x][0]}/{n[x][1]}" for x in ARMS))
    cnt = lambda key: sum(1 for r in per if per[r][key])
    R = len(per)
    overall = {}
    for name, a, b in (("A35a (h vs g: does repeated feedback help?)", "h>g", "g>h"),
                       ("A35b (h vs f: adaptive LLM policy vs the hand-coded rule)", "h>f", "f>h")):
        w, l = cnt(a), cnt(b)
        done = all(out[r]["fixed_point"][x][0] in ("checked", "lower bound", "none") for r in out for x in ARMS)
        verdict = "PASS" if (w >= 5 and l <= 2) else "FAIL"
        overall[name] = f"{verdict if done else 'pending'}: wins {w}, losses {l}, of {R} races (needs >= 5 wins and <= 2 losses)"
    for key in ("g>f", "f>g", "f>b", "b>f", "h>b", "b>h", "g>b", "b>g"):
        overall[key] = f"{cnt(key)} of {R}"
    pf = [out[r]["init_pins"] for r in out if out[r]["init_pins"] is not None]
    overall["A35e (initial policies pinning period_frac <= 0.5)"] = (
        f"{sum(1 for p in pf if p.get('period_frac') is not None and p['period_frac'] <= 0.5)} of {len(pf)}")
    for k, v in overall.items():
        print(f"  {k}: {v}")
    if js:
        json.dump({"races": out, "overall": overall, "at": now()}, open(js, "w"), indent=1, default=str)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--init", action="store_true")
    ap.add_argument("--policy-prompt", action="store_true")
    ap.add_argument("--policy-ingest", action="store_true")
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    A.DRY["on"] = a.dry_run
    T.DRY["on"] = a.dry_run
    B.check_space()
    if a.init:
        init()
    if a.policy_prompt:
        policy_prompt()
    if a.policy_ingest:
        policy_ingest()
    if a.step:
        step()
    if a.report:
        report(a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
