#!/usr/bin/env python3
"""Addendum 34 gate: is a candidate RTL rewrite of the MD5 engine cycle-for-cycle equivalent to the original?

  (0) interface + synthesizability: Yosys reads the candidate as Verilog-2005, elaborates `md5`, and its ports (names,
      directions, widths) must equal the original's; `initial` blocks are rejected.
  (a) lockstep simulation (Verilator, uninitialised state randomised): original (renamed md5_orig) and candidate driven by
      the same random stimulus on every input, including asynchronous resets, for >= --cycles cycles; data_o and ready_o
      are compared on every cycle after the first reset.
  (b) digests: >= --messages random messages (MD5-padded, 1..4 blocks) driven through the documented protocol
      (newtext_i, then 4 loads of 128 bits per block, then wait for ready_o); data_o when ready_o rises after the last
      block must equal Python's hashlib.md5 (both the original and the candidate are checked, which also tests the harness).
  (c) bounded formal equivalence (SymbiYosys, ABC bmc3, async reset modelled with async2sync): outputs equal for every
      input sequence up to the deepest depth that finishes within --formal-timeout. Reported, not required.
Exit status 0 only if (0), (a) and (b) pass. Usage:
  python3 farm/rtl34/verify.py --orig designs/md5/src/md5.v --cand <file> --out <log> [--cycles N] [--messages N]
                               [--formal-depth N] [--formal-timeout S] [--no-formal] [--work DIR]
"""
from __future__ import annotations

import argparse
import glob
import hashlib
import json
import os
import random
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import time


def tool(name):
    p = shutil.which(name)
    if p:
        return p
    pats = {"verilator": "/nix/store/*-verilator-5*/bin/verilator", "yosys": "/nix/store/*-yosys-0.62/bin/yosys",
            "sby": "/nix/store/*-yosys-sby-0.62/bin/sby"}
    hits = sorted(glob.glob(pats.get(name, "")))
    if not hits:
        raise SystemExit(f"{name} not found")
    return hits[-1]


LOG = []


def log(msg):
    LOG.append(msg)
    print(msg, flush=True)


def run(cmd, cwd, timeout=None, env=None):
    t0 = time.time()
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        return r.returncode, r.stdout, r.stderr, time.time() - t0
    except subprocess.TimeoutExpired as e:
        return None, (e.stdout or b"").decode() if isinstance(e.stdout, bytes) else (e.stdout or ""), "timeout", time.time() - t0


# ------------------------------------------------------------------------------------------------ (0) interface

def ports(vfile, work, name):
    y = tool("yosys")
    js = os.path.join(work, f"{name}_ports.json")
    rc, out, err, _ = run([y, "-q", "-p", f"read_verilog {os.path.abspath(vfile)}; hierarchy -check -top md5; proc; check -assert; "
                           f"write_json {js}"], work, timeout=600)
    if rc != 0:
        return None, (out + err)[-3000:]
    m = json.load(open(js))["modules"]["md5"]["ports"]
    return {k: (v["direction"], len(v["bits"])) for k, v in m.items()}, ""


# ------------------------------------------------------------------------------------------------ Verilator harness

TOP_V = r"""
module lockstep_top(input clk, input reset, input load_i, input newtext_i, input [127:0] data_i,
                    output [127:0] o_data, output o_ready, output [127:0] c_data, output c_ready);
  md5_orig o(.clk(clk), .reset(reset), .load_i(load_i), .ready_o(o_ready), .newtext_i(newtext_i), .data_i(data_i), .data_o(o_data));
  md5      c(.clk(clk), .reset(reset), .load_i(load_i), .ready_o(c_ready), .newtext_i(newtext_i), .data_i(data_i), .data_o(c_data));
endmodule
"""

