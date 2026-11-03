#!/usr/bin/env python3
"""AD (TrueClock overnight push, workstream AD: experiment A "slack is not distance" and experiment D "three nodes, one
flow"). Local driver and the registered scoring code named in docs/qa_week/AD_PREREG.md.

  ad.py plan --batch NAME --what smoke|main   write farm/qa/AD/dispatch.json (+ batches/NAME.json) from grid.json
  ad.py collect [--results DIR]               download new ad-* artifacts of this branch's AD workflow runs, keeping
                                              only the small files the analysis reads (no logs, no layouts)
  ad.py table [--results DIR] [--prefix P]
  ad.py t1 [--out FILE]                       T1: the law fitted on E5's 30 ASAP7 grid runs predicts E5's 16 rebuilds
                                              (a registered retrodiction: those outcomes were already in the record)
  ad.py analyze [--results DIR] [--out FILE]  T2a, T2b, T3 and D on the collected AD runs

Units: every time is in ps (sky130hd's ns metrics are converted by adlib.load_run).

The law (ideas/mechanism-law.md section 2): per setting, F = the clock the setting can meet, found as E5 found it
(the interpolated crossing of claim = target between the adjacent targets where the setting goes from missing setup
to meeting it; E5's `crossing`, copied from agents/analysis/fixedpoint/analyze.py). r = T/F, e = (C - F)/F. Only
settings with an interpolated F enter. Within a setting, repeated (T, C) points count once. s- = least squares slope
of e on (r - 1) through the origin over points with r < 1; s+ the same over r > 1.
"""
from __future__ import annotations

import argparse
import json
import math
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
import adlib  # noqa: E402

REPO = "Avi-Patel-1/beforeroute-farm"
BRANCH = "qa-ad-law"
WF_NAME = "AD law and nodes (ORFS)"
DEFAULT_RESULTS = os.path.abspath(os.path.join(HERE, "..", "..", "..", "results_ad"))
GRID_PATH = os.path.join(HERE, "grid.json")
DISPATCH_PATH = os.path.join(HERE, "dispatch.json")
E5_ANALYSIS = os.path.join(HERE, "..", "E5", "e5_analysis.json")


# ======================================================================================================== planning
def grid_runs(arm: dict) -> list[dict]:
    """An arm's registered grid: per design, settings x targets, tags <tag>-<design>-<nnn> in listed order."""
    out = []
    for d in arm["designs"]:
        k = 0
        for s in d["settings"]:
            for t in s["targets"]:
                k += 1
                v = dict(arm.get("extra_vars", {}).get(d["design"], {}))
                v.update(s["vars"])
                out.append({"tag": f"{arm['tag']}-{d['design']}-{k:03d}", "design": d["design"],
                            "platform": arm["platform"], "period": int(t), "vars": v, "setting": s["setting"],
                            "kind": "grid", "arm": arm["name"], "abc_d": int(arm.get("abc_d", 0))})
    return out


def t3_runs(grid: dict) -> list[dict]:
    """T3: replays of E5's 9 winners (the top 3 per design by AutoTuner's score), with the re-time hook on."""
    e5 = json.load(open(E5_ANALYSIS))
    out = []
    for c in sorted(e5["primary"]["chains"], key=lambda c: c["chain_id"]):
        w = e5["runs"][c["winner"]]
        rank = c["chain_id"].rsplit("-", 1)[1]
        out.append({"tag": f"adr-{c['design']}-{rank}", "design": c["design"], "platform": "asap7",
                    "period": int(w["period"]), "vars": w["vars"] or {}, "setting": w["setting"], "kind": "replay",
                    "arm": "T3", "retime": 1, "replay_of": c["winner"]})
    return out


def split(xs, n):
    return [xs[j::n] for j in range(n) if xs[j::n]]


def write_dispatch(batch, groups, about):
    d = {"batch": batch, "about": about, "groups": groups}
    os.makedirs(os.path.join(HERE, "batches"), exist_ok=True)
    for p in (DISPATCH_PATH, os.path.join(HERE, "batches", batch + ".json")):
        json.dump(d, open(p, "w"), indent=1)
    n = sum(len(g.get("runs", [])) for g in groups)
    print(f"wrote {DISPATCH_PATH}: {len(groups)} groups, {n} grid/replay runs, "
          f"{sum(len(g.get('await_chains', [])) for g in groups)} chain selections")


