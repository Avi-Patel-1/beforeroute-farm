# pdc9e8d: ABSTAIN

**Limiter.** WNS 5.78 ns (claim 5.93 ns) is on reg-to-output paths. All 64 bits of G06/G07 are buffered copies
of one flop, i394. The path is about 0.58 ns of clock latency, then clk-to-Q, then three buf_2 repeaters
(about 0.34 ns each at ss), then a Yosys buf_2, then a buf_1, then the clkbuf_4 port buffer. Wire is only about
0.09 ns of the 3.34 ns arrival. Reg-to-reg (about 4.22 ns) is mostly dlygate hold padding and doesn't depend on
the pins.

**Why no move.** repair_design's Steiner-junction fanout fix puts a repeater on the larger branch each time a merge
goes over 10 loads. For 65 loads this gives a depth of 3 at best, whatever the layout. A plain 2-arm line of about
32 loads per arm tends to reach depth 4 (+0.34 ns). The stock layout already packs the 64 outputs contiguously on E
(plus a 4-pin spill on S near the flop) and got depth 3.

**The legal alternatives:**
- Moving G06 and/or G07 to W adds a die-wide bridge net (+0.03-0.05 ns).
- G06 W2 + G07 E2 gives depth 3 but a longer root net.
- G02/G05 to W plus G06/G07 to S makes one 60 um line. That saves at most about 0.02 ns of wire and risks depth 4.

Every option's expected gain is below the 0.05 ns grid and the build-to-build chaos. G02/G04/G05 are unconnected,
G01 is a tie output, and G03 has 8.2 ns of slack.

**Expected effect:** the same result as the tool's pins. Confidence that no legal move would beat stock in
expectation: 0.65.
