#!/usr/bin/env python3
"""Build signoff (S-stage) labels for a finished LibreLane run.

Usage: labels.py <run_dir> [--out <dir>]

Parses every corner's checks.rpt under the final STAPostPNR step (max slew / max
capacitance / max fanout violators), maps violating pins to nets through the
final ODB, and writes labels.json with one record per net:
  violated (any type, any corner), per-type flags, worst actual/limit ratio per
  type, the corners involved, the net's driver key and fanout at signoff.
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SECTION_RE = re.compile(r"^(max slew|max capacitance|max fanout)\s*$")
ROW_RE = re.compile(r"^(\S+)\s+(-?[\d.]+)\s+(-?[\d.]+)(?:\s+(-?[\d.]+))?\s*(\(VIOLATED\))?\s*$")
COUNT_RE = re.compile(r"^max (slew|fanout|cap) violation count (\d+)")
TYPE_KEY = {"max slew": "slew", "max capacitance": "cap", "max fanout": "fanout"}


def parse_checks(path: str):
    """Return (rows, counts) where rows = list of dicts(pin, type, limit, actual, slack, violated)."""
    rows, counts, section = [], {}, None
    for line in open(path, errors="replace"):
        s = line.rstrip("\n")
        m = SECTION_RE.match(s)
        if m:
            section = TYPE_KEY[m.group(1)]
            continue
        m = COUNT_RE.match(s)
        if m:
            counts[m.group(1)] = int(m.group(2))
            continue
        if s.startswith("====") or s.startswith("report_") or s.startswith("check_"):
            if not SECTION_RE.match(s):
                # leaving a violator table once another report header starts
                if s.startswith("report_") or s.startswith("check_"):
                    section = None
            continue
        if section is None:
            continue
        m = ROW_RE.match(s)
        if m:
            pin, limit, actual, slack, vio = m.groups()
            if pin in ("Pin",) or pin.startswith("---"):
                continue
            limit_f, actual_f = float(limit), float(actual)
            slack_f = float(slack) if slack is not None else (limit_f - actual_f)
            rows.append(
                {
                    "pin": pin,
                    "type": section,
                    "limit": limit_f,
                    "actual": actual_f,
                    "slack": slack_f,
                    "violated": bool(vio) or slack_f < 0,
                }
            )
    return rows, counts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("run_dir")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    run_dir = os.path.abspath(a.run_dir)
    out = a.out or os.path.join(run_dir, "br-labels")
    os.makedirs(out, exist_ok=True)

    sta_dirs = sorted(glob.glob(os.path.join(run_dir, "*-openroad-stapostpnr")))
    if not sta_dirs:
        raise SystemExit("no STAPostPNR step dir found")
    sta_dir = sta_dirs[-1]
    corner_dirs = sorted(d for d in glob.glob(os.path.join(sta_dir, "*")) if os.path.isdir(d))

    # final ODB -> nets / pins
    odbs = glob.glob(os.path.join(run_dir, "final", "odb", "*.odb"))
    if not odbs:
        raise SystemExit("no final ODB found")
    netmap_path = os.path.join(out, "final_nets.json")
    if not os.path.exists(netmap_path):
        cmd = ["openroad", "-exit", "-no_splash", "-python", os.path.join(HERE, "labels_odb.py"), odbs[0], netmap_path]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0 or not os.path.exists(netmap_path):
            print(r.stdout[-2000:], r.stderr[-2000:], file=sys.stderr)
            raise SystemExit("labels_odb.py failed")
    netmap = json.load(open(netmap_path))
    nets, pin_to_net = netmap["nets"], netmap["pin_to_net"]

    per_net = {}
    unmapped_pins = set()
    corner_counts = {}
    for cd in corner_dirs:
        corner = os.path.basename(cd)
        rpt = os.path.join(cd, "checks.rpt")
        if not os.path.exists(rpt):
            continue
        rows, counts = parse_checks(rpt)
        corner_counts[corner] = counts
        for r in rows:
            if not r["violated"]:
                continue
            net = pin_to_net.get(r["pin"])
            if net is None:
                unmapped_pins.add(r["pin"])
                continue
            rec = per_net.setdefault(
                net,
                {
                    "net": net,
                    "driver_s": nets[net]["driver"],
                    "fanout_s": nets[net]["fanout"],
                    "sigtype_s": nets[net]["sigtype"],
                    "viol_slew": 0,
                    "viol_cap": 0,
                    "viol_fanout": 0,
                    "worst_slew_ratio_s": 0.0,
                    "worst_cap_ratio_s": 0.0,
                    "worst_fanout_ratio_s": 0.0,
                    "corners": set(),
                    "pins": set(),
                    "n_obs": 0,
                },
            )
            t = r["type"]
            rec[f"viol_{t}"] = 1
            ratio = (r["actual"] / r["limit"]) if r["limit"] else float("inf")
            k = f"worst_{t}_ratio_s"
            rec[k] = max(rec[k], ratio)
            rec["corners"].add(corner)
            rec["pins"].add(r["pin"])
            rec["n_obs"] += 1

    records = []
    for net, rec in per_net.items():
        rec["violated"] = 1
        rec["corners"] = sorted(rec["corners"])
        rec["pins"] = sorted(rec["pins"])
        records.append(rec)

    summary = {
        "run_dir": run_dir,
        "sta_dir": sta_dir,
        "corners": [os.path.basename(c) for c in corner_dirs],
        "corner_counts": corner_counts,
        "nets_total": len(nets),
        "nets_violating": len(records),
        "positive_rate": (len(records) / len(nets)) if nets else None,
        "unmapped_pins": sorted(unmapped_pins)[:50],
        "n_unmapped_pins": len(unmapped_pins),
    }
    json.dump({"summary": summary, "nets": records}, open(os.path.join(out, "labels.json"), "w"), indent=1)
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