def cmd_plan(a):
    grid = json.load(open(GRID_PATH))
    arms = {x["name"]: x for x in grid["arms"]}
    if a.what == "smoke":
        def sm(tag, platform, design, period, vars_=None, **kw):
            r = {"tag": tag, "design": design, "platform": platform, "period": period, "vars": vars_ or {},
                 "setting": "S0", "kind": "smoke", "arm": "smoke"}
            r.update(kw)
            return r
        e5 = json.load(open(E5_ANALYSIS))
        w = e5["runs"]["e5g-gcd-001"]
        groups = [
            {"name": "sm-sky", "num_cores": 4, "timeout_s": 3600,
             "runs": [sm("smoke-ads-gcd", "sky130hd", "gcd", 1100)]},
            {"name": "sm-abc", "num_cores": 4, "timeout_s": 3600, "parallel": 2,
             "runs": [sm("smoke-adb-gcd-215", "asap7", "gcd", 215, {"SYNTH_USE_SYN": 0}, abc_d=1),
                      sm("smoke-adb-gcd-450", "asap7", "gcd", 450, {"SYNTH_USE_SYN": 0}, abc_d=1),
                      sm("smoke-adc-gcd-215", "asap7", "gcd", 215, {"SYNTH_USE_SYN": 0}),
                      sm("smoke-adr-gcd-1", "asap7", "gcd", int(w["period"]), w["vars"], retime=1)]},
            {"name": "sm-ibex", "num_cores": 4, "timeout_s": 3600, "parallel": 3,
             "runs": [sm("smoke-adb-ibex-630", "asap7", "ibex", 630, abc_d=1, stop="synth"),
                      sm("smoke-adb-ibex-1305", "asap7", "ibex", 1305, abc_d=1, stop="synth"),
                      sm("smoke-adc-ibex-630", "asap7", "ibex", 630, stop="synth")]},
            {"name": "sm-gt2n", "num_cores": 4, "timeout_s": 3600,
             "runs": [sm("smoke-adg-gcd", "gt2n", "gcd", 170)]},
            {"name": "sm-chain", "num_cores": 4, "timeout_s": 3600,
             "await_chains": [{"key": "smoke/sky130hd/gcd", "design": "gcd", "platform": "sky130hd",
                               "grid_tags": ["smoke-ads-gcd"], "grid_groups": ["sm-sky"], "ranks": [1],
                               "chain_prefix": "smoke-adsk-gcd", "arm": "smoke", "max_rebuilds": 1,
                               "max_wait_s": 2400}]},
        ]
        write_dispatch(a.batch, groups, "AD smoke (plumbing only; tags smoke-*; excluded from every analysis)")
        return
    # ---- main batch: the registered runs, in priority order (T2 grids, sky130hd chains, T3, GT2N, control)
    G = {}
    for name in ("T2a", "T2b", "DG", "C"):
        for r in grid_runs(arms[name]):
            G.setdefault((name, r["design"]), []).append(r)
    T3 = t3_runs(grid)
    groups = []
    # designs whose grid anchor is computed on the runner from pilots re-run solo in this batch (amendment 1)
    RT = set((a.runtime_anchor or "").split(",")) - {""}
    PILOTS = {"sky130hd/aes": [3600, 5760, 9000], "sky130hd/ibex": [8000, 12800, 20000], "gt2n/aes": [350, 490, 700]}
    MULT = {"S0": [0.70, 0.85, 1.00, 1.40], "S1": [0.80, 1.20, 1.45], "S2": [0.80, 1.20, 1.45]}
    pilot_groups = {}
    for key in [k for k in ("sky130hd/ibex", "sky130hd/aes") if k in RT]:
        platform, design = key.split("/")
        pilot_groups[key] = []
        for T in PILOTS[key]:
            name = f"p2-{platform}-{design}-{T}"
            groups.append({"name": name, "num_cores": 4, "timeout_s": 7200, "parallel": 1,
                           "runs": [{"tag": f"smoke-pilot2-{platform}-{design}-{T}", "design": design,
                                     "platform": platform, "period": T, "vars": {}, "setting": "S0", "kind": "pilot",
                                     "arm": "smoke"}]})
            pilot_groups[key].append(name)

    def add_pilots(key):
        platform, design = key.split("/")
        pilot_groups[key] = []
        for T in PILOTS[key]:
            name = f"p2-{platform}-{design}-{T}"
            groups.append({"name": name, "num_cores": 4, "timeout_s": 7200, "parallel": 1,
                           "runs": [{"tag": f"smoke-pilot2-{platform}-{design}-{T}", "design": design,
                                     "platform": platform, "period": T, "vars": {}, "setting": "S0", "kind": "pilot",
                                     "arm": "smoke"}]})
            pilot_groups[key].append(name)

    def grid_groups_for(arm_name, design, n, prefix, timeout):
        arm = arms[arm_name]
        key = f"{arm['platform']}/{design}"
        if key not in RT:
            return [add(f"{prefix}-{i + 1}", p, timeout=timeout) for i, p in enumerate(split(G[(arm_name, design)], n))]
        d = next(x for x in arm["designs"] if x["design"] == design)
        settings = [{"setting": s_["setting"], "vars": s_["vars"], "mult": MULT[s_["setting"]]} for s_ in d["settings"]]
        names = []
        for i in range(n):
            spec = {"key": f"{arm_name}/{key}", "arm": arm_name, "tag": arm["tag"], "design": design,
                    "platform": arm["platform"], "pilot_tags": [f"smoke-pilot2-{key.replace('/', '-')}-{T}"
                                                                for T in PILOTS[key]],
                    "pilot_groups": pilot_groups[key], "settings": settings, "share": list(range(10))[i::n],
                    "max_wait_s": 9000, "extra_vars": arm.get("extra_vars", {}).get(design, {})}
            groups.append({"name": f"{prefix}-{i + 1}", "num_cores": 4, "timeout_s": timeout, "parallel": 1,
                           "anchor_grid": [spec]})
            names.append(f"{prefix}-{i + 1}")
        return names

    def add(name, runs=None, aw=None, timeout=10800, parallel=1):
        g = {"name": name, "num_cores": 4, "timeout_s": timeout, "parallel": parallel}
        if runs:
            g["runs"] = runs
        if aw:
            g["await_chains"] = aw
        groups.append(g)
        return name

    def await_spec(arm, design, ranks, grid_groups, prefix, max_wait=9000):
        rs = G[(arm, design)]
        return {"key": f"{arm}/{rs[0]['platform']}/{design}", "design": design, "platform": rs[0]["platform"],
                "grid_tags": [r["tag"] for r in rs], "grid_groups": grid_groups, "ranks": ranks,
                "chain_prefix": prefix, "arm": arm, "max_wait_s": max_wait}

    # order: (pilots above), work that needs no anchor, GT2N pilots, anchored T2a grids, T2b ibex, chains, GT2N
    add("s-gcd", G[("T2a", "gcd")], [await_spec("T2a", "gcd", [1, 2, 3], [], "adsk-gcd")], timeout=3600)
    add("b-gcd", G[("T2b", "gcd")], timeout=3600, parallel=2)
    [add(f"b-aes-{i + 1}", p, timeout=5400) for i, p in enumerate(split(G[("T2b", "aes")], 2))]
    add("r-aes-gcd", [r for r in T3 if r["design"] != "ibex"], timeout=5400)
    if "gt2n/aes" in RT:
        add_pilots("gt2n/aes")
    s_ibex = grid_groups_for("T2a", "ibex", 5, "s-ibex", 10800)
    s_aes = grid_groups_for("T2a", "aes", 4, "s-aes", 9000)
    add("r-ibex", [r for r in T3 if r["design"] == "ibex"], timeout=5400)
    [add(f"b-ibex-{i + 1}", p, timeout=5400) for i, p in enumerate(split(G[("T2b", "ibex")], 3))]
    # D: sky130hd rebuild chains (runner side, once the design's grid has landed), one chain per job
    for i in (1, 2, 3):
        add(f"ks-ibex-{i}", aw=[await_spec("T2a", "ibex", [i], s_ibex, "adsk-ibex")], timeout=10800)
    for i in (1, 2, 3):
        add(f"ks-aes-{i}", aw=[await_spec("T2a", "aes", [i], s_aes, "adsk-aes")], timeout=9000)
    # D: GT2N grids and chains
    add("g-gcd", G[("DG", "gcd")], [await_spec("DG", "gcd", [1, 2, 3], [], "adgk-gcd")], timeout=3600)
    g_aes = grid_groups_for("DG", "aes", 4, "g-aes", 9000)
    for i in (1, 2, 3):
        add(f"kg-aes-{i}", aw=[await_spec("DG", "aes", [i], g_aes, "adgk-aes")], timeout=9000)
    # descriptive control: ASAP7 gcd and aes through Yosys/ABC without the clock (the T2b synthesizer, stock)
    add("c-gcd", G[("C", "gcd")], timeout=3600, parallel=2)
    add("c-aes", G[("C", "aes")], timeout=5400)
    write_dispatch(a.batch, groups, "AD main batch (registered in docs/qa_week/AD_PREREG.md): T2a/D sky130hd grid "
                   "and chains, T2b ASAP7 ABC-told-the-clock grid, T3 re-time replays, D GT2N grid and chains, "
                   "descriptive Yosys control")


