#!/usr/bin/env python3
"""Experiment E (Addendum 42) scorer. Committed before any rebuild is dispatched; definitions = docs/qa_week/E_PREREG.md.

Labels: <chains>/<erk-tag>/chain.json (the runner-side chain record; downloaded artifacts result-erk-*), matched to
packets through the private key (packet -> source) and farm/qa/E/chains.json (source -> chain tag).
Predictions: <pred>/<arm>/<packet_id>.json. Main arms are scored on the 35 main packets; control arms (rung2_rename,
rung2_shuffle) are matched to their main packet through the key and reported as differences only.

Per arm: false passes / predicted passes; missed passes / actual passes; abstentions; correct calls (abstain = not
correct); Brier = mean (p_pass - pass1)^2 over all sources; |slope error| median (primary) and mean; kept-clock relative
error over sources whose chain kept a clock (null prediction scores 1.0), median and p90 (nearest rank); kept-vs-none
agreement. A missing or invalid prediction counts as p_pass 0.5, call abstain, slope 0, kept null.
Comparisons: exact two-sided McNemar on per-source correctness (alpha 0.05) -> beats / ties / loses; kept clock:
median error lower by > 1 percentage point = beats, higher by > 1 point = loses, else ties.
Registered tests R1, R2, R3 as in the pre-registration. Also per family (equal-family medians).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import statistics as st
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import elib as E  # noqa: E402

MAIN = ["raw_claim", "law", "io_rule", "two_point", "handpicked", "rung1", "rung2", "rung3", "codex_det"]


def load_pred(path, C0, T0):
    try:
        p = json.load(open(path))
        pp = float(p["p_pass"])
        if not 0.0 <= pp <= 1.0:
            raise ValueError("p_pass")
        call = p.get("call")
        if call not in ("pass", "fail", "abstain"):
            raise ValueError("call")
        sl = p.get("slope")
        if sl is None and p.get("claim1_ns") is not None:
            sl = (float(p["claim1_ns"]) - C0) / (E.ceil05(C0) - T0)
        sl = float(sl)
        k = p.get("kept_clock_ns")
        k = None if k is None else float(k)
        return {"p_pass": pp, "call": call, "slope": sl, "kept": k, "valid": True}
    except Exception:
        return {"p_pass": 0.5, "call": "abstain", "slope": 0.0, "kept": None, "valid": False}


def nearest_rank(xs, q):
    xs = sorted(xs)
    if not xs:
        return None
    return xs[max(0, math.ceil(q * len(xs)) - 1)]


def mcnemar(a_ok, b_ok):
    b = sum(1 for x, y in zip(a_ok, b_ok) if x and not y)
    c = sum(1 for x, y in zip(a_ok, b_ok) if y and not x)
    n = b + c
    if n == 0:
        return b, c, 1.0
    k = min(b, c)
    p = 2 * sum(math.comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return b, c, min(1.0, p)


def verdict_pf(a_ok, b_ok):
    b, c, p = mcnemar(a_ok, b_ok)
    if p < 0.05 and b > c:
        return "beats", b, c, p
    if p < 0.05 and c > b:
        return "loses", b, c, p
    return "ties", b, c, p


def verdict_kept(ea, eb):
    if ea is None or eb is None:
        return "n/a"
    if ea < eb - 0.01:
        return "beats"
    if ea > eb + 0.01:
        return "loses"
    return "ties"


def score_arm(rows, preds):
    out = {"n": len(rows), "valid": sum(1 for r in rows if preds[r["pid"]]["valid"])}
    pp = [preds[r["pid"]] for r in rows]
    y = [r["pass1"] for r in rows]
    calls = [p["call"] for p in pp]
    out["predicted_passes"] = sum(1 for c in calls if c == "pass")
    out["false_passes"] = sum(1 for c, t in zip(calls, y) if c == "pass" and not t)
    out["actual_passes"] = sum(y)
    out["missed_passes"] = sum(1 for c, t in zip(calls, y) if c == "fail" and t)
    out["abstentions"] = sum(1 for c in calls if c == "abstain")
    ok = [(c == "pass" and t) or (c == "fail" and not t) for c, t in zip(calls, y)]
    out["correct"] = sum(ok)
    out["brier"] = sum((p["p_pass"] - (1.0 if t else 0.0)) ** 2 for p, t in zip(pp, y)) / len(rows)
    se = [abs(p["slope"] - r["slope"]) for p, r in zip(pp, rows) if r["slope"] is not None]
    out["slope_err_median"] = st.median(se) if se else None
    out["slope_err_mean"] = sum(se) / len(se) if se else None
    ke = []
    agree = 0
    for p, r in zip(pp, rows):
        if (p["kept"] is None) == (r["kept"] is None):
            agree += 1
        if r["kept"] is not None:
            ke.append(1.0 if p["kept"] is None else abs(p["kept"] - r["kept"]) / r["kept"])
    out["kept_err_median"] = st.median(ke) if ke else None
    out["kept_err_p90"] = nearest_rank(ke, 0.9)
    out["kept_n"] = len(ke)
    out["kept_vs_none_agree"] = agree
    fam = {}
    for p, r in zip(pp, rows):
        if r["slope"] is not None:
            fam.setdefault(r["family"], []).append(abs(p["slope"] - r["slope"]))
    out["slope_err_median_by_family"] = {f: st.median(v) for f, v in sorted(fam.items())}
    out["slope_err_equal_family"] = st.median([st.median(v) for v in fam.values()]) if fam else None
    return out, ok


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--chains", required=True, help="dir with <erk-tag>/chain.json")
    ap.add_argument("--key", required=True)
    ap.add_argument("--pred", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--chains-index", default=os.path.join(HERE, "chains.json"))
    a = ap.parse_args()
    key = json.load(open(a.key))
    chains = json.load(open(a.chains_index))["chains"]
    tag_of = {c["source"]: c["tag"] for c in chains}
    rows = []
    for pid, v in sorted(key["packets"].items()):
        if v["kind"] != "main":
            continue
        cp = os.path.join(a.chains, tag_of[v["source"]], "chain.json")
        if not os.path.exists(cp):
            print(f"[score] {pid} {v['source']}: chain not landed")
            continue
        c = json.load(open(cp))
        rows.append({"pid": pid, "source": v["source"], "family": v["design"], "T0": c["T0_ns"], "C0": c["C0_ns"],
                     "pass1": bool(c["first_pass"]), "slope": c["slope"], "kept": c["kept_clock_ns"],
                     "two_point": bool(v.get("has_second_point"))})
    res = {"n_landed": len(rows), "arms": {}, "tests": {}}
    oks = {}
    for arm in sorted(os.listdir(a.pred)):
        d = os.path.join(a.pred, arm)
        if not os.path.isdir(d) or arm.endswith("_rename") or arm.endswith("_shuffle"):
            continue
        sub = [r for r in rows if arm != "two_point" or r["two_point"]]
        preds = {r["pid"]: load_pred(os.path.join(d, r["pid"] + ".json"), r["C0"], r["T0"]) for r in sub}
        res["arms"][arm], ok = score_arm(sub, preds)
        oks[arm] = dict(zip([r["pid"] for r in sub], ok))
        if arm != "two_point":    # every arm also on the two-point subset (R1's third part)
            s2 = [r for r in rows if r["two_point"]]
            res["arms"][arm]["on_two_point_subset"] = score_arm(s2, {r["pid"]: preds[r["pid"]] for r in s2})[0]
    # controls: prediction differences against the main rung-2 prediction of the same source
    for ctl in ("rung2_rename", "rung2_shuffle"):
        d = os.path.join(a.pred, ctl)
        if not os.path.isdir(d):
            continue
        diffs = []
        for pid, v in key["packets"].items():
            if v["kind"] != ctl.split("_")[1]:
                continue
            main_pid = v["main_packet"]
            r = next((x for x in rows if x["pid"] == main_pid), None)
            if r is None:
                continue
            p1 = load_pred(os.path.join(a.pred, "rung2", main_pid + ".json"), r["C0"], r["T0"])
            p2 = load_pred(os.path.join(d, pid + ".json"), r["C0"], r["T0"])
            diffs.append({"main": main_pid, "control": pid, "d_p_pass": p2["p_pass"] - p1["p_pass"],
                          "same_call": p1["call"] == p2["call"], "d_slope": p2["slope"] - p1["slope"],
                          "slope_err_main": abs(p1["slope"] - r["slope"]) if r["slope"] is not None else None,
                          "slope_err_control": abs(p2["slope"] - r["slope"]) if r["slope"] is not None else None})
        res["controls_" + ctl] = diffs

    def common(x, y):
        ids = [i for i in oks.get(x, {}) if i in oks.get(y, {})]
        return [oks[x][i] for i in ids], [oks[y][i] for i in ids]
    A = res["arms"]
    if "rung1" in A and "law" in A:
        v_pf = verdict_pf(*common("rung1", "law"))
        v_k = verdict_kept(A["rung1"]["kept_err_median"], A["law"]["kept_err_median"])
        fp1 = A["rung1"]["on_two_point_subset"]["false_passes"]
        fp2 = A["two_point"]["false_passes"] if "two_point" in A else None
        part3 = fp2 is not None and fp1 > fp2
        res["tests"]["R1"] = {"pass_fail_vs_law": v_pf, "kept_vs_law": v_k,
                              "false_passes_rung1_on_19": fp1, "false_passes_two_point": fp2,
                              "holds": v_pf[0] in ("ties", "loses") and v_k in ("ties", "loses") and part3}
    if "rung2" in A and "rung1" in A and "law" in A:
        v21 = verdict_pf(*common("rung2", "rung1"))
        p_i = A["rung2"]["slope_err_median"] < A["rung1"]["slope_err_median"] and v21[0] != "loses"
        v2l = verdict_pf(*common("rung2", "law"))
        p_iii = A["rung2"]["slope_err_median"] <= 0.80 * A["law"]["slope_err_median"]
        res["tests"]["R2"] = {"i_beats_rung1": p_i, "pass_fail_vs_rung1": v21, "ii_pass_fail_vs_law": v2l,
                              "iii_slope_ratio_vs_law": A["rung2"]["slope_err_median"] / A["law"]["slope_err_median"]
                              if A["law"]["slope_err_median"] else None,
                              "holds": p_i and v2l[0] == "ties" and p_iii}
    if "rung3" in A and "law" in A and "handpicked" in A:
        r3 = A["rung3"]["slope_err_median"]
        res["tests"]["R3"] = {"slope_ratio_vs_law": r3 / A["law"]["slope_err_median"] if A["law"]["slope_err_median"] else None,
                              "beats_handpicked": r3 < A["handpicked"]["slope_err_median"],
                              "holds": r3 <= 0.75 * A["law"]["slope_err_median"] and r3 < A["handpicked"]["slope_err_median"]}
    json.dump(res, open(a.out, "w"), indent=1)
    print(f"[score] {len(rows)} sources landed")
    hdr = f"{'arm':14s} {'n':>3s} {'FP/pred':>8s} {'miss/act':>9s} {'abst':>4s} {'corr':>4s} {'Brier':>6s} {'slope med':>9s} {'kept med':>8s} {'kept p90':>8s}"
    print(hdr)
    for arm, r in A.items():
        print(f"{arm:14s} {r['n']:3d} {r['false_passes']:3d}/{r['predicted_passes']:<4d} {r['missed_passes']:3d}/{r['actual_passes']:<5d} "
              f"{r['abstentions']:4d} {r['correct']:4d} {r['brier']:6.3f} {r['slope_err_median'] if r['slope_err_median'] is not None else float('nan'):9.3f} "
              f"{(r['kept_err_median'] or 0):8.3%} {(r['kept_err_p90'] or 0):8.3%}")
    for t, v in res["tests"].items():
        print(t, json.dumps(v))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
