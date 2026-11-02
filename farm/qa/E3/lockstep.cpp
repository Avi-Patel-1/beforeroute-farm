// Addendum 40 / E3 lockstep harness: the original MD5 (renamed md5_orig) and the rewrite (md5) share every input;
// data_o and ready_o are compared before and after every clock edge.
//   sim messages <seed>        : binary stimulus on stdin (written by e3.py from Python hashlib):
//                                "E3M1", u32 n; per message u32 nblk, u32 idle, nblk*16 u32 load words
//                                (data_i[127:96] first), 4 u32 expected data_o words ([127:96] first)
//                                protocol: idle cycles, newtext_i for one cycle, per block 4 loads then wait for ready_o
//   sim random <seed> <cycles> : random stimulus on every input incl. asynchronous resets and interrupted hashes
//                                (the Addendum 34 gate's stimulus phases)
// Last line: RESULT {json}. Exit status 0 only if nothing mismatched.
#include "Vlockstep_top.h"
#include "verilated.h"
#include <cstdio>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <vector>
#include <string>

static Vlockstep_top* t;
static uint64_t cyc = 0, mismatch_cycles = 0;
static int printed = 0;

static uint64_t s = 0x9E3779B97F4A7C15ull;
static inline uint64_t rnd() { s ^= s << 13; s ^= s >> 7; s ^= s << 17; return s; }
static inline bool chance(double p) { return (rnd() >> 11) * (1.0 / 9007199254740992.0) < p; }

static void set_in(int reset, int load, int newtext, const uint32_t* d) {
  t->reset = reset; t->load_i = load; t->newtext_i = newtext;
  for (int i = 0; i < 4; i++) t->data_i[i] = d ? d[i] : 0;
}
static bool same() {
  if (t->o_ready != t->c_ready) return false;
  for (int i = 0; i < 4; i++) if (t->o_data[i] != t->c_data[i]) return false;
  return true;
}
static void report(const char* why) {
  mismatch_cycles++;
  if (printed++ < 10)
    printf("MISMATCH (%s) at cycle %llu: orig ready=%d data=%08x%08x%08x%08x  cand ready=%d data=%08x%08x%08x%08x\n", why,
           (unsigned long long)cyc, t->o_ready, t->o_data[3], t->o_data[2], t->o_data[1], t->o_data[0], t->c_ready,
           t->c_data[3], t->c_data[2], t->c_data[1], t->c_data[0]);
}
// one clock cycle with the inputs already set: compare (asynchronous reset acts before the edge), edge, compare
static void step() {
  t->eval();
  if (!same()) report("before edge");
  t->clk = 0; t->eval();
  t->clk = 1; t->eval();
  cyc++;
  if (!same()) report("after edge");
}

// initial reset cycles: not compared (before the first edge with reset low the registers hold their random power-up
// state, which differs between the two designs by construction); comparison starts once reset has acted
static void raw_tick() { t->eval(); t->clk = 0; t->eval(); t->clk = 1; t->eval(); cyc++; }

static bool rd(void* p, size_t n) { return fread(p, 1, n, stdin) == n; }

