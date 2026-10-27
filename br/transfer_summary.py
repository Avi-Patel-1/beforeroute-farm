#!/usr/bin/env python3
"""Condense transfer_gf180.py's summary.json into the headline tables (markdown on stdout).

Usage: transfer_summary.py <out dir of transfer_gf180.py> [--feature-set base]
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np


def f(x, pct=True, nd=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "-"
    return f"{100 * x:.{nd}f}%" if pct else f"{x:.3f}"


def mean(lst, key):
    v = [x.get(key) for x in lst if x.get(key) is not None]
    return (float(np.mean(v)), float(np.min(v)), float(np.max(v)), len(v)) if v else (None, None, None, 0)


def extension_tables(S, fs="port"):
    """Per design + mean: catch-95 and PR-AUC of zero-shot (and k=all adaptation if present) vs estimate, R8, perfect;
    per-run wins/losses of zero-shot against the estimate and against R8 (catch-95, lower wins; PR-AUC, higher wins)."""
    L = []
    designs = S["designs"]
    arms = S["arms"].get(fs, {})
    proto = S.get("protocol", "?")
    L.append(f"Protocol: {proto}; feature set: {fs}; signal nets; per held-out design pooled over its runs.\n")
    head = "| GF180 design | runs | violator rate | perfect catch95 | est catch95 | R8 catch95 | zero-shot catch95 | est PR-AUC | R8 PR-AUC | zero-shot PR-AUC |"
    extra = [arm for arm in ("ft", "merge") if any("all" in (arms.get(d, {}).get(arm) or {}) for d in designs)]
    for arm in extra:
        head += f" {arm} k=all catch95 / PR-AUC |"
    L.append(head)
    L.append("|---" * (10 + len(extra)) + "|")
    acc = {k: [] for k in ("rate", "perf", "est", "r8", "zs", "est_pr", "r8_pr", "zs_pr")}
    acc_x = {arm: ([], []) for arm in extra}
    wins = {"est_c": [0, 0, 0], "r8_c": [0, 0, 0], "est_p": [0, 0, 0], "r8_p": [0, 0, 0]}  # win, loss, tie
    per_run_rows = []
    for d in designs:
        x = S["describe"][d]
        b = S["baselines"][d]
        zs = ((arms.get(d, {}).get("zs") or {}).get("0") or [{}])[0]
        rate = x["violator_rate"]
        vals = dict(rate=rate, perf=0.95 * rate, est=b["est_load_slew_ratio"].get("frac_to_catch_95"),
                    r8=b["R8"].get("frac_to_catch_95"), zs=zs.get("frac_to_catch_95"),
                    est_pr=b["est_load_slew_ratio"].get("pr_auc"), r8_pr=b["R8"].get("pr_auc"), zs_pr=zs.get("pr_auc"))
        for k, v in vals.items():
            if v is not None:
                acc[k].append(v)
        row = (f"| {d} | {x['runs']} | {f(rate)} | {f(vals['perf'])} | {f(vals['est'])} | {f(vals['r8'])} | {f(vals['zs'])} | "
               f"{f(vals['est_pr'], False)} | {f(vals['r8_pr'], False)} | {f(vals['zs_pr'], False)} |")
        for arm in extra:
            r = ((arms.get(d, {}).get(arm) or {}).get("all") or [{}])[0]
            row += f" {f(r.get('frac_to_catch_95'))} / {f(r.get('pr_auc'), False)} |"
            if r.get("frac_to_catch_95") is not None:
                acc_x[arm][0].append(r["frac_to_catch_95"])
                acc_x[arm][1].append(r["pr_auc"])
        L.append(row)
        est_r = {p["run"]: p for p in b["est_load_slew_ratio"].get("per_run", [])}
        r8_r = {p["run"]: p for p in b["R8"].get("per_run", [])}
        for p in zs.get("per_run", []):
            e, r = est_r.get(p["run"], {}), r8_r.get(p["run"], {})
            for key, other, m, better in (("est_c", e, "frac_to_catch_95", -1), ("r8_c", r, "frac_to_catch_95", -1),
                                          ("est_p", e, "pr_auc", 1), ("r8_p", r, "pr_auc", 1)):
                if p.get(m) is None or other.get(m) is None:
                    continue
                dlt = (p[m] - other[m]) * better
                wins[key][0 if dlt > 1e-9 else (1 if dlt < -1e-9 else 2)] += 1
            rate_r = p["positives"] / p["n"] if p.get("n") else None
            per_run_rows.append(f"| {p['run']} | {f(rate_r)} | {f(0.95 * rate_r if rate_r else None)} | {f(e.get('frac_to_catch_95'))} | "
                                f"{f(r.get('frac_to_catch_95'))} | {f(p.get('frac_to_catch_95'))} | {f(e.get('pr_auc'), False)} | "
                                f"{f(r.get('pr_auc'), False)} | {f(p.get('pr_auc'), False)} |")
    mrow = (f"| **mean of {len(designs)}** | | {f(np.mean(acc['rate']))} | {f(np.mean(acc['perf']))} | {f(np.mean(acc['est']))} | "
            f"{f(np.mean(acc['r8']))} | **{f(np.mean(acc['zs']))}** | {f(np.mean(acc['est_pr']), False)} | {f(np.mean(acc['r8_pr']), False)} | "
            f"**{f(np.mean(acc['zs_pr']), False)}** |")
    for arm in extra:
        c, p = acc_x[arm]
        mrow += f" {f(np.mean(c)) if c else '-'} / {f(np.mean(p), False) if p else '-'} |"
    L.append(mrow)
    L.append("")
    n = sum(wins["est_c"])
    L.append(f"Per-run wins / losses / ties of zero-shot ({n} runs): catch-95 vs estimate {wins['est_c'][0]} / {wins['est_c'][1]} / {wins['est_c'][2]}; "
             f"vs R8 {wins['r8_c'][0]} / {wins['r8_c'][1]} / {wins['r8_c'][2]}; PR-AUC vs estimate {wins['est_p'][0]} / {wins['est_p'][1]} / {wins['est_p'][2]}; "
             f"vs R8 {wins['r8_p'][0]} / {wins['r8_p'][1]} / {wins['r8_p'][2]}.\n")
    L.append("| run | violator rate | perfect catch95 | est catch95 | R8 catch95 | zero-shot catch95 | est PR-AUC | R8 PR-AUC | zero-shot PR-AUC |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    L.extend(per_run_rows)
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("--results", default=None, help="farm results dir: also print the per-run table (knobs, nets, violators)")
    ap.add_argument("--extension", action="store_true",
                    help="compact table: mean catch-95 / PR-AUC of zero-shot vs estimate vs R8 vs perfect, per-run wins/losses")
    ap.add_argument("--from-cache", default=None,
                    help="rebuild the arm results from <out>/cache for these feature sets (e.g. port), for the run sets in "
                         "summary.json; prefix 'strict_' entries are reported as separate arms")
    a = ap.parse_args()
    S = json.load(open(os.path.join(a.out, "summary.json")))
    designs = S["designs"]
    if a.from_cache:
        import glob
        import re
        import zlib

        S["arms"] = {}
        for d in designs:
            lp = os.path.join(a.out, "cache", f"sky130_lodo_{d}.json")
            if os.path.exists(lp):
                S.setdefault("sky130_lodo", {})[d] = json.load(open(lp))
        for fs in a.from_cache.split(","):
            for d in designs:
                tsig = f"{zlib.crc32('|'.join(S['runs'][d]).encode()):08x}"
                A = S["arms"].setdefault(fs, {}).setdefault(d, {})
                for p in sorted(glob.glob(os.path.join(a.out, "cache", f"*{fs}_*_{d}_*{tsig}*.json"))):
                    key = os.path.basename(p)[:-5]
                    m = re.match(rf"^(strict_)?{fs}_(zs|gfonly|merge|mergew|ft)_{re.escape(d)}_(?:k(\w+?)_)?(?:r(\d+)_)?{tsig}(?:_[0-9a-f]{{8}})?$", key)
                    if not m:
                        continue
                    strict, arm, k, _r = m.groups()
                    k = "0" if arm == "zs" else k
                    A.setdefault(("strict_" if strict else "") + arm, {}).setdefault(k, []).append(json.load(open(p)))
    L = []
    if a.extension:
        print(extension_tables(S))
        return 0
    if a.results:
        import glob

        L.append("### GF180 runs\n")
        L.append("| run | status | util / density | clock (ns) | max tran (ns) | flow (s) | nets | violating nets | rate | setup WS (ns) | route DRC |")
        L.append("|---|---|---|---|---|---|---|---|---|---|---|")
        for jp in sorted(glob.glob(os.path.join(a.results, "g1-*", "job.json"))):
            rd = os.path.dirname(jp)
            j = json.load(open(jp))
            ov = j.get("overrides", {})
            lab = os.path.join(rd, "labels.json")
            met = os.path.join(rd, "metrics.json")
            s = json.load(open(lab))["summary"] if os.path.exists(lab) else {}
            m = json.load(open(met)) if os.path.exists(met) else {}
            nt, nv = s.get("nets_total"), s.get("nets_violating")
            ws = m.get("timing__setup__ws")
            L.append(f"| {j['tag']} | {j.get('status')} | {ov.get('FP_CORE_UTIL')} / {ov.get('PL_TARGET_DENSITY_PCT')} | {ov.get('CLOCK_PERIOD')} | "
                     f"{ov.get('MAX_TRANSITION_CONSTRAINT')} | {j.get('flow_seconds')} | {nt} | {nv} | {f(nv / nt if nt else None)} | "
                     f"{'-' if ws is None else f'{ws:.1f}'} | {m.get('route__drc_errors', '-')} |")
        L.append("")
    L.append("### Zero-shot: sky130-trained model on GF180 (signal nets; per held-out design, pooled over its runs)\n")
    L.append("| GF180 design | runs | violator rate | perfect ranker: catch 95% at | est-slew: catch 95% / R@5% / PR-AUC | R8: catch 95% / R@5% / PR-AUC | "
             + " | ".join(f"zero-shot [{fs}]: catch 95% / R@5% / PR-AUC" for fs in S["arms"]) + " |")
    L.append("|---|---|---|---|---|---|" + "---|" * len(S["arms"]))
    for d in designs:
        x = S["describe"][d]
        b = S["baselines"][d]
        cells = [d, str(x["runs"]), f(x["violator_rate"]), f(0.95 * x["violator_rate"])]
        for m in (b["est_load_slew_ratio"], b["R8"]):
            cells.append(f"{f(m.get('frac_to_catch_95'))} / {f(m.get('recall@5%'))} / {f(m.get('pr_auc'), False)}")
        for fs, byd in S["arms"].items():
            zs = (byd.get(d, {}).get("zs") or {}).get("0")
            m = zs[0] if zs else {}
            cells.append(f"{f(m.get('frac_to_catch_95'))} / {f(m.get('recall@5%'))} / {f(m.get('pr_auc'), False)}")
        L.append("| " + " | ".join(cells) + " |")
    L.append("")
    if S.get("sky130_lodo"):
        L.append("### Reference: same designs held out within sky130 (base features)\n")
        L.append("| sky130 design | violator rate | perfect: catch 95% at | model: catch 95% / R@5% / PR-AUC | est-slew: catch 95% / R@5% / PR-AUC | R8: catch 95% / R@5% / PR-AUC |")
        L.append("|---|---|---|---|---|---|")
        for d, m in S["sky130_lodo"].items():
            r = m.get("base_rate")
            b, r8 = m["baseline_est_load_slew_ratio"], m["baseline_R8"]
            L.append(f"| {d} | {f(r)} | {f(0.95 * r if r else None)} | {f(m.get('frac_to_catch_95'))} / {f(m.get('recall@5%'))} / {f(m.get('pr_auc'), False)} | "
                     f"{f(b.get('frac_to_catch_95'))} / {f(b.get('recall@5%'))} / {f(b.get('pr_auc'), False)} | "
                     f"{f(r8.get('frac_to_catch_95'))} / {f(r8.get('recall@5%'))} / {f(r8.get('pr_auc'), False)} |")
        L.append("")
    L.append("### Zero-shot per GF180 run (signal nets)\n")
    fss = list(S["arms"])
    L.append("| run | violators / nets | perfect catch 95% | est-slew catch 95% / R@5% | R8 catch 95% / R@5% | "
             + " | ".join(f"zero-shot [{fs}] catch 95% / R@5% / PR-AUC" for fs in fss) + " |")
    L.append("|---|---|---|---|---|" + "---|" * len(fss))
    for d in designs:
        b = S["baselines"][d]
        est = {x["run"]: x for x in b["est_load_slew_ratio"].get("per_run", [])}
        r8 = {x["run"]: x for x in b["R8"].get("per_run", [])}
        zs = {fs: {x["run"]: x for x in ((S["arms"][fs].get(d, {}).get("zs") or {}).get("0") or [{}])[0].get("per_run", [])} for fs in fss}
        for run in sorted(est):
            e, r = est[run], r8.get(run, {})
            rate = e["positives"] / e["n"] if e.get("n") else None
            cells = [run, f"{e['positives']} / {e['n']}", f(0.95 * rate if rate else None),
                     f"{f(e.get('frac_to_catch_95'))} / {f(e.get('recall@5%'))}", f"{f(r.get('frac_to_catch_95'))} / {f(r.get('recall@5%'))}"]
            for fs in fss:
                z = zs[fs].get(run, {})
                cells.append(f"{f(z.get('frac_to_catch_95'))} / {f(z.get('recall@5%'))} / {f(z.get('pr_auc'), False)}")
            L.append("| " + " | ".join(cells) + " |")
    L.append("")
    L.append("### Blind spot: violators the pre-route estimate called clean (estimated worst load slew ratio <= 1)\n")
    L.append("| design | GF180 blind spot | GF180 violators | sky130 blind spot (same design) | sky130 violator rate |")
    L.append("|---|---|---|---|---|")
    for d in designs:
        x = S["describe"][d]
        sk = S["describe_sky130"].get(d, {})
        L.append(f"| {d} | {f(x['blind_spot_load'])} | {x['violators']} | {f(sk.get('blind_spot_load'))} | {f(sk.get('violator_rate'))} |")
    L.append("")
    for fs, byd in S["arms"].items():
        for key, label in (("frac_to_catch_95", "nets flagged to catch 95% (lower is better)"), ("recall@5%", "recall @ 5% flagged"), ("pr_auc", "PR-AUC")):
            ks = sorted({k for d in designs for arm in byd.get(d, {}).values() for k in arm}, key=lambda k: (k == "all", int(k) if k != "all" else 0))
            L.append(f"### Adaptation curve [{fs} features]: {label}; per held-out design, mean over draws (min-max)\n")
            L.append("| held-out | arm | " + " | ".join(f"k={k}" for k in ks) + " |")
            L.append("|---|---|" + "---|" * len(ks))
            for d in designs:
                A = byd.get(d, {})
                for arm, lab in (("zs", "zero-shot"), ("gfonly", "GF180-only"), ("merge", "merge"), ("mergew", "merge (re-weighted)"),
                                 ("ft", "fine-tune"), ("strict_zs", "zero-shot, strict"), ("strict_ft", "fine-tune, strict")):
                    if arm not in A:
                        continue
                    cells = []
                    for k in ks:
                        mu, lo, hi, n = mean(A[arm].get(k, []), key)
                        pct = key != "pr_auc"
                        if mu is None:
                            cells.append("")
                        elif n == 1:
                            cells.append(f(mu, pct))
                        else:
                            cells.append(f"{f(mu, pct)} ({f(lo, pct)}-{f(hi, pct)})")
                    L.append(f"| {d} | {lab} | " + " | ".join(cells) + " |")
            L.append("")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
