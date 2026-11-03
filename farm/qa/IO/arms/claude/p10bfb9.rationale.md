# p10bfb9 rationale

At T0 the worst slack is reg-to-reg (0.533). Next is one input cone at 0.58-0.65: G04 bits (W edge),
G01 (N) and G09 (E). It runs comparator, or4 tree, decode, write-enable, mux select, data registers.
That cone is already upsized (or4_4, buf_6/8). The r2r paths still use buf_1 and clkbuf_1/2, so the
resizer has more headroom there. I expect the input cone to limit tighter clocks.

**G01 -> W2 (y=129.5).** Its only critical sink is i2224 (and3, ~(104,128)), at 0.590 ns. All other
loads have at least 0.99 ns. The sink is about 250 um from the pin today, through a buf_2 driving 85 fF.
After the move it is about 105 um away, level with the sink and beside the decode cone.
Expect the G01 path to gain 0.15-0.3 ns. Confidence 0.65.

**G09 -> W2 (y=164.9).** Its only critical sink is also i2224 (0.653 ns). Distance drops from about
190 um to about 140 um. The loads that get farther all have at least 1.48 ns of slack.
Expect a 0.05-0.15 ns gain. Confidence 0.55.

**G04 -> W2 (y=133.6-162.2).** The stock pins spread over y=143-208, and G04[0] sits on the N edge.
The critical comparator sinks are at y about 92-125. 17 of 20 pins move closer to their critical sink;
bits 14, 16 and 18 move 3-13 um away. The compare cone should become more compact.
Expect most G04 paths to gain 0.05-0.2 ns, with bit 14 about neutral. Confidence 0.5.

Side effect: G01, G09 and G04[0] stop pulling the upper-right control cluster. The r2r detour
(87,99) -> (182,169) -> (200,65) -> G08 registers may shorten slightly. Confidence 0.4.
CLK, G03, G08 and the outputs keep their stock pins; the outputs have 2-3.6 ns of slack.