static int messages() {
  char magic[4]; uint32_t n;
  if (!rd(magic, 4) || memcmp(magic, "E3M1", 4) || !rd(&n, 4)) { printf("bad stimulus header\n"); return 1; }
  set_in(0, 0, 0, nullptr); raw_tick(); raw_tick();              // reset (active low) for two cycles
  set_in(1, 0, 0, nullptr);
  uint64_t msgs = 0, blocks = 0, orig_ok = 0, cand_ok = 0, latency_bad = 0, no_ready = 0, digest_bad_printed = 0;
  std::vector<uint32_t> w;
  for (uint32_t m = 0; m < n; m++) {
    uint32_t hdr[2];
    if (!rd(hdr, 8)) { printf("short stimulus at message %u\n", m); return 1; }
    uint32_t nblk = hdr[0], idle = hdr[1];
    w.resize(nblk * 16 + 4);
    if (!rd(w.data(), w.size() * 4)) { printf("short stimulus at message %u\n", m); return 1; }
    for (uint32_t i = 0; i < idle; i++) { set_in(1, 0, 0, nullptr); step(); }
    set_in(1, 0, 1, nullptr); step();
    uint32_t got_o[4] = {0}, got_c[4] = {0};
    for (uint32_t b = 0; b < nblk; b++) {
      for (int ld = 0; ld < 4; ld++) {
        const uint32_t* q = &w[b * 16 + ld * 4];
        uint32_t d[4] = {q[3], q[2], q[1], q[0]};                 // q[0] -> data_i[127:96]
        set_in(1, 1, 0, d); step();
      }
      set_in(1, 0, 0, nullptr);
      int lat_o = -1, lat_c = -1;
      for (int k = 0; k < 400 && (lat_o < 0 || lat_c < 0); k++) {
        step();
        if (t->o_ready && lat_o < 0) { lat_o = k + 1; for (int i = 0; i < 4; i++) got_o[i] = t->o_data[i]; }
        if (t->c_ready && lat_c < 0) { lat_c = k + 1; for (int i = 0; i < 4; i++) got_c[i] = t->c_data[i]; }
      }
      if (lat_o < 0 || lat_c < 0) {
        if (no_ready++ < 10) printf("NO_READY message %u block %u (orig %d cand %d)\n", m, b, lat_o, lat_c);
      }
      if (lat_o != 64 || lat_c != 64) latency_bad++;
      blocks++;
    }
    const uint32_t* e = &w[nblk * 16];
    uint32_t exp[4] = {e[3], e[2], e[1], e[0]};
    bool eo = !memcmp(got_o, exp, 16), ec = !memcmp(got_c, exp, 16);
    orig_ok += eo; cand_ok += ec; msgs++;
    if ((!eo || !ec) && digest_bad_printed++ < 10)
      printf("DIGEST MISMATCH message %u: expected %08x%08x%08x%08x orig %08x%08x%08x%08x cand %08x%08x%08x%08x\n", m,
             exp[3], exp[2], exp[1], exp[0], got_o[3], got_o[2], got_o[1], got_o[0], got_c[3], got_c[2], got_c[1], got_c[0]);
  }
  printf("RESULT {\"messages\": %llu, \"blocks\": %llu, \"orig_ok\": %llu, \"cand_ok\": %llu, \"latency_bad\": %llu, "
         "\"no_ready\": %llu, \"mismatch_cycles\": %llu, \"cycles\": %llu}\n",
         (unsigned long long)msgs, (unsigned long long)blocks, (unsigned long long)orig_ok, (unsigned long long)cand_ok,
         (unsigned long long)latency_bad, (unsigned long long)no_ready, (unsigned long long)mismatch_cycles,
         (unsigned long long)cyc);
  return (mismatch_cycles || orig_ok != msgs || cand_ok != msgs || latency_bad || no_ready) ? 1 : 0;
}

static int random_protocol(uint64_t ncyc) {
  const double P[][4] = {  // load, newtext, reset, hold-newtext (the Addendum 34 gate's phases)
    {0.35, 0.003, 0.0002, 0.0}, {0.90, 0.001, 0.0001, 0.0}, {0.10, 0.02, 0.0005, 0.3}, {1.00, 0.0, 0.0, 0.0},
    {0.50, 0.05, 0.002, 0.5}, {0.25, 0.0005, 0.00005, 0.0}};
  set_in(0, 0, 0, nullptr); raw_tick(); raw_tick();
  uint64_t resets = 0, readys = 0, newtexts = 0;
  int phase = 0, rst_left = 0, nt_left = 0;
  uint32_t d[4];
  for (uint64_t i = 0; i < ncyc; i++) {
    if (i % 5000 == 0) phase = (int)(rnd() % 6);
    const double* p = P[phase];
    int load = chance(p[0]), newtext, reset;
    if (nt_left > 0) { newtext = 1; nt_left--; }
    else { newtext = chance(p[1]); if (newtext && chance(p[3])) nt_left = 1 + (int)(rnd() % 4); }
    for (int k = 0; k < 4; k++) d[k] = (uint32_t)rnd();
    if (rst_left > 0) { reset = 0; rst_left--; }
    else if (chance(p[2])) { reset = 0; rst_left = (int)(rnd() % 3); resets++; }
    else reset = 1;
    set_in(reset, load, newtext, d); step();
    readys += t->o_ready; newtexts += newtext;
  }
  printf("RESULT {\"cycles\": %llu, \"mismatch_cycles\": %llu, \"resets\": %llu, \"newtext_cycles\": %llu, \"ready_pulses\": %llu}\n",
         (unsigned long long)cyc, (unsigned long long)mismatch_cycles, (unsigned long long)resets,
         (unsigned long long)newtexts, (unsigned long long)readys);
  return mismatch_cycles ? 1 : 0;
}

int main(int argc, char** argv) {
  Verilated::commandArgs(argc, argv);
  t = new Vlockstep_top;
  std::string mode = argc > 1 ? argv[1] : "messages";
  if (argc > 2) s ^= strtoull(argv[2], 0, 10) * 0x9E3779B97F4A7C15ull;
  int rc = mode == "random" ? random_protocol(strtoull(argv[3], 0, 10)) : messages();
  t->final(); delete t;
  return rc;
}
