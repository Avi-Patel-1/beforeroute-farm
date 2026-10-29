#!/usr/bin/env python3
"""Addendum 34 gate for the ZipCPU divider (zipdiv): is a candidate RTL rewrite cycle-for-cycle equivalent to the original?

  (0) interface + synthesizability: Yosys reads the candidate as Verilog-2005, elaborates `zipdiv` with its default
      parameters, and its ports (names, directions, widths) and parameter defaults must equal the original's; `initial`
      blocks are rejected.
  (a) lockstep simulation (Verilator, uninitialised state randomised): original (renamed zipdiv_orig) and candidate driven
      by the same random stimulus on every input for >= --cycles cycles, in phases that respect the request protocol
      (i_wr only while idle), break it (i_wr at any time, held i_wr), reset mid-division, issue back-to-back requests and
      stress zero, negative and extreme operands; operands also change while no request is made. Every output
      (o_busy, o_valid, o_err, o_quotient, o_flags) is compared after every clock edge and again after every input change,
      from the first (synchronous) reset on. Harness check: every division requested while idle and not interrupted is
      compared, when o_valid rises, with a C reference (quotient; o_err for a zero divisor), for both modules; the run must
      complete enough divisions of each kind, or the stimulus is judged too weak.
  (c) bounded formal equivalence (SymbiYosys, ABC bmc3): outputs equal for every input sequence after a reset, up to the
      deepest depth that finishes within --formal-timeout. Reported, not required.
Exit status 0 only if (0) and (a) pass (the registered gate (i); the digest test (ii) is MD5's). Usage:
  python3 farm/rtl34/verify_zipdiv.py --orig designs/zipdiv/src/zipdiv.v --cand <file> --out <log> [--cycles N]
                                      [--formal-depth N] [--formal-timeout S] [--no-formal] [--work DIR]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify import run, tool  # noqa: E402  (tool lookup and subprocess helper shared with the MD5 gate)

LOG = []


def log(msg):
    LOG.append(msg)
    print(msg, flush=True)


# ------------------------------------------------------------------------------------------------ (0) interface

def interface(vfile, work, name):
    y = tool("yosys")
    js = os.path.join(work, f"{name}_ports.json")
    rc, out, err, _ = run([y, "-q", "-p", f"read_verilog {os.path.abspath(vfile)}; hierarchy -check -top zipdiv; proc; "
                           f"check -assert; write_json {js}"], work, timeout=600)
    if rc != 0:
        return None, None, (out + err)[-3000:]
    mods = json.load(open(js))["modules"]
    m = mods.get("zipdiv")
    if m is None:
        return None, None, f"no module named zipdiv after elaboration (got {sorted(mods)})"
    ports = {k: (v["direction"], len(v["bits"])) for k, v in m["ports"].items()}
    params = {k: int(v, 2) if re.fullmatch(r"[01]+", str(v)) else v for k, v in (m.get("parameter_default_values") or {}).items()}
    return ports, params, ""


# ------------------------------------------------------------------------------------------------ Verilator harness

TOP_V = r"""
module lockstep_top(input wire i_clk, input wire i_reset, input wire i_wr, input wire i_signed,
                    input wire [31:0] i_numerator, input wire [31:0] i_denominator,
                    output wire o_busy, output wire o_valid, output wire o_err, output wire [31:0] o_quotient,
                    output wire [3:0] o_flags,
                    output wire c_busy, output wire c_valid, output wire c_err, output wire [31:0] c_quotient,
                    output wire [3:0] c_flags);
  zipdiv_orig o(.i_clk(i_clk), .i_reset(i_reset), .i_wr(i_wr), .i_signed(i_signed), .i_numerator(i_numerator),
                .i_denominator(i_denominator), .o_busy(o_busy), .o_valid(o_valid), .o_err(o_err), .o_quotient(o_quotient),
                .o_flags(o_flags));
  zipdiv      c(.i_clk(i_clk), .i_reset(i_reset), .i_wr(i_wr), .i_signed(i_signed), .i_numerator(i_numerator),
                .i_denominator(i_denominator), .o_busy(c_busy), .o_valid(c_valid), .o_err(c_err), .o_quotient(c_quotient),
                .o_flags(c_flags));
endmodule
"""

MAIN_CPP = r"""
#include "Vlockstep_top.h"
#include "verilated.h"
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <vector>

