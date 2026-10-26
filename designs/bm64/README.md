# bm64: Radix-16 Booth sequential multiplier, N=256-bit operands, 512-bit product

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/BM64 (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)); upstream M. A. Morris & Associates Booth multiplier.
Author/copyright: Michael A. Morris, dba M. A. Morris & Associates (c) 2010-2012.
License: **LGPL-2.1-or-later (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `BM64`; single clock `Clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 20.0 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v0.21 sky130_fd_sc_hd: CLOCK_PERIOD 20.0, FP_CORE_UTIL 18, PL_TARGET_DENSITY 0.23, SYNTH_MAX_FANOUT 6.

## Files

- `src/BM64.v`  sha256 `125db21d15d2949cb8d47dfd15289f1c0895f2dde54089f6a032ac7f7fdee666`
- `src/LICENSE`  sha256 `48d8c2ffea3ce23186cb1ce2aecbd1a7be397d0248070b6eb235917f85fe703a`
