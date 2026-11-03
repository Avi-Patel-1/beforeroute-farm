#!/usr/bin/env python3
"""AD (TrueClock overnight, experiments A and D): run one group of farm/qa/AD/dispatch.json on a GitHub runner, in the
pinned ORFS image. Derived from farm/qa/E5/run_group.py (Addendum 41, frozen).

A group holds any of
  "runs":   independent flow runs {"tag", "design", "platform", "period" (ps), "vars", "setting", "kind", "arm",
            "abc_d" (0/1, T2b), "retime" (0/1, T3), "stop" ("synth": smoke only)};
  "chains": registered rebuild chains (as E5) {"chain_id", "design", "platform", "setting", "vars", "tag_prefix",
            "winner": {"tag", "period", "claim", "pass"}};
  "await_chains": runner-side top-3 selection and chains for one design on one platform, once its grid has landed:
            {"key", "design", "platform", "grid_tags", "grid_groups", "ranks", "chain_prefix", "arm",
             "max_wait_s"}. The grid runs are read from this job's own results and, for runs other jobs of this
            workflow run made, from their uploaded artifacts (ad-<batch>-<group>), polled through the REST API with
            the job's token. Selection is E5's: the design's 10 grid runs must all have landed (E5's
            --require-complete); top 3 by AutoTuner's score; then E5's chain rule for each listed rank.
plus "num_cores", "timeout_s" and "parallel" (flows run at once; default 1). Every flow: farm/qa/AD/orfs_run.sh in a
fresh container; results/<tag>/ gets run.json (from the container) and job.json (from here).
"""
from __future__ import annotations

import argparse
import json
import os
import platform as _platform
import shutil
import subprocess
import sys
import tempfile
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import adlib  # noqa: E402

REPO = os.path.abspath(os.path.join(HERE, "..", "..", ".."))


def cpu_model() -> str:
    try:
        for line in open("/proc/cpuinfo"):
            if line.startswith("model name"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return _platform.processor() or "?"


def run_one(run: dict, image: str, results: str, num_cores: int, timeout_s: int) -> dict:
    tag = run["tag"]
    out = os.path.join(results, tag)
    os.makedirs(out, exist_ok=True)
    mv = " ".join(f"{k}={v}" for k, v in sorted((run.get("vars") or {}).items()))
    env = {"TAG": tag, "DESIGN": run["design"], "PLATFORM": run.get("platform", "asap7"),
           "PERIOD_PS": str(int(run["period"])), "NUM_CORES": str(num_cores), "MAKE_VARS": mv,
           "RUN_TIMEOUT": str(timeout_s), "AD_ABC_D": str(int(run.get("abc_d", 0))),
           "AD_RETIME": str(int(run.get("retime", 0))), "MAKE_STOP": run.get("stop", "")}
    cmd = ["docker", "run", "--rm", "--name", tag, "-v", f"{REPO}:/work"]
    for k, v in env.items():
        cmd += ["-e", f"{k}={v}"]
    cmd += [image, "bash", "/work/farm/qa/AD/orfs_run.sh"]
    t0 = time.time()
    print(f"[ad] start {tag}: {env['PLATFORM']} {run['design']} {run['period']} ps {mv} abc_d={env['AD_ABC_D']} "
          f"retime={env['AD_RETIME']}", flush=True)
    with open(os.path.join(out, "docker.log"), "w") as lf:
        try:
            rc = subprocess.call(cmd, stdout=lf, stderr=subprocess.STDOUT, timeout=timeout_s + 600)
        except subprocess.TimeoutExpired:
            subprocess.call(["docker", "kill", tag])
            rc = -9
    subprocess.call(["sudo", "chown", "-R", f"{os.getuid()}:{os.getgid()}", out])
    runj = {}
    try:
        runj = json.load(open(os.path.join(out, "run.json")))
    except Exception:
        pass
    job = {"tag": tag, "design": run["design"], "platform": env["PLATFORM"], "period_ps": int(run["period"]),
           "vars": run.get("vars") or {}, "setting": run.get("setting"), "kind": run.get("kind"),
           "arm": run.get("arm"), "chain_id": run.get("chain_id"), "abc_d": int(run.get("abc_d", 0)),
           "retime": int(run.get("retime", 0)), "num_cores": num_cores,
           "status": runj.get("status", "no_run_json"), "docker_rc": rc, "wall_s": round(time.time() - t0, 1),
           "cpu": cpu_model(), "nproc": os.cpu_count(), "image": image, "runner": os.environ.get("RUNNER_NAME"),
           "gh_run_id": os.environ.get("GITHUB_RUN_ID"), "gh_sha": os.environ.get("GITHUB_SHA")}
    json.dump(job, open(os.path.join(out, "job.json"), "w"), indent=1)
    r = adlib.load_run(out)
    print(f"[ad] done  {tag}: status={r['status']} ws={r['ws']} hold={r['hold_ws']} drc={r['drc']} "
          f"claim={r['claim']} pass={r['pass']} synth={r.get('synth_sha1')} ({job['wall_s']:.0f} s)", flush=True)
    return r


def run_chain(ch: dict, image: str, results: str, num_cores: int, timeout_s: int) -> dict:
    w = dict(ch["winner"])
    state = [{"tag": w["tag"], "period": w["period"], "claim": w["claim"], "pass": w["pass"]}]
    log = []
    k = 0
    maxr = int(ch.get("max_rebuilds", adlib.MAX_REBUILDS))
    while True:
        nxt, why = adlib.chain_next(state, maxr)
        log.append({"after": state[-1]["tag"], "next": nxt, "why": why})
        print(f"[ad] chain {ch['chain_id']}: next={nxt} ({why})", flush=True)
        if nxt is None:
            break
        k += 1
        reuse = next((s for s in state if s["period"] == nxt), None)
        if reuse is not None:   # same configuration at the same clock: the flow is deterministic, reuse the result
            state.append(dict(reuse, reused=True))
            continue
        run = {"tag": f"{ch['tag_prefix']}{k}", "design": ch["design"], "platform": ch.get("platform", "asap7"),
               "period": nxt, "vars": ch.get("vars") or {}, "setting": ch.get("setting"), "kind": "rebuild",
               "arm": ch.get("arm"), "chain_id": ch["chain_id"]}
        r = run_one(run, image, results, num_cores, timeout_s)
        state.append({"tag": r["tag"], "period": nxt, "claim": r["claim"], "pass": r["pass"]})
    res = {"chain_id": ch["chain_id"], "design": ch["design"], "platform": ch.get("platform", "asap7"),
           "setting": ch.get("setting"), "arm": ch.get("arm"), "winner": w, "chain": state, "steps": log,
           "kept_clock": adlib.kept_clock(state)}
    os.makedirs(os.path.join(results, "chains"), exist_ok=True)
    json.dump(res, open(os.path.join(results, "chains", ch["chain_id"] + ".json"), "w"), indent=1)
    return res


# ------------------------------------------------------------------ runner-side selection from other jobs' artifacts
def gh_api(path: str, out_path: str | None = None):
    cmd = ["gh", "api", "-H", "Accept: application/vnd.github+json", path]
    if out_path:
        with open(out_path, "wb") as fo:
            r = subprocess.run(cmd, stdout=fo, stderr=subprocess.PIPE)
        return r.returncode == 0
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"gh api {path}: {r.stderr.strip()[:200]}")
    return json.loads(r.stdout)


