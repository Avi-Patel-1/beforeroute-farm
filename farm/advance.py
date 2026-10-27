#!/usr/bin/env python3
"""Advance the iterations-to-closure experiment one step per call (idempotent).

For each base:
  * signoff-guided loop  sgl<k>: list_k = list_{k-1} U signal violators of pass k-1 (pass 0 = baseline);
    dispatch lst-sgl<k+1>-70 when pass k has landed with residual violators, up to --max-pass.
  * BeforeRoute + cleanup cln<k>: list = model-flagged list of <seed arm> U residual violators of the
    previous pass (pass 0 = the seed arm itself); dispatch lst-cln<k>-70, up to --max-pass.
Lists are committed under farm/lists/<base>/ (the runner reads them from the checkout).
"""
import argparse, glob, json, os, subprocess, sys

REPO = "Avi-Patel-1/beforeroute-farm"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..")


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def landed(results, tag):
    try:
        return json.load(open(os.path.join(results, tag, "job.json"))).get("status") == "completed"
    except Exception:
        return False


def signal_violators(results, tag):
    lab = json.load(open(os.path.join(results, tag, "labels.json")))
    return sum(1 for r in lab["nets"] if r.get("violated") and r.get("sigtype_s") == "SIGNAL")


def dispatched(base, arm, log):
    return f"{base} {arm}" in log


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", default="d3-salsa20-000,d3-des-000,d3-y_huff-000,d3-ocs_blitter-000,d3-bm64-000,d3-md5-000,d3b-sha512-000,d3b-ldpcenc-000")
    ap.add_argument("--results", default=os.path.join(ROOT, "results"))
    ap.add_argument("--max-pass", type=int, default=4)
    ap.add_argument("--seed-arm", default="tgt050-70")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    state = os.path.join(a.results, ".advance_dispatched")
    log = open(state).read() if os.path.exists(state) else ""
    todo = []  # (base, arm, list_path, prev_list, prev_arm_tag)
    for base in a.bases.split(","):
        ldir = os.path.join(ROOT, "farm", "lists", base)
        # signoff-guided loop
        for k in range(1, a.max_pass):
            arm_k = f"lst-sgl{k}-70"
            if not landed(a.results, f"{base}-{arm_k}"):
                break
            nxt = f"lst-sgl{k+1}-70"
            if signal_violators(a.results, f"{base}-{arm_k}") == 0 or dispatched(base, nxt, log):
                continue
            todo.append((base, nxt, os.path.join(ldir, f"sgl{k+1}.json"), os.path.join(ldir, f"sgl{k}.json"), f"{base}-{arm_k}"))
        # BeforeRoute + cleanup
        seed = f"{base}-{a.seed_arm}"
        flagged = os.path.join(a.results, base, f"flagged_{a.seed_arm}.json")
        if landed(a.results, seed) and os.path.exists(flagged):
            prev_arm, prev_list = seed, flagged
            for k in range(1, a.max_pass):
                arm_k = f"lst-cln{k}-70"
                if signal_violators(a.results, prev_arm) == 0:
                    break
                if not dispatched(base, arm_k, log):
                    todo.append((base, arm_k, os.path.join(ldir, f"cln{k}.json"), prev_list, prev_arm))
                    break
                if not landed(a.results, f"{base}-{arm_k}"):
                    break
                prev_arm, prev_list = f"{base}-{arm_k}", os.path.join(ldir, f"cln{k}.json")
    if not todo:
        print("[advance] nothing to do")
        return 0
    made = []
    for base, arm, out, prev_list, prev_arm in todo:
        r = sh([sys.executable, "br/iterate.py", "--base", base, "--out", out, "--prev-list", prev_list, "--prev-arm", prev_arm, "--results", a.results])
        print(r.stdout.strip() or r.stderr.strip()[:300])
        if r.returncode == 0:
            made.append((base, arm, out))
    if a.dry_run or not made:
        return 0
    sh(["git", "add"] + [m[2] for m in made])
    msg = "Advance iterations-to-closure: " + ", ".join(f"{b} {arm}" for b, arm, _ in made) + "\n\nCo-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_016XcZ7Zp4en4cWPeoAqbHJG"
    sh(["git", "commit", "-qm", msg])
    for i in range(5):
        if sh(["git", "push", "-q", "origin", "main"]).returncode == 0:
            break
        sh(["git", "pull", "-q", "--rebase", "origin", "main"])
    by_base = {}
    for b, arm, _ in made:
        by_base.setdefault(b, []).append(arm)
    with open(state, "a") as f:
        for b, arms in by_base.items():
            r = sh(["gh", "workflow", "run", "hero.yml", "-R", REPO, "--ref", "main", "-f", f"base_tag={b}",
                    "-f", "arms=" + json.dumps(arms), "-f", "model=models/model_holdout_picorv32_v3.txt"])
            ok = r.returncode == 0
            print(f"[advance] {b}: dispatch {arms} -> {'ok' if ok else r.stderr.strip()[:200]}")
            if ok:
                for arm in arms:
                    f.write(f"{b} {arm}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
