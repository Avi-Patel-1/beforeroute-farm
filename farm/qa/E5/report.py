#!/usr/bin/env python3
"""E5 (Addendum 41): markdown tables for docs/qa_week/E5_RESULT.md from results/ and e5.py analyze's JSON.
Local only (the runner never imports this file).

  report.py [--results DIR] [--analysis FILE]
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import e5lib  # noqa: E402

DEFAULT_RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))


def f(x, nd=1, pct=False):
    if x is None:
        return "–"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if pct:
        return f"{100 * x:+.{nd}f}%"
    return f"{x:.{nd}f}"


IO_FRAC = 0.2   # clk_io_pct in the gcd, aes and ibex SDCs: input and output delays are 20% of the clock


def port_claim(r):
    """Claim of the worst port path: target - min(worst slack from inputs, worst slack to outputs)."""
    v = [x for x in (r.get("ws_in"), r.get("ws_out")) if x is not None]
    return (float(r["period"]) - min(v)) if v else None


def winner_split(A, results):
    """Added after registration at the coordinator's request (descriptive, no criterion). For each winner W (target T0)
    and its first rebuild (target R1): the claim of the worst register-to-register path and of the worst port path at
    both, and how much of the claim's move C1 - C0 the I/O arithmetic alone predicts: with every path's own delay held
    at W's values, a port path's claim moves by 0.2 x (R1 - T0) (its I/O delays are 20% of the clock) and a
    register-to-register claim does not move, so the I/O-only forecast is max(r2r claim at W, port claim at W + 0.2 x
    (R1 - T0))."""
    rows = []
    for c in A["primary"]["chains"]:
        ch = e5lib._load(os.path.join(results, "chains", c["chain_id"] + ".json"), {}) or {}
        st0 = ch.get("chain") or []
        if len(st0) < 2:
            continue
        w = e5lib.load_run(os.path.join(results, c["winner"]))
        r1 = e5lib.load_run(os.path.join(results, st0[1]["tag"])) if not st0[1].get("reused") else w
        if w.get("period") is None or r1.get("period") is None:
            continue
        T0, R1 = float(w["period"]), float(r1["period"])
        p0, p1 = port_claim(w), port_claim(r1)
        q0, q1 = w.get("t_r2r"), r1.get("t_r2r")
        C0, C1 = w["claim"], r1["claim"]
        fc = None
        if p0 is not None and q0 is not None:
            fc = max(q0, p0 + IO_FRAC * (R1 - T0))
        drift = (C1 - C0) if (C1 is not None and C0 is not None) else None
        rows.append({"chain_id": c["chain_id"], "design": c["design"], "winner": c["winner"], "T0": T0, "R1": R1,
                     "C0": C0, "C1": C1, "lim0": "port" if w.get("port") else "r2r",
                     "lim1": "port" if r1.get("port") else "r2r", "port0": p0, "port1": p1, "r2r0": q0, "r2r1": q1,
                     "port_move": (p1 - p0) if (p0 is not None and p1 is not None) else None,
                     "port_io": IO_FRAC * (R1 - T0), "r2r_move": (q1 - q0) if (q0 is not None and q1 is not None) else None,
                     "io_forecast": fc, "drift": drift,
                     "io_share": ((fc - C0) / drift) if (fc is not None and drift) else None})
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=DEFAULT_RESULTS)
    ap.add_argument("--analysis", default=os.path.join(DEFAULT_RESULTS, "e5_analysis.json"))
    a = ap.parse_args()
    A = json.load(open(a.analysis))
    R = A["runs"]
    print("## Grid runs\n")
    print("| tag | design | setting | target (ps) | WS (ps) | claim (ps) | hold WS | DRC | judge | limiting path | flow min |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for t in sorted(R):
        r = R[t]
        if not t.startswith("e5g-"):
            continue
        lim = "–" if r["port"] is None else ("port" if r["port"] else "reg-to-reg")
        print(f"| {t} | {r['design']} | {r['setting']} | {r['period']} | {f(r['ws'], 2)} | {f(r['claim'], 1)} | "
              f"{f(r['hold_ws'], 1)} | {r['drc']} | {'pass' if r['pass'] else ('fail' if r['pass'] is False else r['status'])} | "
              f"{lim} | {f((r['elapsed_s'] or 0) / 60, 1)} |")
    P = A["primary"]
    print("\n## Winners and their rebuild chains\n")
    print("| chain | winner | setting | asked (ps) | claim C0 | 1st rebuild at | judge | its claim C1 | d1 | chain (target → claim, judge) | kept |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for c in P["chains"]:
        steps = "; ".join(f"{T} → {f(C, 1)} {'P' if p else 'F'}" for T, C, p in c["chain"][1:])
        w = R.get(c["winner"], {})
        print(f"| {c['chain_id']} | {c['winner']} | {w.get('setting', '?')} | {c['T0']} | {f(c['C0'], 1)} | {c['R1']} | "
              f"{'pass' if c['first_pass'] else 'fail'} | {f(c['C1'], 1)} | {f(c['d1'], 1, pct=True)} | {steps} | "
              f"{c['kept'] if c['kept'] else 'none'} |")
    print(f"\nPrimary: {P['first_rebuild_fails']} of {P['n_registered']} registered first rebuilds failed; "
          f"median |d1| {f(P['median_abs_d1'], 1, pct=True)}; verdict: {P['verdict']}")
    print("\n## Port-limited vs register-limited, per winner (descriptive, added after registration)\n")
    print("| chain | limiting path at W → at 1st rebuild | port claim W → R1 (ps) | of which I/O arithmetic 0.2·(R1−T0) | "
          "reg-to-reg claim W → R1 (ps) | claim move C1−C0 | I/O-only forecast of C1 | share of the move from I/O arithmetic |")
    print("|---|---|---|---|---|---|---|---|")
    for x in winner_split(A, a.results):
        print(f"| {x['chain_id']} | {x['lim0']} → {x['lim1']} | {f(x['port0'])} → {f(x['port1'])} "
              f"({'+' if (x['port_move'] or 0) >= 0 else ''}{f(x['port_move'])}) | +{f(x['port_io'])} | "
              f"{f(x['r2r0'])} → {f(x['r2r1'])} ({'+' if (x['r2r_move'] or 0) >= 0 else ''}{f(x['r2r_move'])}) | "
              f"{'+' if (x['drift'] or 0) >= 0 else ''}{f(x['drift'])} | {f(x['io_forecast'])} | "
              f"{f(x['io_share'] * 100 if x['io_share'] is not None else None, 0)}% |")
    S = A["secondary"]
    print("\n## Claim error vs the clock each setting can meet (bracketed settings only)\n")
    print("| bin (target / F) | 7 nm median (n) | port | reg-to-reg | sky130 median (n) |")
    print("|---|---|---|---|---|")
    for lab in ("tight (<0.9)", "near (0.9-1.1)", "loose (1.1-1.5)", "very loose (>1.5)"):
        b = {k: S["bins"].get(f"{lab}|{k}") for k in ("all", "port", "r2r")}
        sk = S["sky130_bins"][lab]
        cell = lambda x: "–" if not x else f"{f(x['median'], 1, pct=True)} ({x['n']})"
        print(f"| {lab} | {cell(b['all'])} | {cell(b['port'])} | {cell(b['r2r'])} | {f(sk['all'], 1, pct=True)} ({sk['n']}) |")
    print(f"\nS1 tight median: {f(S['S1_tight_overclaim_median'], 1, pct=True)}; S2: {S['S2_verdict']}")
    print(f"Bracketed settings: {S['interpolated_settings']} of {len(S['settings'])} with ≥ 2 targets")
    print("\n| setting | n | targets | F (interp.) | how | F (judge) | slope C vs target | port slope | r2r slope |")
    print("|---|---|---|---|---|---|---|---|---|")
    for g in S["settings"]:
        k = g["key"]
        print(f"| {k['design']} {json.dumps(k['vars'])} | {g['n']} | {', '.join(str(int(t)) for t in g['targets'])} | "
              f"{f(g['F_emp'], 1)} | {g['how']} | {g['F_obs'] or '–'} | {f(g['slope_teff'], 2)} | {f(g['slope_port'], 2)} | "
              f"{f(g['slope_r2r'], 2)} |")
    sl = S["slopes"]
    print(f"\nSlopes (median over settings): C vs target {sl['teff'] and f(sl['teff']['median'], 2)}; "
          f"port {sl['port'] and f(sl['port']['median'], 2)}; r2r {sl['r2r'] and f(sl['r2r']['median'], 2)}")
    # replay check: audit runs that repeat a pilot run's design, setting and clock
    print("\n## Replay check (audit run vs pilot run, same design, knobs and clock)\n")
    pil = {}
    for name in sorted(os.listdir(a.results)):
        if name.startswith("e5s-"):
            r = e5lib.load_run(os.path.join(a.results, name))
            job = e5lib._load(os.path.join(a.results, name, "job.json"), {}) or {}
            pil[(r["design"], json.dumps(job.get("vars") or {}, sort_keys=True), r["period"])] = r
    for t in sorted(R):
        r = R[t]
        job = e5lib._load(os.path.join(a.results, t, "job.json"), {}) or {}
        key = (r["design"], json.dumps(job.get("vars") or {}, sort_keys=True), r["period"])
        if key in pil:
            p = pil[key]
            same = (p["ws"] == r["ws"] and p["hold_ws"] == r["hold_ws"] and p["area_um2"] == r["area_um2"])
            print(f"- {t} vs {p['tag']}: WS {r['ws']} vs {p['ws']}, hold {r['hold_ws']} vs {p['hold_ws']}, "
                  f"area {r['area_um2']} vs {p['area_um2']} → {'identical' if same else 'DIFFERENT'}")


if __name__ == "__main__":
    main()