# ======================================================================================================== collecting
KEEP = ("run.json", "job.json", "make_vars.txt", "ad_abc_evidence.txt", "ad_abc_patch.txt", "constraint.sdc")
KEEP_REPORTS = ("e5_hook.json", "ad_retime.json", "synth_stat.txt", "6_finish.rpt")


def gh_json(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)


def wf_runs():
    out = []
    for page in range(1, 4):
        d = gh_json(f"repos/{REPO}/actions/runs?branch={BRANCH}&per_page=100&page={page}")
        out += [x for x in d.get("workflow_runs", []) if x.get("name") == WF_NAME]
        if len(d.get("workflow_runs", [])) < 100:
            break
    return out


def cmd_collect(a):
    os.makedirs(a.results, exist_ok=True)
    done_path = os.path.join(a.results, ".ad_artifacts_done.json")
    try:
        done = set(json.load(open(done_path)))
    except Exception:
        done = set()
    new = 0
    for run in wf_runs():
        if a.run_id and str(run["id"]) != str(a.run_id):
            continue
        rid = run["id"]
        arts = []
        for page in range(1, 6):
            d = gh_json(f"repos/{REPO}/actions/runs/{rid}/artifacts?per_page=100&page={page}")
            arts += d.get("artifacts", [])
            if len(d.get("artifacts", [])) < 100:
                break
        for art in arts:
            key = f"{rid}:{art['name']}"
            if key in done or art.get("expired"):
                continue
            with tempfile.TemporaryDirectory(dir=a.results) as td:
                zp = os.path.join(td, "a.zip")
                with open(zp, "wb") as fo:
                    r = subprocess.run(["gh", "api", f"repos/{REPO}/actions/artifacts/{art['id']}/zip"], stdout=fo,
                                       stderr=subprocess.PIPE)
                if r.returncode != 0:
                    print(f"[collect] {art['name']}: download failed")
                    continue
                with zipfile.ZipFile(zp) as z:
                    for nm in z.namelist():
                        if nm.startswith("/") or ".." in nm.split("/"):
                            raise RuntimeError(f"unsafe path in artifact: {nm}")
                        parts = nm.split("/")
                        keep = (len(parts) == 2 and parts[1] in KEEP) or \
                               (len(parts) == 3 and parts[1] == "logs" and parts[2].endswith(".json")) or \
                               (len(parts) == 3 and parts[1] == "reports" and parts[2] in KEEP_REPORTS) or \
                               (len(parts) == 2 and parts[0] in ("chains", "anchors") and parts[1].endswith(".json"))
                        if not keep or nm.endswith("/"):
                            continue
                        dst = os.path.join(a.results, *parts)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        with z.open(nm) as fi, open(dst, "wb") as fo:
                            shutil.copyfileobj(fi, fo)
                        if parts[-1] == "run.json" and len(parts) == 2:
                            new += 1
            done.add(key)
            print(f"[collect] {art['name']}")
    json.dump(sorted(done), open(done_path, "w"))
    print(f"[collect] {new} run dirs updated")


