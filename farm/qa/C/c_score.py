#!/usr/bin/env python3
"""Experiment C: the registered pass/fail computation (docs/qa_week/C_PREREG.md, "Registered tests").

Fixed-point clocks come from the A35/A32 code unchanged: tune_a35.fixed_point (rule races; A35's arms b, f, g read from
results/tune_xa/state.json, the new arms s, m, d from results/tune_xm/state.json) and tune_a32.fixed_point (proposer
races; A32's arms a, b, f from results/tune_x8/state.json, the new arm p from results/tune_xn/state.json). A race is won by
the 2% rule of Addenda 33/35 (tune_a32.wins): x beats y if x's fixed point is checked and <= 0.98 x y's (y checked or a
lower bound), or y has no feasible run; anything not checked is no win.
Arm names in the write-up (lens): s = scores-only Opus, m9 = the open 9B model (tag letter m), c = the four-line script
(tag letter d), S = scores-only Opus proposer (tag letter p).
Usage: c_score.py [--json out.json] [--md out.md] [--selftest]
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import clib as C  # noqa: E402

R, B, A = C.R, C.B, C.A
XM_STATE = os.path.join(C.ROOT, "results", "tune_xm", "state.json")
XN_STATE = os.path.join(C.ROOT, "results", "tune_xn", "state.json")
DEADLINE = datetime.datetime(2026, 11, 7, 12, 0, tzinfo=datetime.timezone.utc)   # registered decision deadline
FINAL = ("checked", "lower bound", "none")
NAMES = {"b": "b (plain TPE)", "f": "f (hand pin 0.45)", "g": "g (Opus, reports)", "s": "s (Opus, scores only)",
         "m": "m9 (open 9B model, reports)", "d": "c (four-line script)", "a": "a (Opus proposer, reports)",
         "p": "S (Opus proposer, scores only)"}


def load(path):
    return A.load(path, {"tags": {}, "policies": {}})


def rule_fp(states):
    """{race: {arm: (kind, value, best_tag)}} for the 10 rule races."""
    out = {}
    for d, s in R.races():
        r = f"{d}|s{s}"
        out[r] = {}
        for x in ("b", "f", "g"):
            out[r][x] = R.fixed_point(states["xa"], d, s, x)
        for x in ("s", "m", "d"):
            out[r][x] = R.fixed_point(states["xm"], d, s, x)
    return out


def prop_fp(states):
    out = {}
    for d in C.PROP_DESIGNS:
        out[d] = {x: B.fixed_point(states["x8"], d, x) for x in ("a", "b", "f")}
        out[d]["p"] = B.fixed_point(states["xn"], d, "p")
        out[d]["start"] = B.start_fixed(states["x8"], d)
    return out


def tally(fp, x, y):
    w = [r for r in fp if B.wins(fp[r][x], fp[r][y])]
    l = [r for r in fp if B.wins(fp[r][y], fp[r][x])]
    return {"wins": len(w), "losses": len(l), "ties_or_unresolved": len(fp) - len(w) - len(l), "won": w, "lost": l}


def beats10(t):
    """A35's rule for 10 races: >= 5 wins and <= 2 losses."""
    return t["wins"] >= 5 and t["losses"] <= 2


def tie2(t):
    """'tie within +-2 races': |wins - losses| <= 2."""
    return abs(t["wins"] - t["losses"]) <= 2


def pins(st_xa, st_xm):
    """Initial policies per arm and race (g from A35; s, m, d from this experiment)."""
    out = {}
    for d, s in R.races():
        r = f"{d}|s{s}"
        out[r] = {"g": (st_xa["policies"].get(R.pkey(d, s, "init")) or {}).get("pins")}
        for x in ("s", "m", "d"):
            p = st_xm.get("policies", {}).get(R.pkey(d, s, x))
            out[r][x] = None if p is None else p.get("pins")
    return out


def count_pf(pp, x):
    got = [pp[r][x] for r in pp if pp[r][x] is not None]
    return sum(1 for p in got if p.get("period_frac") is not None and p["period_frac"] <= 0.5), len(got)


def first_rebuild_fail(states, kind):
    """Per arm: races where the first closure run of the arm's best failed (lens: 'first-rebuild failures per reader')."""
    out = {}
    if kind == "rule":
        for x, key in (("b", "xa"), ("f", "xa"), ("g", "xa"), ("s", "xm"), ("m", "xm"), ("d", "xm")):
            n = f = 0
            for d, s in R.races():
                b, _ = R.arm_best(states[key], d, s, x)
                if b is None:
                    continue
                ks, _ = R.chain_of(states[key], b["tag"])
                ks = sorted([v for v in ks if v["status"] not in ("dispatched", "pending")], key=lambda v: v["tag"])
                if ks:
                    n += 1
                    f += not B.passed(ks[0])
            out[x] = {"first_rebuilds": n, "failed": f}
    else:
        for x, key in (("a", "x8"), ("b", "x8"), ("f", "x8"), ("p", "xn")):
            n = f = 0
            for d in C.PROP_DESIGNS:
                b, _ = B.arm_best(states[key], d, x)
                if b is None:
                    continue
                ks = sorted([dict(v, tag=t) for t, v in states[key]["tags"].items() if v["arm"] == "k"
                             and v.get("source") == b["tag"] and v["status"] not in ("dispatched", "pending")],
                            key=lambda v: v["tag"])
                if ks:
                    n += 1
                    f += not B.passed(ks[0])
            out[x] = {"first_rebuilds": n, "failed": f}
    return out


