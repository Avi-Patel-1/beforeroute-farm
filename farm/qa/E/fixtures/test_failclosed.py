#!/usr/bin/env python3
"""Fail-closed fixture (Addendum 42, pre-registration clarification 12; Codex's audit findings). Synthetic inputs only.
  A. br/run_job.py e_judge: a missing, NaN, infinite, string or boolean judge field, or a missing electrical bar, is
     never a pass (the old code read a missing DRC or slew/cap count as 0).
  B. br/run_job.py run_chain: a first rebuild that is otherwise passing but lacks route DRC (or a slew count) FAILS
     with a defined slope; a rebuild that leaves neither metrics nor a job record is an infrastructure loss (no
     chain.json, chain_partial.json, exit 3); a chain spec without its bar is refused before anything is built.
  C. farm/qa/E/make_chains.py: a source run lacking a judge field is not admitted and nothing is written.
  D. farm/qa/E/run_predictor.py: every dependency hashed (unlisted, unhashed or changed files refuse; an unlisted file
     next to the entry cannot be imported), packets checked against the committed manifest (a missing or changed
     packet refuses), errors / non-determinism / invalid outputs / reads outside the allowed roots exit 1 and write
     nothing into <pred>/<arm>/.
  E. farm/qa/E/verify_packets.py: an empty or partial SPEF corner, or a per-net dump row without a corner value, fails.
Run: python3 farm/qa/E/fixtures/test_failclosed.py  -> prints OK or raises AssertionError."""
import contextlib
import gzip
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import types

HERE = os.path.dirname(os.path.abspath(__file__))
E_DIR = os.path.abspath(os.path.join(HERE, ".."))
BR = os.path.abspath(os.path.join(HERE, "..", "..", "..", "..", "br"))
sys.path.insert(0, BR)
import run_job as RJ  # noqa: E402

_REAL_RUN = subprocess.run   # RJ.subprocess IS the subprocess module: part B patches it, then restores it

FULL = {"timing__setup__ws": 0.2, "timing__setup_r2r__ws": 0.3, "timing__hold__ws": 0.05, "route__drc_errors": 0,
        "design__max_slew_violation__count": 3, "design__max_cap_violation__count": 1}
CORNERS = [f"{rc}_{p}" for rc in ("min", "nom", "max") for p in ("tt_025C_1v80", "ss_100C_1v60", "ff_n40C_1v95")]


def sha(p):
    return hashlib.sha256(open(p, "rb").read()).hexdigest()


def run(cmd):
    return _REAL_RUN([sys.executable] + cmd, capture_output=True, text=True)


# ---------------------------------------------------------------- A. judge
def part_a():
    assert RJ.e_judge(FULL, 4) == (True, [], 4.0)
    assert RJ.e_judge(dict(FULL, timing__setup__ws=0.0, timing__hold__ws=0.0), 4)[0]       # boundaries pass
    assert not RJ.e_judge(FULL, 3)[0]                                                       # drv 4 > bar 3
    for k in RJ.E_JUDGE_KEYS:
        m = dict(FULL)
        del m[k]
        ok, missing, _ = RJ.e_judge(m, 4)
        assert not ok and missing == [k], (k, ok, missing)
        for bad in (None, float("nan"), float("inf"), "0", True):
            ok, missing, _ = RJ.e_judge(dict(FULL, **{k: bad}), 4)
            assert not ok and k in missing, (k, bad)
    for bar in (None, float("nan"), "295"):
        ok, missing, _ = RJ.e_judge(FULL, bar)
        assert not ok and "drv_bar" in missing, bar
    assert not RJ.e_judge({}, 4)[0] and not RJ.e_judge(None, 4)[0]
    # the old expression passed a run with no DRC count; the new judge does not
    m = {k: v for k, v in FULL.items() if k != "route__drc_errors"}
    old = (m.get("timing__setup__ws") >= 0 and m.get("timing__hold__ws") >= 0 and (m.get("route__drc_errors") or 0) == 0)
    assert old and not RJ.e_judge(m, 4)[0]


