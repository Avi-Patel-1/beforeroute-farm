#!/usr/bin/env python3
"""Experiment E: build the training set (train_E / rung 3's sandbox) from the historical record of TRAINING families only.

Labelled runs = runs of settings run at >= 2 distinct targets (same non-clock overrides) in results/tune*/state.json,
original RTL only. Raw records come from results/<tag>/ and, when the per-net dumps were pruned locally, from the run's
GitHub artifact `result-<tag>` (30-day retention). Every run is packed with farm/qa/E/epack.py (format E1.0, rung 2,
no layout: historical runs never kept DEF/SPEF). Size policy (cap ~300 MB): families with median std cells < 3,000 keep
both per-net dumps; 3,000-15,000 keep the post-GRT dump only; >= 15,000 are report-level (contract, summary, metrics,
checks, drv) without per-net dumps.

Writes <out>/runs/<run_id>/, <out>/labels.csv, <out>/pairs.csv, <out>/README.md and a private key file (run_id -> tag)
to <keyfile> (NOT in the training set). Test families are refused.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import csv
import glob
import hashlib
import io
import json
import math
import os
import shutil
import statistics as stt
import subprocess
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import epack  # noqa: E402

SKIP_FLAGS = {"RUN_MAGIC_DRC", "RUN_KLAYOUT_DRC", "RUN_LVS", "RUN_KLAYOUT_XOR", "RUN_IRDROP_REPORT", "RUN_LINTER"}

REC = os.environ.get("E_RECORD", "/home/claude/eda")
REPO = "Avi-Patel-1/beforeroute-farm"
TEST = {"zipdiv", "cic_decimator", "wbqspiflash", "picorv32"}


def family(d):
    if d.startswith("clip16"):
        return "clip16"
    for f in ("zipdiv", "md5"):
        if d == f or d.startswith(f + "_"):
            return f
    return d


def key_of(ov):
    return json.dumps({k: v for k, v in ov.items() if k != "CLOCK_PERIOD"}, sort_keys=True)


def drv(m):
    return (m.get("design__max_slew_violation__count") or 0) + (m.get("design__max_cap_violation__count") or 0)


def stock_bar(d):
    for pre in ("x1d", "x2d", "x4d", "x5d", "x6d"):
        p = os.path.join(REC, "results", f"{pre}-{d}-001", "metrics.json")
        if os.path.exists(p):
            m = json.load(open(p))
            if m.get("timing__setup__ws") is not None:
                return drv(m), f"{pre}-{d}-001"
    # race designs: x6d with the largest frac that landed (tune_a32.ref_drv_x8)
    st = json.load(open(os.path.join(REC, "results", "tune_x6", "state.json")))["tags"]
    for _, t in sorted(((v.get("frac", 1.0), t) for t, v in st.items() if v["design"] == d and v["arm"] == "d"),
                       key=lambda x: -x[0]):
        p = os.path.join(REC, "results", t, "metrics.json")
        if os.path.exists(p) and json.load(open(p)).get("timing__setup__ws") is not None:
            return drv(json.load(open(p))), t
    return None, None


def judge(m, bar):
    ws, h = m.get("timing__setup__ws"), m.get("timing__hold__ws")
    if ws is None:
        return False
    return ws >= 0 and h is not None and h >= 0 and (m.get("route__drc_errors") or 0) == 0 and (bar is None or drv(m) <= bar)


def record():
    runs = []
    for sp in sorted(glob.glob(os.path.join(REC, "results", "tune*", "state.json"))):
        study = os.path.basename(os.path.dirname(sp))
        for tag, v in json.load(open(sp))["tags"].items():
            d = v.get("design")
            if not d or family(d) in TEST or v.get("status") == "superseded" or not v.get("overrides"):
                continue
            if v.get("variant") not in (None, "orig"):
                continue
            mp = os.path.join(REC, "results", tag, "metrics.json")
            if not os.path.exists(mp):
                continue
            m = json.load(open(mp))
            if m.get("timing__setup__ws") is None:
                continue
            runs.append({"tag": tag, "study": study, "design": d, "family": family(d), "arm": v.get("arm"),
                         "T": float(v["overrides"]["CLOCK_PERIOD"]), "key": key_of(v["overrides"]),
                         "overrides": v["overrides"], "m": m, "source": v.get("source"), "root": v.get("root")})
    seen, out, tags = set(), [], set()
    for r in runs:   # one record per (design, setting, target): exact repeats are the same measurement
        k = (r["design"], r["key"], round(r["T"], 4))
        if k in seen or r["tag"] in tags:
            continue
        seen.add(k)
        tags.add(r["tag"])
        out.append(r)
    return out


def crossing(pts):
    """agents/analysis/fixedpoint/analyze.py crossing (interpolated only; None otherwise)."""
    g = [(T, c - T) for T, c in pts]
    for (t1, g1), (t2, g2) in zip(g, g[1:]):
        if g1 > 0 >= g2:
            return t1 + (t2 - t1) * g1 / (g1 - g2)
    return None


def fetch_artifact(tag, dest, members=("nets.jsonl", "nets_signoff.jsonl", "final_nets.json", "labels.json")):
    try:
        out = subprocess.run(["gh", "api", f"repos/{REPO}/actions/artifacts?name=result-{tag}&per_page=5"],
                             capture_output=True, text=True, timeout=60)
        arts = [a for a in json.loads(out.stdout).get("artifacts", []) if not a.get("expired")]
        if not arts:
            return "no artifact"
        a = max(arts, key=lambda a: a["created_at"])
        z = subprocess.run(["gh", "api", f"repos/{REPO}/actions/artifacts/{a['id']}/zip"], capture_output=True,
                           timeout=600)
        if z.returncode != 0:
            return "download failed"
        zf = zipfile.ZipFile(io.BytesIO(z.stdout))
        os.makedirs(dest, exist_ok=True)
        got = []
        for nme in zf.namelist():
            if nme in members:
                with zf.open(nme) as fi, open(os.path.join(dest, nme), "wb") as fo:
                    shutil.copyfileobj(fi, fo)
                got.append(nme)
        return "ok:" + ",".join(got)
    except Exception as e:
        return f"error {type(e).__name__}: {e}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--keyfile", required=True)
    ap.add_argument("--cache", required=True, help="scratch dir for artifact members (deleted per run)")
    ap.add_argument("--salt", required=True)
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    runs = record()
    by_set = {}
    for r in runs:
        by_set.setdefault((r["design"], r["key"]), []).append(r)
    lab_sets = {k: sorted(v, key=lambda r: r["T"]) for k, v in by_set.items() if len({round(r["T"], 4) for r in v}) >= 2}
    cells = {}
    for r in runs:
        cells.setdefault(r["family"], []).append(r["m"].get("design__instance__count__stdcell") or 0)
    med = {f: stt.median(v) for f, v in cells.items()}
    bars = {}
    fams = sorted({k[0] for k in lab_sets})
    fam_pseudo = {f: "F" + hashlib.sha256((a.salt + "fam" + family(f)).encode()).hexdigest()[:4] for f in fams}
    jobs = []
    for (d, key), rs in sorted(lab_sets.items()):
        if d not in bars:
            bars[d] = stock_bar(d)
        sp = "S" + hashlib.sha256((a.salt + "set" + d + key).encode()).hexdigest()[:8]
        for r in rs:
            rid = "T" + hashlib.sha256((a.salt + "run" + r["tag"]).encode()).hexdigest()[:8]
            jobs.append((d, key, sp, rid, r))
    if a.limit:
        jobs = jobs[:a.limit]
    print(f"[train] {len(lab_sets)} labelled settings, {len(jobs)} runs, families {sorted({family(j[0]) for j in jobs})}")
    os.makedirs(os.path.join(a.out, "runs"), exist_ok=True)
    keys = {}

    def one(job):
        d, key, sp, rid, r = job
        fam = family(d)
        level = "both" if med[fam] < 3000 else ("postgrt" if med[fam] < 15000 else "report")
        src = os.path.join(REC, "results", r["tag"])
        tmp = os.path.join(a.cache, rid)
        os.makedirs(tmp, exist_ok=True)
        for f in ("metrics.json", "resolved.json", "labels.json", "job.json"):
            if os.path.exists(os.path.join(src, f)):
                shutil.copy2(os.path.join(src, f), tmp)
        if os.path.isdir(os.path.join(src, "checks")):
            shutil.copytree(os.path.join(src, "checks"), os.path.join(tmp, "checks"), dirs_exist_ok=True)
        note = "local"
        if level == "report":   # names only (pseudonymize the reports); no per-net files are written
            for f in ("final_nets.json.gz", "final_nets.json"):
                if os.path.exists(os.path.join(src, f)):
                    shutil.copy2(os.path.join(src, f), os.path.join(tmp, f))
                    break
        if level != "report":
            need = ["nets.jsonl", "final_nets.json"] + (["nets_signoff.jsonl"] if level == "both" else [])
            have = {f: os.path.exists(os.path.join(src, f + ".gz")) or os.path.exists(os.path.join(src, f)) for f in need}
            if not all(have.values()):
                note = fetch_artifact(r["tag"], tmp, members=tuple(need) + ("labels.json",))
            for f in need:
                for ext in (".gz", ""):
                    if os.path.exists(os.path.join(src, f + ext)) and not os.path.exists(os.path.join(tmp, f)) \
                            and not os.path.exists(os.path.join(tmp, f + ".gz")):
                        shutil.copy2(os.path.join(src, f + ext), os.path.join(tmp, f + ext))
            if level == "postgrt":
                for f in ("nets_signoff.jsonl", "nets_signoff.jsonl.gz"):
                    if os.path.exists(os.path.join(tmp, f)):
                        os.remove(os.path.join(tmp, f))
        settings = {k: v for k, v in r["overrides"].items() if k != "CLOCK_PERIOD" and k not in SKIP_FLAGS}
        info = {"packet_id": rid, "T0": r["T"], "drv_bar": bars[d][0], "settings": settings}
        try:
            epack.build_packet(tmp, os.path.join(a.out, "runs", rid), a.salt + rid, info, rung=2, layout=False,
                               write_connectivity=(level != "report"))
            ok = True
        except Exception as e:
            ok = False
            note += f"; pack error {type(e).__name__}: {e}"
        shutil.rmtree(tmp, ignore_errors=True)
        pk = os.path.join(a.out, "runs", rid)
        has = {"postgrt": os.path.exists(os.path.join(pk, "nets", "postgrt.jsonl.gz")),
               "signoff": os.path.exists(os.path.join(pk, "nets", "signoff.jsonl.gz"))}
        return rid, r["tag"], ok, note, has, level

    results = {}
    with cf.ThreadPoolExecutor(a.workers) as ex:
        for i, (rid, tag, ok, note, has, level) in enumerate(ex.map(one, jobs)):
            results[rid] = (tag, ok, note, has, level)
            keys[rid] = tag
            if i % 25 == 0:
                print(f"[train] {i + 1}/{len(jobs)} {rid} {ok} {note[:60]} {has}", flush=True)
    # labels
    rows, pairs = [], []
    for (d, key, sp, rid, r) in jobs:
        tag, ok, note, has, level = results[rid]
        if not ok:
            continue
        rs = lab_sets[(d, key)]
        bar = bars[d][0]
        C0 = r["T"] - r["m"]["timing__setup__ws"]
        R1 = epack.ceil05(C0)
        others = [o for o in rs if abs(o["T"] - r["T"]) > 1e-9]
        exact = [o for o in others if abs(o["T"] - R1) < 1e-6]
        p = exact[0] if exact else min(others, key=lambda o: (abs(o["T"] - R1), o["T"]))
        Cp = p["T"] - p["m"]["timing__setup__ws"]
        passing = sorted(o["T"] for o in rs if judge(o["m"], bar))
        pts = sorted((o["T"], o["T"] - o["m"]["timing__setup__ws"]) for o in rs)
        # chain (Addenda 32/35 closure + re-runs rooted at this run), when this run is a chain winner
        ch = [o for o in runs if o["design"] == d and o["key"] == key and o["arm"] in ("k", "c")
              and (o.get("source") == r["tag"] or o.get("root") == r["tag"])]
        kept, first = "", ""
        if ch:
            okc = [o["T"] for o in ch if judge(o["m"], bar)]
            kept = min(okc + ([r["T"]] if judge(r["m"], bar) else [])) if (okc or judge(r["m"], bar)) else ""
            fk = [o for o in ch if abs(o["T"] - R1) < 1e-6]
            first = int(judge(fk[0]["m"], bar)) if fk else ""
        rows.append({"run_id": rid, "family": fam_pseudo[d], "setting": sp, "level": level,
                     "has_postgrt": int(has["postgrt"]), "has_signoff": int(has["signoff"]),
                     "T0_ns": round(r["T"], 4), "C0_ns": round(C0, 6), "R1_ns": R1,
                     "source_pass": int(judge(r["m"], bar)),
                     "partner_run_id": [x[3] for x in jobs if x[4]["tag"] == p["tag"]][0] if any(x[4]["tag"] == p["tag"] for x in jobs) else "",
                     "partner_T_ns": round(p["T"], 4), "partner_C_ns": round(Cp, 6),
                     "partner_pass": int(judge(p["m"], bar)), "partner_is_R1": int(bool(exact)),
                     "slope": round((Cp - C0) / (p["T"] - r["T"]), 6),
                     "chain_kept_clock_ns": kept, "chain_first_pass": first,
                     "F_obs_ns": passing[0] if passing else "", "F_emp_ns": (round(crossing(pts), 6) if crossing(pts) else ""),
                     "n_targets": len({round(o["T"], 4) for o in rs})})
        for o in others:
            Co = o["T"] - o["m"]["timing__setup__ws"]
            oid = [x[3] for x in jobs if x[4]["tag"] == o["tag"]]
            pairs.append({"run_id": rid, "other_run_id": oid[0] if oid else "", "setting": sp, "family": fam_pseudo[d],
                          "T0_ns": round(r["T"], 4), "C0_ns": round(C0, 6), "T1_ns": round(o["T"], 4), "C1_ns": round(Co, 6),
                          "pass1": int(judge(o["m"], bar)), "slope": round((Co - C0) / (o["T"] - r["T"]), 6)})
    for name, data in (("labels.csv", rows), ("pairs.csv", pairs)):
        with open(os.path.join(a.out, name), "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(data[0].keys()))
            w.writeheader()
            w.writerows(data)
    json.dump({"keys": keys, "families": {v: k for k, v in fam_pseudo.items()},
               "notes": {rid: v[2] for rid, v in results.items()}}, open(a.keyfile, "w"), indent=1)
    print(f"[train] wrote {len(rows)} labelled runs, {len(pairs)} pairs; failed {sum(1 for v in results.values() if not v[1])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
