# pbae019 rationale

**Move: G01 to S1** (32 pins, a run at x of about 31.5 to 60 um).

**Diagnosis.** At T0 the worst family (i469/i11659 to the G11 output flops, 0.48 ns) is inflated by
1.17 ns dlygate4sd3 hold buffers on the D pins of the bottom-right G11 flops. Those flops have about
1.65 ns of slack before the buffers. G11 bits with less setup room (bits 0-7) got their hold fixes on
the Q branch instead. At rebuild clocks of about 8.3 ns or less, this family should stop being critical.

The next family has no hold buffers. It runs from i4564 (and the inputs G15, G13 and G12) through the
match logic and the load-enable buffer tree to the 32 G01 register muxes, at 0.53-0.74 ns. Those
registers are split between the S and W edges. The enable tree spans about 510 um (MST) and its
critical leaf net is 80 fF.

**Expected effect.** The G01 muxes and flops cluster in one corner, so the enable tree shrinks to
roughly 150-250 um. Expected gain: about 0.1-0.25 ns on the i4564 and G15/G13/G12 paths to the G01
registers, since they share the tail. The G01 Q paths (2.7-5.3 ns slack) and input paths (3.2+ ns
slack) can absorb the longer wires. The comparator region and the G12 pins are left alone.

**Not moved.** G13, G15, G05, G03 and G12: their high-fanout nets sit about 100 um from every edge,
so pin position changes wire RC by under 0.01 ns. G11: moving it would cut its pre-buffer slack
from about 1.65 to 1.3 ns.

**Confidence:** enable-tail delay drops 0.6; better final clock 0.55.