# ---------------------------------------------------------------- B. runner-side chain
def fake_flow(C, drop=None, lost_at=(), calls=None):
    def flow(cmd, *a, **k):
        sp = cmd[cmd.index("--job-spec") + 1]
        res = cmd[cmd.index("--results") + 1]
        spec = json.load(open(sp))
        T = spec["overrides"]["CLOCK_PERIOD"]
        if calls is not None:
            calls.append(T)
        d = os.path.join(res, spec["tag"])
        os.makedirs(d, exist_ok=True)
        if round(T, 4) in lost_at:          # worker died: no metrics, no job record
            return types.SimpleNamespace(returncode=-9)
        m = dict(FULL, timing__setup__ws=T - C(T), timing__setup_r2r__ws=T - C(T))
        for key in (drop or {}).get(round(T, 4), ()):
            m.pop(key)
        json.dump(m, open(os.path.join(d, "metrics.json"), "w"))
        json.dump({"flow_exit": 0, "status": "completed", "flow_completed": True}, open(os.path.join(d, "job.json"), "w"))
        return types.SimpleNamespace(returncode=0)
    return flow


def chain(name, C, T0, source_pass, bar=10, **kw):
    calls = []
    RJ.subprocess.run = fake_flow(C, calls=calls, **kw)
    d = tempfile.mkdtemp(prefix="e_failclosed_chain_")
    a = types.SimpleNamespace(results=d, jobs=4, pdk_root="/x", timeout=10)
    ch = {"T0": T0, "C0": C(T0), "source_pass": source_pass, "drv_bar": bar, "max_rebuilds": 4}
    if bar is None:
        del ch["drv_bar"]
    spec = {"tag": "t-" + name, "design": "d", "config": "c", "overrides": {"CLOCK_PERIOD": T0}, "chain": ch}
    with contextlib.redirect_stdout(io.StringIO()):
        rc = RJ.run_chain(spec, a)
    top = os.path.join(d, "t-" + name)
    cj = os.path.join(top, "chain.json")
    return rc, (json.load(open(cj)) if os.path.exists(cj) else None), top, calls


def part_b():
    flat = lambda T: 9.0   # noqa: E731  claim 9.0 whatever the target: source at 10 passes, R1 = 9.0 passes on setup
    rc, c, _, _ = chain("full", flat, 10.0, True)
    assert rc == 0 and c["first_pass"] and c["rebuilds"][0]["judge_missing"] == [], c
    # B1: R1 otherwise passing but its DRC count is missing -> FAIL (old code: PASS), slope still defined
    rc, c, _, _ = chain("no_drc", flat, 10.0, True, drop={9.0: ("route__drc_errors",)})
    r = c["rebuilds"][0]
    assert rc == 0 and not c["first_pass"] and r["outcome"] == "landed" and r["judge_missing"] == ["route__drc_errors"], c
    assert c["slope"] is not None and abs(c["slope"]) < 1e-12, c
    assert [x["clock_ns"] for x in c["rebuilds"]] == [9.0, 9.05] and c["kept_clock_ns"] == 9.05, c   # step back passes
    # B2: missing slew count -> FAIL
    rc, c, _, _ = chain("no_slew", flat, 10.0, True, drop={9.0: ("design__max_slew_violation__count",)})
    assert not c["first_pass"] and c["rebuilds"][0]["judge_missing"] == ["design__max_slew_violation__count"], c
    # B3: the worker left neither metrics nor a job record at R1 -> infrastructure loss: no chain.json, exit 3
    rc, c, top, _ = chain("lost", flat, 10.0, True, lost_at=(9.0,))
    part = json.load(open(os.path.join(top, "chain_partial.json")))
    assert rc == 3 and c is None and part["status"] == "infra_lost", (rc, c)
    assert json.load(open(os.path.join(top, "job.json")))["status"] == "chain_infra_lost"
    # B4: chain spec without its electrical bar -> refused before any build, no chain record
    rc, c, top, calls = chain("no_bar", flat, 10.0, True, bar=None)
    assert rc == 2 and c is None and calls == [] and not os.path.exists(os.path.join(top, "chain_partial.json"))
    # B5: a flow failure WITH a job record stays a recorded flow failure (clarification 2 ii), not an infra loss
    def failing(cmd, *a, **k):
        spec = json.load(open(cmd[cmd.index("--job-spec") + 1]))
        d = os.path.join(cmd[cmd.index("--results") + 1], spec["tag"])
        os.makedirs(d, exist_ok=True)
        json.dump({"flow_exit": 2, "status": "flow_failed", "flow_completed": False}, open(os.path.join(d, "job.json"), "w"))
        return types.SimpleNamespace(returncode=1)
    RJ.subprocess.run = failing
    d = tempfile.mkdtemp(prefix="e_failclosed_chain_")
    spec = {"tag": "t-ff", "design": "d", "config": "c", "overrides": {"CLOCK_PERIOD": 7.0},
            "chain": {"T0": 7.0, "C0": 8.0, "source_pass": False, "drv_bar": 10, "max_rebuilds": 4}}
    with contextlib.redirect_stdout(io.StringIO()):
        rc = RJ.run_chain(spec, types.SimpleNamespace(results=d, jobs=4, pdk_root="/x", timeout=10))
    c = json.load(open(os.path.join(d, "t-ff", "chain.json")))
    assert rc == 0 and c["first_outcome"] == "no_metrics" and c["slope"] is None and c["kept_clock_ns"] is None, c
    assert [r["clock_ns"] for r in c["rebuilds"]] == [8.0, 8.05] and c["rebuilds"][0]["flow_exit"] == 2, c


