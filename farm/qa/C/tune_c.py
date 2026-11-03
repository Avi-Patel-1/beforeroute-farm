#!/usr/bin/env python3
"""Experiment C ("method, not model"; docs/qa_week/C_PREREG.md): race driver for the new arms. Launch phase only.

Rule races (lens A37): Addendum 35's 10 races (5 designs x seeds 1, 2), new arms, each a frozen policy that TPE searches
under for 4 rounds of 2 runs, then closure + re-run chain (Amendment 32.2), exactly as A35's arm g:
  s  scores-only Opus 5.5 (prompts farm/qa/C/prompts/rule-*/round1.md, one fresh instance per race)
  m  m9: Qwen3.5-9B on a GitHub-hosted runner, reading g's prompt bytes (workflow c_m9.yml)
  d  the lens's arm c, the four-line script (clib.script_pins); tag letter d because c and k are the chain/closure letters
Proposer races (lens A38): Addendum 32's 7 designs, new arm p (the lens's S): a fresh Opus 5.5 instance per round proposes
2 full settings from the scores-only prompt (4 rounds), then closure + chain as Amendment 32.2.
Reused unchanged: tune_a35 (study, warm start, ask_round, tell, closure_jobs, fixed_point), tune_a32 (start set, run
summaries, clamp, chain rules, tell, fixed_point), tune_a27 (suggest, specs). Overridden here only: state paths and tag
prefixes (xm = rule races, xn = proposer races), the arm list, where policies come from, and git/dispatch: specs are
committed to branch qa-c-method and sent as ONE farm.yml run at a time (--ref qa-c-method, max_parallel = the share).
Usage (each step is idempotent; run from the worktree root):
  tune_c.py --init                         warm-start the 30 rule studies (no runs)
  tune_c.py --script                       write and ingest the 10 script rule files (arm d)
  tune_c.py --m9-dispatch --share N        push farm/qa/C/m9/dispatch.json (10 calls) -> workflow c_m9.yml
  tune_c.py --m9-ingest                    download that run's artifacts and ingest the 10 m9 rule files
  tune_c.py --opus-ingest                  ingest Opus replies found in the hand-off folder (rule s, proposer p)
  tune_c.py --prop-prompts                 write the proposer prompts that are due (rounds 2-4) for the coordinator
  tune_c.py --step --share N               collect our results, tell, ask due rounds, closure/chain, send one farm run
  tune_c.py --status                       what is due, running, waiting
  add --dry-run to any of them: nothing is committed, pushed or dispatched; specs go to results/tune_x?/dry_jobs
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import shutil
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import clib as C  # noqa: E402
import make_prompts as MP  # noqa: E402

T, A, B, R = C.T, C.A, C.B, C.R
sys.path.insert(0, C.FARM)
import collect as CO  # noqa: E402

BRANCH = "qa-c-method"
REPO = T.REPO
EXP = {"rule": ("xm", "tune_xm", ["s", "m", "d"]), "prop": ("xn", "tune_xn", ["p"])}
RUNS = os.path.join(T.ROOT, "results", "tune_xm", "farm_runs.json")
MAX_RESEND = 2
DRY = {"on": False}


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sh(cmd, check=False):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=T.ROOT)
    if check and r.returncode != 0:
        raise SystemExit(f"{' '.join(cmd[:4])}...: {r.stderr[-400:]}")
    return r


def use(exp):
    pre, sub, arms = EXP[exp]
    A.PREFIX = pre
    A.TUNE = os.path.join(T.ROOT, "results", sub)
    A.STATE = os.path.join(A.TUNE, "state.json")
    A.DRY["on"] = T.DRY["on"] = DRY["on"]
    if exp == "rule":
        R.ARMS = list(arms)
        R.pins_for = pins_for


def load(exp):
    use(exp)
    path = os.path.join(A.TUNE, "dry", "state.json") if DRY["on"] else A.STATE
    st = A.load(path, {"tags": {}, "policies": {}, "replies": {}})
    for k in ("tags", "policies", "replies"):
        st.setdefault(k, {})
    return st


def save(st):
    if DRY["on"]:
        os.makedirs(os.path.join(A.TUNE, "dry"), exist_ok=True)
        json.dump(st, open(os.path.join(A.TUNE, "dry", "state.json"), "w"), indent=1)
        return
    A.save(st)


def pins_for(st, d, s, x, k):
    pol = st["policies"].get(R.pkey(d, s, x))
    return None if pol is None else dict(pol["pins"])


# ---------------------------------------------------------------- git and dispatch (branch qa-c-method only)

def commit_push(paths, msg):
    """Commit the given paths on qa-c-method and push it. Never touches main."""
    if DRY["on"] or not paths:
        print(f"[C] {'dry run: would commit' if DRY['on'] else 'nothing to commit'} {len(paths)} files: {msg}")
        return True
    head = sh(["git", "rev-parse", "--abbrev-ref", "HEAD"]).stdout.strip()
    if head != BRANCH:
        raise SystemExit(f"refusing to commit: HEAD is {head}, not {BRANCH}")
    sh(["git", "add", "-f", "--"] + sorted(set(paths)), check=True)
    body = (msg + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\n"
            "Claude-Session: https://claude.ai/code/session_016XcZ7Zp4en4cWPeoAqbHJG")
    r = sh(["git", "commit", "-q", "-m", body])
    if r.returncode != 0 and "nothing to commit" not in (r.stdout + r.stderr):
        print(f"[C] commit failed: {r.stderr[-300:]}")
        return False
    for _ in range(5):
        sh(["git", "pull", "-q", "--rebase", "origin", BRANCH])
        if sh(["git", "push", "-q", "origin", BRANCH]).returncode == 0:
            return True
        time.sleep(3)
    print("[C] push failed 5 times")
    return False


def runs():
    return A.load(RUNS, {"farm": [], "m9": []})


def save_runs(rr):
    if not DRY["on"]:
        os.makedirs(os.path.dirname(RUNS), exist_ok=True)
        json.dump(rr, open(RUNS, "w"), indent=1)


def run_status(rid):
    r = sh(["gh", "run", "view", str(rid), "-R", REPO, "--json", "status,conclusion"])
    try:
        return json.loads(r.stdout)
    except Exception:  # noqa: BLE001
        return {"status": "unknown"}


def active_farm_run(rr, lane):
    for e in reversed(rr["farm"]):
        if e.get("done") or (lane != "both" and e.get("lane", "both") not in (lane, "both")):
            continue
        s = run_status(e["id"])
        if s.get("status") == "completed":
            e["done"] = True
            continue
        return e
    return None


def newest_run(workflow, since):
    """The newest run of `workflow` on our branch created after `since` (minus 2 min for clock skew)."""
    t = (datetime.datetime.strptime(since, "%Y-%m-%dT%H:%M:%SZ") - datetime.timedelta(minutes=2)).strftime("%Y-%m-%dT%H:%M:%SZ")
    r = sh(["gh", "run", "list", "-R", REPO, "-w", workflow, "-b", BRANCH, "--limit", "5", "--json",
            "databaseId,createdAt,status"])
    try:
        rows = [x for x in json.loads(r.stdout) if x["createdAt"] >= t]
    except Exception:  # noqa: BLE001
        rows = []
    return max(rows, key=lambda x: x["createdAt"])["databaseId"] if rows else None


def dispatch(tags, share):
    if DRY["on"]:
        print(f"[C] dry run: would dispatch {len(tags)} jobs (max_parallel {share}) from {BRANCH}: {tags[:4]}...")
        return None
    t0 = now()
    r = sh(["gh", "workflow", "run", "farm.yml", "-R", REPO, "--ref", BRANCH, "-f", f"tags={json.dumps(tags)}",
            "-f", f"max_parallel={share}"])
    if r.returncode != 0:
        print(f"[C] dispatch failed: {r.stderr[-300:]}")
        return False
    for _ in range(20):
        time.sleep(3)
        rid = newest_run("farm.yml", t0)
        if rid:
            return rid
    return 0


# ---------------------------------------------------------------- results: collect only our own tags

def our_tags():
    out = {}
    for exp in ("rule", "prop"):
        st = load(exp)
        for t, v in st["tags"].items():
            out[t] = (exp, v)
    return out


def collect_mine(rr):
    """Download result-<tag> artifacts of our farm runs for tags without a local result; re-queue lost runs."""
    got, cache = 0, {}
    for e in rr["farm"]:
        if e.get("collected"):
            continue
        st_run = run_status(e["id"])       # read before downloading: a run completed now has all its artifacts
        absent = []
        for t in e["tags"]:
            dest = os.path.join(T.ROOT, "results", t)
            if os.path.exists(os.path.join(dest, "job.json")):
                continue
            fresh = not os.path.exists(dest)
            os.makedirs(dest, exist_ok=True)
            ok = CO.download_artifact(REPO, e["id"], f"result-{t}", dest, cache)
            if ok is True and os.path.exists(os.path.join(dest, "job.json")):
                got += 1
                continue
            if fresh and not os.listdir(dest):
                os.rmdir(dest)
            if ok is True or ok == "no such artifact":
                absent.append(t)               # the job left no artifact or no job.json: infrastructure loss
            else:
                print(f"[C] {t}: download not done ({ok}); retried next step")
        if st_run.get("status") == "completed" and not [t for t in e["tags"] if t not in absent and not
                                                        os.path.exists(os.path.join(T.ROOT, "results", t, "job.json"))]:
            if absent:
                requeue(absent)
            e["collected"] = True
    save_runs(rr)
    print(f"[C] collected {got} new results")
    return got


def requeue(tags):
    """A run stopped by infrastructure (no job.json) is re-sent, at most MAX_RESEND times; then it counts as a failed run."""
    for exp in ("rule", "prop"):
        st = load(exp)
        ch = False
        for t in tags:
            v = st["tags"].get(t)
            if not v or v["status"] != "dispatched":
                continue
            v["resent"] = v.get("resent", 0) + 1
            if v["resent"] <= MAX_RESEND:
                v["status"] = "pending"
                print(f"[C] {t}: no result after its farm run; re-sent ({v['resent']}/{MAX_RESEND})")
            else:
                v.update({"status": "failed", "teff": None, "constraints": [1e3, 1e3, 1e3], "feasible": False,
                          "landed_at": now(), "lost": True})
                print(f"[C] {t}: lost {MAX_RESEND + 1} times; counted as a failed run")
            ch = True
        if ch:
            save(st)


# ---------------------------------------------------------------- rule races: policies

def set_policy(st, d, s, x, raw, source, reply, reask_raw=None, reask_file=None, final=False):
    v = C.validate(raw)
    rec = {"source": source, "reply": reply, "decided_at": now(), "malformed_first": not v["ok"]}
    pol = v if v["ok"] else None
    if not v["ok"]:
        if reask_raw is not None:
            v2 = C.validate(reask_raw)
            rec["reask"] = reask_file
            pol = v2 if v2["ok"] else None
            rec["malformed_final"] = not v2["ok"]
        elif not final:
            print(f"[C] {d} s{s} arm {x}: reply unreadable ({v['error']}); one re-ask is due")
            return False
        else:
            rec["malformed_final"] = True
    rec.update({"pins": pol["pins"] if pol else {}, "rationale": pol["rationale"] if pol else "",
                "log": pol["log"] if pol else [], "error": None if v["ok"] else v.get("error")})
    st["policies"][R.pkey(d, s, x)] = rec
    print(f"[C] {d} s{s} arm {x} ({source}): pins {json.dumps(rec['pins'])}" + (f"  (adjusted: {rec['log']})" if rec["log"] else "")
          + ("  [EMPTY POLICY after an unreadable re-ask]" if rec.get("malformed_final") else ""))
    return True


def repo_reply(race, name):
    return os.path.join(C.REPO_REPLIES, race, name)


def init():
    st = load("rule")
    for d, s in R.races():
        for x in R.ARMS:
            R.warm(d, x, s)
    st.setdefault("registered", "Experiment C (docs/qa_week/C_PREREG.md)")
    st.setdefault("init_at", now())
    save(st)
    print("[C] warm-started: " + ", ".join(f"{d}-{x}{s}" for d, s in R.races() for x in R.ARMS))


def script():
    st = load("rule")
    files = []
    for d, s in R.races():
        if R.pkey(d, s, "d") in st["policies"]:
            continue
        rf = C.script_rule_file(d)
        p = repo_reply(C.rule_race(d, s), "script.json")
        os.makedirs(os.path.dirname(p), exist_ok=True)
        open(p, "w").write(json.dumps(rf, indent=1) + "\n")
        set_policy(st, d, s, "d", open(p).read(), "script", os.path.relpath(p, T.ROOT))
        files.append(p)
    save(st)
    return files


def m9_dispatch(share):
    items = [{"id": C.rule_race(d, s), "prompt": os.path.relpath(R.ppath(d, s, 1, "prompt.md"), T.ROOT)} for d, s in R.races()]
    p = os.path.join(HERE, "m9", "dispatch.json")
    json.dump({"batch": "race", "max_parallel": share, "items": items}, open(p, "w"), indent=1)
    t0 = now()
    if not commit_push([p], f"Experiment C: m9 race batch ({len(items)} calls, max_parallel {share})"):
        return None
    if DRY["on"]:
        return None
    for _ in range(40):
        time.sleep(5)
        rid = newest_run("c_m9.yml", t0)
        if rid:
            rr = runs()
            rr["m9"].append({"id": rid, "batch": "race", "dispatched_at": t0})
            save_runs(rr)
            print(f"[C] m9 race batch: workflow run {rid}")
            return rid
    print("[C] m9 workflow run not found yet; check gh run list -w c_m9.yml")
    return 0


def m9_ingest():
    rr = runs()
    rid = next((e["id"] for e in reversed(rr["m9"]) if e["batch"] == "race"), None)
    if not rid:
        raise SystemExit("no m9 race batch recorded")
    st = load("rule")
    files = []
    for d, s in R.races():
        if R.pkey(d, s, "m") in st["policies"]:
            continue
        race = C.rule_race(d, s)
        dest = os.path.join(T.ROOT, "results", "tune_xm", "m9", race)
        if not os.path.exists(os.path.join(dest, "receipt.json")):
            os.makedirs(dest, exist_ok=True)
            ok = CO.download_artifact(REPO, rid, f"c-m9-race-{race}", dest, {})
            if ok is not True:
                print(f"[C] {race}: m9 artifact not ready ({ok})")
                continue
        reply = os.path.join(dest, "reply.txt")
        if not os.path.exists(reply):
            print(f"[C] {race}: m9 job ended without a reply (see its receipt/log); re-run that item")
            continue
        out = []
        for name in ("reply.txt", "reask_reply.txt", "receipt.json"):
            if os.path.exists(os.path.join(dest, name)):
                q = repo_reply(race, f"m9_{name}")
                os.makedirs(os.path.dirname(q), exist_ok=True)
                shutil.copyfile(os.path.join(dest, name), q)
                out.append(q)
        rq = repo_reply(race, "m9_reask_reply.txt")
        set_policy(st, d, s, "m", open(reply).read(), "m9", os.path.relpath(repo_reply(race, "m9_reply.txt"), T.ROOT),
                   reask_raw=open(rq).read() if os.path.exists(rq) else None,
                   reask_file=os.path.relpath(rq, T.ROOT) if os.path.exists(rq) else None, final=True)
        files += out
    save(st)
    return files


def opus_ingest():
    files = []
    st = load("rule")
    for d, s in R.races():
        if R.pkey(d, s, "s") in st["policies"]:
            continue
        race = C.rule_race(d, s)
        src = os.path.join(C.OPUS_REPLIES, race, "round1.json")
        if not os.path.exists(src):
            continue
        q = repo_reply(race, "opus_round1.json")
        os.makedirs(os.path.dirname(q), exist_ok=True)
        shutil.copyfile(src, q)
        files.append(q)
        rsrc = os.path.join(C.OPUS_REPLIES, race, "round1_reask.json")
        rq = None
        if os.path.exists(rsrc):
            rq = repo_reply(race, "opus_round1_reask.json")
            shutil.copyfile(rsrc, rq)
            files.append(rq)
        set_policy(st, d, s, "s", open(q).read(), "opus-scores-only", os.path.relpath(q, T.ROOT),
                   reask_raw=open(rq).read() if rq else None, reask_file=os.path.relpath(rq, T.ROOT) if rq else None)
    save(st)
    files += prop_ingest()
    return files


# ---------------------------------------------------------------- proposer races (arm p)

def p_runs(st, d):
    return [dict(v, tag=t) for t, v in st["tags"].items() if v["design"] == d and v["arm"] == "p"]


def p_round_due(st, d):
    """Next proposer round for d (1..4) once the previous round has landed; None otherwise (or if the design stopped)."""
    if d in st.get("stopped", {}):
        return None
    mine = p_runs(st, d)
    if any(v["status"] in ("dispatched", "pending") for v in mine):
        return None
    k = max([v.get("round", 0) for v in mine] or [0]) + 1
    return k if k <= B.ROUNDS else None


def prop_prompts():
    st = load("prop")
    new, files = [], []
    for d in C.PROP_DESIGNS:
        k = p_round_due(st, d)
        if k is None or k == 1:
            continue                                  # round-1 prompts were written and hashed with the registration
        race = C.prop_race(d)
        if os.path.exists(os.path.join(C.REPO_PROMPTS, race, f"round{k}.md")):
            continue
        full, views = C.prop_prompt_full(st, d, k)
        e = MP.prop_prompt(st, d, k, state_path=A.STATE)
        orig = os.path.join(C.REPO_PROMPTS, race, f"round{k}.full.md")   # the report-bearing text it was derived from
        open(orig, "w").write(full)
        e["original"] = os.path.relpath(orig, T.ROOT)
        own = tuple(v["tag"] for v in p_runs(st, d))
        errs, _ = __import__("leakcheck").check(open(os.path.join(T.ROOT, e["repo_path"])).read(), full, views, own)
        e["leak_check_at_write"] = "PASS" if not errs else errs
        if errs:
            raise SystemExit(f"[C] {race} round {k}: leak check failed: {errs}")
        new.append(e)
        files += [os.path.join(T.ROOT, e["repo_path"]), orig]
        print(f"[C] due for the coordinator: {e['ideas_path']} -> reply to {e['reply_path']}")
    if new:
        MP.add_entries(new)
        files.append(MP.MANIFEST)
    return files


def prop_ingest():
    st = load("prop")
    st.setdefault("replies", {})
    files = []
    for d in C.PROP_DESIGNS:
        k = p_round_due(st, d)
        if k is None:
            continue
        race = C.prop_race(d)
        src = os.path.join(C.OPUS_REPLIES, race, f"round{k}.json")
        if not os.path.exists(src):
            continue
        q = repo_reply(race, f"opus_round{k}.json")
        os.makedirs(os.path.dirname(q), exist_ok=True)
        shutil.copyfile(src, q)
        files.append(q)
        v = C.validate_settings(open(q).read())
        rec = {"reply": os.path.relpath(q, T.ROOT), "malformed_first": not v["ok"], "at": now()}
        if not v["ok"]:
            rsrc = os.path.join(C.OPUS_REPLIES, race, f"round{k}_reask.json")
            if not os.path.exists(rsrc):
                print(f"[C] {race} round {k}: reply unreadable ({v['error']}); one re-ask is due")
                continue
            rq = repo_reply(race, f"opus_round{k}_reask.json")
            shutil.copyfile(rsrc, rq)
            files.append(rq)
            v = C.validate_settings(open(rq).read())
            rec["reask"] = os.path.relpath(rq, T.ROOT)
            if not v["ok"]:
                rec["malformed_final"] = True
                st.setdefault("stopped", {})[d] = f"round {k}: reply and re-ask unreadable"
                st["replies"][f"{d}|{k}"] = rec
                print(f"[C] {race}: round {k} unreadable after the re-ask; the arm stops on {d} (unresolved)")
                continue
        st["replies"][f"{d}|{k}"] = rec
        for i, s in enumerate(v["settings"]):
            log = []
            p = {name: B.clamp(name, kind, rng, s.get(name), log) for name, kind, rng, _ in B.KNOBS}
            missing = [name for name, *_ in B.KNOBS if name not in s]
            if missing:
                log.append(f"missing {missing} -> defaults used")
            ov = A.fixed(p, d)
            tag = A.next_tag(st, "p", d)
            A.add(st, tag, d, "p", ov, params=p, round=k, slot=i, rationale=v["rationale"], clamp_log=log,
                  reply_file=rec.get("reask", rec["reply"]))
            files.append(os.path.join(T.ROOT, "farm", "jobs", f"{tag}.json"))
            print(f"[C] {race} round {k}: {tag} {B.fmt_params(p)}" + (f"  (adjusted: {log})" if log else ""))
    save(st)
    return files


def closure_p(st):
    """tune_a32.closure()'s two loops (Addendum 31 closure, Amendments 32.1/32.2 chain) for arm p, unchanged."""
    new = []
    for d in C.PROP_DESIGNS:
        b, done = B.arm_best(st, d, "p")
        if not done or b is None:
            continue
        runs_ = [dict(v, tag=t) for t, v in st["tags"].items() if v["arm"] == "k" and v.get("source") == b["tag"]]
        if any(v["status"] in ("dispatched", "pending") for v in runs_):
            continue
        if [v for v in runs_ if v.get("feasible") and (v.get("wns") or -1) >= 0] or len(runs_) > B.MAX_REFINE:
            pass
        else:
            if not runs_:
                clk = B.ceil05(b["teff"])
            else:
                missed = max(v["teff"] for v in runs_ if v.get("teff") is not None) if any(v.get("teff") is not None for v in runs_) else None
                last = max(v["overrides"]["CLOCK_PERIOD"] for v in runs_)
                clk = max(B.ceil05(missed) if missed else last + 0.05, round(last + 0.05, 2))
            ov = dict(b["overrides"])
            ov["CLOCK_PERIOD"] = clk
            tag = A.next_tag(st, "k", d)
            A.add(st, tag, d, "k", ov, source=b["tag"], source_arm="p", params=b.get("params"))
            new.append(tag)
            print(f"[C] {d} arm p: best {b['tag']} T_eff {b['teff']:.3f} -> closure {tag} at {clk} ns")
            continue
        nxt = B.chain_next(st, B.chain_runs(st, b["tag"]), B.MAX_CHAIN)
        if nxt is None:
            continue
        last, clk = nxt
        ov = dict(last["overrides"])
        ov["CLOCK_PERIOD"] = clk
        tag = A.next_tag(st, "c", d)
        A.add(st, tag, d, "c", ov, source=last["tag"], root=b["tag"], source_arm="p", params=b.get("params"))
        new.append(tag)
        print(f"[C] {d} arm p: {last['tag']} passed at {last['overrides']['CLOCK_PERIOD']} -> re-run {tag} at {clk} ns")
    return new


