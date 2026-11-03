#!/usr/bin/env python3
"""F: descriptive tables for F_RESULT.md from f_score.py's output and the landed run directories (no test here; the
registered test is f_score.py). Usage: f_report.py [--results DIR] [--score FILE]"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import flib  # noqa: E402

DEFAULT_RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results_F"))


def f(x, nd=1, pct=False):
    if x is None:
        return "–"
    if pct:
        return f"{x * 100:+.{nd}f}%"
    return f"{x:.{nd}f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=DEFAULT_RESULTS)
    ap.add_argument("--score", default=None)
    a = ap.parse_args()
    sc = json.load(open(a.score or os.path.join(a.results, "f_score.json")))
    cfgs = {c["id"]: c for c in json.load(open(os.path.join(HERE, "configs.json")))["configs"]}
    print("| config | design / platform | T0 | published claim | replay claim (gap) | first rebuild at | its slack | its claim | d1 | first rebuild judge | chain (clock: pass/fail) | kept |")
    print("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for r in sc["rows"]:
        c = cfgs[r["config"]]
        nd = 3 if c["platform"].startswith("sky130") else 1
        det = r.get("r1_detail") or {}
        judge = "–"
        if r.get("landed_r1"):
            if r.get("r1_pass"):
                judge = "pass"
            else:
                parts = [k for k, ok in (("setup", det.get("pass_setup")), ("hold", det.get("pass_hold")),
                                         ("DRC", det.get("pass_drc"))) if ok is False]
                judge = "FAIL (" + ", ".join(parts or ["no metrics"]) + ")"
        slack = det.get("ws")
        chain = "; ".join(f"{p:g}: {'pass' if ok else ('fail' if ok is False else 'n/a')}"
                          for p, _, ok in (r.get("chain") or [])[1:])
        repro = (f"{f(r.get('C0'), nd)} ({f(r.get('gap'), 2, True)})" + ("" if r.get("reproduced") else " NOT reproduced")) \
            if r.get("landed_replay") else "not landed"
        print(f"| {r['config']} | {c['design']} / {c['platform']} | {r['T0']:g} | {f(r['C0_pub'], nd)} | {repro} | "
              f"{f(r.get('R1'), 2 if nd == 3 else 0)} | {f(slack, nd)} | {f(r.get('C1'), nd)} | {f(r.get('d1'), 1, True)} | "
              f"{judge} | {chain or '–'} | {('–' if r.get('kept_clock') is None else format(r['kept_clock'], 'g'))} |")
    print()
    print("verdict:", sc["verdict"])
    for k in ("n_registered", "n_replay_landed", "n_reproduced", "n_first_rebuild_landed", "median_d1",
              "first_rebuild_fails", "first_rebuild_failures_by_part", "P2_setup_only", "by_source",
              "by_replay_slack_sign", "d1_vs_published_median", "kept_over_C0_median", "not_reproduced"):
        print(f"{k}: {sc.get(k)}")


if __name__ == "__main__":
    main()