def fetch_group_artifacts(batch: str, groups: list[str], dest: str, have: set) -> None:
    """Download (once) the uploaded artifacts ad-<batch>-<group> of this workflow run into dest/<group>/."""
    repo, rid = os.environ.get("GITHUB_REPOSITORY"), os.environ.get("GITHUB_RUN_ID")
    if not repo or not rid:
        return
    arts = []
    for page in range(1, 6):
        d = gh_api(f"repos/{repo}/actions/runs/{rid}/artifacts?per_page=100&page={page}")
        arts += d.get("artifacts", [])
        if len(d.get("artifacts", [])) < 100:
            break
    want = {f"ad-{batch}-{g}": g for g in groups}
    for a in arts:
        g = want.get(a["name"])
        if g is None or g in have or a.get("expired"):
            continue
        zp = os.path.join(dest, f"{g}.zip")
        if not gh_api(f"repos/{repo}/actions/artifacts/{a['id']}/zip", zp):
            print(f"[ad] artifact {a['name']}: download failed; will retry", flush=True)
            continue
        ex = os.path.join(dest, g)
        with zipfile.ZipFile(zp) as z:
            for nm in z.namelist():
                if nm.startswith("/") or ".." in nm.split("/"):
                    raise RuntimeError(f"unsafe path in artifact: {nm}")
            z.extractall(ex)
        os.remove(zp)
        have.add(g)
        print(f"[ad] fetched artifact {a['name']}", flush=True)


def find_grid(tags: list[str], roots: list[str]) -> dict:
    found = {}
    for t in tags:
        for root in roots:
            d = os.path.join(root, t)
            if os.path.isfile(os.path.join(d, "run.json")) or os.path.isfile(os.path.join(d, "job.json")):
                found[t] = d
                break
    return found


