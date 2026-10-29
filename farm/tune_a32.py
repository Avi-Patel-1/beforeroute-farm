#!/usr/bin/env python3
"""Addendum 32: does an LLM that reads the signoff reports beat a Bayesian optimizer that sees only the scores?

Designs: the 7 held-out designs of Addendum 30. Start set (shared by both arms): the 8 live borrowed runs of Addendum 30
(arm z: the 8 settings frozen for Addendum 27, applied unchanged), already landed. Each arm then gets 8 new runs per
design, asked 2 at a time in 4 rounds; a round is asked once that arm's previous 2 runs on that design have landed.
  arm a  LLM agent. Each round a fresh LLM instance gets one prompt (written by --agent-prompt, saved with its reply under
         farm/agent_a32/<design>/ and committed with the round's job specs, before dispatch) holding only: the task, the knob space, facts about this design and this arm's
         history on it (start set + its earlier rounds, each with a signoff diagnostic summary and the agent's earlier
         rationales). It replies with exactly 2 settings in JSON. Values outside the space are clamped and logged.
  arm b  TPE, the sampler of Addenda 24-30 (multivariate, grouped, constant liar, constraint-aware), warm-started with the
         start set as 8 completed trials (parameters, T_eff, constraints); 2 trials asked per round.
Objective and feasibility as Addendum 30 (T_eff = clock - worst setup slack over 9 corners; hold >= 0, router DRC 0, no
more slew/cap pins than the design's stock reference run). Closure as Addendum 31: each arm's best new run (lowest T_eff,
feasible) is re-run at ceil(T_eff/0.05)*0.05 ns, and up to twice more at max(ceil(largest missed T_eff/0.05)*0.05,
f+0.05). Tags x8<arm>-<design>-<nnn> (k = closure).
Addendum 33: arm f = arm b with period_frac fixed at 0.45 (--init-f). Amendment 32.2: fixed-point re-run chains (arm c,
start set: arm s) in --closure; A32a3-c3, A33a-b in --report.
Usage: tune_a32.py --init-b | --init-f | --agent-prompt | --agent-ingest DIR | --step | --closure | --report [--json f] [--dry-run]
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import tune as T  # noqa: E402
import tune_a27 as A  # noqa: E402  (machinery: suggest with the RC knob, studies, tells, specs, dispatch)

A.PREFIX = "x8"
A.TUNE = os.path.join(T.ROOT, "results", "tune_x8")
A.STATE = os.path.join(A.TUNE, "state.json")
AGENT_DIR = os.path.join(T.ROOT, "farm", "agent_a32")   # tracked: prompts and replies are committed with the job specs
X6_STATE = os.path.join(T.ROOT, "results", "tune_x6", "state.json")
SOURCES = os.path.join(T.ROOT, "results", "tune_x4", "sources.json")
HELD = {"xtea": 26.03, "zipdiv": 19.09, "usb_cdc_core": 15.6, "wbqspiflash": 18.86, "cic_decimator": 10.0, "APU": 17.0,
        "PPU": 18.0}
A.NEW = dict(HELD)
A.TUNED = {}
A.DESIGNS = {d: {"dir": f"designs/{d}", "config": "config_sky130.json", "period": p} for d, p in HELD.items()}
A.N_Z = 8                      # TPE start-up trials = the 8 start-set trials (TPE models from the first ask on)
ROUNDS, PER_ROUND, SEED = 4, 2, 2032
MAX_REFINE = 2
FUNCTION = {}
try:
    import csv
    for r in csv.DictReader(open(os.path.join(T.ROOT, "agents", "results_page", "out", "designs.csv"))):
        FUNCTION[r["design"]] = (r.get("function") or "", r.get("std_cells") or "")
except Exception:
    pass

# the knob space, exactly as farm/tune.py suggest() + farm/tune_a25.py RC_MODEL (ranges parsed from the source of truth)
KNOBS = [
    ("period_frac", "float", (0.45, 1.0), "clock target as a fraction of the design's default clock period"),
    ("FP_CORE_UTIL", "int", (20, 50), "core utilisation, % (lower leaves room for wires and late repairs)"),
    ("density_delta", "int", (5, 30), "placement density = utilisation + this many points (capped at 80)"),
    ("SYNTH_STRATEGY", "cat", ("AREA 0", "AREA 1", "AREA 2", "AREA 3", "DELAY 0", "DELAY 1", "DELAY 2", "DELAY 3", "DELAY 4"),
     "Yosys/ABC synthesis script (AREA = smaller, DELAY = faster logic)"),
    ("SYNTH_ABC_BUFFERING", "bool", (False, True), "insert buffers during synthesis"),
    ("SYNTH_SIZING", "bool", (False, True), "resize gates during synthesis"),
    ("PL_TIMING_DRIVEN", "bool", (False, True), "timing-driven global placement"),
    ("PL_ROUTABILITY_DRIVEN", "bool", (False, True), "routability-driven global placement (spreads cells in crowded areas)"),
    ("RUN_POST_GRT_RESIZER_TIMING", "bool", (False, True), "timing repair again after global routing"),
    ("RUN_POST_GRT_DESIGN_REPAIR", "bool", (False, True), "slew/cap/fanout repair again after global routing"),
    ("PL_RESIZER_SETUP_SLACK_MARGIN", "float", (0.0, 0.4), "extra setup margin (ns) placement-stage repair aims for"),
    ("GRT_RESIZER_SETUP_SLACK_MARGIN", "float", (0.0, 0.4), "extra setup margin (ns) post-global-route repair aims for"),
    ("DESIGN_REPAIR_MAX_SLEW_PCT", "int", (10, 40), "repair aims this % below the slew limit"),
    ("DESIGN_REPAIR_MAX_CAP_PCT", "int", (10, 40), "repair aims this % below the capacitance limit"),
    ("RC_MODEL", "cat", ("stock", "cap213", "orfs"),
     "wire R/C assumed before routing: stock LEF values; cap213 = wire capacitance x2.13 (measured gap to signoff "
     "extraction in this flow); orfs = OpenROAD-flow-scripts per-layer values"),
]


def check_space():
    """The ranges above must match farm/tune.py and farm/tune_a25.py (refuse to run otherwise)."""
    src = open(os.path.join(HERE, "tune.py")).read()
    for name, kind, rng, _ in KNOBS:
        if kind in ("float", "int"):
            m = re.search(r'suggest_(float|int)\("%s",\s*([0-9.]+),\s*([0-9.]+)\)' % name, src)
            assert m and (float(m.group(2)), float(m.group(3))) == (float(rng[0]), float(rng[1])), name
    assert "STRATEGIES = " + json.dumps(list(KNOBS[3][2])) in src.replace("'", '"')
    assert 'suggest_categorical("RC_MODEL", ["stock", "cap213", "orfs"])' in open(os.path.join(HERE, "tune_a25.py")).read()


def ref_drv_x8(d):
    """The Addendum-30 electrical reference: the design's stock run at the default clock (or Amendment 27.1's fallback)."""
    st = A.load(X6_STATE, {"tags": {}})["tags"]
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


A.ref_drv = ref_drv_x8


def start_set(d):
    """The 8 live borrowed runs of Addendum 30 on design d: (tag, record, Optuna params)."""
    st = A.load(X6_STATE, {"tags": {}})["tags"]
    src = json.load(open(SOURCES))["sources"]
    out = []
    for t, v in sorted(st.items()):
        if v["design"] == d and v["arm"] == "z" and v.get("status") != "superseded":
            out.append((t, v, dict(src[v["source_design"]]["params"])))
    assert len(out) == 8, (d, len(out))
    return out


def seed(d):
    return SEED + zlib.crc32(d.encode()) % 100000


FLOOR = 0.45          # Addendum 33: arm f fixes period_frac at the floor of the space


def tpe_study(d, arm="b"):
    import optuna
    optuna.logging.set_verbosity(optuna.logging.WARNING)
    sampler = optuna.samplers.TPESampler(multivariate=True, group=True, constant_liar=True, n_startup_trials=A.N_Z,
                                         seed=seed(d),
                                         constraints_func=lambda t: t.user_attrs.get("constraints", [1.0, 1.0, 1.0]))
    if arm == "f":
        sampler = optuna.samplers.PartialFixedSampler(fixed_params={"period_frac": FLOOR}, base_sampler=sampler)
    os.makedirs(A.TUNE, exist_ok=True)
    path = os.path.join(A.TUNE, "dry" if A.DRY["on"] else "", f"{d}-{arm}.db")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    return optuna.create_study(study_name=f"{d}-{arm}", storage=f"sqlite:///{path}", sampler=sampler, direction="minimize",
                               load_if_exists=True)


# ---------------------------------------------------------------- diagnostics (what the agent reads)

def corner_short(c):
    m = re.match(r"(nom|min|max)_(tt|ss|ff)_(n?\d+)C_(\d)v(\d+)", c)
    return c if not m else f"{m.group(2)} {m.group(3).replace('n', '-')}C {m.group(4)}.{m.group(5)}V {m.group(1)}-RC"


def diagnostics(tag, clock, ref):
    """A compact signoff summary of one run, from results/<tag>/metrics.json and job.json."""
    r = os.path.join(T.ROOT, "results", tag)
    m = A.load(os.path.join(r, "metrics.json"), {})
    j = A.load(os.path.join(r, "job.json"), {})
    if m.get("timing__setup__ws") is None:
        err = ""
        try:
            e = open(os.path.join(r, "error.log"), errors="replace").read()
            mm = re.findall(r"\[(?:ERROR )?([A-Z]{2,4}-\d{4})\][^\n]{0,120}", e)
            err = mm[-1] if mm else e.strip().splitlines()[-1][:160] if e.strip() else ""
        except Exception:
            pass
        return f"  run stopped before signoff ({j.get('status', 'failed')}){'; last error: ' + err if err else ''}"
    corners = sorted({k.split("corner:")[1] for k in m if k.startswith("timing__setup__ws__corner:")})
    ws = {c: m["timing__setup__ws__corner:" + c] for c in corners}
    hs = {c: m.get("timing__hold__ws__corner:" + c) for c in corners}
    cw = min(ws, key=ws.get)
    ch = min((c for c in corners if hs[c] is not None), key=lambda c: hs[c], default=None)
    worst_ws, r2r = m.get("timing__setup__ws"), m.get("timing__setup_r2r__ws")
    io_limited = r2r is not None and worst_ws is not None and worst_ws < r2r - 1e-3
    slew = max([m.get(k) or 0 for k in m if k.startswith("design__max_slew_violation__count__corner:")] or [0])
    cap = max([m.get(k) or 0 for k in m if k.startswith("design__max_cap_violation__count__corner:")] or [0])
    fo = m.get("design__max_fanout_violation__count") or 0
    drc_it = [m.get(f"route__drc_errors__iter:{i}") for i in range(0, 64) if m.get(f"route__drc_errors__iter:{i}") is not None]
    wl, wl_est = m.get("route__wirelength"), m.get("route__wirelength__estimated")
    lines = [
        f"  setup: worst slack {worst_ws:+.3f} ns at {corner_short(cw)} (reg-to-reg worst {r2r:+.3f} ns"
        f"{'; the worst path touches an input/output port' if io_limited else ''}); TNS {m.get('timing__setup__tns', 0):.2f} ns; "
        f"{m.get('timing__setup_vio__count', 0)} violating endpoints at the target",
        f"  hold: worst slack {m.get('timing__hold__ws', 0):+.3f} ns" + (f" at {corner_short(ch)}" if ch else "")
        + f"; {m.get('timing__hold_vio__count', 0)} violations; {m.get('design__instance__count__hold_buffer', 0)} hold buffers inserted",
        f"  electrical: {T.drv_count(m)} slew/cap pins summed over corners (bar {ref}); worst corner max-slew {slew}, max-cap {cap}; "
        f"fanout violations {fo}",
        f"  cells: {m.get('design__instance__count__stdcell', 0)} std cells, {m.get('design__instance__count__class:timing_repair_buffer', 0)} "
        f"timing-repair buffers; std-cell area {m.get('design__instance__area__stdcell', 0):,.0f} um2; utilisation "
        f"{100 * (m.get('design__instance__utilization') or 0):.0f}%",
        f"  routing: wirelength {wl or 0:,.0f} um (pre-route estimate {wl_est or 0:,.0f}); detailed-route DRC by iteration "
        f"{drc_it[:6]}{'...' if len(drc_it) > 6 else ''}, final {m.get('route__drc_errors', 0)}",
        f"  clock: skew {m.get('clock__skew__worst_setup', 0):.3f} ns (setup) / {m.get('clock__skew__worst_hold', 0):.3f} ns (hold); "
        f"power {1000 * (m.get('power__total') or 0):.2f} mW; flow runtime {round((j.get('flow_seconds') or 0) / 60, 1)} min",
    ]
    return "\n".join(lines)


def params_of(v):
    """Optuna-style parameters of a run of this study (start set: from sources; arms a/b: stored)."""
    return v.get("params")


def fmt_params(p):
    return json.dumps(p, separators=(", ", ": "))


def history(st, d, arm):
    """Start set + the arm's own runs on d, oldest first, as (label, tag, params, record, rationale)."""
    rows = []
    for t, v, p in start_set(d):
        rows.append((f"start {v['source_design']}", t, p, v, None))
    for t, v in sorted(st["tags"].items()):
        if v["design"] == d and v["arm"] == arm:
            rows.append((f"round {v.get('round')}", t, v.get("params"), v, v.get("rationale")))
    return rows


