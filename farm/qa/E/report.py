#!/usr/bin/env python3
"""Experiment E (Addendum 42): print the result tables (markdown) from the registered scorer's inputs. Presentation
only: every number is computed with score.py's own functions (load_pred, score_arm, verdict_pf, verdict_kept); nothing
here decides a registered test. Written and committed before any rebuild label existed.

  report.py --chains DIR --key packet_key.json --pred DIR --score score.json [--chains-index chains.json]
Sections: label states; per-arm scoreboard (35 sources; two-point line on its 19); registered tests R1-R3 part by part;
descriptive pairwise pass/fail comparisons (incl. Codex's comparator); slope error per family; the two-point subset;
renaming / shuffled-view controls; the per-source label table.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import score as S  # noqa: E402

ORDER = ["raw_claim", "law", "io_rule", "two_point", "handpicked", "rung1", "rung2", "rung3", "codex_det"]


def f3(x):
    return "–" if x is None else f"{x:.3f}"


def pct(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chains", required=True)
    ap.add_argument("--key", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--score", required=True)
    ap.add_argument("--chains-index", default=os.path.join(HERE, "chains.json"))
    a = ap.parse_args()
    res = json.load(open(a.score))
    key = json.load(open(a.key))
    tag_of = {c["source"]: c["tag"] for c in json.load(open(a.chains_index))["chains"]}
    rows = []
    for pid, v in sorted(key["packets"].items()):
        if v["kind"] != "main":
            continue
        cp = os.path.join(a.chains, tag_of[v["source"]], "chain.json")
        if not os.path.exists(cp):
            continue
        c = json.load(open(cp))
        rows.append({"pid": pid, "source": v["source"], "family": v["design"], "T0": c["T0_ns"], "C0": c["C0_ns"],
                     "R1": c.get("R1_ns"), "pass1": bool(c["first_pass"]), "slope": c["slope"], "C1": c.get("C1_ns"),
                     "kept": c["kept_clock_ns"], "source_pass": c.get("source_pass"),
                     "first_outcome": c.get("first_outcome"), "two_point": bool(v.get("has_second_point")),
                     "n_rebuilds": c.get("n_rebuilds"),
                     "missing": sorted({m for r in c.get("rebuilds", []) for m in (r.get("judge_missing") or [])})})
    preds, oks = {}, {}
    for arm in ORDER:
        d = os.path.join(a.pred, arm)
        if not os.path.isdir(d):
            continue
        sub = [r for r in rows if arm != "two_point" or r["two_point"]]
        preds[arm] = {r["pid"]: S.load_pred(os.path.join(d, r["pid"] + ".json"), r["C0"], r["T0"]) for r in sub}
        _, ok = S.score_arm(sub, preds[arm])
        oks[arm] = dict(zip([r["pid"] for r in sub], ok))
    A = res["arms"]

    print("## Label states")
    print(f"- checked: {res['n_checked']} of 35; not checked (no chain record after the registered re-dispatch): "
          f"{len(res['not_checked'])} {res['not_checked'] or ''}")
    print(f"- first rebuild passed: {sum(r['pass1'] for r in rows)} of {len(rows)}; first rebuild without final "
          f"metrics (fail, slope undefined): {len(res['first_rebuild_no_metrics'])}; slope undefined: "
          f"{len(res['slope_undefined'])}")
    print(f"- kept clock: {sum(r['kept'] is not None for r in rows)} chains kept a clock ({len(res['kept_source_only'])} "
          f"only the source's own target); {len(res['kept_null'])} kept none")
    miss = [r for r in rows if r["missing"]]
    print(f"- rebuilds with a missing judge field (failed by the fail-closed judge): {len(miss)}"
          + (f" {[(r['source'], r['missing']) for r in miss]}" if miss else ""))

    print("\n## Scoreboard (35 sources; two-point line on its 19)")
    print("| arm | n | valid | false pass / called pass | missed / actual pass | abstain | correct | Brier | slope err median "
          "(mean) | kept err median (p90) | kept n | kept-vs-none agree |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for arm in ORDER:
        if arm not in A:
            continue
        r = A[arm]
        print(f"| {arm} | {r['n']} | {r.get('valid', '–')} | {r['false_passes']}/{r['predicted_passes']} | "
              f"{r['missed_passes']}/{r['actual_passes']} | {r['abstentions']} | {r['correct']} | {r['brier']:.3f} | "
              f"{f3(r['slope_err_median'])} ({f3(r['slope_err_mean'])}) | {pct(r['kept_err_median'])} "
              f"({pct(r['kept_err_p90'])}) | {r['kept_n']} | {r['kept_vs_none_agree']} |")
    print("Slope missing (abstention without a slope, or invalid file): "
          + ", ".join(f"{arm} {A[arm]['slope_missing']}" for arm in ORDER if arm in A and A[arm]["slope_missing"]))

    print("\n## Registered tests")
    T = res["tests"]
    if "R1" in T:
        t = T["R1"]
        print(f"- **R1** holds: **{t['holds']}**. (a) rung 1 vs the law, pass/fail: {t['pass_fail_vs_law'][0]} "
              f"(rung 1 right & law wrong {t['pass_fail_vs_law'][1]}, reverse {t['pass_fail_vs_law'][2]}, exact McNemar "
              f"p = {t['pass_fail_vs_law'][3]:.3g}); (b) kept clock vs the law: {t['kept_vs_law']} (medians "
              f"{pct(A['rung1']['kept_err_median'])} vs {pct(A['law']['kept_err_median'])}); (c) false passes on the 19 "
              f"two-point sources: rung 1 {t['false_passes_rung1_on_19']} vs two-point line {t['false_passes_two_point']}.")
    if "R2" in T:
        t = T["R2"]
        print(f"- **R2** holds: **{t['holds']}**. (i) rung 2 beats rung 1: {t['i_beats_rung1']} (slope err medians "
              f"{f3(A['rung2']['slope_err_median'])} vs {f3(A['rung1']['slope_err_median'])}; pass/fail vs rung 1 "
              f"{t['pass_fail_vs_rung1'][0]}, p = {t['pass_fail_vs_rung1'][3]:.3g}); (ii) pass/fail vs the law: "
              f"{t['ii_pass_fail_vs_law'][0]} ({t['ii_pass_fail_vs_law'][1]}/{t['ii_pass_fail_vs_law'][2]}, p = "
              f"{t['ii_pass_fail_vs_law'][3]:.3g}); (iii) slope error ratio rung 2 / law = "
              f"{f3(t['iii_slope_ratio_vs_law'])} (needs ≤ 0.80).")
    if "R3" in T:
        t = T["R3"]
        print(f"- **R3** holds: **{t['holds']}**. slope error ratio rung 3 / law = {f3(t['slope_ratio_vs_law'])} "
              f"(needs ≤ 0.75); rung 3 {f3(A['rung3']['slope_err_median'])} vs hand-picked "
              f"{f3(A['handpicked']['slope_err_median'])}: beats the hand-picked feature {t['beats_handpicked']}.")

    print("\n## Pass/fail comparisons (exact McNemar on per-source correctness; descriptive except R1/R2 above)")
    print("| A vs B | A right, B wrong | B right, A wrong | p | verdict for A |")
    print("|---|---|---|---|---|")
    pairs = [("rung1", "law"), ("rung2", "law"), ("rung2", "rung1"), ("rung3", "law"), ("codex_det", "law"),
             ("codex_det", "rung2"), ("codex_det", "rung3"), ("rung2", "raw_claim"), ("law", "raw_claim"),
             ("io_rule", "law"), ("handpicked", "law")]
    for x, y in pairs:
        if x in oks and y in oks:
            ids = [i for i in oks[x] if i in oks[y]]
            v = S.verdict_pf([oks[x][i] for i in ids], [oks[y][i] for i in ids])
            print(f"| {x} vs {y} | {v[1]} | {v[2]} | {v[3]:.3g} | {v[0]} |")

    print("\n## Slope error per family (median |ŝ − s|; equal-family median)")
    fams = sorted({r["family"] for r in rows})
    print("| arm | " + " | ".join(fams) + " | equal-family | pooled |")
    print("|---|" + "---|" * (len(fams) + 2))
    for arm in ORDER:
        if arm in A:
            bf = A[arm]["slope_err_median_by_family"]
            print(f"| {arm} | " + " | ".join(f3(bf.get(f)) for f in fams) +
                  f" | {f3(A[arm]['slope_err_equal_family'])} | {f3(A[arm]['slope_err_median'])} |")

    print("\n## The 19 two-point sources (every arm on the same subset)")
    print("| arm | false pass / called pass | correct | slope err median |")
    print("|---|---|---|---|")
    for arm in ORDER:
        if arm in A:
            r = A[arm] if arm == "two_point" else A[arm].get("on_two_point_subset")
            if r and r.get("n"):
                print(f"| {arm} | {r['false_passes']}/{r['predicted_passes']} | {r['correct']} | "
                      f"{f3(r['slope_err_median'])} |")

    for ctl, what in (("controls_rung2_rename", "Renaming control (same packet, different salt; fresh reader)"),
                      ("controls_rung2_shuffle", "Shuffled-view diagnostic (per-net fields permuted, layout withheld)")):
        if res.get(ctl):
            print(f"\n## {what}: control minus main rung-2 prediction")
            print("| main | control | Δp_pass | same call | Δslope | slope err main | slope err control |")
            print("|---|---|---|---|---|---|---|")
            for d in res[ctl]:
                print(f"| {d['main']} | {d['control']} | {d['d_p_pass']:+.2f} | {d['same_call']} | {f3(d['d_slope'])} | "
                      f"{f3(d['slope_err_main'])} | {f3(d['slope_err_control'])} |")

    print("\n## Per-source labels")
    print("| source | packet | stratum (T0/C0) | T0 | C0 | R1 | pass1 | C1 | slope | kept | rebuilds |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sorted(rows, key=lambda r: r["source"]):
        q = r["T0"] / r["C0"]
        stratum = "tight" if q < 1 else ("loose" if q < 1.3 else "very loose")
        p1 = "pass" if r["pass1"] else ("fail (no metrics)" if r["first_outcome"] != "landed" else "fail")
        c1 = "–" if r["C1"] is None else f"{r['C1']:.3f}"
        kept = "none" if r["kept"] is None else f"{r['kept']:.2f}"
        r1 = "–" if r["R1"] is None else f"{r['R1']:.2f}"
        print(f"| {r['source']} | {r['pid']} | {stratum} | {r['T0']:.2f} | {r['C0']:.3f} | {r1} | {p1} | {c1} | "
              f"{f3(r['slope'])} | {kept} | {r['n_rebuilds']} |")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
