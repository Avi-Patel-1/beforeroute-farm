# zipdiv: ZipCPU 32-bit signed/unsigned iterative integer divider

Unmodified RTL copied (not symlinked) from https://github.com/efabless/openlane-ci-designs designs/zipdiv (commit 6676a20db8775e0ca9a6df099e807b4951b8da6f); upstream ZipCPU/zipcpu rtl/core/div.v (Gisselquist Technology).
Author/copyright: Dan Gisselquist, Gisselquist Technology LLC (c) 2015-2018.
License: **GPL-3.0-or-later (per source header) -- NOT a permissive license**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `zipdiv`; single clock `i_clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 20.0 ns, FP_CORE_UTIL 40, PL_TARGET_DENSITY_PCT 50, farm PDN block.
Original flow settings for reference: OpenLane v1 sky130_fd_sc_hd: CLOCK_PERIOD 20, FP_CORE_UTIL 40, MAX_FANOUT_CONSTRAINT 6, SYNTH_STRATEGY DELAY 2.

## Files

- `src/zipdiv.v`  sha256 `58775b1ff9abf5d66876f65072a5d5d0199de3832d7850b6926fc35ac1bb6f61`
- `src/LICENSE`  sha256 `b31860601d5355714a82c5b43aa0acfe35e51e4be161daf9db772ce49c0d4243`