def run_line(label, tag, p, v, ref):
    teff, feas = v.get("teff"), v.get("feasible")
    if v.get("status") in ("dispatched", "pending"):
        return f"- {label} [{tag}] still running; setting {fmt_params(p)}"
    why = []
    cons = v.get("constraints") or []
    if cons and v.get("teff") is not None:
        if cons[0] > 0:
            why.append("router DRC errors")
        if cons[1] > 0:
            why.append("hold violated")
        if cons[2] > 0:
            why.append("more slew/cap pins than the bar")
    clock = (v.get("overrides") or {}).get("CLOCK_PERIOD")
    head = (f"- {label} [{tag}] clock target {clock} ns -> T_eff {teff:.3f} ns, "
            f"{'FEASIBLE' if feas else 'INFEASIBLE (' + ', '.join(why) + ')'}" if teff is not None else f"- {label} [{tag}] no result")
    return head + f"\n  setting {fmt_params(p)}\n" + diagnostics(tag, clock, ref)


PROMPT = """You are tuning the settings of an open-source chip design flow (LibreLane/OpenROAD on the SkyWater sky130 130 nm
process) for one design. Use ONLY the information in this message: do not read files, run commands, search, or use
anything you may know about other runs or designs. Reply with the JSON described at the end and nothing else.

GOAL. Find settings that let this design pass signoff at the shortest clock period. Each run is scored by its effective
clock T_eff = (clock target it was given) - (worst setup slack over 9 signoff corners); lower is better. A run counts
only if it is FEASIBLE: hold slack >= 0 at every corner, zero router DRC errors, and no more slew/capacitance violation
pins (summed over the 9 corners) than the bar, which is set by the stock flow's run on this design. Note: T_eff from a
run aimed at a much looser or tighter target can be optimistic; the best run will later be re-checked at its T_eff.

DESIGN. {design}: {function}. Default clock period {default} ns. Stock flow: about {cells} standard cells. Bar: {bar}
slew/cap pins.

KNOBS (the only things you can set; give every knob, within these ranges):
{knobs}

HISTORY on this design ({n} runs so far: 8 'start' runs are settings found on other designs and applied unchanged;
'round' runs are your own earlier proposals, with your rationale). Each run shows its setting and a signoff summary.
{history}

TASK. Round {round} of {rounds}. Propose exactly {k} NEW settings for this design (different from every setting above),
chosen to lower the best feasible T_eff, using what the signoff summaries tell you (for example which corner limits
setup, whether the worst path touches a port, hold-buffer counts, slew/cap pins against the bar, congestion, wire length
against the pre-route estimate). Reply with JSON only, in this form:
{{"rationale": "<at most 120 words: what the reports suggest and why these settings>",
 "settings": [{{<all 15 knobs>}}, {{<all 15 knobs>}}]}}
"""