# ---------------------------------------------------------------- the loop

def step(share, lane="both"):
    """One pass: collect, tell, ask, closure/chain, then send all due runs of the lane(s) as one farm run, unless a farm run
    of the same lane is still active. lane 'both' = one stream for both race sets; 'rule'/'prop' = two separate lanes."""
    rr = runs()
    if not DRY["on"]:
        collect_mine(rr)
    exps = ("rule", "prop") if lane == "both" else (lane,)
    files, todo = [], {"rule": [], "prop": []}
    for exp in exps:
        st = load(exp)
        if exp == "rule":
            if not DRY["on"]:
                R.tell(st)
            for d, s in R.races():
                for x in R.ARMS:
                    k = R.next_round(st, d, s, x)
                    if k is None:
                        continue
                    pins = pins_for(st, d, s, x, k)
                    if pins is None:
                        continue
                    R.ask_round(st, d, s, x, k, pins)
            R.closure_jobs(st)
        else:
            if not DRY["on"]:
                B.tell(st)
            closure_p(st)
        save(st)
        todo[exp] = sorted(t for t, v in st["tags"].items() if v["status"] == "pending")
    alltags = todo["rule"] + todo["prop"]
    if not alltags:
        print("[C] nothing to send")
        return
    act = None if DRY["on"] else active_farm_run(rr, lane)
    if act:
        save_runs(rr)
        print(f"[C] our farm run {act['id']} is still active: {len(alltags)} specs wait for the next step")
        return
    files = [os.path.join(T.ROOT, "farm", "jobs", f"{t}.json") for t in alltags]
    if not commit_push(files, f"Experiment C: runs ({len(todo['rule'])} rule-race, {len(todo['prop'])} proposer-race)"):
        return
    rid = dispatch(alltags, share)
    if rid is False:
        return
    for exp in exps:
        st = load(exp)
        for t in todo[exp]:
            st["tags"][t]["status"] = "dispatched"
            st["tags"][t]["asked_at"] = now()
            st["tags"][t]["farm_run"] = rid
        save(st)
    if rid is not None:
        rr["farm"].append({"id": rid, "tags": alltags, "dispatched_at": now(), "max_parallel": share, "lane": lane})
        save_runs(rr)
    print(f"[C] sent {len(alltags)} jobs as farm run {rid} (max_parallel {share})")


