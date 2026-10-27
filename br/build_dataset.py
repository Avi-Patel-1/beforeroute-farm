#!/usr/bin/env python3
"""Join per-run feature dumps (G) with signoff labels (S) into one dataset.

Usage: build_dataset.py [--results <dir>] [--out dataset.parquet]

Join key: the net's driver (instance/pin at G == driver at S). Nets are renamed
or split by later steps but driver instances survive; a G net whose driver key
is absent at S is matched by name as a fallback, else marked unjoined.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import re

import pandas as pd

DRIVE_RE = re.compile(r"_(\d+)$")
CLASS_RE = re.compile(r"__([a-z0-9]+?)(?:_\d+)?$")


def master_class(m: str | None) -> str:
    if not m:
        return "port"
    mm = CLASS_RE.search(m)
    base = mm.group(1) if mm else m
    for k in ("clkdlybuf", "dlygate", "dlymetal", "clkbuf", "clkinv", "einvp", "einvn", "ebuf", "buf", "inv",
              "dfxtp", "dfrtp", "dfstp", "dfbbp", "dfxbp", "dfrbp", "edfxtp", "edfxbp", "sdfxtp", "sdfrtp",
              "nand", "nor", "xnor", "xor", "and", "or", "mux", "a2", "a3", "a4", "o2", "o3", "o4", "conb", "diode", "fa", "ha", "maj", "dlclkp", "dlxtp", "dlrtp"):
        if base.startswith(k):
            return k
    return base


def drive_index(m: str | None) -> float:
    if not m:
        return float("nan")
    mm = DRIVE_RE.search(m)
    return float(mm.group(1)) if mm else float("nan")


def _open_jsonl(path: str):
    """Open a per-net dump, or its gzipped copy (training-run dumps are gzipped to fit the session disk)."""
    if os.path.exists(path):
        return open(path)
    import gzip
    return gzip.open(path + ".gz", "rt")


def load_run(rdir: str):
    job = json.load(open(os.path.join(rdir, "job.json")))
    if job.get("status") != "completed":
        return None, job
    feats = [json.loads(l) for l in _open_jsonl(os.path.join(rdir, "nets.jsonl"))]
    lab = json.load(open(os.path.join(rdir, "labels.json")))
    final = json.load(open(os.path.join(rdir, "final_nets.json")))
    resolved = json.load(open(os.path.join(rdir, "resolved.json")))
    summ = json.load(open(os.path.join(rdir, "dump_summary.json")))
    metrics = json.load(open(os.path.join(rdir, "metrics.json")))

    by_driver_s = {}
    for name, rec in final["nets"].items():
        if rec["driver"]:
            by_driver_s[rec["driver"]] = name
    lab_by_net = {r["net"]: r for r in lab["nets"]}
    # signoff view (actual values for every net), keyed by driver
    so_by_driver = {}
    so_path = os.path.join(rdir, "nets_signoff.jsonl")
    if os.path.exists(so_path) or os.path.exists(so_path + ".gz"):
        for l in _open_jsonl(so_path):
            r = json.loads(l)
            if r.get("driver_kind") == "inst":
                so_by_driver[f"{r['driver_inst']}/{r['driver_pin']}"] = r
            elif r.get("driver_kind") == "port":
                so_by_driver[f"PORT:{r['driver_pin']}"] = r

    rows = []
    n_join_driver = n_join_name = n_unjoined = 0
    for f in feats:
        if f.get("driver_kind") == "inst":
            key = f"{f['driver_inst']}/{f['driver_pin']}"
        elif f.get("driver_kind") == "port":
            key = f"PORT:{f['driver_pin']}"
        else:
            key = None
        s_net = by_driver_s.get(key) if key else None
        how = "driver"
        if s_net is None:
            if f["net"] in final["nets"]:
                s_net, how = f["net"], "name"
            else:
                how = "none"
        if how == "driver":
            n_join_driver += 1
        elif how == "name":
            n_join_name += 1
        else:
            n_unjoined += 1
        lr = lab_by_net.get(s_net) if s_net else None
        layers = f.get("guide_len_by_layer_um") or {}
        gtot = f.get("guide_len_um") or 0.0
        row = {
            "run": job["tag"],
            "design": summ.get("design"),
            "net": f["net"],
            "net_s": s_net,
            "join_how": how,
            "driver_key": key,
            "sigtype": f.get("sigtype"),
            "is_clock": f.get("is_clock", 0),
            "fanout": f.get("fanout"),
            "n_load_ports": f.get("n_load_ports"),
            "driver_kind": f.get("driver_kind"),
            "driver_master": f.get("driver_master"),
            "driver_class": master_class(f.get("driver_master")),
            "drive_index": drive_index(f.get("driver_master")),
            "driver_slew_ns": f.get("driver_slew_ns"),
            "driver_slew_ratio": f.get("driver_slew_ratio"),
            "worst_load_slew_ns": f.get("worst_load_slew_ns"),
            "worst_load_slew_ratio": f.get("worst_load_slew_ratio"),
            "driver_slew_limit_lib_ns": f.get("driver_slew_limit_lib_ns"),
            "driver_cap_limit_lib_pf": f.get("driver_cap_limit_lib_pf"),
            "driver_slack_ns": f.get("driver_slack_ns"),
            "hpwl_um": f.get("hpwl_um"),
            "bbox_w_um": f.get("bbox_w_um"),
            "bbox_h_um": f.get("bbox_h_um"),
            "density_mean": f.get("density_mean"),
            "density_max": f.get("density_max"),
            "guide_len_um": gtot,
            "guide_frac_li1": (layers.get("li1", 0.0) / gtot) if gtot else 0.0,
            "guide_frac_met1": (layers.get("met1", 0.0) / gtot) if gtot else 0.0,
            "guide_frac_met2": (layers.get("met2", 0.0) / gtot) if gtot else 0.0,
            "guide_frac_met3up": (sum(v for k, v in layers.items() if k in ("met3", "met4", "met5")) / gtot) if gtot else 0.0,
            "net_cap_pf_max": f.get("net_cap_pf_max"),
            "net_cap_pf_tt": (f.get("net_cap_pf_by_corner") or {}).get("nom_tt_025C_1v80"),
            "pin_cap_pf_max": f.get("pin_cap_pf_max"),
            "cap_ratio": f.get("cap_ratio"),
            "fanout_ratio": f.get("fanout_ratio"),
            # design-level context
            "d_utilization": summ.get("utilization"),
            "d_core_area_um2": summ.get("core_area_um2"),
            "d_inst_count": summ.get("inst_count"),
            "d_clock_period_ns": float(resolved.get("CLOCK_PERIOD") or float("nan")),
            "d_fp_core_util": float(resolved.get("FP_CORE_UTIL") or float("nan")),
            "d_pl_density_pct": float(resolved.get("PL_TARGET_DENSITY_PCT") or float("nan")),
            "d_max_tran_ns": summ.get("sdc_max_transition_ns"),
            "d_post_grt_repair": int(bool(resolved.get("RUN_POST_GRT_DESIGN_REPAIR"))),
            # labels
            "y": int(lr is not None),
            "y_slew": int(bool(lr and lr.get("viol_slew"))),
            "y_cap": int(bool(lr and lr.get("viol_cap"))),
            "y_fanout": int(bool(lr and lr.get("viol_fanout"))),
            "s_worst_slew_ratio": (lr or {}).get("worst_slew_ratio_s", 0.0) if lr else 0.0,
            "s_worst_cap_ratio": (lr or {}).get("worst_cap_ratio_s", 0.0) if lr else 0.0,
            "s_n_corners": len((lr or {}).get("corners", [])) if lr else 0,
        }
        so = so_by_driver.get(key) if key else None
        row["act_load_slew_ratio"] = so.get("worst_load_slew_ratio") if so else None
        row["act_driver_slew_ratio"] = so.get("driver_slew_ratio") if so else None
        row["act_cap_ratio"] = so.get("cap_ratio") if so else None
        row["act_net_cap_pf_max"] = so.get("net_cap_pf_max") if so else None
        rows.append(row)
    stats = {
        "run": job["tag"],
        "design": summ.get("design"),
        "nets_g": len(feats),
        "nets_s": len(final["nets"]),
        "join_driver": n_join_driver,
        "join_name": n_join_name,
        "unjoined": n_unjoined,
        "join_rate": (n_join_driver + n_join_name) / max(1, len(feats)),
        "labels_violating_nets_s": lab["summary"]["nets_violating"],
        "positives_joined": sum(r["y"] for r in rows),
        "positive_rate_joined": sum(r["y"] for r in rows) / max(1, len(rows)),
        "corner_counts": lab["summary"]["corner_counts"],
        "stdcell_area": metrics.get("design__instance__area__stdcell"),
        "flow_seconds": job.get("flow_seconds"),
    }
    return rows, stats


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results"))
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    results = os.path.abspath(a.results)
    out = a.out or os.path.join(results, "dataset.parquet")
    all_rows, all_stats = [], []
    frames = []  # per-run DataFrames (much smaller than one huge list of dicts)

    def compact(f):
        for c in f.columns:
            if f[c].dtype == "float64":
                f[c] = f[c].astype("float32")
            elif f[c].dtype == "int64":
                f[c] = pd.to_numeric(f[c], downcast="integer")
        return f

    for rdir in sorted(glob.glob(os.path.join(results, "*"))):
        if not os.path.isdir(rdir) or not os.path.exists(os.path.join(rdir, "job.json")):
            continue
        if rdir.endswith(("-ckpt", "-dmp")) or "-ckptrc" in os.path.basename(rdir):  # checkpoint feature dumps carry no labels
            continue
        try:
            rows, stats = load_run(rdir)
        except Exception as e:  # keep going; report
            print(f"[br] {os.path.basename(rdir)}: ERROR {type(e).__name__}: {e}")
            continue
        if rows is None:
            print(f"[br] {os.path.basename(rdir)}: skipped ({stats.get('status')})")
            continue
        frames.append(compact(pd.DataFrame(rows)))
        all_rows = True
        all_stats.append(stats)
        print(f"[br] {stats['run']:28s} nets={stats['nets_g']:6d} join={stats['join_rate']:.3f} "
              f"pos={stats['positives_joined']:5d} ({stats['positive_rate_joined']:.3%})  viol_nets_s={stats['labels_violating_nets_s']}")
    if not all_rows:
        print("[br] no completed runs")
        return 1
    df = pd.concat(frames, ignore_index=True, sort=False)
    del frames
    tmp = out + ".tmp"
    df.to_parquet(tmp, index=False)
    os.replace(tmp, out)  # atomic: readers never see a half-written file
    json.dump(all_stats, open(os.path.splitext(out)[0] + ".stats.json", "w"), indent=1)
    print(f"[br] wrote {len(df)} rows from {len(all_stats)} runs -> {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