def knob_text():
    out = []
    for name, kind, rng, what in KNOBS:
        r = f"{rng[0]} to {rng[1]}" if kind in ("float", "int") else (" | ".join(map(str, rng)) if kind == "cat" else "true | false")
        out.append(f"- {name} ({kind}: {r}): {what}")
    return "\n".join(out)


def agent_round(st, d):
    """The next agent round for d (1-based) if its previous round has landed and fewer than ROUNDS were asked, else None."""
    mine = [v for v in st["tags"].values() if v["design"] == d and v["arm"] == "a"]
    if any(v["status"] in ("dispatched", "pending") for v in mine):
        return None
    k = max([v.get("round", 0) for v in mine] or [0]) + 1
    return k if k <= ROUNDS else None


def agent_prompt():
    """Write the prompt for every design whose next agent round is due; print the files."""
    st = A.load(A.STATE, {"tags": {}})
    os.makedirs(AGENT_DIR, exist_ok=True)
    out = []
    for d in HELD:
        k = agent_round(st, d)
        if k is None:
            continue
        ref = ref_drv_x8(d)
        rows = history(st, d, "a")
        hist = []
        for label, tag, p, v, why in rows:
            line = run_line(label, tag, p, v, ref)
            if why:
                line += f"\n  (your rationale then: {why})"
            hist.append(line)
        fn, cells = FUNCTION.get(d, ("", ""))
        text = PROMPT.format(design=d, function=fn or "open-source design", default=HELD[d], cells=cells or "?", bar=ref,
                             knobs=knob_text(), n=len(rows), history="\n".join(hist), round=k, rounds=ROUNDS, k=PER_ROUND)
        p = os.path.join(AGENT_DIR, d, f"round{k}_prompt.md")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        if os.path.exists(p):                      # a written prompt is part of the record: never rewrite it
            same = open(p).read() == text
            print(f"[a32] {d}: agent round {k} prompt already written ({'unchanged' if same else 'kept; history has changed since'}) -> {p}")
            out.append(p)
            continue
        open(p, "w").write(text)
        out.append(p)
        print(f"[a32] {d}: agent round {k} prompt -> {p} ({len(text)} chars)")
    return out


