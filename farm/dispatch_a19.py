#!/usr/bin/env python3
"""Addendum 19 dispatcher (idempotent; state in results/.a19_state.json).

Phase 1 (once): one hero run per original base with the Addendum-19 arms, spread over branches whose checkpoint caches
the base can restore (main-seeded bases: any branch fast-forwarded to main; Round-5 bases: r5); the Round-1 v4-model arm
as its own run (the model is a per-run input); seeds for the correlated-flow bases (branch cf) and the re-placed noise
bases (branch jit).
Phase 2 (each call): once a seed run has completed, dispatch that base's follow-up arms on the same branch, so every arm
restores the cached checkpoint instead of rebuilding it.
Usage: dispatch_a19.py [--dry-run] [--phase1] (phase 2 always runs)
"""
import argparse, json, os, subprocess, sys, time, fcntl

REPO = "Avi-Patel-1/beforeroute-farm"
ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
MODEL = {
    "d3-bm64-000": "models/model_holdout_bm64_v4.txt", "d3-des-000": "models/model_holdout_des_v4.txt",
    "d3-md5-000": "models/model_holdout_md5_v4.txt", "d3-ocs_blitter-000": "models/model_holdout_ocs_blitter_v4.txt",
    "d3-salsa20-000": "models/model_holdout_salsa20_v4.txt", "d3-y_huff-000": "models/model_holdout_y_huff_v4.txt",
    "d3b-ldpcenc-000": "models/model_holdout_ldpcenc_v4.txt", "d3b-sha512-000": "models/model_holdout_sha512_v4.txt",
    "d5-blabla-000": "models/model_all_v5.txt", "d5-chacha-000": "models/model_all_v5.txt", "d5-point_add-000": "models/model_all_v5.txt",
    "d1-picorv32-006": "models/model_holdout_picorv32_v3.txt", "d1-picorv32-016": "models/model_holdout_picorv32_v3.txt",
    "d1-aes_cipher-000": "models/model_holdout_aes_v3.txt",
}
MODEL_V4 = {"d1-picorv32-006": "models/model_holdout_picorv32_v4.txt", "d1-picorv32-016": "models/model_holdout_picorv32_v4.txt",
            "d1-aes_cipher-000": "models/model_holdout_aes_v4.txt"}
BRANCH = {"d3b-ldpcenc-000": "rcal", "d3b-sha512-000": "rcal", "d3-bm64-000": "rcal", "d3-des-000": "rcal",
          "d1-picorv32-006": "rct", "d1-picorv32-016": "rct", "d1-aes_cipher-000": "rct", "d3-md5-000": "rct",
          "d3-ocs_blitter-000": "chains", "d3-salsa20-000": "chains", "d3-y_huff-000": "chains",
          "d5-blabla-000": "r5", "d5-chacha-000": "r5", "d5-point_add-000": "r5"}
ROUND3 = {"d3-bm64-000", "d3-des-000", "d3-md5-000", "d3-ocs_blitter-000", "d3-salsa20-000", "d3-y_huff-000"}
ARMS = ["rcal213-20", "rcal213-30", "bst500-30-10r", "rqn-30r", "rnd1-30r", "rqt900-30r", "rcalorfs-10", "rcalorfs-30",
        "thr500-30co", "rcal213-10t", "rcal213-30t", "thr500-30crt", "bst500-30-10rt"]
CF_ARMS = ["uni10", "uni30", "uni10t"]
JIT_ARMS = ["rcal213-10", "thr500-30cr", "bst500-30-10r"]
JIT_DESIGNS = ["d3b-ldpcenc-000", "d3b-sha512-000", "d5-blabla-000", "d5-chacha-000", "d5-point_add-000",
               "d1-picorv32-006", "d1-picorv32-016", "d1-aes_cipher-000"]


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)


def dispatch(base, arms, model, ref, dry):
    if dry:
        print(f"[a19] would dispatch {base} on {ref}: {arms} ({model})")
        return True
    r = sh(["gh", "workflow", "run", "hero.yml", "-R", REPO, "--ref", ref, "-f", f"base_tag={base}",
            "-f", "arms=" + json.dumps(arms), "-f", f"model={model}"])
    ok = r.returncode == 0
    print(f"[a19] {base} on {ref}: {arms} -> {'ok' if ok else 'FAILED ' + r.stderr.strip()[:200]}")
    return ok


def derived(base, kind):
    fam, rest = base.split("-", 1)
    return [f"{fam}cfo-{rest}"] if kind == "cf" else [f"{fam}j1-{rest}", f"{fam}j2-{rest}"]