static uint64_t s = 0x9E3779B97F4A7C15ull;
static inline uint64_t rnd() { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }
static inline bool chance(double p) { return (rnd() >> 11) * (1.0 / 9007199254740992.0) < p; }

static const uint32_t EDGE[] = {0u, 1u, 2u, 3u, 7u, 10u, 0xFFFFFFFFu, 0xFFFFFFFEu, 0x80000000u, 0x80000001u, 0x7FFFFFFFu,
                                0x7FFFFFFEu, 0x40000000u, 0xC0000000u, 0x00010000u, 0x0000FFFFu, 0xFFFF0000u, 0x55555555u,
                                0xAAAAAAAAu};
static uint32_t operand() {
  switch (rnd() % 8) {
    case 0: return EDGE[rnd() % (sizeof(EDGE) / sizeof(EDGE[0]))];
    case 1: return 1u << (rnd() % 32);                                  // powers of two
    case 2: return (uint32_t)(rnd() % 64);                              // small positive
    case 3: return (uint32_t)(-(int64_t)(rnd() % 64));                  // small negative
    case 4: return ((uint32_t)rnd()) >> (rnd() % 32);                   // random magnitude
    default: return (uint32_t)rnd();
  }
}

struct In { int reset, wr, sgn; uint32_t n, d; };
static Vlockstep_top* t;
static uint64_t cyc = 0;

static void set_in(const In& x) {
  t->i_reset = x.reset; t->i_wr = x.wr; t->i_signed = x.sgn; t->i_numerator = x.n; t->i_denominator = x.d;
}
static void tick() {            // inputs are applied while i_clk is low; one rising edge per cycle
  t->i_clk = 0; t->eval();
  t->i_clk = 1; t->eval();
  cyc++;
}
static bool same() {
  return t->o_busy == t->c_busy && t->o_valid == t->c_valid && t->o_err == t->c_err && t->o_quotient == t->c_quotient &&
         t->o_flags == t->c_flags;
}
static void dump(const char* why, const std::vector<In>& hist) {
  printf("MISMATCH (%s) at cycle %llu: orig busy=%d valid=%d err=%d quotient=%08x flags=%x  "
         "cand busy=%d valid=%d err=%d quotient=%08x flags=%x\n", why, (unsigned long long)cyc,
         t->o_busy, t->o_valid, t->o_err, t->o_quotient, t->o_flags, t->c_busy, t->c_valid, t->c_err, t->c_quotient, t->c_flags);
  size_t n = hist.size(), k = n > 40 ? n - 40 : 0;
  for (size_t i = k; i < n; i++)
    printf("  input[-%zu]: reset=%d wr=%d signed=%d numerator=%08x denominator=%08x\n", n - i, hist[i].reset, hist[i].wr,
           hist[i].sgn, hist[i].n, hist[i].d);
}
static uint32_t reference(uint32_t n, uint32_t d, int sgn) {
  if (!sgn) return n / d;
  int64_t a = (int32_t)n, b = (int32_t)d;
  return (uint32_t)(a / b);     // truncates toward zero; INT_MIN / -1 wraps to INT_MIN as in 32-bit hardware
}