def all_runs(results, prefix=None):
    out = {}
    if not os.path.isdir(results):
        return out
    for name in sorted(os.listdir(results)):
        d = os.path.join(results, name)
        if not os.path.isdir(d) or name == "chains" or name.startswith("."):
            continue
        if prefix and not name.startswith(prefix):
            continue
        out[name] = adlib.load_run(d)
    return out


def cmd_table(a):
    R = all_runs(a.results, a.prefix)
    print("tag\tplatform\tsetting\tperiod\tws\tclaim\thold\tdrc\tpass\tport\tsynth_cells\tsynth_sha1\tabc_hits\tstatus")
    for t, r in R.items():
        f = (lambda x: None if x is None else round(x, 2))
        print("\t".join(str(x) for x in (t, r["platform"], r["setting"], r["period"], f(r["ws"]), f(r["claim"]),
                                          f(r["hold_ws"]), r["drc"], r["pass"], r["port"], r.get("synth_cells"),
                                          (r.get("synth_sha1") or "")[:10], r.get("abc_d_log_hits"), r["status"])))


# ======================================================================================================== the law
def linfit(xs, ys):
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx < 1e-12:
        return None, None
    s = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    return s, my - s * mx


def crossing(pts):
    """Copied from farm/qa/E5/e5.py (itself from agents/analysis/fixedpoint/analyze.py): pts [(T, claim)] sorted by T.
    Returns (F, how)."""
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


def setting_key(r):
    return json.dumps({"platform": r.get("platform", "asap7"), "design": r["design"], "vars": r.get("vars") or {}},
                      sort_keys=True)


def settings_F(runs):
    """Per setting: F by E5's crossing over the median claim at each target. Returns {key: (F, how, runs)}."""
    groups = defaultdict(list)
    for r in runs:
        if r.get("claim") is not None:
            groups[setting_key(r)].append(r)
    out = {}
    for k, rs in groups.items():
        byT = defaultdict(list)
        for r in rs:
            byT[float(r["period"])].append(r["claim"])
        Ts = sorted(byT)
        if len(Ts) < 2:
            out[k] = (None, "one target", rs)
            continue
        F, how = crossing([(T, st.median(byT[T])) for T in Ts])
        out[k] = (F, how, rs)
    return out


def law_points(SF):
    pts = []
    for k, (F, how, rs) in SF.items():
        if how != "interpolated":
            continue
        seen = set()
        for r in sorted(rs, key=lambda r: (r["period"], r["tag"])):
            kk = (float(r["period"]), round(r["claim"], 3))
            if kk in seen:
                continue
            seen.add(kk)
            pts.append({"tag": r["tag"], "design": r["design"], "key": k, "F": F, "r": r["period"] / F,
                        "e": (r["claim"] - F) / F, "port": r.get("port")})
    return pts


def slope0(pairs):
    sxx = sum(x * x for x, _ in pairs)
    return None if sxx <= 0 else sum(x * y for x, y in pairs) / sxx


def fit_law(pts):
    lo = [(p["r"] - 1, p["e"]) for p in pts if p["r"] < 1]
    hi = [(p["r"] - 1, p["e"]) for p in pts if p["r"] > 1]
    return {"s_minus": slope0(lo), "n_minus": len(lo), "s_plus": slope0(hi), "n_plus": len(hi)}


BINS = (("tight (<0.9)", 0, 0.9), ("near (0.9-1.1)", 0.9, 1.1), ("loose (1.1-1.5)", 1.1, 1.5),
        ("very loose (>1.5)", 1.5, 99))


def bins_of(pts):
    out = {}
    for lab, lo, hi in BINS:
        xs = sorted(p["e"] for p in pts if lo <= p["r"] < hi)
        out[lab] = {"n": len(xs), "median": st.median(xs) if xs else None}
    return out