def clamp(name, kind, rng, val, log):
    if kind == "bool":
        if isinstance(val, str):
            val = val.strip().lower() in ("true", "1", "yes", "on")
        return bool(val)
    if kind == "cat":
        if val in rng:
            return val
        log.append(f"{name}={val!r} not allowed -> {rng[0]!r}")
        return rng[0]
    try:
        x = float(val)
    except Exception:
        log.append(f"{name}={val!r} not a number -> midpoint")
        x = (rng[0] + rng[1]) / 2
    y = min(max(x, rng[0]), rng[1])
    if y != x:
        log.append(f"{name}={x} clamped to {y}")
    return int(round(y)) if kind == "int" else round(y, 4)


def agent_ingest(src_dir):
    """Read <design>/round<k>_reply.json for every due round, validate, add 2 jobs per design, dispatch."""
    st = A.load(A.STATE, {"tags": {}})
    new = []
    for d in HELD:
        k = agent_round(st, d)
        if k is None:
            continue
        f = os.path.join(src_dir, d, f"round{k}_reply.json")
        if not os.path.exists(f):
            continue
        raw = open(f).read()
        m = re.search(r"\{.*\}", raw, re.S)
        rep = json.loads(m.group(0))
        sets = rep["settings"][:PER_ROUND]
        if len(sets) < PER_ROUND:
            raise SystemExit(f"{d}: reply has {len(sets)} settings")
        for i, s in enumerate(sets):
            log = []
            p = {name: clamp(name, kind, rng, s.get(name), log) for name, kind, rng, _ in KNOBS}
            missing = [name for name, *_ in KNOBS if name not in s]
            if missing:
                log.append(f"missing {missing} -> defaults used")
            ov = A.fixed(p, d)
            tag = A.next_tag(st, "a", d)
            A.add(st, tag, d, "a", ov, params=p, round=k, slot=i, rationale=rep.get("rationale", "")[:1200], clamp_log=log,
                  reply_file=os.path.relpath(f, T.ROOT))
            new.append(tag)
            print(f"[a32] {d} round {k}: {tag} {fmt_params(p)}" + (f"  (adjusted: {log})" if log else ""))
    A.save(st)
    if new and not A.DRY["on"]:
        logs = sorted({os.path.relpath(p, T.ROOT) for t in new for p in (
            os.path.join(T.ROOT, st["tags"][t]["reply_file"]),
            os.path.join(T.ROOT, os.path.dirname(st["tags"][t]["reply_file"]), f"round{st['tags'][t]['round']}_prompt.md"))})
        T.sh(["git", "add"] + logs, check=True)   # committed together with the job specs by A.send
    A.send(st, [(new, 20)], f"Addendum 32: LLM-agent runs ({len(new)}), with the prompts and replies")
    return new


