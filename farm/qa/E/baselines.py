#!/usr/bin/env python3
"""Experiment E (Addendum 42): scripted baselines' predictions for the 35 sources, written before any label exists.

Arms: raw_claim, law, io_rule, two_point (19 sources with a record second point), handpicked (slope = a + b*f fitted by
least squares on the training labels, f = elib.handpicked_feature of the post-GRT dump).
Inputs: farm/qa/E/sources.json; the capture runs' results (<results>/ers-*/metrics.json, nets.jsonl.gz); the private
packet key (source -> packet id); the training set (labels.csv + runs/<id>/nets/postgrt.jsonl.gz).
Output: <pred>/<arm>/<packet_id>.json (PACKET_FORMAT.md schema) and <pred>/baselines_meta.json.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import elib as E  # noqa: E402


def drv(m):
    return (m.get("design__max_slew_violation__count") or 0) + (m.get("design__max_cap_violation__count") or 0)


def judge(m, bar):
    ws, h = m.get("timing__setup__ws"), m.get("timing__hold__ws")
    return ws is not None and ws >= 0 and h is not None and h >= 0 and (m.get("route__drc_errors") or 0) == 0 \
        and drv(m) <= bar


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="dir holding the downloaded ers-* capture results")
    ap.add_argument("--key", required=True, help="private packet key json")
    ap.add_argument("--train", required=True, help="training set dir (labels.csv, runs/)")
    ap.add_argument("--pred", required=True)
    ap.add_argument("--meta", default=None, help="where to write baselines_meta.json (default: beside --key, private)")
    a = ap.parse_args()
    src = json.load(open(os.path.join(HERE, "sources.json")))["sources"]
    key = json.load(open(a.key))
    pid_of = {v["source"]: pid for pid, v in key["packets"].items() if v["kind"] == "main"}
    # hand-picked feature fit (training families only)
    xs, ys = [], []
    for r in csv.DictReader(open(os.path.join(a.train, "labels.csv"))):
        if r["has_postgrt"] != "1":
            continue
        p = os.path.join(a.train, "runs", r["run_id"], "nets", "postgrt.jsonl.gz")
        f = E.handpicked_feature(p)
        if f is None:
            continue
        xs.append(f)
        ys.append(float(r["slope"]))
    ha, hb = E.ols(xs, ys)
    meta = {"handpicked_fit": {"a": ha, "b": hb, "n": len(xs)}, "sources": {}}
    for s in src:
        sid = s["source"]
        if sid not in pid_of or not os.path.exists(os.path.join(a.results, sid, "metrics.json")):
            print(f"[baselines] {sid}: no packet or no capture result yet; skipped")
            continue
        pid = pid_of[sid]
        m = json.load(open(os.path.join(a.results, sid, "metrics.json")))
        T0 = float(s["T0"])
        ws0, wr0 = m["timing__setup__ws"], m.get("timing__setup_r2r__ws")
        C0 = T0 - ws0
        sp = judge(m, s["stock_drv_bar"])
        arms = {"raw_claim": E.predict_from_response(lambda T: C0, T0, C0, sp),
                "law": E.predict_from_response(E.law_response(T0, ws0)[0], T0, C0, sp),
                "io_rule": E.predict_from_response(E.io_response(T0, ws0, wr0), T0, C0, sp)}
        if s.get("second_point"):
            q = s["second_point"]
            sh = (C0 - q["C"]) / (T0 - q["T"])
            arms["two_point"] = E.predict_from_response(E.line_response(T0, C0, sh), T0, C0, sp)
        f = E.handpicked_feature(os.path.join(a.results, sid, "nets.jsonl.gz"))
        if f is not None:
            arms["handpicked"] = E.predict_from_response(E.line_response(T0, C0, ha + hb * f), T0, C0, sp)
        meta["sources"][pid] = {"T0": T0, "C0": C0, "R1": E.ceil05(C0), "source_pass": sp, "handpicked_f": f,
                                "replay_matches_record": abs(ws0 - s["ws0_record"]) < 1e-9}
        for arm, pr in arms.items():
            d = os.path.join(a.pred, arm)
            os.makedirs(d, exist_ok=True)
            out = {"packet_id": pid, "arm": arm, **pr}
            json.dump(out, open(os.path.join(d, pid + ".json"), "w"), indent=1)
    json.dump(meta, open(a.meta or os.path.join(os.path.dirname(os.path.abspath(a.key)), "baselines_meta.json"), "w"),
              indent=1)
    print(f"[baselines] {len(src)} sources; handpicked fit a={ha:.4f} b={hb:.4f} on n={len(xs)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
