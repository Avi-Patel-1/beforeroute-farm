#!/usr/bin/env python3
"""AD: print the tables of a result file from ad.py analyze's JSON (reporting only; the registered scoring is ad.py)."""
import json
import sys

d = json.load(open(sys.argv[1]))
f3 = (lambda x: "–" if x is None else f"{x:.3f}")
pct = (lambda x: "–" if x is None else f"{100 * x:+.1f}%")


def law_row(label, blk):
    L = blk["law"]
    return (f"| {label} | {blk['n_runs']} | {blk['interpolated_settings']} | {f3(L['s_minus'])} (n {L['n_minus']}) | "
            f"{f3(L['s_plus'])} (n {L['n_plus']}) |")


print("| population | runs | settings with interpolated F | s⁻ (runs) | s⁺ (runs) |")
print("|---|---|---|---|---|")
print(law_row("**T2a: ORFS sky130hd, grid**", d["T2a"]))
print(law_row("T2a with its rebuild chains (beside)", d["T2a"]["with_chains"]))
print(law_row("**T2b: ORFS ASAP7, ABC told the clock, grid**", d["T2b"]))
if "control" in d:
    print(law_row("control: ASAP7 Yosys/ABC without target (gcd, aes)", d["control"]))
print(law_row("E5 ASAP7 grid (beside)", d["E5_baseline"]["grid"]))
print(law_row("E5 ASAP7 grid + rebuilds (the plan's 0.20/0.65)", d["E5_baseline"]["grid_and_chains"]))
print()
print("Per design (s⁻ / s⁺):")
for k in ("T2a", "T2b"):
    for des, L in d[k]["per_design"].items():
        print(f"- {k} {des}: s⁻ {f3(L['s_minus'])} (n {L['n_minus']}), s⁺ {f3(L['s_plus'])} (n {L['n_plus']})")
print()
print("Settings and F:")
for k in ("T2a", "T2b"):
    for key, v in d[k]["settings"].items():
        kk = json.loads(key)
        print(f"- {k} {kk['design']} {kk['vars']}: F {'–' if v['F'] is None else round(v['F'], 1)} ({v['how']})")
print()
print("Bins (median claim error, n):")
for k in ("T2a", "T2b"):
    print(f"- {k}: " + "; ".join(f"{lab} {pct(b['median'])} (n {b['n']})" for lab, b in d[k]["bins"].items()))
print(f"- D sky130hd grid+chains: " + "; ".join(f"{lab} {pct(b['median'])} (n {b['n']})"
                                               for lab, b in d["D"]["sky130hd_bins"].items()))
print()
print("Verdicts:")
for k in ("T2a", "T2b"):
    print(f"- {k}: {d[k]['verdict']}")
print(f"- T2b netlist check: {d['T2b'].get('netlist_check')}")
print(f"- D1: {d['D']['first_rebuild_fails']}/{d['D']['n_winners']} first rebuilds failed -> {d['D']['first_rebuild_verdict']}")
print(f"- D2: tight bin {d['D']['sky130hd_tight_bin']} -> {d['D']['tight_verdict']}")
print(f"- T3: {d['T3']['pass']}/{d['T3']['n']} -> {d['T3']['verdict']}")
print()
print("| chain | winner | T0 | C0 | R1 | first rebuild | C1 | d1 | chain (clock, claim, pass) | kept |")
print("|---|---|---|---|---|---|---|---|---|---|")
for c in d["D"]["chains"]:
    print(f"| {c['chain_id']} | {c['winner']} | {c['T0']} | {c['C0']:.1f} | {c['R1']} | "
          f"{'pass' if c['first_pass'] else 'FAIL'} | {'–' if c['C1'] is None else round(c['C1'], 1)} | "
          f"{pct(c['d1'])} | {[(p, None if cl is None else round(cl, 1), ok) for p, cl, ok in c['chain'][1:]]} | "
          f"{c['kept']} |")
print()
print("| T3 replay | of | T0 | replay = E5 | re-time at T0 = flow | T* | WS at T* | hold at T* | pass |")
print("|---|---|---|---|---|---|---|---|---|")
for r in d["T3"]["rows"]:
    print(f"| {r['tag']} | {r.get('replay_of')} | {r['T0']} | {r.get('replay_identical')} | "
          f"{r.get('t0_reproduces_flow')} | {r.get('Tstar')} | {r.get('ws_at_Tstar')} | {r.get('hold_at_Tstar')} | "
          f"{r['pass_at_Tstar']} |")