def init_b(arm="b"):
    """Warm-start each design's TPE study with the start set, then ask round 1 (2 trials per design). arm f (Addendum 33):
    the same, with period_frac fixed at FLOOR for every new trial."""
    import optuna
    st = A.load(A.STATE, {"tags": {}})
    if any(v["arm"] == arm for v in st["tags"].values()):
        raise SystemExit(f"arm {arm} already initialised")
    new = []
    for d in HELD:
        s = tpe_study(d, arm)
        if len(s.trials) == 0:
            for t, v, p in start_set(d):
                s.enqueue_trial(p)
                tr = s.ask()
                ov = A.suggest(tr, d)
                assert abs(ov["CLOCK_PERIOD"] - v["overrides"]["CLOCK_PERIOD"]) < 1e-6, (d, t)
                cons = v.get("constraints") or [1e3, 1e3, 1e3]
                tr.set_user_attr("constraints", cons)
                tr.set_user_attr("start_tag", t)
                s.tell(tr, v["teff"] if v.get("teff") is not None else 2.0 * HELD[d])
        for i in range(PER_ROUND):
            tr = s.ask()
            ov = A.suggest(tr, d)
            if arm == "f":
                assert abs(tr.params["period_frac"] - FLOOR) < 1e-12, tr.params
            tag = A.next_tag(st, arm, d)
            A.add(st, tag, d, arm, ov, params=dict(tr.params), trial=tr.number, round=1, slot=i)
            new.append(tag)
    A.save(st)
    what = "Addendum 32: TPE" if arm == "b" else "Addendum 33: TPE with period_frac fixed at the floor"
    A.send(st, [(new, 20)], f"{what}, warm-start runs, round 1 ({len(new)})")
    print(f"[a32] arm {arm}: {len(new)} round-1 jobs")


def tell(st):
    """Tell landed runs (both arms); TPE trials are told to their study."""
    import optuna
    told = 0
    for tag, v in st["tags"].items():
        if v["status"] != "dispatched":
            continue
        ref = ref_drv_x8(v["design"])
        status, teff, cons, m = T.outcome(tag, v["overrides"]["CLOCK_PERIOD"], ref)
        if status is None:
            continue
        j = A.load(os.path.join(T.ROOT, "results", tag, "job.json"), {})
        v.update({"status": status, "teff": teff, "constraints": cons, "feasible": T.feasible(cons), "landed_at": A.now(),
                  "area": m.get("design__instance__area__stdcell"), "hold": m.get("timing__hold__ws"),
                  "wns": m.get("timing__setup__ws"), "drc": m.get("route__drc_errors"), "drv": T.drv_count(m) if m else None,
                  "drv_ref": ref, "flow_seconds": j.get("flow_seconds")})
        if v["arm"] in ("b", "f") and not A.DRY["on"]:
            s = tpe_study(v["design"], v["arm"])
            try:
                tid = s._storage.get_trial_id_from_study_id_trial_number(s._study_id, v["trial"])
                s._storage.set_trial_user_attr(tid, "constraints", cons)
                s.tell(v["trial"], teff if teff is not None else 2.0 * HELD[v["design"]])
            except Exception as e:
                print(f"[a32] tell {tag}: {e}")
        told += 1
    return told


def step():
    st = A.load(A.STATE, None)
    if st is None:
        print("[a32] not initialised")
        return
    told = tell(st)
    A.save(st)
    new = []
    for arm in ("b", "f"):
        for d in HELD:
            mine = [v for v in st["tags"].values() if v["design"] == d and v["arm"] == arm]
            if not mine or any(v["status"] in ("dispatched", "pending") for v in mine):
                continue
            k = max(v.get("round", 0) for v in mine) + 1
            if k > ROUNDS:
                continue
            s = tpe_study(d, arm)
            for i in range(PER_ROUND):
                tr = s.ask()
                ov = A.suggest(tr, d)
                if arm == "f":
                    assert abs(tr.params["period_frac"] - FLOOR) < 1e-12, tr.params
                tag = A.next_tag(st, arm, d)
                A.add(st, tag, d, arm, ov, params=dict(tr.params), trial=tr.number, round=k, slot=i)
                new.append(tag)
    retry = [t for t, v in st["tags"].items() if v["status"] == "pending" and t not in new]
    A.save(st)
    A.send(st, [(retry + new, 20)], f"Addendum 32: TPE runs ({len(new)})" + (f", {len(retry)} re-sent" if retry else ""))
    due = [d for d in HELD if agent_round(st, d) is not None and any(v["design"] == d and v["arm"] == "a" for v in st["tags"].values())]
    print(f"[a32] step: told {told}, TPE asked {len(new)}, re-sent {len(retry)}; agent rounds due: {due}")