MAIN_CPP = r"""
#include "Vlockstep_top.h"
#include "verilated.h"
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <string>

static uint64_t s = 0x9E3779B97F4A7C15ull;
static inline uint64_t rnd() { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }
static inline bool chance(double p) { return (rnd() >> 11) * (1.0 / 9007199254740992.0) < p; }

struct In { int reset, load, newtext; uint32_t d[4]; };

static Vlockstep_top* t;
static uint64_t cyc = 0;

static void set_in(const In& x) {
  t->reset = x.reset; t->load_i = x.load; t->newtext_i = x.newtext;
  for (int i = 0; i < 4; i++) t->data_i[i] = x.d[i];
}
static void tick() {            // inputs are applied while clk is low; one rising edge per cycle
  t->clk = 0; t->eval();
  t->clk = 1; t->eval();
  cyc++;
}
static bool same() {
  if (t->o_ready != t->c_ready) return false;
  for (int i = 0; i < 4; i++) if (t->o_data[i] != t->c_data[i]) return false;
  return true;
}
static void dump(const char* why, const std::vector<In>& hist) {
  printf("MISMATCH (%s) at cycle %llu: orig ready=%d data=%08x%08x%08x%08x  cand ready=%d data=%08x%08x%08x%08x\n", why,
         (unsigned long long)cyc, t->o_ready, t->o_data[3], t->o_data[2], t->o_data[1], t->o_data[0], t->c_ready,
         t->c_data[3], t->c_data[2], t->c_data[1], t->c_data[0]);
  size_t n = hist.size(), k = n > 12 ? n - 12 : 0;
  for (size_t i = k; i < n; i++)
    printf("  input[-%zu]: reset=%d load=%d newtext=%d data=%08x%08x%08x%08x\n", n - i, hist[i].reset, hist[i].load,
           hist[i].newtext, hist[i].d[3], hist[i].d[2], hist[i].d[1], hist[i].d[0]);
}

int lockstep(uint64_t ncyc) {
  // phases vary the stimulus statistics so that long hashes, interrupted hashes, back-to-back loads and resets all occur
  const double P[][4] = {  // load, newtext, reset, hold-newtext
    {0.35, 0.003, 0.0002, 0.0}, {0.90, 0.001, 0.0001, 0.0}, {0.10, 0.02, 0.0005, 0.3}, {1.00, 0.0, 0.0, 0.0},
    {0.50, 0.05, 0.002, 0.5}, {0.25, 0.0005, 0.00005, 0.0}};
  std::vector<In> hist;
  In x{}; x.reset = 0; set_in(x); tick(); tick();                   // initial reset (asynchronous, active low)
  x.reset = 1; set_in(x); t->eval();
  uint64_t checked = 0, resets = 0, readys = 0, newtexts = 0;
  int phase = 0, rst_left = 0, nt_left = 0;
  for (uint64_t i = 0; i < ncyc; i++) {
    if (i % 5000 == 0) phase = (int)(rnd() % 6);
    const double* p = P[phase];
    x.load = chance(p[0]);
    if (nt_left > 0) { x.newtext = 1; nt_left--; }
    else { x.newtext = chance(p[1]); if (x.newtext && chance(p[3])) nt_left = 1 + (int)(rnd() % 4); }
    for (int k = 0; k < 4; k++) x.d[k] = (uint32_t)rnd();
    if (rst_left > 0) { x.reset = 0; rst_left--; }
    else if (chance(p[2])) { x.reset = 0; rst_left = (int)(rnd() % 3); resets++; }
    else x.reset = 1;
    hist.push_back(x); if (hist.size() > 64) hist.erase(hist.begin());
    set_in(x); t->eval();                                         // asynchronous reset acts before the edge
    if (!same()) { dump("before edge", hist); return 1; }
    tick();
    if (!same()) { dump("after edge", hist); return 1; }
    checked++; readys += t->o_ready; newtexts += x.newtext;
  }
  printf("LOCKSTEP PASS: %llu cycles compared, %llu resets, %llu newtext cycles, %llu ready pulses (orig)\n",
         (unsigned long long)checked, (unsigned long long)resets, (unsigned long long)newtexts, (unsigned long long)readys);
  return readys > 100 ? 0 : 2;   // too few completed hashes = weak stimulus
}

int digests(const char* path) {
  FILE* f = fopen(path, "r");
  if (!f) { printf("no stimulus file\n"); return 1; }
  int nmsg; if (fscanf(f, "%d", &nmsg) != 1) return 1;
  In x{}; x.reset = 0; set_in(x); tick(); tick(); x.reset = 1; set_in(x); t->eval();
  int ok_o = 0, ok_c = 0;
  for (int m = 0; m < nmsg; m++) {
    int nblk, idle; uint32_t exp[4];
    if (fscanf(f, "%d %d", &nblk, &idle) != 2) return 1;
    for (int i = 0; i < idle; i++) { x.load = 0; x.newtext = 0; set_in(x); tick(); }
    x.newtext = 1; x.load = 0; set_in(x); tick(); x.newtext = 0;
    uint32_t got_o[4] = {0}, got_c[4] = {0};
    for (int b = 0; b < nblk; b++) {
      for (int w = 0; w < 4; w++) {
        uint32_t d[4];
        if (fscanf(f, "%x %x %x %x", &d[3], &d[2], &d[1], &d[0]) != 4) return 1;
        x.load = 1; for (int k = 0; k < 4; k++) x.d[k] = d[k]; set_in(x); tick();
      }
      x.load = 0; set_in(x);
      int seen_o = 0, seen_c = 0;
      for (int k = 0; k < 400 && !(seen_o && seen_c); k++) {
        tick();
        if (t->o_ready && !seen_o) { seen_o = 1; for (int i = 0; i < 4; i++) got_o[i] = t->o_data[i]; }
        if (t->c_ready && !seen_c) { seen_c = 1; for (int i = 0; i < 4; i++) got_c[i] = t->c_data[i]; }
      }
      if (!seen_o || !seen_c) { printf("DIGEST: message %d block %d: ready_o never rose (orig %d cand %d)\n", m, b, seen_o, seen_c); return 1; }
    }
    if (fscanf(f, "%x %x %x %x", &exp[3], &exp[2], &exp[1], &exp[0]) != 4) return 1;
    bool eo = !memcmp(got_o, exp, 16), ec = !memcmp(got_c, exp, 16);
    ok_o += eo; ok_c += ec;
    if (!ec || !eo) {
      printf("DIGEST MISMATCH message %d: expected %08x%08x%08x%08x orig %08x%08x%08x%08x cand %08x%08x%08x%08x\n", m,
             exp[3], exp[2], exp[1], exp[0], got_o[3], got_o[2], got_o[1], got_o[0], got_c[3], got_c[2], got_c[1], got_c[0]);
      return 1;
    }
  }
  printf("DIGEST PASS: %d of %d messages (orig %d, cand %d)\n", ok_c, nmsg, ok_o, ok_c);
  return 0;
}

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  t = new Vlockstep_top;
  std::string mode = argc > 1 ? argv[1] : "lockstep";
  if (argc > 3) s ^= strtoull(argv[3], 0, 10) * 0x9E3779B97F4A7C15ull;
  int rc = mode == "lockstep" ? lockstep(strtoull(argv[2], 0, 10)) : digests(argv[2]);
  t->final(); delete t;
  return rc;
}
"""


