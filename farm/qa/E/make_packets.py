#!/usr/bin/env python3
"""Experiment E (Addendum 42): build the blind test packets from the captured source runs.

For every source in farm/qa/E/sources.json: packet id R<6 hex> = sha256(salt + source); <out>/<pid>/rung1/ (contract +
summary) and <out>/<pid>/rung2/ (the full raw record). Controls on the first 6 packet ids in sorted order: a renaming
control (new id, new pseudonym salt; rung 2) and a shuffled-view diagnostic (new id; per-net geometric/electrical fields
permuted among nets of the same driver cell and fanout; layout withheld). The private key (packet -> source, kind, the
original names) goes to <private>/packet_key.json and <private>/names/<pid>.json; neither is ever given to a reader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import epack  # noqa: E402

SKIP_FLAGS = {"RUN_MAGIC_DRC", "RUN_KLAYOUT_DRC", "RUN_LVS", "RUN_KLAYOUT_XOR", "RUN_IRDROP_REPORT", "RUN_LINTER"}


def drv(m):
    return (m.get("design__max_slew_violation__count") or 0) + (m.get("design__max_cap_violation__count") or 0)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="dir holding the downloaded ers-* results (with capture/)")
    ap.add_argument("--out", required=True)
    ap.add_argument("--private", required=True)
    ap.add_argument("--salt", required=True)
    ap.add_argument("--n-controls", type=int, default=6)
    ap.add_argument("--only", default=None, help="comma list of sources (debug)")
    a = ap.parse_args()
    src = json.load(open(os.path.join(HERE, "sources.json")))["sources"]
    if a.only:
        src = [s for s in src if s["source"] in a.only.split(",")]
    os.makedirs(os.path.join(a.private, "names"), exist_ok=True)
    key = {"about": "PRIVATE: packet -> source. Never give this file or names/ to a reader.", "packets": {}}
    kp = os.path.join(a.private, "packet_key.json")
    if os.path.exists(kp):
        key = json.load(open(kp))

    def pid_for(s, kind):
        return "R" + hashlib.sha256((a.salt + kind + s["source"]).encode()).hexdigest()[:6]

    def build(s, pid, kind, rung_dirs, salt, shuffle=None, main_pid=None):
        jd = json.load(open(os.path.join(os.path.dirname(HERE), "..", "jobs", s["source"] + ".json")))
        settings = {k: v for k, v in jd["overrides"].items() if k != "CLOCK_PERIOD" and k not in SKIP_FLAGS}
        info = {"packet_id": pid, "T0": s["T0"], "drv_bar": s["stock_drv_bar"], "settings": settings}
        res = None
        for rung in rung_dirs:
            d = os.path.join(a.out, pid, f"rung{rung}")
            shutil.rmtree(d, ignore_errors=True)
            res = epack.build_packet(os.path.join(a.results, s["source"]), d, salt, info, rung=rung,
                                     layout=(shuffle is None), shuffle_seed=shuffle)
        json.dump(sorted(res["map"].keys()), open(os.path.join(a.private, "names", pid + ".json"), "w"))
        key["packets"][pid] = {"source": s["source"], "design": s["design"], "record_tag": s["record_tag"],
                               "kind": kind, "main_packet": main_pid, "has_second_point": bool(s.get("second_point")),
                               "T0": s["T0"], "salt": salt, "shuffle_seed": shuffle}
        print(f"[packets] {pid} {kind:8s} {s['source']}", flush=True)

    mains = {}
    for s in src:
        pid = pid_for(s, "main")
        mains[s["source"]] = pid
        build(s, pid, "main", (1, 2), a.salt + pid)
    ctl = sorted(mains.items(), key=lambda kv: kv[1])[:a.n_controls] if not a.only else []
    by = {s["source"]: s for s in src}
    for sid, mpid in ctl:
        s = by[sid]
        rp = pid_for(s, "rename")
        build(s, rp, "rename", (2,), a.salt + "rename" + rp, main_pid=mpid)
        sp = pid_for(s, "shuffle")
        seed = int(hashlib.sha256((a.salt + "seed" + sid).encode()).hexdigest()[:8], 16)
        build(s, sp, "shuffle", (2,), a.salt + "shuffle" + sp, shuffle=seed, main_pid=mpid)
    json.dump(key, open(kp, "w"), indent=1)
    print(f"[packets] {len(key['packets'])} packets in key")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
