#!/usr/bin/env python3
"""E5b (Addendum 42): 2 nm smoke test of TrueClock's claimed-clock rule on the GT2N kit (ORFS gcd).

Subcommands
  plan                          print GitHub step outputs (tags, batch, chain flags) from jobs.json
  run-job --tag T --out D       run job T's listed clock targets one after another (runner side)
  chain --sweep D --out D       pick the best passing sweep run and run the rebuild chain (runner side)
  table D...                    print every metrics.json found under the given directories (local)
  selftest                      check the chain rule on synthetic runs (local)

Definitions (registered in docs/qa_week/E5b_PREREG.md; its SHA-256 is farm/qa/E5b/PREREG.sha256):
  worst setup slack (ws) comes from ORFS's post-route finish report (6_finish.rpt: OpenRCX-extracted SPEF,
  OpenSTA, the kit's single TT 0.7 V 25 C corner); claim = target period - ws; a run is valid when it was
  detail-routed and has a finish timing report; it passes when it is valid and ws >= 0.
"""
import argparse
import gzip
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
JOBS = HERE / "jobs.json"
PLATFORM = "gt2n_compat_bspdn_proxy"
DESIGN = "gcd"
VARIANT = "base"
KIT_IN_CONTAINER = "/work/kit/gt2n_openroad_run"
RUN_TIMEOUT_S = 90 * 60


# ----------------------------------------------------------------------------------------------- rule
def ceil_grid(x, grid):
    """Round x (ps) up to the grid; tolerant of float noise in report values."""
    return int(math.ceil(round(x / grid, 6))) * grid


def is_pass(r):
    return bool(r and r.get("valid") and r.get("ws_setup_ps") is not None and r["ws_setup_ps"] >= 0)


def select_best(runs):
    """Best passing run: smallest claimed clock among passing runs (ties: smaller target)."""
    ok = [r for r in runs if is_pass(r)]
    if not ok:
        return None
    return min(ok, key=lambda r: (r["claim_ps"], r["period_ps"]))


def brief(r):
    keys = ("batch", "tag", "run", "period_ps", "ws_setup_ps", "claim_ps", "ws_hold_ps", "drt_violations",
            "valid", "status")
    out = {k: r.get(k) for k in keys}
    out["pass"] = is_pass(r)
    return out


def run_chain(best, grid, max_rebuilds, do_run):
    """Registered rebuild chain.

    1. First rebuild at c1 = ceil_grid(claim of the best passing run).
    2. While a rebuild passes, rebuild at ceil_grid(its claim) if that is below its own clock and not tried yet.
    3. If the first rebuild fails, step back once to max(ceil_grid(its claim), c1 + grid) if that is below the
       best run's clock; a passing step-back continues as in 2.
    4. At most max_rebuilds rebuilds in all. The kept clock is the last passing clock (the best run's own
       clock if no rebuild passes).
    do_run(period_ps, label) -> metrics dict.
    """
    trail = {"grid_ps": grid, "max_rebuilds": max_rebuilds, "start": brief(best), "steps": []}
    last_pass = best
    c = ceil_grid(best["claim_ps"], grid)
    if c >= best["period_ps"]:
        trail["stop"] = "claim rounds up to the best run's own clock; nothing to rebuild"
        trail["claim_held"] = None
        trail["kept_ps"] = best["period_ps"]
        return trail
    tried = set()
    step_back_used = False
    role = "first"
    n = 0
    while True:
        n += 1
        r = do_run(c, "r%d" % n)
        tried.add(c)
        step = brief(r)
        step.update(n=n, role=role, target_ps=c)
        trail["steps"].append(step)
        if is_pass(r):
            last_pass = r
            nxt = ceil_grid(r["claim_ps"], grid)
            if n >= max_rebuilds:
                trail["stop"] = "rebuild limit reached"
                break
            if nxt >= r["period_ps"]:
                trail["stop"] = "claim rounds up to the last passing clock (converged)"
                break
            if nxt in tried:
                trail["stop"] = "next target already tried"
                break
            c, role = nxt, "re-run"
        else:
            if n == 1 and not step_back_used:
                step_back_used = True
                if n >= max_rebuilds:
                    trail["stop"] = "rebuild limit reached"
                    break
                fail_claim = r.get("claim_ps") if r.get("valid") else None
                sb = c + grid if fail_claim is None else max(ceil_grid(fail_claim, grid), c + grid)
                if sb >= best["period_ps"]:
                    trail["stop"] = "first rebuild failed; step-back target not below the best run's clock"
                    break
                if sb in tried:
                    trail["stop"] = "first rebuild failed; step-back target already tried"
                    break
                c, role = sb, "step-back"
            else:
                trail["stop"] = "rebuild failed"
                break
    first = trail["steps"][0] if trail["steps"] else None
    trail["claim_held"] = bool(first and first["pass"])
    trail["kept_ps"] = last_pass["period_ps"]
    passing = [s["target_ps"] for s in trail["steps"] if s["pass"]]
    trail["first_passing_rebuild_ps"] = passing[0] if passing else None
    if passing:
        trail["more_clock_from_rebuilding_again"] = round(passing[0] / trail["kept_ps"], 4)
    trail["best_run_clock_over_kept"] = round(best["period_ps"] / trail["kept_ps"], 4)
    return trail


