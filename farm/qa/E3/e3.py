#!/usr/bin/env python3
"""Addendum 40 / E3: correctness evidence for the accepted MD5 rewrite r2 against the original MD5 RTL.

  original : designs/md5/src/md5.v        (OpenCores MD5, as copied; the 15.50 ns build xao-md5-002)
  rewrite  : designs/md5_a34_r2/src/md5.v (Addendum 34 r2; the 8.85 ns headline build xam-md5-004)
  netlist  : farm/qa/E3/netlist/md5_xap-md5-003.nl.v.gz (routed netlist of xam-md5-004's spec, re-run as xap-md5-003)

Modes (run on a GitHub runner by .github/workflows/analyze.yml on branch qa-e3-md5; every mode writes into --out):
  formal   : unbounded equivalence proof attempts (SymbiYosys prove mode) on a miter of the two unmodified files
  controls : the same proof configurations on deliberately mutated rewrites (must not pass) and a BMC counterexample
  lockstep : random MD5-padded messages through both RTLs in one Verilator simulation: outputs compared every cycle,
             digests compared with Python hashlib, hash latency checked; then random-protocol lockstep cycles
  gate     : the routed netlist in Icarus Verilog with sky130_fd_sc_hd functional models, digests vs hashlib
Toolchains: "image" = the farm's pinned LibreLane image ($IMAGE, via docker; yosys/sby 0.62, bitwuzla, yosys-abc,
iverilog); "oss" = the OSS CAD Suite release unpacked at $OSS_CAD (yices); Verilator from the runner's apt.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import glob
import gzip
import hashlib
import json
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
ORIG = os.path.join(ROOT, "designs", "md5", "src", "md5.v")
CAND = os.path.join(ROOT, "designs", "md5_a34_r2", "src", "md5.v")
NETLIST_GZ = os.path.join(HERE, "netlist", "md5_xap-md5-003.nl.v.gz")
SHA = {"orig": "dcf8dcd545883ee175a63bf032f1e9a26882cb021f78ed23e7968e66319b03e3",
       "cand": "eb3b0b393c1be88f7625d511131ddb1cbb4b683814cbee98ebfbd8b0f3aaa411",
       "netlist": "7ceb289732fad332803a6e62f18b933689f5d7ad9861393ec992e7a7a7a4d6be"}

# deliberately broken rewrites (negative controls): (name, old text, new text); each old text occurs exactly once
MUTANTS = {
    "m1_const": ("37: tnf=32'hF6BB4B60;", "37: tnf=32'hF6BB4B61;"),          # one bit of one step constant (step 38)
    "m2_rot": ("4'd9:  rotf = {x[20:0],x[31:21]};", "4'd9:  rotf = {x[21:0],x[31:22]};"),  # rotate 11 -> 10
    "m3_ct": ("wire [31:0] Ct  = br + C;", "wire [31:0] Ct  = br ^ C;"),        # one output adder -> xor
}

EXPOSE_O = "message ar br cr dr A B C D getdata_state generate_hash round64 round".split()
EXPOSE_C = "message ar br cr dr A B C D getdata_state generate_hash round64 pre iq fc0 fc1".split()

T0 = time.time()


def sha256(path):
    return hashlib.sha256(open(path, "rb").read()).hexdigest()


def log(msg, fh=None):
    line = f"[{time.strftime('%H:%M:%SZ', time.gmtime())} +{time.time() - T0:7.0f}s] {msg}"
    print(line, flush=True)
    if fh:
        fh.write(line + "\n")
        fh.flush()


def check_sources():
    got = {"orig": sha256(ORIG), "cand": sha256(CAND)}
    for k in got:
        if got[k] != SHA[k]:
            raise SystemExit(f"{k} sha256 {got[k]} != registered {SHA[k]}")
    return got


def mutate(text, name):
    old, new = MUTANTS[name]
    if text.count(old) != 1:
        raise SystemExit(f"mutant {name}: pattern occurs {text.count(old)} times")
    return text.replace(old, new)


# ------------------------------------------------------------------------------------------- tool invocation

def image_cmd(workdir, argv):
    """Run argv inside the pinned LibreLane image with the repo mounted at /work (cwd = workdir)."""
    rel = os.path.relpath(os.path.abspath(workdir), ROOT)
    return ["docker", "run", "--rm", "-v", f"{ROOT}:/work", "-w", f"/work/{rel}", os.environ["IMAGE"],
            "python3", "/work/farm/qa/E3/e3.py", "_inner"] + argv


def inner(argv):
    """Inside the image: put yosys/yosys-abc/yosys-smtbmc, bitwuzla, iverilog on PATH and exec argv."""
    pats = {"sby": "/nix/store/*-yosys-sby-*/bin/sby", "yosys": "/nix/store/*-yosys-0.*/bin/yosys",
            "yosys-abc": "/nix/store/*-yosys-0.*/bin/yosys-abc", "yosys-smtbmc": "/nix/store/*-yosys-0.*/bin/yosys-smtbmc",
            "bitwuzla": "/nix/store/*-bitwuzla-*/bin/bitwuzla", "iverilog": "/nix/store/*-iverilog-*/bin/iverilog",
            "eqy": "/nix/store/*-yosys-eqy-*/bin/eqy"}
    dirs = []
    for name, pat in pats.items():
        p = shutil.which(name) or (sorted(glob.glob(pat)) or [None])[-1]
        if p:
            dirs.append(os.path.dirname(p))
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(dict.fromkeys(dirs)) + os.pathsep + env.get("PATH", "")
    exe = shutil.which(argv[0], path=env["PATH"]) or argv[0]
    os.execve(exe, [exe] + argv[1:], env)


def oss_env():
    env = dict(os.environ)
    oss = os.environ.get("OSS_CAD", "/tmp/oss-cad-suite")
    env["PATH"] = os.path.join(oss, "bin") + os.pathsep + env.get("PATH", "")
    return env


def run(cmd, cwd, logpath, timeout, env=None):
    t0 = time.time()
    with open(logpath, "w") as fh:
        try:
            p = subprocess.run(cmd, cwd=cwd, stdout=fh, stderr=subprocess.STDOUT, timeout=timeout, env=env)
            rc = p.returncode
        except subprocess.TimeoutExpired:
            rc = None
    return rc, time.time() - t0


def versions(out):
    """Tool versions actually used: inside the image (resolved like inner()) and the OSS CAD Suite, when present."""
    v = {"python": sys.version.split()[0], "image": os.environ.get("IMAGE", ""), "oss_release": os.environ.get("OSS_TAG", "")}
    probes = [("image_yosys", image_cmd(out, ["yosys", "-V"])), ("image_sby", image_cmd(out, ["sby", "--version"])),
              ("image_bitwuzla", image_cmd(out, ["bitwuzla", "--version"]))]
    oss = os.environ.get("OSS_CAD", "/tmp/oss-cad-suite")
    if os.path.isdir(oss):
        probes += [("oss_yosys", [os.path.join(oss, "bin", "yosys"), "-V"]), ("oss_sby", [os.path.join(oss, "bin", "sby"), "--version"]),
                   ("oss_yices", [os.path.join(oss, "bin", "yices-smt2"), "--version"])]
    for name, cmd in probes:
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300, env=oss_env() if name.startswith("oss") else None)
            v[name] = (r.stdout + r.stderr).strip().splitlines()[:2]
        except Exception as e:  # noqa: BLE001
            v[name] = f"error: {e}"
    return v


# ------------------------------------------------------------------------------------------- (a) formal

# proc -norom: elaborate constant case tables (the original's t ROM, the rewrite's tnf, the miter's K) as logic. With
# Yosys's default proc_rom they become $mem ROMs, whose contents the SMT model treats as state that is only initialised
# in the base case, so a k-induction step could pick arbitrary ROM contents (a spurious counterexample to induction).
SBY_SCRIPT = """[script]
read_verilog md5_orig.v
rename md5 md5_orig
read_verilog md5_cand.v
read_verilog -formal miter.sv
proc -norom
{expose}
prep -top miter