def arm_best(st, d, arm):
    rs = [dict(v, tag=t) for t, v in st["tags"].items() if v["design"] == d and v["arm"] == arm]
    ok = [v for v in rs if v.get("feasible") and v.get("teff") is not None]
    done = len(rs) == ROUNDS * PER_ROUND and all(v["status"] not in ("dispatched", "pending") for v in rs)
    return (min(ok, key=lambda v: v["teff"]) if ok else None), done


def ceil05(x):
    return round(math.ceil(round(x / 0.05, 6)) * 0.05, 2)


def closure():
    """Addendum 31's rule for each arm's best new run: first run at ceil(T_eff); up to MAX_REFINE more."""
    st = A.load(A.STATE, None)
    if st is None:
        return
    tell(st)
    new = []
    for d in HELD:
        for arm in ("a", "b", "f"):
            b, done = arm_best(st, d, arm)
            if not done or b is None:
                continue
            runs = [dict(v, tag=t) for t, v in st["tags"].items() if v["arm"] == "k" and v.get("source") == b["tag"]]
            if any(v["status"] in ("dispatched", "pending") for v in runs):
                continue
            passed = [v for v in runs if v.get("feasible") and (v.get("wns") or -1) >= 0]
            if passed:
                continue
            if len(runs) > MAX_REFINE:
                continue
            if not runs:
                clk = ceil05(b["teff"])
            else:
                missed = max(v["teff"] for v in runs if v.get("teff") is not None) if any(v.get("teff") is not None for v in runs) else None
                last = max(v["overrides"]["CLOCK_PERIOD"] for v in runs)
                clk = max(ceil05(missed) if missed else last + 0.05, round(last + 0.05, 2))
            ov = dict(b["overrides"])
            ov["CLOCK_PERIOD"] = clk
            tag = A.next_tag(st, "k", d)
            A.add(st, tag, d, "k", ov, source=b["tag"], source_arm=arm, params=b.get("params"))
            new.append(tag)
            print(f"[a32] {d} arm {arm}: best {b['tag']} T_eff {b['teff']:.3f} -> closure {tag} at {clk} ns")
    # Amendments 32.1/32.2: once an arm's closure passes, keep re-running the last passing run at ceil(its T_eff) while
    # that is lower, until a miss, no decrease, or 4 re-runs in the chain (closure included); start set: tags x8s
    for d in HELD:
        for arm in ("a", "b", "f"):
            b, done = arm_best(st, d, arm)
            if not done or b is None:
                continue
            nxt = chain_next(st, chain_runs(st, b["tag"]), MAX_CHAIN)
            if nxt is None:
                continue
            last, clk = nxt
            ov = dict(last["overrides"])
            ov["CLOCK_PERIOD"] = clk
            tag = A.next_tag(st, "c", d)
            A.add(st, tag, d, "c", ov, source=last["tag"], root=b["tag"], source_arm=arm, params=b.get("params"))
            new.append(tag)
            print(f"[a32] {d} arm {arm}: {last['tag']} passed at {last['overrides']['CLOCK_PERIOD']} (T_eff {last['teff']:.3f}) "
                  f"-> re-run {tag} at {clk} ns")
        # the start set's checked point, continued from its passing closure run (Amendment 32.2)
        sp = start_point(d)
        if sp and sp.get("closed_tag"):
            root = sp["closed_tag"]
            rec = find_run(root)
            if rec and rec.get("teff") is not None:
                chain = [dict(rec, tag=root)] + [dict(v, tag=t) for t, v in st["tags"].items() if v["arm"] == "s" and v.get("root") == root]
                nxt = chain_next(st, chain, 1 + MAX_START_EXTRA)
                if nxt is not None:
                    last, clk = nxt
                    ov = dict(last["overrides"])
                    ov["CLOCK_PERIOD"] = clk
                    tag = A.next_tag(st, "s", d)
                    A.add(st, tag, d, "s", ov, source=last["tag"], root=root, source_arm="start")
                    new.append(tag)
                    print(f"[a32] {d} start: {last['tag']} passed at {last['overrides']['CLOCK_PERIOD']} (T_eff "
                          f"{last['teff']:.3f}) -> re-run {tag} at {clk} ns")
    A.save(st)
    A.send(st, [(new, 20)], f"Addendum 32: closure runs ({len(new)})")


MAX_CHAIN = 4          # Amendment 32.2: re-runs per arm's best, closure included
MAX_START_EXTRA = 2    # the start set's point already had two re-runs (Addendum 30's re-run arm + closure)