# ======================================================================================================== anchoring
def cmd_anchor(a):
    """Grid anchor for sky130hd and GT2N (registered in AD_PREREG.md, 'Grid anchor'): P0 = 5 * round(F_pilot / 5),
    F_pilot = E5's crossing over the shipped config's pilot runs (smoke01 + smoke02, tags smoke-ads-gcd,
    smoke-adsk-gcd-1-1, smoke-adg-gcd, smoke-pilot-*). Targets: 5 * round(m * P0 / 5)."""
    R = all_runs(a.results, "smoke-")
    pts = defaultdict(list)
    for t, r in R.items():
        if r["claim"] is None or r.get("platform") not in ("sky130hd", "gt2n"):
            continue
        if (r.get("vars") or {}) not in ({}, None):
            continue
        pts[(r["platform"], r["design"])].append((float(r["period"]), r["claim"], t))
    out = {}
    for k, ps in sorted(pts.items()):
        ps.sort()
        byT = defaultdict(list)
        for T, C, _ in ps:
            byT[T].append(C)
        F, how = crossing([(T, st.median(byT[T])) for T in sorted(byT)])
        P0 = None if F is None else int(5 * round(F / 5))
        tg = None if P0 is None else {
            "S0": [int(5 * round(m * P0 / 5)) for m in (0.70, 0.85, 1.00, 1.40)],
            "S1S2": [int(5 * round(m * P0 / 5)) for m in (0.80, 1.20, 1.45)]}
        out["/".join(k)] = {"pilots": [(T, round(C, 2), t) for T, C, t in ps], "F_pilot": F, "how": how, "P0": P0,
                            "targets": tg}
        print(f"{'/'.join(k):14s} pilots {[(int(T), round(C, 1)) for T, C, _ in ps]} -> F_pilot "
              f"{'-' if F is None else round(F, 1)} ({how}) -> P0 {P0} targets {tg}")
    json.dump(out, open(a.out, "w"), indent=1)
    if a.apply:   # write P0 and the targets into grid.json (arms T2a = sky130hd, DG = gt2n)
        grid = json.load(open(GRID_PATH))
        for arm in grid["arms"]:
            if arm["platform"] not in ("sky130hd", "gt2n"):
                continue
            for d in arm["designs"]:
                k = f"{arm['platform']}/{d['design']}"
                d["P0_shipped"] = d.get("P0_shipped", d["P0"])
                if k not in out or out[k]["P0"] is None:   # anchored on the runner (Amendment 1)
                    d["P0"] = None
                    d["anchor"] = "runtime: run_group.py anchor_grid from the smoke-pilot2 runs of the main batch"
                    for s_ in d["settings"]:
                        s_["targets"] = [0] * len(s_["targets"])
                    print(f"{k}: runtime anchor")
                    continue
                d["anchor"] = "ad.py anchor (smoke01/smoke02 pilots)"
                d["P0"] = out[k]["P0"]
                d["F_pilot"] = out[k]["F_pilot"]
                for s in d["settings"]:
                    s["targets"] = out[k]["targets"]["S0" if s["setting"] == "S0" else "S1S2"]
        json.dump(grid, open(GRID_PATH, "w"), indent=1)
        print(f"wrote anchored targets into {GRID_PATH}")


# ======================================================================================================== T1
def cmd_t1(a):
    """T1 (registered retrodiction). Fit s-/s+ on E5's 30 ASAP7 grid runs only (F per setting from those grid runs
    alone), then predict each of E5's 16 rebuild runs at its actual target R: claim C^ = F + s (R - F), s = s- if
    R < F else s+; pass/fail: pass iff C^ <= R (equivalently R >= F, for s < 1). Pass: >= 13 of 16 pass/fail calls
    right AND median |C^ - C| / C <= 3%. A rebuild of a setting without an interpolated grid F gets no prediction and
    counts as a wrong call (its claim error is left out of the median)."""
    e5 = json.load(open(E5_ANALYSIS))
    runs = e5["runs"]
    for t, r in runs.items():
        r.setdefault("platform", "asap7")
        r["vars"] = r.get("vars") or {}
    grid = [r for t, r in runs.items() if t.startswith("e5g-")]
    reb = [r for t, r in sorted(runs.items()) if t.startswith("e5k-")]
    assert len(grid) == 30 and len(reb) == 16, (len(grid), len(reb))
    SF = settings_F(grid)
    pts = law_points(SF)
    law = fit_law(pts)
    rows = []
    for r in reb:
        k = setting_key(r)
        F, how, _ = SF.get(k, (None, "no grid runs", []))
        R = float(r["period"])
        row = {"tag": r["tag"], "design": r["design"], "setting": r["setting"], "R": R, "C": r["claim"],
               "pass": r["pass"], "F_grid": F, "F_how": how}
        if F is None or how != "interpolated":
            row.update(pred_claim=None, pred_pass=None, call_right=False, claim_err=None)
        else:
            s = law["s_minus"] if R < F else law["s_plus"]
            C_hat = F + s * (R - F)
            pp = C_hat <= R
            row.update(s_used=s, pred_claim=C_hat, pred_pass=pp, call_right=(pp == bool(r["pass"])),
                       claim_err=abs(C_hat - r["claim"]) / r["claim"])
        # baselines (reported beside): the winner's own claim, and "every rebuild passes"
        rows.append(row)
    right = sum(1 for x in rows if x["call_right"])
    errs = [x["claim_err"] for x in rows if x["claim_err"] is not None]
    med = st.median(errs) if errs else None
    verdict = "PASS" if (right >= 13 and med is not None and med <= 0.03) else "FAIL"
    # baselines beside (no criterion): the claim itself (each rebuild's claim forecast as its chain winner's claim
    # C0, and every rebuild at or above C0 called a pass, which is what the claim asserts); all-fail calls
    c0 = {}
    for c in e5["primary"]["chains"]:
        for k in range(1, 5):
            c0[f"{c['chain_id']}-{k}"] = c["C0"]
    for x in rows:
        x["C0"] = c0.get(x["tag"])
        x["claim_baseline_err"] = None if x["C0"] is None else abs(x["C0"] - x["C"]) / x["C"]
        x["claim_baseline_call_right"] = (x["R"] >= (x["C0"] or 0)) == bool(x["pass"])
    base_allfail = sum(1 for x in rows if not x["pass"])
    berrs = [x["claim_baseline_err"] for x in rows if x["claim_baseline_err"] is not None]
    out = {"law": law, "settings": {k: {"F": v[0], "how": v[1], "targets": sorted({r["period"] for r in v[2]})}
                                    for k, v in SF.items()},
           "points": pts, "rebuilds": rows, "calls_right": right, "n": len(rows), "median_claim_error": med,
           "verdict": verdict, "baseline_all_fail_calls_right": base_allfail,
           "baseline_all_pass_calls_right": len(rows) - base_allfail,
           "baseline_claim_calls_right": sum(1 for x in rows if x["claim_baseline_call_right"]),
           "baseline_claim_median_error": st.median(berrs) if berrs else None}
    json.dump(out, open(a.out, "w"), indent=1, default=float)
    print(f"T1 law on 30 grid runs: s- {law['s_minus']:.3f} (n {law['n_minus']}), s+ {law['s_plus']:.3f} "
          f"(n {law['n_plus']}); interpolated settings {sum(1 for v in SF.values() if v[1] == 'interpolated')}/"
          f"{len(SF)}")
    for x in rows:
        pc = "-" if x["pred_claim"] is None else f"{x['pred_claim']:.1f}"
        ce = "-" if x["claim_err"] is None else f"{100 * x['claim_err']:.1f}%"
        print(f"  {x['tag']:14s} {x['setting']} R={x['R']:.0f} F={x['F_grid'] if x['F_grid'] is None else round(x['F_grid'], 1)}"
              f" C={x['C']:.1f} C^={pc} err={ce} pass={x['pass']} pred={x['pred_pass']} right={x['call_right']}")
    print(f"T1: calls right {right}/16 (need >= 13); median claim error "
          f"{'-' if med is None else f'{100 * med:.2f}%'} (need <= 3%) -> {verdict}")
    bm = out["baseline_claim_median_error"]
    print(f"beside: the claim itself: calls right {out['baseline_claim_calls_right']}/16, median claim error "
          f"{'-' if bm is None else f'{100 * bm:.2f}%'}; all-fail calls right {base_allfail}/16")