[files]
md5_orig.v
md5_cand.v
miter.sv
"""

# configuration -> (toolchain, mode, depth, engine line, miter)
CONFIGS = {
    "F1_kind_bitwuzla": ("image", "prove", 2, "smtbmc bitwuzla", "inv"),
    "F2_pdr": ("image", "prove", None, "abc pdr", "inv"),
    "F3_kind_yices": ("oss", "prove", 2, "smtbmc yices", "inv"),
    "F4_pdr_plain": ("image", "prove", None, "abc pdr", "plain"),
    "B_bmc_bitwuzla": ("image", "bmc", 10, "smtbmc bitwuzla", "inv"),
    # v2 (Nov 2, after the ROM fix): pre invariant stated with the original's own tr_var/nblock
    "G1_kind_bitwuzla": ("image", "prove", 2, "smtbmc bitwuzla", "inv2"),
    "G2_pdr": ("image", "prove", None, "abc pdr", "inv2"),
    "G3_kind_yices": ("oss", "prove", 2, "smtbmc yices", "inv2"),
    # decomposed proof: D1 lemma (one step from an unconstrained state) + D2 induction step
    "D1_lemma_bitwuzla": ("image", "bmc", 1, "smtbmc bitwuzla", "lemma"),
    "D1_lemma_yices": ("oss", "bmc", 1, "smtbmc yices", "lemma"),
    "D2_step_bitwuzla": ("image", "prove", 2, "smtbmc bitwuzla", "step"),
    "D2_step_yices": ("oss", "prove", 2, "smtbmc yices", "step"),
    "B2_bmc_bitwuzla": ("image", "bmc", 10, "smtbmc bitwuzla", "inv2"),
}
EXPOSE_EXTRA = {"inv": ([], []), "inv2": (["nblock", "tr_var"], []), "lemma": (["nblock", "tr_var", "aux31"], ["aux"]),
                "step": (["nblock", "tr_var", "aux31"], ["aux"])}


def sby_file(cfg, timeout):
    tc, mode, depth, engine, miter = CONFIGS[cfg]
    opts = [f"mode {mode}", "multiclock off", f"timeout {timeout}"]
    if depth:
        opts.append(f"depth {depth}")
    expose = ""
    if miter in EXPOSE_EXTRA:
        eo, ec = EXPOSE_EXTRA[miter]
        expose = ("expose " + " ".join(f"md5_orig/{w}" for w in EXPOSE_O + eo) + "\n" +
                  "expose " + " ".join(f"md5/{w}" for w in EXPOSE_C + ec))
    return "[options]\n" + "\n".join(opts) + f"\n\n[engines]\n{engine}\n\n" + SBY_SCRIPT.format(expose=expose)


def sby_task(name, cfg, cand_text, workroot, timeout):
    """One SymbiYosys run; returns a result dict. Status from sby's own status file/summary."""
    d = os.path.join(workroot, name)
    os.makedirs(d, exist_ok=True)
    shutil.copy(ORIG, os.path.join(d, "md5_orig.v"))           # byte-identical copy (module renamed by Yosys)
    open(os.path.join(d, "md5_cand.v"), "w").write(cand_text)
    miter = CONFIGS[cfg][4]
    shutil.copy(os.path.join(HERE, f"miter_{miter}.sv"), os.path.join(d, "miter.sv"))
    open(os.path.join(d, "e3.sby"), "w").write(sby_file(cfg, timeout))
    files = {f: sha256(os.path.join(d, f)) for f in ("md5_orig.v", "md5_cand.v", "miter.sv", "e3.sby")}
    tc = CONFIGS[cfg][0]
    argv = ["sby", "-f", "e3.sby"]
    if tc == "image":
        cmd, env = image_cmd(d, argv), None
    else:
        cmd, env = [os.path.join(os.environ.get("OSS_CAD", "/tmp/oss-cad-suite"), "bin", "sby"), "-f", "e3.sby"], oss_env()
    rc, sec = run(cmd, d, os.path.join(d, "sby_stdout.log"), timeout + 600, env)
    txt = open(os.path.join(d, "sby_stdout.log"), errors="replace").read()
    m = re.findall(r"DONE \((\w+), rc=(\d+)\)", txt)
    status = m[-1][0] if m else ("TIMEOUT" if rc is None else f"rc={rc}")
    res = {"name": name, "config": cfg, "toolchain": tc, "engine": CONFIGS[cfg][3], "mode": CONFIGS[cfg][1],
           "depth": CONFIGS[cfg][2], "miter": miter, "status": status, "rc": rc, "seconds": round(sec, 1), "files_sha256": files,
           "summary": [l for l in txt.splitlines() if re.search(r"summary:|DONE|Assert failed|failed assertion|Reached|induction|basecase|engine_0: Status|Checking assumptions|ERROR", l)][-40:]}
    for w in glob.glob(os.path.join(d, "e3", "engine_*", "*.vcd"))[:4]:
        res.setdefault("traces", []).append(os.path.relpath(w, workroot))
    log(f"{name}: {status} ({sec:.0f} s)")
    return res