def passed(v):
    return v.get("feasible") and v.get("wns") is not None and v["wns"] >= 0 and v.get("teff") is not None


def chain_runs(st, best_tag):
    """Closure runs of an arm's best plus its Amendment 32.1/32.2 re-runs (arm c rooted at it)."""
    ks = [dict(v, tag=t) for t, v in st["tags"].items() if v["arm"] == "k" and v.get("source") == best_tag]
    kt = {v["tag"] for v in ks}
    cs = [dict(v, tag=t) for t, v in st["tags"].items() if v["arm"] == "c" and (v.get("root") == best_tag or v.get("source") in kt)]
    return ks + cs


def chain_next(st, chain, cap):
    """(last passing run, next clock) or None: the next fixed-point re-run if one is due."""
    if not chain or any(v.get("status") in ("dispatched", "pending") for v in chain):
        return None
    ok = [v for v in chain if passed(v)]
    if not ok or len(chain) >= cap:
        return None
    last = min(ok, key=lambda v: v["overrides"]["CLOCK_PERIOD"])
    clk = ceil05(last["teff"])
    lastclk = last["overrides"]["CLOCK_PERIOD"]
    failed = [v["overrides"]["CLOCK_PERIOD"] for v in chain if v.get("status") not in ("dispatched", "pending") and not passed(v)]
    if clk >= lastclk - 1e-9 or any(f >= clk - 1e-9 and f < lastclk for f in failed):
        return None
    return last, clk


def find_run(tag):
    for path in (X6_STATE, os.path.join(T.ROOT, "results", "tune_x7", "state.json"), A.STATE):
        r = A.load(path, {"tags": {}})["tags"].get(tag)
        if r:
            return r
    return None


def start_point(d):
    rep = A.load(os.path.join(T.ROOT, "agents", "analysis", "closure_a31_report.json"), {})
    pts = {p.get("point"): p for p in rep.get("points") or [] if p.get("design") == d}
    return pts.get("borrowed") or pts.get("md5")


def fixed_point(st, d, arm):
    """Amendment 32.2: (kind, smallest passing clock in the chain of the arm's best, best tag)."""
    k = checked(st, d, arm)
    if k[0] != "checked":
        return k
    ok = [v["overrides"]["CLOCK_PERIOD"] for v in chain_runs(st, k[2]) if passed(v) and v.get("status") not in ("dispatched", "pending")]
    return ("checked", min([k[1]] + ok), k[2])


def start_fixed(st, d):
    z = start_checked(d)
    sp = start_point(d)
    if z[0] != "checked" or not sp or not sp.get("closed_tag"):
        return z
    ok = [v["overrides"]["CLOCK_PERIOD"] for v in st["tags"].values() if v["arm"] == "s" and v.get("root") == sp["closed_tag"]
          and v.get("status") not in ("dispatched", "pending") and passed(v)]
    return ("checked", min([z[1]] + ok))


def checked(st, d, arm):
    """(kind, value, best tag): checked = smallest clock passed by a closure run of the arm's best; lower bound = largest
    clock failed when none passed; single = the best run's T_eff while its closure has not landed."""
    b, done = arm_best(st, d, arm)
    if b is None:
        return ("none", None, None) if done else ("open", None, None)
    runs = [v for t, v in st["tags"].items() if v["arm"] == "k" and v.get("source") == b["tag"] and v["status"] not in ("dispatched", "pending")]
    ok = [v["overrides"]["CLOCK_PERIOD"] for v in runs if v.get("feasible") and (v.get("wns") or -1) >= 0]
    if ok:
        return ("checked", min(ok), b["tag"])
    if len(runs) > MAX_REFINE:
        return ("lower bound", max(v["overrides"]["CLOCK_PERIOD"] for v in runs), b["tag"])
    return ("single", b["teff"], b["tag"])


def checked2(st, d, arm):
    """Amendment 32.1: the smaller passing clock of the arm's closure and its second re-run (closure value while the
    second re-run is missing, running or failed)."""
    k = checked(st, d, arm)
    if k[0] != "checked":
        return k
    ks = {t for t, v in st["tags"].items() if v["arm"] == "k" and v.get("source") == k[2]}
    ok = [v["overrides"]["CLOCK_PERIOD"] for v in st["tags"].values() if v["arm"] == "c" and v.get("source") in ks
          and v["status"] not in ("dispatched", "pending") and v.get("feasible") and (v.get("wns") or -1) >= 0]
    return ("checked", min([k[1]] + ok), k[2])


def start_checked(d):
    """The start set's best, checked (Addendum 31.2's 'borrowed' point for d), from the closure report."""
    rep = A.load(os.path.join(T.ROOT, "agents", "analysis", "closure_a31_report.json"), {})
    pts = {p.get("point"): p for p in rep.get("points") or [] if p.get("design") == d}
    # Amendment 31.2 lists a separate "borrowed" point only when the best borrowed setting differs from MD5's; when it is
    # MD5's setting (same overrides), the "md5" point is that setting's closure
    p = pts.get("borrowed") or pts.get("md5")
    if p:
        k = p.get("kind")
        return (k, p.get("hi") if k == "checked" else p.get("lo") if k == "lower bound" else p.get("teff"))
    return ("open", None)