def malformed(st_xm, st_xn):
    out = {}
    for x in ("s", "m"):
        recs = [p for k, p in st_xm.get("policies", {}).items() if k.endswith(f"|{x}")]
        out[x] = {"replies": len(recs), "malformed_first": sum(1 for p in recs if p.get("malformed_first")),
                  "empty_policy_after_reask": sum(1 for p in recs if p.get("malformed_final"))}
    recs = st_xn.get("replies", {})
    out["p"] = {"replies": len(recs), "malformed_first": sum(1 for v in recs.values() if v.get("malformed_first")),
                "unanswered_rounds": sum(1 for v in recs.values() if v.get("malformed_final"))}
    return out


def score(states, now=None):
    now = now or datetime.datetime.now(datetime.timezone.utc)
    rf, pf = rule_fp(states), prop_fp(states)
    t = {f"{x}>{y}": tally(rf, x, y) for x in ("b", "f", "g", "s", "m", "d") for y in ("b", "f", "g", "s", "m", "d") if x < y or x > y}
    u = {f"{x}>{y}": tally(pf, x, y) for x in ("a", "b", "f", "p") for y in ("a", "b", "f", "p") if x != y}
    rule_done = all(rf[r][x][0] in FINAL for r in rf for x in ("s", "m", "d"))
    prop_done = all(pf[d]["p"][0] in FINAL for d in pf)
    decided_rule = rule_done or now >= DEADLINE
    decided_prop = prop_done or now >= DEADLINE
    pp = pins(states["xa"], states["xm"])
    v = lambda ok, decided: ("PASS" if ok else "FAIL") if decided else ("pending (so far " + ("PASS" if ok else "FAIL") + ")")
    tests = {
        "C-R1 (lens A37-1): g beats s (>= 5 wins, <= 2 losses of 10)": {
            "verdict": v(beats10(t["g>s"]), decided_rule), "wins": t["g>s"]["wins"], "losses": t["g>s"]["losses"],
            "prediction": "FAIL, within +-2", "prediction_held": (not beats10(t["g>s"])) and tie2(t["g>s"])},
        "C-R2 (lens A37-2): m9 beats b (>= 5 wins, <= 2 losses of 10)": {
            "verdict": v(beats10(t["m>b"]), decided_rule), "wins": t["m>b"]["wins"], "losses": t["m>b"]["losses"],
            "prediction": "PASS, 6-8 wins, 0-2 losses",
            "prediction_held": 6 <= t["m>b"]["wins"] <= 8 and t["m>b"]["losses"] <= 2},
        "C-R3 (lens A37-4): c (script) beats b (>= 5 wins, <= 2 losses of 10)": {
            "verdict": v(beats10(t["d>b"]), decided_rule), "wins": t["d>b"]["wins"], "losses": t["d>b"]["losses"],
            "prediction": "PASS, 7-9 wins", "prediction_held": beats10(t["d>b"]) and 7 <= t["d>b"]["wins"] <= 9},
        "C-P1 (lens A38-1): a beats S on >= 4 of 7": {
            "verdict": v(u["a>p"]["wins"] >= 4, decided_prop), "wins": u["a>p"]["wins"], "losses": u["a>p"]["losses"],
            "prediction": "FAIL, a ahead on 2-3", "prediction_held": 2 <= u["a>p"]["wins"] <= 3},
        "C-P2 (lens A38-2): S beats b on >= 4 of 7": {
            "verdict": v(u["p>b"]["wins"] >= 4, decided_prop), "wins": u["p>b"]["wins"], "losses": u["p>b"]["losses"],
            "prediction": "PASS narrowly", "prediction_held": u["p>b"]["wins"] >= 4},
    }
    for k, x in tests.items():          # a prediction is scored only once its test is decided
        if not (decided_prop if k.startswith("C-P") else decided_rule):
            x["prediction_held"] = "pending"
    headline = {
        "script ties Opus (|W(c>g) - W(g>c)| <= 2)": tie2(t["d>g"]),
        "small model ties Opus (|W(m9>g) - W(g>m9)| <= 2)": tie2(t["m>g"]),
        "reports buy the proposer 2-3 of 7 designs (W(a>S) in {2, 3})": 2 <= u["a>p"]["wins"] <= 3,
    }
    pins_le = {x: count_pf(pp, x) for x in ("g", "s", "m", "d")}
    sub = {
        "s pins period_frac <= 0.5 in >= 7 of 10 (lens A37-1)": pins_le["s"][0] >= 7,
        "m9 pins period_frac <= 0.5 in 6-9 of 10 (lens A37-2)": 6 <= pins_le["m"][0] <= 9,
        "m9 ties g (lens A37-2)": tie2(t["m>g"]),
        "c ties g (lens A37-4)": tie2(t["d>g"]),
    }
    return {"at": now.strftime("%Y-%m-%dT%H:%M:%SZ"), "rule_complete": rule_done, "prop_complete": prop_done,
            "decided": {"rule": decided_rule, "prop": decided_prop}, "tests": tests, "headline_predictions": headline,
            "sub_predictions": sub, "pins_period_frac_le_05": {x: f"{a} of {n}" for x, (a, n) in pins_le.items()},
            "pairwise_rule": {k: {kk: vv for kk, vv in x.items()} for k, x in t.items()},
            "pairwise_prop": u, "fixed_points_rule": rf, "fixed_points_prop": pf, "pins": pp,
            "first_rebuild_failures": {"rule": first_rebuild_fail(states, "rule"), "prop": first_rebuild_fail(states, "prop")},
            "malformed": malformed(states["xm"], states["xn"])}


