#!/usr/bin/env python3
"""Workstream B, arm C3 (docs/qa_week/B_PREREG.md, branch qa-b-frozen-io): E5's ASAP7 grid and chains with the I/O budget
frozen at 0.2*P0 (clk_io_pct = 0.2*P0/T; farm/qa/B3/orfs_run.sh).

  b3.py grid   --batch NAME [--max-parallel 2] [--smoke]   write farm/qa/B3/dispatch.json (+ batches/NAME.json)
  b3.py chains --results DIR --batch NAMEk --spec-out F --require-complete   (runner side: top 3 per design, chains)

Grid = E5's registered grid (farm/qa/E5/grid.json) unchanged; tags b3g-<design>-<nnn> numbered as E5's e5g-<design>-<nnn>.
Selection = E5's: lowest AutoTuner score (e5lib.tuner_score) among the design's 10 grid runs, ties by tag; chains by
e5lib.chain_next with every rebuild frozen the same way; tags b3k-<design>-<rank>-<k>.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "E5"))
import e5lib  # noqa: E402

GRID_PATH = os.path.join(HERE, "..", "E5", "grid.json")
DISPATCH_PATH = os.path.join(HERE, "dispatch.json")
# grid jobs per design (2-slot share: longest first); chain jobs per design
GRID_JOBS = {"ibex": 3, "aes": 2, "gcd": 1}
CHAIN_JOBS = {"ibex": 3, "aes": 3, "gcd": 1}
ORDER = ["ibex", "aes", "gcd"]


def grid_runs(grid):
    out = []
    for d in grid["designs"]:
        k = 0
        for s in d["settings"]:
            for t in s["targets"]:
                k += 1
                out.append({"tag": f"b3g-{d['design']}-{k:03d}", "design": d["design"], "period": int(t),
                            "vars": s["vars"], "setting": s["setting"], "kind": "grid", "io_p0": int(d["P0"]),
                            "e5_twin": f"e5g-{d['design']}-{k:03d}"})
    return out


def write(batch, groups, about, max_parallel, extra=None):
    d = {"batch": batch, "about": about, "max_parallel": max_parallel, "groups": groups}
    if extra:
        d.update(extra)
    os.makedirs(os.path.join(HERE, "batches"), exist_ok=True)
    for p in (DISPATCH_PATH, os.path.join(HERE, "batches", batch + ".json")):
        json.dump(d, open(p, "w"), indent=1)
    print(f"wrote {DISPATCH_PATH}: {len(groups)} groups, "
          f"{sum(len(g.get('runs', [])) + len(g.get('chains', [])) for g in groups)} runs/chains, max_parallel "
          f"{max_parallel}")


def cmd_grid(a):
    grid = json.load(open(GRID_PATH))
    runs = grid_runs(grid)
    byd = {d["design"]: d for d in grid["designs"]}
    if a.smoke:
        # plumbing only (tags smoke-*): gcd frozen at 215 ps, and gcd at P0 (must equal E5's e5g-gcd-003)
        g = byd["gcd"]
        rs = [dict(r, tag="smoke-" + r["tag"]) for r in runs if r["tag"] in ("b3g-gcd-001", "b3g-gcd-003")]
        groups = [{"name": "smoke-gcd", "num_cores": g["num_cores"], "timeout_s": g["timeout_s"], "runs": rs}]
        write(a.batch, groups, "workstream B C3 smoke (not part of any analysis)", a.max_parallel)
        return
    groups = []
    for name in ORDER:
        d = byd[name]
        rs = [r for r in runs if r["design"] == name]
        n = GRID_JOBS[name]
        for j in range(n):
            part = rs[j::n]
            if part:
                groups.append({"name": f"{name}{j + 1}", "num_cores": d["num_cores"], "timeout_s": d["timeout_s"],
                               "runs": part})
    write(a.batch, groups, "workstream B arm C3 (registered, docs/qa_week/B_PREREG.md): E5 grid with frozen I/O",
          a.max_parallel, {"auto_chains": ",".join(ORDER)})


def all_runs(results, prefix):
    out = {}
    for name in sorted(os.listdir(results)):
        d = os.path.join(results, name)
        if not os.path.isdir(d) or name == "chains" or not name.startswith(prefix):
            continue
        out[name] = e5lib.load_run(d)
    return out


def top3(R, design, k=3):
    rs = [r for r in R.values() if r["design"] == design]
    rs = [r for r in rs if e5lib.tuner_score(r) < 9e99]
    rs.sort(key=lambda r: (e5lib.tuner_score(r), r["tag"]))
    return rs[:k]


def cmd_chains(a):
    grid = json.load(open(GRID_PATH))
    R = all_runs(a.results, "b3g-")
    want = {r["tag"]: r for r in grid_runs(grid)}
    byd = {d["design"]: d for d in grid["designs"]}
    groups = []
    for name in ORDER:
        if a.designs and name not in a.designs.split(","):
            continue
        d = byd[name]
        tags = [t for t, r in want.items() if r["design"] == name]
        missing = [t for t in tags if t not in R or R[t]["status"] in ("missing", "no_run_json")]
        if missing and a.require_complete:
            print(f"{name}: grid incomplete ({len(missing)} of {len(tags)} missing: {missing}); no chains")
            continue
        chs = []
        for i, w in enumerate(top3(R, name), 1):
            job = json.load(open(os.path.join(a.results, w["tag"], "job.json")))
            ch = {"chain_id": f"b3k-{name}-{i}", "design": name, "setting": w["setting"], "vars": job.get("vars") or {},
                  "tag_prefix": f"b3k-{name}-{i}-", "io_p0": int(d["P0"]),
                  "winner": {"tag": w["tag"], "period": w["period"], "claim": w["claim"], "pass": w["pass"]}}
            chs.append(ch)
            print(f"{ch['chain_id']}: winner {w['tag']} {w['setting']} T0={w['period']} claim={w['claim']:.2f} "
                  f"pass={w['pass']} -> first rebuild at {e5lib.ceil_grid(w['claim'])} ps")
        n = CHAIN_JOBS[name]
        for j in range(n):
            part = chs[j::n]
            if part:
                groups.append({"name": f"k{name}{j + 1}", "num_cores": d["num_cores"], "timeout_s": d["timeout_s"],
                               "chains": part})
    json.dump({"batch": a.batch, "about": "workstream B C3 rebuild chains (top 3 per design, frozen I/O)",
               "groups": groups}, open(a.spec_out, "w"), indent=1)
    print(f"wrote {a.spec_out} ({len(groups)} groups)")


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    g = sp.add_parser("grid")
    g.add_argument("--batch", required=True)
    g.add_argument("--max-parallel", type=int, default=2)
    g.add_argument("--smoke", action="store_true")
    c = sp.add_parser("chains")
    c.add_argument("--results", required=True)
    c.add_argument("--batch", required=True)
    c.add_argument("--spec-out", required=True)
    c.add_argument("--designs", default="")
    c.add_argument("--require-complete", action="store_true")
    a = ap.parse_args()
    {"grid": cmd_grid, "chains": cmd_chains}[a.cmd](a)


if __name__ == "__main__":
    main()