def status():
    for exp in ("rule", "prop"):
        st = load(exp)
        from collections import Counter
        print(f"[C] {exp}: {len(st['tags'])} runs, status {dict(Counter(v['status'] for v in st['tags'].values()))}, "
              f"policies {len(st.get('policies', {}))}")
    st = load("rule")
    due = [f"{C.rule_race(d, s)}:{x}" for d, s in R.races() for x in R.ARMS if R.pkey(d, s, x) not in st["policies"]]
    print(f"[C] rule policies still missing: {due}")
    st = load("prop")
    print("[C] proposer rounds due: " + ", ".join(f"{d}:{p_round_due(st, d)}" for d in C.PROP_DESIGNS if p_round_due(st, d)))
    rr = runs()
    print(f"[C] farm runs: {[(e['id'], len(e['tags']), e.get('done')) for e in rr['farm']]}; m9 runs: {rr['m9']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    for f in ("init", "script", "m9-dispatch", "m9-ingest", "opus-ingest", "prop-prompts", "step", "status", "dry-run"):
        ap.add_argument(f"--{f}", action="store_true")
    ap.add_argument("--share", type=int, default=1, help="max concurrent farm jobs (the workstream's share)")
    ap.add_argument("--lane", default="both", choices=("both", "rule", "prop"),
                    help="which race set this step serves; each lane keeps at most one active farm run")
    a = ap.parse_args()
    DRY["on"] = a.dry_run
    B.check_space()
    files = []
    if a.init:
        init()
    if a.script:
        files += script()
    if a.m9_ingest:
        files += m9_ingest()
    if a.opus_ingest:
        files += opus_ingest()
    if a.prop_prompts:
        files += prop_prompts()
    if files:
        commit_push([f for f in files if not f.startswith(os.path.join(T.ROOT, "results"))],
                    "Experiment C: rule files / replies / prompts (before the runs that use them)")
    if a.m9_dispatch:
        m9_dispatch(a.share)
    if a.step:
        step(a.share, a.lane)
    if a.status:
        status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