def await_chains(spec: dict, batch: str, image: str, results: str, num_cores: int, timeout_s: int,
                 par: int) -> None:
    key = spec["key"]
    tags = list(spec["grid_tags"])
    cache = tempfile.mkdtemp(prefix="adgrid-")
    have: set = set()
    t0 = time.time()
    max_wait = int(spec.get("max_wait_s", 10800))
    groups = [g for g in spec.get("grid_groups", [])]

    def landed_now():
        roots = [results] + [os.path.join(cache, g) for g in sorted(have)]
        found = find_grid(tags, roots)
        return {t: d for t, d in found.items() if adlib.load_run(d)["status"] not in ("missing", "no_run_json")}

    while True:
        landed = landed_now()
        if len(landed) == len(tags):
            break
        all_in = all(g in have for g in groups)   # every other grid job has finished and uploaded
        if all_in or time.time() - t0 > max_wait:
            why = "grid incomplete: every grid job finished" if all_in else "grid incomplete after max wait"
            sel = {"key": key, "status": why, "landed": sorted(landed),
                   "missing": sorted(set(tags) - set(landed)), "waited_s": round(time.time() - t0)}
            os.makedirs(os.path.join(results, "chains"), exist_ok=True)
            json.dump(sel, open(os.path.join(results, "chains", f"select-{key.replace('/', '-')}.json"), "w"),
                      indent=1)
            print(f"[ad] {key}: {why}; no chains ({sel['missing']})", flush=True)
            return
        try:
            fetch_group_artifacts(batch, [g for g in groups if g not in have], cache, have)
        except Exception as e:  # transient API trouble: keep polling
            print(f"[ad] {key}: artifact poll error: {e}", flush=True)
        if len(landed_now()) < len(tags) and not all(g in have for g in groups):
            time.sleep(90)
    runs = [adlib.load_run(landed[t]) for t in tags]
    for r, t in zip(runs, tags):   # vars and setting come from the grid run's own job.json
        j = adlib._load(os.path.join(landed[t], "job.json"), {}) or {}
        r["vars"], r["setting"] = j.get("vars") or {}, j.get("setting")
    picks = adlib.top3(runs)
    sel = {"key": key, "status": "selected", "waited_s": round(time.time() - t0),
           "grid": [{"tag": r["tag"], "period": r["period"], "claim": r["claim"], "pass": r["pass"],
                     "score": adlib.tuner_score(r), "status": r["status"]} for r in runs],
           "top3": [r["tag"] for r in picks]}
    os.makedirs(os.path.join(results, "chains"), exist_ok=True)
    json.dump(sel, open(os.path.join(results, "chains", f"select-{key.replace('/', '-')}.json"), "w"), indent=1)
    print(f"[ad] {key}: top 3 by AutoTuner score: {sel['top3']}", flush=True)
    chs = []
    for i, w in enumerate(picks, 1):
        if i not in spec.get("ranks", [1, 2, 3]):
            continue
        chs.append({"chain_id": f"{spec['chain_prefix']}-{i}", "design": spec["design"],
                    "platform": spec["platform"], "setting": w["setting"], "vars": w["vars"], "arm": spec.get("arm"),
                    "tag_prefix": f"{spec['chain_prefix']}-{i}-", "max_rebuilds": spec.get("max_rebuilds", 4),
                    "winner": {"tag": w["tag"], "period": w["period"], "claim": w["claim"], "pass": w["pass"]}})
        print(f"[ad] {chs[-1]['chain_id']}: winner {w['tag']} {w['setting']} T0={w['period']} "
              f"claim={w['claim']:.2f} pass={w['pass']} -> first rebuild at {adlib.ceil_grid(w['claim'])} ps",
              flush=True)
    with ThreadPoolExecutor(max_workers=par) as ex:
        list(ex.map(lambda c: run_chain(c, image, results, num_cores, timeout_s), chs))
    shutil.rmtree(cache, ignore_errors=True)


# ------------------------------------------------------------------ runner-side grid anchor (amendment, AD_PREREG.md)
def wait_for_tags(tags: list[str], groups: list[str], batch: str, results: str, max_wait: int, label: str):
    """Wait until every tag has landed (in this job's results or in the listed groups' artifacts of this workflow
    run). Returns (landed {tag: dir}, complete?)."""
    cache = tempfile.mkdtemp(prefix="adwait-")
    have: set = set()
    t0 = time.time()

    def landed_now():
        roots = [results] + [os.path.join(cache, g) for g in sorted(have)]
        found = find_grid(tags, roots)
        return {t: d for t, d in found.items() if adlib.load_run(d)["status"] not in ("missing", "no_run_json")}

    while True:
        landed = landed_now()
        if len(landed) == len(tags):
            return landed, True
        if all(g in have for g in groups) or time.time() - t0 > max_wait:
            print(f"[ad] {label}: gave up waiting after {round(time.time() - t0)} s; landed {sorted(landed)}",
                  flush=True)
            return landed, False
        try:
            fetch_group_artifacts(batch, [g for g in groups if g not in have], cache, have)
        except Exception as e:
            print(f"[ad] {label}: artifact poll error: {e}", flush=True)
        if len(landed_now()) < len(tags) and not all(g in have for g in groups):
            time.sleep(90)


