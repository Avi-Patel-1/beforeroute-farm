#!/usr/bin/env python3
"""IO1 registered verdict (docs/qa_week/IO_PREREG.md, "Registered tests").

Usage: python3 farm/qa/IO/score.py --results DIR [--json OUT.json]
DIR/io-<case>-<arm>/chain.json for the 10 cases x 3 arms (stock, script, claude), as phase2.py collect leaves them.
Kept clock K = smallest passing clock of the chain (source run included); none if nothing passed.
Gain of arm a over arm b: g = K_b / K_a - 1 (positive: a verified a faster clock). Both none: 0; a none: -1;
b none: +inf. A beat is g > THETA (E4's chaos floor, 2.3%; the smoke's no-op replay was bit-identical).
  P1: Claude beats stock on >= 6 of the 10 cases
  P2: the median over the 10 cases of g(claude over stock) >= 3%
  P3: Claude beats the script on >= 5 of the 10 cases
The registered prediction holds iff P1, P2 and P3 all hold. A case without a landed chain for an arm counts as no
beat for the tests that need that arm, and is left out of the median (the result must say so).
"""
import argparse
import hashlib
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
THETA = 0.023
ARMS = ("stock", "script", "claude")


def gain(Ka, Kb):
    if Ka is None and Kb is None:
        return 0.0
    if Ka is None:
        return -1.0
    if Kb is None:
        return float("inf")
    return Kb / Ka - 1.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    cases = json.load(open(os.path.join(HERE, "cases.json")))["cases"]
    rows, missing, plan_mismatch = [], [], []
    for c in cases:
        r = {"case": c["case"], "design": c["design"], "T0": c["T0"], "record_kept": c["record_chain"]["kept"]}
        for arm in ARMS:
            p = os.path.join(a.results, f"io-{c['case']}-{arm}", "chain.json")
            if not os.path.exists(p):
                r[arm] = None
                missing.append(f"{c['case']}-{arm}")
                continue
            ch = json.load(open(p))
            if arm != "stock":
                pp = os.path.join(HERE, "plans", f"{c['case']}-{arm}.json")
                want = hashlib.sha256(open(pp, "rb").read()).hexdigest() if os.path.exists(pp) else None
                if ch.get("plan_sha256") != want:
                    plan_mismatch.append(f"{c['case']}-{arm}")
            r[arm] = {"kept": ch.get("kept"), "n_runs": len(ch["runs"]),
                      "claim0": ch["runs"][0].get("claim") if ch["runs"] else None,
                      "first_rebuild_passed": ch["runs"][1]["passed"] if len(ch["runs"]) > 1 else None,
                      "truncated": ch.get("truncated")}
        K = {arm: (r[arm] or {}).get("kept") if r[arm] else None for arm in ARMS}
        have = {arm: r[arm] is not None for arm in ARMS}
        r["g_claude_stock"] = gain(K["claude"], K["stock"]) if have["claude"] and have["stock"] else None
        r["g_claude_script"] = gain(K["claude"], K["script"]) if have["claude"] and have["script"] else None
        r["g_script_stock"] = gain(K["script"], K["stock"]) if have["script"] and have["stock"] else None
        rows.append(r)

    def beats(key):
        return sum(1 for r in rows if r[key] is not None and r[key] > THETA)

    gcs = [r["g_claude_stock"] for r in rows if r["g_claude_stock"] is not None]
    med = statistics.median(gcs) if gcs else None
    P1 = beats("g_claude_stock") >= 6
    P2 = med is not None and med >= 0.03
    P3 = beats("g_claude_script") >= 5
    out = {"theta": THETA, "n_cases": len(rows), "missing_chains": missing, "plan_sha_mismatch": plan_mismatch,
           "claude_beats_stock": beats("g_claude_stock"), "median_g_claude_stock": med,
           "claude_beats_script": beats("g_claude_script"),
           "script_beats_stock": beats("g_script_stock"),
           "median_g_script_stock": (statistics.median([r["g_script_stock"] for r in rows
                                                        if r["g_script_stock"] is not None]) if rows else None),
           "stock_beats_claude": beats_rev(rows, "g_claude_stock"),
           "P1": P1, "P2": P2, "P3": P3, "prediction_holds": bool(P1 and P2 and P3), "rows": rows}
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)
    print(f"| case | design | T0 | K stock | K script | K claude | g claude/stock | g claude/script | g script/stock |")
    print("|---|---|---|---|---|---|---|---|---|")
    f = lambda v: "-" if v is None else (f"{v:+.1%}" if abs(v) != float("inf") else "inf")  # noqa: E731
    k = lambda r, arm: "-" if r[arm] is None else (r[arm]["kept"] if r[arm]["kept"] is not None else "none")  # noqa: E731
    for r in rows:
        print(f"| {r['case']} | {r['design']} | {r['T0']} | {k(r, 'stock')} | {k(r, 'script')} | {k(r, 'claude')} | "
              f"{f(r['g_claude_stock'])} | {f(r['g_claude_script'])} | {f(r['g_script_stock'])} |")
    print(f"\nP1 Claude beats stock (> {THETA:.1%}) on {out['claude_beats_stock']} of 10 (need 6): {P1}")
    print(f"P2 median g(claude over stock) = {f(med)} (need >= +3.0%): {P2}")
    print(f"P3 Claude beats script on {out['claude_beats_script']} of 10 (need 5): {P3}")
    print(f"Registered prediction holds: {out['prediction_holds']}  (missing chains: {missing or 'none'}; "
          f"plan hash mismatches: {plan_mismatch or 'none'})")


def beats_rev(rows, key):
    return sum(1 for r in rows if r[key] is not None and r[key] < -THETA)


if __name__ == "__main__":
    main()
