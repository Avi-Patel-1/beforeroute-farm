#!/usr/bin/env python3
"""Spawn farm job specs on the deployed Modal app (farm/modal_app.py) and collect their results into results/<tag>/.

Deployed calls keep running when this machine is away; call ids are kept in results/modal_calls.json so any later
check-in collects them. A call that errors (container lost, not a flow failure) is re-spawned once.
Usage:
  modal_backend.py --spawn TAG [TAG ...] [--jobs 4]     (reads farm/jobs/<tag>.json)
  modal_backend.py --collect                            (non-blocking; extracts finished results)
  modal_backend.py --status
"""
from __future__ import annotations

import argparse
import datetime
import io
import json
import os
import tarfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
CALLS = os.path.join(ROOT, "results", "modal_calls.json")
APP, FN = "beforeroute-farm", "run_flow"


def now():
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load():
    try:
        return json.load(open(CALLS))
    except Exception:
        return {}


def save(st):
    os.makedirs(os.path.dirname(CALLS), exist_ok=True)
    json.dump(st, open(CALLS + ".tmp", "w"), indent=1)
    os.replace(CALLS + ".tmp", CALLS)


def spawn(tags, jobs=4):
    import modal
    fn = modal.Function.from_name(APP, FN)
    st = load()
    done = []
    for t in tags:
        spec = json.load(open(os.path.join(ROOT, "farm", "jobs", f"{t}.json")))
        fc = fn.spawn(spec, jobs)
        st[t] = {"call": fc.object_id, "spawned_at": now(), "jobs": jobs, "status": "running", "attempt": st.get(t, {}).get("attempt", 0) + 1}
        done.append(t)
        save(st)
    print(f"[modal] spawned {len(done)}")
    return done


def collect():
    import modal
    st = load()
    n_new = n_err = 0
    respawn = []
    for t, v in st.items():
        if v.get("status") != "running":
            continue
        fc = modal.FunctionCall.from_id(v["call"])
        try:
            data = fc.get(timeout=0)
        except TimeoutError:
            continue
        except Exception as e:  # the call itself failed (container lost/killed), not the flow
            v["status"], v["error"] = "error", str(e)[:300]
            n_err += 1
            if v.get("attempt", 1) < 2:
                respawn.append(t)
            continue
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            tf.extractall(os.path.join(ROOT, "results"), filter="data")
        v["status"], v["landed_at"] = "done", now()
        n_new += 1
    save(st)
    if respawn:
        spawn(respawn, st[respawn[0]].get("jobs", 4))
    running = sum(1 for v in load().values() if v.get("status") == "running")
    print(f"[modal] collected {n_new}, call errors {n_err} (re-spawned {len(respawn)}), {running} running")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spawn", nargs="*")
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--collect", action="store_true")
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.spawn:
        spawn(a.spawn, a.jobs)
    if a.collect:
        collect()
    if a.status or not (a.spawn or a.collect):
        st = load()
        from collections import Counter
        print(Counter(v.get("status") for v in st.values()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