def anchor_grid(spec: dict, batch: str, image: str, results: str, num_cores: int, timeout_s: int, par: int) -> None:
    """The registered grid anchor computed on the runner: P0 = 5 * round(F_pilot / 5), F_pilot = E5's crossing over
    the design's pilot runs (median claim per target); then this job's share of the design's 10 grid runs."""
    sys.path.insert(0, HERE)
    import ad  # noqa: E402  (crossing, as registered)
    key = spec["key"]
    landed, complete = wait_for_tags(spec["pilot_tags"], spec.get("pilot_groups", []), batch, results,
                                     int(spec.get("max_wait_s", 9000)), key)
    pts = {}
    for t, d in landed.items():
        r = adlib.load_run(d)
        if r["claim"] is not None:
            pts.setdefault(float(r["period"]), []).append(r["claim"])
    rec = {"key": key, "pilots": {str(T): v for T, v in sorted(pts.items())}, "complete": complete}
    os.makedirs(os.path.join(results, "anchors"), exist_ok=True)
    if len(pts) < 2:
        rec["status"] = "no anchor (fewer than 2 pilot claims)"
        json.dump(rec, open(os.path.join(results, "anchors", key.replace("/", "-") + ".json"), "w"), indent=1)
        print(f"[ad] {key}: no anchor; grid not run", flush=True)
        return
    import statistics as st
    F, how = ad.crossing([(T, st.median(pts[T])) for T in sorted(pts)])
    if F is None:
        rec["status"] = f"no anchor ({how})"
        json.dump(rec, open(os.path.join(results, "anchors", key.replace("/", "-") + ".json"), "w"), indent=1)
        print(f"[ad] {key}: no anchor ({how}); grid not run", flush=True)
        return
    P0 = int(5 * round(F / 5))
    runs = []
    k = 0
    for s_ in spec["settings"]:
        for m in s_["mult"]:
            k += 1
            v = dict(spec.get("extra_vars", {}))
            v.update(s_["vars"])
            runs.append({"tag": f"{spec['tag']}-{spec['design']}-{k:03d}", "design": spec["design"],
                         "platform": spec["platform"], "period": int(5 * round(m * P0 / 5)), "vars": v,
                         "setting": s_["setting"], "kind": "grid", "arm": spec["arm"]})
    rec.update(status="anchored", F_pilot=F, how=how, P0=P0, grid=[(r["tag"], r["setting"], r["period"]) for r in runs])
    json.dump(rec, open(os.path.join(results, "anchors", key.replace("/", "-") + ".json"), "w"), indent=1)
    mine = [runs[i] for i in spec["share"] if i < len(runs)]
    print(f"[ad] {key}: F_pilot {F:.1f} ({how}) -> P0 {P0}; this job runs {[(r['tag'], r['period']) for r in mine]}",
          flush=True)
    with ThreadPoolExecutor(max_workers=par) as ex:
        list(ex.map(lambda r: run_one(r, image, results, num_cores, timeout_s), mine))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", required=True)
    ap.add_argument("--group", required=True)
    ap.add_argument("--image", required=True)
    ap.add_argument("--results", default="results")
    a = ap.parse_args()
    spec = json.load(open(a.spec))
    grp = next(g for g in spec["groups"] if g["name"] == a.group)
    results = os.path.abspath(a.results)
    os.makedirs(results, exist_ok=True)
    nc = int(grp.get("num_cores", 4))
    to = int(grp.get("timeout_s", 3 * 3600))
    par = int(grp.get("parallel", 1))
    print(f"[ad] batch {spec['batch']} group {a.group}: cpu={cpu_model()} nproc={os.cpu_count()} num_cores={nc} "
          f"parallel={par}", flush=True)
    with ThreadPoolExecutor(max_workers=par) as ex:
        if grp.get("runs"):
            list(ex.map(lambda r: run_one(r, a.image, results, nc, to), grp["runs"]))
        if grp.get("chains"):
            list(ex.map(lambda c: run_chain(c, a.image, results, nc, to), grp["chains"]))
    for an in grp.get("anchor_grid", []):
        anchor_grid(an, spec["batch"], a.image, results, nc, to, par)
    for aw in grp.get("await_chains", []):
        await_chains(aw, spec["batch"], a.image, results, nc, to, par)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