def formal_mode(a):
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    srcs = check_sources()
    cand = open(CAND).read()
    names = a.configs.split(",")
    results, futs = [], {}
    with cf.ThreadPoolExecutor(max_workers=len(names)) as ex:
        for cfg in names:
            futs[ex.submit(sby_task, cfg, cfg, cand, os.path.join(out, "runs"), a.timeout)] = cfg
        first_pass = None
        pending = set(futs)
        while pending:
            done, pending = cf.wait(pending, timeout=30, return_when=cf.FIRST_COMPLETED)
            for f in done:
                r = f.result()
                results.append(r)
                if r["status"] == "PASS" and first_pass is None:
                    first_pass = time.time()
                    log(f"first PASS: {r['name']}; other configurations get at most {a.grace} s more")
            if first_pass and pending and time.time() - first_pass > a.grace:
                log("grace period over: stopping the remaining configurations")
                subprocess.run("docker ps -q | xargs -r docker kill", shell=True)
                subprocess.run(["pkill", "-f", "oss-cad-suite"], check=False)
    json.dump({"mode": "formal", "sources_sha256": srcs, "results": results, "versions": versions(out),
               "oss_release": os.environ.get("OSS_TAG", "")}, open(os.path.join(out, "formal.json"), "w"), indent=1)
    for r in results:
        print(r["name"], r["status"], r["seconds"])


