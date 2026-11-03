#!/usr/bin/env python3
"""F: the registered test (docs/qa_week/F_PREREG.md), computed from landed results.

  f_score.py collect --run-id N [--results DIR]   download this workflow run's f-* artifacts (primary, then -cont)
  f_score.py score [--results DIR] [--out FILE]   registered tests + descriptive tables -> JSON, verdict on stdout

Definitions (as registered):
  C0_pub  published claim (configs.json: EDA-env ECP = 1000/reported_reward ps; ORFS-agent ECP_final).
  C0      the replay's claim: the published configuration run as published at its published target T0
          (asked period - worst setup slack; EDA-env: eval clock - wns from its own measure.tcl).
  reproduced  replay completed and |C0/C0_pub - 1| <= 2 %.
  R1 = ceil_grid(C0) (5 ps ASAP7, 0.05 ns sky130hd); C1 = the first rebuild's claim; d1 = C1/C0 - 1
  (positive = the claim was optimistic). First-rebuild pass = setup >= 0, hold >= 0, DRC 0 at R1.
  Population P = reproduced configurations.
  P1: median d1 over P (first rebuilds with a claim) >= +3 %.   P2: at least one first rebuild in P fails.
  The plan's prediction HOLDS iff P1 and P2. |P| < 3 -> underpowered (reported, still computed).
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics as st
import subprocess
import sys
import tempfile
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import flib  # noqa: E402

REPO = "Avi-Patel-1/beforeroute-farm"
DEFAULT_RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results_F"))
REPRO_TOL = 0.02
P1_THRESHOLD = 0.03


def gh_json(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)


def cmd_collect(a):
    os.makedirs(a.results, exist_ok=True)
    arts = gh_json(f"repos/{REPO}/actions/runs/{a.run_id}/artifacts?per_page=100").get("artifacts", [])
    arts = sorted(arts, key=lambda x: (x["name"].endswith("-cont"), x["name"]))   # primary first, then -cont
    for art in arts:
        if not art["name"].startswith("f-") or art.get("expired"):
            continue
        with tempfile.TemporaryDirectory(dir=a.results) as td:
            zp = os.path.join(td, "a.zip")
            with open(zp, "wb") as fo:
                r = subprocess.run(["gh", "api", f"repos/{REPO}/actions/artifacts/{art['id']}/zip"], stdout=fo)
            if r.returncode:
                print(f"[collect] {art['name']}: download failed")
                continue
            with zipfile.ZipFile(zp) as z:
                for nm in z.namelist():
                    if nm.startswith("/") or ".." in nm.split("/"):
                        raise RuntimeError(f"unsafe path in artifact: {nm}")
                z.extractall(os.path.join(td, "x"))
            src = os.path.join(td, "x")
            for name in sorted(os.listdir(src)):
                s = os.path.join(src, name)
                if name == "chains":
                    os.makedirs(os.path.join(a.results, "chains"), exist_ok=True)
                    for f in os.listdir(s):
                        shutil.copy2(os.path.join(s, f), os.path.join(a.results, "chains", f))
                elif os.path.isdir(s):
                    d = os.path.join(a.results, name)
                    if os.path.exists(d):
                        shutil.rmtree(d)
                    shutil.copytree(s, d)
            print(f"[collect] {art['name']}")


def med(xs):
    xs = [x for x in xs if x is not None]
    return st.median(xs) if xs else None


def cmd_score(a):
    cfgs = json.load(open(os.path.join(HERE, "configs.json")))["configs"]
    rows = []
    for c in cfgs:
        cp = os.path.join(a.results, "chains", f"f-{c['id']}.json")
        ch = json.load(open(cp)) if os.path.exists(cp) else None
        pub = c["published"]
        row = {"config": c["id"], "source": c["source"], "design": c["design"], "platform": c["platform"],
               "T0": pub["T0"], "C0_pub": pub["claim"], "landed_replay": False, "landed_r1": False}
        if ch:
            st0 = ch["chain"]
            w = st0[0]
            row["landed_replay"] = True
            row["C0"] = w.get("claim")
            row["replay_pass"] = w.get("pass")
            row["replay_slack"] = (pub["T0"] - w["claim"]) if w.get("claim") is not None else None
            row["gap"] = (w["claim"] / pub["claim"] - 1) if w.get("claim") is not None else None
            row["reproduced"] = row["gap"] is not None and abs(row["gap"]) <= REPRO_TOL
            if len(st0) > 1:
                f1 = st0[1]
                row["landed_r1"] = True
                row["R1"] = f1["period"]
                row["C1"] = f1.get("claim")
                row["r1_pass"] = bool(f1.get("pass"))
                row["d1"] = (f1["claim"] / w["claim"] - 1) if (f1.get("claim") is not None and w.get("claim")) else None
                row["d1_vs_published"] = (f1["claim"] / pub["claim"] - 1) if f1.get("claim") is not None else None
            elif w.get("claim") is not None:
                nxt, why = flib.chain_next(st0, c["grid"])
                row["r1_note"] = why
            row["chain"] = [(s["period"], s.get("claim"), s.get("pass")) for s in st0]
            row["kept_clock"] = ch.get("kept_clock")
            row["kept_over_C0"] = (ch["kept_clock"] / w["claim"]) if (ch.get("kept_clock") and w.get("claim")) else None
            row["chain_complete"] = ch.get("complete")
        tag_dir = os.path.join(a.results, f"f-{c['id']}-1")
        if os.path.isdir(tag_dir):
            r1 = flib.load_run(tag_dir)
            row["r1_detail"] = {k: r1.get(k) for k in ("status", "ws", "hold_ws", "drc", "pass_setup", "pass_hold",
                                                        "pass_drc", "area_um2", "power_w", "ws_r2r")}
        rows.append(row)
    P = [r for r in rows if r.get("reproduced")]
    landed = [r for r in P if r["landed_r1"]]
    complete = all(r["landed_replay"] for r in rows) and all(r["landed_r1"] for r in P)
    d1s = [r["d1"] for r in landed if r.get("d1") is not None]
    fails = [r["config"] for r in landed if not r["r1_pass"]]
    p1 = (med(d1s) is not None and med(d1s) >= P1_THRESHOLD)
    p2 = len(fails) >= 1
    out = {
        "n_registered": len(rows), "n_replay_landed": sum(r["landed_replay"] for r in rows),
        "n_reproduced": len(P), "n_first_rebuild_landed": len(landed),
        "not_reproduced": [(r["config"], r.get("gap")) for r in rows if r["landed_replay"] and not r.get("reproduced")],
        "median_d1": med(d1s), "first_rebuild_fails": fails,
        "P1_median_optimistic_ge_3pct": p1, "P2_at_least_one_fails": p2,
        "underpowered": len(P) < 3, "complete": complete,
        "verdict": ("PREDICTION HOLDS" if (p1 and p2) else "PREDICTION FAILS (" + ", ".join(
            x for x, ok in (("P1 median optimism < 3%", p1), ("P2 no first rebuild failed", p2)) if not ok) + ")")
        + ("" if complete else " [INTERIM: not every registered replay / first rebuild has landed]")
        + (" [UNDERPOWERED: fewer than 3 reproduced configurations]" if len(P) < 3 else ""),
        "rows": rows,
    }
    # descriptive splits (no criterion)
    def split(rs):
        ds = [r["d1"] for r in rs if r.get("d1") is not None]
        return {"n": len(rs), "n_with_d1": len(ds), "median_d1": med(ds),
                "fails": sum(1 for r in rs if r.get("landed_r1") and not r.get("r1_pass"))}
    out["by_source"] = {s: split([r for r in landed if r["source"] == s]) for s in ("EDA-env", "ORFS-agent")}
    out["by_replay_slack_sign"] = {
        "negative (claim from a failing run)": split([r for r in landed if (r.get("replay_slack") or 0) < 0]),
        "non-negative (claim from a passing run)": split([r for r in landed if (r.get("replay_slack") or 0) >= 0])}
    # beside: P2 judged on setup only (which part of the judge each first-rebuild failure breaks)
    def broke(r):
        d = r.get("r1_detail") or {}
        if d.get("status") != "completed":
            return ["no metrics"]
        return [k for k, ok in (("setup", d.get("pass_setup")), ("hold", d.get("pass_hold")),
                                ("drc", d.get("pass_drc"))) if not ok]
    out["first_rebuild_failures_by_part"] = {r["config"]: broke(r) for r in landed if not r["r1_pass"]}
    out["P2_setup_only"] = any(("setup" in v or "no metrics" in v) for v in out["first_rebuild_failures_by_part"].values())
    out["d1_vs_published_median"] = med([r.get("d1_vs_published") for r in landed])
    out["kept_over_C0_median"] = med([r.get("kept_over_C0") for r in landed])
    json.dump(out, open(a.out, "w"), indent=1, default=float)
    print(out["verdict"])
    print(f"registered {out['n_registered']}, replays landed {out['n_replay_landed']}, reproduced {out['n_reproduced']},"
          f" first rebuilds landed {out['n_first_rebuild_landed']}; median d1 {out['median_d1']}; fails {fails}")
    for r in rows:
        print(f"  {r['config']:13s} T0={r['T0']} C0_pub={r['C0_pub']:.3f} C0={r.get('C0')} gap={r.get('gap')} "
              f"repro={r.get('reproduced')} R1={r.get('R1')} C1={r.get('C1')} pass1={r.get('r1_pass')} d1={r.get('d1')} "
              f"kept={r.get('kept_clock')} chain={r.get('chain')}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("collect")
    p.add_argument("--run-id", required=True)
    p.add_argument("--results", default=DEFAULT_RESULTS)
    p = sub.add_parser("score")
    p.add_argument("--results", default=DEFAULT_RESULTS)
    p.add_argument("--out", default=os.path.join(DEFAULT_RESULTS, "f_score.json"))
    a = ap.parse_args()
    {"collect": cmd_collect, "score": cmd_score}[a.cmd](a)


if __name__ == "__main__":
    main()
