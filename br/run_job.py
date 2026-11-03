#!/usr/bin/env python3
"""BeforeRoute worker: run one LibreLane job, extract features + labels, keep a compact result.

Usage:
  run_job.py --design <design_dir> --config <config.json|yaml> --tag <run_tag>
             [--override KEY=JSONVALUE ...] [--overrides-json <file>]
             [--results <dir>] [--jobs 2] [--keep-run] [--pdk-root <dir>]

Steps: (1) write an overlay config (base config + overrides) into the design
dir, (2) run `librelane` to completion, (3) DumpNetsPostGRT on the run,
(4) labels from the nine-corner signoff reports, (5) copy the compact outputs
(nets.jsonl, labels.json, final_nets.json, metrics.json, resolved.json, the
flow log gzipped, a job.json manifest) into <results>/<tag>/ and, unless
--keep-run, delete the run directory.
"""
from __future__ import annotations

import argparse
import gzip
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def load_config(path):
    if path.endswith(".json"):
        return json.load(open(path))
    import yaml

    return yaml.safe_load(open(path))


def _gz_copy(src, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(src, "rb") as fi, gzip.open(dst, "wb", compresslevel=6) as fo:
        shutil.copyfileobj(fi, fo)


def capture(run_dir, results, max_bytes=400 * 1024 * 1024):
    """Experiment E full capture (spec "capture": true), read-only on the finished run: final DEF, SPEF per RC corner,
    mapped netlist, signoff SDC, the post-route and post-GRT STA report trees; all gzipped under <results>/capture/.
    Returns {relative path: bytes} of what was kept."""
    import glob

    cap = os.path.join(results, "capture")
    got = {}

    def keep(src, rel):
        if os.path.getsize(src) > max_bytes:
            got[rel] = f"skipped: {os.path.getsize(src)} bytes"
            return
        dst = os.path.join(cap, rel + ".gz")
        _gz_copy(src, dst)
        got[rel + ".gz"] = os.path.getsize(dst)

    fin = os.path.join(run_dir, "final")
    for f in sorted(glob.glob(os.path.join(fin, "def", "*.def"))):
        keep(f, "final.def")
    for f in sorted(glob.glob(os.path.join(fin, "nl", "*.nl.v"))):
        keep(f, "final.nl.v")
    for f in sorted(glob.glob(os.path.join(fin, "sdc", "*.sdc"))):
        keep(f, "final.sdc")
    for f in sorted(glob.glob(os.path.join(fin, "spef", "*", "*.spef"))):
        keep(f, os.path.join("spef", os.path.basename(os.path.dirname(f)) + ".spef"))
    for step, name in (("*-openroad-stapostpnr", "sta_postpnr"), ("*-openroad-stamidpnr-3", "sta_postgrt")):
        steps = sorted(glob.glob(os.path.join(run_dir, step)))
        if not steps:
            continue
        for f in sorted(glob.glob(os.path.join(steps[-1], "**", "*.rpt"), recursive=True)):
            keep(f, os.path.join(name, os.path.relpath(f, steps[-1])))
    return got


def _ceil05(x):
    import math

    return round(math.ceil(round(x / 0.05, 6)) * 0.05, 2)


def run_chain(spec, a):
    """Experiment E (Addendum 42) registered rebuild chain, run on the runner (spec "chain"):
    source S (T0, claim C0); judge = setup WS >= 0 and hold WS >= 0 (9 corners), route DRC 0, max-slew + max-cap count
    <= drv_bar; a rebuild without metrics fails.
      1. first rebuild at R1 = ceil05(C0);
      2. after a passing rebuild with claim C: rebuild at ceil05(C) while that is below the chain's smallest passing
         clock and above every failed clock of the chain below it;
      3. if the first rebuild fails: step back once to max(ceil05(C1), R1 + 0.05) unless that is not below the
         smallest passing clock (the source's own target if it passed); a failure after that ends the chain;
      4. at most 4 rebuilds; a clock already run in the chain reuses that result. Kept clock = smallest passing clock,
         the source included (None if none passed).
    Rebuild results go to <results>/<tag>/rebuilds/<tag>-<k>/ (per-net dumps removed to keep the artifact small);
    the chain record to <results>/<tag>/chain.json."""
    ch = spec["chain"]
    tag = spec["tag"]
    top = os.path.abspath(os.path.join(a.results, tag))
    reb = os.path.join(top, "rebuilds")
    os.makedirs(reb, exist_ok=True)
    cap = int(ch.get("max_rebuilds", 4))
    bar = ch.get("drv_bar")
    T0, C0 = float(ch["T0"]), float(ch["C0"])
    tried, order = {}, []
    t_start = time.time()

    def drv(m):
        return (m.get("design__max_slew_violation__count") or 0) + (m.get("design__max_cap_violation__count") or 0)

    def build(clk):
        k = len(order) + 1
        sub = f"{tag}-{k}"
        s2 = {"tag": sub, "design": spec["design"], "config": spec["config"],
              "overrides": dict(spec["overrides"], CLOCK_PERIOD=clk)}
        sp = os.path.join(top, f"{sub}.spec.json")
        json.dump(s2, open(sp, "w"), indent=1)
        t1 = time.time()
        subprocess.run([sys.executable, os.path.abspath(__file__), "--job-spec", sp, "--jobs", str(a.jobs),
                        "--results", reb, "--pdk-root", a.pdk_root, "--timeout", str(a.timeout)])
        d = os.path.join(reb, sub)
        m = {}
        try:
            m = json.load(open(os.path.join(d, "metrics.json")))
        except Exception:
            m = {}
        for f in ("nets.jsonl", "nets_signoff.jsonl", "final_nets.json", "nets.jsonl.gz", "nets_signoff.jsonl.gz",
                  "final_nets.json.gz"):
            if os.path.exists(os.path.join(d, f)):
                os.remove(os.path.join(d, f))
        ws, wr, hold = m.get("timing__setup__ws"), m.get("timing__setup_r2r__ws"), m.get("timing__hold__ws")
        drc = m.get("route__drc_errors")
        ok = (ws is not None and ws >= 0 and hold is not None and hold >= 0 and (drc or 0) == 0
              and (bar is None or drv(m) <= bar))
        try:
            jj = json.load(open(os.path.join(d, "job.json")))
        except Exception:
            jj = {}
        rec = {"k": k, "tag": sub, "clock_ns": clk, "ws_ns": ws, "ws_r2r_ns": wr, "hold_ws_ns": hold, "drc": drc,
               "drv": drv(m) if m else None, "claim_ns": (clk - ws) if ws is not None else None, "pass": bool(ok),
               "metrics": ws is not None, "flow_exit": jj.get("flow_exit"), "job_status": jj.get("status"),
               "outcome": "landed" if ws is not None else "no_metrics", "seconds": round(time.time() - t1, 1)}
        tried[round(clk, 4)] = rec
        order.append(rec)
        print(f"[chain] {sub} at {clk} ns: ws {ws} hold {hold} drc {drc} drv {rec['drv']} -> {'PASS' if ok else 'FAIL'}",
              flush=True)
        return rec

    def run_or_reuse(clk):
        r = tried.get(round(clk, 4))
        return (r, False) if r is not None else (build(clk), True)

    smallest = T0 if ch.get("source_pass") else None
    failed = []
    R1 = _ceil05(C0)
    first = build(R1)
    last = None
    if first["pass"]:
        smallest = R1 if smallest is None else min(smallest, R1)
        last = first
    else:
        failed.append(R1)
        step = max(_ceil05(first["claim_ns"]) if first["claim_ns"] is not None else round(R1 + 0.05, 2),
                   round(R1 + 0.05, 2))
        if (smallest is None or step < smallest - 1e-9) and len(order) < cap:
            r2, _ = run_or_reuse(step)
            if r2["pass"]:
                smallest = step if smallest is None else min(smallest, step)
                last = r2
            else:
                failed.append(step)
    while last is not None and len(order) < cap:
        nxt = _ceil05(last["claim_ns"])
        if smallest is not None and nxt >= smallest - 1e-9:
            break
        if any(f >= nxt - 1e-9 and (smallest is None or f < smallest) for f in failed):
            break
        r, new = run_or_reuse(nxt)
        if r["pass"]:
            smallest = nxt if smallest is None else min(smallest, nxt)
            last = r
        else:
            failed.append(nxt)
            break
        if not new:
            break
    out = {"tag": tag, "source_tag": ch.get("source_tag"), "T0_ns": T0, "C0_ns": C0, "R1_ns": R1,
           "source_pass": bool(ch.get("source_pass")), "drv_bar": bar, "rebuilds": order,
           "first_pass": first["pass"], "first_outcome": first["outcome"], "C1_ns": first["claim_ns"],
           "slope": ((first["claim_ns"] - C0) / (R1 - T0)) if first["claim_ns"] is not None and abs(R1 - T0) > 1e-9 else None,
           "kept_clock_ns": smallest, "failed_clocks_ns": failed, "n_rebuilds": len(order),
           "seconds": round(time.time() - t_start, 1), "rule": "Addendum 42 (docs/qa_week/E_PREREG.md)"}
    json.dump(out, open(os.path.join(top, "chain.json"), "w"), indent=1)
    json.dump({"tag": tag, "status": "chain_done", "n_rebuilds": len(order)}, open(os.path.join(top, "job.json"), "w"))
    print(json.dumps(out, indent=1))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job-spec", default=None, help="JSON file with design, config, tag, overrides (overrides CLI values)")
    ap.add_argument("--design", default=None)
    ap.add_argument("--config", default=None)
    ap.add_argument("--tag", default=None)
    ap.add_argument("--override", action="append", default=[])
    ap.add_argument("--overrides-json", default=None)
    ap.add_argument("--results", default=os.path.join(HERE, "..", "results"))
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--keep-run", action="store_true")
    ap.add_argument("--pdk-root", default=os.environ.get("PDK_ROOT", "/home/claude/eda/pdk"))
    ap.add_argument("--timeout", type=int, default=7200)
    a = ap.parse_args()
    spec = {}
    if a.job_spec:
        spec = json.load(open(a.job_spec))
        a.design = a.design or spec["design"]
        a.config = a.config or spec["config"]
        a.tag = a.tag or spec["tag"]
    if not (a.design and a.config and a.tag):
        ap.error("--design, --config and --tag are required (or --job-spec)")
    if spec.get("chain"):
        return run_chain(spec, a)

    design = os.path.abspath(a.design)
    cfg_path = os.path.abspath(a.config) if os.path.isabs(a.config) or os.path.exists(a.config) else os.path.join(design, a.config)
    base = load_config(cfg_path)
    overrides = dict(spec.get("overrides") or {})
    if a.overrides_json:
        overrides.update(json.load(open(a.overrides_json)))
    for ov in a.override:
        k, v = ov.split("=", 1)
        try:
            overrides[k] = json.loads(v)
        except json.JSONDecodeError:
            overrides[k] = v
    cfg = dict(base)
    cfg.update(overrides)
    # keep pdk-specific sub-dicts of YAML configs intact; overrides are top-level
    overlay = os.path.join(design, f"config.{a.tag}.json")
    json.dump(cfg, open(overlay, "w"), indent=1)

    results = os.path.abspath(os.path.join(a.results, a.tag))
    os.makedirs(results, exist_ok=True)
    manifest = {
        "tag": a.tag,
        "design_dir": design,
        "base_config": cfg_path,
        "overrides": overrides,
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "host": os.uname().nodename,
        "jobs": a.jobs,
    }
    run_dir = os.path.join(design, "runs", a.tag)
    if os.path.exists(run_dir):
        shutil.rmtree(run_dir)
    t0 = time.time()
    flow_log = os.path.join(results, "flow.log")
    cmd = ["librelane", "--pdk-root", a.pdk_root, "--manual-pdk", "--run-tag", a.tag, "-j", str(a.jobs), overlay]
    # Optional early stop at global route (spec "prune": {"above": <ns>}): once the mid-PnR STA after global routing
    # (step *-openroad-stamidpnr-3) has written its state, the global-route proxy is CLOCK_PERIOD - its setup WS; if the
    # proxy is above the threshold the flow is stopped before detailed routing. Without "prune" nothing changes.
    prune = spec.get("prune") or None
    pruned = None
    with open(flow_log, "w") as lf:
        if not prune:
            try:
                r = subprocess.run(cmd, cwd=design, stdout=lf, stderr=subprocess.STDOUT, timeout=a.timeout)
                rc = r.returncode
            except subprocess.TimeoutExpired:
                rc = -9
                lf.write("\n[br] TIMEOUT\n")
        else:
            import glob as _glob
            p = subprocess.Popen(cmd, cwd=design, stdout=lf, stderr=subprocess.STDOUT)
            checked = False
            while True:
                try:
                    rc = p.wait(timeout=5)
                    break
                except subprocess.TimeoutExpired:
                    pass
                if time.time() - t0 > a.timeout:
                    p.kill()
                    p.wait()
                    rc = -9
                    lf.write("\n[br] TIMEOUT\n")
                    break
                if checked:
                    continue
                so = sorted(_glob.glob(os.path.join(run_dir, "*-openroad-stamidpnr-3", "state_out.json")))
                if not so:
                    continue
                try:
                    ws = json.load(open(so[0])).get("metrics", {}).get("timing__setup__ws")
                except Exception:
                    continue  # still being written
                checked = True
                period = float(cfg.get("CLOCK_PERIOD"))
                proxy = None if ws is None else period - float(ws)
                manifest["gr_proxy"] = proxy
                manifest["gr_proxy_seconds"] = round(time.time() - t0, 1)
                manifest["prune_above"] = prune.get("above")
                if proxy is not None and prune.get("above") is not None and proxy > float(prune["above"]):
                    pruned = proxy
                    p.terminate()
                    try:
                        p.wait(timeout=60)
                    except subprocess.TimeoutExpired:
                        p.kill()
                        p.wait()
                    rc = -15
                    lf.write(f"\n[br] PRUNED at global route: proxy {proxy:.3f} ns > {prune['above']} ns\n")
                    break
    manifest["flow_exit"] = rc
    manifest["flow_seconds"] = round(time.time() - t0, 1)
    if pruned is not None:
        manifest["status"] = "pruned"
        with open(flow_log, "rb") as fi, gzip.open(flow_log + ".gz", "wb") as fo:
            shutil.copyfileobj(fi, fo)
        os.remove(flow_log)
        json.dump(manifest, open(os.path.join(results, "job.json"), "w"), indent=1)
        if not a.keep_run:
            shutil.rmtree(run_dir, ignore_errors=True)
        print(json.dumps(manifest, indent=1))
        return 0

    def copy_if(src, dst_name):
        if os.path.exists(src):
            shutil.copy2(src, os.path.join(results, dst_name))
            return True
        return False

    final_metrics = os.path.join(run_dir, "final", "metrics.json")
    manifest["flow_completed"] = copy_if(final_metrics, "metrics.json")
    copy_if(os.path.join(run_dir, "resolved.json"), "resolved.json")
    copy_if(os.path.join(run_dir, "error.log"), "error.log")

    status = "flow_failed"
    if manifest["flow_completed"]:
        status = "completed"
        t1 = time.time()
        d = subprocess.run([sys.executable, os.path.join(HERE, "run_dump.py"), run_dir, "--pdk-root", a.pdk_root],
                           capture_output=True, text=True)
        manifest["dump_exit"] = d.returncode
        manifest["dump_seconds"] = round(time.time() - t1, 1)
        open(os.path.join(results, "dump.log"), "w").write(d.stdout[-20000:] + "\n--- stderr ---\n" + d.stderr[-20000:])
        ok1 = copy_if(os.path.join(run_dir, "br-dump-postgrt", "nets.jsonl"), "nets.jsonl")
        copy_if(os.path.join(run_dir, "br-dump-postgrt", "dump_summary.json"), "dump_summary.json")
        # signoff view (final ODB + RCX parasitics): actual per-net slews/caps for all nets
        t1b = time.time()
        d2 = subprocess.run([sys.executable, os.path.join(HERE, "run_dump.py"), run_dir, "--signoff", "--pdk-root", a.pdk_root],
                            capture_output=True, text=True)
        manifest["dump_signoff_exit"] = d2.returncode
        manifest["dump_signoff_seconds"] = round(time.time() - t1b, 1)
        open(os.path.join(results, "dump_signoff.log"), "w").write(d2.stdout[-20000:] + "\n--- stderr ---\n" + d2.stderr[-20000:])
        copy_if(os.path.join(run_dir, "br-dump-signoff", "nets_signoff.jsonl"), "nets_signoff.jsonl")
        t2 = time.time()
        lab = subprocess.run([sys.executable, os.path.join(HERE, "labels.py"), run_dir], capture_output=True, text=True)
        manifest["labels_exit"] = lab.returncode
        manifest["labels_seconds"] = round(time.time() - t2, 1)
        open(os.path.join(results, "labels.log"), "w").write(lab.stdout[-20000:] + "\n--- stderr ---\n" + lab.stderr[-20000:])
        ok2 = copy_if(os.path.join(run_dir, "br-labels", "labels.json"), "labels.json")
        copy_if(os.path.join(run_dir, "br-labels", "final_nets.json"), "final_nets.json")
        if not (ok1 and ok2):
            status = "extract_failed"
        # signoff reports (small) for audit
        import glob

        for rpt in glob.glob(os.path.join(run_dir, "*-openroad-stapostpnr", "*", "checks.rpt")):
            corner = os.path.basename(os.path.dirname(rpt))
            os.makedirs(os.path.join(results, "checks"), exist_ok=True)
            shutil.copy2(rpt, os.path.join(results, "checks", f"{corner}.checks.rpt"))
        if spec.get("capture"):
            t3 = time.time()
            try:
                manifest["capture"] = capture(run_dir, results)
            except Exception as e:  # never lose the run's own results to a capture problem
                manifest["capture_error"] = f"{type(e).__name__}: {e}"
            manifest["capture_seconds"] = round(time.time() - t3, 1)
        for f in ("nets.jsonl", "nets_signoff.jsonl", "final_nets.json"):
            p = os.path.join(results, f)
            if spec.get("capture") and os.path.exists(p):   # keep artifacts small: gzip the per-net dumps
                with open(p, "rb") as fi, gzip.open(p + ".gz", "wb", compresslevel=6) as fo:
                    shutil.copyfileobj(fi, fo)
                os.remove(p)
    # gzip the flow log
    with open(flow_log, "rb") as fi, gzip.open(flow_log + ".gz", "wb") as fo:
        shutil.copyfileobj(fi, fo)
    os.remove(flow_log)
    manifest["status"] = status
    manifest["ended_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    json.dump(manifest, open(os.path.join(results, "job.json"), "w"), indent=1)
    if not a.keep_run and os.path.exists(run_dir):
        shutil.rmtree(run_dir, ignore_errors=True)
    print(json.dumps(manifest, indent=1))
    return 0 if status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