def controls_mode(a):
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    srcs = check_sources()
    cand = open(CAND).read()
    jobs = []
    for spec in a.jobs.split(","):          # e.g. m1_const:F1_kind_bitwuzla
        mut, cfg = spec.split(":")
        jobs.append((f"{mut}__{cfg}", cfg, mutate(cand, mut)))
    results = []
    with cf.ThreadPoolExecutor(max_workers=a.parallel) as ex:
        for r in ex.map(lambda j: sby_task(j[0], j[1], j[2], os.path.join(out, "runs"), a.timeout), jobs):
            results.append(r)
    json.dump({"mode": "controls", "sources_sha256": srcs, "mutants": MUTANTS, "results": results, "versions": versions(out),
               "oss_release": os.environ.get("OSS_TAG", "")}, open(os.path.join(out, "controls.json"), "w"), indent=1)
    for r in results:
        print(r["name"], r["status"], r["seconds"])


# ------------------------------------------------------------------------------------------- stimulus

EDGE = [0, 1, 2, 3, 54, 55, 56, 57, 63, 64, 65, 118, 119, 120, 121, 127, 128, 129, 183, 184, 191, 192, 247, 248, 255,
        256, 311, 312, 319, 320, 375, 376, 383, 384, 439, 440, 446, 447]


def md5_blocks(msg: bytes):
    """MD5 padding; returns per block the 4 loads (each 4 words, data_i[127:96] first) and the expected data_o words."""
    ln = len(msg)
    pad = msg + b"\x80" + b"\x00" * ((55 - ln) % 64) + struct.pack("<Q", (8 * ln) & 0xFFFFFFFFFFFFFFFF)
    blocks = []
    for b in range(0, len(pad), 64):
        M = struct.unpack("<16I", pad[b:b + 64])
        blocks.append([M[4 * k: 4 * k + 4] for k in range(4)])     # load k carries M[4k] in bits [127:96]
    exp = struct.unpack("<4I", hashlib.md5(msg).digest())           # data_o = {A, B, C, D}
    return blocks, exp


def messages(n, seed, maxlen, edges=True):
    rng = random.Random(seed)
    for i in range(n):
        ln = EDGE[i] if (edges and i < len(EDGE) and EDGE[i] <= maxlen) else rng.randrange(0, maxlen + 1)
        msg = rng.randbytes(ln)
        idle = rng.randrange(0, 4)
        yield ln, idle, msg


# ------------------------------------------------------------------------------------------- (b1) lockstep

TOP_V = r"""
module lockstep_top(input clk, input reset, input load_i, input newtext_i, input [127:0] data_i,
                    output [127:0] o_data, output o_ready, output [127:0] c_data, output c_ready);
  md5_orig o(.clk(clk), .reset(reset), .load_i(load_i), .ready_o(o_ready), .newtext_i(newtext_i), .data_i(data_i), .data_o(o_data));
  md5      c(.clk(clk), .reset(reset), .load_i(load_i), .ready_o(c_ready), .newtext_i(newtext_i), .data_i(data_i), .data_o(c_data));
endmodule
"""


