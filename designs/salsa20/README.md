# salsa20: Salsa20 stream cipher core (ARX, 32-bit words, 8 parallel quarter-rounds) with 32-bit register API

Unmodified RTL copied (not symlinked) from https://github.com/efabless/openlane-ci-designs designs/salsa20 (commit 6676a20db8775e0ca9a6df099e807b4951b8da6f); upstream secworks/salsa20.
Author/copyright: Joachim Strombergson / Secworks Sweden AB (c) 2013.
License: **BSD-2-Clause (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `salsa20`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 38.0 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v1 sky130_fd_sc_hd: CLOCK_PERIOD 38, FP_CORE_UTIL 20, PL_TARGET_DENSITY 0.32, GPL/DPL_CELL_PADDING 4, MAX_FANOUT_CONSTRAINT 6, PL_RESIZER_HOLD_SLACK_MARGIN 0.25, heuristic diode insertion on input ports.

## Files

- `src/salsa20.v`  sha256 `1e150658f1eab9fead106d07b5375b8cb05e48e647ac991dc6e1f151a9580c34`
- `src/LICENSE`  sha256 `622f545fef7f4c01ff689ba25a49da383371a32f449857d33376601c4488f6e3`
