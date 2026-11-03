#!/usr/bin/env python3
"""Workstream B smoke receipt checks (plumbing only; smoke runs enter no analysis).

  python3 farm/qa/B/smoke_check.py --sky DIR --asap DIR [--record /home/claude/eda/results] [--e5 /home/claude/qa/asap7/results]

sky130: (1) control smoke-b-xtea-ctl (xac-xtea-024 replayed at F_best = 4.20 ns with IO_DELAY_CONSTRAINT = 20) must equal
the record run in every metrics.json key; (2) frozen chain smoke-b2a-xtea-*: CLOCK_PERIOD x IO_DELAY_CONSTRAINT / 100 = D =
0.84 ns in resolved.json and in the flow log's base.sdc lines; chain state stepped through stage 1 and the resume stage.
ASAP7: (3) smoke-b3g-gcd-003 (310 ps = P0) equals E5's e5g-gcd-003 in every metric except execution-time keys;
(4) smoke-b3g-gcd-001 (215 ps): constraint.sdc carries clk_io_pct 0.28837209 (I/O delay 62 ps).
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import re


def J(p):
    if p.endswith(".gz"):
        return json.load(gzip.open(p, "rt"))
    return json.load(open(p))


def merged_logs(d):
    m = {}
    for p in sorted(glob.glob(os.path.join(d, "logs", "*.json"))):
        try:
            x = json.load(open(p))
        except Exception:
            continue
        if isinstance(x, dict):
            m.update(x)
    return m


def exec_key(k):
    return "runtime" in k or k.endswith("_s")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sky", required=True)
    ap.add_argument("--asap", required=True)
    ap.add_argument("--record", default="/home/claude/eda/results")
    ap.add_argument("--e5", default="/home/claude/qa/asap7/results")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    out = {}
    # (1) sky130 control
    try:
        m = J(os.path.join(a.sky, "smoke-b-xtea-ctl", "metrics.json"))
        mo = J(os.path.join(a.record, "xac-xtea-024", "metrics.json"))
        diff = sorted(k for k in set(m) | set(mo) if m.get(k) != mo.get(k))
        r = J(os.path.join(a.sky, "smoke-b-xtea-ctl", "resolved.json.gz"))
        out["sky_control"] = {"keys": len(mo), "diff_keys": diff, "identical": not diff,
                              "IO_DELAY_CONSTRAINT": r.get("IO_DELAY_CONSTRAINT"), "CLOCK_PERIOD": r.get("CLOCK_PERIOD"),
                              "ws": m.get("timing__setup__ws"), "ws_record": mo.get("timing__setup__ws")}
    except Exception as e:
        out["sky_control"] = {"error": repr(e)}
    # (2) sky130 frozen chain
    rows = []
    for d in sorted(glob.glob(os.path.join(a.sky, "smoke-b2a-xtea-*"))):
        tag = os.path.basename(d)
        try:
            r = J(os.path.join(d, "resolved.json.gz"))
            m = J(os.path.join(d, "metrics.json"))
        except Exception as e:
            rows.append({"tag": tag, "error": repr(e)})
            continue
        T, io = float(r["CLOCK_PERIOD"]), float(r["IO_DELAY_CONSTRAINT"])
        sdc = []
        fl = os.path.join(d, "flow.log.gz")
        if os.path.exists(fl):
            txt = gzip.open(fl, "rt", errors="replace").read()
            sdc = sorted(set(re.findall(r"Setting (input|output) delay to: ([0-9.eE+-]+)", txt)))
        rows.append({"tag": tag, "T": T, "IO_DELAY_CONSTRAINT": io, "delay_ns": T * io / 100.0,
                     "delay_ok": abs(T * io / 100.0 - 0.84) < 1e-6, "sdc_lines": sdc,
                     "ws": m.get("timing__setup__ws"), "claim": T - m["timing__setup__ws"]})
    ch = None
    p = os.path.join(a.sky, "chains", "smoke-b2a-xtea.json")
    if os.path.exists(p):
        c = json.load(open(p))
        ch = {"stage": c.get("stage"), "complete": c.get("complete"), "kept": c.get("kept_clock"),
              "first_pass": c.get("first_pass_clock"),
              "state": [(s["tag"], s["period"], s["claim"], s["pass"], s.get("io_pct")) for s in c["state"]],
              "steps": [(s["stage"], s["after"], s["next"], s["why"]) for s in c["steps"]]}
    out["sky_chain"] = {"runs": rows, "chain": ch,
                        "all_delays_0p84": bool(rows) and all(r.get("delay_ok") for r in rows)}
    # (3)/(4) ASAP7
    try:
        m = merged_logs(os.path.join(a.asap, "smoke-b3g-gcd-003"))
        mo = merged_logs(os.path.join(a.e5, "e5g-gcd-003"))
        diff = sorted(k for k in set(m) | set(mo) if m.get(k) != mo.get(k) and not exec_key(k))
        out["asap_control"] = {"keys": len(mo), "diff_keys_non_exec": diff, "identical": not diff and bool(m),
                               "ws": m.get("finish__timing__setup__ws"), "ws_e5": mo.get("finish__timing__setup__ws")}
    except Exception as e:
        out["asap_control"] = {"error": repr(e)}
    try:
        sdc = open(os.path.join(a.asap, "smoke-b3g-gcd-001", "constraint.sdc")).read()
        pct = re.search(r"^set clk_io_pct (\S+)", sdc, re.M).group(1)
        per = re.search(r"^set clk_period (\S+)", sdc, re.M).group(1)
        m = merged_logs(os.path.join(a.asap, "smoke-b3g-gcd-001"))
        mo = merged_logs(os.path.join(a.e5, "e5g-gcd-001"))
        hook = J(os.path.join(a.asap, "smoke-b3g-gcd-001", "reports", "e5_hook.json"))
        out["asap_frozen"] = {"clk_period": per, "clk_io_pct": pct, "io_delay_ps": float(per) * float(pct),
                              "ws": m.get("finish__timing__setup__ws"), "claim": float(per) - m["finish__timing__setup__ws"],
                              "claim_e5_stock": float(per) - mo["finish__timing__setup__ws"], "hook": hook}
    except Exception as e:
        out["asap_frozen"] = {"error": repr(e)}
    s = json.dumps(out, indent=1, default=str)
    print(s)
    if a.out:
        open(a.out, "w").write(s)


if __name__ == "__main__":
    main()
