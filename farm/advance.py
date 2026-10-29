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
    """signal nets violating slew or cap at signoff (fanout-only residuals are antenna-diode loads, excluded from
    closure by Addendum 2)"""
    lab = json.load(open(os.path.join(results, tag, "labels.json")))
    return sum(1 for r in lab["nets"] if r.get("violated") and r.get("sigtype_s") == "SIGNAL" and (r.get("viol_slew") or r.get("viol_cap")))


def mapped_residuals(results, base, tag):
    """slew/cap signal violators of arm `tag`, mapped to net names of the base's post-GRT database
    (by name, else by driver instance; unmapped nets dropped) -- same mapping as br/iterate.py"""
    names, by_inst = set(), {}
    for line in open(os.path.join(results, base, "nets.jsonl")):
        n = json.loads(line)
        names.add(n["net"])
        if n.get("driver_inst"):
            by_inst.setdefault(n["driver_inst"], n["net"])
    out = []
    for r in json.load(open(os.path.join(results, tag, "labels.json")))["nets"]:
        if not (r.get("violated") and r.get("sigtype_s") == "SIGNAL" and (r.get("viol_slew") or r.get("viol_cap"))):
            continue
        nm = r["net"] if r["net"] in names else by_inst.get((r.get("driver_s") or "").split("/")[0])
        if nm:
            out.append(nm)
    return sorted(set(out))


def dispatched(base, arm, log):
    return f"{base} {arm}" in log


def escalation(results, base, arm, prev_list, prev_arm, log):
    """Addendum 8: build the two-tier escalation list for a stalled chain; None if the chain already escalated or
    has no slew/cap residuals left."""
    chain = "sgl" if "-sgl" in arm else "cln"
    if f"{base} lsx-{chain}" in log:
        return None
    resid = mapped_residuals(results, base, prev_arm)
    if not resid:
        return None
    k = arm.split(chain)[1].split("-")[0]
    name = f"{chain}{k}x"
    out = os.path.join(ROOT, "farm", "lists", base, f"{name}.json")
    lst = json.load(open(prev_list))
    json.dump({"tiers": [{"nets": sorted(set(lst) | set(resid)), "slew_pct": 70, "cap_pct": 70},
                         {"nets": resid, "slew_pct": 90, "cap_pct": 90}]}, open(out, "w"))
    return (base, f"lsx-{name}", out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bases", default="d3-salsa20-000,d3-des-000,d3-y_huff-000,d3-ocs_blitter-000,d3-bm64-000,d3-md5-000,d3b-sha512-000,d3b-ldpcenc-000,d1-picorv32-006,d1-picorv32-016,d1-aes_cipher-000,d5-chacha-000,d5-point_add-000,d5-blabla-000")
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
        # Round-5 bases score the deployment view (features at the checkpoint): seed arm tgt050-70c
        seed_arm = a.seed_arm + "c" if base.startswith("d5-") else a.seed_arm
        seed = f"{base}-{seed_arm}"
        flagged = os.path.join(a.results, base, f"flagged_{seed_arm}.json")
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
        if r.returncode != 0:
            continue
        try:
            info = json.loads(r.stdout.strip().splitlines()[-1])
        except Exception:
            info = {}
        if info.get("added", 1) == 0:
            # every residual violator is already on the list: the next pass would repeat the previous one exactly
            # (deterministic flow) -> the chain has stalled. Addendum 8: one escalation pass (same list at 70%, then
            # the residual violators again at 90%); afterwards the chain ends.
            with open(state, "a") as f:
                f.write(f"{base} {arm} STALLED\n")
            try:
                os.remove(out)  # the repeated list itself is not dispatched
            except OSError:
                pass
            esc = escalation(a.results, base, arm, prev_list, prev_arm, log)
            if esc:
                made.append(esc)
                print(f"[advance] {base} {arm}: stalled -> escalation pass {esc[1]}")
            else:
                print(f"[advance] {base} {arm}: stalled; no escalation (already escalated or no slew/cap residuals)")
            continue
        made.append((base, arm, out))
    if a.dry_run or not made:
        return 0
    sh(["git", "add"] + [m[2] for m in made])
    msg = "Advance iterations-to-closure: " + ", ".join(f"{b} {arm}" for b, arm, _ in made)
    sh(["git", "commit", "-qm", msg])
    for i in range(5):
        if sh(["git", "push", "-q", "origin", "main"]).returncode == 0:
            break
        sh(["git", "pull", "-q", "--rebase", "origin", "main"])
    by_base = {}
    for b, arm, _ in made:
        by_base.setdefault(b, []).append(arm)
    # chain passes are sequential, so they run on their own branch (fast-forwarded to main) where the runner pool
    # serves them alongside the long main-branch queue; Round-5 bases stay on r5, where their checkpoint cache lives
    for ref in {("r5" if b.startswith("d5-") else "chains") for b in by_base}:
        sh(["git", "push", "-q", "origin", f"main:{ref}"])
    with open(state, "a") as f:
        for b, arms in by_base.items():
            ref = "r5" if b.startswith("d5-") else "chains"
            r = sh(["gh", "workflow", "run", "hero.yml", "-R", REPO, "--ref", ref, "-f", f"base_tag={b}",
                    "-f", "arms=" + json.dumps(arms), "-f", "model=models/model_holdout_picorv32_v3.txt"])
            ok = r.returncode == 0
            print(f"[advance] {b}: dispatch {arms} -> {'ok' if ok else r.stderr.strip()[:200]}")
            if ok:
                for arm in arms:
                    f.write(f"{b} {arm}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
