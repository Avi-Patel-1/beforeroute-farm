# wbqspiflash: Wishbone quad-SPI flash controller (wbqspiflash + llqspi low-level port): large control FSM

Unmodified RTL copied (not symlinked) from https://github.com/efabless/openlane-ci-designs designs/wbqspiflash (commit 6676a20db8775e0ca9a6df099e807b4951b8da6f); upstream ZipCPU/qspiflash (Gisselquist Technology).
Author/copyright: Dan Gisselquist, Gisselquist Technology LLC (c) 2015-2019.
License: **LGPL-3.0-or-later (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `wbqspiflash`; single clock `i_clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 20.0 ns, FP_CORE_UTIL 40, PL_TARGET_DENSITY_PCT 50, farm PDN block.
Original flow settings for reference: OpenLane v1 sky130_fd_sc_hd: CLOCK_PERIOD 20, FP_CORE_UTIL 40, MAX_FANOUT_CONSTRAINT 4, SYNTH_STRATEGY DELAY 0, GPL/DPL_CELL_PADDING 4, DIODE_INSERTION_STRATEGY 6.

## Files

- `src/wbqspiflash.v`  sha256 `31c1f1b9d627a542379d59359149a33ba9b596afe43598297f1a67b07fff2d1f`
- `src/LICENSE`  sha256 `fb8343b50bca08e1124f9bfe83e798f83e66d0f26dc6cb1c71539e70a3db4d4e`
