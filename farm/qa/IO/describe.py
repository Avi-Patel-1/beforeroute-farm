#!/usr/bin/env python3
"""IO phase 2: descriptive views beside the registered verdict (NOT registered; score.py alone gives the verdict).

Usage: python3 farm/qa/IO/describe.py --results DIR [--json OUT.json]
DIR/io-<case>-<arm>/ as phase2.py collect leaves it (chain.json, <tag>-r<k>/{metrics,job,pins_applied}.json).

Reports, per case and arm: every build of the chain (clock, pass, claim, worst setup/hold slack, DRC, slew+cap pins);
the pins the plan actually moved in each build (groups dropped because they no longer fit, pins whose position
differs from the tool's); for ABSTAIN plans, whether every build is identical to the stock arm's build at the same
clock (all metrics.json keys); flow time; and the gains restricted to the cases where Claude moved pins
(a secondary, descriptive view written after the pin files were locked; labelled as not registered).
"""
import argparse
import json
import os
import statistics

HERE = os.path.dirname(os.path.abspath(__file__))
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


def jl(p):
    return json.load(open(p)) if os.path.exists(p) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    ap.add_argument("--json", default=None)
    a = ap.parse_args()
    cases = json.load(open(os.path.join(HERE, "cases.json")))["cases"]
    out = {"cases": [], "noop_identity": [], "flow_hours": {}, "secondary_moved_only": None}
    flow_s = {arm: 0.0 for arm in ARMS}
    n_builds = {arm: 0 for arm in ARMS}
    for c in cases:
        row = {"case": c["case"], "design": c["design"], "T0": c["T0"], "record_claim0": c["claim0_record"],
               "record_kept": c["record_chain"]["kept"], "arms": {}}
        plans = {arm: jl(os.path.join(HERE, "plans", f"{c['case']}-{arm}.json")) for arm in ("script", "claude")}
        for arm in ARMS:
            d = os.path.join(a.results, f"io-{c['case']}-{arm}")
            ch = jl(os.path.join(d, "chain.json"))
            if ch is None:
                row["arms"][arm] = None
                continue
            builds = []
            for r in ch["runs"]:
                rd = os.path.join(d, r["tag"])
                pa = jl(os.path.join(rd, "pins_applied.json"))
                b = {k: r.get(k) for k in ("tag", "kind", "clock", "passed", "claim", "ws", "ws_r2r", "hold", "drc", "drv",
                                           "flow_completed", "status", "wall_s", "retried")}
                if pa is not None:
                    changed = sum(1 for p, mv in pa["moved"].items()
                                  if (pa["stock"].get(p, {}).get("edge"), pa["stock"].get(p, {}).get("pos"))
                                  != (mv["edge"], mv["pos"]))
                    b["pins"] = {"moved_groups": pa["n_moved_groups"], "placed_pins": pa["n_moved_pins"],
                                 "pins_off_stock_position": changed, "dropped_groups": pa["dropped_groups"]}
                else:
                    b["pins"] = None
                flow_s[arm] += r.get("wall_s") or 0.0
                n_builds[arm] += 1
                builds.append(b)
            row["arms"][arm] = {"kept": ch.get("kept"), "truncated": ch.get("truncated"), "plan_sha256": ch.get("plan_sha256"),
                                "n_moves_in_plan": len(plans[arm]["moves"]) if arm != "stock" and plans[arm] else 0,
                                "first_rebuild_passed": builds[1]["passed"] if len(builds) > 1 else None,
                                "builds": builds}
        K = {arm: (row["arms"][arm] or {}).get("kept") for arm in ARMS}
        have = {arm: row["arms"][arm] is not None for arm in ARMS}
        row["g_claude_stock"] = gain(K["claude"], K["stock"]) if have["claude"] and have["stock"] else None
        row["g_claude_script"] = gain(K["claude"], K["script"]) if have["claude"] and have["script"] else None
        row["g_script_stock"] = gain(K["script"], K["stock"]) if have["script"] and have["stock"] else None
        row["g_stock_record"] = gain(K["stock"], row["record_kept"]) if have["stock"] else None
        row["claude_moved"] = bool(plans["claude"] and plans["claude"]["moves"])
        # no-op identity: an ABSTAIN plan vs the stock arm, build by build at equal clocks, every metrics.json key
        if not row["claude_moved"] and have["claude"] and have["stock"]:
            sd = {b["clock"]: b["tag"] for b in row["arms"]["stock"]["builds"]}
            for b in row["arms"]["claude"]["builds"]:
                if b["clock"] not in sd:
                    out["noop_identity"].append({"case": c["case"], "clock": b["clock"], "stock_has_clock": False})
                    continue
                m1 = jl(os.path.join(a.results, f"io-{c['case']}-claude", b["tag"], "metrics.json")) or {}
                m0 = jl(os.path.join(a.results, f"io-{c['case']}-stock", sd[b["clock"]], "metrics.json")) or {}
                diff = sorted(k for k in set(m0) | set(m1) if m0.get(k) != m1.get(k))
                out["noop_identity"].append({"case": c["case"], "clock": b["clock"], "stock_has_clock": True,
                                             "n_keys": len(set(m0) | set(m1)), "n_differing": len(diff),
                                             "differing_keys": diff[:20]})
        out["cases"].append(row)
    out["flow_hours"] = {arm: round(flow_s[arm] / 3600, 2) for arm in ARMS}
    out["flow_hours"]["total"] = round(sum(flow_s.values()) / 3600, 2)
    out["n_builds"] = dict(n_builds, total=sum(n_builds.values()))

    moved = [r for r in out["cases"] if r["claude_moved"]]

    def beats(rows, key, sign=1):
        return sum(1 for r in rows if r[key] is not None and sign * r[key] > THETA)

    def med(rows, key):
        v = [r[key] for r in rows if r[key] is not None]
        return statistics.median(v) if v else None

    out["secondary_moved_only"] = {
        "label": "descriptive, NOT registered: the cases where Claude moved pins (its other cases ran a no-op plan)",
        "cases": [r["case"] for r in moved], "n": len(moved),
        "claude_beats_stock": beats(moved, "g_claude_stock"), "stock_beats_claude": beats(moved, "g_claude_stock", -1),
        "median_g_claude_stock": med(moved, "g_claude_stock"),
        "claude_beats_script": beats(moved, "g_claude_script"), "script_beats_claude": beats(moved, "g_claude_script", -1),
        "median_g_claude_script": med(moved, "g_claude_script"),
        "script_beats_stock": beats(moved, "g_script_stock"), "stock_beats_script": beats(moved, "g_script_stock", -1),
        "median_g_script_stock": med(moved, "g_script_stock")}
    allr = out["cases"]
    out["beside_all10"] = {
        "script_beats_stock": beats(allr, "g_script_stock"), "stock_beats_script": beats(allr, "g_script_stock", -1),
        "median_g_script_stock": med(allr, "g_script_stock"),
        "stock_kept_vs_record": [(r["case"], (r["arms"]["stock"] or {}).get("kept"), r["record_kept"]) for r in allr]}
    if a.json:
        json.dump(out, open(a.json, "w"), indent=1)

    f = lambda v: "-" if v is None else (f"{v:+.1%}" if abs(v) != float("inf") else "inf")  # noqa: E731
    print("| case | arm | builds: clock ns (P/F, claim ns) | kept ns | pins moved per build (dropped) |")
    print("|---|---|---|---|---|")
    for r in allr:
        for arm in ARMS:
            A = r["arms"][arm]
            if A is None:
                print(f"| {r['case']} | {arm} | not landed | - | - |")
                continue
            bs = "; ".join(f"{b['clock']} {'P' if b['passed'] else 'F'} ({b['claim']:.3f})" if b["claim"] is not None
                           else f"{b['clock']} F (no metrics)" for b in A["builds"])
            pins = ", ".join("-" if b["pins"] is None else
                             f"{b['pins']['pins_off_stock_position']}/{b['pins']['placed_pins']}"
                             + (f" drop {b['pins']['dropped_groups']}" if b["pins"]["dropped_groups"] else "")
                             for b in A["builds"])
            print(f"| {r['case']} | {arm} | {bs} | {A['kept']} | {pins} |")
    print()
    print("No-op identity (ABSTAIN plans vs stock, same clock):",
          f"{sum(1 for x in out['noop_identity'] if x.get('n_differing') == 0)} of {len(out['noop_identity'])} builds identical")
    for x in out["noop_identity"]:
        if x.get("n_differing"):
            print("  differs:", x)
    s = out["secondary_moved_only"]
    print(f"\nSecondary (NOT registered), the {s['n']} moved cases {s['cases']}:")
    print(f"  Claude vs stock: Claude beats {s['claude_beats_stock']}, stock beats {s['stock_beats_claude']}, "
          f"median g {f(s['median_g_claude_stock'])}")
    print(f"  Claude vs script: Claude beats {s['claude_beats_script']}, script beats {s['script_beats_claude']}, "
          f"median g {f(s['median_g_claude_script'])}")
    print(f"  script vs stock: script beats {s['script_beats_stock']}, stock beats {s['stock_beats_script']}, "
          f"median g {f(s['median_g_script_stock'])}")
    b = out["beside_all10"]
    print(f"Beside (all 10): script beats stock {b['script_beats_stock']}, stock beats script {b['stock_beats_script']}, "
          f"median g(script/stock) {f(b['median_g_script_stock'])}")
    print(f"Flow time (h, sum of build wall times): {out['flow_hours']}; builds {out['n_builds']}")


if __name__ == "__main__":
    main()