# ----------------------------------------------------------------------------------------------- parsing
def _num(pattern, text, cast=float, last=False):
    hits = re.findall(pattern, text)
    if not hits:
        return None
    try:
        return cast(hits[-1] if last else hits[0])
    except ValueError:
        return None


def _read(p):
    try:
        return Path(p).read_text(errors="replace")
    except OSError:
        return ""


def _load_json(p):
    try:
        return json.loads(Path(p).read_text())
    except (OSError, ValueError):
        return {}


def parse_run(rd, period_ps):
    w = rd / "work"
    rep = w / "reports" / PLATFORM / DESIGN / VARIANT
    logs = w / "logs" / PLATFORM / DESIGN / VARIANT
    res = w / "results" / PLATFORM / DESIGN / VARIANT
    m = {"period_ps": period_ps}

    fin = _read(rep / "6_finish.rpt")
    m["finish_report"] = bool(fin)
    m["ws_setup_ps"] = _num(r"worst slack max\s+(-?[0-9.]+(?:e[-+]?\d+)?)", fin)
    m["tns_setup_ps"] = _num(r"tns max\s+(-?[0-9.]+(?:e[-+]?\d+)?)", fin)
    m["period_min_ps"] = _num(r"period_min\s*=\s*(-?[0-9.]+)", fin)
    m["fmax_mhz_report"] = _num(r"fmax\s*=\s*(-?[0-9.]+|inf)", fin)
    m["setup_violation_count"] = _num(r"setup violation count\s+(\d+)", fin, int)
    m["hold_violation_count"] = _num(r"hold violation count\s+(\d+)", fin, int)
    m["max_slew_violations"] = _num(r"max slew violation count\s+(\d+)", fin, int)
    m["max_cap_violations"] = _num(r"max cap violation count\s+(\d+)", fin, int)
    m["max_fanout_violations"] = _num(r"max fanout violation count\s+(\d+)", fin, int)
    # the worst setup path (start/end points), for the record
    mx = fin.split("report_checks -path_delay max", 1)
    if len(mx) == 2:
        m["worst_path_start"] = (re.search(r"Startpoint:\s*(\S+)", mx[1]) or [None, None])[1]
        m["worst_path_end"] = (re.search(r"Endpoint:\s*(\S+)", mx[1]) or [None, None])[1]

    fj = _load_json(logs / "6_report.json")
    m["ws_hold_ps"] = fj.get("finish__timing__hold__ws")
    if m["ws_setup_ps"] is None and isinstance(fj.get("finish__timing__setup__ws"), (int, float)):
        m["ws_setup_ps"] = fj["finish__timing__setup__ws"]
    for k in ("finish__design__instance__count", "finish__design__instance__area",
              "finish__design__instance__utilization", "finish__design__instance__count__stdcell",
              "finish__timing__setup__ws", "finish__timing__hold__ws", "finish__timing__setup__tns",
              "finish__timing__hold__tns", "finish__power__total"):
        if k in fj:
            m[k] = fj[k]

    rj = _load_json(logs / "5_2_route.json")
    m["route_metrics"] = {k: v for k, v in rj.items() if isinstance(v, (int, float))}
    rlog = _read(logs / "5_2_route.log")
    m["drt_violations"] = _num(r"Number of violations\s*=\s*(\d+)", rlog, int, last=True)
    for k in ("detailedroute__route__drc_errors", "detailedroute__route__drc_errors__count"):
        if m["drt_violations"] is None and isinstance(rj.get(k), int):
            m["drt_violations"] = rj[k]
    m["unrouted_error"] = "Design has unrouted nets" in rlog
    m["routed"] = (res / "5_2_route.odb").exists() and not m["unrouted_error"]

    syn = _read(rep / "synth_stat.txt")
    m["synth_cells"] = _num(r"Number of cells:?\s+(\d+)", syn, int, last=True)
    m["synth_area_um2"] = _num(r"Chip area for (?:top )?module.*?:\s*([0-9.]+)", syn, last=True)

    elapsed = {}
    for lf in sorted(logs.glob("*.log")):
        e = re.findall(r"Elapsed time: ([0-9:.]+)\[h:\]min:sec", _read(lf))
        if e:
            parts = [float(x) for x in e[-1].split(":")]
            secs = 0.0
            for x in parts:
                secs = secs * 60 + x
            elapsed[lf.stem] = round(secs, 1)
    m["stage_elapsed_s"] = elapsed

    m["valid"] = bool(m["routed"] and m["finish_report"] and m["ws_setup_ps"] is not None)
    m["claim_ps"] = round(period_ps - m["ws_setup_ps"], 4) if m["ws_setup_ps"] is not None else None
    m["pass"] = is_pass(m)
    return m