# ---------------------------------------------------------------- C. chain writer admission
def part_c():
    d = tempfile.mkdtemp(prefix="e_failclosed_mc_")
    res, jobs = os.path.join(d, "results"), os.path.join(d, "jobs")
    os.makedirs(jobs)
    srcs = []
    for i, ws in enumerate((0.4, -0.3)):
        t = f"ers-fam-{i:02d}"
        os.makedirs(os.path.join(res, t))
        json.dump(dict(FULL, timing__setup__ws=ws), open(os.path.join(res, t, "metrics.json"), "w"))
        json.dump({"flow_completed": True, "flow_exit": 0}, open(os.path.join(res, t, "job.json"), "w"))
        json.dump({"tag": t, "design": "dd", "config": "cc", "overrides": {"CLOCK_PERIOD": 10.0}},
                  open(os.path.join(jobs, t + ".json"), "w"))
        srcs.append({"source": t, "T0": 10.0, "stock_drv_bar": 10, "ws0_record": ws})
    json.dump({"sources": srcs}, open(os.path.join(d, "sources.json"), "w"))
    out = os.path.join(d, "chains.json")
    args = ["--results", res, "--sources", os.path.join(d, "sources.json"), "--jobs-dir", jobs, "--chains-out", out]
    r = run([os.path.join(E_DIR, "make_chains.py")] + args)
    assert r.returncode == 0, r.stdout + r.stderr
    sp = [c["source_pass"] for c in json.load(open(out))["chains"]]
    assert sp == [True, False], sp
    # now the first source lacks its DRC count: not admitted, nothing written
    for f in os.listdir(jobs):
        if f.startswith("erk-"):
            os.remove(os.path.join(jobs, f))
    os.remove(out)
    m = json.load(open(os.path.join(res, "ers-fam-00", "metrics.json")))
    del m["route__drc_errors"]
    json.dump(m, open(os.path.join(res, "ers-fam-00", "metrics.json"), "w"))
    r = run([os.path.join(E_DIR, "make_chains.py")] + args)
    assert r.returncode == 1 and "NOT ADMITTED" in r.stdout, r.stdout + r.stderr
    assert not os.path.exists(out) and not [f for f in os.listdir(jobs) if f.startswith("erk-")]


# ---------------------------------------------------------------- D. predictor runner
def write_view(view, files):
    os.makedirs(view, exist_ok=True)
    for rel, text in files.items():
        os.makedirs(os.path.dirname(os.path.join(view, rel)), exist_ok=True)
        open(os.path.join(view, rel), "w").write(text)
    man = {"format": "E1.0", "files": {rel: {"bytes": os.path.getsize(os.path.join(view, rel)),
                                             "sha256": sha(os.path.join(view, rel))} for rel in files}}
    json.dump(man, open(os.path.join(view, "MANIFEST.json"), "w"))


def make_packets(root):
    lines = []
    for pid, kinds in (("RAAA01", ("rung1", "rung2")), ("RBBB02", ("rung1", "rung2")), ("RCCC03", ("rung2",))):
        for k in kinds:
            v = os.path.join(root, pid, k)
            write_view(v, {"contract.json": json.dumps({"packet_id": pid, "x": len(pid)})})
            lines.append(f"{sha(os.path.join(v, 'MANIFEST.json'))}  {pid}/{k}/MANIFEST.json")
    open(os.path.join(root, "..", "packets_manifest.sha256"), "w").write("\n".join(lines) + "\n")


ENTRY = '''import json, os
from helper import slope_of
HERE = os.path.dirname(os.path.abspath(__file__))
W = json.load(open(os.path.join(HERE, "w.json")))
def predict(run_dir):
    c = json.load(open(os.path.join(run_dir, "contract.json")))
    BODY
    return {"p_pass": W["p"], "call": "pass", "slope": slope_of(c), "kept_clock_ns": 10.0}
'''


