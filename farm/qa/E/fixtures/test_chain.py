#!/usr/bin/env python3
"""E-chain fixture (Addendum 42): the runner-side chain (br/run_job.py run_chain) on a fake deterministic flow, against
hand-checked expectations and against elib.simulate_chain (the baselines' simulation of the same registered rule).
Cases: tight source, no pass (kept null); passing source whose rebuilds all fail (kept = the source's own target);
first rebuild without metrics (flow failure: slope undefined, step back to R1 + 0.05); converging loose chain.
Run: python3 farm/qa/E/fixtures/test_chain.py  -> prints OK or raises AssertionError."""
import contextlib
import io
import json
import os
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "..", "..", "br"))
sys.path.insert(0, os.path.join(HERE, ".."))
import run_job as RJ  # noqa: E402
import elib as E  # noqa: E402


def fake_flow(C, no_metrics_at=()):
    def run(cmd, *a, **k):
        sp = cmd[cmd.index("--job-spec") + 1]
        res = cmd[cmd.index("--results") + 1]
        spec = json.load(open(sp))
        T = spec["overrides"]["CLOCK_PERIOD"]
        d = os.path.join(res, spec["tag"])
        os.makedirs(d, exist_ok=True)
        if round(T, 4) in no_metrics_at:
            json.dump({"flow_exit": 1, "status": "flow_failed"}, open(os.path.join(d, "job.json"), "w"))
            return types.SimpleNamespace(returncode=1)
        c = C(T)
        json.dump({"timing__setup__ws": T - c, "timing__setup_r2r__ws": T - c, "timing__hold__ws": 0.1,
                   "route__drc_errors": 0, "design__max_slew_violation__count": 0,
                   "design__max_cap_violation__count": 0}, open(os.path.join(d, "metrics.json"), "w"))
        json.dump({"flow_exit": 0, "status": "completed"}, open(os.path.join(d, "job.json"), "w"))
        return types.SimpleNamespace(returncode=0)
    return run


def chain(name, C, T0, source_pass, no_metrics_at=()):
    C0 = C(T0)
    RJ.subprocess.run = fake_flow(C, no_metrics_at)
    d = tempfile.mkdtemp(prefix="e_chain_fixture_")
    a = types.SimpleNamespace(results=d, jobs=4, pdk_root="/x", timeout=10)
    spec = {"tag": "t-" + name, "design": "d", "config": "c", "overrides": {"CLOCK_PERIOD": T0},
            "chain": {"T0": T0, "C0": C0, "source_pass": source_pass, "drv_bar": 0, "max_rebuilds": 4}}
    with contextlib.redirect_stdout(io.StringIO()):
        RJ.run_chain(spec, a)
    return json.load(open(os.path.join(d, "t-" + name, "chain.json"))), C0


def law(F, sl=0.59, sh=0.29):
    return lambda T: F + (sl if T < F else sh) * (T - F)


def main():
    # 1. tight, law-like: R1 and the step back both below F -> no pass, kept null
    c, C0 = chain("tight", law(10.0), 7.0, False)
    assert [r["clock_ns"] for r in c["rebuilds"]] == [8.25, 9.0] and not any(r["pass"] for r in c["rebuilds"]), c
    assert c["kept_clock_ns"] is None and abs(c["slope"] - 0.59) < 1e-9 and c["first_outcome"] == "landed", c
    # 2. passing source, every rebuild below T0 fails, step back not below T0 -> kept = T0 (source only)
    resp = lambda T: 10.0 - 2.0 if T >= 10.0 else 10.5   # noqa: E731  source at 10.0 claims 8.0
    c, C0 = chain("source_only", resp, 10.0, True)
    assert [r["clock_ns"] for r in c["rebuilds"]] == [8.0] and c["kept_clock_ns"] == 10.0, c
    assert abs(c["slope"] - (10.5 - 8.0) / (8.0 - 10.0)) < 1e-9, c
    # 3. first rebuild produces no metrics: slope undefined, step back to R1 + 0.05
    c, C0 = chain("no_metrics", law(10.0), 7.0, False, no_metrics_at=(8.25,))
    assert c["first_outcome"] == "no_metrics" and c["C1_ns"] is None and c["slope"] is None, c
    assert [r["clock_ns"] for r in c["rebuilds"]] == [8.25, 8.3] and c["rebuilds"][0]["flow_exit"] == 1, c
    # 4. converging loose chain: kept below T0, at most 4 rebuilds
    c, C0 = chain("loose", law(10.0), 14.0, True)
    assert [r["clock_ns"] for r in c["rebuilds"]] == [11.2, 10.35, 10.15, 10.05] and c["kept_clock_ns"] == 10.05, c
    # runner-side chain == the baselines' simulation of the same rule (cases 1, 2, 4)
    for C, T0, sp in ((law(10.0), 7.0, False), (resp, 10.0, True), (law(10.0), 14.0, True)):
        c, C0 = chain("cmp", C, T0, sp)
        p1, c1, kept, order = E.simulate_chain(C, T0, C0, sp)
        assert [r["clock_ns"] for r in c["rebuilds"]] == order and kept == c["kept_clock_ns"] and p1 == c["first_pass"]
    print("OK chain fixture")


if __name__ == "__main__":
    main()
