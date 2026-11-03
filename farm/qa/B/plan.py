#!/usr/bin/env python3
"""Workstream B (constraint hygiene, "is it just your SDC?"): the registered plan tables. Reads the landed record only
(no runs). Writes farm/qa/B/plan.json; docs/qa_week/B_PREREG.md quotes it.

  python3 -I farm/qa/B/plan.py [--root /home/claude/eda] [--out farm/qa/B/plan.json]

Tables:
  fbest   per design: F_best = the fastest clock the design has closed in the record (smallest CLOCK_PERIOD of a full-flow
          run of designs/<design> in results/ that met setup and hold at all nine corners with router DRC 0), io0 = the
          design's shipped I/O fraction (IO_DELAY_CONSTRAINT/100: 0.20; clip16 designs 0.10), D = io0 * F_best (ns),
          and the record run that sets F_best.
  c2a     48 winners: the 8 Bayesian-tuned winners of Addenda 24/25 (A24d/A25d: each design's best feasible tuner run)
          and the 40 race winners of Addendum 35 (each race arm's best feasible run; farm/tune_a35.py arm_best).
  s       the 40 race winners again (D = 1.0 ns flat).
  c1      the 60 settings whose all-path fixed point is bracketed (agents/analysis/fixedpoint/data.json, "interpolated")
          and their 328 runs (one per distinct target).
  c3      the E5 ASAP7 grid (branch qa-e5-asap7 farm/qa/E5/grid.json), unchanged settings and targets.
  c2b     the 10 Addendum-35 races (5 designs x 2 seeds), plain TPE as arm b.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import statistics as st
from collections import defaultdict

DRV_KEYS = ("design__max_slew_violation__count", "design__max_cap_violation__count")
A24 = ["aes_cipher", "picorv32", "y_huff"]                      # farm/tune.py DESIGNS (PREFIX x1)
A25 = ["des", "md5", "bm64", "ocs_blitter", "blabla"]           # farm/tune_a25.py (PREFIX x2)
A35_DES = ["xtea", "cic_decimator", "zipdiv", "usb_cdc_core", "wbqspiflash"]   # farm/tune_a35.py DES
SEEDS, ARMS35 = [1, 2], ["b", "f", "g", "h"]
ORIGINAL_FAILURES = ["x1t-picorv32-014", "x1t-y_huff-005", "x2t-bm64-007"]    # FACTCHECK.md M1a


def J(p, default=None):
    try:
        return json.load(open(p))
    except Exception:
        return default


def ceil05(x):                                                  # farm/tune_a32.py ceil05
    return round(math.ceil(round(x / 0.05, 6)) * 0.05, 2)


def drv(m):
    return sum((m.get(k) or 0) for k in DRV_KEYS)


def design_of(job):
    return os.path.basename((job.get("design_dir") or "").rstrip("/"))


def fbest_table(root, designs):
    """F_best per design from every full-flow record run (job.json names designs/<design>; metrics landed)."""
    best = {}
    n_runs = defaultdict(int)
    for d in sorted(glob.glob(os.path.join(root, "results", "*", "job.json"))):
        job = J(d, {}) or {}
        des = design_of(job)
        if des not in designs:
            continue
        rd = os.path.dirname(d)
        m = J(os.path.join(rd, "metrics.json"))
        if not m:
            continue
        T = (job.get("overrides") or {}).get("CLOCK_PERIOD")
        if T is None:
            T = (J(os.path.join(rd, "resolved.json"), {}) or {}).get("CLOCK_PERIOD")
        ws, hs, drc = m.get("timing__setup__ws"), m.get("timing__hold__ws"), m.get("route__drc_errors")
        if T is None or ws is None or hs is None:
            continue
        n_runs[des] += 1
        if ws >= 0 and hs >= 0 and drc == 0:
            key = (float(T), os.path.basename(rd))
            if des not in best or key < best[des]:
                best[des] = key
    out = {}
    for des in sorted(designs):
        cfg = J(os.path.join(root, "designs", des, "config_sky130.json"), {}) or {}
        io0 = float(cfg.get("IO_DELAY_CONSTRAINT", 20)) / 100.0
        if des not in best:
            out[des] = {"F_best": None, "io0": io0, "D": None, "run": None, "record_runs": n_runs[des]}
            continue
        F, tag = best[des]
        out[des] = {"F_best": F, "io0": io0, "D": round(io0 * F, 6), "run": tag, "record_runs": n_runs[des],
                    "shipped_period": cfg.get("CLOCK_PERIOD")}
    return out


def bayes_winners(root):
    out = []
    for prefix, sf, des in (("x1", "results/tune/state.json", A24), ("x2", "results/tune_x2/state.json", A25)):
        stx = J(os.path.join(root, sf))["tags"]
        for d in des:
            mine = [dict(v, tag=t) for t, v in stx.items() if v["arm"] == "t" and v["design"] == d]
            ok = [v for v in mine if v.get("feasible") and v.get("teff") is not None]
            b = min(ok, key=lambda v: (v["teff"], v["tag"]))           # farm/tune.py confirm(): best feasible T_eff
            conf = sorted([dict(v, tag=t) for t, v in stx.items() if v["arm"] == "c" and v["design"] == d],
                          key=lambda v: v["tag"])
            c = conf[0] if conf else None
            ref = drv(J(os.path.join(root, "results", f"{prefix}d-{d}-001", "metrics.json"), {}))   # Amendment 24.1
            out.append({"set": "A24/A25 (Bayesian, TPE)", "design": d, "source": b["tag"],
                        "T0": float(b["overrides"]["CLOCK_PERIOD"]), "claim_orig": b["teff"], "drv_ref": ref,
                        "drv_ref_from": f"{prefix}d-{d}-001",
                        "orig_first_rebuild": c and {"tag": c["tag"], "clock": c["overrides"]["CLOCK_PERIOD"],
                                                     "wns": c.get("wns"), "feasible": c.get("feasible"),
                                                     "pass": bool(c.get("feasible") and (c.get("wns") or -1) >= 0)},
                        "original_failure": b["tag"] in ORIGINAL_FAILURES})
    return out


def race_winners(root):
    sx = J(os.path.join(root, "results", "tune_xa", "state.json"))["tags"]
    x6 = J(os.path.join(root, "results", "tune_x6", "state.json"))["tags"]

    def ref_x8(d):                                                    # farm/tune_a32.py ref_drv_x8
        ds = sorted(((v.get("frac", 1.0), t) for t, v in x6.items() if v["design"] == d and v["arm"] == "d"
                     and v.get("status") != "superseded"), key=lambda x: -x[0])
        for _, t in ds:
            m = J(os.path.join(root, "results", t, "metrics.json"), {}) or {}
            if m.get("timing__setup__ws") is not None:
                return drv(m), t
        return None, None

    out = []
    for d in A35_DES:
        ref, reft = ref_x8(d)
        for s in SEEDS:
            for x in ARMS35:
                rs = [dict(v, tag=t) for t, v in sorted(sx.items()) if v["design"] == d and v["arm"] == f"{x}{s}"]
                ok = [v for v in rs if v.get("feasible") and v.get("teff") is not None]
                b = min(ok, key=lambda v: v["teff"])                     # farm/tune_a35.py arm_best
                ks = sorted([dict(v, tag=t) for t, v in sx.items() if v["arm"] == "k" and v.get("source") == b["tag"]],
                            key=lambda v: v["tag"])
                cs = sorted([dict(v, tag=t) for t, v in sx.items() if v["arm"] == "c" and v.get("root") == b["tag"]],
                            key=lambda v: v["tag"])
                okc = [v for v in ks + cs if v.get("feasible") and v.get("wns") is not None and v["wns"] >= 0]
                first = ks[0] if ks else None
                out.append({"set": f"A35 race {x}{s}", "design": d, "source": b["tag"],
                            "T0": float(b["overrides"]["CLOCK_PERIOD"]), "claim_orig": b["teff"], "drv_ref": ref,
                            "drv_ref_from": reft,
                            "orig_first_rebuild": first and {"tag": first["tag"],
                                                             "clock": first["overrides"]["CLOCK_PERIOD"],
                                                             "wns": first.get("wns"), "feasible": first.get("feasible"),
                                                             "pass": bool(first.get("feasible") and
                                                                          (first.get("wns") or -1) >= 0)},
                            "orig_kept": min((v["overrides"]["CLOCK_PERIOD"] for v in okc), default=None),
                            "original_failure": False})
    return out


def c1_population(root):
    d = J(os.path.join(root, "agents", "analysis", "fixedpoint", "data.json"))
    G = [g for g in d["groups"] if g["F_emp_how"] == "interpolated"]
    rows = []
    for gi, g in enumerate(sorted(G, key=lambda g: (g["design"], g["tags"][0]))):
        byT = defaultdict(list)
        for p in g["points"]:
            byT[round(p["T"], 4)].append(p["tag"])
        for T in sorted(byT):
            src = sorted(byT[T])[0]                     # one run per distinct target (the first tag if repeated)
            rows.append({"setting": gi, "design": g["design"], "T": T, "source": src,
                         "F_stock": g["F_emp"], "repeats": len(byT[T])})
    return {"settings": len(G), "runs": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default="/home/claude/eda")
    ap.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "plan.json"))
    a = ap.parse_args()
    root = a.root
    c2a = bayes_winners(root) + race_winners(root)
    c1 = c1_population(root)
    designs = sorted({w["design"] for w in c2a} | {r["design"] for r in c1["runs"]})
    fb = fbest_table(root, set(designs))
    for w in c2a:
        f = fb[w["design"]]
        w["D"] = f["D"]
        w["io_pct_T0"] = round(100.0 * f["D"] / w["T0"], 6)
        w["spec"] = f"farm/jobs/{w['source']}.json"
    for r in c1["runs"]:
        f = fb[r["design"]]
        r["D"] = f["D"]
        r["io_pct"] = round(100.0 * f["D"] / r["T"], 6)
    e5 = None
    for p in ("/home/claude/qa/asap7/farm/qa/E5/grid.json",):
        e5 = J(p)
    out = {
        "about": __doc__,
        "fbest": fb,
        "c2a": c2a,
        "s": [dict(w, D=1.0, io_pct_T0=round(100.0 / w["T0"], 6)) for w in c2a if w["set"].startswith("A35")],
        "c1": c1,
        "c3": {"grid": e5, "rule": "clk_io_pct = 0.2 * P0 / T (P0 = the design's ORFS default period); the line is left "
                                   "untouched when T == P0"},
        "c2b": {"races": [{"design": d, "seed": s, "D": fb[d]["D"]} for d in A35_DES for s in SEEDS]},
    }
    json.dump(out, open(a.out, "w"), indent=1)
    # summary
    print("F_best / D per design:")
    for k, v in fb.items():
        print(f"  {k:20s} F_best {v['F_best']} ns ({v['run']}), io0 {v['io0']}, D {v['D']} ns, record runs {v['record_runs']}")
    print(f"C2a winners {len(c2a)} (Bayesian {sum(1 for w in c2a if not w['set'].startswith('A35'))}, race "
          f"{sum(1 for w in c2a if w['set'].startswith('A35'))}); original first-rebuild failures "
          f"{sum(1 for w in c2a if w['orig_first_rebuild'] and not w['orig_first_rebuild']['pass'])}")
    print(f"C1 settings {c1['settings']}, runs {len(c1['runs'])}")


if __name__ == "__main__":
    main()
