# y_huff: JPEG encoder Y-channel Huffman coder: wide 64x12-bit input, run-length/Huffman lookup, bit packing

Unmodified RTL copied (not symlinked) from https://github.com/efabless/openlane-ci-designs designs/y_huff (commit 6676a20db8775e0ca9a6df099e807b4951b8da6f); upstream OpenCores jpegencode (David Lundgren).
Author/copyright: David Lundgren (c) 2009.
License: **Permissive OpenCores-style notice (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `y_huff`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 11.35 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v1 sky130: CLOCK_PERIOD 11.35, FP_CORE_UTIL 25, FP_SIZING absolute DIE_AREA 0 0 700 700, GPL/DPL_CELL_PADDING 4, MAX_FANOUT_CONSTRAINT 6, heuristic diode insertion on input ports.

## Files

- `src/y_huff.v`  sha256 `6292ba953b7016f227cc331be4036b25bf1f88649c6ee6cb75507d02eaca67ea`
- `src/LICENSE`  sha256 `0f91e8e4bc39a67486e587fbb05531416752591a04f8dc60fd632c4390c0d683`