def prune(rd):
    """Keep logs, reports, the final netlist/SDC/SPEF (gzipped); drop databases and layouts."""
    w = rd / "work"
    shutil.rmtree(w / "objects", ignore_errors=True)
    for p in list(w.rglob("*")):
        if not p.is_file():
            continue
        if p.suffix in (".odb", ".gds", ".def", ".oas") or p.name.endswith((".gds.gz", ".odb.gz")):
            p.unlink()
        elif p.suffix in (".spef", ".v", ".log", ".rpt", ".sdc") and p.stat().st_size > 512 * 1024:
            with open(p, "rb") as fi, gzip.open(str(p) + ".gz", "wb") as fo:
                shutil.copyfileobj(fi, fo)
            p.unlink()


# ----------------------------------------------------------------------------------------------- running
def fmt_period(p):
    return str(int(p)) if float(p).is_integer() else ("%.3f" % p).rstrip("0").rstrip(".")


def run_one(ws, rel, period_ps, meta):
    image = os.environ["IMAGE"]
    rd = ws / rel
    rd.mkdir(parents=True, exist_ok=False)
    shutil.copy(HERE / "gcd_gt2n_config.mk", rd / "config.mk")
    sdc = (HERE / "constraint.sdc.in").read_text().replace("@CLK_PERIOD_PS@", fmt_period(period_ps))
    (rd / "constraint.sdc").write_text(sdc)
    uid, gid = os.getuid(), os.getgid()
    cin = "/work/" + rel
    nproc = os.cpu_count() or 4
    make = ("make -f /OpenROAD-flow-scripts/flow/Makefile DESIGN_CONFIG=%s/config.mk WORK_HOME=%s/work "
            "CONTAINER_PROJ=%s GT2N_KIT=%s NUM_CORES=%d finish" % (cin, cin, KIT_IN_CONTAINER, KIT_IN_CONTAINER, nproc))
    inner = ("cd /OpenROAD-flow-scripts/flow && . ../env.sh >/dev/null 2>&1; %s; rc=$?; "
             "chown -R %d:%d %s; exit $rc" % (make, uid, gid, cin))
    name = "e5b-" + re.sub(r"[^A-Za-z0-9_.-]", "-", rel)[-60:]
    cmd = ["docker", "run", "--rm", "--name", name, "-v", "%s:/work" % ws, "-e", "HOME=/tmp", image, "bash", "-c", inner]
    print("[e5b] %s: target %s ps" % (rel, fmt_period(period_ps)), flush=True)
    t0 = time.time()
    with open(rd / "make.log", "w") as log:
        try:
            rc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=RUN_TIMEOUT_S).returncode
            status = "ok" if rc == 0 else "flow_error"
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", name])
            subprocess.run(["docker", "run", "--rm", "-v", "%s:/work" % ws, image, "chown", "-R", "%d:%d" % (uid, gid), cin])
            rc, status = None, "timeout"
    m = parse_run(rd, period_ps)
    m.update(meta)
    m.update(status=status, make_rc=rc, wall_s=round(time.time() - t0, 1), image=image,
             gt2n_commit=os.environ.get("GT2N_COMMIT"), kit_sha256=os.environ.get("KIT_SHA256"),
             github_run_id=os.environ.get("GITHUB_RUN_ID"), github_sha=os.environ.get("GITHUB_SHA"))
    if status != "ok" or not m["valid"]:
        tail = _read(rd / "make.log").splitlines()[-40:]
        m["make_log_tail"] = tail
    prune(rd)
    (rd / "metrics.json").write_text(json.dumps(m, indent=1, sort_keys=True))
    print("[e5b] %s: status=%s valid=%s ws=%s claim=%s hold=%s drt=%s wall=%.0fs" % (
        rel, status, m["valid"], m["ws_setup_ps"], m["claim_ps"], m["ws_hold_ps"], m["drt_violations"],
        m["wall_s"]), flush=True)
    return m


