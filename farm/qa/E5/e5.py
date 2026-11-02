#!/usr/bin/env python3
"""E5 (Addendum 41) local driver: collect artifacts, list runs, write dispatch batches, analyze.

  e5.py collect [--results DIR]          download new e5-* artifacts of this branch's E5 workflow runs (REST only)
  e5.py table   [--results DIR] [--prefix e5g]
  e5.py status                           jobs of this branch's E5 workflow runs that are queued or running
  e5.py chains  --batch NAME             write dispatch.json with the registered rebuild chains (top 3 per design)
  e5.py analyze [--out FILE]             registered tests and descriptive bins -> JSON

Artifacts hold metrics JSON, gzipped logs and reports only (no layouts).
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
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import e5lib  # noqa: E402

REPO = "Avi-Patel-1/beforeroute-farm"
BRANCH = "qa-e5-asap7"
WF_NAME = "E5 ASAP7 audit (ORFS)"
DEFAULT_RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results"))


def gh_json(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)


def wf_runs():
    out = []
    for page in range(1, 6):
        d = gh_json(f"repos/{REPO}/actions/runs?branch={BRANCH}&per_page=100&page={page}")
        got = [x for x in d.get("workflow_runs", []) if x.get("name") == WF_NAME]
        out += got
        if len(d.get("workflow_runs", [])) < 100:
            break
    return out


def run_jobs(rid):
    d = gh_json(f"repos/{REPO}/actions/runs/{rid}/jobs?per_page=100")
    return d.get("jobs", [])


def cmd_status(a):
    n = 0
    for run in wf_runs():
        if run["status"] == "completed":
            continue
        for j in run_jobs(run["id"]):
            if j["status"] != "completed":
                n += 1
                print(f"{run['id']}\t{j['name']}\t{j['status']}\t{j.get('started_at')}")
    print(f"{n} E5 jobs queued or running")


def cmd_collect(a):
    os.makedirs(a.results, exist_ok=True)
    done_path = os.path.join(a.results, ".e5_artifacts_done.json")
    try:
        done = set(json.load(open(done_path)))
    except Exception:
        done = set()
    new = 0
    for run in wf_runs():
        rid = run["id"]
        arts = gh_json(f"repos/{REPO}/actions/runs/{rid}/artifacts?per_page=100").get("artifacts", [])
        jobs = {j["name"]: j for j in run_jobs(rid)}
        for art in arts:
            key = f"{rid}:{art['name']}"
            if key in done or art.get("expired"):
                continue
            # only take an artifact once its job has completed (the upload step runs last)
            if run["status"] != "completed":
                jname = art["name"].split("-", 2)[-1]
                jname = next((n for n in jobs if n.endswith(" " + jname)), None)
                if jname is None or jobs[jname]["status"] != "completed":
                    continue
            with tempfile.TemporaryDirectory(dir=a.results) as td:
                zp = os.path.join(td, "a.zip")
                with open(zp, "wb") as fo:
                    r = subprocess.run(["gh", "api", f"repos/{REPO}/actions/artifacts/{art['id']}/zip"], stdout=fo,
                                       stderr=subprocess.PIPE)
                if r.returncode != 0:
                    print(f"[collect] {art['name']}: download failed {r.stderr.decode(errors='replace')[:120]}")
                    continue
                ex = os.path.join(td, "x")
                with zipfile.ZipFile(zp) as z:
                    for nm in z.namelist():   # refuse absolute or parent paths
                        if nm.startswith("/") or ".." in nm.split("/"):
                            raise RuntimeError(f"unsafe path in artifact: {nm}")
                    z.extractall(ex)
                for name in sorted(os.listdir(ex)):
                    src = os.path.join(ex, name)
                    if name == "chains":
                        os.makedirs(os.path.join(a.results, "chains"), exist_ok=True)
                        for f in os.listdir(src):
                            shutil.copy2(os.path.join(src, f), os.path.join(a.results, "chains", f))
                        continue
                    if not os.path.isdir(src):
                        continue
                    dst = os.path.join(a.results, name)
                    if os.path.exists(dst):
                        shutil.rmtree(dst)
                    shutil.copytree(src, dst)
                    r = e5lib.load_run(dst)
                    print(f"[collect] {name}: {r['status']} ws={r['ws']} hold={r['hold_ws']} drc={r['drc']} "
                          f"claim={r['claim']} pass={r['pass']}")
                    new += 1
            done.add(key)
    json.dump(sorted(done), open(done_path, "w"))
    print(f"[collect] {new} run dirs updated")


def all_runs(results, prefix=None):
    out = {}
    for name in sorted(os.listdir(results)):
        d = os.path.join(results, name)
        if not os.path.isdir(d) or name == "chains" or name.startswith("."):
            continue
        if prefix and not name.startswith(prefix):
            continue
        out[name] = e5lib.load_run(d)
    return out


def cmd_table(a):
    R = all_runs(a.results, a.prefix)
    print("tag\tdesign\tsetting\tperiod\tws\tclaim\thold\tdrc\tpass\tport\tws_r2r\tutil\tarea\telapsed_s\tstatus")
    for t, r in R.items():
        print("\t".join(str(x) for x in (t, r["design"], r["setting"], r["period"],
                                          None if r["ws"] is None else round(r["ws"], 2),
                                          None if r["claim"] is None else round(r["claim"], 2),
                                          None if r["hold_ws"] is None else round(r["hold_ws"], 2), r["drc"],
                                          r["pass"], r["port"], r["ws_r2r"], r["util"], r["area_um2"],
                                          r["elapsed_s"], r["status"])))


GRID_PATH = os.path.join(HERE, "grid.json")
DISPATCH_PATH = os.path.join(HERE, "dispatch.json")


def grid_runs(grid):
    """The registered grid: per design, settings x targets, tags e5g-<design>-<nnn> in listed order."""
    out = []
    for d in grid["designs"]:
        k = 0
        for s in d["settings"]:
            for t in s["targets"]:
                k += 1
                out.append({"tag": f"e5g-{d['design']}-{k:03d}", "design": d["design"], "period": int(t),
                            "vars": s["vars"], "setting": s["setting"], "kind": "grid"})
    return out


def write_dispatch(batch, groups, about):
    assert len(groups) <= 8
    d = {"batch": batch, "about": about, "groups": groups}
    os.makedirs(os.path.join(HERE, "batches"), exist_ok=True)
    for p in (DISPATCH_PATH, os.path.join(HERE, "batches", batch + ".json")):
        json.dump(d, open(p, "w"), indent=1)
    print(f"wrote {DISPATCH_PATH} ({len(groups)} groups, "
          f"{sum(len(g.get('runs', [])) + len(g.get('chains', [])) for g in groups)} runs/chains)")


def cmd_grid(a):
    grid = json.load(open(GRID_PATH))
    runs = grid_runs(grid)
    groups = []
    for d in grid["designs"]:
        if a.designs and d["design"] not in a.designs.split(","):
            continue
        rs = [r for r in runs if r["design"] == d["design"]]
        n = int(d["jobs"])
        for j in range(n):
            part = rs[j::n]
            if part:
                groups.append({"name": f"{d['design']}{j + 1}", "num_cores": d["num_cores"],
                               "timeout_s": d["timeout_s"], "runs": part})
    write_dispatch(a.batch, groups, "E5 audit grid (registered in Addendum 41): settings x clock targets")


def top3(R, design, k=3):
    """The tuner's picks: lowest AutoTuner score (claimed clock, DRC-penalized) among the design's grid runs."""
    rs = [r for r in R.values() if r["design"] == design and r["tag"].startswith("e5g-")]
    rs = [r for r in rs if e5lib.tuner_score(r) < 9e99]
    rs.sort(key=lambda r: (e5lib.tuner_score(r), r["tag"]))
    return rs[:k]


def cmd_chains(a):
    grid = json.load(open(GRID_PATH))
    R = all_runs(a.results, "e5g-")
    groups = []
    for d in grid["designs"]:
        if a.designs and d["design"] not in a.designs.split(","):
            continue
        for i, w in enumerate(top3(R, d["design"]), 1):
            vars_ = (json.load(open(os.path.join(a.results, w["tag"], "job.json"))) or {}).get("vars") or {}
            ch = {"chain_id": f"e5k-{d['design']}-{i}", "design": d["design"], "setting": w["setting"], "vars": vars_,
                  "tag_prefix": f"e5k-{d['design']}-{i}-",
                  "winner": {"tag": w["tag"], "period": w["period"], "claim": w["claim"], "pass": w["pass"]}}
            groups.append({"name": f"k{d['design']}{i}", "num_cores": d["num_cores"], "timeout_s": d["timeout_s"],
                           "chains": [ch]})
            print(f"{ch['chain_id']}: winner {w['tag']} {w['setting']} T0={w['period']} claim={w['claim']:.2f} "
                  f"pass={w['pass']} -> first rebuild at {e5lib.ceil_grid(w['claim'])} ps")
    write_dispatch(a.batch, groups, "E5 registered rebuild chains (Addendum 41): top 3 settings per design")


# ---------------------------------------------------------------- analysis (fixed-point method of agents/analysis/fixedpoint)
def linfit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx < 1e-12:
        return None, None
    s = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return s, my - s * mx


def crossing(pts):
    """Copied from agents/analysis/fixedpoint/analyze.py: pts [(T, teff)] sorted by T. Returns (F, how)."""
    g = [(T, te - T) for T, te in pts]
    for (t1, g1), (t2, g2) in zip(g, g[1:]):
        if g1 > 0 >= g2:
            return t1 + (t2 - t1) * g1 / (g1 - g2), "interpolated"

    def extra(p1, p2, how):
        s, b = linfit([p1[0], p2[0]], [p1[1], p2[1]])
        if s is None or s >= 0.999:
            return None, how + " (no crossing: slope >= 1)"
        return b / (1 - s), how
    if all(x <= 0 for _, x in g):
        return extra(pts[0], pts[1], "extrapolated below")
    if all(x > 0 for _, x in g):
        return extra(pts[-2], pts[-1], "extrapolated above")
    s, b = linfit([p[0] for p in pts], [p[1] for p in pts])
    if s is None or s >= 0.999:
        return None, "no crossing"
    return b / (1 - s), "fit all"


def summ(xs):
    xs = sorted(xs)
    if not xs:
        return None
    return {"n": len(xs), "median": st.median(xs), "min": xs[0], "max": xs[-1]}


SKY130_BINS = {  # agents/analysis/fixedpoint/data.json, interpolated settings (60 settings, 328 points)
    "tight (<0.9)": {"all": -0.1450, "port": -0.1113, "r2r": -0.1540, "n": 111},
    "near (0.9-1.1)": {"all": -0.0000, "port": -0.0002, "r2r": -0.0000, "n": 153},
    "loose (1.1-1.5)": {"all": 0.0823, "port": 0.0925, "r2r": 0.0458, "n": 48},
    "very loose (>1.5)": {"all": 0.1374, "port": 0.1389, "r2r": 0.1157, "n": 16},
}
BINS = (("tight (<0.9)", 0, 0.9), ("near (0.9-1.1)", 0.9, 1.1), ("loose (1.1-1.5)", 1.1, 1.5),
        ("very loose (>1.5)", 1.5, 99))


def setting_key(r, job):
    return json.dumps({"design": r["design"], "vars": (job or {}).get("vars") or {}}, sort_keys=True)


def cmd_analyze(a):
    R = all_runs(a.results)
    audit = {t: r for t, r in R.items() if t.startswith(("e5g-", "e5k-"))}
    jobs = {t: (e5lib._load(os.path.join(a.results, t, "job.json"), {}) or {}) for t in audit}
    out = {"runs": audit}
    # ---- primary: the registered chains of the top 3 settings per design
    chains = {}
    cdir = os.path.join(a.results, "chains")
    for f in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
        c = e5lib._load(os.path.join(cdir, f))
        if c and c["chain_id"].startswith("e5k-"):
            chains[c["chain_id"]] = c
    prim = []
    for cid, c in sorted(chains.items()):
        w = c["winner"]
        st0 = c["chain"]
        first = st0[1] if len(st0) > 1 else dict(st0[0], first_is_winner=True)
        c1 = first.get("claim")
        prim.append({"chain_id": cid, "design": c["design"], "winner": w["tag"], "T0": w["period"], "C0": w["claim"],
                     "R1": first["period"], "first_pass": bool(first.get("pass")), "C1": c1,
                     "d1": (c1 / w["claim"] - 1) if (c1 is not None and w["claim"]) else None,
                     "kept": c.get("kept_clock"), "kept_over_claim": (c["kept_clock"] / w["claim"])
                     if c.get("kept_clock") else None, "n_rebuilds": sum(1 for s in st0[1:] if not s.get("reused")),
                     "chain": [(s["period"], s.get("claim"), s.get("pass")) for s in st0]})
    reg = [p for p in prim if p["design"] in ("gcd", "aes")]
    fails = sum(1 for p in reg if not p["first_pass"])
    d1s = [abs(p["d1"]) for p in reg if p["d1"] is not None]
    med = st.median(d1s) if d1s else None
    out["primary"] = {"chains": prim, "registered_designs": ["gcd", "aes"], "n_registered": len(reg),
                      "first_rebuild_fails": fails, "median_abs_d1": med,
                      "a_fail": fails >= 1, "b_drift": (med is not None and med > 0.02),
                      "verdict": None if len(reg) < 6 else ("H1 SUPPORTED (claims did not hold)" if (fails >= 1 or (
                          med is not None and med > 0.02)) else "H1 NOT SUPPORTED (claims held)")}
    # ---- secondary: claim error vs the clock each setting can meet (fixed point), binned like sky130
    groups = defaultdict(list)
    for t, r in audit.items():
        if r["claim"] is None:
            continue
        groups[setting_key(r, jobs[t])].append(r)
    G = []
    for k, rs in groups.items():
        byT = defaultdict(list)
        for r in rs:
            byT[float(r["period"])].append(r)
        Ts = sorted(byT)
        if len(Ts) < 2:
            continue
        pts = [(T, st.median(x["claim"] for x in byT[T])) for T in Ts]
        F, how = crossing(pts)
        passing = [r["period"] for r in rs if r["pass"]]
        port_pts = sorted((r["period"], r["claim"]) for r in rs if r["port"])
        r2r_pts = sorted((r["period"], r["t_r2r"]) for r in rs if r["t_r2r"] is not None)
        G.append({"key": json.loads(k), "n": len(rs), "targets": Ts, "F_emp": F, "how": how,
                  "F_obs": min(passing) if passing else None,
                  "slope_teff": linfit([p[0] for p in pts], [p[1] for p in pts])[0],
                  "slope_port": linfit([p[0] for p in port_pts], [p[1] for p in port_pts])[0]
                  if len({p[0] for p in port_pts}) >= 2 else None,
                  "slope_r2r": linfit([p[0] for p in r2r_pts], [p[1] for p in r2r_pts])[0]
                  if len({p[0] for p in r2r_pts}) >= 2 else None,
                  "points": [{"tag": r["tag"], "T": r["period"], "teff": r["claim"], "port": r["port"],
                              "pass": r["pass"]} for r in sorted(rs, key=lambda r: r["period"])]})
    bias = []
    for g in G:
        if g["how"] != "interpolated":
            continue
        for p in g["points"]:
            bias.append({"design": g["key"]["design"], "tag": p["tag"], "port": p["port"], "ratio": p["T"] / g["F_emp"],
                         "bias": (p["teff"] - g["F_emp"]) / g["F_emp"]})
    bins = {}
    for lab, lo, hi in BINS:
        for kind in ("all", "port", "r2r"):
            xs = [b["bias"] for b in bias if lo <= b["ratio"] < hi and (kind == "all" or (kind == "port") == bool(b["port"]))]
            bins[f"{lab}|{kind}"] = summ(xs)
    s2 = {}
    for lab in ("tight (<0.9)", "loose (1.1-1.5)"):
        b = bins[f"{lab}|all"]
        s2[lab] = None if (not b or b["n"] < 3) else {"asap7_median": b["median"], "n": b["n"],
                                                       "sky130_median": SKY130_BINS[lab]["all"],
                                                       "further": abs(b["median"]) > abs(SKY130_BINS[lab]["all"])}
    if any(v is None for v in s2.values()):
        s2_verdict = "insufficient (a bin has fewer than 3 points)"
    elif all(v["further"] for v in s2.values()):
        s2_verdict = "supports the speaker notes (drift further at 7 nm in both bins)"
    elif not any(v["further"] for v in s2.values()):
        s2_verdict = "contradicts the speaker notes (drift smaller at 7 nm in both bins)"
    else:
        s2_verdict = "mixed"
    out["secondary"] = {"settings": G, "interpolated_settings": sum(1 for g in G if g["how"] == "interpolated"),
                        "bias_points": bias, "bins": bins, "sky130_bins": SKY130_BINS,
                        "S1_tight_overclaim_median": (bins["tight (<0.9)|all"] or {}).get("median"),
                        "S2": s2, "S2_verdict": s2_verdict,
                        "slopes": {"teff": summ([g["slope_teff"] for g in G if g["slope_teff"] is not None]),
                                   "port": summ([g["slope_port"] for g in G if g["slope_port"] is not None]),
                                   "r2r": summ([g["slope_r2r"] for g in G if g["slope_r2r"] is not None])}}
    json.dump(out, open(a.out, "w"), indent=1, default=float)
    p = out["primary"]
    print(f"primary: {p['n_registered']} registered chains, first-rebuild fails {p['first_rebuild_fails']}, "
          f"median |d1| {p['median_abs_d1']}, verdict {p['verdict']}")
    for c in prim:
        print(f"  {c['chain_id']}: {c['winner']} T0={c['T0']} C0={c['C0']:.1f} R1={c['R1']} pass1={c['first_pass']} "
              f"C1={c['C1']} d1={c['d1']} kept={c['kept']} chain={c['chain']}")
    print("S1 tight median:", out["secondary"]["S1_tight_overclaim_median"], "| S2:", s2_verdict)
    for k, v in bins.items():
        if v:
            print("  ", k, {kk: round(vv, 4) if isinstance(vv, float) else vv for kk, vv in v.items()})


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("collect", "table", "status", "grid", "chains", "analyze"):
        p = sub.add_parser(name)
        p.add_argument("--results", default=DEFAULT_RESULTS)
        p.add_argument("--prefix", default=None)
        p.add_argument("--batch", default=None)
        p.add_argument("--designs", default=None, help="comma list (grid/chains)")
        p.add_argument("--out", default=os.path.join(DEFAULT_RESULTS, "e5_analysis.json"))
    a = ap.parse_args()
    {"collect": cmd_collect, "table": cmd_table, "status": cmd_status, "grid": cmd_grid, "chains": cmd_chains,
     "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