def predictor_dir(body="pass", helper="def slope_of(c):\n    return 0.1 * c['x']\n"):
    d = tempfile.mkdtemp(prefix="e_failclosed_pred_src_")
    open(os.path.join(d, "entry.py"), "w").write(ENTRY.replace("BODY", body))
    open(os.path.join(d, "helper.py"), "w").write(helper)
    open(os.path.join(d, "w.json"), "w").write('{"p": 0.7}')
    open(os.path.join(d, "SUMS"), "w").write("".join(f"{sha(os.path.join(d, f))}  {f}\n"
                                                     for f in ("entry.py", "helper.py", "w.json")))
    return d


def rp(src, base, extra=(), deps=("helper.py", "w.json"), sums=True):
    pred = os.path.join(base, "pred")
    cmd = [os.path.join(E_DIR, "run_predictor.py"), "--module", os.path.join(src, "entry.py"),
           "--deps"] + [os.path.join(src, x) for x in deps] + \
          (["--sums", os.path.join(src, "SUMS")] if sums else []) + \
          ["--arm", "fx", "--packets", os.path.join(base, "packets"), "--pred", pred,
           "--packets-manifest", os.path.join(base, "packets_manifest.sha256")] + list(extra)
    r = run(cmd)
    out = os.path.join(pred, "fx")
    return r, (sorted(os.listdir(out)) if os.path.isdir(out) else None)


def fresh_base():
    base = tempfile.mkdtemp(prefix="e_failclosed_rp_")
    make_packets(os.path.join(base, "packets"))
    return base


def part_d():
    base = fresh_base()
    src = predictor_dir()
    r, files = rp(src, base)
    assert r.returncode == 0 and files == ["RAAA01.json", "RBBB02.json"], r.stdout + r.stderr
    rec = json.load(open(os.path.join(base, "pred", "fx", "RAAA01.json")))
    assert rec["p_pass"] == 0.7 and abs(rec["slope"] - 0.6) < 1e-12 and set(rec["deps_sha256"]) == {"entry.py", "helper.py", "w.json"}
    rcp = json.load(open(os.path.join(base, "predictor_runs", "fx", "receipt.json")))
    assert rcp["valid"] == rcp["expected"] == 2 and not rcp["errors"] and not rcp["guard_violations"], rcp
    # D2: a dependency without an expected digest refuses
    open(os.path.join(src, "SUMS2"), "w").write("".join(l for l in open(os.path.join(src, "SUMS")) if "helper.py" not in l))
    base = fresh_base()
    r, files = rp(src, base, deps=("helper.py", "w.json"), sums=False, extra=["--sums", os.path.join(src, "SUMS2")])
    assert r.returncode == 2 and files is None and "every dependency must be hashed" in r.stdout, r.stdout
    # D3: a changed dependency refuses
    s2 = predictor_dir()
    open(os.path.join(s2, "w.json"), "w").write('{"p": 0.9}')
    r, files = rp(s2, fresh_base())
    assert r.returncode == 2 and files is None and "mismatch" in r.stdout, r.stdout
    # D4: an error on one packet -> exit 1, nothing written to <pred>/<arm>/
    s3 = predictor_dir(body="if c['packet_id'] == 'RBBB02': raise RuntimeError('boom')")
    r, files = rp(s3, fresh_base())
    assert r.returncode == 1 and files is None, r.stdout + r.stderr
    #     ... unless --promote-errors (error records score as abstentions); exit code stays 1
    r, files = rp(s3, fresh_base(), extra=["--promote-errors"])
    assert r.returncode == 1 and files == ["RAAA01.json", "RBBB02.json"], r.stdout + r.stderr
    # D5: a missing main packet refuses (no silent skip)
    base = fresh_base()
    shutil.rmtree(os.path.join(base, "packets", "RBBB02", "rung2"))
    r, files = rp(src, base)
    assert r.returncode == 2 and files is None and "PACKET CHECK FAILED" in r.stdout, r.stdout
    # D6: a packet file changed after the manifest refuses
    base = fresh_base()
    open(os.path.join(base, "packets", "RAAA01", "rung2", "contract.json"), "a").write(" ")
    r, files = rp(src, base)
    assert r.returncode == 2 and files is None, r.stdout
    # D7: reading outside the allowed roots -> exit 1
    s4 = predictor_dir(body="open('/etc/hostname').read()")
    r, files = rp(s4, fresh_base())
    assert r.returncode == 1 and files is None and "guard" in (r.stdout + r.stderr), r.stdout + r.stderr
    # D8: non-deterministic predict() -> exit 1
    s5 = predictor_dir(body="W['p'] = round(W['p'] * 0.5, 6)")
    r, files = rp(s5, fresh_base())
    assert r.returncode == 1 and files is None, r.stdout + r.stderr
    # D9: an invalid output (p_pass 1.5) -> exit 1
    s6 = predictor_dir(body="W['p'] = 1.5")
    r, files = rp(s6, fresh_base())
    assert r.returncode == 1 and files is None, r.stdout + r.stderr
    # D10: a file next to the entry that is NOT listed cannot be imported (only verified copies are importable)
    s7 = predictor_dir(body="import sidecar")
    open(os.path.join(s7, "sidecar.py"), "w").write("X = 1\n")
    r, files = rp(s7, fresh_base())
    assert r.returncode == 1 and files is None and "sidecar" in (r.stdout + r.stderr), r.stdout + r.stderr


