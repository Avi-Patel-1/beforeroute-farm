# p0ba4e7 rationale

The worst paths at T0 (0.51 to 0.68 ns) are register-to-register paths. Almost all start at i17576 and run through a comparator OR tree near the west edge, then split. One branch goes to the FSM mux bank at the bottom middle. The other goes through a buffer tree to the G09 data register muxes.

G13, G12 and G03 enter the same tree. Their I/O delay is 20% of the period, so these paths matter less as the clock tightens. The moves therefore work mainly through where the cells get placed.

**G03 W2.** The comparator reads G03. Its pins now spread over W y=165 to 260, while its logic is centred near y=180. Packing the pins at y=165 to 191 should pull the comparator and trunk cells closer together. Expected gain: shorter n1282, n1278 and n734, and shorter G03[12]/[9]/[8] input paths. Expected change: delay down about 0.01 to 0.03 ns on the top paths. Confidence 0.55.

**G09 S1.** Bits 25 to 28 sit on the W edge and bit 31 on the N edge. Because of this, the select buffer i5920 at (118,50) has to reach back up 220 to 243 um to registers i7912, i8840 and i18610 (slack 0.63 to 0.64). Packing all 32 bits at S x=43 to 72 should give a compact bank closer to the trunk. Expected change: shorter n2649 and n523, and delay down 0.02 to 0.1 ns on the branch-2 paths. G09[31] and G09[28] get longer, but they have 3 to 6 ns of slack. Confidence 0.55.

A linear placement-response model gave a small gain at every stiffness tried (+0.008 to +0.034 ns of worst slack). That is below the flow's noise, so overall confidence is modest.
