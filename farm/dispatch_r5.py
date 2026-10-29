#!/usr/bin/env python3
"""Round 5 dispatcher (idempotent, restart-safe; state in results/.r5_state.json).

Per base: (1) dispatch a seed run (builds the baseline once and fills the checkpoint cache);
(2) when the seed run has completed, collect the baseline, build the signoff-guided loop's first
list from the baseline's signoff violators, commit it, and dispatch the pre-registered arms
plus lst-sgl1-70 in one hero run. Arms are never dispatched before the seed finished, so every
arm restores the cached checkpoint instead of rebuilding it.
"""
import argparse, json, os, subprocess, sys, time

REPO = "Avi-Patel-1/beforeroute-farm"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
BASES = ["d5-chacha-000", "d5-point_add-000", "d5-blabla-000"]
ARMS = ["rerun", "uni50", "uni70", "est050-70c", "tgt050-70c", "thr500-70c", "exp100-70c", "lst-sgl1-70"]
MODEL = "models/model_all_v5.txt"
# Round 5 runs on its own branch: the runner pool serves queued jobs of different refs side by side, so a
# separate ref is not stuck behind the long main-branch queue. The branch only ever fast-forwards to main.
REF = "r5"


def sh(cmd, **kw):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT, **kw)


def find_run(job_name, after):
    """Most recent hero run (created after `after`, ISO) whose first job is `job_name`."""
    r = sh(["gh", "run", "list", "-R", REPO, "-w", "hero.yml", "--limit", "40", "--json", "databaseId,createdAt"])
    for run in json.loads(r.stdout or "[]"):
        if run["createdAt"] < after:
            continue
        j = sh(["gh", "run", "view", str(run["databaseId"]), "-R", REPO, "--json", "jobs", "--jq", ".jobs[].name"])
        if job_name in j.stdout.split():
            return run["databaseId"]
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    import fcntl  # one dispatcher at a time (the collector loop and the check-in cycle both call this)
    lock = open(os.path.join(ROOT, "results", ".r5_lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[r5] another dispatcher is running")
        return 0
    path = os.path.join(ROOT, "results", ".r5_state.json")
    st = json.load(open(path)) if os.path.exists(path) else {}
    for b in BASES:
        s = st.setdefault(b, {})
        if not s.get("seed_dispatched"):
            if a.dry_run:
                print(f"[r5] {b}: would dispatch seed"); continue
            t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 5))
            sh(["git", "push", "-q", "origin", f"main:{REF}"])
            r = sh(["gh", "workflow", "run", "hero.yml", "-R", REPO, "--ref", REF, "-f", f"base_tag={b}",
                    "-f", 'arms=["seed"]', "-f", f"model={MODEL}"])
            if r.returncode != 0:
                print(f"[r5] {b}: seed dispatch failed: {r.stderr.strip()[:200]}"); continue
            s["seed_dispatched"] = t
            json.dump(st, open(path, "w"), indent=1)
            print(f"[r5] {b}: seed dispatched")
            continue
        if not s.get("seed_run"):
            rid = find_run(f"{b}-seed", s["seed_dispatched"])
            if rid:
                s["seed_run"] = rid
                json.dump(st, open(path, "w"), indent=1)
            else:
                print(f"[r5] {b}: seed run not visible yet"); continue
        if s.get("arms_dispatched"):
            continue
        v = sh(["gh", "run", "view", str(s["seed_run"]), "-R", REPO, "--json", "status,conclusion"])
        info = json.loads(v.stdout or "{}")
        if info.get("status") != "completed":
            print(f"[r5] {b}: seed run {s['seed_run']} {info.get('status')}"); continue
        # collect the baseline produced by the seed (hero_collect copies the base dir from the artifact)
        sh([sys.executable, "farm/hero_collect.py", "--repo", REPO, "--base", b, "--results", "results", "--run-id", str(s["seed_run"])])
        job = os.path.join(ROOT, "results", b, "job.json")
        status = json.load(open(job)).get("status") if os.path.exists(job) else "missing"
        if status != "completed" or not os.path.exists(os.path.join(ROOT, "results", b, "labels.json")):
            s["seed_status"] = status
            json.dump(st, open(path, "w"), indent=1)
            print(f"[r5] {b}: baseline not usable (status {status}); arms NOT dispatched — handle by hand")
            continue
        lst = f"farm/lists/{b}/sgl1.json"
        r = sh([sys.executable, "br/iterate.py", "--base", b, "--out", lst, "--results", "results"])
        print(r.stdout.strip() or r.stderr.strip()[:300])
        if a.dry_run:
            print(f"[r5] {b}: would dispatch {ARMS}"); continue
        sh(["git", "add", lst])
        sh(["git", "commit", "-qm", f"Round 5: signoff-guided loop pass-1 list for {b}"])
        for _ in range(5):
            if sh(["git", "push", "-q", "origin", "main"]).returncode == 0:
                break
            sh(["git", "pull", "-q", "--rebase", "origin", "main"])
        sh(["git", "push", "-q", "origin", f"main:{REF}"])  # fast-forward: the list commit and current code
        r = sh(["gh", "workflow", "run", "hero.yml", "-R", REPO, "--ref", REF, "-f", f"base_tag={b}",
                "-f", "arms=" + json.dumps(ARMS), "-f", f"model={MODEL}"])
        if r.returncode == 0:
            s["arms_dispatched"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            with open(os.path.join(ROOT, "results", ".advance_dispatched"), "a") as f:
                f.write(f"{b} lst-sgl1-70\n")
            print(f"[r5] {b}: arms dispatched {ARMS}")
        else:
            print(f"[r5] {b}: arm dispatch failed: {r.stderr.strip()[:200]}")
        json.dump(st, open(path, "w"), indent=1)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