def build_lockstep(work, cand_text):
    os.makedirs(work, exist_ok=True)
    src = open(ORIG).read()
    ren = src.replace("module md5(", "module md5_orig(", 1)
    assert ren != src and ren.count("module md5_orig(") == 1
    open(os.path.join(work, "md5_orig.v"), "w").write(ren)
    open(os.path.join(work, "md5_cand.v"), "w").write(cand_text)
    open(os.path.join(work, "lockstep_top.v"), "w").write(TOP_V)
    shutil.copy(os.path.join(HERE, "lockstep.cpp"), os.path.join(work, "lockstep.cpp"))
    cmd = ["verilator", "--cc", "--exe", "--build", "-j", "4", "-O2", "-Wno-fatal", "-Wno-lint", "-Wno-style",
           "-Wno-WIDTH", "-Wno-MULTIDRIVEN", "-Wno-COMBDLY", "-Wno-BLKSEQ", "-Wno-UNOPTFLAT", "-Wno-LATCH",
           "-Wno-CASEINCOMPLETE", "--x-assign", "unique", "--x-initial", "unique", "--top-module", "lockstep_top",
           "md5_orig.v", "md5_cand.v", "lockstep_top.v", "lockstep.cpp", "-o", "sim"]
    rc, sec = run(cmd, work, os.path.join(work, "build.log"), 3600)
    if rc != 0:
        raise SystemExit("verilator build failed: " + open(os.path.join(work, "build.log")).read()[-3000:])
    return {f: sha256(os.path.join(work, f)) for f in ("md5_orig.v", "md5_cand.v", "lockstep_top.v", "lockstep.cpp")}


def feed_messages(proc, n, seed, maxlen, corrupt=None):
    """Write the binary stimulus to the simulator's stdin. Returns (messages, blocks, length histogram summary)."""
    w = proc.stdin
    w.write(b"E3M1" + struct.pack("<I", n))
    nblk_total, buf = 0, []
    for i, (ln, idle, msg) in enumerate(messages(n, seed, maxlen)):
        blocks, exp = md5_blocks(msg)
        if corrupt is not None and i == corrupt:
            exp = (exp[0] ^ 1,) + tuple(exp[1:])
        nblk_total += len(blocks)
        words = [len(blocks), idle]
        for blk in blocks:
            for ld in blk:
                words.extend(ld)
        words.extend(exp)
        buf.append(struct.pack(f"<{len(words)}I", *words))
        if len(buf) >= 2000:
            w.write(b"".join(buf))
            buf = []
    w.write(b"".join(buf))
    w.close()
    return n, nblk_total


def lockstep_shard(work, mode, n, seed, maxlen, corrupt=None, cycles=0):
    sim = os.path.join(work, "obj_dir", "sim")
    t0 = time.time()
    if mode == "messages":
        p = subprocess.Popen([sim, "messages", str(seed), "+verilator+rand+reset+2", f"+verilator+seed+{seed}"],
                             stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=work)
        nmsg, nblk = feed_messages(p, n, seed, maxlen, corrupt)
        outtxt = p.stdout.read().decode(errors="replace")
        rc = p.wait()
        res = {"mode": mode, "seed": seed, "messages_sent": nmsg, "blocks_sent": nblk, "maxlen": maxlen}
    else:
        r = subprocess.run([sim, "random", str(seed), str(cycles), "+verilator+rand+reset+2", f"+verilator+seed+{seed}"],
                           capture_output=True, text=True, cwd=work)
        outtxt, rc = r.stdout + r.stderr, r.returncode
        res = {"mode": mode, "seed": seed, "cycles_requested": cycles}
    m = re.search(r"^RESULT (\{.*\})$", outtxt, re.M)
    res.update({"rc": rc, "seconds": round(time.time() - t0, 1), "sim": json.loads(m.group(1)) if m else None,
                "tail": outtxt[-2500:]})
    return res