def load_states():
    return {"xa": load(C.A35_STATE), "x8": load(C.A32_STATE), "xm": load(XM_STATE), "xn": load(XN_STATE)}


def selftest(states):
    """The same code must reproduce the registered A35/A32/A33 counts from the A35/A32 states."""
    rf = {f"{d}|s{s}": {x: R.fixed_point(states["xa"], d, s, x) for x in ("b", "f", "g", "h")} for d, s in R.races()}
    pf = {d: {x: B.fixed_point(states["x8"], d, x) for x in ("a", "b", "f")} for d in C.PROP_DESIGNS}
    want = [("g>b", rf, "g", "b", 9), ("b>g", rf, "b", "g", 1), ("g>f", rf, "g", "f", 4), ("f>g", rf, "f", "g", 4),
            ("h>g", rf, "h", "g", 4), ("g>h", rf, "g", "h", 2), ("h>f", rf, "h", "f", 5), ("f>h", rf, "f", "h", 3),
            ("f>b", rf, "f", "b", 7), ("A32a3 a>b", pf, "a", "b", 6), ("A33a f>b", pf, "f", "b", 5), ("A33b a>f", pf, "a", "f", 3)]
    ok = True
    for name, fp, x, y, n in want:
        got = sum(1 for r in fp if B.wins(fp[r][x], fp[r][y]))
        ok &= got == n
        print(f"  selftest {name}: {got} (record: {n}) {'ok' if got == n else 'MISMATCH'}")
    print(f"selftest: {'PASS' if ok else 'FAIL'}")
    return ok


def md(res):
    L = [f"# Experiment C — registered tests (computed {res['at']} by farm/qa/C/c_score.py)", ""]
    L += ["| test | verdict | wins | losses | prediction | prediction held |", "|---|---|---|---|---|---|"]
    for k, x in res["tests"].items():
        L.append(f"| {k} | {x['verdict']} | {x['wins']} | {x['losses']} | {x['prediction']} | {x['prediction_held']} |")
    L += ["", "| headline prediction (task) | held |", "|---|---|"] + [f"| {k} | {v} |" for k, v in res["headline_predictions"].items()]
    L += ["", "| sub-prediction (lens) | held |", "|---|---|"] + [f"| {k} | {v} |" for k, v in res["sub_predictions"].items()]
    f = lambda z: f"{z[0]} {z[1]:.2f}" if z[1] is not None else z[0]
    L += ["", "| race | b | f | g | s | m9 | c |", "|---|---|---|---|---|---|---|"]
    for r, x in res["fixed_points_rule"].items():
        L.append(f"| {r} | " + " | ".join(f(x[a]) for a in ("b", "f", "g", "s", "m", "d")) + " |")
    L += ["", "| design | a | b | f | S | start |", "|---|---|---|---|---|---|"]
    for d, x in res["fixed_points_prop"].items():
        L.append(f"| {d} | " + " | ".join(f(x[a]) for a in ("a", "b", "f", "p")) + f" | {f(x['start'])} |")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    ap.add_argument("--md", default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    states = load_states()
    if a.selftest and not selftest(states):
        return 1
    res = score(states)
    for k, x in res["tests"].items():
        print(f"{k}: {x['verdict']} (wins {x['wins']}, losses {x['losses']}); prediction {x['prediction']}: held={x['prediction_held']}")
    for k, x in {**res["headline_predictions"], **res["sub_predictions"]}.items():
        print(f"  {k}: {x}")
    if a.json:
        json.dump(res, open(a.json, "w"), indent=1, default=str)
    if a.md:
        open(a.md, "w").write(md(res))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
