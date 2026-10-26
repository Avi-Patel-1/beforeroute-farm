# y_dct: JPEG encoder Y-channel 8x8 DCT: constant-coefficient multipliers and adder trees

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/y_dct (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)); upstream OpenCores jpegencode (David Lundgren).
Author/copyright: David Lundgren (c) 2009.
License: **Permissive OpenCores-style notice (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `y_dct`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 20.52 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v0.21 sky130_fd_sc_hd: CLOCK_PERIOD 20.52, FP_CORE_UTIL 20, PL_TARGET_DENSITY 0.25, SYNTH_ADDER_TYPE FA.

## Files

- `src/y_dct.v`  sha256 `2d7839a2b86cf952b838abf234eea47b7149484107d5dcbeb3ebb1855a7950f1`
- `src/LICENSE`  sha256 `901304dc2a55fea62c2c4edf5f7ed1f4a4d2251b350c6cdd09cf388a49c99402`
