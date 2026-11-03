#!/usr/bin/env python3
"""Workstream B: download this workstream's artifacts (REST only), keep only the members the analysis needs.

  python3 farm/qa/B/collect.py --run-id ID [--run-id ID ...] --results DIR [--keep-logs]

Evidence (always): sky130 base.sdc [INFO] lines -> <tag>/sdc_lines.txt; ASAP7 finish-report external delays, clock edges,
period_min and the loaded liberty/SDC files -> <tag>/finish_evidence.txt (whole logs kept only with --keep-logs).
Kept per run directory: metrics.json, job.json, host.json, run.json, resolved.json (gzipped), checks/ (gzipped),
logs/*.json and reports/e5_hook.json (ASAP7), constraint.sdc / constraint.orig.sdc (ASAP7), docker.log tail; with
--keep-logs also flow.log.gz (sky130 SDC delay lines). chains/*.json: the latest stage of each chain.
An artifact is taken only once its job has completed. Everything else in the zip is discarded.
"""
from __future__ import annotations

import argparse
import fnmatch
import gzip
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile

REPO = "Avi-Patel-1/beforeroute-farm"
KEEP = ["*/metrics.json", "*/job.json", "*/host.json", "*/run.json", "*/resolved.json", "*/checks/*",
        "*/logs/*.json", "*/reports/e5_hook.json", "*/constraint.sdc", "*/constraint.orig.sdc", "*/docker.log",
        "chains/*.json", "*/make_vars.txt", "*/b_meta.json", "deferred/*.json", "races/*.json"]
LOGS = ["*/flow.log.gz", "*/reports/6_finish.rpt", "*/reports/6_finish.rpt.gz"]