# ---------------------------------------------------------------- E. packet verifier
def make_packet(root, spef_nets=None, empty_corner=None, dump_hole=False):
    p = os.path.join(root, "RZZZ99", "rung2")
    os.makedirs(os.path.join(p, "nets"))
    os.makedirs(os.path.join(p, "layout", "spef"))
    json.dump({"source": {"claim_ns": 10.5, "target_ns": 10.0}, "chain": {"R1_ns": 10.5}},
              open(os.path.join(p, "contract.json"), "w"))
    json.dump({"timing__setup__ws": -0.5}, open(os.path.join(p, "metrics.json"), "w"))
    conn = {"n1": {"driver": "u1/X", "pins": ["u2/A"], "fanout": 1}, "n2": {"driver": "u2/X", "pins": ["u1/A"], "fanout": 1},
            "in0": {"driver": "PORT:in0", "pins": ["in0"], "fanout": 0}}
    json.dump({"nets": conn}, gzip.open(os.path.join(p, "nets", "connectivity.json.gz"), "wt"))
    with gzip.open(os.path.join(p, "nets", "postgrt.jsonl.gz"), "wt") as f:
        for i, n in enumerate(conn):
            caps = {c: 0.001 * (i + 1) for c in CORNERS}
            if dump_hole and n == "n2":
                caps["max_ss_100C_1v60"] = None
            f.write(json.dumps({"net": n, "net_cap_pf_by_corner": caps}) + "\n")
    with gzip.open(os.path.join(p, "layout", "final.def.gz"), "wt") as f:
        f.write("UNITS DISTANCE MICRONS 1000 ;\nCOMPONENTS 2 ;\n- u1 cellA ;\n- u2 cellB ;\nEND COMPONENTS\n"
                "NETS 3 ;\n- n1 ( u1 X ) ( u2 A ) ;\n- n2 ( u2 X ) ( u1 A ) ;\n- in0 ( PIN in0 ) ;\nEND NETS\n")
    for k, rc in enumerate(("min", "nom", "max")):
        nets = ("n1", "n2") if spef_nets is None else spef_nets.get(rc, ("n1", "n2"))
        body = "*SPEF \"x\"\n*T_UNIT 1 NS\n*C_UNIT 1 PF\n*R_UNIT 1 OHM\n*L_UNIT 1 HENRY\n\n*NAME_MAP\n*1 n1\n*2 n2\n\n"
        if rc != empty_corner:
            for n in nets:
                body += f"*D_NET *{n[1]} {0.002 * (k + 1):.4f}\n*CONN\n*END\n\n"
        with gzip.open(os.path.join(p, "layout", "spef", rc + ".spef.gz"), "wt") as f:
            f.write(body)


def verify(**kw):
    root = tempfile.mkdtemp(prefix="e_failclosed_vp_")
    make_packet(root, **kw)
    return run([os.path.join(E_DIR, "verify_packets.py"), root])


def part_e():
    r = verify()
    assert r.returncode == 0 and "min 2/2 (100.0%" in r.stdout, r.stdout + r.stderr
    r = verify(empty_corner="nom")           # units valid, no D_NET: the old subset test accepted this
    assert r.returncode == 1 and "SPEF nom: populated 0/2" in r.stdout, r.stdout
    r = verify(spef_nets={"max": ("n1",)})   # one wired net without parasitics at one corner
    assert r.returncode == 1 and "SPEF max: populated 1/2" in r.stdout, r.stdout
    r = verify(dump_hole=True)               # a dump row without a value at one corner
    assert r.returncode == 1 and "corner population 2/3" in r.stdout, r.stdout


def main():
    part_a()
    try:
        part_b()
    finally:
        RJ.subprocess.run = _REAL_RUN
    part_c()
    part_d()
    part_e()
    print("OK fail-closed fixture (judge, chain, chain writer, predictor runner, packet verifier)")


if __name__ == "__main__":
    main()