def build(orig, cand, work, seed):
    src = open(orig).read()
    ren = re.sub(r"\bmodule\s+md5\b", "module md5_orig", src, count=1)
    if ren == src:
        raise SystemExit("could not rename the original module")
    open(os.path.join(work, "md5_orig.v"), "w").write(ren)
    shutil.copy(cand, os.path.join(work, "md5_cand.v"))
    open(os.path.join(work, "lockstep_top.v"), "w").write(TOP_V)
    open(os.path.join(work, "main.cpp"), "w").write(MAIN_CPP)
    v = tool("verilator")
    cmd = [v, "--cc", "--exe", "--build", "-j", "2", "-O2", "-Wno-fatal", "-Wno-lint", "-Wno-style", "-Wno-WIDTH",
           "-Wno-MULTIDRIVEN", "-Wno-COMBDLY", "-Wno-BLKSEQ", "-Wno-UNOPTFLAT", "-Wno-LATCH", "-Wno-CASEINCOMPLETE",
           "--x-assign", "unique", "--x-initial", "unique", "--top-module", "lockstep_top",
           "md5_orig.v", "md5_cand.v", "lockstep_top.v", "main.cpp", "-o", "sim"]
    rc, out, err, sec = run(cmd, work, timeout=1800)
    return rc == 0, (out + err)[-4000:], sec