int lockstep(uint64_t ncyc) {
  // per phase: request probability, requests only while idle?, reset probability, hold-request probability,
  //            signed probability, zero-divisor probability, operand churn probability while not requesting
  struct Ph { double wr; int idle_only; double rst, hold, sgn, zero, churn; const char* name; };
  const Ph P[] = {
    {0.50, 1, 0.0001, 0.00, 0.50, 0.03, 0.5, "protocol"},
    {1.00, 1, 0.0000, 0.00, 0.50, 0.03, 0.9, "back-to-back"},
    {0.05, 0, 0.0010, 0.20, 0.50, 0.05, 0.5, "requests at any time"},
    {0.30, 0, 0.0050, 0.40, 0.50, 0.10, 0.9, "requests and resets at any time"},
    {0.50, 1, 0.0100, 0.00, 0.50, 0.05, 0.5, "resets mid-division"},
    {0.50, 1, 0.0002, 0.00, 0.70, 0.30, 0.5, "zero divisors, signed extremes"}};
  const int NPH = sizeof(P) / sizeof(P[0]);
  std::vector<In> hist;
  In x{}; x.reset = 1; x.n = (uint32_t)rnd(); x.d = (uint32_t)rnd();
  int nfirst = 1 + (int)(rnd() % 3);
  for (int i = 0; i < nfirst; i++) { set_in(x); tick(); }           // first reset: compare from here on
  if (!same()) { dump("after the first reset", hist); return 1; }
  struct { bool on; uint32_t n, d; int sgn; } pend = {false, 0, 0, 0};
  uint64_t checked = 0, resets = 0, wr = 0, wr_busy = 0, valids = 0, errs = 0;
  uint64_t ref_ok = 0, ref_signed_neg = 0, ref_zero = 0, ref_extreme = 0;
  int phase = 0, rst_left = 0, hold_left = 0;
  for (uint64_t i = 0; i < ncyc; i++) {
    if (i % 4000 == 0) phase = (int)(rnd() % NPH);
    const Ph& p = P[phase];
    bool idle = !t->o_busy;
    // request
    int req = 0;
    if (hold_left > 0) { req = 1; hold_left--; }
    else if ((!p.idle_only || idle) && chance(p.wr)) { req = 1; if (chance(p.hold)) hold_left = 1 + (int)(rnd() % 6); }
    x.wr = req;
    if (req) {
      x.n = operand(); x.d = chance(p.zero) ? 0u : operand(); x.sgn = chance(p.sgn);
      if (phase == 5 && chance(0.3)) { x.n = 0x80000000u; x.d = chance(0.5) ? 0xFFFFFFFFu : x.d; }
    } else {
      if (chance(p.churn)) x.n = (uint32_t)rnd();
      if (chance(p.churn)) x.d = (uint32_t)rnd();
      if (chance(p.churn)) x.sgn = (int)(rnd() & 1);
    }
    // synchronous reset, sometimes for several cycles
    if (rst_left > 0) { x.reset = 1; rst_left--; }
    else if (chance(p.rst)) { x.reset = 1; rst_left = (int)(rnd() % 3); resets++; }
    else x.reset = 0;
    // reference bookkeeping: a request made while idle (and not in reset) starts a clean division
    if (x.reset) pend.on = false;
    else if (x.wr) {
      wr++;
      if (idle) { pend.on = true; pend.n = x.n; pend.d = x.d; pend.sgn = x.sgn; }
      else { pend.on = false; wr_busy++; }
    }
    hist.push_back(x); if (hist.size() > 64) hist.erase(hist.begin());
    set_in(x); t->eval();
    if (!same()) { dump("after an input change, before the edge", hist); return 1; }
    tick();
    if (!same()) { dump("after the edge", hist); return 1; }
    checked++; valids += t->o_valid; errs += t->o_err;
    if (t->o_valid && pend.on) {
      uint32_t want = pend.d ? reference(pend.n, pend.d, pend.sgn) : 0;
      bool ok_o = pend.d ? (!t->o_err && t->o_quotient == want) : (t->o_err == 1);
      bool ok_c = pend.d ? (!t->c_err && t->c_quotient == want) : (t->c_err == 1);
      if (!ok_o || !ok_c) {
        printf("REFERENCE MISMATCH at cycle %llu: %s %08x / %08x: want %s%08x; orig err=%d quotient=%08x; cand err=%d "
               "quotient=%08x\n", (unsigned long long)cyc, pend.sgn ? "signed" : "unsigned", pend.n, pend.d,
               pend.d ? "" : "o_err (quotient not checked) ", want, t->o_err, t->o_quotient, t->c_err, t->c_quotient);
        return 3;
      }
      ref_ok++;
      if (!pend.d) ref_zero++;
      if (pend.sgn && ((pend.n >> 31) || (pend.d >> 31))) ref_signed_neg++;
      if (pend.n == 0x80000000u || pend.d == 0x80000000u || pend.d == 0xFFFFFFFFu) ref_extreme++;
      pend.on = false;
    }
  }
  printf("LOCKSTEP PASS: %llu cycles compared (outputs after every edge and every input change), %llu resets, %llu requests "
         "(%llu while busy), %llu o_valid pulses, %llu o_err cycles (orig)\n", (unsigned long long)checked,
         (unsigned long long)resets, (unsigned long long)wr, (unsigned long long)wr_busy, (unsigned long long)valids,
         (unsigned long long)errs);
  printf("REFERENCE PASS: %llu clean divisions matched the C reference in both modules (%llu signed with a negative operand, "
         "%llu zero divisors, %llu with -2^31 or -1 operands)\n", (unsigned long long)ref_ok,
         (unsigned long long)ref_signed_neg, (unsigned long long)ref_zero, (unsigned long long)ref_extreme);
  if (ref_ok < 1000 || ref_signed_neg < 100 || ref_zero < 20 || wr_busy < 1000 || resets < 100) {
    printf("STIMULUS TOO WEAK\n");
    return 2;
  }
  return 0;
}

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  t = new Vlockstep_top;
  if (argc > 2) s ^= strtoull(argv[2], 0, 10) * 0x9E3779B97F4A7C15ull;
  int rc = lockstep(strtoull(argv[1], 0, 10));
  t->final(); delete t;
  return rc;
}
"""


def build(orig, cand, work):
    src = open(orig).read()
    ren = re.sub(r"^(\s*)module(\s+)zipdiv\b", r"\1module\2zipdiv_orig", src, count=1, flags=re.M)
    if ren == src:
        raise SystemExit("could not rename the original module")
    open(os.path.join(work, "zipdiv_orig.v"), "w").write(ren)
    shutil.copy(cand, os.path.join(work, "zipdiv_cand.v"))
    open(os.path.join(work, "lockstep_top.v"), "w").write(TOP_V)
    open(os.path.join(work, "main.cpp"), "w").write(MAIN_CPP)
    v = tool("verilator")
    cmd = [v, "--cc", "--exe", "--build", "-j", "2", "-O2", "-Wno-fatal", "-Wno-lint", "-Wno-style", "-Wno-WIDTH",
           "-Wno-MULTIDRIVEN", "-Wno-COMBDLY", "-Wno-BLKSEQ", "-Wno-UNOPTFLAT", "-Wno-LATCH", "-Wno-CASEINCOMPLETE",
           "--x-assign", "unique", "--x-initial", "unique", "--top-module", "lockstep_top",
           "zipdiv_orig.v", "zipdiv_cand.v", "lockstep_top.v", "main.cpp", "-o", "sim"]
    rc, out, err, sec = run(cmd, work, timeout=1800)
    return rc == 0, (out + err)[-4000:], sec


# ------------------------------------------------------------------------------------------------ (c) formal

MITER_V = r"""
module miter(input wire i_clk, input wire i_reset, input wire i_wr, input wire i_signed,
             input wire [31:0] i_numerator, input wire [31:0] i_denominator);
  wire b1, v1, e1, b2, v2, e2; wire [31:0] q1, q2; wire [3:0] f1, f2;
  zipdiv_orig o(.i_clk(i_clk), .i_reset(i_reset), .i_wr(i_wr), .i_signed(i_signed), .i_numerator(i_numerator),
                .i_denominator(i_denominator), .o_busy(b1), .o_valid(v1), .o_err(e1), .o_quotient(q1), .o_flags(f1));
  zipdiv      c(.i_clk(i_clk), .i_reset(i_reset), .i_wr(i_wr), .i_signed(i_signed), .i_numerator(i_numerator),
                .i_denominator(i_denominator), .o_busy(b2), .o_valid(v2), .o_err(e2), .o_quotient(q2), .o_flags(f2));
  reg init = 1'b1;
  always @(posedge i_clk) init <= 1'b0;
  always @(*) begin
    if (init) assume (i_reset);
    if (!init) assert (b1 == b2 && v1 == v2 && e1 == e2 && q1 == q2 && f1 == f2);
  end