# ======================================================================================================== T2, T3, D
def cmd_analyze(a):
    R = all_runs(a.results)
    R = {t: r for t, r in R.items() if not t.startswith("smoke-")}
    for t, r in R.items():
        j = adlib._load(os.path.join(a.results, t, "job.json"), {}) or {}
        r["vars"] = j.get("vars") or {}
        r["arm"] = j.get("arm")
    out = {"n_runs": len(R)}

    def arm_runs(prefixes):
        return [r for t, r in R.items() if t.startswith(prefixes)]

    def law_block(runs, label):
        SF = settings_F(runs)
        pts = law_points(SF)
        law = fit_law(pts)
        per = {}
        for d in sorted({p["design"] for p in pts}):
            per[d] = fit_law([p for p in pts if p["design"] == d])
        return {"label": label, "n_runs": len(runs), "n_with_claim": sum(1 for r in runs if r["claim"] is not None),
                "settings": {k: {"F": v[0], "how": v[1]} for k, v in SF.items()},
                "interpolated_settings": sum(1 for v in SF.values() if v[1] == "interpolated"),
                "law": law, "per_design": per, "bins": bins_of(pts), "points": pts}

    # ---- T2a: ORFS on sky130hd, the 30 grid runs (primary); with chains beside
    s_grid = arm_runs(("ads-",))
    s_all = s_grid + arm_runs(("adsk-",))
    t2a = law_block(s_grid, "T2a sky130hd grid")
    sm = t2a["law"]["s_minus"]
    sp = t2a["law"]["s_plus"]
    if sm is None or sp is None:
        v = "not computable (a side has no points)"
    elif sm <= 0.35 and sp >= 0.45:
        v = "PREDICTION HELD (flow: s- <= 0.35 and s+ >= 0.45)"
    elif sm >= 0.45:
        v = "NODE, NOT FLOW (s- >= 0.45)"
    else:
        v = "NEITHER (prediction not met; s- below 0.45)"
    t2a["verdict"] = v if len(s_grid) >= 30 else f"PARTIAL ({len(s_grid)} of 30 grid runs landed): {v}"
    t2a["with_chains"] = {k: v for k, v in law_block(s_all, "T2a sky130hd grid + chains").items() if k != "points"}
    out["T2a"] = t2a
    # ---- T2b: ORFS on ASAP7 with ABC told the clock, the 30 grid runs
    b_grid = arm_runs(("adb-",))
    t2b = law_block(b_grid, "T2b asap7 ABC -D grid")
    sm = t2b["law"]["s_minus"]
    if sm is None:
        v = "not computable"
    elif sm >= 0.35:
        v = "PREDICTION HELD (synthesis: s- >= 0.35)"
    elif sm < 0.30:
        v = "NOT SYNTHESIS (s- < 0.30)"
    else:
        v = "INCONCLUSIVE (0.30 <= s- < 0.35)"
    t2b["verdict"] = v if len(b_grid) >= 30 else f"PARTIAL ({len(b_grid)} of 30 grid runs landed): {v}"
    t2b["abc_d_evidence"] = {r["tag"]: {"log_hits": r.get("abc_d_log_hits"), "synth_sha1": r.get("synth_sha1"),
                                        "synth_cells": r.get("synth_cells"), "synth_area": r.get("synth_area_um2")}
                             for r in b_grid}
    # registered check: the patch reached ABC (log) and, per design, whether the mapped netlist varied with the target
    per_design = {}
    for d in sorted({r["design"] for r in b_grid}):
        rs = [r for r in b_grid if r["design"] == d]
        shas = {r.get("synth_sha1") for r in rs if r.get("synth_sha1") not in (None, "none")}
        per_design[d] = {"runs": len(rs), "log_hits_all": all((r.get("abc_d_log_hits") or 0) >= 1 for r in rs),
                         "distinct_netlists": len(shas),
                         "note": ("patch ran but ABC's mapping did not depend on the target"
                                  if len(shas) == 1 else "netlist varied with the target")}
    t2b["netlist_check"] = per_design
    out["T2b"] = t2b
    # ---- control (descriptive): ASAP7 gcd/aes through Yosys without the clock
    c_grid = arm_runs(("adc-",))
    if c_grid:
        out["control"] = {k: v for k, v in law_block(c_grid, "control asap7 Yosys no -D").items()}
        out["control"]["synth"] = {r["tag"]: {"synth_sha1": r.get("synth_sha1"), "synth_cells": r.get("synth_cells")}
                                   for r in c_grid}
    # ---- E5 baseline beside (grid only and grid + chains), from the committed E5 record
    e5 = json.load(open(E5_ANALYSIS))
    e5r = []
    for t, r in e5["runs"].items():
        r = dict(r, platform="asap7", vars=r.get("vars") or {})
        e5r.append(r)
    out["E5_baseline"] = {"grid": {k: v for k, v in law_block([r for r in e5r if r["tag"].startswith("e5g-")],
                                                                 "E5 asap7 grid").items() if k != "points"},
                          "grid_and_chains": {k: v for k, v in law_block(e5r, "E5 asap7 grid + chains").items()
                                              if k != "points"}}
    # ---- D: first rebuilds of the new winners (sky130hd and GT2N), and the sky130hd tight bin
    chains = {}
    cdir = os.path.join(a.results, "chains")
    for f in sorted(os.listdir(cdir)) if os.path.isdir(cdir) else []:
        c = adlib._load(os.path.join(cdir, f))
        if c and c.get("chain_id", "").startswith(("adsk-", "adgk-")):
            chains[c["chain_id"]] = c
    prim = []
    for cid, c in sorted(chains.items()):
        w = c["winner"]
        stp = c["chain"]
        first = stp[1] if len(stp) > 1 else dict(stp[0], first_is_winner=True)
        c1 = first.get("claim")
        prim.append({"chain_id": cid, "platform": c.get("platform"), "design": c["design"], "winner": w["tag"],
                     "T0": w["period"], "C0": w["claim"], "R1": first["period"], "first_pass": bool(first.get("pass")),
                     "first_is_winner": bool(first.get("first_is_winner")), "C1": c1,
                     "d1": (c1 / w["claim"] - 1) if (c1 is not None and w["claim"]) else None,
                     "kept": c.get("kept_clock"),
                     "chain": [(s["period"], s.get("claim"), s.get("pass")) for s in stp]})
    n = len(prim)
    fails = sum(1 for p in prim if not p["first_pass"])
    sky_all = law_block(s_all, "D sky130hd grid + chains (E5's S1 method)")
    tight = sky_all["bins"]["tight (<0.9)"]
    if tight["n"] < 3 or tight["median"] is None:
        tv = "insufficient (tight bin has fewer than 3 points)"
    else:
        tv = ("NEARER ASAP7 (median > -10.05%)" if tight["median"] > -0.1005 else
              "NEARER LIBRELANE (median <= -10.05%)")
    d_first = None if n == 0 else fails / n
    out["D"] = {"chains": prim, "n_winners": n, "first_rebuild_fails": fails, "fail_fraction": d_first,
                "first_rebuild_verdict": None if n == 0 else (
                    "PREDICTION HELD (>= 55% fail)" if d_first >= 0.55 else "PREDICTION FAILED (< 55% fail)"),
                "sky130hd_tight_bin": tight, "tight_verdict": tv,
                "sky130hd_bins": sky_all["bins"],
                "gt2n": {k: v for k, v in law_block(arm_runs(("adg-", "adgk-")), "D gt2n grid + chains").items()
                         if k != "points"},
                "registered_count": "15 winners if every chain started (sky130hd 9, gt2n 6)"}
    # ---- T3: re-time judge on the 9 replayed ASAP7 winners
    t3 = []
    for t, r in sorted(R.items()):
        if not t.startswith("adr-"):
            continue
        orig = None
        j = adlib._load(os.path.join(a.results, t, "job.json"), {}) or {}
        rt = r.get("retime") or {}
        row = {"tag": t, "design": r["design"], "T0": r["period"], "ws": r["ws"], "hold": r["hold_ws"],
               "drc": r["drc"], "retime": rt}
        # replay check against E5's record of the same setting at the same clock
        for et, er in e5["runs"].items():
            if et.startswith("e5g-") and er["design"] == r["design"] and er["period"] == r["period"] and \
                    (er.get("vars") or {}) == (r.get("vars") or {}):
                orig = er
        if orig:
            row["replay_of"] = orig["tag"]
            row["replay_identical"] = (r["ws"] is not None and abs(r["ws"] - orig["ws"]) < 0.01 and
                                       abs(r["hold_ws"] - orig["hold_ws"]) < 0.01)
        ok = (isinstance(rt, dict) and isinstance(rt.get("tstar_value"), (int, float)) and
              isinstance(rt.get("tstar"), dict) and isinstance(rt.get("t0"), dict))
        if ok:
            t0m, tsm = rt["t0"], rt["tstar"]
            row["t0_reproduces_flow"] = (t0m.get("ws_all") is not None and r["ws"] is not None and
                                         abs(t0m["ws_all"] - r["ws"]) < 0.01 and
                                         abs(t0m["hold_ws_all"] - r["hold_ws"]) < 0.01)
            row["Tstar"] = rt["tstar_value"]
            row["ws_at_Tstar"] = tsm.get("ws_all")
            row["hold_at_Tstar"] = tsm.get("hold_ws_all")
            row["pass_at_Tstar"] = (row["t0_reproduces_flow"] and tsm.get("ws_all") is not None and tsm["ws_all"] >= 0 and
                                    tsm.get("hold_ws_all") is not None and tsm["hold_ws_all"] >= 0 and
                                    r["drc"] is not None and int(r["drc"]) == 0)
        else:
            row["pass_at_Tstar"] = False
            row["note"] = "no re-time result"
        t3.append(row)
    n3 = len(t3)
    p3 = sum(1 for x in t3 if x["pass_at_Tstar"])
    aes_s0 = next((x for x in t3 if x.get("replay_of") == "e5g-aes-001"), None)
    aes_ok = bool(aes_s0 and aes_s0.get("Tstar") == 385 and aes_s0.get("pass_at_Tstar"))
    v3 = None if n3 == 0 else ("PREDICTION HELD (>= 8 of 9 pass and aes S0 meets 385 ps)"
                                if (p3 >= 8 and aes_ok) else "PREDICTION FAILED")
    if 0 < n3 < 9 and v3 == "PREDICTION FAILED" and p3 + (9 - n3) >= 8 and (aes_ok or aes_s0 is None):
        v3 = f"INCOMPLETE ({n3} of 9 landed; not yet decided)"
    out["T3"] = {"rows": t3, "n": n3, "pass": p3, "aes_S0_265_meets_385": aes_ok, "verdict": v3}
    json.dump(out, open(a.out, "w"), indent=1, default=float)
    f3 = (lambda x: "-" if x is None else f"{x:.3f}")
    print(f"T2a sky130hd grid: s- {f3(out['T2a']['law']['s_minus'])} (n {out['T2a']['law']['n_minus']}), "
          f"s+ {f3(out['T2a']['law']['s_plus'])} (n {out['T2a']['law']['n_plus']}), interpolated settings "
          f"{out['T2a']['interpolated_settings']} -> {out['T2a']['verdict']}")
    print(f"T2b asap7 -D grid:  s- {f3(out['T2b']['law']['s_minus'])} (n {out['T2b']['law']['n_minus']}), "
          f"s+ {f3(out['T2b']['law']['s_plus'])} (n {out['T2b']['law']['n_plus']}), interpolated settings "
          f"{out['T2b']['interpolated_settings']} -> {out['T2b']['verdict']}")
    print(f"T2b netlist check: {out['T2b']['netlist_check']}")
    print(f"D: first rebuilds failed {fails}/{n} -> {out['D']['first_rebuild_verdict']}; sky130hd tight bin "
          f"{tight} -> {tv}")
    print(f"T3: {p3}/{n3} pass at the corrected claim; aes S0 (265 ps layout) meets 385 ps: {aes_ok} -> "
          f"{out['T3']['verdict']}")


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("plan", "collect", "table", "anchor", "t1", "analyze"):
        p = sub.add_parser(name)
        p.add_argument("--results", default=DEFAULT_RESULTS)
        p.add_argument("--prefix", default=None)
        p.add_argument("--batch", default=None)
        p.add_argument("--what", default="main", choices=("smoke", "main"))
        p.add_argument("--run-id", default=None)
        p.add_argument("--apply", action="store_true", help="anchor: write the targets into grid.json")
        p.add_argument("--runtime-anchor", default="", help="plan: platform/design list anchored on the runner")
        p.add_argument("--out", default=os.path.join(DEFAULT_RESULTS, f"ad_{name}.json"))
    a = ap.parse_args()
    if a.cmd in ("t1", "analyze", "anchor"):
        os.makedirs(os.path.dirname(a.out), exist_ok=True)
    {"plan": cmd_plan, "collect": cmd_collect, "table": cmd_table, "anchor": cmd_anchor, "t1": cmd_t1,
     "analyze": cmd_analyze}[a.cmd](a)


if __name__ == "__main__":
    main()
