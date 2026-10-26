# point_add: Elliptic-curve point addition over GF(3^97): GF(3^m) multiplier/cubic/inverse datapath, mostly XOR/AND logic

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/point_add (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)); upstream OpenCores Elliptic Curve Group core (Homer Hsing, City University of Hong Kong).
Author/copyright: City University of Hong Kong / Homer (Dongsheng) Hsing (c) 2011.
License: **LGPL-3.0-or-later (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `point_add`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 10.0 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v0.21 sky130_fd_sc_hd: CLOCK_PERIOD 10.0, FP_CORE_UTIL 25, PL_TARGET_DENSITY 0.30, SYNTH_MAX_FANOUT 5; in-file `define macros (M=97).

## Files

- `src/ecg.v`  sha256 `d62d104451c959ca9d9a93b506a6cdb5dff0016706d279ea13a67345cdeddaf7`
- `src/LICENSE`  sha256 `7cb43c0b1a84ad8078cf47f0630e49ef04164afd838ad5a6f59b16ebcb330ef2`
