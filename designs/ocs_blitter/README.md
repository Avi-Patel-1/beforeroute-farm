# ocs_blitter: Amiga OCS blitter (Wishbone): DMA sequencing FSM, barrel shifters, minterm logic, fill/line modes

Unmodified RTL copied (not symlinked) from https://github.com/The-OpenROAD-Project/OpenLane designs/ocs_blitter (tag v0.21 (a6ac8cf836df4d776136a9d71b86bfa8e89aa695)); upstream Aleksander Osman's Amiga OCS blitter.
Author/copyright: Aleksander Osman (c) 2010.
License: **BSD-2-Clause (per source header)**; see `src/LICENSE` (the original notices are retained in the source headers).

Top module: `ocs_blitter`; single clock `CLK_I`; no macros or SRAM.

## Local LibreLane 3 config (`config_sky130.json`)

CLOCK_PERIOD 18.2 ns, FP_CORE_UTIL 35, PL_TARGET_DENSITY_PCT 45, farm PDN block.
Original flow settings for reference: OpenLane v0.21 sky130_fd_sc_hd: CLOCK_PERIOD 18.2, FP_CORE_UTIL 35, PL_TARGET_DENSITY 0.40, SYNTH_MAX_FANOUT 6.

## Files

- `src/ocs_blitter.v`  sha256 `7d3f0e4304b4a3afd1c0a7bd171cbc844e78f318dd7dcad6124b4af70490e574`
- `src/LICENSE`  sha256 `3e808d8165bd06ac091a6f01763b0942e0bffd33d3391b60bff1588ca72739d8`
