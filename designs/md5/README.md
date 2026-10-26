# md5: MD5 hash core: 64-step round FSM with 32-bit adders, rotates and F/G/H/I functions

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/md5 (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)); upstream OpenCores systemcmd5 (Javier Castillo).
Author/copyright: Javier Castillo / OPENCORES.ORG (c) 2000.
License: **LGPL-2.1-or-later (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `md5`; single clock `clk`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 37.05 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v0.21 sky130_fd_sc_hd: CLOCK_PERIOD 37.05, FP_CORE_UTIL 35, PL_TARGET_DENSITY 0.40, SYNTH_MAX_FANOUT 6.

## Files

- `src/md5.v`  sha256 `dcf8dcd545883ee175a63bf032f1e9a26882cb021f78ed23e7968e66319b03e3`
- `src/LICENSE`  sha256 `4b6ec7e782703813b0f41ac38afa9da245bc72ef643d296f624e96b4bf62bf93`