def jobs_spec():
    return json.loads(JOBS.read_text())


def cmd_plan(_a):
    d = jobs_spec()
    batch = d["batch"]
    tags = [j["tag"] for j in d.get("jobs", [])]
    if len(tags) > 4 or len(set(tags)) != len(tags) or any(not t.startswith(batch + "-") for t in tags):
        sys.exit("jobs.json: at most 4 unique tags, each starting with '<batch>-'")
    ch = d.get("chain") or {}
    print("tags=" + json.dumps(tags))
    print("batch=" + batch)
    print("chain=" + ("true" if ch else "false"))
    print("sweep_batch=" + str(ch.get("sweep_batch", batch)))
    print("sweep_run_id=" + str(ch.get("sweep_run_id", "")))


def cmd_run_job(a):
    d = jobs_spec()
    job = next(j for j in d["jobs"] if j["tag"] == a.tag)
    ws = Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd())).resolve()
    out = []
    for r in job["runs"]:
        rel = "%s/%s" % (a.out.strip("/"), r["name"])
        meta = {"batch": d["batch"], "tag": a.tag, "run": r["name"], "registered": bool(d.get("registered"))}
        out.append(run_one(ws, rel, r["period_ps"], meta))
    print(json.dumps([brief(m) for m in out], indent=1))