# ------------------------------------------------------------------------------------------------ (b) stimulus

def md5_words(msg: bytes):
    ln = len(msg)
    pad = msg + b"\x80" + b"\x00" * ((55 - ln) % 64) + struct.pack("<Q", (8 * ln) & 0xFFFFFFFFFFFFFFFF)
    assert len(pad) % 64 == 0
    blocks = []
    for b in range(0, len(pad), 64):
        M = [struct.unpack("<I", pad[b + 4 * i: b + 4 * i + 4])[0] for i in range(16)]
        blocks.append([M[4 * k: 4 * k + 4] for k in range(4)])   # load k carries M[4k] in bits [127:96]
    dg = hashlib.md5(msg).digest()
    exp = [struct.unpack("<I", dg[4 * i: 4 * i + 4])[0] for i in range(4)]   # data_o = {A, B, C, D}
    return blocks, exp


def stimulus(path, n, seed):
    rng = random.Random(seed)
    edge = [0, 1, 3, 55, 56, 57, 63, 64, 65, 119, 120, 128, 183, 184, 200, 247]
    lines = [str(n)]
    for i in range(n):
        ln = edge[i] if i < len(edge) else rng.randrange(0, 240)
        msg = bytes(rng.randrange(256) for _ in range(ln))
        blocks, exp = md5_words(msg)
        lines.append(f"{len(blocks)} {rng.randrange(0, 4)}")
        for blk in blocks:
            for w in blk:
                lines.append(" ".join(f"{x:08x}" for x in w))
        lines.append(" ".join(f"{x:08x}" for x in exp))
    open(path, "w").write("\n".join(lines) + "\n")


# ------------------------------------------------------------------------------------------------ (c) formal

MITER_V = r"""
module miter(input clk, input reset, input load_i, input newtext_i, input [127:0] data_i);
  wire [127:0] d1, d2; wire r1, r2;
  md5_orig o(.clk(clk), .reset(reset), .load_i(load_i), .ready_o(r1), .newtext_i(newtext_i), .data_i(data_i), .data_o(d1));
  md5      c(.clk(clk), .reset(reset), .load_i(load_i), .ready_o(r2), .newtext_i(newtext_i), .data_i(data_i), .data_o(d2));
  reg init = 1'b1;
  always @(posedge clk) init <= 1'b0;
  always @(*) begin
    if (init) assume (!reset);
    if (!init) assert (d1 == d2 && r1 == r2);
  end
endmodule
"""