def lockstep_mode(a):
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    srcs = check_sources()
    vv = subprocess.run(["verilator", "--version"], capture_output=True, text=True).stdout.strip()
    log(f"verilator: {vv}")
    cand = open(CAND).read()
    real = os.path.join(out, "build_real")
    mut = os.path.join(out, "build_m1")
    files_real = build_lockstep(real, cand)
    files_mut = build_lockstep(mut, mutate(cand, "m1_const"))
    log("builds done")
    res = {"mode": "lockstep", "sources_sha256": srcs, "verilator": vv, "files_real": files_real, "files_m1": files_mut}
    seeds = [a.seed0 + i for i in range(a.shards)]
    per = a.messages // a.shards
    with cf.ThreadPoolExecutor(max_workers=a.shards) as ex:
        shards = list(ex.map(lambda s: lockstep_shard(real, "messages", per, s, a.maxlen), seeds))
    res["message_shards"] = shards
    log("message shards done: " + json.dumps([s["sim"] for s in shards]))
    # harness negative controls: the m1 mutant must be caught; a corrupted expected digest must be caught
    res["control_m1"] = lockstep_shard(mut, "messages", 2000, a.seed0 + 100, a.maxlen)
    res["control_corrupt"] = lockstep_shard(real, "messages", 50, a.seed0 + 101, a.maxlen, corrupt=17)
    log("controls done")
    if a.random_cycles:
        rs = [a.seed0 + 200 + i for i in range(a.shards)]
        with cf.ThreadPoolExecutor(max_workers=a.shards) as ex:
            res["random_shards"] = list(ex.map(lambda s: lockstep_shard(real, "random", 0, s, 0, cycles=a.random_cycles // a.shards), rs))
        log("random-protocol shards done")
    # verdict per the registered criterion A40b
    tot = {"messages": 0, "orig_ok": 0, "cand_ok": 0, "blocks": 0, "latency_bad": 0, "mismatch_cycles": 0, "cycles": 0}
    ok = True
    for s in shards:
        r = s["sim"] or {}
        if not r or s["rc"] != 0:
            ok = False
        for k in tot:
            tot[k] += r.get(k, 0)
        if r.get("messages") != s["messages_sent"] or r.get("blocks") != s["blocks_sent"]:
            ok = False
    ok = ok and tot["messages"] == per * a.shards and tot["orig_ok"] == tot["messages"] and tot["cand_ok"] == tot["messages"] \
        and tot["latency_bad"] == 0 and tot["mismatch_cycles"] == 0
    c1 = (res["control_m1"]["sim"] or {})
    c2 = (res["control_corrupt"]["sim"] or {})
    controls_ok = (c1.get("mismatch_cycles", 0) > 0 or c1.get("cand_ok", 0) < c1.get("messages", 1)) and \
                  (c2.get("cand_ok", 0) == c2.get("messages", 0) - 1 and c2.get("orig_ok", 0) == c2.get("messages", 0) - 1)
    rnd = res.get("random_shards", [])
    res["random_total"] = {"cycles": sum((s["sim"] or {}).get("cycles", 0) for s in rnd),
                           "mismatch_cycles": sum((s["sim"] or {}).get("mismatch_cycles", 0) for s in rnd),
                           "ready_pulses": sum((s["sim"] or {}).get("ready_pulses", 0) for s in rnd),
                           "resets": sum((s["sim"] or {}).get("resets", 0) for s in rnd),
                           "all_rc0": all(s["rc"] == 0 for s in rnd)}
    res["totals"] = tot
    res["verdict"] = {"A40b_messages_pass": ok, "harness_controls_detected": controls_ok}
    json.dump(res, open(os.path.join(out, "lockstep.json"), "w"), indent=1)
    log("VERDICT " + json.dumps(res["verdict"]) + " totals " + json.dumps(tot) + " random " + json.dumps(res["random_total"]))


# ------------------------------------------------------------------------------------------- (b2) gate level

GL_TB = r"""`timescale 1ns/1ps
module tb;
  reg clk = 0, reset = 0, load_i = 0, newtext_i = 0; reg [127:0] data_i = 0;
  wire ready_o; wire [127:0] data_o;
  md5 dut(.clk(clk), .reset(reset), .load_i(load_i), .newtext_i(newtext_i), .data_i(data_i), .ready_o(ready_o), .data_o(data_o));
  always #(%(half)s) clk = ~clk;
  integer f, nmsg, m, nblk, idle, b, w, k, i, ok, bad, seen, r, cycles, lat, latbad, xs, blocks;
  reg [31:0] d3, d2, d1, d0, e3, e2, e1, e0; reg [127:0] got;
  task tick; begin @(posedge clk); #(%(quarter)s); cycles = cycles + 1; end endtask
  reg [8*512-1:0] stim;
  initial begin
    if (!$value$plusargs("stim=%%s", stim)) begin $display("NO_STIM"); $finish; end
    f = $fopen(stim, "r"); r = $fscanf(f, "%%d", nmsg);
    cycles = 0; ok = 0; bad = 0; latbad = 0; xs = 0; blocks = 0;
    reset = 0; tick; tick; reset = 1;
    for (m = 0; m < nmsg; m = m + 1) begin
      r = $fscanf(f, "%%d %%d", nblk, idle);
      for (i = 0; i < idle; i = i + 1) begin load_i = 0; newtext_i = 0; tick; end
      newtext_i = 1; load_i = 0; tick; newtext_i = 0;
      for (b = 0; b < nblk; b = b + 1) begin
        for (w = 0; w < 4; w = w + 1) begin
          r = $fscanf(f, "%%h %%h %%h %%h", d3, d2, d1, d0);
          load_i = 1; data_i = {d3, d2, d1, d0}; tick;
        end
        load_i = 0; seen = 0; lat = 0;
        for (k = 0; k < 400 && !seen; k = k + 1) begin tick; if (ready_o === 1'b1) begin seen = 1; got = data_o; lat = k + 1; end end
        if (!seen) begin $display("NO_READY m=%%0d b=%%0d", m, b); $finish; end
        if (lat != 64) latbad = latbad + 1;
        blocks = blocks + 1;
      end
      r = $fscanf(f, "%%h %%h %%h %%h", e3, e2, e1, e0);
      if (^got === 1'bx) xs = xs + 1;
      if (got === {e3, e2, e1, e0}) ok = ok + 1;
      else begin bad = bad + 1; if (bad <= 10) $display("MISMATCH m=%%0d got %%h exp %%h", m, got, {e3, e2, e1, e0}); end
    end
    $display("RESULT messages %%0d ok %%0d bad %%0d latency_bad %%0d x_digests %%0d blocks %%0d cycles %%0d", nmsg, ok, bad, latbad, xs, blocks, cycles);
    $finish;
  end
endmodule
"""


def write_text_stim(path, n, seed, maxlen, corrupt=None):
    lines = [str(n)]
    nblk = 0
    for i, (ln, idle, msg) in enumerate(messages(n, seed, maxlen)):
        blocks, exp = md5_blocks(msg)
        if corrupt is not None and i == corrupt:
            exp = (exp[0] ^ 1,) + tuple(exp[1:])
        nblk += len(blocks)
        lines.append(f"{len(blocks)} {idle}")
        for blk in blocks:
            for ld in blk:
                lines.append(" ".join(f"{x:08x}" for x in ld))
        lines.append(" ".join(f"{x:08x}" for x in exp))
    open(path, "w").write("\n".join(lines) + "\n")
    return nblk


def find_models():
    hits = sorted(glob.glob(os.path.join(ROOT, "pdk", "**", "sky130_fd_sc_hd", "verilog", "sky130_fd_sc_hd.v"), recursive=True))
    if not hits:
        raise SystemExit("sky130_fd_sc_hd verilog models not found under pdk/")
    vdir = os.path.dirname(hits[0])
    return [os.path.join(vdir, "primitives.v"), os.path.join(vdir, "sky130_fd_sc_hd.v")]


def gate_mode(a):
    out = os.path.abspath(a.out)
    os.makedirs(out, exist_ok=True)
    nl = os.path.join(out, "md5.nl.v")
    with gzip.open(NETLIST_GZ, "rb") as fi, open(nl, "wb") as fo:
        fo.write(fi.read())
    nl_sha = sha256(nl)
    if nl_sha != SHA["netlist"]:
        raise SystemExit(f"netlist sha256 {nl_sha} != registered {SHA['netlist']}")
    models = find_models()
    res = {"mode": "gate", "netlist_sha256": nl_sha, "models": [os.path.relpath(m, ROOT) for m in models],
           "models_sha256": {os.path.basename(m): sha256(m) for m in models}, "clock_ns": a.clock}
    tbdir = os.path.join(out, "sim")
    os.makedirs(tbdir, exist_ok=True)

    def rel(p):
        return "/work/" + os.path.relpath(p, ROOT)

    # compile once (Icarus Verilog in the pinned image, the same flags as A35p/A36p), then one vvp per shard
    open(os.path.join(tbdir, "tb.v"), "w").write(GL_TB % {"half": f"{a.clock / 2:.4f}", "quarter": f"{a.clock / 4:.4f}"})
    cmd = image_cmd(tbdir, ["iverilog", "-g2005", "-DFUNCTIONAL", "-DUNIT_DELAY=#0.1", "-o", "sim.vvp", "tb.v", rel(nl)] +
                    [rel(m) for m in models])
    rc, sec = run(cmd, tbdir, os.path.join(tbdir, "iverilog.log"), 3600)
    res["compile"] = {"rc": rc, "seconds": round(sec, 1), "cmd": cmd[-12:], "tb_sha256": sha256(os.path.join(tbdir, "tb.v"))}
    log(f"iverilog rc={rc} ({sec:.0f} s)")
    if rc != 0:
        res["compile"]["log"] = open(os.path.join(tbdir, "iverilog.log")).read()[-3000:]
        json.dump(res, open(os.path.join(out, "gate.json"), "w"), indent=1)
        raise SystemExit("iverilog failed")

    def one(tag, n, seed, maxlen, corrupt=None):
        d = os.path.join(tbdir, tag)
        os.makedirs(d, exist_ok=True)
        stim = os.path.join(d, "stim.txt")
        nblk = write_text_stim(stim, n, seed, maxlen, corrupt)
        rc, sec = run(image_cmd(tbdir, ["vvp", "-n", "sim.vvp", f"+stim={rel(stim)}"]), tbdir, os.path.join(d, "vvp.log"), 5 * 3600)
        txt = open(os.path.join(d, "vvp.log"), errors="replace").read()
        m = re.search(r"RESULT messages (\d+) ok (\d+) bad (\d+) latency_bad (\d+) x_digests (\d+) blocks (\d+) cycles (\d+)", txt)
        r = {"tag": tag, "seed": seed, "messages_sent": n, "blocks_sent": nblk, "rc": rc, "seconds": round(sec, 1),
             "tail": txt[-1500:]}
        if m:
            r.update(dict(zip(["messages", "ok", "bad", "latency_bad", "x_digests", "blocks", "cycles"], map(int, m.groups()))))
        try:
            os.remove(stim)
        except OSError:
            pass
        log(f"gate {tag}: {json.dumps({k: r.get(k) for k in ('messages', 'ok', 'bad', 'latency_bad', 'x_digests', 'blocks', 'cycles', 'seconds')})}")
        return r

    seeds = [a.seed0 + i for i in range(a.shards)]
    per = a.messages // a.shards
    with cf.ThreadPoolExecutor(max_workers=a.shards) as ex:
        shards = list(ex.map(lambda s: one(f"shard_{s}", per, s, a.maxlen), seeds))
    res["shards"] = shards
    res["control_corrupt"] = one("control_corrupt", 3, a.seed0 + 100, a.maxlen, corrupt=1)
    tot = {k: sum(s.get(k, 0) for s in shards) for k in ("messages", "ok", "bad", "latency_bad", "x_digests", "blocks", "cycles")}
    ok = all("error" not in s and s.get("messages") == s["messages_sent"] and s.get("blocks") == s["blocks_sent"] for s in shards) \
        and tot["messages"] >= 1000 and tot["ok"] == tot["messages"] and tot["bad"] == 0 and tot["latency_bad"] == 0 \
        and tot["x_digests"] == 0
    c = res["control_corrupt"]
    res["totals"] = tot
    res["verdict"] = {"A40c_pass": ok, "harness_control_detected": c.get("bad") == 1 and c.get("ok") == 2}
    json.dump(res, open(os.path.join(out, "gate.json"), "w"), indent=1)
    os.remove(nl)
    log("VERDICT " + json.dumps(res["verdict"]) + " totals " + json.dumps(tot))


# ------------------------------------------------------------------------------------------- main

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "_inner":
        return inner(sys.argv[2:])
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["formal", "controls", "lockstep", "gate"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--data", default=None)                 # accepted for analyze.yml compatibility; unused
    ap.add_argument("--configs", default="F1_kind_bitwuzla,F2_pdr,F3_kind_yices")
    ap.add_argument("--jobs", default="")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--timeout", type=int, default=18000)
    ap.add_argument("--grace", type=int, default=1200)
    ap.add_argument("--messages", type=int, default=1000000)
    ap.add_argument("--shards", type=int, default=4)
    ap.add_argument("--seed0", type=int, default=40001)
    ap.add_argument("--maxlen", type=int, default=447)
    ap.add_argument("--random-cycles", type=int, default=0)
    ap.add_argument("--clock", type=float, default=8.85)
    ap.add_argument("--oss", action="store_true")           # tells the workflow to unpack the OSS CAD Suite
    ap.add_argument("--gate", action="store_true")          # tells the workflow to restore the PDK
    a = ap.parse_args()
    {"formal": formal_mode, "controls": controls_mode, "lockstep": lockstep_mode, "gate": gate_mode}[a.mode](a)


if __name__ == "__main__":
    main()