def cmd_chain(a):
    d = jobs_spec()
    cfg = d["chain"]
    sweep_batch = cfg.get("sweep_batch", d["batch"])
    runs = []
    for p in sorted(Path(a.sweep).rglob("metrics.json")):
        m = _load_json(p)
        if m.get("batch") == sweep_batch and m.get("tag") != "chain":
            runs.append(m)
    ws = Path(os.environ.get("GITHUB_WORKSPACE", os.getcwd())).resolve()
    outdir = ws / a.out
    outdir.mkdir(parents=True, exist_ok=True)
    best = select_best(runs)
    head = {"sweep_batch": sweep_batch, "sweep": [brief(r) for r in sorted(runs, key=lambda r: r["period_ps"])]}
    if best is None:
        trail = dict(head, stop="no passing sweep run", claim_held=None)
    else:
        def do_run(period, label):
            rel = "%s/%s_t%s" % (a.out.strip("/"), label, fmt_period(period))
            meta = {"batch": d["batch"], "tag": "chain", "run": "%s_t%s" % (label, fmt_period(period)),
                    "registered": bool(d.get("registered")), "chain_from": best.get("tag") + "/" + best.get("run")}
            return run_one(ws, rel, period, meta)
        trail = dict(head, **run_chain(best, cfg.get("grid_ps", 1), cfg.get("max_rebuilds", 4), do_run))
    (outdir / "chain.json").write_text(json.dumps(trail, indent=1))
    print(json.dumps(trail, indent=1))


def cmd_table(a):
    rows = []
    for d in a.dirs:
        for p in sorted(Path(d).rglob("metrics.json")):
            rows.append(_load_json(p))
    rows.sort(key=lambda r: (str(r.get("batch")), str(r.get("tag")), r.get("period_ps") or 0))
    print("%-10s %-22s %-14s %7s %9s %9s %8s %5s %5s %s" % (
        "batch", "tag", "run", "T_ps", "ws_ps", "claim_ps", "hold", "drt", "pass", "status"))
    for r in rows:
        print("%-10s %-22s %-14s %7s %9s %9s %8s %5s %5s %s" % (
            r.get("batch"), r.get("tag"), r.get("run"), r.get("period_ps"), r.get("ws_setup_ps"),
            r.get("claim_ps"), r.get("ws_hold_ps"), r.get("drt_violations"), is_pass(r), r.get("status")))


def cmd_selftest(_a):
    def fake(model):
        def do_run(t, label):
            ws = model(t)
            return {"period_ps": t, "ws_setup_ps": ws, "claim_ps": t - ws, "valid": True, "run": label}
        return do_run
    best = {"period_ps": 700, "ws_setup_ps": 50.0, "claim_ps": 650.0, "valid": True, "run": "b"}
    # port-limited path: claim = 0.2 T + d with d = 520 -> fixed point 650
    t1 = run_chain(best, 1, 4, fake(lambda t: t - (0.2 * t + 520)))
    assert t1["claim_held"] and t1["kept_ps"] == 650, t1
    # first rebuild fails by 10 ps, the step-back passes, then the chain converges at 658
    t2 = run_chain(best, 1, 4, fake(lambda t: -10.0 if t == 650 else t - 658.0))
    assert not t2["claim_held"] and [s["role"] for s in t2["steps"]] == ["first", "step-back", "re-run"], t2
    assert t2["steps"][1]["target_ps"] == 660 and t2["kept_ps"] == 658, t2
    # every rebuild fails: kept clock is the best run's own
    t3 = run_chain(best, 1, 4, fake(lambda t: -5.0))
    assert t3["kept_ps"] == 700 and len(t3["steps"]) == 2, t3
    # chain capped at 4 rebuilds
    t4 = run_chain(best, 1, 4, fake(lambda t: 30.0))
    assert len(t4["steps"]) == 4 and t4["kept_ps"] == 560, t4
    assert select_best([best, dict(best, period_ps=800, claim_ps=640.0, ws_setup_ps=-1.0)]) is best
    print("selftest ok")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("plan")
    p = sub.add_parser("run-job")
    p.add_argument("--tag", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("chain")
    p.add_argument("--sweep", required=True)
    p.add_argument("--out", required=True)
    p = sub.add_parser("table")
    p.add_argument("dirs", nargs="+")
    sub.add_parser("selftest")
    a = ap.parse_args()
    {"plan": cmd_plan, "run-job": cmd_run_job, "chain": cmd_chain, "table": cmd_table,
     "selftest": cmd_selftest}[a.cmd](a)


if __name__ == "__main__":
    main()