def gh_json(path):
    r = subprocess.run(["gh", "api", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)


SKY_PAT = re.compile(r"(Setting (?:input|output) delay to: .*|Using clock .*|Setting clock uncertainty to: .*|"
                     r"Setting timing derate to: .*|Setting load to: .*)")
ASAP_RPT = re.compile(r"(.*external delay.*|.*clock \S+ \(rise edge\).*|.*period_min = .*)")
ASAP_LOG = re.compile(r"^(read_liberty .*|read_sdc .*)$", re.M)


def evidence(z, names, results):
    """Small evidence files instead of whole logs (audit request: show the constraints the tools actually loaded).
    sky130: base.sdc's own [INFO] lines from flow.log.gz -> <tag>/sdc_lines.txt (unique lines with counts).
    ASAP7: external-delay / clock-edge / period_min lines of reports/6_finish.rpt(.gz) and the read_liberty / read_sdc
    lines of logs/6_report.log.gz -> <tag>/finish_evidence.txt."""
    import collections
    for nm in names:
        parts = nm.split("/")
        if len(parts) < 2:
            continue
        tag = parts[0]
        try:
            if nm.endswith("flow.log.gz") and len(parts) == 2:
                txt = gzip.decompress(z.read(nm)).decode(errors="replace")
                c = collections.Counter(m.strip() for m in SKY_PAT.findall(txt))
                if c:
                    os.makedirs(os.path.join(results, tag), exist_ok=True)
                    with open(os.path.join(results, tag, "sdc_lines.txt"), "w") as fo:
                        for line, n in sorted(c.items()):
                            fo.write(f"{n}\t{line}\n")
            elif parts[1:] in (["reports", "6_finish.rpt"], ["reports", "6_finish.rpt.gz"]):
                raw = z.read(nm)
                txt = (gzip.decompress(raw) if nm.endswith(".gz") else raw).decode(errors="replace")
                ev = sorted(set(" ".join(x.split()) for x in ASAP_RPT.findall(txt)))
                lg = f"{tag}/logs/6_report.log.gz"
                if lg in names:
                    ev += sorted(set(ASAP_LOG.findall(gzip.decompress(z.read(lg)).decode(errors="replace"))))
                os.makedirs(os.path.join(results, tag), exist_ok=True)
                with open(os.path.join(results, tag, "finish_evidence.txt"), "w") as fo:
                    fo.write("\n".join(ev) + "\n")
        except Exception as e:
            print(f"[collect] evidence {nm}: {e!r}")


def chain_rank(c):
    return (c.get("stage", 1), len(c.get("state") or []))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-id", action="append", required=True)
    ap.add_argument("--results", required=True)
    ap.add_argument("--keep-logs", action="store_true")
    ap.add_argument("--tmp", default=os.environ.get("TMPDIR", "/tmp"))
    a = ap.parse_args()
    os.makedirs(a.results, exist_ok=True)
    done_path = os.path.join(a.results, ".b_artifacts_done.json")
    try:
        done = set(json.load(open(done_path)))
    except Exception:
        done = set()
    pats = KEEP + (LOGS if a.keep_logs else [])
    new = 0
    for rid in a.run_id:
        run = gh_json(f"repos/{REPO}/actions/runs/{rid}")
        jobs = {j["name"]: j for j in gh_json(f"repos/{REPO}/actions/runs/{rid}/jobs?per_page=100").get("jobs", [])}
        arts = gh_json(f"repos/{REPO}/actions/runs/{rid}/artifacts?per_page=100").get("artifacts", [])
        for art in arts:
            key = f"{rid}:{art['name']}"
            if key in done or art.get("expired"):
                continue
            if run["status"] != "completed":
                # artifact b-<batch>-<group> / b3-<batch>-<group>: job name "<batch> <group>"
                pref, rest = art["name"].split("-", 1)
                batch, group = rest.split("-", 1) if "-" in rest else (rest, "")
                jn = f"{batch} {group}"
                if group.endswith("spec"):
                    pass
                elif jn not in jobs or jobs[jn]["status"] != "completed":
                    continue
            with tempfile.TemporaryDirectory(dir=a.tmp) as td:
                zp = os.path.join(td, "a.zip")
                with open(zp, "wb") as fo:
                    r = subprocess.run(["gh", "api", f"repos/{REPO}/actions/artifacts/{art['id']}/zip"], stdout=fo,
                                       stderr=subprocess.PIPE)
                if r.returncode != 0:
                    print(f"[collect] {art['name']}: download failed {r.stderr.decode(errors='replace')[:120]}")
                    continue
                with zipfile.ZipFile(zp) as z:
                    for nm in z.namelist():
                        if nm.startswith("/") or ".." in nm.split("/"):
                            raise RuntimeError(f"unsafe path in artifact: {nm}")
                        if nm.endswith("/") or not any(fnmatch.fnmatch(nm, p) for p in pats):
                            continue
                        if nm.startswith("chains/"):
                            c = json.loads(z.read(nm))
                            dst = os.path.join(a.results, nm)
                            os.makedirs(os.path.dirname(dst), exist_ok=True)
                            old = None
                            if os.path.exists(dst):
                                try:
                                    old = json.load(open(dst))
                                except Exception:
                                    old = None
                            if old is None or chain_rank(c) >= chain_rank(old):
                                json.dump(c, open(dst, "w"), indent=1)
                            continue
                        dst = os.path.join(a.results, nm)
                        os.makedirs(os.path.dirname(dst), exist_ok=True)
                        data = z.read(nm)
                        if nm.endswith("docker.log"):
                            data = data[-20000:]
                        if (nm.endswith("resolved.json") or "/checks/" in nm) and not nm.endswith(".gz"):
                            with gzip.open(dst + ".gz", "wb") as fo:
                                fo.write(data)
                        else:
                            with open(dst, "wb") as fo:
                                fo.write(data)
                with zipfile.ZipFile(zp) as z:
                    evidence(z, z.namelist(), a.results)
                tags = {n.split("/")[0] for n in zipfile.ZipFile(zp).namelist() if "/" in n} - {"chains"}
                new += len(tags)
                print(f"[collect] {art['name']}: {len(tags)} run dirs")
            done.add(key)
    json.dump(sorted(done), open(done_path, "w"))
    print(f"[collect] {new} run dirs updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