def formal(work, depth, timeout):
    fdir = os.path.join(work, "formal")
    os.makedirs(fdir, exist_ok=True)
    open(os.path.join(fdir, "miter.sv"), "w").write(MITER_V)
    shutil.copy(os.path.join(work, "md5_orig.v"), fdir)
    shutil.copy(os.path.join(work, "md5_cand.v"), fdir)
    sby = tool("sby")
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(tool("yosys")) + os.pathsep + env.get("PATH", "")
    best, t0, out = 0, time.time(), ""
    for d in [k for k in (4, 8, 12, 16, 24, 32, 48, 64, 80) if k <= depth]:
        left = timeout - (time.time() - t0)
        if left < 30:
            break
        cfg = f"""[options]
mode bmc
depth {d}
multiclock off

[engines]
abc bmc3

[script]
read_verilog md5_orig.v
read_verilog md5_cand.v
read_verilog -formal miter.sv
prep -top miter
async2sync

[files]
md5_orig.v
md5_cand.v
miter.sv
"""
        open(os.path.join(fdir, f"d{d}.sby"), "w").write(cfg)
        rc, o, e, sec = run([sby, "-f", f"d{d}.sby"], fdir, timeout=left, env=env)
        st = "timeout" if rc is None else ("PASS" if rc == 0 else "FAIL")
        log(f"  formal bmc depth {d}: {st} ({sec:.0f} s)")
        if st != "PASS":
            if st == "FAIL":
                return f"FAIL at depth <= {d} (see {fdir}/d{d})"
            break
        best = d
    return f"no mismatch up to depth {best} (cycles from reset)" if best else "not completed"


# ------------------------------------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig", required=True)
    ap.add_argument("--cand", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cycles", type=int, default=250000)
    ap.add_argument("--messages", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=34)
    ap.add_argument("--formal-depth", type=int, default=80)
    ap.add_argument("--formal-timeout", type=int, default=1800)
    ap.add_argument("--no-formal", action="store_true")
    ap.add_argument("--work", default=None)
    a = ap.parse_args()
    work = a.work or tempfile.mkdtemp(prefix="rtl34_")
    os.makedirs(work, exist_ok=True)
    t0 = time.time()
    log(f"Addendum 34 gate: orig={a.orig} cand={a.cand} work={work} time={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    log(f"  orig sha256 {hashlib.sha256(open(a.orig, 'rb').read()).hexdigest()}")
    log(f"  cand sha256 {hashlib.sha256(open(a.cand, 'rb').read()).hexdigest()}")
    verdict = {"interface": False, "lockstep": False, "digests": False, "formal": "not run"}
    # (0)
    if re.search(r"^\s*initial\b", open(a.cand).read(), re.M):
        log("(0) FAIL: the candidate has an initial block")
    else:
        po, eo = ports(a.orig, work, "orig")
        pc, ec = ports(a.cand, work, "cand")
        if pc is None:
            log("(0) FAIL: Yosys could not elaborate the candidate as Verilog-2005:\n" + ec)
        elif po != pc:
            log(f"(0) FAIL: ports differ: orig {po} cand {pc}")
        else:
            verdict["interface"] = True
            log(f"(0) PASS: Verilog-2005, elaborates, same ports {sorted(pc)}")
    if verdict["interface"]:
        ok, msg, sec = build(a.orig, a.cand, work, a.seed)
        if not ok:
            log("Verilator build failed:\n" + msg)
        else:
            log(f"  Verilator build {sec:.0f} s")
            rc, out, err, sec = run([os.path.join(work, "obj_dir", "sim"), "lockstep", str(a.cycles), str(a.seed)], work,
                                    timeout=3600)
            log("(a) " + (out.strip() or err.strip())[-3000:] + f"  [{sec:.0f} s]")
            verdict["lockstep"] = rc == 0
            stim = os.path.join(work, "digests.txt")
            stimulus(stim, a.messages, a.seed)
            rc, out, err, sec = run([os.path.join(work, "obj_dir", "sim"), "digests", stim], work, timeout=3600)
            log("(b) " + (out.strip() or err.strip())[-3000:] + f"  [{sec:.0f} s]")
            verdict["digests"] = rc == 0
            if not a.no_formal and verdict["lockstep"] and verdict["digests"]:
                log("(c) bounded formal equivalence (reported, not required):")
                verdict["formal"] = formal(work, a.formal_depth, a.formal_timeout)
                log("(c) " + verdict["formal"])
    ok = verdict["interface"] and verdict["lockstep"] and verdict["digests"]
    log(f"VERDICT: {'PASS' if ok else 'FAIL'} {json.dumps(verdict)}  ({time.time() - t0:.0f} s)")
    open(a.out, "w").write("\n".join(LOG) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