def wins(x, y, margin=0.02):
    """x beats y by more than margin (lower clock is better); bounds handled as in the registered text."""
    kx, vx = x[0], x[1]
    ky, vy = y[0], y[1]
    if kx != "checked":
        return False
    if ky in ("none",):
        return True
    if ky == "checked":
        return vx <= (1 - margin) * vy
    if ky == "lower bound":
        return vx <= (1 - margin) * vy
    return False


def report(js):
    st = A.load(A.STATE, {"tags": {}})
    out, per = {}, {}
    for d in HELD:
        a, b, z = checked(st, d, "a"), checked(st, d, "b"), start_checked(d)
        a2, b2 = checked2(st, d, "a"), checked2(st, d, "b")
        a3, b3, f3, z3 = fixed_point(st, d, "a"), fixed_point(st, d, "b"), fixed_point(st, d, "f"), start_fixed(st, d)
        f1 = checked(st, d, "f")
        n = {arm: (sum(1 for v in st["tags"].values() if v["design"] == d and v["arm"] == arm and v["status"] not in ("dispatched", "pending")),
                   sum(1 for v in st["tags"].values() if v["design"] == d and v["arm"] == arm)) for arm in ("a", "b", "f", "k", "c", "s")}
        per[d] = {"A32a": wins(a, b), "A32b": wins(a, z), "A32c": wins(b, z),
                  "A32a2": wins(a2, b2), "A32b2": wins(a2, z), "A32c2": wins(b2, z),
                  "A32a3": wins(a3, b3), "A32b3": wins(a3, z3), "A32c3": wins(b3, z3),
                  "A33a": wins(f3, b3), "A33b": wins(a3, f3)}
        out[d] = {"agent": a, "tpe": b, "start": z, "agent2": a2, "tpe2": b2, "agent3": a3, "tpe3": b3, "floor3": f3,
                  "floor": f1, "start3": z3, "landed": n, **per[d]}
        f = lambda x: f"{x[0]} {x[1]:.2f}" if x[1] is not None else x[0]
        print(f"== {d}: agent {f(a)} | TPE {f(b)} | TPE@floor {f(f1)} | start {f(z)} || fixed point: agent {f(a3)} TPE {f(b3)} "
              f"floor {f(f3)} start {f(z3)} | runs " + " ".join(f"{k} {n[k][0]}/{n[k][1]}" for k in n))
    import datetime as _dt
    decided = _dt.datetime.now(_dt.timezone.utc) >= _dt.datetime(2026, 10, 29, 15, 30, tzinfo=_dt.timezone.utc)
    overall = {}
    for k in ("A32a", "A32b", "A32c"):
        w = sum(1 for d in HELD if per[d][k])
        overall[k] = ((("PASS" if w >= 4 else "FAIL") + f" ({w} of {len(HELD)}; 4 needed; decided at 15:30Z Oct 29)") if decided
                      else f"pending ({w} of {len(HELD)} so far; 4 needed; decided at 15:30Z Oct 29)")
    overall.update({k: f"{sum(1 for d in HELD if per[d][k])} of {len(HELD)} (Amendment 32.1, reported beside, no criterion)"
                    for k in ("A32a2", "A32b2", "A32c2")})
    overall.update({k: f"{sum(1 for d in HELD if per[d][k])} of {len(HELD)} (Amendment 32.2, fixed point, reported beside, no criterion)"
                    for k in ("A32a3", "A32b3", "A32c3")})
    d33 = _dt.datetime.now(_dt.timezone.utc) >= _dt.datetime(2026, 10, 29, 20, 30, tzinfo=_dt.timezone.utc)
    for k in ("A33a", "A33b"):
        w = sum(1 for d in HELD if per[d][k])
        overall[k] = ((("PASS" if w >= 4 else "FAIL") + f" ({w} of {len(HELD)}; 4 needed; decided at 20:30Z Oct 29)") if d33
                      else f"pending ({w} of {len(HELD)} so far; 4 needed; decided at 20:30Z Oct 29)")
    for k, v in overall.items():
        print(f"  {k}: {v}")
    if js:
        json.dump({"designs": out, "per_design": per, "overall": overall}, open(js, "w"), indent=1, default=str)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--init-b", action="store_true")
    ap.add_argument("--init-f", action="store_true")
    ap.add_argument("--agent-prompt", action="store_true")
    ap.add_argument("--agent-ingest", default=None)
    ap.add_argument("--step", action="store_true")
    ap.add_argument("--closure", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    A.DRY["on"] = a.dry_run
    T.DRY["on"] = a.dry_run
    check_space()
    if a.init_b:
        init_b()
    if a.init_f:
        init_b("f")
    if a.step:
        step()
    if a.agent_prompt:
        agent_prompt()
    if a.agent_ingest:
        agent_ingest(a.agent_ingest)
    if a.closure:
        closure()
    if a.report:
        report(a.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