endmodule
"""


def formal(work, depth, timeout):
    """One SymbiYosys BMC run to --formal-depth under --formal-timeout; ABC bmc3 reports each frame it clears, so the
    deepest cleared frame is the depth proven even when the run is stopped by the timeout."""
    fdir = os.path.join(work, "formal")
    os.makedirs(fdir, exist_ok=True)
    open(os.path.join(fdir, "miter.sv"), "w").write(MITER_V)
    shutil.copy(os.path.join(work, "zipdiv_orig.v"), fdir)
    shutil.copy(os.path.join(work, "zipdiv_cand.v"), fdir)
    env = dict(os.environ)
    env["PATH"] = os.path.dirname(tool("yosys")) + os.pathsep + env.get("PATH", "")
    cfg = f"""[options]
mode bmc
depth {depth}
multiclock off

[engines]
abc bmc3

[script]
read_verilog zipdiv_orig.v
read_verilog zipdiv_cand.v
read_verilog -formal miter.sv
prep -top miter
async2sync

[files]
zipdiv_orig.v
zipdiv_cand.v
miter.sv
"""
    open(os.path.join(fdir, "bmc.sby"), "w").write(cfg)
    rc, o, e, sec = run([tool("sby"), "-f", "bmc.sby"], fdir, timeout=timeout, env=env)
    txt = ""
    lf = os.path.join(fdir, "bmc", "logfile.txt")
    if os.path.exists(lf):
        txt = open(lf).read()
    frames = [int(m.group(1)) for m in re.finditer(r"engine_0:\s+(\d+)\s+\+\s+:", txt)]
    deep = max(frames) if frames else None
    if rc is not None and rc != 0 and "FAIL" in txt:
        return f"FAIL: counterexample within {depth} cycles of reset (see {fdir}/bmc)"
    if rc == 0:
        return f"PASS: outputs equal for every input sequence up to {depth} cycles after reset ({sec:.0f} s)"
    return (f"no counterexample in frames 0..{deep} (cycles after reset); stopped after {sec:.0f} s" if deep is not None
            else f"not completed in {sec:.0f} s")


# ------------------------------------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--orig", required=True)
    ap.add_argument("--cand", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cycles", type=int, default=250000)
    ap.add_argument("--seed", type=int, default=34)
    ap.add_argument("--formal-depth", type=int, default=60)
    ap.add_argument("--formal-timeout", type=int, default=1800)
    ap.add_argument("--no-formal", action="store_true")
    ap.add_argument("--work", default=None)
    a = ap.parse_args()
    work = a.work or tempfile.mkdtemp(prefix="rtl34z_")
    os.makedirs(work, exist_ok=True)
    t0 = time.time()
    log(f"Addendum 34 gate (zipdiv): orig={a.orig} cand={a.cand} work={work} "
        f"time={time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}")
    log(f"  orig sha256 {hashlib.sha256(open(a.orig, 'rb').read()).hexdigest()}")
    log(f"  cand sha256 {hashlib.sha256(open(a.cand, 'rb').read()).hexdigest()}")
    verdict = {"interface": False, "lockstep": False, "formal": "not run"}
    if re.search(r"^\s*initial\b", open(a.cand).read(), re.M):
        log("(0) FAIL: the candidate has an initial block")
    else:
        po, pa_o, eo = interface(a.orig, work, "orig")
        pc, pa_c, ec = interface(a.cand, work, "cand")
        if po is None:
            log("(0) harness error: the original does not elaborate:\n" + eo)
        elif pc is None:
            log("(0) FAIL: Yosys could not elaborate the candidate as Verilog-2005:\n" + ec)
        elif po != pc:
            log(f"(0) FAIL: ports differ: orig {po} cand {pc}")
        elif pa_o != pa_c:
            log(f"(0) FAIL: parameters differ: orig {pa_o} cand {pa_c}")
        else:
            verdict["interface"] = True
            log(f"(0) PASS: Verilog-2005, elaborates, same ports {sorted(pc)} and parameters {pa_c}")
    if verdict["interface"]:
        ok, msg, sec = build(a.orig, a.cand, work)
        if not ok:
            log("Verilator build failed:\n" + msg)
        else:
            log(f"  Verilator build {sec:.0f} s")
            xr = ["+verilator+rand+reset+2", f"+verilator+seed+{a.seed}"]      # uninitialised state starts random
            rc, out, err, sec = run([os.path.join(work, "obj_dir", "sim"), str(a.cycles), str(a.seed)] + xr, work,
                                    timeout=3600)
            log("(a) " + (out.strip() or err.strip())[-4000:] + f"  [{sec:.0f} s]")
            verdict["lockstep"] = rc == 0
            if rc == 3:
                log("(a) harness error: the original disagrees with the C reference")
            if not a.no_formal and verdict["lockstep"]:
                log("(c) bounded formal equivalence (reported, not required) ...")
                verdict["formal"] = formal(work, a.formal_depth, a.formal_timeout)
                log("(c) " + verdict["formal"])
    ok = verdict["interface"] and verdict["lockstep"]
    log(f"VERDICT: {'PASS' if ok else 'FAIL'} {json.dumps(verdict)}  ({time.time() - t0:.0f} s)")
    open(a.out, "w").write("\n".join(LOG) + "\n")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