def job_index(st, after):
    """{job name: run id} for hero runs created after `after`; each run's job list is fetched once and kept in the
    state (a run's job names never change once they appear), so a call costs one list plus one view per new run."""
    cache = st.setdefault("run_jobs", {})
    r = sh(["gh", "run", "list", "-R", REPO, "-w", "hero.yml", "--limit", "100", "--json", "databaseId,createdAt"])
    for run in json.loads(r.stdout or "[]"):
        rid = str(run["databaseId"])
        if run["createdAt"] < after or cache.get(rid):
            continue
        j = sh(["gh", "run", "view", rid, "-R", REPO, "--json", "jobs", "--jq", ".jobs[].name"])
        names = j.stdout.split()
        if names:
            cache[rid] = names
    return {n: int(rid) for rid, names in cache.items() for n in names}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--phase1", action="store_true")
    ap.add_argument("--a20", action="store_true", help="Addendum 20: hold-preserving repair arms on the 14 bases")
    ap.add_argument("--a21", action="store_true", help="Addendum 21: utilization-sweep seeds (arms follow in phase 2)")
    a = ap.parse_args()
    lock = open(os.path.join(ROOT, "results", ".a19_lock"), "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print("[a19] another dispatcher is running")
        return 0
    path = os.path.join(ROOT, "results", ".a19_state.json")
    st = json.load(open(path)) if os.path.exists(path) else {"phase1": {}, "seeds": {}}
    save = lambda: (None if a.dry_run else json.dump(st, open(path, "w"), indent=1))
    if a.phase1:
        # seeds first: their follow-up arms wait on them, so they must not queue behind the arm runs
        for base in BRANCH:
            for nb in derived(base, "cf"):
                if nb not in st["seeds"]:
                    t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 5))
                    if dispatch(nb, ["seed"], MODEL[base], "cf", a.dry_run):
                        st["seeds"][nb] = {"ref": "cf", "after": t, "model": MODEL[base], "arms": CF_ARMS}; save()
        for base in JIT_DESIGNS:
            for nb in derived(base, "jit"):
                if nb not in st["seeds"]:
                    t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 5))
                    if dispatch(nb, ["seed"], MODEL[base], "jit", a.dry_run):
                        st["seeds"][nb] = {"ref": "jit", "after": t, "model": MODEL[base], "arms": JIT_ARMS}; save()
        for base, ref in BRANCH.items():
            key = f"{base}:main"
            if key not in st["phase1"]:
                arms = ARMS + ([] if base in ROUND3 else ["rcal213-0"])
                if dispatch(base, arms, MODEL[base], ref, a.dry_run):
                    st["phase1"][key] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()); save()
            if base in MODEL_V4 and f"{base}:v4" not in st["phase1"]:
                if dispatch(base, ["thr500-30crv4"], MODEL_V4[base], ref, a.dry_run):
                    st["phase1"][f"{base}:v4"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()); save()
    if a.a20:
        for base, ref in BRANCH.items():
            if f"{base}:a20" in st["phase1"]:
                continue
            if dispatch(base, ["rcy213-10", "rcy213-10y", "thr500-30cry", "bst500-30-10ry"], MODEL[base], ref, a.dry_run):
                st["phase1"][f"{base}:a20"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()); save()
    if a.a21:
        U_ARMS = ["rcal213-10", "rcal213-30", "thr500-30cr", "bst500-30-10r", "rqn-30r"]
        for base in ("d3b-ldpcenc-000", "d3b-sha512-000", "d3-salsa20-000"):
            fam, rest = base.split("-", 1)
            for u in ("u50", "u60"):
                nb = f"{fam}{u}-{rest}"
                if nb in st["seeds"]:
                    continue
                t = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 5))
                if dispatch(nb, ["seed"], MODEL[base], "util", a.dry_run):
                    st["seeds"][nb] = {"ref": "util", "after": t, "model": MODEL[base], "arms": U_ARMS}; save()
    # phase 2: follow-up arms once each seed run completed
    pending = [nb for nb, s in st["seeds"].items() if not s.get("arms_dispatched") and not s.get("run")]
    idx = job_index(st, min(st["seeds"][nb]["after"] for nb in pending)) if pending else {}
    save()
    for nb, s in st["seeds"].items():
        if s.get("arms_dispatched"):
            continue
        if not s.get("run"):
            rid = idx.get(f"{nb}-seed")
            if not rid:
                print(f"[a19] {nb}: seed run not visible yet"); continue
            s["run"] = rid; save()
        v = json.loads(sh(["gh", "run", "view", str(s["run"]), "-R", REPO, "--json", "status,conclusion"]).stdout or "{}")
        if v.get("status") != "completed":
            print(f"[a19] {nb}: seed {s['run']} {v.get('status')}"); continue
        if v.get("conclusion") != "success":
            print(f"[a19] {nb}: seed {s['run']} concluded {v.get('conclusion')}; not dispatching arms"); continue
        # the job itself always succeeds (hero_arm.sh || true): read the seed's own status from its artifact
        if not s.get("seed_status"):
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                sh(["gh", "run", "download", str(s["run"]), "-R", REPO, "-n", f"hero-{nb}-seed", "-D", td])
                try:
                    st_ = json.load(open(os.path.join(td, nb, "job.json"))).get("status", "unknown")
                    # a flow that ends in deferred hold/setup errors still reached signoff (labels.json exists): usable
                    s["seed_status"] = "completed" if (st_ == "completed" or os.path.exists(os.path.join(td, nb, "labels.json"))) else st_
                    s["seed_status_raw"] = str(st_)[:200]
                except Exception:
                    s["seed_status"] = "no_artifact"
            save()
        if s["seed_status"] != "completed":
            print(f"[a19] {nb}: seed status {s['seed_status']}; not dispatching arms"); continue
        if dispatch(nb, s["arms"], s["model"], s["ref"], a.dry_run):
            s["arms_dispatched"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()); save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
